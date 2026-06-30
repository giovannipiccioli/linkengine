"""
Assembler: group recognized spans into Reference candidates.

Strategy (frame-based, still intentionally lightweight):

* **Anchored frames** start from act-identity spans (DOCTYPE and ALIAS). Each frame knows the
  coarse kind of citation it can form (legislation, prassi, case-law, EU act, alias) and which
  floating slots are compatible with it.
* **Orphan case-law frames** are built for court authorities with their own nearby numbers,
  dates, case numbers or Rv. values (e.g. "Cass. n. 123/2020", or "Sez. I ... Rv. 279726").
* A Reference is kept only if it has an act identity (doctype/alias/authority) AND a
  number/date/case-number — the validity rule.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .aliases import ALIAS_NIR, SELF_VALID_ALIASES
from .catalog import AGENCY_DOCTYPES, CASELAW_AUTH, CONDITIONAL_AGENCY_DOCTYPES
from .model import Entity, Reference, Span
from .partitions import segment, _resolve_backward

# Partition→act pairing connectors. A partition *run* (a contiguous block of partition spans
# with no act inside it) attaches to an act either on its RIGHT through a genitive
# ("art. 19 *del* d.lgs. 546") or by bare adjacency to a code alias ("art. 2697 c.c."), or on its
# LEFT when the act is immediately followed by it ("d.lgs. 546, art. 19"). ``_GEN_R`` is the
# right-side connector (genitive — optionally followed by the act's ordinal, "della VI direttiva"
# — or bare); ``_PUNCT`` is the left-side connector (only punctuation between act and partition).
_GEN_R = re.compile(
    r"^[\s,;:()]*(?:del(?:l[ao'’])?(?:la|le|lo|li|gli|i)?|dei|degli|d['’]|al|allo|all[ae]|"
    r"all['’]|agli|ai|nel(?:l[ao'’])?|sul(?:l[ao'’])?|ex)?\s*(?:[ivxlcdm]{1,6}\s+)?$", re.I)
_PUNCT = re.compile(r"^[\s,;:.()]*$")
# joins sibling article-groups that *share* one act ("art. 8 e art. 32 ... del d.lgs. 286",
# "artt. 2, 10, 29 e 30 Cost."). A bare "e"/"," (optionally with an elided article "l'") — but NOT
# a genitive: "e dell'art. 360 ... del c.p.c." starts a *fresh* act-phrase, so art. 360 is not in
# the list and ``dell'`` must break it.
_LISTSEP = re.compile(r"^[\s,;:()]*(?:e|ed)?\s*(?:l['’]|lo|la|gli|le|i)?\s*$", re.I)
_SENT_BOUND = re.compile(r"\.\s")
_CLAUSE_BOUND = re.compile(r";|\.(?:[\"'’”)\]]*\s*(?=[A-ZÀ-Ü(])|(?=[A-ZÀ-Ü]))")
_BOUNDARY_ABBR = re.compile(r"\b(?:n|nn|num|art|artt|co|c|lett|sez|sent|ord|cass|civ|pen)\.\s*", re.I)
_PROCEDURAL_LINE_BOUNDARY = re.compile(
    r"\n\s*(?:deposit(?:at[ao]|o)|fatto\s+e\s+diritto|svolgimento\b|motivi\b|"
    r"ritenuto\b|considerato\b|con\s+(?:ricors|appell)|il\s+ricorso\b)",
    re.I,
)
_DATE_AFTER_DOCTYPE = re.compile(r"^[\s,]*(?:del(?:l[ao])?\s+)?$", re.I)
_DATE_AFTER_NUMBER = re.compile(r"^[\s,]*(?:del(?:l[ao])?\s+)?$", re.I)
_DATE_BEFORE_NUMBER = re.compile(r"^[\s,]*(?:nn?\.?|num(?:ero)?\.?)?\s*\d", re.I)
_YEAR_AFTER_NUMBER = re.compile(r"^[\s,]*(?:del(?:l[ao])?\s+)?$", re.I)
_NUMBER_BEFORE_ANCHOR = re.compile(
    r"^[\s,;:()]*"
    r"(?:(?:del(?:la|lo|le|l['’])?|della|dello|delle|dei|degli|di)\s+)?$",
    re.I,
)
_NUMBER_BEFORE_COURT_HEADING = re.compile(
    r"^\s*(?:IN\s+NOME\s+DEL\s+POPOLO\s+ITALIANO\s*)?(?:LA\s+)?$", re.I)
_SERIES_SEP = re.compile(r"^[\s,;]*(?:e|ed)?\s*(?:nn?\.?\s*)?$", re.I)
_CASELAW_DATE_NUM_GAP = re.compile(r"^[\s,]*(?:\([^)]{0,90}\)[\s,]*)?$", re.I)
_UNKNOWN_RIGHT_ACT = re.compile(
    r"^[\s,]*(?:del(?:l[ao'’])?|della|dello|delle|dei|degli)\s+"
    r"(?!(?:[ivxlcdm]{1,6}\s+)?(?:cit(?:ato|ata|\.|\b)|d\.?\s?p\.?\s?r|d\.?\s?l|"
    r"d\.?\s?lgs|decret|legg|l\.|cod|c\.|t\.?\s?u|cost|statuto|direttiv|regolament))"
    r"[A-ZÀ-Üa-zà-ù][A-Za-zÀ-ÖØ-öø-ÿ.]*",
    re.I)
ANCHOR_ENTITIES = {Entity.DOCTYPE, Entity.ALIAS}
PARTITION_ENTITIES = {Entity.ALLEGATO, Entity.CONSIDERANDO, Entity.ARTICLE, Entity.COMMA,
                      Entity.PARAGRAPH, Entity.LETTER, Entity.NUMERO, Entity.PUNTO,
                      Entity.PERIODO}
TRAILING_SUBPART_ENTITIES = {Entity.COMMA, Entity.PARAGRAPH, Entity.LETTER, Entity.NUMERO,
                             Entity.PUNTO, Entity.PERIODO}
# CASELAW_AUTH is imported from catalog (the knowledge base) — the single source of truth.
# doctype anchors a court AUTHORITY may bind to. A court qualifies a *pronouncement*
# (sentenza/ordinanza), never a piece of legislation: "...c.p.c. Questa Corte, sentenza
# n. 4091" — "Questa Corte" belongs to the sentenza, not to the nearer c.p.c. alias.
CASELAW_DOCTYPE = {"SENT", "ORD"}
LOCAL_AUTH_DOCTYPE = {"COMUNE": {"DEL"}}

MAX_GAP = 70          # max char gap between a floating span and its anchor
ACT_NUMBER_GAP = 40   # legislation numbers need a local act marker, not intervening prose
AUTH_NUM_GAP = 35     # max gap for an orphan authority to claim a number

FRAME_CASELAW = "caselaw"
FRAME_PRASSI = "prassi"
FRAME_EU_ACT = "eu_act"
FRAME_ALIAS = "alias"
FRAME_ACT = "act"


@dataclass
class AnchorFrame:
    """A citation frame seeded by a DOCTYPE/ALIAS anchor.

    The frame is deliberately small: it owns the Reference being assembled and exposes the
    compatibility gates that used to be scattered through the nearest-anchor loop.
    """
    anchor: Span
    ref: Reference
    kind: str

    @property
    def doctype(self) -> str:
        return self.anchor.value if self.anchor.entity == Entity.DOCTYPE else ""

    @property
    def is_caselaw(self) -> bool:
        return self.kind == FRAME_CASELAW

    @property
    def is_prassi(self) -> bool:
        if self.kind == FRAME_PRASSI:
            return True
        return self.doctype in CONDITIONAL_AGENCY_DOCTYPES and not any(
            s.entity == Entity.EU_ACRONYM for s in self.ref.spans) and any(
                s.entity == Entity.OTHER_AUTH for s in self.ref.spans)

    @property
    def is_eu_act(self) -> bool:
        if self.kind == FRAME_EU_ACT:
            return True
        return any(s.entity == Entity.EU_ACRONYM for s in self.ref.spans)

    def add(self, span: Span) -> None:
        self.ref.spans.append(span)


@dataclass
class OrphanCaseLawFrame:
    """A court authority that builds its own citation without a doctype anchor."""
    authority: Span
    spans: List[Span]

    @classmethod
    def seed(cls, authority: Span) -> "OrphanCaseLawFrame":
        return cls(authority=authority, spans=[authority])

    def add(self, span: Span) -> None:
        if all(s is not span for s in self.spans):
            self.spans.append(span)

    def discard(self, span: Span) -> None:
        self.spans = [s for s in self.spans if s is not span]

    def to_reference(self) -> Reference:
        return Reference(spans=list(self.spans), start=self.authority.start, end=self.authority.end)


@dataclass
class OrphanFrameRegistry:
    """Provisional ownership for authority-led case-law frames.

    Ownership remains local until the series is complete because a later separator or date may
    move a span to a different authority. Completed frames are committed to ``AssemblyState``.
    """
    frames: Dict[int, OrphanCaseLawFrame]
    owner_by_span: Dict[int, Span] = field(default_factory=dict)

    @classmethod
    def create(cls, authorities: List[Span]) -> "OrphanFrameRegistry":
        return cls({id(authority): OrphanCaseLawFrame.seed(authority)
                    for authority in authorities})

    def frame_for(self, authority: Span) -> OrphanCaseLawFrame:
        return self.frames[id(authority)]

    def is_owned(self, span: Span) -> bool:
        return id(span) in self.owner_by_span

    def assign(self, span: Span, authority: Span) -> None:
        old_authority = self.owner_by_span.get(id(span))
        if old_authority is authority:
            return
        if old_authority is not None:
            self.frame_for(old_authority).discard(span)
        self.frame_for(authority).add(span)
        self.owner_by_span[id(span)] = authority

    def assign_through(self, span: Span, owned_span: Span) -> None:
        authority = self.owner_by_span.get(id(owned_span))
        if authority is None:
            raise ValueError("cannot assign through an unowned orphan-frame span")
        self.assign(span, authority)

    def references(self, authorities: List[Span]) -> List[Reference]:
        references = []
        for authority in authorities:
            frame = self.frame_for(authority)
            if any(span.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.CASE_NUMBER)
                   for span in frame.spans):
                references.append(frame.to_reference())
        return references


def _frame_kind(anchor: Span) -> str:
    if anchor.entity == Entity.ALIAS:
        return FRAME_ALIAS
    if anchor.entity != Entity.DOCTYPE:
        return FRAME_ACT
    if anchor.value in CASELAW_DOCTYPE:
        return FRAME_CASELAW
    if anchor.value in AGENCY_DOCTYPES:
        return FRAME_PRASSI
    if anchor.value == "DIR" or anchor.attrs.get("eu_hint") or anchor.attrs.get("scope") == "comunitario":
        return FRAME_EU_ACT
    return FRAME_ACT


def _build_anchor_frames(anchors: List[Span]) -> List[AnchorFrame]:
    return [
        AnchorFrame(
            anchor=a,
            ref=Reference(spans=[a], start=a.start, end=a.end),
            kind=_frame_kind(a),
        )
        for a in anchors
    ]


@dataclass
class AssemblyState:
    """Mutable state shared by the assembly phases.

    Span ownership used to be tracked independently in ``used``, ``bound_to`` and
    ``anchor_ref`` collections inside :func:`assemble`. Keeping it here makes binding a single
    operation and gives every phase the same indexed view of the recognized spans.
    """
    text: str
    spans: List[Span]
    anchors: List[Span]
    frames: List[AnchorFrame]
    floating: List[Span]
    by_entity: Dict[Entity, List[Span]]
    references: List[Reference]
    frame_by_anchor: Dict[int, AnchorFrame]
    owner_by_span: Dict[int, Reference] = field(default_factory=dict)
    attached_partition_ids: Set[int] = field(default_factory=set)
    boundary_cache: Dict[Tuple[int, int, int, int], bool] = field(default_factory=dict)

    @classmethod
    def create(cls, spans: List[Span], text: str) -> "AssemblyState":
        clean = [s for s in spans
                 if not (s.entity == Entity.DATE and s.attrs.get("role") == "proc")]
        clean.sort(key=lambda s: s.start)
        by_entity: Dict[Entity, List[Span]] = {}
        for span in clean:
            by_entity.setdefault(span.entity, []).append(span)
        anchors = [s for s in clean if s.entity in ANCHOR_ENTITIES]
        frames = _build_anchor_frames(anchors)
        return cls(
            text=text,
            spans=clean,
            anchors=anchors,
            frames=frames,
            floating=[s for s in clean if s.entity not in ANCHOR_ENTITIES],
            by_entity=by_entity,
            references=[f.ref for f in frames],
            frame_by_anchor={id(f.anchor): f for f in frames},
        )

    def of(self, *entities: Entity) -> List[Span]:
        return [span for entity in entities for span in self.by_entity.get(entity, [])]

    def owner_of(self, span: Span) -> Optional[Reference]:
        return self.owner_by_span.get(id(span))

    def is_owned(self, span: Span) -> bool:
        return id(span) in self.owner_by_span

    def bind(self, span: Span, target: Reference) -> None:
        if all(existing is not span for existing in target.spans):
            target.spans.append(span)
        self.owner_by_span[id(span)] = target

    def bind_through(self, span: Span, owned_span: Span) -> None:
        """Bind ``span`` to the frame that already owns ``owned_span``."""
        target = self.owner_of(owned_span)
        if target is None:
            raise ValueError("cannot bind through an unowned span")
        self.bind(span, target)

    def add_reference(self, ref: Reference) -> None:
        self.references.append(ref)
        for span in ref.spans:
            self.owner_by_span[id(span)] = ref

    def attach_partition(self, span: Span, target: Optional[Reference] = None) -> None:
        self.attached_partition_ids.add(id(span))
        if target is not None:
            self.bind(span, target)

    def reference_span_ids(self) -> Set[int]:
        return {id(span) for ref in self.references for span in ref.spans}

    def hard_boundary(self, a: Span, b: Span) -> bool:
        left, right = ((a.start, a.end), (b.start, b.end))
        if left > right:
            left, right = right, left
        key = left + right
        result = self.boundary_cache.get(key)
        if result is None:
            result = _hard_boundary_between(self.text, a, b)
            self.boundary_cache[key] = result
        return result


def _frame_accepts_slot(frame: AnchorFrame, span: Span) -> bool:
    """Coarse structural compatibility for non-partition spans."""
    if span.entity in PARTITION_ENTITIES:
        return False
    if span.entity in (Entity.CASE_NUMBER, Entity.RV_NUMBER):
        return frame.is_caselaw
    if span.entity == Entity.AUTHORITY and span.value in CASELAW_AUTH:
        return frame.is_caselaw
    if span.entity == Entity.OTHER_AUTH:
        return frame.is_prassi or frame.doctype in CONDITIONAL_AGENCY_DOCTYPES
    if span.entity == Entity.AUTHORITY and span.value in LOCAL_AUTH_DOCTYPE:
        return frame.doctype in LOCAL_AUTH_DOCTYPE[span.value]
    if span.entity == Entity.NUM_YEAR and span.attrs.get("prax_number"):
        return frame.is_prassi
    return True


def _candidate_frames(span: Span, frames: List[AnchorFrame]) -> List[AnchorFrame]:
    return [f for f in frames if _frame_accepts_slot(f, span)]


def _frame_accepts_partition_group(frame: AnchorFrame, group: List[Span]) -> bool:
    """Structural partition compatibility.

    Prassi citations do not normally carry legal partitions. Recitals are meaningful only on
    EU legislative frames; if they occur next to a national act we consume them without binding
    so they cannot hop to another nearby citation.
    """
    if frame.is_prassi:
        return False
    if any(s.entity == Entity.CONSIDERANDO for s in group):
        return frame.is_eu_act and frame.doctype in {"REG", "DIR", "DECIS"}
    return True


def _gap(a: Span, b: Span) -> int:
    return max(0, a.start - b.end, b.start - a.end)


def _semicolon_between(text: str, a: Span, b: Span) -> bool:
    """True if a ';' separates the two spans. A semicolon is a citation-list boundary, so an
    act number must not bind to an anchor on the other side of one ("Circolare ... n. 47/2005;
    direttiva 2006/112" — 47/2005 is the circolare's, not the directive's)."""
    lo, hi = (a.end, b.start) if a.end <= b.start else (b.end, a.start)
    return ";" in text[lo:hi]


def _hard_boundary_between(text: str, a: Span, b: Span) -> bool:
    lo, hi = (a.end, b.start) if a.end <= b.start else (b.end, a.start)
    raw = text[lo:hi]
    if ";" in raw:
        return True
    if "\n" in raw and _PROCEDURAL_LINE_BOUNDARY.search(raw):
        return True
    if "." not in raw:
        return False
    # A long dotted gap cannot be a local citation connector; avoid running abbreviation cleanup
    # over whole paragraphs when a far-away anchor is being considered.
    if len(raw) > 160:
        return True
    gap = _BOUNDARY_ABBR.sub("", raw)
    return bool(_CLAUSE_BOUND.search(gap))


def _span_between(text: str, a: Span, b: Span) -> str:
    lo, hi = (a.end, b.start) if a.end <= b.start else (b.end, a.start)
    return text[lo:hi]


def _number_can_precede_authority(text: str, number: Span, authority: Span) -> bool:
    if number.end > authority.start:
        return True
    gap = text[number.end:authority.start]
    return bool(_NUMBER_BEFORE_ANCHOR.match(gap) or _NUMBER_BEFORE_COURT_HEADING.match(gap))


def _ref_has_year(ref: Reference) -> bool:
    for s in ref.spans:
        if s.entity in (Entity.NUM_YEAR, Entity.YEAR, Entity.DATE):
            if s.entity == Entity.NUM_YEAR and not s.attrs.get("year"):
                continue
            return True
    return False


def _is_caselaw_anchor(a: Span) -> bool:
    return a.entity == Entity.DOCTYPE and a.value in CASELAW_DOCTYPE


def _is_caselaw_ref(ref: Reference) -> bool:
    return any(s.entity == Entity.DOCTYPE and s.value in CASELAW_DOCTYPE for s in ref.spans) or \
        any(s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH for s in ref.spans)


def _date_should_bind(s: Span, a: Span, ref: Reference, text: str) -> bool:
    """A legislation/prassi date is accepted only when it looks like the act's own date.
    Leading/trailing narrative dates are left free so they neither fill ``doc-date`` nor
    stretch the visible anchor."""
    if _is_caselaw_anchor(a):
        return s.start >= a.start and not _hard_boundary_between(text, s, a)
    if a.entity == Entity.ALIAS:
        return False
    if _ref_has_year(ref):
        return False
    if s.start < a.start:
        return False
    nums = [n for n in ref.spans if n.entity in (Entity.NUMBER, Entity.NUM_YEAR)]
    if any(n.end <= s.start and s.start - n.end <= 24
           and _DATE_AFTER_NUMBER.match(text[n.end:s.start]) for n in nums):
        return True
    if _hard_boundary_between(text, s, a):
        return False
    if _DATE_AFTER_DOCTYPE.match(text[a.end:s.start]):
        return True
    if s.start - a.end <= 32 and _DATE_BEFORE_NUMBER.match(text[s.end:s.end + 18]):
        return True
    return False


def _year_should_bind(s: Span, a: Span, ref: Reference, text: str) -> bool:
    if _is_caselaw_anchor(a):
        return s.start >= a.start and not _ref_has_year(ref) and not _hard_boundary_between(text, s, a)
    if a.entity == Entity.ALIAS:
        return False
    if s.start < a.start or _hard_boundary_between(text, s, a):
        return False
    if _ref_has_year(ref):
        return False
    nums = [n for n in ref.spans if n.entity in (Entity.NUMBER, Entity.NUM_YEAR)]
    return any(n.end <= s.start and s.start - n.end <= 24
               and _YEAR_AFTER_NUMBER.match(text[n.end:s.start]) for n in nums)


def _article_groups(part_spans: List[Span], anchors: List[Span], text: str) -> List[List[Span]]:
    """Split partition spans into **article-groups** — one article (ARTICLE/ALLEGATO) plus its
    dependent sub-partitions, or a top-level sub-partition run with no article ("commi 1 e 2").
    Each group is paired to one act. We first cut the spans into act-bounded *runs* (no act /
    sentence boundary / wide gap inside), resolve backward "del…" links per run so a sub-part
    sits with its article ("comma 1 dell'art. 19" -> art. 19 owns comma 1), then start a new
    group at every article."""
    spans = sorted(part_spans, key=lambda s: s.start)
    runs: List[List[Span]] = []
    cur: List[Span] = []
    for s in spans:
        if cur:
            gap = text[cur[-1].end:s.start]
            if _SENT_BOUND.search(gap) or len(gap) > 80 or \
                    any(cur[-1].end <= a.start and a.end <= s.start for a in anchors):
                runs.append(cur); cur = []
        cur.append(s)
    if cur:
        runs.append(cur)

    HEAD = (Entity.ARTICLE, Entity.ALLEGATO, Entity.CONSIDERANDO)
    groups: List[List[Span]] = []
    for run in runs:
        g: List[Span] = []
        for s in _resolve_backward(run, text):       # canonical shallow->deep order
            if s.entity in HEAD and g:
                groups.append(g); g = []
            g.append(s)
        if g:
            groups.append(g)
    return groups


def _pair_group(i: int, tokens, text: str) -> Optional[Span]:
    """Pick the act an article-group binds to, in precedence order:
    1. **right-direct** — the act just after it via a genitive / bare adjacency ("art. 19 *del*
       d.lgs.", "art. 2697 c.c.");
    2. **right-list** — the act ending a list of sibling groups that *share* it ("art. 8 e art. 32
       ... *del* d.lgs. 286"); a list breaks at a genitive ("e *dell'*art. 360 ... del c.p.c.");
    3. **left-direct** — the act just before it, only punctuation between ("d.lgs. 546, art. 19");
    4. **left-list** — the act starting such a list on the left;
    5. **nearest fallback** — only for an article-rooted group with dirty connectors
       ("art. 156 ult. co. c.p.p."), to the closest act within a short window.
    Returns the act anchor Span, or None (leave unpaired)."""
    n, (_, g, gs, ge) = len(tokens), tokens[i]
    # 1. right-direct
    if i + 1 < n and tokens[i + 1][0] == "act" and _GEN_R.match(text[ge:tokens[i + 1][2]]):
        return tokens[i + 1][1]
    # 2. right-list
    j = i
    while j + 1 < n and tokens[j + 1][0] == "grp" and _LISTSEP.match(text[tokens[j][3]:tokens[j + 1][2]]):
        j += 1
    if j > i and j + 1 < n and tokens[j + 1][0] == "act" and _GEN_R.match(text[tokens[j][3]:tokens[j + 1][2]]):
        return tokens[j + 1][1]
    # 3. left-direct
    if i > 0 and tokens[i - 1][0] == "act" and _PUNCT.match(text[tokens[i - 1][3]:gs]):
        return tokens[i - 1][1]
    # 4. left-list
    j = i
    while j - 1 >= 0 and tokens[j - 1][0] == "grp" and _LISTSEP.match(text[tokens[j - 1][3]:tokens[j][2]]):
        j -= 1
    if j < i and j - 1 >= 0 and tokens[j - 1][0] == "act" and _PUNCT.match(text[tokens[j - 1][3]:tokens[j][2]]):
        return tokens[j - 1][1]
    # 5. nearest fallback (article-rooted groups only; a punto/paragrafo-only group stays free
    # for the CGUE catch-all rather than latch onto a legislation act)
    if any(s.entity in (Entity.ARTICLE, Entity.ALLEGATO, Entity.CONSIDERANDO) for s in g):
        best, cand = 26, None
        for t in tokens:
            if t[0] != "act":
                continue
            d = max(0, t[2] - ge, gs - t[3])
            if d < best:
                best, cand = d, t[1]
        return cand
    return None


def _unknown_right_act_after_group(i: int, tokens, text: str) -> bool:
    """A partition list followed by an unrecognized named act belongs to that act, not to
    some nearby recognized act. Treat the group as intentionally unpaired so precision wins:
    "artt. 20 e 31 della Carta" should not attach to a nearby directive once bare Carta is
    no longer an alias."""
    n = len(tokens)
    if tokens[i][0] != "grp":
        return False
    j = i
    while j + 1 < n and tokens[j + 1][0] == "grp" and \
            _LISTSEP.match(text[tokens[j][3]:tokens[j + 1][2]]):
        j += 1
    if j + 1 < n and tokens[j + 1][0] == "act" and \
            _GEN_R.match(text[tokens[j][3]:tokens[j + 1][2]]):
        return False
    next_start = tokens[j + 1][2] if j + 1 < n else min(len(text), tokens[j][3] + 48)
    tail = text[tokens[j][3]:next_start]
    if re.match(r"\s*c\.?\s?c\.?\s?n\.?\s?l\.?\b|\s*ccnl\b", tail, re.I):
        return True
    return bool(_UNKNOWN_RIGHT_ACT.match(tail))


def _pair_partitions(state: AssemblyState) -> None:
    """Attach each partition article-group to the act it modifies (``_pair_group``), adding the
    group's spans to that anchor's Reference. Unpaired spans stay free for the CGUE phase or are
    dropped — better to miss a partition than mis-bind it."""
    anchors = state.anchors
    groups = _article_groups(
        [s for s in state.floating if s.entity in PARTITION_ENTITIES], anchors, state.text)
    if not anchors or not groups:
        return
    tokens = []
    for a in anchors:
        frame = state.frame_by_anchor[id(a)]
        ident = [s for s in frame.ref.spans if s.entity in _ACT_IDENTITY] or [a]
        tokens.append(("act", a, min(s.start for s in ident), max(s.end for s in ident)))
    for g in groups:
        tokens.append(("grp", g, min(s.start for s in g), max(s.end for s in g)))
    tokens.sort(key=lambda t: t[2])

    for i, tok in enumerate(tokens):
        if tok[0] != "grp":
            continue
        if _unknown_right_act_after_group(i, tokens, state.text):
            for span in tok[1]:
                state.attach_partition(span)
            continue
        target = _pair_group(i, tokens, state.text)
        if target is not None:
            frame = state.frame_by_anchor[id(target)]
            if not _frame_accepts_partition_group(frame, tok[1]):
                for span in tok[1]:
                    state.attach_partition(span)
                continue
            for span in tok[1]:
                state.attach_partition(span, frame.ref)


def _attach_trailing_subparts(state: AssemblyState) -> None:
    """Attach subpartitions that sit immediately after a code alias whose article is before it.

    Italian codes are often written as "art. 360 c.p.c., comma 1, n. 5": the article belongs
    to the code alias on the right, while the comma/numero trail after the alias. The main
    article-group pairing intentionally stops at the act anchor, so this small local pass adds
    the trailing subparts to the already-paired article reference.
    """
    subparts = sorted(
        [s for s in state.floating
         if s.entity in TRAILING_SUBPART_ENTITIES
         and id(s) not in state.attached_partition_ids],
        key=lambda s: s.start)
    if not subparts:
        return
    for frame in state.frames:
        ref = frame.ref
        if not any(s.entity in (Entity.ARTICLE, Entity.ALLEGATO, Entity.CONSIDERANDO)
                   for s in ref.spans):
            continue
        cursor = frame.anchor.end
        while True:
            cand = None
            for s in subparts:
                if id(s) in state.attached_partition_ids or s.start < cursor:
                    continue
                if s.start - cursor > 18:
                    break
                if _PUNCT.match(state.text[cursor:s.start]):
                    cand = s
                break
            if cand is None:
                break
            state.attach_partition(cand, ref)
            cursor = cand.end


def _build_orphan_caselaw_refs(state: AssemblyState) -> List[Reference]:
    """Build case-law frames where the court authority is itself the anchor.

    This owns the Cassazione/Corte/CGUE series logic that does not start from an explicit
    ``sentenza`` or ``ordinanza`` doctype frame: "Cass. 10266/2018, 30927/2018", "Sez. I,
    n. ... Rv. ...", and date-before-number variants.
    """
    text = state.text
    anchors = state.anchors
    cl_auths = [s for s in state.of(Entity.AUTHORITY) if s.value in CASELAW_AUTH]
    free_auths = [s for s in cl_auths if not state.is_owned(s)]
    # only spans not already bound to an act (a number bound to its own doctype, "d.lgs. ...
    # n. 546", must not also be claimed by a nearby court).
    numbers = [s for s in state.of(Entity.NUMBER, Entity.NUM_YEAR, Entity.CASE_NUMBER)
               if not state.is_owned(s)]
    rv_nums = [s for s in state.of(Entity.RV_NUMBER) if not state.is_owned(s)]
    # a standalone YEAR is treated like a date here so the "court YEAR, n. NUM" form
    # ("Cassazione 1998, n. 4775") supplies the ECLI year (a year alone never makes a ref).
    dates = [s for s in state.of(Entity.DATE, Entity.YEAR) if not state.is_owned(s)]

    def owner(span: Span) -> Optional[Span]:
        """Nearest compatible court authority for a number/date/Rv span."""
        cands = [au for au in free_auths if _gap(au, span) <= AUTH_NUM_GAP
                 and not state.hard_boundary(au, span)
                 and not (state.anchors
                          and min(_gap(span, a) for a in state.anchors) < _gap(au, span))]
        if span.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.CASE_NUMBER):
            cands = [au for au in cands
                     if _number_can_precede_authority(state.text, span, au)]
        cands = [au for au in cands
                 if not (au.value == "THIS_COURT" and au.start > span.end
                         and re.search(r"\bR\.?\s?V\.?", text[span.end:au.start], re.I))]
        if span.entity == Entity.RV_NUMBER:
            cands = [au for au in cands if au.end <= span.start]
        if not cands:
            return None
        pre = [au for au in cands if au.end <= span.start]
        return (min(pre, key=lambda a: span.start - a.end) if pre
                else min(cands, key=lambda a: _gap(a, span)))

    registry = OrphanFrameRegistry.create(free_auths)

    for s in numbers + dates + rv_nums:
        o = owner(s)
        if o is not None:
            registry.assign(s, o)

    # Continue a number/date list governed by one authority ("Cass. 10266/2018, 30927/2018").
    series_items = sorted(numbers + dates, key=lambda x: x.start)
    for s in series_items:
        prev = next((p for p in reversed(series_items)
                     if p.end <= s.start and registry.is_owned(p)), None)
        if prev is None:
            continue
        gap = text[prev.end:s.start]
        if not _SERIES_SEP.match(gap):
            continue
        if any(prev.end <= o.start and o.end <= s.start for o in cl_auths + anchors):
            continue
        registry.assign_through(s, prev)

    # Bridge through the date: a docket number trailing a date already owned by a court
    # ("Cass. ..., 14 gennaio 2015, n. 428") belongs to that court even when too far from the
    # court keyword itself for owner(). Bind it to the nearest preceding owned date.
    for s in numbers:
        if registry.is_owned(s):
            continue
        best, best_gap = None, 26
        for au in free_auths:
            for d in registry.frame_for(au).spans:
                gap = text[d.end:s.start]
                relaxed = d.entity == Entity.DATE and d.end <= s.start and \
                    _CASELAW_DATE_NUM_GAP.match(gap) and (s.start - d.end) < 95
                ordinary = d.entity == Entity.DATE and d.end <= s.start and \
                    (s.start - d.end) < best_gap
                if (ordinary or relaxed) \
                        and not (anchors and min(_gap(s, a) for a in anchors) < (s.start - d.end)):
                    best, best_gap = au, s.start - d.end
        if best is not None:
            registry.assign(s, best)

    for rv in rv_nums:
        if registry.is_owned(rv):
            continue
        previous = [s for s in numbers + dates
                    if s.end <= rv.start and registry.is_owned(s) and rv.start - s.end <= 95]
        if not previous:
            continue
        prev = max(previous, key=lambda s: s.end)
        if any(prev.end <= o.start and o.end <= rv.start for o in cl_auths + anchors):
            continue
        registry.assign_through(rv, prev)

    return registry.references(free_auths)


