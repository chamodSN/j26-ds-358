"""
Member 4 - Step 5: fine-tune a cross-encoder on ESCI electronics v2.3.

Loss    : BCEWithLogitsLoss, one logit per (query, product) pair, soft target = ESCI gain
          (E 1.0, S 0.1, C 0.01, I 0.0).
Formats : every train row, every epoch, gets one of the product_to_text styles at random
          (equal chance, seed 42 + epoch). Validation is scored separately in each style.
Query   : cfg['query_col'] picks the query input column (raw or focused query).
Saving  : <base>/models/<run>/epoch_<n>/ after each epoch (model + tokenizer, no optimizer);
          metrics appended to <base>/results/finetune_val_log.csv. Re-running resumes
          from the last saved epoch.
"""
import os, time, json, random, numpy as np, pandas as pd, torch
from torch.nn import BCEWithLogitsLoss
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup

STYLES = ["title", "title_brand", "full", "full_bullets", "key_value"]
CFG = dict(styles=STYLES, query_col="query", epochs=3, lr=2e-5, warmup=0.10, weight_decay=0.01, batch=32, accum=1,
           max_len=256, eval_batch=128, seed=42)

def set_seed(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)

def epoch_pairs(train, epoch, seed=42, styles=STYLES, query_col="query"):
    """One epoch: every train row once, shuffled, each with a random format (equal chance)."""
    rng = np.random.default_rng(seed + epoch)
    style = rng.choice(list(styles), size=len(train))
    text = np.empty(len(train), dtype=object)
    for s in styles:
        m = style == s
        text[m] = train[f"text_{s}"].values[m]
    order = rng.permutation(len(train))
    return (train[query_col].values[order], text[order],
            train["gain"].values[order].astype(np.float32), style[order])

@torch.no_grad()
def score_pairs(model, tok, queries, texts, max_len, bs, device="cuda"):
    model.eval()
    lens = np.array([len(q) + len(t) for q, t in zip(queries, texts)])
    order = np.argsort(lens)                       # similar lengths together = less padding
    out = np.empty(len(order), dtype=np.float32)
    for i in range(0, len(order), bs):
        idx = order[i:i + bs]
        enc = tok([queries[j] for j in idx], [texts[j] for j in idx], truncation=True,
                  max_length=max_len, padding=True, return_tensors="pt").to(device)
        with torch.autocast(device_type=device, dtype=torch.float16, enabled=(device == "cuda")):
            out[idx] = model(**enc).logits.squeeze(-1).float().cpu().numpy()
    return out

def eval_styles(model, tok, val, evaluate, cfg, device="cuda"):
    rows, perq = [], []
    q = val[cfg.get("query_col", "query")].tolist()
    for s in cfg.get("styles", STYLES):
        v = val[["query_id", "gain"]].copy()
        v["score"] = score_pairs(model, tok, q, val[f"text_{s}"].tolist(), cfg["max_len"], cfg["eval_batch"], device)
        m, pq = evaluate(v)
        rows.append({"style": s, **m}); perq.append(pq.assign(style=s))
    return rows, pd.concat(perq)

