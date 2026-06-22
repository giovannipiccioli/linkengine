"""
Assembler: group recognized spans into Reference candidates.

Strategy (proximity-based):

* **Anchors** are act-identity spans: DOCTYPE and ALIAS.
* Every other span (partition / number / year / date / case-number / authority /
  eu-acronym ...) is attached to its **nearest anchor** within a max char gap.
* An AUTHORITY with a nearby number but no doctype/alias anchor claiming it becomes its own
  case-law anchor (e.g. "Cass. n. 123/2020").
* A Reference is kept only if it has an act identity (doctype/alias/authority) AND a
  number/date/case-number — the validity rule.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from .aliases import ALIAS_NIR, SELF_VALID_ALIASES
from .catalog import CASELAW_AUTH
from .model import Entity, Reference, Span
from .partitions import segment

# In Italian legal prose a partition attaches to the act on its *right*: "art. 14, comma 3,
# del d.lgs. 546" and "art. 360, comma 1, n. 3, c.p.c." both name a partition OF the act that
# follows — even when another act sits closer on the left. The act follows either through a
# genitive connector (del/della/dell'/dei/.../al/all'/...) or by bare adjacency (the code
# alias right after the run). The residue between the partition run and the right anchor, with
# the intervening partition mentions blanked out, must match one of these (and never cross a
# sentence boundary — no period, no stray words).
_RIGHT_ACT = re.compile(
    r"^[\s,;()]*(?:del(?:l[ao'’])?(?:la|le|lo|li|gli|i)?|dei|d['’]|"
    r"all['’]|all[ao]|agli|ai|alle|nel(?:l[ao'’])?)\s*$"   # ... del / della / dell' / ...
    r"|^[\s,;]*$", re.I)                                   # bare adjacency: only punctuation

ANCHOR_ENTITIES = {Entity.DOCTYPE, Entity.ALIAS}
NUMERIC_ENTITIES = {Entity.NUMBER, Entity.NUM_YEAR, Entity.YEAR, Entity.DATE,
                    Entity.CASE_NUMBER}
PARTITION_ENTITIES = {Entity.ALLEGATO, Entity.ARTICLE, Entity.COMMA, Entity.PARAGRAPH,
                      Entity.LETTER, Entity.NUMERO, Entity.PUNTO, Entity.PERIODO}
# CASELAW_AUTH is imported from catalog (the knowledge base) — the single source of truth.
# doctype anchors a court AUTHORITY may bind to. A court qualifies a *pronouncement*
# (sentenza/ordinanza), never a piece of legislation: "...c.p.c. Questa Corte, sentenza
# n. 4091" — "Questa Corte" belongs to the sentenza, not to the nearer c.p.c. alias.
CASELAW_DOCTYPE = {"SENT", "ORD"}

MAX_GAP = 70          # max char gap between a floating span and its anchor
AUTH_NUM_GAP = 35     # max gap for an orphan authority to claim a number


def _gap(a: Span, b: Span) -> int:
    return max(0, a.start - b.end, b.start - a.end)


def _semicolon_between(text: str, a: Span, b: Span) -> bool:
    """True if a ';' separates the two spans. A semicolon is a citation-list boundary, so an
    act number must not bind to an anchor on the other side of one ("Circolare ... n. 47/2005;
    direttiva 2006/112" — 47/2005 is the circolare's, not the directive's)."""
    lo, hi = (a.end, b.start) if a.end <= b.start else (b.end, a.start)
    return ";" in text[lo:hi]


def _right_act_anchor(p: Span, anchors: List[Span], part_spans: List[Span],
                      text: str) -> Optional[Span]:
    """Return the act on ``p``'s right that it modifies (via a genitive or by bare adjacency),
    or None. Scans to the nearest right anchor and checks the gap text — with intervening
    partition mentions ("comma 3", "n. 3", "lett. a") blanked out — against ``_RIGHT_ACT``.
    Overrides nearest-distance so the whole run "art. 360, comma 1, n. 3, c.p.c." binds to the
    c.p.c. on its right, not the closer left-hand act."""
    rights = [a for a in anchors if a.start >= p.end]
    if not rights:
        return None
    a = min(rights, key=lambda x: x.start)
    between = text[p.end:a.start]
    for q in part_spans:                       # blank intervening "comma 3", "lett. a", ...
        if q is p or q.start < p.end or q.end > a.start:
            continue
        s0, s1 = q.start - p.end, q.end - p.end
        between = between[:s0] + " " * (s1 - s0) + between[s1:]
    return a if _RIGHT_ACT.match(between) else None


def assemble(spans: List[Span], text: str) -> List[Reference]:
    spans = sorted(spans, key=lambda s: s.start)
    anchors = [s for s in spans if s.entity in ANCHOR_ENTITIES]
    floating = [s for s in spans if s.entity not in ANCHOR_ENTITIES]

    refs: List[Reference] = []
    anchor_ref = {}
    for a in anchors:
        r = Reference(spans=[a], start=a.start, end=a.end)
        anchor_ref[id(a)] = r
        refs.append(r)

    caselaw_anchors = [a for a in anchors if a.entity == Entity.DOCTYPE
                       and a.value in CASELAW_DOCTYPE]
    cl_auths = [s for s in floating if s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH]

    case_nums = [s for s in floating if s.entity == Entity.CASE_NUMBER]
    part_spans = [s for s in floating if s.entity in PARTITION_ENTITIES]

    used = set()
    bound_to = {}     # id(floating span) -> the Reference it was attached to
    # attach floating spans to nearest anchor within MAX_GAP. A court AUTHORITY is
    # restricted to case-law anchors (sentenza/ordinanza): it must never latch onto a
    # nearer legislation alias/doctype and turn it into caselaw.
    for s in floating:
        # a partition tied to a right-hand act ("art. 14, comma 3, del d.lgs. 546" via a
        # genitive; "art. 360, comma 1, n. 3, c.p.c." by bare adjacency) binds there,
        # overriding nearest-distance (which would otherwise mis-bind it left).
        if s.entity in PARTITION_ENTITIES:
            gt = _right_act_anchor(s, anchors, part_spans, text)
            if gt is not None:
                anchor_ref[id(gt)].spans.append(s)
                used.add(id(s))
                continue
        # a *case-law* AUTHORITY or a CGUE CASE_NUMBER must bind only to a case-law anchor
        # (sentenza/ordinanza), never to a nearer legislation anchor (e.g. a directive). A
        # non-case-law authority like COMUNE (a delibera comunale) binds to any anchor.
        cands = caselaw_anchors if s.entity == Entity.CASE_NUMBER or (
            s.entity == Entity.AUTHORITY and s.value in CASELAW_AUTH) else anchors
        best, best_gap = None, MAX_GAP + 1
        for a in cands:
            # an act number never binds across a ';' (a citation-list boundary)
            if s.entity in (Entity.NUMBER, Entity.NUM_YEAR) and _semicolon_between(text, s, a):
                continue
            g = _gap(s, a)
            if g < best_gap:
                best, best_gap = a, g
        # a punto/paragrafo closer to a CGUE case number than to its legislation anchor is that
        # case's point ("causa C-152/02, punti 35 e 36"), not the nearby directive's; leave it
        # loose so the case-number catch-all below claims it.
        if best is not None and s.entity in (Entity.PUNTO, Entity.PARAGRAPH) \
                and any(_gap(s, c) < best_gap for c in case_nums):
            continue
        # a number sitting closer to a case-law authority ("...(Cass. ..., n. 16189/2023)")
        # is that court's docket number, not a number for this distant act anchor.
        if best is not None and s.entity in (Entity.NUMBER, Entity.NUM_YEAR) and \
                any(_gap(s, au) < best_gap for au in cl_auths):
            continue
        if best is not None:
            anchor_ref[id(best)].spans.append(s)
            bound_to[id(s)] = anchor_ref[id(best)]
            used.add(id(s))

    # a number/date left loose because it hugged a case-law authority that is *itself*
    # already bound to a sentenza/ordinanza anchor joins that same pronouncement:
    # "sentenza della Corte Costituzionale n. 348/2007" — the authority sits on the SENT
    # anchor, so the docket number must land there too (else the ref has no number and dies).
    bound_cl_auths = [au for au in cl_auths if id(au) in bound_to]
    for s in floating:
        if id(s) in used or s.entity not in (Entity.NUMBER, Entity.NUM_YEAR, Entity.DATE):
            continue
        near = [au for au in bound_cl_auths if _gap(s, au) <= AUTH_NUM_GAP]
        if not near:
            continue
        au = min(near, key=lambda a: _gap(s, a))
        bound_to[id(au)].spans.append(s)
        used.add(id(s))

    # orphan authority + number -> case-law reference. A single authority may govern a
    # *list* of numbers ("Cass. 10266/2018, 30927/2018"): collect every nearby number for
    # which this authority is the closest anchor; the multi-number split below turns them
    # into one reference each.
    free_auths = [s for s in floating if s.entity == Entity.AUTHORITY
                  and s.value in CASELAW_AUTH and id(s) not in used]
    numbers = [s for s in floating if s.entity in (Entity.NUMBER, Entity.NUM_YEAR,
                                                   Entity.CASE_NUMBER)]
    # a standalone YEAR is treated like a date here so the "court YEAR, n. NUM" form
    # ("Cassazione 1998, n. 4775") supplies the ECLI year (a year alone never makes a ref).
    dates = [s for s in floating if s.entity in (Entity.DATE, Entity.YEAR)]

    def _owner(span):
        """The case-law authority a number/date belongs to: the nearest *preceding* one
        within range ("Cass. <date>, n. <num>" — each follows its court), so a series
        ("Cass. ... n. 2920; Cass. ... n. 5157") pairs each citation correctly."""
        cands = [au for au in free_auths if _gap(au, span) <= AUTH_NUM_GAP
                 and not (anchors and min(_gap(span, a) for a in anchors) < _gap(au, span))]
        if not cands:
            return None
        pre = [au for au in cands if au.end <= span.start]
        return (min(pre, key=lambda a: span.start - a.end) if pre
                else min(cands, key=lambda a: _gap(a, span)))

    groups = {id(au): [au] for au in free_auths}
    owned = set()
    for s in numbers + dates:
        o = _owner(s)
        if o is not None:
            groups[id(o)].append(s)
            owned.add(id(s))
    # bridge through the date: a docket number trailing a date already owned by a court
    # ("Cass. ..., 14 gennaio 2015, n. 428") belongs to that court even when too far from the
    # court keyword itself for _owner. Bind it to the nearest preceding owned date.
    for s in numbers:
        if id(s) in owned:
            continue
        best, best_gap = None, 26
        for au in free_auths:
            for d in groups[id(au)]:
                if d.entity == Entity.DATE and d.end <= s.start and (s.start - d.end) < best_gap \
                        and not (anchors and min(_gap(s, a) for a in anchors) < (s.start - d.end)):
                    best, best_gap = au, s.start - d.end
        if best is not None:
            groups[id(best)].append(s)
            owned.add(id(s))
    for au in free_auths:
        g = groups[id(au)]
        if any(s.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.CASE_NUMBER) for s in g):
            refs.append(Reference(spans=g, start=au.start, end=au.end))

    # a CGUE case number ("C-123/20") is self-identifying case-law: if nothing claimed it,
    # seed a reference — its number/year alone build the CELEX (e.g. C-123/20 -> 62020CJ0123).
    claimed = {id(s) for r in refs for s in r.spans}
    for s in floating:
        if s.entity == Entity.CASE_NUMBER and id(s) not in claimed:
            refs.append(Reference(spans=[s]))

    # a partition still unattached (e.g. "punti 20-25" after a bare CGUE case number, or
    # "paragrafi 11 e 12" after a plain-number CGUE ref) joins the nearest CGUE reference
    # within range. Restricted to CGUE refs: a punto/paragrafo is meaningful there (it feeds
    # the CELEX locator or simply segments the citation); for an ECLI court attaching one would
    # only split the citation into duplicate ECLIs.
    caselaw_refs = [r for r in refs
                    if any(s.entity == Entity.CASE_NUMBER for s in r.spans)
                    or any(s.entity == Entity.AUTHORITY and s.value == "CGUE"
                           for s in r.spans)]
    claimed = {id(s) for r in refs for s in r.spans}
    for p in [s for s in floating if s.entity in PARTITION_ENTITIES and id(s) not in claimed]:
        best, bg = None, MAX_GAP + 1
        for r in caselaw_refs:
            g = _gap(p, Span(min(x.start for x in r.spans), max(x.end for x in r.spans),
                             Entity.DOCTYPE, "", ""))
            if g < bg:
                best, bg = r, g
        if best is not None:
            best.spans.append(p)

    # finalize: segment the partition into leaf paths (one citation each), split act-number
    # lists, validate, set text/context.
    out: List[Reference] = []
    for r in refs:
        part = [s for s in r.spans if s.entity in PARTITION_ENTITIES]
        other = [s for s in r.spans if s.entity not in PARTITION_ENTITIES]
        leaves = segment(part, text) if part else [[]]
        children = [r2 for leaf in leaves
                    for r2 in _split_multinumber(Reference(spans=other + leaf)) if _valid(r2)]
        _assign_text_context(children, text)
        out.extend(children)

    out += _propagate_acts(out, spans, text)
    return out


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
        t = text[tstart:tend].strip(" ,;")
        for suf in (" e", " ed"):              # drop a trailing conjunction ("15 e" -> "15")
            if t.endswith(suf):
                t = t[:-len(suf)].rstrip(" ,;")
        c.attrs["text"] = t