def _bind_date_through_number(state: AssemblyState, date: Span) -> bool:
    """Bind a trailing date through a number already owned by a prassi/case-law frame."""
    previous_prax = [number for number in state.of(Entity.NUM_YEAR)
                     if number.attrs.get("prax_number")
                     and number.end <= date.start and date.start - number.end <= 32
                     and state.is_owned(number)
                     and _DATE_AFTER_NUMBER.match(state.text[number.end:date.start])]
    if previous_prax:
        number = max(previous_prax, key=lambda span: span.end)
        state.bind_through(date, number)
        return True

    previous_case = [number for number in state.of(Entity.NUMBER, Entity.NUM_YEAR)
                     if number.end <= date.start and date.start - number.end <= 45
                     and state.is_owned(number)
                     and _is_caselaw_ref(state.owner_of(number))
                     and _DATE_AFTER_NUMBER.match(state.text[number.end:date.start])]
    if previous_case:
        number = max(previous_case, key=lambda span: span.end)
        state.bind_through(date, number)
        return True
    return False


def _select_anchor_frame(state: AssemblyState, span: Span,
                         candidates: List[AnchorFrame],
                         court_authorities: List[Span]) -> Tuple[Optional[AnchorFrame], int, bool]:
    """Select the local compatible frame and report whether the number is act-internal."""
    best_frame: Optional[AnchorFrame] = None
    best_gap = MAX_GAP + 1
    for frame in candidates:
        anchor = frame.anchor
        gap = _gap(span, anchor)
        if gap >= best_gap or gap > MAX_GAP:
            continue
        if span.entity in (Entity.NUMBER, Entity.NUM_YEAR) and \
                not frame.is_caselaw and not frame.is_prassi and gap > ACT_NUMBER_GAP:
            continue
        if span.entity in (Entity.NUMBER, Entity.NUM_YEAR) and span.end <= anchor.start \
                and not _NUMBER_BEFORE_ANCHOR.match(state.text[span.end:anchor.start]):
            continue
        if span.entity in (Entity.NUMBER, Entity.NUM_YEAR) and \
                (_semicolon_between(state.text, span, anchor)
                 or state.hard_boundary(span, anchor)):
            continue
        best_frame, best_gap = frame, gap

    act_internal = False
    if span.entity in (Entity.NUM_YEAR, Entity.NUMBER):
        preceding = [frame for frame in candidates if frame.anchor.end <= span.start
                     and span.start - frame.anchor.end <= 30
                     and not _semicolon_between(state.text, span, frame.anchor)
                     and not any(frame.anchor.end <= authority.start
                                 and authority.end <= span.start
                                 for authority in court_authorities)
                     and not any(frame.anchor.end <= other.start and other.end <= span.start
                                 for other in state.anchors if other is not frame.anchor)]
        if preceding:
            best_frame = min(preceding, key=lambda frame: span.start - frame.anchor.end)
            best_gap = span.start - best_frame.anchor.end
            act_internal = True
    return best_frame, best_gap, act_internal


