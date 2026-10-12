"""
Member 4 - Fine-tune the cross-encoder on ESCI electronics (SO1).  Made for Colab (GPU).

Setup (master plan Section 5.2)
  base model   cross-encoder/ms-marco-MiniLM-L-6-v2, 1 output (logit) -> sigmoid = relevance 0..1
  loss         BCEWithLogitsLoss on soft labels E=1.0, S=0.1, C=0.01, I=0.0
  training     3 epochs, lr 2e-5, batch 32, max length 256, linear warmup 10%, seed 42,
               fp16 on GPU
  selection    after each epoch, NDCG@10 on DEV; the best epoch is saved to <out>/best/.
               The test split is never read by this script.

Colab layout (MyDrive/m4/):
  src/metrics.py, src/train_cross_encoder.py
  data/processed/esci_elec_train.parquet, data/processed/esci_elec_dev.parquet
Colab cells:
  from google.colab import drive; drive.mount('/content/drive')
  %cd /content/drive/MyDrive/m4
  !pip -q install transformers pandas pyarrow
  !python src/train_cross_encoder.py --limit 2000 --epochs 1 --out-dir models/smoke   # smoke test
  !python src/train_cross_encoder.py                                                 # full run

Outputs
  <out>/best/               HF model + tokenizer (load with sentence_transformers.CrossEncoder)
  <out>/train_report.json   settings, data sizes, dev metrics per epoch, best epoch, timings
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_linear_schedule_with_warmup)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import evaluate, summarize  # noqa: E402

M4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = M4_DIR / "data" / "processed"
BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class Collate:
    def __init__(self, tokenizer, max_length):
        self.tok, self.max_length = tokenizer, max_length

    def __call__(self, batch):
        q, p, y = zip(*batch)
        enc = self.tok(list(q), list(p), truncation="only_second", padding=True,
                       max_length=self.max_length, return_tensors="pt")
        enc["labels"] = torch.tensor(y, dtype=torch.float32)
        return enc


@torch.no_grad()
def score(model, df, collate, batch_size, device, use_amp):
    model.eval()
    rows = list(zip(df["query"], df["product_text"], df["label"]))
    out = []
    for batch in DataLoader(rows, batch_size=batch_size, shuffle=False, collate_fn=collate):
        batch.pop("labels")
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
            out.append(model(**batch).logits.float().view(-1).cpu())
    model.train()
    return torch.cat(out).numpy()


def dev_metrics(model, dev, collate, args, device, use_amp):
    s = score(model, dev, collate, args.eval_batch_size, device, use_amp)
    return summarize(evaluate(dev.assign(score=s), "score", seed=args.seed))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out-dir", type=Path, default=M4_DIR / "models" / "cross_encoder")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--eval-batch-size", type=int, default=128)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--warmup", type=float, default=0.1)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0,
                    help="smoke test: use only the first N train rows (by query) and ~N/5 dev rows")
    ap.add_argument("--no-fp16", action="store_true")
    args = ap.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda" and not args.no_fp16
    print(f"device={device} fp16={use_amp}")

    train = pd.read_parquet(args.data_dir / "esci_elec_train.parquet")
    dev = pd.read_parquet(args.data_dir / "esci_elec_dev.parquet")
    if args.limit:
        def head_by_query(d, n):
            q = d.query_id.drop_duplicates().sample(frac=1, random_state=args.seed)
            size = d.groupby("query_id").size().reindex(q)
            return d[d.query_id.isin(q[size.cumsum().values <= n])]
        train, dev = head_by_query(train, args.limit), head_by_query(dev, max(200, args.limit // 5))
    print(f"train {len(train):,} rows / {train.query_id.nunique():,} queries; "
          f"dev {len(dev):,} rows / {dev.query_id.nunique():,} queries")

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=1).to(device)
    collate = Collate(tok, args.max_length)

    rows = list(zip(train["query"], train["product_text"], train["label"].astype(float)))
    g = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(rows, batch_size=args.batch_size, shuffle=True, collate_fn=collate,
                        generator=g)
    steps = len(loader) * args.epochs
    no_decay = ["bias", "LayerNorm.weight", "layernorm", "norm.weight"]
    params = [
        {"params": [p for n, p in model.named_parameters()
                    if not any(nd in n for nd in no_decay)], "weight_decay": args.weight_decay},
        {"params": [p for n, p in model.named_parameters()
                    if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]
    opt = torch.optim.AdamW(params, lr=args.lr)
    sched = get_linear_schedule_with_warmup(opt, int(args.warmup * steps), steps)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    report = {"settings": {k: str(v) for k, v in vars(args).items()},
              "device": str(device), "fp16": use_amp,
              "versions": {"torch": torch.__version__,
                           "transformers": __import__("transformers").__version__},
              "data": {"train_rows": len(train), "train_queries": int(train.query_id.nunique()),
                       "dev_rows": len(dev), "dev_queries": int(dev.query_id.nunique())},
              "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "epochs": []}
    args.out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    m0 = dev_metrics(model, dev, collate, args, device, use_amp)
    print(f"epoch 0 (no fine-tuning) dev: {m0}")
    report["epochs"].append({"epoch": 0, "dev": m0})
    best = -1.0

    model.train()
    for epoch in range(1, args.epochs + 1):
        te, total, n = time.perf_counter(), 0.0, 0
        for i, batch in enumerate(loader, 1):
            labels = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                logits = model(**batch).logits.view(-1)
            loss = loss_fn(logits.float(), labels)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            total, n = total + loss.item(), n + 1
            if i % 200 == 0 or i == len(loader):
                print(f"epoch {epoch} step {i}/{len(loader)} loss {total / n:.4f}", flush=True)

        m = dev_metrics(model, dev, collate, args, device, use_amp)
        ep = {"epoch": epoch, "train_loss": round(total / n, 5), "dev": m,
              "minutes": round((time.perf_counter() - te) / 60, 1)}
        if m["ndcg@10"] > best:
            best = m["ndcg@10"]
            model.save_pretrained(args.out_dir / "best")
            tok.save_pretrained(args.out_dir / "best")
            ep["saved_as_best"] = True
            report["best_epoch"], report["best_dev"] = epoch, m
        report["epochs"].append(ep)
        print(f"epoch {epoch} dev: {m}{'  <- best, saved' if ep.get('saved_as_best') else ''}")
        (args.out_dir / "train_report.json").write_text(json.dumps(report, indent=2))

    report["total_minutes"] = round((time.perf_counter() - t0) / 60, 1)
    (args.out_dir / "train_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nbest epoch {report.get('best_epoch')} dev NDCG@10 {best:.4f}; "
          f"model in {args.out_dir / 'best'}")


if __name__ == "__main__":
    main()