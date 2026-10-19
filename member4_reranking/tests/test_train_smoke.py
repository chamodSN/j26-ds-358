import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np, pandas as pd
from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast
from metrics import evaluate
from train_cross_encoder import train_run, epoch_pairs, CFG, STYLES


def _data(n, q0, rng):
    g = rng.choice([1.0, 0.1, 0.01, 0.0], n)
    d = pd.DataFrame({"query_id": q0 + rng.integers(0, 10, n), "gain": g})
    d["query"] = "phone " + d["query_id"].astype(str)
    for s in STYLES:
        d[f"text_{s}"] = np.where(g >= 1, "samsung phone", "red case") + " " + s
    return d


def test_epoch_pairs_mix_and_seed():
    tr = _data(400, 0, np.random.default_rng(0))
    q1, t1, y1, s1 = epoch_pairs(tr, 1)
    q1b, _, _, s1b = epoch_pairs(tr, 1)
    _, _, _, s2 = epoch_pairs(tr, 2)
    assert (s1 == s1b).all() and not (s1 == s2).all()          # same seed = same draw; new epoch = new draw
    assert set(s1) == set(STYLES) and sorted(y1) == sorted(tr["gain"].astype(np.float32))


def test_train_and_resume(tmp_path):
    words = "[PAD] [UNK] [CLS] [SEP] [MASK] phone samsung red case title brand full bullets _".split()
    vocab = words + list("abcdefghijklmnopqrstuvwxyz0123456789")
    (tmp_path / "tiny").mkdir(); (tmp_path / "tiny" / "vocab.txt").write_text("\n".join(vocab))
    BertTokenizerFast(str(tmp_path / "tiny" / "vocab.txt")).save_pretrained(tmp_path / "tiny")
    BertForSequenceClassification(BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1,
                                             num_attention_heads=2, intermediate_size=32)).save_pretrained(tmp_path / "tiny")
    rng = np.random.default_rng(0)
    tr, va = _data(64, 0, rng), _data(32, 100, rng)
    base = tmp_path / "out"; (base / "results").mkdir(parents=True)
    cfg = {**CFG, "epochs": 1, "batch": 16, "accum": 2}
    train_run(str(tmp_path / "tiny"), "r", tr, va, evaluate, str(base), cfg=cfg, device="cpu")
    cfg["epochs"] = 2
    train_run(str(tmp_path / "tiny"), "r", tr, va, evaluate, str(base), cfg=cfg, device="cpu")
    log = pd.read_csv(base / "results" / "finetune_val_log.csv")
    assert sorted(log["epoch"].unique()) == [1, 2] and len(log) == 2 * len(STYLES)
    assert (base / "models" / "r" / "epoch_2").exists()


def test_train_one_format_eval_all(tmp_path):
    words = "[PAD] [UNK] [CLS] [SEP] [MASK] phone samsung red case title brand full bullets _ key value".split()
    vocab = words + list("abcdefghijklmnopqrstuvwxyz0123456789")
    (tmp_path / "tiny").mkdir(); (tmp_path / "tiny" / "vocab.txt").write_text("\n".join(vocab))
    BertTokenizerFast(str(tmp_path / "tiny" / "vocab.txt")).save_pretrained(tmp_path / "tiny")
    BertForSequenceClassification(BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1,
                                             num_attention_heads=2, intermediate_size=32)).save_pretrained(tmp_path / "tiny")
    rng = np.random.default_rng(1)
    tr, va = _data(64, 0, rng), _data(32, 100, rng)
    base = tmp_path / "out"; (base / "results").mkdir(parents=True)
    cfg = {**CFG, "epochs": 1, "batch": 16, "styles": ["full"], "eval_styles": STYLES}
    train_run(str(tmp_path / "tiny"), "fo", tr, va, evaluate, str(base), cfg=cfg, device="cpu")
    log = pd.read_csv(base / "results" / "finetune_val_log.csv")
    assert sorted(log["style"]) == sorted(STYLES)          # trained on 1 format, scored on all