def _bind_anchor_slots(state: AssemblyState) -> None:
    """Phase 1: bind numbers, dates and authorities to compatible anchored frames."""
    court_authorities = [span for span in state.of(Entity.AUTHORITY)
                         if span.value in CASELAW_AUTH]
    for span in state.floating:
        if span.entity in PARTITION_ENTITIES:
            continue
        candidates = _candidate_frames(span, state.frames)
        if not candidates:
            continue
        if span.entity == Entity.DATE and _bind_date_through_number(state, span):
            continue

        frame, gap, act_internal = _select_anchor_frame(
            state, span, candidates, court_authorities)
        if frame is None:
            continue
        anchor = frame.anchor
        if span.entity == Entity.DATE and \
                not _date_should_bind(span, anchor, frame.ref, state.text):
            continue
        if span.entity == Entity.YEAR and \
                not _year_should_bind(span, anchor, frame.ref, state.text):
            continue
        if anchor.entity == Entity.ALIAS and span.entity in (
                Entity.NUMBER, Entity.NUM_YEAR, Entity.YEAR):
            continue
        if span.entity in (Entity.AUTHORITY, Entity.OTHER_AUTH) and \
                state.hard_boundary(span, anchor):
            continue
        if span.entity == Entity.EU_ACRONYM and \
                (_is_caselaw_anchor(anchor) or state.hard_boundary(span, anchor)):
            continue
        if not act_internal and span.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.DATE) and \
                not (span.entity == Entity.NUM_YEAR and span.attrs.get("prax_number")) and \
                any(_gap(span, authority) < gap for authority in court_authorities):
            continue
        if span.entity == Entity.AUTHORITY and span.value in CASELAW_AUTH:
            lo, hi = ((anchor.end, span.start) if anchor.end <= span.start
                      else (span.end, anchor.start))
            if any(authority is not span and lo <= authority.start and authority.end <= hi
                   for authority in court_authorities):
                continue
        state.bind(span, frame.ref)


