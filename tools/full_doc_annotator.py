"""Pre-annotation and metrics helpers for the full-document benchmark.

Typical workflow:

    python -m tools.full_doc_annotator candidates bdgt_sentenza_z55_3804_2022.txt \
        --jsonl /tmp/z55_candidates.jsonl --html /tmp/z55_candidates.html

Manually review/edit candidate JSONL rows, then append accepted rows to
``tests/gold/full_document_spans.jsonl``. Metrics can be checked with:

    python -m tools.full_doc_annotator metrics --verbose
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re
from statistics import mean
from typing import Iterable

from linkengine import LinkEngine


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "tests" / "benchmark_docs"
GOLD = ROOT / "tests" / "gold" / "full_document_spans.jsonl"
DEFAULT_THRESHOLD = 0.82


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _docs(names: Iterable[str] | None) -> list[Path]:
    if names:
        return [DOC_DIR / name for name in names]
    return sorted(DOC_DIR.glob("*.txt"))


def _read_gold(path: Path = GOLD) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _locate(text: str, anchor: str, cursors: dict[str, int]) -> tuple[int, int]:
    start = text.find(anchor, cursors[anchor])
    if start < 0:
        start = text.find(anchor)
    if start < 0:
        return -1, -1
    cursors[anchor] = start + len(anchor)
    return start, start + len(anchor)


def _candidate_rows(doc: Path, context: int) -> list[dict]:
    text = doc.read_text(encoding="utf-8")
    rows = [row for row in LinkEngine().extract(text).rows if row.get("urn")]
    cursors: defaultdict[str, int] = defaultdict(int)
    out = []
    for index, row in enumerate(rows, 1):
        anchor = row.get("text", "")
        start, end = _locate(text, anchor, cursors)
        before = text[max(0, start - context):start] if start >= 0 else ""
        after = text[end:min(len(text), end + context)] if end >= 0 else ""
        out.append({
            "doc": doc.name,
            "index": index,
            "urn": row["urn"],
            "text": anchor,
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "accepted": True,
            "note": "",
        })
    return out


def _write_jsonl(rows: list[dict], path: Path | None) -> None:
    data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if path:
        path.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


def _write_html(rows: list[dict], path: Path) -> None:
    parts = [
        "<!doctype html><meta charset='utf-8'>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:24px;}",
        "table{border-collapse:collapse;width:100%;font-size:14px;}",
        "td,th{border-top:1px solid #ddd;padding:8px;vertical-align:top;}",
        "code{white-space:pre-wrap;}",
        ".ctx{color:#555}.anchor{background:#fff2a8;color:#111}",
        "</style>",
        "<h1>linkengine full-document candidates</h1>",
        "<table><thead><tr><th>#</th><th>doc</th><th>URN</th><th>context</th></tr></thead><tbody>",
    ]
    for row in rows:
        before = html.escape(row["before"])
        anchor = html.escape(row["text"])
        after = html.escape(row["after"])
        parts.append(
            "<tr>"
            f"<td>{row['index']}</td>"
            f"<td>{html.escape(row['doc'])}</td>"
            f"<td><code>{html.escape(row['urn'])}</code></td>"
            f"<td><span class='ctx'>{before}</span>"
            f"<span class='anchor'>{anchor}</span>"
            f"<span class='ctx'>{after}</span></td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _best_match(target: dict, candidates: list[dict], used: set[int],
                *, require_threshold: float | None = None):
    best = None
    for i, candidate in enumerate(candidates):
        if i in used or candidate["urn"] != target["urn"]:
            continue
        score = _jaccard(target["text"], candidate["text"])
        if best is None or score > best[0]:
            best = (score, i, candidate)
    if best is None:
        return None
    if require_threshold is not None and best[0] < require_threshold:
        return None
    return best


def _score_doc(name: str, gold_rows: list[dict], produced_rows: list[dict], threshold: float):
    gold_counts = Counter(row["urn"] for row in gold_rows)
    produced_counts = Counter(row["urn"] for row in produced_rows)
    urn_tp = sum(min(gold_counts[urn], produced_counts[urn]) for urn in gold_counts | produced_counts)

    used = set()
    span_tp = 0
    span_scores = []
    missing = []
    for gold in gold_rows:
        match = _best_match(gold, produced_rows, used, require_threshold=threshold)
        if match is None:
            missing.append(gold)
        else:
            span_tp += 1
            span_scores.append(match[0])
            used.add(match[1])

    used_gold = set()
    extras = []
    for produced in produced_rows:
        match = _best_match(produced, gold_rows, used_gold, require_threshold=threshold)
        if match is None:
            extras.append(produced)
        else:
            used_gold.add(match[1])

    return {
        "doc": name,
        "gold": len(gold_rows),
        "produced": len(produced_rows),
        "urn_tp": urn_tp,
        "span_tp": span_tp,
        "urn_precision": urn_tp / len(produced_rows) if produced_rows else 1.0,
        "urn_recall": urn_tp / len(gold_rows) if gold_rows else 1.0,
        "span_precision": span_tp / len(produced_rows) if produced_rows else 1.0,
        "span_recall": span_tp / len(gold_rows) if gold_rows else 1.0,
        "anchor_avg": mean(span_scores) if span_scores else 0.0,
        "missing": missing,
        "extras": extras,
    }


def cmd_candidates(args: argparse.Namespace) -> None:
    rows = []
    for doc in _docs(args.docs):
        rows.extend(_candidate_rows(doc, args.context))
    _write_jsonl(rows, Path(args.jsonl) if args.jsonl else None)
    if args.html:
        _write_html(rows, Path(args.html))


def cmd_coverage(args: argparse.Namespace) -> None:
    gold_rows = _read_gold(Path(args.gold))
    counts = Counter(row["doc"] for row in gold_rows)
    for doc in sorted(DOC_DIR.glob("*.txt")):
        print(f"{doc.name}\t{counts.get(doc.name, 0)}")


def cmd_metrics(args: argparse.Namespace) -> None:
    gold_rows = _read_gold(Path(args.gold))
    docs = sorted({row["doc"] for row in gold_rows})
    if args.docs:
        docs = args.docs
    all_scores = []
    for name in docs:
        doc = DOC_DIR / name
        if not doc.exists():
            raise SystemExit(f"Missing benchmark doc: {name}")
        produced = [
            {"doc": row["doc"], "urn": row["urn"], "text": row["text"]}
            for row in _candidate_rows(doc, args.context)
        ]
        gold = [row for row in gold_rows if row["doc"] == name]
        score = _score_doc(name, gold, produced, args.threshold)
        all_scores.append(score)
        print(
            f"{name}: gold={score['gold']} produced={score['produced']} "
            f"urn_p={score['urn_precision']:.3f} urn_r={score['urn_recall']:.3f} "
            f"span_p={score['span_precision']:.3f} span_r={score['span_recall']:.3f} "
            f"anchor_avg={score['anchor_avg']:.3f}"
        )
        if args.verbose and (score["missing"] or score["extras"]):
            for row in score["missing"][:20]:
                print(f"  MISSING {row['urn']} :: {row['text']!r}")
            for row in score["extras"][:20]:
                print(f"  EXTRA   {row['urn']} :: {row['text']!r}")

    gold_total = sum(s["gold"] for s in all_scores)
    produced_total = sum(s["produced"] for s in all_scores)
    urn_tp = sum(s["urn_tp"] for s in all_scores)
    span_tp = sum(s["span_tp"] for s in all_scores)
    print("TOTAL:")
    print(f"  docs={len(all_scores)} gold={gold_total} produced={produced_total}")
    print(f"  urn_precision={urn_tp / produced_total if produced_total else 1.0:.3f}")
    print(f"  urn_recall={urn_tp / gold_total if gold_total else 1.0:.3f}")
    print(f"  span_precision={span_tp / produced_total if produced_total else 1.0:.3f}")
    print(f"  span_recall={span_tp / gold_total if gold_total else 1.0:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("candidates", help="pre-annotate benchmark documents")
    p.add_argument("docs", nargs="*", help="benchmark document filenames")
    p.add_argument("--context", type=int, default=140)
    p.add_argument("--jsonl", help="write candidate JSONL to this path")
    p.add_argument("--html", help="write review HTML to this path")
    p.set_defaults(func=cmd_candidates)

    p = sub.add_parser("coverage", help="show span-gold rows per benchmark document")
    p.add_argument("--gold", default=str(GOLD))
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("metrics", help="compare engine output against span gold")
    p.add_argument("docs", nargs="*", help="optional document subset")
    p.add_argument("--gold", default=str(GOLD))
    p.add_argument("--context", type=int, default=140)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_metrics)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
