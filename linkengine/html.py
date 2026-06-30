"""
HTML highlighting — re-emit the input text with every recognized legal reference highlighted
(styled like a link), so you can *see* in the text which citations were found.

**One function**, ``annotate_html`` — pick what you get with the ``page`` flag::

    from linkengine import annotate_html

    annotate_html(text)                  # -> an inline HTML fragment (embed it in your own page)
    annotate_html(text, page=True)       # -> a complete standalone HTML document (save & open)

Each citation is wrapped in ``<span class="lkn-ref" data-urn=… data-…>…</span>``: the visible
text is unchanged (just highlighted via CSS), while the extracted fields live in ``data-*``
attributes for inspection (DevTools) or programmatic use — no details are shown inline.

Design notes
------------
* The **``text`` field of each row is the anchor** that gets wrapped, located in the source via
  ``str.find`` seeded at the reference's char offset (``Reference.start``) — the row's
  ``text`` is the anchor substring, while ``Reference.start/end`` is the whole citation extent.
* ``only_with_urn=True`` highlights only references that resolved to a ``urn``; the rest stay
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

# Fields shown as attributes: `urn` first (the headline), then every feature field except the
# bookkeeping field and `text`/`context` (which are not normalized output).
_EXCLUDE = {"id", "text", "context"}
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


def _open_tag(rows: Sequence[Dict[str, str]], tag: str, css_class: str, attr_prefix: str) -> str:
    """The opening tag for one citation: a CSS class (for highlighting) plus the extracted
    fields as ``data-*`` attributes (``urn`` first) — details live here, never inline."""
    parts = [tag]
    if css_class:
        parts.append(f'class="{_esc_attr(css_class)}"')
    if len(rows) > 1:
        parts.append(f'{attr_prefix}refs="{len(rows)}"')   # this anchor carries N references
    for f in _ATTR_FIELDS:
        v = _merged_values(rows, f)
        if v:
            parts.append(f'{attr_prefix}{f}="{_esc_attr(v)}"')
    return "<" + " ".join(parts) + ">"


# Default stylesheet for ``page=True``: citations look like links (coloured + underlined), with
# nothing shown inline — legislation blue, caselaw green, prassi amber.
_DEFAULT_CSS = """
  .lkn-doc { white-space: pre-wrap; word-wrap: break-word; max-width: 50rem; margin: 2rem auto;
             padding: 0 1rem; color: #1f2328;
             font: 16px/1.7 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .lkn-ref { color: #1d4ed8; text-decoration: underline; text-decoration-color: #93b4fb;
             text-decoration-thickness: 2px; text-underline-offset: 2px; }
  .lkn-ref[data-ref-type="caselaw"] { color: #15803d; text-decoration-color: #86d6a4; }
  .lkn-ref[data-ref-type="prassi"]  { color: #b45309; text-decoration-color: #f0c08a; }
""".strip("\n")


# ── public API — the single entry point for HTML output ──────────────────────────
def annotate_html(text: str, result: Optional[ExtractResult] = None, *, page: bool = False,
                  only_with_urn: bool = False, css: Optional[str] = None,
                  title: str = "linkengine — recognized references",
                  tag: str = "span", css_class: str = "lkn-ref",
                  attr_prefix: str = "data-") -> str:
    """Highlight every recognized legal reference in ``text`` and return HTML.

    Each citation is wrapped in ``<span class="lkn-ref" data-urn=… data-…>…</span>``: the visible
    text is unchanged (highlighted by the stylesheet), the extracted fields live only in the
    ``data-*`` attributes (for DevTools / programmatic use). Non-citation text is HTML-escaped
    and otherwise left verbatim.

    Choose the output with ``page``:

    * ``page=False`` (default) → an **inline HTML fragment** to embed in your own page.
    * ``page=True``           → a complete, styled, standalone **HTML document** you can write
      straight to a ``.html`` file and open in a browser.

    Parameters
    ----------
    result : reuse an ``engine.extract(text)`` result to avoid re-extracting; if omitted the
        text is extracted with a default engine. (To use a configured engine — e.g. a
        ``default_authority`` — pass ``result=my_engine.extract(text)``.)
    only_with_urn : highlight only references that resolved to a ``urn``; leave the rest as text.
    css, title : the stylesheet and ``<title>`` of the document (used only when ``page=True``).
    """
    if text is None:
        return ""
    if result is None:
        result = _engine().extract(text)
    anchors = _build_anchors(text, result, only_with_urn)

    buf: List[str] = []
    cursor = 0
    for s, e, rows in anchors:
        buf.append(_esc(text[cursor:s]))
        buf.append(_open_tag(rows, tag, css_class, attr_prefix))
        buf.append(_esc(text[s:e]))
        buf.append(f"</{tag}>")
        cursor = e
    buf.append(_esc(text[cursor:]))
    body = "".join(buf)

    if not page:
        return body
    style = _DEFAULT_CSS if css is None else css
    return (
        "<!doctype html>\n"
        '<html lang="it">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n<style>\n{style}\n</style>\n</head>\n"
        f'<body>\n<pre class="lkn-doc">{body}</pre>\n</body>\n</html>\n'
    )