def _bind_partitions(state: AssemblyState) -> None:
    """Phase 2: assign complete partition groups, then local trailing subpartitions."""
    _pair_partitions(state)
    _attach_trailing_subparts(state)


def _bind_through_court_authorities(state: AssemblyState) -> None:
    """Phase 3: let a court already on a pronouncement carry its nearby loose identity slots."""
    court_authorities = [span for span in state.of(Entity.AUTHORITY)
                         if span.value in CASELAW_AUTH]
    bound_authorities = [span for span in court_authorities if state.is_owned(span)]
    numeric_slots = {Entity.NUMBER, Entity.NUM_YEAR, Entity.DATE, Entity.RV_NUMBER}
    for span in state.floating:
        if state.is_owned(span) or span.entity not in numeric_slots:
            continue
        near = [authority for authority in bound_authorities
                if _gap(span, authority) <= AUTH_NUM_GAP
                and not state.hard_boundary(span, authority)]
        if span.entity in (Entity.NUMBER, Entity.NUM_YEAR):
            near = [authority for authority in near
                    if _number_can_precede_authority(state.text, span, authority)]
        if not near:
            continue
        authority = min(near, key=lambda candidate: _gap(span, candidate))
        if any(_gap(span, other) < _gap(span, authority)
               and not state.hard_boundary(span, other)
               for other in court_authorities if other is not authority):
            continue
        state.bind_through(span, authority)


