"""
LinkEngine: run the recognizers, assemble references into feature rows, and build each
row's canonical identifier.

Two phases: phase 1 (`_fill_fields`) fills the recognition fields from the spans; phase 2
(`urn.build_urn`) builds the canonical `urn` directly from those fields — URN-NIR for
national/regional legislation, CELEX for EU acts, ECLI for case law, PRAX for
administrative practice.
"""
from __future__ import annotations

from typing import Dict, List

from . import normalize as NZ
from .aliases import ALIAS_CELEX, alias_nir
from .geo import region_urn as _region_urn
from .assembler import CASELAW_AUTH, PARTITION_ENTITIES, assemble
from .model import (Entity, ExtractResult, PARTITION_LABEL, PARTITION_RANK, Reference,
                    Span, empty_row)
from . import recognizers as RZ
from .recognizers import RECOGNIZERS


import re as _re2
from .aliases import ALIAS_NIR
from .normalize import norm_latin_suffix as _nls
from .urn import build_urn, compat_url

_BARE_CODE_NUM = _re2.compile(
    r"(?<![\w./])(\d{1,4}(?:[-\s]?(?:bis|ter|quater|quinquies|sexies))?)"
    r"\s*,?\s*(?:del(?:l[ao'’])?(?:la|le|lo|li|gli|i)?\s+)?$", _re2.I)
_CODE_PART = {Entity.ARTICLE, Entity.COMMA, Entity.LETTER, Entity.NUMERO, Entity.PARAGRAPH}

# doc-types that make a reference *prassi* (administrative practice) rather than legislation:
# Agenzia Entrate circolari / risoluzioni / interpelli, ministerial provvedimenti, pareri, ...
PRASSI_DOCTYPES = {"CIRC", "RIS", "INTERPELLO", "PROVV", "PARERE", "NOTA", "DET"}


def _bare_code_articles(text, spans):
    """A bare number right before an act is its cited article. Two cases:

    * before a **code alias** ("342 c.p.c." / "1600, c.c." -> articolo 342 / 1600); the alias
      carries its own urn:nir base, so any 1-4 digit leading number is the article.
    * before a **doctype that has its own number** (the Cassazione style "7 L. ... n. 1034" /
      "48 legge 833" -> article 7 / 48); here the leading number is capped at 3 digits so a
      4-digit year ("2018 L. 205") is not mistaken for an article.

    Only when no explicit partition is adjacent to the act and the number is not already a
    recognized number or introduced by art/comma/n."""
    nums_all = [s for s in spans if s.entity in (Entity.NUMBER, Entity.NUM_YEAR)]
    acts = [(a, 4) for a in spans if a.entity == Entity.ALIAS and a.value in ALIAS_NIR]
    for d in [s for s in spans if s.entity == Entity.DOCTYPE]:
        if any(0 <= n.start - d.end <= 30 for n in nums_all):     # the act has a number of its own
            acts.append((d, 3))
    parts = [s for s in spans if s.entity in _CODE_PART]
    nums = [s for s in spans if s.entity in (Entity.NUMBER, Entity.NUM_YEAR, Entity.YEAR)]
    new = []
    for a, maxdig in acts:
        if any(0 <= a.start - s.end <= 8 or 0 <= s.start - a.end <= 8 for s in parts):
            continue
        win0 = max(0, a.start - 16)        # room for an optional "del/della" before the act
        m = _BARE_CODE_NUM.search(text[win0:a.start])
        if not m or len(_re2.match(r"\d+", m.group(1)).group()) > maxdig:
            continue
        start, end = win0 + m.start(1), win0 + m.end(1)
        if any(not (end <= ns.start or start >= ns.end) for ns in nums):
            continue
        if _re2.search(r"(?:artt?|comma|commi|co|c|lett|nn?|num|numero)\.?\s*$",
                       text[max(0, start - 7):start], _re2.I):
            continue
        new.append(Span(start, end, Entity.ARTICLE, _nls(m.group(1)), text[start:end]))
    return new


def _resolve_overlaps(spans):
    """Cross-recognizer overlap resolution:
    * an ALIAS subsumes a DOCTYPE it textually contains ("legge fallimentare" is the
      LEGGE_FALL alias, not the L doctype + 'legge');
    * a court AUTHORITY subsumes an overlapping ALIAS ("Corte cost." is the CORTE_COST
      authority, not the COST/Costituzione alias 'cost.').
    """
    aliases = [s for s in spans if s.entity == Entity.ALIAS]
    auths = [s for s in spans if s.entity == Entity.AUTHORITY]
    # a budget law ("legge finanziaria 2008") subsumes the plain "legge" doctype and the bare
    # year that otherwise match inside it.
    budget = [s for s in spans if s.attrs.get("budget")]
    # a regional-law doctype ("l. reg.") subsumes the plain REG doctype that the trailing
    # "reg." otherwise matches.
    regional = [s for s in spans if s.entity == Entity.DOCTYPE
                and s.attrs.get("scope") == "regionale"]
    out = []
    for s in spans:
        if s.entity == Entity.DOCTYPE and any(a.start <= s.start and s.end <= a.end
                                              for a in aliases):
            continue
        if s.entity == Entity.ALIAS and any(not (s.end <= au.start or s.start >= au.end)
                                            for au in auths):
            continue
        if (s.entity == Entity.DOCTYPE and s.attrs.get("scope") != "regionale"
                and any(not (s.end <= r.start or s.start >= r.end) for r in regional)):
            continue
        if (not s.attrs.get("budget")
                and s.entity in (Entity.DOCTYPE, Entity.YEAR, Entity.NUMBER, Entity.NUM_YEAR)
                and any(b.start <= s.start and s.end <= b.end for b in budget)):
            continue
        out.append(s)
    return out


