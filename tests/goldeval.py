"""
Gold-based evaluation for linkengine — self-contained (uses only the ``linkengine`` package).

Four hand-verified gold sets live in ``tests/gold/``:

* ``gold_manual.csv``     — ``text|expected_urn|category|note``; recall (the expected URNs must
  all be produced). Multiple expected URNs are space-separated.
* ``gold_partitions.csv`` — same format; deep article/comma/lettera/numero partition chains.
* ``gold_precision.csv``  — ``id|authority|note|expected_urns|text``; full-sentence excerpts
  scored as an exact set (precision AND recall: a spurious URN is penalised). ``authority`` is
  the deciding court, used to resolve self-references ("questa Corte").
* ``gold_fields.jsonl``   — per citation, the expected **segmentation** (number of references)
  and every recognition field + the ``urn`` (a subset match: an entry pins only what it cares
  about). Optional top-level ``default-authority`` / ``default-region`` / ``reg-scope``.

Run::

    python -m tests.goldeval            # all sets
    python -m tests.goldeval --verbose  # show misses
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter

from linkengine import LinkEngine

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")

# recognition fields a field-gold entry may pin (besides the computed "urn" and "text" anchor)
_FIELDS = ("ref-type", "ref-scope", "doc-type", "authority", "ministry", "region", "city", "section",
           "number", "year", "full-number", "doc-date", "partition", "alias", "other-authority",
           "eu-acronym", "case-number", "rv-number")


def norm_urn(u: str) -> str:
    """Canonicalize an identifier for comparison: trim and drop trailing separators."""
    return re.sub(r"!vig=[0-9-]+$", "", (u or "").strip()).rstrip("~-_; ").strip()


def _pred_urns(engine: LinkEngine, text: str) -> set:
    return {norm_urn(r.get("urn", "")) for r in engine.extract(text).rows} - {""}


def _read_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="|"))


# ── recall over hand-verified URNs (manual + partitions) ────────────────────────
def score_recall(path, verbose=False, title="GOLD"):
    eng = LinkEngine()
    rows = _read_csv(path)
    bycat, bycat_ok, npass = Counter(), Counter(), 0
    for r in rows:
        expected = {norm_urn(u) for u in r["expected_urn"].split() if u.strip()}
        preds = _pred_urns(eng, r["text"])
        ok = expected <= preds
        npass += ok
        bycat[r["category"]] += 1
        bycat_ok[r["category"]] += ok
        if verbose and not ok:
            print(f"  MISS [{r['category']}] {r['text']!r}\n        want {sorted(expected)}\n"
                  f"        got  {sorted(preds)}")
    print(f"\n==== {title} ====\n  PASS: {npass}/{len(rows)} = {100*npass/max(len(rows),1):.0f}%")
    for c in sorted(bycat):
        print(f"    {c:9s} {bycat_ok[c]}/{bycat[c]}")
    return npass, len(rows)


# ── exact-set precision/recall over full-sentence excerpts ──────────────────────
def score_precision(path, verbose=False):
    rows = _read_csv(path)
    tp = fp = fn = 0
    for r in rows:
        eng = LinkEngine(default_authority=r.get("authority", "") or "")
        preds = _pred_urns(eng, r["text"])
        expected = {norm_urn(u) for u in r["expected_urns"].split() if u.strip()}
        tp += len(expected & preds); fp += len(preds - expected); fn += len(expected - preds)
        if verbose and preds != expected:
            print(f"  [{r['id']}] {r.get('note','')}")
            if expected - preds:
                print(f"      MISSING : {sorted(expected - preds)}")
            if preds - expected:
                print(f"      SPURIOUS: {sorted(preds - expected)}")
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    print(f"\n==== GOLD PRECISION (full-sentence, exact set) ====")
    print(f"  excerpts: {len(rows)}   TP={tp} FP={fp} FN={fn}")
    print(f"  precision={prec:.3f}  recall={rec:.3f}  F1={f1:.3f}")
    return tp, fp, fn


# ── field-level gold (segmentation + all fields + urn) ──────────────────────────
def _load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln and not ln.startswith("//"):
                out.append(json.loads(ln))
    return out


def _produced(entry):
    eng = LinkEngine(default_authority=entry.get("default-authority", ""),
                     default_region=entry.get("default-region", ""),
                     default_regolamento_scope=entry.get("reg-scope", "nazionale"))
    out = []
    for r in eng.extract(entry["text"]).rows:
        d = {f: r.get(f, "") for f in _FIELDS}
        d["urn"] = norm_urn(r.get("urn", ""))
        d["text"] = r.get("text", "")
        out.append(d)
    return out


def _match(expected, produced_list):
    return any(all(str(p.get(k, "")) == str(v) for k, v in expected.items()) for p in produced_list)


def score_fields(path, verbose=False):
    gold = _load_jsonl(path)
    bycat, bycat_ok, npass = Counter(), Counter(), 0
    for entry in gold:
        produced = _produced(entry)
        exp = entry["refs"]
        ok = len(produced) == len(exp) and all(_match(e, produced) for e in exp)
        npass += ok
        bycat[entry.get("cat", "misc")] += 1
        bycat_ok[entry.get("cat", "misc")] += ok
        if verbose and not ok:
            tag = "SEG" if len(produced) != len(exp) else "FLD"
            print(f"  {tag}  {entry['text']!r}  (expected {len(exp)} refs, got {len(produced)})")
            for p in produced:
                print(f"        got: { {k: v for k, v in p.items() if v} }")
    print(f"\n==== GOLD FIELDS (segmentation + fields + anchoring + urn) ====")
    print(f"  PASS: {npass}/{len(gold)} = {100*npass/max(len(gold),1):.0f}%")
    for c in sorted(bycat):
        print(f"    {c:9s} {bycat_ok[c]}/{bycat[c]}")
    return npass, len(gold)


def run_all(verbose=False):
    n1, t1 = score_recall(os.path.join(GOLD_DIR, "gold_manual.csv"), verbose, "GOLD (hand-verified)")
    n2, t2 = score_recall(os.path.join(GOLD_DIR, "gold_partitions.csv"), verbose, "GOLD PARTITIONS")
    score_precision(os.path.join(GOLD_DIR, "gold_precision.csv"), verbose)
    n3, t3 = score_fields(os.path.join(GOLD_DIR, "gold_fields.jsonl"), verbose)
    return (n1, t1), (n2, t2), (n3, t3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    run_all(ap.parse_args().verbose)