def _build_orphan_frames(state: AssemblyState) -> None:
    """Phase 4: build authority-led case-law frames and standalone CGUE case frames."""
    for ref in _build_orphan_caselaw_refs(state):
        state.add_reference(ref)
    claimed = state.reference_span_ids()
    for case_number in state.of(Entity.CASE_NUMBER):
        if id(case_number) not in claimed:
            state.add_reference(Reference(spans=[case_number]))


def _bind_cgue_partitions(state: AssemblyState) -> None:
    """Phase 5: bind still-loose points/paragraphs only to nearby CGUE references."""
    case_refs = [ref for ref in state.references
                 if any(span.entity == Entity.CASE_NUMBER for span in ref.spans)
                 or any(span.entity == Entity.AUTHORITY and span.value == "CGUE"
                        for span in ref.spans)]
    claimed = state.reference_span_ids()
    loose = [span for span in state.floating
             if span.entity in PARTITION_ENTITIES and id(span) not in claimed]
    for partition in loose:
        best, best_gap = None, MAX_GAP + 1
        for ref in case_refs:
            refspan = Span(min(span.start for span in ref.spans),
                           max(span.end for span in ref.spans), Entity.DOCTYPE, "", "")
            if state.hard_boundary(partition, refspan) or \
                    "[[" in _span_between(state.text, partition, refspan):
                continue
            gap = _gap(partition, refspan)
            if gap < best_gap:
                best, best_gap = ref, gap
        if best is not None:
            state.bind(partition, best)


