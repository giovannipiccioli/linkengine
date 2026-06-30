"""
``run_linkengine_string(text) -> pipe-CSV`` — run the engine and emit the current feature rows
as a header-less, ``"``-quoted, pipe-separated CSV (one line per reference; ``ERROR: No data
in output`` when empty).
"""
from __future__ import annotations

from .engine import LinkEngine
from .model import FEATURE_FIELDS

_engine = LinkEngine()


def run_linkengine_string(ref_string: str) -> str:
    res = _engine.extract(ref_string or "")
    lines = []
    for row in res.rows:
        vals = [str(row.get(c, "")) for c in FEATURE_FIELDS]
        lines.append("|".join('"' + v.replace('"', "") + '"' for v in vals))
    if not lines:
        return "ERROR: No data in output"
    return "\n".join(lines)