def train_run(model_name, run_name, train, val, evaluate, base, cfg=CFG, device="cuda", log_name="finetune_val_log.csv"):
    run_dir = f"{base}/models/{run_name}"; os.makedirs(run_dir, exist_ok=True)
    log_path = f"{base}/results/{log_name}"
    done = sorted(int(d.split("_")[1]) for d in os.listdir(run_dir) if d.startswith("epoch_"))
    start = done[-1] if done else 0
    if start >= cfg["epochs"]:
        print(run_name, "already finished"); return
    src = f"{run_dir}/epoch_{start}" if start else model_name
    print(f"{run_name}: starting at epoch {start + 1} from {src}")

    set_seed(cfg["seed"])
    tok = AutoTokenizer.from_pretrained(src)
    model = AutoModelForSequenceClassification.from_pretrained(src, num_labels=1, ignore_mismatched_sizes=True).to(device)
    micro = cfg["batch"] // cfg["accum"]
    steps_per_epoch = int(np.ceil(len(train) / cfg["batch"]))
    total = steps_per_epoch * cfg["epochs"]
    no_decay = ("bias", "LayerNorm.weight", "layer_norm.weight")
    params = [{"params": [p for n, p in model.named_parameters() if not any(k in n for k in no_decay)], "weight_decay": cfg["weight_decay"]},
              {"params": [p for n, p in model.named_parameters() if any(k in n for k in no_decay)], "weight_decay": 0.0}]
    opt = torch.optim.AdamW(params, lr=cfg["lr"])
    sched = get_linear_schedule_with_warmup(opt, int(cfg["warmup"] * total), total)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(start * steps_per_epoch): sched.step()      # resume: same LR position
    scaler = torch.amp.GradScaler("cuda", enabled=(device == "cuda"))
    loss_fn = BCEWithLogitsLoss()
    cum = 0.0
    if start and os.path.exists(log_path):
        old = pd.read_csv(log_path); old = old[(old.run == run_name) & (old.epoch <= start)]
        cum = float(old["cum_train_time_s"].max()) if len(old) else 0.0

    for ep in range(start + 1, cfg["epochs"] + 1):
        model.train(); t0 = time.time()
        qs, ts, ys, _ = epoch_pairs(train, ep, cfg["seed"], cfg.get("styles", STYLES), cfg.get("query_col", "query"))
        run_loss, n = 0.0, 0
        for b in range(0, len(qs), cfg["batch"]):
            bq, bt, by = qs[b:b + cfg["batch"]], ts[b:b + cfg["batch"]], ys[b:b + cfg["batch"]]
            for m0 in range(0, len(bq), micro):
                enc = tok(list(bq[m0:m0 + micro]), list(bt[m0:m0 + micro]), truncation=True,
                          max_length=cfg["max_len"], padding=True, return_tensors="pt").to(device)
                y = torch.tensor(by[m0:m0 + micro], device=device)
                with torch.autocast(device_type=device, dtype=torch.float16, enabled=(device == "cuda")):
                    logits = model(**enc).logits.squeeze(-1)
                loss = loss_fn(logits.float(), y) * (len(y) / len(by))
                scaler.scale(loss).backward()
                run_loss += loss.item()          # micro-losses add up to the batch-mean loss
            scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True); sched.step()
            n += 1
            if n % 500 == 0: print(f"  epoch {ep} step {n}/{steps_per_epoch} loss {run_loss / n:.4f}")
        train_time = time.time() - t0; cum += train_time
        ck = f"{run_dir}/epoch_{ep}"; model.save_pretrained(ck); tok.save_pretrained(ck)
        rows, perq = eval_styles(model, tok, val, evaluate, cfg, device)
        rec = [{"run": run_name, "model": model_name, "epoch": ep, **r, "train_loss": round(run_loss / n, 5),
                "epoch_train_time_s": round(train_time, 1), "cum_train_time_s": round(cum, 1),
                "batch": cfg["batch"], "accum": cfg["accum"], "resumed_from_epoch": start} for r in rows]
        pd.DataFrame(rec).to_csv(log_path, mode="a", header=not os.path.exists(log_path), index=False)
        perq.to_csv(f"{run_dir}/per_query_val_epoch_{ep}.csv", index=False)
        print(f"epoch {ep} done: loss {run_loss / n:.4f}, {train_time / 60:.1f} min")
        print(pd.DataFrame(rows).to_string(index=False))
    json.dump({**cfg, "model_name": model_name, "loss": "BCEWithLogitsLoss, soft targets = ESCI gain",
               "formats": f"random, equal chance per row per epoch, seed 42+epoch: {cfg.get('styles', STYLES)}",
               "query_input": cfg.get("query_col", "query")}, open(f"{run_dir}/train_config.json", "w"), indent=2)
    del model; torch.cuda.empty_cache()