def _finalize_frames(state: AssemblyState) -> List[Reference]:
    """Phase 6: branch partitions/numbers, validate references, and assign visible anchors."""
    out: List[Reference] = []
    for ref in state.references:
        if any(span.entity == Entity.AUTHORITY and span.value in CASELAW_AUTH
               and span.value != "THIS_COURT" for span in ref.spans):
            ref.spans = [span for span in ref.spans
                         if not (span.entity == Entity.AUTHORITY
                                 and span.value == "THIS_COURT")]
        partitions = [span for span in ref.spans if span.entity in PARTITION_ENTITIES]
        identity = [span for span in ref.spans if span.entity not in PARTITION_ENTITIES]
        leaves = segment(partitions, state.text) if partitions else [[]]
        children = [child for child in _partition_number_children(identity, leaves)
                    if _valid(child)]
        _assign_text_context(children, state.text)
        out.extend(child for child in children if child.attrs.get("text"))

    out += _propagate_acts(
        out, state.spans, state.text, state.attached_partition_ids)
    return out


def assemble(spans: List[Span], text: str) -> List[Reference]:
    """Assemble recognized spans through explicit frame ownership phases."""
    state = AssemblyState.create(spans, text)
    _bind_anchor_slots(state)
    _bind_partitions(state)
    _bind_through_court_authorities(state)
    _build_orphan_frames(state)
    _bind_cgue_partitions(state)
    return _finalize_frames(state)


