"""
Partition recognition + segmentation.

A partition expression is a run of partition *elements* (allegato / articolo /
comma|paragrafo / lettera / numero|punto / periodo) joined by conjunctions ("e", ",") and
"del/della/dell'" links. One citation references a single root-to-leaf *path*; conjunctions
and the "del" backward links produce several leaves. This module turns a run of element
spans into the set of leaf paths (each a list of spans), which the assembler attaches to an
act to form one reference per leaf.

The method:

1. **Recognize elements** as offset-anchored spans, expanding value lists ("commi 1 e 2-bis"
   -> two COMMA spans) and ordinals ("primo comma" -> comma 1). NUMERO ("n. 3") is only
   taken when it sits *inside* a partition chain (right after a comma/lettera), never as a
   document number.

2. **Resolve backward links**: "comma 1 dell'art. 19" / "lettera b) del comma 2 dell'art. 17"
   — a shallower element introduced by "del…" owns the deeper elements before it; we reorder
   it to sit in front of them, turning every expression into canonical shallow→deep order.

3. **Build leaf paths** by a single left→right pass over the (reordered) elements, keeping a
   running path: when an element is not strictly deeper than the current leaf it starts a new
   branch — we emit the current leaf and truncate the path to the shallower levels. This one
   rule covers deep chains, sibling conjunctions at any level, and mixed forms
   ("comma 1 lett. a e b, e comma 2").

The three domains share this segmentation; they differ only in which element type is used
(national: comma; EU law: paragrafo; EU case-law: punto) and in the downstream URN locator
transform (handled by normalize/urn), not here.
"""
from __future__ import annotations

import re
from typing import List

from .model import Entity, Span
from .normalize import norm_latin_suffix

I = re.IGNORECASE

# depth: smaller = shallower (closer to the act). comma/paragrafo are siblings; numero/punto
# are siblings; allegato is the shallowest container.
RANK = {
    Entity.ALLEGATO: 0, Entity.CONSIDERANDO: 2, Entity.ARTICLE: 2,
    Entity.COMMA: 3, Entity.PARAGRAPH: 3, Entity.LETTER: 4,
    Entity.NUMERO: 5, Entity.PUNTO: 5, Entity.PERIODO: 6,
}

_LATIN = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies)"
_SUFFIX_SEP = r"[-\s\u00ad]?"
_NUMV = r"\d+(?:" + _SUFFIX_SEP + _LATIN + r")?"
# a numeric value OR a range (`5-7`, `5 a 8`): the range alternative comes first so `5-7`
# is read as a range, while `2-bis` (suffix, not a second number) still falls to _NUMV.
_NUMV_OR_RANGE = r"(?:\d+\s*(?:[-–]|a)\s*\d+|" + _NUMV + r")"
# a letter value is a *standalone* letter: the `(?![a-z])` guard stops the list from eating
# the first letter of a following word ("lett. b), del d.P.R." must not yield letter "d").
_LETV = r"[a-z](?![a-z'’])(?:" + _SUFFIX_SEP + _LATIN + r")?\)?"
_SEP = r"(?:\s*[,;]\s*|\s+(?:e|ed)\s+)"
_NUMV_RE = re.compile(_NUMV, I)
_LETV_RE = re.compile(r"[a-z](?![a-z'’])(?:" + _SUFFIX_SEP + _LATIN + r")?\)?", I)
_SEP_RE = re.compile(_SEP, I)
_RANGE_RE = re.compile(r"(\d+)\s*([-–]|a)\s*(\d+)", I)   # "5-7" / "5 a 8" -> expand inclusive
_MAX_RANGE = 30          # guard: wider ranges keep only the two endpoints
_CONJ_LETTERS = ("e", "ed", "o")     # letters that double as Italian conjunctions

ORDINALS = {
    "primo": "1", "prima": "1", "secondo": "2", "seconda": "2", "terzo": "3", "terza": "3",
    "quarto": "4", "quinto": "5", "sesto": "6", "settimo": "7", "ottavo": "8", "nono": "9",
    "decimo": "10", "undicesimo": "11", "dodicesimo": "12",
}
_ORD_ALT = "|".join(ORDINALS)

