"""
Gold-based evaluation for linkengine — self-contained (uses only the ``linkengine`` package).

Seven hand-verified gold sets live in ``tests/gold/``:

* ``gold_manual.csv``     — ``text|expected_urn|category|note``; recall (the expected URNs must
  all be produced). Multiple expected URNs are space-separated.
* ``gold_partitions.csv`` — same format; deep article/comma/lettera/numero partition chains.
* ``gold_precision.csv``  — ``id|authority|note|expected_urns|text``; full-sentence excerpts
  scored as an exact set (precision AND recall: a spurious URN is penalised). ``authority`` is
  the deciding court, used to resolve self-references ("questa Corte").
* ``gold_fields.jsonl``   — per citation, the expected **segmentation** (number of references)
  and every recognition field + the ``urn`` (a subset match: an entry pins only what it cares
  about). Optional top-level ``default-authority`` / ``default-region`` / ``reg-scope``.
* ``gold_normativa.jsonl`` / ``gold_normativa_eu.jsonl`` — famous and fixed-seed random
  real-legislation excerpts, each with its exact current-unit NIR or CELEX identifier; scored
  for exact segmentation, anchors, partitions and identifiers. They intentionally retain a few
  unsupported cases as an evaluation corpus.
* ``gold_normativa_novelle.jsonl`` — real amendment clauses and editorial notes. Supported
  entries are regression gates; entries labelled ``known-miss`` deliberately record the
  semantic result that a more complete amendment parser would produce.

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

from linkengine import DocumentContext, LinkEngine

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


# ── normativa mode: real legislation + exact internal-link anchors ────────────
def normativa_case(entry, engine=None):
    """Return ``(matches, produced)`` for one exact normativa gold entry."""
    engine = engine or LinkEngine()
    result = engine.extract(
        entry["text"],
        mode="normativa",
        current_unit_urn=entry["current-unit-urn"],
    )
    produced = [{
        "text": row.get("text", ""),
        "partition": row.get("partition", ""),
        "urn": row.get("urn", ""),
    } for row in result.rows]
    expected = entry["refs"]
    matches = len(produced) == len(expected) and all(
        _match(ref, produced) for ref in expected)
    return matches, produced


def score_normativa(path, verbose=False, title="GOLD NORMATIVA"):
    gold = _load_jsonl(path)
    eng = LinkEngine()
    byselection, byselection_ok, npass = Counter(), Counter(), 0
    for entry in gold:
        ok, produced = normativa_case(entry, eng)
        expected = entry["refs"]
        npass += ok
        selection = entry.get("selection", "unspecified")
        byselection[selection] += 1
        byselection_ok[selection] += ok
        if verbose and not ok:
            print(f"  NORM  [{entry['id']}] {entry.get('source', '')}")
            print(f"        want: {expected}")
            print(f"        got : {produced}")
    print(f"\n==== {title} (real legislation, exact anchors + identifiers) ====")
    print(f"  PASS: {npass}/{len(gold)} = {100*npass/max(len(gold),1):.0f}%")
    for selection in sorted(byselection):
        print(f"    {selection:9s} {byselection_ok[selection]}/{byselection[selection]}")
    return npass, len(gold)


# ── Corte dei conti, full documents ─────────────────────────────────────────────
def score_corte_conti_docs(path, verbose=False):
    """Score every Corte dei conti identifier produced over whole real decisions.

    An evaluation, not a regression gate: recall is bounded by how these documents actually
    cite (a controllo deliberation cited without its procedural type has no identifier to
    find), so the number to watch is precision — an identifier that is produced must be the
    right one. Returns (tp, fp, fn).
    """
    docs_dir = os.path.join(os.path.dirname(__file__), "benchmark_docs")
    gold = _load_jsonl(path)
    tp = fp = fn = 0
    for entry in gold:
        text = open(os.path.join(docs_dir, entry["doc"]), encoding="utf-8").read()
        context = DocumentContext(authority="CORTE_CONTI", cc_section=entry["cc-section"])
        produced = {norm_urn(r["urn"]) for r in LinkEngine().extract(text, context=context).rows
                    if r["urn"].startswith("ECLI:IT:CONT:")}
        expected = {norm_urn(r["urn"]) for r in entry["refs"]}
        tp += len(produced & expected)
        fp += len(produced - expected)
        fn += len(expected - produced)
        if verbose and (produced != expected):
            print(f"  {entry['doc']}")
            for u in sorted(expected - produced):
                text_of = next(r["text"] for r in entry["refs"] if norm_urn(r["urn"]) == u)
                print(f"      MISS {u:34s} {text_of}")
            for u in sorted(produced - expected):
                print(f"      FP   {u}")
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    print("\n==== GOLD CORTE DEI CONTI (whole documents, every citation of the Court) ====")
    print(f"  documents: {len(gold)}   citations: {tp + fn}   TP={tp} FP={fp} FN={fn}")
    print(f"  precision={prec:.3f}  recall={rec:.3f}  F1={2*prec*rec/max(prec+rec, 1e-9):.3f}")
    return tp, fp, fn


def run_all(verbose=False):
    n1, t1 = score_recall(os.path.join(GOLD_DIR, "gold_manual.csv"), verbose, "GOLD (hand-verified)")
    n2, t2 = score_recall(os.path.join(GOLD_DIR, "gold_partitions.csv"), verbose, "GOLD PARTITIONS")
    score_precision(os.path.join(GOLD_DIR, "gold_precision.csv"), verbose)
    n3, t3 = score_fields(os.path.join(GOLD_DIR, "gold_fields.jsonl"), verbose)
    n4, t4 = score_normativa(os.path.join(GOLD_DIR, "gold_normativa.jsonl"), verbose)
    n5, t5 = score_normativa(
        os.path.join(GOLD_DIR, "gold_normativa_eu.jsonl"), verbose, "GOLD NORMATIVA EU")
    n6, t6 = score_normativa(
        os.path.join(GOLD_DIR, "gold_normativa_novelle.jsonl"), verbose,
        "GOLD NORMATIVA NOVELLE")
    score_corte_conti_docs(os.path.join(GOLD_DIR, "gold_corte_conti_docs.jsonl"), verbose)
    return (n1, t1), (n2, t2), (n3, t3), (n4, t4), (n5, t5), (n6, t6)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    run_all(ap.parse_args().verbose)
