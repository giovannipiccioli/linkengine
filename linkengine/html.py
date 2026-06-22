"""
HTML annotation — render the input text back out with every recognized reference wrapped in
a tag carrying its extracted feature fields as attributes. The point is to *see*, in the
text itself, which
references were recognized and what the engine made of each one.

Public API (standalone, like ``urn_to_text``)::

    from linkengine.html import annotate_html, render_html_document

    annotate_html("artt. 15-18 DPR 600/73")            # -> the text with <span> tags inserted
    render_html_document(text, only_with_urn=True)      # -> a full, styled, browser-ready page

Design notes
------------
* The **``text`` field of each row is the anchor** that gets wrapped, located in the source via
  ``str.find`` seeded at the reference's char offset (``Reference.start``) — the row's
  ``text`` is the anchor substring, while ``Reference.start/end`` is the whole citation extent.
* ``only_with_urn=True`` wraps only references that resolved to a ``urn``; the rest stay
  as plain text.
* **Range partitions** (``artt. 15-18 ...``) are already handled upstream: the engine anchors
  the inner articles (16, 17) to the ``-`` and the endpoints (15, 18) to their digits. When
  several references collapse onto the *same* anchor (both 16 and 17 land on the ``-``) they are
  **merged into one tag** whose differing fields (``urn``, ``partition``, …) are space-joined —
  so the ``-`` carries both URNs. Any residual overlap is dropped (keep the first, longest).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .engine import LinkEngine
from .model import FEATURE_FIELDS, ExtractResult
from .urn import urn_to_text

# Fields shown as attributes: `urn` first (the headline), then every feature field except the
# bookkeeping/source ones and `text`/`context` (which are not normalized output).
_EXCLUDE = {"id", "source-name", "source-partition-id", "text", "context"}
_ATTR_FIELDS = ["urn"] + [f for f in FEATURE_FIELDS if f not in _EXCLUDE]

_DEFAULT_ENGINE: Optional[LinkEngine] = None


def _engine() -> LinkEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = LinkEngine()
    return _DEFAULT_ENGINE


# ── escaping ───────────────────────────────────────────────────────────────────
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return _esc(s).replace('"', "&quot;")


# ── anchoring ──────────────────────────────────────────────────────────────────
def _find_anchor(text: str, anchor: str, ref_start: int) -> Tuple[int, int]:
    """Locate the row's ``text`` anchor in the source. Seed the search at the reference's char
    offset (so a repeated short anchor like ``-`` lands in the right citation), then widen."""
    if not anchor:
        return -1, -1
    for start_from in (ref_start, max(0, ref_start - 8), 0):
        idx = text.find(anchor, start_from)
        if idx != -1:
            return idx, idx + len(anchor)
    return -1, -1


def _build_anchors(text: str, result: ExtractResult,
                   only_with_urn: bool) -> List[Tuple[int, int, List[Dict[str, str]]]]:
    """Return ``[(start, end, [rows…]), …]`` in document order, with co-anchored rows merged
    and any overlapping anchors dropped (keep the first/longest)."""
    rows, refs = result.rows, result.references
    spans = []
    for i, row in enumerate(rows):
        if only_with_urn and not (row.get("urn") or "").strip():
            continue
        anchor = row.get("text") or ""
        ref_start = refs[i].start if i < len(refs) else 0
        s, e = _find_anchor(text, anchor, ref_start)
        if s != -1:
            spans.append((s, e, row))

    # group rows sharing the exact same anchor span (the range "-" case)
    groups: Dict[Tuple[int, int], List[Dict[str, str]]] = {}
    for s, e, row in spans:
        groups.setdefault((s, e), []).append(row)

    # emit left-to-right, longest-first on ties; skip anything overlapping a kept anchor
    out: List[Tuple[int, int, List[Dict[str, str]]]] = []
    last_end = -1
    for (s, e) in sorted(groups, key=lambda k: (k[0], -(k[1] - k[0]))):
        if s < last_end:
            continue
        out.append((s, e, groups[(s, e)]))
        last_end = e
    return out


# ── tag building ───────────────────────────────────────────────────────────────
def _merged_values(rows: Sequence[Dict[str, str]], field: str) -> str:
    """Distinct non-empty values of ``field`` across the rows, in order, space-joined."""
    vals: List[str] = []
    for row in rows:
        v = (row.get(field) or "").strip()
        if v and v not in vals:
            vals.append(v)
    return " ".join(vals)


def _title(rows: Sequence[Dict[str, str]]) -> str:
    """Human tooltip: the urn rendered by ``urn_to_text`` (falls back to ref-type)."""
    out: List[str] = []
    for row in rows:
        urn = (row.get("urn") or "").strip()
        t = (urn_to_text(urn) if urn else "") or (row.get("ref-type") or "")
        if t and t not in out:
            out.append(t)
    return " · ".join(out)


def _open_tag(rows: Sequence[Dict[str, str]], tag: str, css_class: str,
              attr_prefix: str, add_title: bool) -> str:
    parts = [tag]
    if css_class:
        parts.append(f'class="{_esc_attr(css_class)}"')
    if add_title:
        t = _title(rows)
        if t:
            parts.append(f'title="{_esc_attr(t)}"')
    if len(rows) > 1:
        parts.append(f'{attr_prefix}refs="{len(rows)}"')   # this anchor carries N references
    for f in _ATTR_FIELDS:
        v = _merged_values(rows, f)
        if v:
            parts.append(f'{attr_prefix}{f}="{_esc_attr(v)}"')
    return "<" + " ".join(parts) + ">"


# ── public API ─────────────────────────────────────────────────────────────────
def annotate_html(text: str, result: Optional[ExtractResult] = None, *,
                  engine: Optional[LinkEngine] = None, only_with_urn: bool = False,
                  tag: str = "span", css_class: str = "lkn-ref",
                  attr_prefix: str = "data-", add_title: bool = True) -> str:
    """Return ``text`` with every recognized reference wrapped in ``<tag … >…</tag>``.

    The wrapped text is the row's ``text`` field; the tag carries the extracted feature fields
    as ``{attr_prefix}{field}`` attributes (``urn`` first) plus a human ``title``. Non-reference
    text is HTML-escaped and otherwise left exactly as in the input.

    Parameters
    ----------
    result : reuse an existing ``LinkEngine.extract`` result (else one is computed).
    engine : a configured ``LinkEngine`` (else a default, cached one is used).
    only_with_urn : wrap only references that resolved to a ``urn``; leave the rest as text.
    """
    if text is None:
        return ""
    if result is None:
        result = (engine or _engine()).extract(text)
    anchors = _build_anchors(text, result, only_with_urn)

    buf: List[str] = []
    cursor = 0
    for s, e, rows in anchors:
        buf.append(_esc(text[cursor:s]))
        buf.append(_open_tag(rows, tag, css_class, attr_prefix, add_title))
        buf.append(_esc(text[s:e]))
        buf.append(f"</{tag}>")
        cursor = e
    buf.append(_esc(text[cursor:]))
    return "".join(buf)


_DEFAULT_CSS = """
  .lkn-doc { white-space: pre-wrap; word-wrap: break-word;
             font: 14px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .lkn-ref { background: #e8eeff; border-bottom: 1px dotted #6a7bd0; border-radius: 2px;
             padding: 0 1px; cursor: help; }
  .lkn-ref[data-ref-type="caselaw"]    { background: #e6f6ea; border-bottom-color: #4f9d68; }
  .lkn-ref[data-ref-type="prassi"]     { background: #fdeede; border-bottom-color: #c9893a; }
  .lkn-ref[data-ref-type="legislation"]{ background: #e8eeff; border-bottom-color: #6a7bd0; }
  .lkn-ref:hover { outline: 1px solid currentColor; }
""".strip("\n")


def render_html_document(text: str, *, title: str = "linkengine — recognized references",
                         css: Optional[str] = None, **annotate_kwargs) -> str:
    """A full, browser-ready HTML page: the annotated text inside a styled ``<pre>``. Keyword
    arguments are forwarded to :func:`annotate_html` (e.g. ``only_with_urn=True``)."""
    body = annotate_html(text, **annotate_kwargs)
    style = _DEFAULT_CSS if css is None else css
    return (
        "<!doctype html>\n"
        '<html lang="it">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n<style>\n{style}\n</style>\n</head>\n"
        f'<body>\n<pre class="lkn-doc">{body}</pre>\n</body>\n</html>\n'
    )
