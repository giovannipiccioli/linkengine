"""Small full-document benchmark over the self-contained sample corpus.

This is intentionally separate from pytest: run it when you want a speed signal, not as a
correctness gate.

    python -m tests.bench_full_docs
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from linkengine import LinkEngine


DOC_DIR = Path(__file__).with_name("benchmark_docs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=10)
    args = parser.parse_args()

    docs = sorted(DOC_DIR.glob("*.txt"))
    engine = LinkEngine()
    texts = [(p.name, p.read_text(encoding="utf-8")) for p in docs]

    warm_refs = sum(len(engine.extract(text).rows) for _, text in texts)
    total_chars = sum(len(text) for _, text in texts) * args.loops
    total_docs = len(texts) * args.loops

    started = time.perf_counter()
    total_refs = 0
    for _ in range(args.loops):
        for _, text in texts:
            total_refs += len(engine.extract(text).rows)
    elapsed = time.perf_counter() - started

    print(f"documents={len(texts)} loops={args.loops} extracts={total_docs}")
    print(f"chars={total_chars} refs={total_refs} warmup_refs={warm_refs}")
    print(f"elapsed={elapsed:.4f}s")
    print(f"docs_per_s={total_docs / elapsed:.2f}")
    print(f"chars_per_s={total_chars / elapsed:.0f}")
    print(f"avg_ms_per_doc={(elapsed * 1000) / total_docs:.3f}")


if __name__ == "__main__":
    main()