# Spans that define an act's *identity* (everything except the cited partition); these are
# "borrowed" when an orphan article inherits a nearby act.
_ACT_IDENTITY = {Entity.DOCTYPE, Entity.ALIAS, Entity.AUTHORITY, Entity.OTHER_AUTH,
                 Entity.MINISTRY, Entity.NUM_YEAR, Entity.NUMBER, Entity.YEAR, Entity.DATE,
                 Entity.EU_ACRONYM, Entity.CASE_NUMBER}
MAX_PROP_DIST = 150          # chars: how far back a bare article may inherit a code/TU alias
MAX_PROP_DIST_ACT = 100      # tighter window for a doctype+number act (number must not stray)


def _propagate_acts(refs: List[Reference], spans: List[Span], text: str) -> List[Reference]:
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
        if s.entity == Entity.ALIAS and s.value in ALIAS_NIR:
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
            acts.append((r.start, ident, MAX_PROP_DIST_ACT))
    if not acts:
        return []

    used = {(s.start, s.end) for r in refs for s in r.spans if s.entity == Entity.ARTICLE}
    orphans = [s for s in spans
               if s.entity == Entity.ARTICLE and (s.start, s.end) not in used]
    subs = [s for s in spans if s.entity in _SUBPART]

    new: List[Reference] = []
    for art in orphans:
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
_SUBPART = {Entity.COMMA, Entity.LETTER, Entity.PARAGRAPH, Entity.NUMERO}


def _split_multinumber(ref: Reference) -> List[Reference]:
    """One authority/doctype governing a list of numbers ("Cass. 10266/2018, 30927/2018")
    -> one reference per number, keeping the shared identity/partition spans."""
    nums = [s for s in ref.spans if s.entity in _NUMISH]
    if len(nums) <= 1:
        # a list of *bare* numbers sharing a single date ("nn. 26636 e 26637 del 18.12.2009"):
        # split per number but keep the date/year shared across the siblings.
        plain = [s for s in ref.spans if s.entity == Entity.NUMBER]
        if len(plain) > 1:
            shared = [s for s in ref.spans if s.entity != Entity.NUMBER]
            return [Reference(spans=list(shared) + [n]) for n in plain]
        return [ref]
    shared = [s for s in ref.spans if s.entity not in _NUM_FAMILY]
    return [Reference(spans=list(shared) + [n]) for n in nums]


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