# numeric value-list, allowing a leading "da" and ranges: "da 5 a 8", "14, 15 e 18", "5-7".
_NUMLIST = r"(?:da\s+)?(" + _NUMV_OR_RANGE + r"(?:" + _SEP + _NUMV_OR_RANGE + r")*)"
# EC-Treaty article lists repeat "CE" after each number ("artt. 45 CE, 46 CE, 55 CE").
# The article list admits an uppercase-only "CE" after each value so the scan continues
# past it; _emit_list skips the token (it is never a value). Uppercase-only ("(?-i:CE)"
# inside the I-flagged pattern) keeps the clitic pronoun "ce" out.
_CE_TOKEN = r"(?:\s+(?-i:CE)\b)?"
_NUMLIST_CE = (r"(?:da\s+)?(" + _NUMV_OR_RANGE + _CE_TOKEN +
               r"(?:" + _SEP + _NUMV_OR_RANGE + _CE_TOKEN + r")*)")
_CE_TOKEN_RE = re.compile(r"\s+CE\b")   # case-sensitive on purpose

# (entity, head-with-value-list regex, value-token regex, value normalizer)
_LIST_PATTERNS = [
    (Entity.CONSIDERANDO, r"\bconsiderand[oi]\s*" + _NUMLIST, _NUMV_RE, norm_latin_suffix),
    (Entity.ARTICLE, r"\bart(?:icol[oi]|t)?[\.,]?\s*" + _NUMLIST_CE, _NUMV_RE, norm_latin_suffix),
    (Entity.COMMA, r"\b(?:commi|comma|co\.|c\.(?=\s*\d))\s*" + _NUMLIST, _NUMV_RE, norm_latin_suffix),
    (Entity.PARAGRAPH, r"\b(?:paragraf[oi]|par\.|§)\s*" + _NUMLIST, _NUMV_RE, norm_latin_suffix),
    (Entity.PUNTO, r"\bpunt[oi]\s*" + _NUMLIST, _NUMV_RE, norm_latin_suffix),
    # a real separator (era/ere, ".", or whitespace) must follow "lett"/"let" so the common
    # words "letto"/"letta"/"lette"/"letti" are not read as "lett" + a letter value.
    (Entity.LETTER, r"\blett?(?:er[ae]\s*|\.\s*|\s+)(" + _LETV + r"(?:" + _SEP + _LETV + r")*)",
     _LETV_RE, lambda v: norm_latin_suffix(v.rstrip(")"))),
]
_LIST_COMPILED = [(e, re.compile(p, I), vr, fn) for e, p, vr, fn in _LIST_PATTERNS]

# ordinals: "primo comma", "secondo periodo"
_ORD_COMMA = re.compile(r"\b(" + _ORD_ALT + r")\s+comm[ai]\b", I)
# numeric/roman ordinal commas: "1° comma" -> comma 1, "III comma" -> comma 3. The roman set
# is an explicit whitelist (II–XX) so Italian words like "di"/"i" are not read as numerals.
_NUM_ORD_COMMA = re.compile(r"\b(\d{1,2})[°ºª]\s*comm[ai]\b", I)
_ROM = r"(?:ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)"
_ROM_COMMA = re.compile(r"\b(" + _ROM + r")\s+comm[ai]\b", I)
_ROM_VAL = {"i": 1, "v": 5, "x": 10}


def _roman_to_int(s: str) -> int:
    v = [_ROM_VAL.get(c, 0) for c in s.lower()]
    return sum(-x if i + 1 < len(v) and x < v[i + 1] else x for i, x in enumerate(v))
_ORD_PERIODO = re.compile(r"\b(" + _ORD_ALT + r")\s+period[oi]\b", I)
_PERIODO = re.compile(r"\bperiod[oi]\s*(\d+)\b(?!\s*[/.-]\s*\d)", I)
# "allegato A" / "allegati" / "alleg. A" / "All. A" -> annex marker. The "all." abbreviation
# requires the dot so the common words "alla/alle/allo" are not matched.
_ALLEGATO = re.compile(r"\b(?:allegat[oi]|alleg\.|all\.)\s*([0-9]+|[ivxlcdm]+|[a-z])\b", I)
# NUMERO candidate ("n. 3", "numero 3", "nn. 3 e 4") — only kept if inside a partition chain
_NUMERO = re.compile(r"\b(?:numero|nn\.?|n\.)\s*(" + _NUMV + r"(?:" + _SEP + _NUMV + r")*)", I)
_ELIDED_ARTICLE = re.compile(r"(?:^|[,\s])(?:e|ed)\s+(" + _NUMV + r")\b", I)
_ELIDED_ARTICLE_AFTER = re.compile(
    r"^[\s,]*(?:(?:commi|comma|co\.|c\.(?=\s*\d)|lett?(?:er[ae]|\.)?|"
    r"numero|nn?\.|del|della|delle|dello|dei|degli|dell['’]|d['’])\b)",
    I,
)