class LinkEngine:
    """Pure-Python citation engine. Stateless; safe to reuse across calls."""

    name = "linkengine"

    def __init__(self, default_authority: str = "", default_region: str = "",
                 default_regolamento_scope: str = "nazionale"):
        # authority assigned to self-references ("questa Corte") — the deciding court of the
        # document being processed (e.g. "CORTE_CASS"). Empty -> self-references stay
        # unresolved (no ECLI), as before.
        self.default_authority = default_authority or ""
        # region assigned to a regional law cited without a region name ("l. reg. n. 4/2007").
        # Accepts a region name ("Campania") or its urn segment ("campania").
        self.default_region = default_region or ""
        # how to read a bare "regolamento N/YYYY" with no EU acronym: "nazionale" (default,
        # -> urn:nir:stato:regolamento) or "comunitario" (-> CELEX, for corpora
        # where regolamenti are predominantly EU).
        self.default_regolamento_scope = default_regolamento_scope or "nazionale"

    def extract(self, text: str, *, debug: bool = False, default_authority: str = None,
                default_region: str = None, default_regolamento_scope: str = None) -> ExtractResult:
        if text is None:
            text = ""
        default_authority = self.default_authority if default_authority is None else default_authority
        default_region = self.default_region if default_region is None else default_region
        reg_scope = self.default_regolamento_scope if default_regolamento_scope is None else default_regolamento_scope
        trace = []
        spans: List[Span] = []
        for mod_name, fn in RECOGNIZERS:
            new = fn(text)
            spans.extend(new)
            if debug:
                trace.append((mod_name, new))

        spans += _bare_code_articles(text, spans)
        spans = _resolve_overlaps(spans)
        refs = assemble(spans, text)
        # two-step pipeline: phase 1 fills the recognition fields; phase 2 builds the canonical
        # ``urn`` directly from them (no url roundtrip) and derives the legacy url /
        # cited-doc-simple-id columns from it. A reference can be fully recognized even when no
        # identifier is built.
        rows = [self._fill_fields(r, default_authority, default_region, reg_scope)
                for r in refs]
        for row in rows:
            row["urn"] = build_urn(row)
            row["url"] = compat_url(row["urn"])
        return ExtractResult(rows=rows, references=refs, spans=spans, trace=trace)

    # ------------------------------------------------------------------
    def _fill_fields(self, ref: Reference, default_authority: str = "",
                     default_region: str = "", reg_scope: str = "nazionale") -> Dict[str, str]:
        """Phase 1: fill the recognition fields (ref-type, ref-scope, authority, region,
        city, section, doc-type, alias, number, year, doc-date, case-number, partition, ...)
        from the recognized spans. Builds no identifier — that is phase 2 (_build_identifier)."""
        row = empty_row()
        row["text"] = ref.attrs.get("text", "")
        row["context"] = ref.attrs.get("context", "") or row["text"]

        doctype = ref.of(Entity.DOCTYPE)
        alias = ref.of(Entity.ALIAS)
        authority = ref.of(Entity.AUTHORITY)
        other_auth = ref.of(Entity.OTHER_AUTH)
        ministry = ref.of(Entity.MINISTRY)
        eu_acr = ref.of(Entity.EU_ACRONYM)
        case_num = ref.of(Entity.CASE_NUMBER)

        # number / year
        number = year = ""
        num_year = ref.of(Entity.NUM_YEAR)
        if num_year:
            number = num_year.attrs.get("number", "")
            year = num_year.attrs.get("year", "")
            if num_year.attrs.get("full"):
                row["full-number"] = num_year.attrs["full"]
            if not year:           # e.g. AdE "n. 36/E del 2016": year is in a separate span
                y = ref.of(Entity.YEAR)
                if y:
                    year = y.attrs.get("year", y.value)
        else:
            n = ref.of(Entity.NUMBER)
            if n:
                number = n.attrs.get("number", n.value)
            y = ref.of(Entity.YEAR)
            if y:
                year = y.attrs.get("year", y.value)
        date = ref.of(Entity.DATE)
        if not year and date:
            year = date.attrs.get("year", "")

        # doc-type + authority (DPR carries authority=PRES_REP on the doctype span)
        if doctype:
            row["doc-type"] = doctype.value
            if doctype.attrs.get("authority"):
                row["authority"] = doctype.attrs["authority"]
        if authority:
            # a self-reference ("questa Corte") resolves to the document's authority
            value = default_authority if authority.value == "THIS_COURT" else authority.value
            if value:
                row["authority"] = value
            if authority.attrs.get("region"):
                row["region"] = authority.attrs["region"]
            if authority.attrs.get("city"):
                row["city"] = authority.attrs["city"]
            if authority.attrs.get("section"):
                row["section"] = authority.attrs["section"]
        if alias:
            row["alias"] = alias.value
        if other_auth:
            row["other-authority"] = other_auth.value
        # Agenzia Entrate prassi: an "NNN/E" number (or an explicit AdE mention) with a
        # prassi doc-type implies other-authority=AG_ENTRATE, which the prassi
        # URN path needs to build PRAX:AE:...
        if row["doc-type"] in ("CIRC", "RIS", "INTERPELLO") and not row["other-authority"]:
            # an interpello (risposta a/ad interpello) is always Agenzia delle Entrate; a
            # circolare/risoluzione only when it carries the "NNN/E" form.
            if row["doc-type"] == "INTERPELLO" or (num_year and num_year.attrs.get("ade")):
                row["other-authority"] = "AG_ENTRATE"
        if ministry:
            row["ministry"] = ministry.value
        if eu_acr:
            row["eu-acronym"] = eu_acr.value
        row["number"] = number
        row["year"] = year
        if date:
            row["doc-date"] = date.value
        if case_num:
            row["case-number"] = case_num.value
            # a CGUE case id is self-identifying: imply the authority (the CELEX is built
            # from this normalized case-number in the identifier phase, _build_identifier).
            if not row["authority"]:
                row["authority"] = "CGUE"

        # partition (ordered by rank: allegato > articolo > comma > paragrafo > lettera > numero).
        # Kept faithful to the text here (e.g. "punto-12"); the URN layer normalizes a CGUE
        # punto/paragrafo/numero to the ~num locator.
        parts = [s for s in ref.spans if s.entity in PARTITION_ENTITIES]
        parts.sort(key=lambda s: -PARTITION_RANK.get(s.entity, 0))
        if parts:
            row["partition"] = "_".join(
                f"{PARTITION_LABEL[s.entity]}-{s.value}" for s in parts)

        # classification
        is_caselaw = (row["authority"] in CASELAW_AUTH) or row["doc-type"] == "SENT" or \
            bool(case_num)
        # a "direttiva" is inherently an EU act (CELEX) even without an explicit acronym;
        # REG/DECIS/RACC can also be national, so they need the EU acronym to confirm.
        is_eu = row["doc-type"] == "DIR" or row["authority"] == "CGUE" or \
            (bool(eu_acr) and row["doc-type"] in NZ.EU_PROV_LETTER)
        # a bare "regolamento N/YYYY" (no acronym, not nationally qualified) follows the
        # configured default scope; "regolamento ministeriale/comunale/..." stays national.
        if row["doc-type"] == "REG" and not eu_acr and reg_scope == "comunitario" and \
                (doctype is None or doctype.attrs.get("scope") != "nazionale"):
            is_eu = True
        is_regional = bool(doctype) and doctype.attrs.get("scope") == "regionale"
        if is_caselaw:
            row["ref-type"] = "caselaw"
            row["ref-scope"] = "comunitario" if row["authority"] == "CGUE" else "nazionale"
        elif row["doc-type"] in PRASSI_DOCTYPES:
            # prassi (Agenzia Entrate circolari / risoluzioni / interpelli, ...) is a first-class
            # ref-type here (administrative practice; its identifier scheme is PRAX).
            row["ref-type"] = "prassi"
            row["ref-scope"] = "nazionale"
        elif row["doc-type"] or row["alias"] or row["other-authority"] or row["ministry"]:
            row["ref-type"] = "legislation"
            if is_regional:
                row["ref-scope"] = "regionale"
            elif is_eu or row["alias"] in RZ.EU_ALIASES:
                row["ref-scope"] = "comunitario"
            elif row["alias"] in RZ.INTL_ALIASES:
                row["ref-scope"] = "internazionale"
            else:
                row["ref-scope"] = "nazionale"

        # region is a recognition field: a regional law's region comes from the citation,
        # else the document's default region. Resolve it here (phase 1) so the identifier
        # phase needs only the row, never the spans.
        if is_regional:
            ru = (doctype.attrs.get("region_urn") if doctype else "") or \
                _region_urn(default_region) or ""
            if ru:
                row["region"] = ru

        # case-law docket numbers are never zero-padded ("Cass. n. 08508/2019" -> 8508).
        if row["ref-type"] == "caselaw" and row["number"]:
            row["number"] = row["number"].lstrip("0") or row["number"]
        return row

    # phase 2 (urn building + legacy url / cited-doc-simple-id derivation) lives in urn.py
    # (build_urn / compat_fields), called from extract().