def _assign_text_context(children: List[Reference], text: str) -> None:
    """Set each split reference's ``text`` (its own sub-part) and ``context`` (the whole
    expression, shared by every sibling). Siblings are bounded by
    their *distinguishing* span (the partition element or number that varies between them),
    so "artt. 14, 15 e 18 del d.lgs. 546/1992" yields text 'artt. 14' / '15' /
    '18 del d.lgs. 546/1992' under one common context. An interpolated range element renders
    as just its symbol ('-' / 'a')."""
    if not children:
        return
    cstart = min(s.start for c in children for s in c.spans)
    cend = max(s.end for c in children for s in c.spans)
    context = text[cstart:cend].strip()
    # a child's "key" is the span that distinguishes it from its siblings — the one unique to
    # it. An article shared by several comma-children (art23 in art23-comma5/6/7) appears in
    # >1 child, so it is not the key (else they'd collide and lose their text).
    idcount = Counter(id(s) for c in children for s in c.spans)

    def keyspan(c: Reference) -> Span:
        uniq = [s for s in c.spans if idcount[id(s)] == 1] or c.spans
        return min(uniq, key=lambda s: s.start)

    keyed = sorted(((keyspan(c), c) for c in children), key=lambda kc: kc[0].start)
    n = len(keyed)

    def trim_chunk(t: str) -> str:
        if re.match(r"^(?:artt?\.?|articol[oi]|comm[ai]|paragraf[oi]|punt[oi]|lett|n\.|\d)",
                    t, re.I):
            t = re.split(r",\s+per\b", t, maxsplit=1, flags=re.I)[0]
        t = re.sub(r"[\s,;]+(?:n\.|nn\.?|num(?:ero)?\.?)\s*$", "", t, flags=re.I)
        return t.strip(" ,;")

    for i, (k, c) in enumerate(keyed):
        c.spans.sort(key=lambda s: s.start)
        c.attrs["context"] = context
        if k.attrs.get("fill"):                  # interpolated range element: just the symbol
            c.start, c.end, c.attrs["text"] = k.start, k.end, text[k.start:k.end].strip()
            continue
        c.start = min(s.start for s in c.spans)
        c.end = max(s.end for s in c.spans)
        tstart = cstart if i == 0 else k.start
        tend = cend if i == n - 1 else keyed[i + 1][0].start
        t = trim_chunk(text[tstart:tend])
        for suf in (" e", " ed"):              # drop a trailing conjunction ("15 e" -> "15")
            if t.endswith(suf):
                t = t[:-len(suf)].rstrip(" ,;")
        c.attrs["text"] = t


# Spans that define an act's *identity* (everything except the cited partition); these are
# "borrowed" when an orphan article inherits a nearby act.
_ACT_IDENTITY = {Entity.DOCTYPE, Entity.ALIAS, Entity.AUTHORITY, Entity.OTHER_AUTH,
                 Entity.NUM_YEAR, Entity.NUMBER, Entity.YEAR, Entity.DATE, Entity.EU_ACRONYM,
                 Entity.CASE_NUMBER}
_PROPAGATING_ALIASES = set(ALIAS_NIR) - {"COST"}
MAX_PROP_DIST = 150          # chars: how far back a bare article may inherit a code/TU alias
MAX_PROP_DIST_ACT = 100      # tighter window for a doctype+number act (number must not stray)


def _is_conversion_law_source(ident: List[Span], text: str) -> bool:
    """A law cited only as the conversion law of a decree-law is a poor source for later
    bare-article inheritance: later "articolo 2" usually still points to the converted
    decreto-legge, not to "legge ... n. X" introduced by "convertito ... dalla legge"."""
    doctype = next((s for s in ident if s.entity == Entity.DOCTYPE), None)
    if doctype is None or doctype.value != "L":
        return False
    before = text[max(0, doctype.start - 70):doctype.start]
    return bool(re.search(r"\bconvertit[oa]\b.{0,50}\bdalla\s+$", before, re.I | re.S))


def _propagate_acts(refs: List[Reference], spans: List[Span], text: str,
                    attached_partition_ids=None) -> List[Reference]:
    """Intra-document context: a bare "art. N" with no act of its
    own inherits the **nearest preceding** act. Two kinds of source:

    * an **alias act** (codici / testi unici, ``codice civile`` -> ``art. 1362``): codes are
      routinely cited by bare article and have no ambiguous number to mis-bind — wide window;
    * a **doctype + number national act** (``d.lgs. 546/1992`` -> a later ``art. 5``): also
      common, but it carries a number that must not stray, so a tighter window and never for
      case-law (an ECLI takes no partition).

    Conservative: ARTICLE orphans only, inherited text = the article mention only.
    """
    acts = []          # (position, identity-spans, max-distance)
    # code / TU alias acts — taken from the raw spans so a *bare* alias with no partition of
    # its own ("Il codice civile disciplina... [far] ...l'art. 1218") is still a source.
    for s in spans:
        if s.entity == Entity.ALIAS and s.value in _PROPAGATING_ALIASES:
            acts.append((s.start, [s], MAX_PROP_DIST))
    for r in refs:
        if any(s.entity == Entity.ALIAS for s in r.spans):
            continue
        doctype = next((s for s in r.spans if s.entity == Entity.DOCTYPE), None)
        has_num = any(s.entity in (Entity.NUMBER, Entity.NUM_YEAR) for s in r.spans)
        is_caselaw = (doctype is not None and doctype.value in CASELAW_DOCTYPE) or any(
            s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH for s in r.spans)
        if doctype is not None and has_num and not is_caselaw:
            ident = [s for s in r.spans if s.entity in _ACT_IDENTITY]
            is_prassi = doctype.value in AGENCY_DOCTYPES or (
                doctype.value in CONDITIONAL_AGENCY_DOCTYPES
                and any(s.entity == Entity.OTHER_AUTH for s in ident)
                and not any(s.entity == Entity.EU_ACRONYM for s in ident)
            )
            if is_prassi:
                continue
            if _is_conversion_law_source(ident, text):
                continue
            acts.append((r.start, ident, MAX_PROP_DIST_ACT))
    if not acts:
        return []

    attached_partition_ids = attached_partition_ids or set()
    used = {(s.start, s.end) for r in refs for s in r.spans if s.entity == Entity.ARTICLE}
    used.update((s.start, s.end) for s in spans
                if s.entity == Entity.ARTICLE and id(s) in attached_partition_ids)
    orphans = [s for s in spans
               if s.entity == Entity.ARTICLE and (s.start, s.end) not in used]
    subs = [s for s in spans if s.entity in _SUBPART]

    new: List[Reference] = []
    for art in orphans:
        if _UNKNOWN_RIGHT_ACT.match(text[art.end:art.end + 32]):
            continue
        if re.match(r"^[\s,]*[I1]\.\s*(?:n[.°]*\s*)?\d", text[art.end:art.end + 32], re.I):
            continue
        preceding = [(pos, ident) for pos, ident, md in acts
                     if pos <= art.start and art.start - pos <= md]
        if not preceding:
            continue
        _, ident = max(preceding, key=lambda x: x[0])      # most recent preceding act
        mine = [art] + [s for s in subs if 0 <= s.start - art.end <= 18]   # commas just after
        local = list(mine)
        ref = Reference(spans=list(ident) + mine)
        ref.spans.sort(key=lambda s: s.start)
        ref.start = min(s.start for s in local)
        ref.end = max(s.end for s in local)
        ref.attrs["text"] = text[ref.start:ref.end].strip()
        ref.attrs["context"] = ref.attrs["text"]
        new.append(ref)
    return new