# "del/della/dei/dell'/al…" backward-link markers. "dell'" needs its own alternative
# because the trailing apostrophe is not a word boundary (it often ends the connector).
_DEL_RE = re.compile(
    r"\b(?:del|della|delle|dello|dei|degli|nel|nella|al|allo|alla|alle)\b|\bdell['’]", I)


def _emit_list(text, m, entity, val_re, normfn, spans):
    """Walk the captured value-list as VALUE (SEP VALUE)*, consuming each separator
    explicitly. This keeps a conjunction from being read as a value ("lett. a e b" -> a, b,
    not a, e, b) and stops the list at a following word ("lett. b, del d.P.R." -> b only).

    A numeric VALUE may itself be a range ("5-7" / "da 5 a 8"): it is expanded into one span
    per element. The two endpoints anchor on their own digits; the interpolated middle
    elements (which have no text of their own) anchor on the range symbol ('-' or 'a') and
    are tagged ``fill`` so they survive de-overlap and are rendered as that symbol only."""
    list_str, base = m.group(1), m.start(1)
    numeric = val_re is _NUMV_RE
    pos, first = 0, True
    while pos < len(list_str):
        rng = _RANGE_RE.match(list_str, pos) if numeric else None
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(3))
            n1e = base + rng.end(1)
            syms, syme = base + rng.start(2), base + rng.end(2)
            n2s, n2e = base + rng.start(3), base + rng.end(3)
            seq = list(range(lo, hi + 1)) if lo <= hi else list(range(lo, hi - 1, -1))
            if len(seq) > _MAX_RANGE:
                seq = [lo, hi]                       # too wide: keep only the endpoints
            for v in seq:
                if v == lo:
                    s, e, at = (m.start() if first else base + rng.start(1)), n1e, {}
                elif v == hi:
                    s, e, at = n2s, n2e, {}
                else:
                    s, e, at = syms, syme, {"fill": True}
                spans.append(Span(s, e, entity, str(v), text[s:e], at))
            first, pos = False, rng.end()
        else:
            vm = val_re.match(list_str, pos)
            if not vm:
                break
            # a continuation letter that *is* a conjunction ("lett. a) e b), e comma 2") and
            # is followed by a word rather than a list separator is the word "e", not letter
            # e — end the list here. ("lett. d, e, f" keeps e: it is followed by ", f".)
            if (not first and entity is Entity.LETTER
                    and vm.group(0).rstrip(")").lower() in _CONJ_LETTERS
                    and re.match(r"\s+[a-zà-ù]{2}", text[base + vm.end():], I)):
                break
            # a continuation letter immediately followed by ".<letter>" is an abbreviation
            # initial ("lett. g, D.Lgs ..." -> g only, not letter d), not a value.
            if (not first and entity is Entity.LETTER
                    and re.match(r"\.\s*[a-zà-ù]", text[base + vm.end():], I)):
                break
            start = m.start() if first else base + vm.start()
            end = base + vm.end()
            spans.append(Span(start, end, entity, normfn(vm.group(0)), text[start:end]))
            first, pos = False, vm.end()
        cm = _CE_TOKEN_RE.match(list_str, pos)   # skip a treaty "CE" between value and sep
        if cm:
            pos = cm.end()
        sm = _SEP_RE.match(list_str, pos)
        if not sm:
            break
        pos = sm.end()


def _nonoverlap(spans: List[Span]) -> List[Span]:
    out: List[Span] = []
    for s in sorted(spans, key=lambda x: (x.start, -(x.end - x.start))):
        # interpolated range elements share the symbol's offset on purpose; keep them all.
        if s.attrs.get("fill") or all(s.end <= o.start or s.start >= o.end for o in out):
            out.append(s)
    return out


def recognize_elements(text: str) -> List[Span]:
    spans: List[Span] = []
    for entity, pat, vr, fn in _LIST_COMPILED:
        for m in pat.finditer(text):
            _emit_list(text, m, entity, vr, fn, spans)
    # Plural article lists can repeat the article number after a subpartition without restating
    # "art.": "artt. 2, comma 1, e 3, comma 1, lettera c)". The ordinary article-list regex
    # stops at "comma 1", so recover the elided sibling article only in that narrow context.
    base_spans = sorted(spans, key=lambda s: s.start)
    plural_articles = [
        s for s in base_spans
        if s.entity == Entity.ARTICLE and re.match(r"\bartt|articoli", s.text, I)
    ]
    for m in _ELIDED_ARTICLE.finditer(text):
        start, end = m.start(1), m.end(1)
        if not plural_articles:
            break
        if not re.search(r"\b(?:artt|articoli)\b", text[max(0, start - 120):start], I):
            continue
        if not _ELIDED_ARTICLE_AFTER.match(text[end:end + 32]):
            continue
        if any(not (end <= s.start or start >= s.end) for s in spans):
            continue
        prev = None
        for article in reversed(plural_articles):
            if article.end <= start:
                if start - article.end <= 100:
                    prev = article
                break
        if prev is None:
            continue
        has_deeper = False
        for s in base_spans:
            if s.start < prev.end:
                continue
            if s.start >= start:
                break
            if s.end <= start and RANK[s.entity] > RANK[Entity.ARTICLE]:
                has_deeper = True
                break
        if not has_deeper:
            continue
        spans.append(Span(start, end, Entity.ARTICLE, norm_latin_suffix(m.group(1)), text[start:end]))
    for m in _ORD_COMMA.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.COMMA, ORDINALS[m.group(1).lower()], m.group(0)))
    for m in _NUM_ORD_COMMA.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.COMMA, m.group(1), m.group(0)))
    for m in _ROM_COMMA.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.COMMA, str(_roman_to_int(m.group(1))), m.group(0)))
    for m in _ORD_PERIODO.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.PERIODO, ORDINALS[m.group(1).lower()], m.group(0)))
    for m in _PERIODO.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.PERIODO, m.group(1), m.group(0)))
    for m in _ALLEGATO.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.ALLEGATO, norm_latin_suffix(m.group(1)), m.group(0)))

    base = _nonoverlap(spans)
    # NUMERO only when it directly follows a partition element ("lettera a), n. 3"); this
    # keeps it distinct from a document number ("d.P.R. n. 600").
    sub = {Entity.COMMA, Entity.PARAGRAPH, Entity.LETTER, Entity.ARTICLE, Entity.NUMERO}
    ends = sorted(s.end for s in base if s.entity in sub)
    for m in _NUMERO.finditer(text):
        if any(0 <= m.start() - e <= 8 and re.fullmatch(r"[\s,;()\.]*", text[e:m.start()])
               for e in ends):
            _emit_list(text, m, Entity.NUMERO, _NUMV_RE, norm_latin_suffix, spans)
    return _nonoverlap(spans)


def _resolve_backward(elements: List[Span], text: str) -> List[Span]:
    """"comma 1 dell'art. 19": a shallower element introduced by 'del…' owns the deeper run
    before it. Move it in front of that run (repeat until stable).

    The 'del…' must *immediately* precede the shallower element — otherwise an unrelated
    later article ("commi 5 a 7, del d.lgs. ..., mentre l'art. 22") would wrongly capture the
    comma run via the act's own "del". A list conjunction before the 'del…' also blocks the move:
    in "comma 1, e dell'art. 360" the "e" makes art. 360 a *new* article, not the comma's owner."""
    els = list(elements)
    for _ in range(len(els) * 2):
        moved = False
        for i in range(1, len(els)):
            conn = text[els[i - 1].end:els[i].start]
            dm = list(_DEL_RE.finditer(conn))
            adjacent = (bool(dm) and len(conn) - dm[-1].end() <= 4
                        and not re.search(r"\b(?:e|ed)\b", conn[:dm[-1].start()], I))
            if RANK[els[i].entity] < RANK[els[i - 1].entity] and adjacent:
                j = i - 1
                while j > 0 and RANK[els[j - 1].entity] > RANK[els[i].entity]:
                    j -= 1
                el = els.pop(i)
                els.insert(j, el)
                moved = True
                break
        if not moved:
            break
    return els


def segment(elements: List[Span], text: str) -> List[List[Span]]:
    """Turn a run of partition element spans into leaf paths (each a list of spans,
    shallow→deep). Empty input -> no leaves."""
    if not elements:
        return []
    els = _resolve_backward(sorted(elements, key=lambda s: s.start), text)
    leaves: List[List[Span]] = []
    path: List[tuple] = []          # list of (rank, span)
    for el in els:
        r = RANK[el.entity]
        if path and r <= path[-1][0]:
            leaves.append([s for _, s in path])
            path = [(pr, ps) for pr, ps in path if pr < r]
        path.append((r, el))
    if path:
        leaves.append([s for _, s in path])
    return leaves