_NUMISH = {Entity.NUM_YEAR, Entity.CASE_NUMBER}
_NUM_FAMILY = {Entity.NUM_YEAR, Entity.CASE_NUMBER, Entity.NUMBER, Entity.YEAR, Entity.DATE}
_SUBPART = {Entity.COMMA, Entity.LETTER, Entity.PARAGRAPH, Entity.NUMERO,
            Entity.PUNTO, Entity.PERIODO}


def _partition_number_children(other: List[Span], leaves: List[List[Span]]) -> List[Reference]:
    """Split a frame without multiplying every partition by every act number.

    A non-case-law frame containing several number/year identities and several partition
    branches is structurally ambiguous. Keep only the number local to the frame's own anchor
    and the partition branches local to that number. A genuine number series with no partition
    branching continues through the ordinary splitter.
    """
    nums = [s for s in other if s.entity == Entity.NUM_YEAR]
    is_caselaw = any(s.entity == Entity.DOCTYPE and s.value in CASELAW_DOCTYPE for s in other) \
        or any(s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH for s in other)
    if is_caselaw or len(nums) <= 1 or len(leaves) <= 1:
        return [child for leaf in leaves
                for child in _split_multinumber(Reference(spans=other + leaf))]

    anchors = [s for s in other if s.entity in ANCHOR_ENTITIES]
    if not anchors:
        return []
    anchor = anchors[0]
    primary = min(nums, key=lambda number: _gap(anchor, number))
    shared = [s for s in other if s.entity not in _NUM_FAMILY]
    children = []
    for leaf in leaves:
        leaf_start = min(part.start for part in leaf)
        leaf_end = max(part.end for part in leaf)
        following = [number for number in nums
                     if leaf_end <= number.start and number.start - leaf_end <= 30]
        nearest = (min(following, key=lambda number: number.start - leaf_end) if following
                   else min(nums, key=lambda number: min(_gap(number, part) for part in leaf)))
        if nearest is primary:
            children.append(Reference(spans=list(shared) + [primary] + leaf))
    return children


def _split_multinumber(ref: Reference) -> List[Reference]:
    """One authority/doctype governing a list of numbers ("Cass. 10266/2018, 30927/2018")
    -> one reference per number, keeping the shared identity/partition spans."""
    nums = [s for s in ref.spans if s.entity in _NUMISH]
    if len(nums) <= 1:
        # a list of *bare* numbers sharing a single date ("nn. 26636 e 26637 del 18.12.2009"):
        # split per number but keep the date/year shared across the siblings.
        plain = [s for s in ref.spans if s.entity == Entity.NUMBER]
        if len(plain) > 1:
            dates = [s for s in ref.spans if s.entity == Entity.DATE]
            if dates:
                shared = [s for s in ref.spans
                          if s.entity not in (Entity.NUMBER, Entity.DATE, Entity.YEAR)]
                out = []
                for n in plain:
                    pre = [d for d in dates if d.end <= n.start]
                    chosen = max(pre, key=lambda d: d.end) if pre else min(dates, key=lambda d: _gap(d, n))
                    out.append(Reference(spans=list(shared) + [chosen, n]))
                return out
            shared = [s for s in ref.spans if s.entity != Entity.NUMBER]
            return [Reference(spans=list(shared) + [n]) for n in plain]
        return [ref]
    shared = [s for s in ref.spans if s.entity not in _NUM_FAMILY]
    dates = [s for s in ref.spans if s.entity == Entity.DATE]
    out = []
    for n in nums:
        mine = list(shared) + [n]
        if not n.attrs.get("year") and dates:
            following = [d for d in dates if n.end <= d.start and d.start - n.end <= 45]
            nearby = following or [d for d in dates if abs(d.start - n.end) <= 45]
            if nearby:
                mine.append(min(nearby, key=lambda d: abs(d.start - n.end)))
        out.append(Reference(spans=mine))
    return out


def _valid(r: Reference) -> bool:
    # a CGUE case id ("C-123/20") is self-identifying case-law on its own.
    if any(s.entity == Entity.CASE_NUMBER for s in r.spans):
        return True
    has_doctype = any(s.entity == Entity.DOCTYPE for s in r.spans)
    has_alias = any(s.entity == Entity.ALIAS for s in r.spans)
    # a self-reference ("questa Corte") is not a *concrete* authority for the number rule:
    # the deciding court's own pronouncement must not become a citation by date alone.
    has_concrete_auth = any(s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH
                            and s.value != "THIS_COURT" for s in r.spans)
    has_this_court = any(s.entity == Entity.AUTHORITY and s.value == "THIS_COURT"
                         for s in r.spans)
    has_identity = has_doctype or has_alias or has_concrete_auth or has_this_court
    has_real_number = any(s.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.CASE_NUMBER)
                          for s in r.spans)
    has_date = any(s.entity == Entity.DATE for s in r.spans)
    has_partition = any(s.entity in PARTITION_ENTITIES for s in r.spans)

    # a self-sufficient named act ("tariffa doganale comune") is a reference on its own
    if any(s.entity == Entity.ALIAS and s.value in SELF_VALID_ALIASES for s in r.spans):
        return True

    # an alias with a partition (e.g. "codice civile, art. 2697") is a valid reference
    if has_alias and has_partition:
        return True

    # a bare "sentenza" or a self-reference with no concrete authority/alias and no real
    # number is almost always the deciding court's OWN pronouncement ("questa Corte ... ha
    # pronunciato la seguente sentenza" + the document's date), not a citation.
    sent_or_self = (any(s.entity == Entity.DOCTYPE and s.value == "SENT" for s in r.spans)
                    or has_this_court)
    if sent_or_self and not has_concrete_auth and not has_alias and not has_real_number:
        return False

    return has_identity and (has_real_number or has_date)
