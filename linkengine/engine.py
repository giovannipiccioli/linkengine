"""
LinkEngine: run the recognizers, assemble references into feature rows, and build each
row's canonical identifier.

Two phases: phase 1 (`_fill_fields`) fills the recognition fields from the spans; phase 2
(`urn.build_urn`) builds the canonical `urn` directly from those fields — URN-NIR for
national/regional legislation, CELEX for EU acts, ECLI for case law, PRAX for
administrative practice.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import normalize as NZ
from .aliases import ALIAS_CELEX, alias_nir
from .catalog import (AGENCY_DOCTYPES, CONDITIONAL_AGENCY_DOCTYPES, COURTS,
                      SECOND_GRADE_TAX_AUTHORITIES)
from .context import DocumentContext
from .geo import AUTONOMOUS_TAX_CITY_TO_GEO
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
    r"(?<![\w./])(\d{1,4}(?:[-\s\u00ad]?(?:bis|ter|quater|quinquies|sexies))?)"
    r"\s*,?\s*(?:del(?:l[ao'’])?(?:la|le|lo|li|gli|i)?\s+)?$", _re2.I)
_CODE_PART = {Entity.CONSIDERANDO, Entity.ARTICLE, Entity.COMMA, Entity.LETTER,
              Entity.NUMERO, Entity.PARAGRAPH, Entity.PERIODO, Entity.PUNTO}
_CODE_SUBPART = {Entity.COMMA, Entity.LETTER, Entity.NUMERO, Entity.PARAGRAPH,
                 Entity.PERIODO, Entity.PUNTO}

# doc-types that make a reference *prassi* (administrative practice) rather than legislation:
# Agenzia Entrate circolari / risoluzioni / interpelli, ministerial provvedimenti, pareri, ...
PRASSI_DOCTYPES = set(AGENCY_DOCTYPES)


def _has_minimal_output_evidence(row: Dict[str, str]) -> bool:
    """Whether a feature row is worth returning even when it has no canonical identifier.

    Resolved rows are always output. Unresolved rows must still look like a citation target,
    not just a loose number: they need an identity cue (doc-type, authority, alias, or case
    number) plus the minimum locator that makes later resolution plausible.
    """
    if row["urn"]:
        return True
    # An unattributed circular number is too ambiguous to identify an administrative issuer.
    # Distinctive /E and /DF forms are attributed before this filter.
    if row["doc-type"] == "CIRC" and not row["other-authority"]:
        return False
    has_number = bool(row["number"] or row["full-number"])
    has_date = bool(row["doc-date"])

    # Self-identifying EU/CEDU-style case ids and other explicit case numbers are useful
    # candidates even when the local normalizer cannot build a final identifier.
    if row["case-number"]:
        return True

    # Date-only ministerial / presidential decrees are common and may be canonicalized later
    # from external metadata; other date-only doctypes are usually document prose.
    if row["doc-type"] == "DECR" and (has_number or has_date):
        return True

    if row["doc-type"] and has_number:
        return True

    if (row["authority"] or row["other-authority"] or row["city"] or row["region"]) and has_number:
        return True

    if row["alias"] and (row["partition"] or has_number):
        return True

    return False


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
        win0 = max(0, a.start - 16)        # room for an optional "del/della" before the act
        direct = _BARE_CODE_NUM.search(text[win0:a.start])
        if direct and len(_re2.match(r"\d+", direct.group(1)).group()) <= maxdig:
            start, end = win0 + direct.start(1), win0 + direct.end(1)
            if not any(not (end <= ns.start or start >= ns.end) for ns in nums + parts) and \
                    not _re2.search(r"(?:artt?|comma|commi|co|c|lett|nn?|num|numero)\.?\s*$",
                                    text[max(0, start - 7):start], _re2.I) and \
                    not _re2.search(r"\bsez(?:ione|\.)?\.?[^.;]{0,10}$",
                                    text[max(0, start - 14):start], _re2.I):
                new.append(Span(start, end, Entity.ARTICLE, _nls(direct.group(1)), text[start:end]))
                continue
        # "1284, comma 4, c.c.": the comma sits between the bare article and the code alias,
        # so recover the article before applying the generic "partition already adjacent" guard.
        prev_subs = [s for s in parts if s.entity in _CODE_SUBPART
                     and s.end <= a.start and 0 <= a.start - s.end <= 18]
        if prev_subs:
            sub = max(prev_subs, key=lambda s: s.end)
            win0 = max(0, sub.start - 18)
            m = _BARE_CODE_NUM.search(text[win0:sub.start])
            if m and len(_re2.match(r"\d+", m.group(1)).group()) <= maxdig:
                start, end = win0 + m.start(1), win0 + m.end(1)
                if not any(not (end <= ns.start or start >= ns.end) for ns in nums + parts) and \
                        not _re2.search(r"(?:artt?|comma|commi|co|c|lett|nn?|num|numero)\.?\s*$",
                                        text[max(0, start - 7):start], _re2.I):
                    new.append(Span(start, end, Entity.ARTICLE, _nls(m.group(1)), text[start:end]))
                    continue
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
    # a partition NUMERO ("art. 36, comma 2, n. 4") only fires *inside* a partition chain, so a
    # document NUMBER the numbers-recognizer also matched on the same "n. 4" is spurious — the
    # partition wins (the "4" is a sub-item, never the act's number).
    numeri = [s for s in spans if s.entity == Entity.NUMERO]
    # a budget law ("legge finanziaria 2008") subsumes the plain "legge" doctype and the bare
    # year that otherwise match inside it.
    budget = [s for s in spans if s.attrs.get("budget")]
    explicit_num_year = [s for s in spans
                         if s.entity == Entity.NUM_YEAR and not s.attrs.get("budget")]
    duplicate_budget = {
        id(b) for b in budget
        if any(n.attrs.get("number") == b.attrs.get("number")
               and n.attrs.get("year") == b.attrs.get("year")
               and max(0, n.start - b.end, b.start - n.end) <= 40
               for n in explicit_num_year)
    }
    # a regional-law doctype ("l. reg.") subsumes the plain REG doctype that the trailing
    # "reg." otherwise matches.
    regional = [s for s in spans if s.entity == Entity.DOCTYPE
                and s.attrs.get("scope") == "regionale"]
    ocr_doctypes = [s for s in spans if s.entity == Entity.DOCTYPE and s.attrs.get("ocr")]
    out = []
    for s in spans:
        if id(s) in duplicate_budget:
            continue
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
        if s.entity in (Entity.NUMBER, Entity.NUM_YEAR) and \
                any(not (s.end <= n.start or s.start >= n.end) for n in numeri):
            continue
        if s.entity in _CODE_PART and any(not (s.end <= d.start or s.start >= d.end)
                                          for d in ocr_doctypes):
            continue
        out.append(s)
    return out


class LinkEngine:
    """Pure-Python citation engine. Stateless; safe to reuse across calls."""

    name = "linkengine"

    def __init__(self, default_authority: str = "", default_region: str = "",
                 default_regolamento_scope: str = "nazionale",
                 ocr_accommodations: bool = True, *,
                 default_context: Optional[DocumentContext] = None):
        # authority assigned to self-references ("questa Corte") — the deciding court of the
        # document being processed (e.g. "CORTE_CASS"). Empty -> self-references stay
        # unresolved (no ECLI), as before.
        if default_context is not None and not isinstance(default_context, DocumentContext):
            raise TypeError("default_context must be a DocumentContext")
        if default_context is None:
            self.default_context = DocumentContext(
                authority=default_authority,
                regional_law_region=default_region,
            )
        elif default_authority or default_region:
            self.default_context = DocumentContext(
                authority=default_authority or default_context.authority,
                city=default_context.city,
                region=default_context.region,
                regional_law_region=default_region or default_context.regional_law_region,
                document_year=default_context.document_year,
            )
        else:
            self.default_context = default_context
        # Retained as public compatibility attributes. New code should use default_context.
        self.default_authority = self.default_context.authority
        # region assigned to a regional law cited without a region name ("l. reg. n. 4/2007").
        # Accepts a region name ("Campania") or its urn segment ("campania").
        self.default_region = self.default_context.regional_law_region
        # how to read a bare "regolamento N/YYYY" with no EU acronym: "nazionale" (default,
        # -> urn:nir:stato:regolamento) or "comunitario" (-> CELEX, for corpora
        # where regolamenti are predominantly EU).
        self.default_regolamento_scope = default_regolamento_scope or "nazionale"
        # OCR accommodation keeps a few narrowly scoped scanned-text fixes active by default
        # (e.g. "I." for "l." in article contexts, "d. I." for "d.l."). Set false for strict
        # literal parsing.
        self.ocr_accommodations = bool(ocr_accommodations)

    def extract(self, text: str, *, debug: bool = False,
                context: Optional[DocumentContext] = None,
                default_authority: str = None, default_region: str = None,
                default_regolamento_scope: str = None,
                ocr_accommodations: bool = None) -> ExtractResult:
        if text is None:
            text = ""
        if context is not None and not isinstance(context, DocumentContext):
            raise TypeError("context must be a DocumentContext")
        doc_context = context or self.default_context
        if default_authority is not None or default_region is not None:
            doc_context = DocumentContext(
                authority=(doc_context.authority if default_authority is None
                           else default_authority),
                city=doc_context.city,
                region=doc_context.region,
                regional_law_region=(doc_context.regional_law_region if default_region is None
                                     else default_region),
                document_year=doc_context.document_year,
            )
        reg_scope = (self.default_regolamento_scope if default_regolamento_scope is None
                     else default_regolamento_scope)
        ocr_enabled = (self.ocr_accommodations if ocr_accommodations is None
                       else bool(ocr_accommodations))
        trace = []
        spans: List[Span] = []
        for mod_name, fn in RECOGNIZERS:
            new = (fn(text, ocr_accommodations=ocr_enabled)
                   if mod_name == "doctypes" else fn(text))
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
        rows = [self._fill_fields(r, doc_context, reg_scope)
                for r in refs]
        for row in rows:
            row["urn"] = build_urn(row)
            row["url"] = compat_url(row["urn"])
        # Keep unresolved rows only when they have a minimally useful citation skeleton. These
        # rows are intentionally returned as candidates for later, more contextual resolvers.
        keep = [i for i, row in enumerate(rows) if _has_minimal_output_evidence(row)]
        rows = [rows[i] for i in keep]
        refs = [refs[i] for i in keep]
        for citation_id, row in enumerate(rows, 1):
            row["id"] = str(citation_id)
        return ExtractResult(rows=rows, references=refs, spans=spans, trace=trace)

    # ------------------------------------------------------------------
    def _fill_fields(self, ref: Reference, context: Optional[DocumentContext] = None,
                     reg_scope: str = "nazionale") -> Dict[str, str]:
        """Phase 1: fill the recognition fields (ref-type, ref-scope, authority, region,
        city, section, doc-type, alias, number, year, doc-date, case-number, partition, ...)
        from the recognized spans. Builds no identifier — that is phase 2 (_build_identifier)."""
        context = context or DocumentContext()
        row = empty_row()
        row["text"] = ref.attrs.get("text", "")
        row["context"] = ref.attrs.get("context", "") or row["text"]

        doctype = ref.of(Entity.DOCTYPE)
        alias = ref.of(Entity.ALIAS)
        authority = ref.of(Entity.AUTHORITY)
        other_auths = ref.all_of(Entity.OTHER_AUTH)
        other_auth = None
        if other_auths:
            # A sentence can mention one institution before naming the issuer of the cited
            # document. Prefer the authority closest to its doctype ("INPS ... circolare
            # dell'Agenzia Entrate" -> AE), rather than whichever recognizer fired first.
            explicit_ae = next((s for s in other_auths if s.value == "AG_ENTRATE"), None)
            if doctype and doctype.value == "INTERPELLO" and explicit_ae:
                # The named Agenzia is the respondent; another nearby authority may merely
                # identify the applicant ("Fondo di Previdenza del MEF").
                other_auth = explicit_ae
            elif doctype:
                other_auth = min(
                    other_auths,
                    key=lambda s: max(0, s.start - doctype.end, doctype.start - s.end),
                )
            else:
                other_auth = other_auths[0]
        eu_acr = ref.of(Entity.EU_ACRONYM)
        case_num = ref.of(Entity.CASE_NUMBER)
        rv_num = ref.of(Entity.RV_NUMBER)

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
            if doctype.attrs.get("ministry"):
                row["ministry"] = doctype.attrs["ministry"]
        if authority:
            # a self-reference ("questa Corte") resolves to the document's authority
            is_self_reference = authority.value == "THIS_COURT"
            value = context.authority if is_self_reference else authority.value
            if value:
                row["authority"] = value
                if is_self_reference:
                    geo_kind = COURTS.get(value, {}).get("geo")
                    if value in SECOND_GRADE_TAX_AUTHORITIES and \
                            context.city in AUTONOMOUS_TAX_CITY_TO_GEO and \
                            context.region in ("", "TAA"):
                        row["region"] = AUTONOMOUS_TAX_CITY_TO_GEO[context.city]
                    elif geo_kind == "city" and context.city:
                        row["city"] = context.city
                    elif geo_kind == "region" and context.region:
                        row["region"] = context.region
            if authority.attrs.get("region"):
                row["region"] = authority.attrs["region"]
            if authority.attrs.get("city"):
                row["city"] = authority.attrs["city"]
            if authority.attrs.get("section"):
                row["section"] = authority.attrs["section"]
        if rv_num:
            row["rv-number"] = rv_num.value
            if not row["authority"]:
                row["authority"] = "CORTE_CASS"
        if alias:
            row["alias"] = alias.value
        if other_auth:
            row["other-authority"] = other_auth.value
        # A /DF circular number identifies the MEF Dipartimento delle Finanze.
        if row["doc-type"] == "CIRC" and num_year and num_year.attrs.get("df"):
            row["other-authority"] = "MEFDF"
        # Agenzia Entrate prassi: an "NNN/E" number (or an explicit AdE mention) with a
        # prassi doc-type implies other-authority=AG_ENTRATE, which the prassi
        # URN path needs to build PRAX:AE:...
        if row["doc-type"] in ("CIRC", "RIS", "INTERPELLO") and not row["other-authority"]:
            # an interpello (risposta a/ad interpello) is always Agenzia delle Entrate; a
            # circolare/risoluzione only when it carries the "NNN/E" form.
            if row["doc-type"] == "INTERPELLO" or (num_year and num_year.attrs.get("ade")):
                row["other-authority"] = "AG_ENTRATE"
        if eu_acr:
            row["eu-acronym"] = eu_acr.value
        row["number"] = number
        row["year"] = year
        if date:
            row["doc-date"] = date.value

        # Apply chronology only once the act type is known. In particular, a two-digit Regio
        # Decreto year belongs to 1861-1946, not to the contemporary pivot used by ordinary
        # citations. A document-year ceiling is optional metadata supplied by the caller.
        year_source = num_year.text if num_year else (date.text if date else "")
        year_match = _re2.search(r"(\d{2}|\d{4})\D*$", year_source or "")
        raw_year = year_match.group(1) if year_match else ""
        normalized_year = NZ.year_for_doctype(row["doc-type"], row["year"], raw_year)
        if normalized_year != row["year"]:
            if row["doc-date"] and row["year"] and row["doc-date"].startswith(row["year"] + "-"):
                row["doc-date"] = (normalized_year + row["doc-date"][4:]) if normalized_year else ""
            row["year"] = normalized_year
        if context.document_year and row["year"].isdigit() and \
                int(row["year"]) > context.document_year:
            if row["doc-date"].startswith(row["year"] + "-"):
                row["doc-date"] = ""
            row["year"] = ""
        if case_num:
            row["case-number"] = case_num.value
            # a CGUE case id is self-identifying: imply the authority (the CELEX is built
            # from this normalized case-number in the identifier phase, _build_identifier).
            if not row["authority"]:
                row["authority"] = "CGUE"

        # an alias *is* its act: its number/year are fixed by the alias, so a nearby document
        # number is never this reference's (it is a docket, or belongs to an adjacent act).
        if row["alias"] and (row["alias"] in ALIAS_NIR or row["alias"] in ALIAS_CELEX):
            row["number"] = row["year"] = row["full-number"] = ""
        # who-can-emit-what: the Agenzia delle Entrate / Dogane does not hand down a sentenza or
        # an ordinanza — an agency mention next to such a doc-type is not its emitter, so drop it.
        if row["other-authority"] and row["doc-type"] and \
                row["doc-type"] not in AGENCY_DOCTYPES | CONDITIONAL_AGENCY_DOCTYPES:
            row["other-authority"] = ""

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
            bool(case_num) or bool(rv_num)
        # a "direttiva" is inherently an EU act (CELEX) even without an explicit acronym;
        # REG/DECIS/RACC can also be national, so they need the EU acronym to confirm.
        is_eu = row["doc-type"] == "DIR" or row["authority"] == "CGUE" or \
            (bool(eu_acr) and row["doc-type"] in NZ.EU_PROV_LETTER) or \
            (row["doc-type"] == "REG" and bool(doctype) and doctype.attrs.get("eu_hint"))
        # a bare "regolamento N/YYYY" (no acronym, not nationally qualified) follows the
        # configured default scope; "regolamento ministeriale/comunale/..." stays national.
        if row["doc-type"] == "REG" and not eu_acr and reg_scope == "comunitario" and \
                (doctype is None or doctype.attrs.get("scope") != "nazionale"):
            is_eu = True
        is_regional = bool(doctype) and doctype.attrs.get("scope") == "regionale"
        if is_caselaw:
            row["ref-type"] = "caselaw"
            row["ref-scope"] = "comunitario" if row["authority"] == "CGUE" else "nazionale"
        elif row["doc-type"] == "DEL" and row["authority"] == "COMUNE":
            row["ref-type"] = "other acts"
            row["ref-scope"] = "nazionale"
        elif row["doc-type"] in PRASSI_DOCTYPES or (
                row["doc-type"] in CONDITIONAL_AGENCY_DOCTYPES
                and row["other-authority"] and not eu_acr):
            # prassi (Agenzia Entrate circolari / risoluzioni / interpelli, ...) is a first-class
            # ref-type here (administrative practice; its identifier scheme is PRAX).
            row["ref-type"] = "prassi"
            row["ref-scope"] = "nazionale"
        elif row["doc-type"] or row["alias"] or row["other-authority"]:
            row["ref-type"] = "legislation"
            if is_regional:
                row["ref-scope"] = "regionale"
            elif is_eu or row["alias"] in RZ.EU_ALIASES:
                row["ref-scope"] = "comunitario"
            elif row["alias"] in RZ.INTL_ALIASES:
                row["ref-scope"] = "internazionale"
            else:
                row["ref-scope"] = "nazionale"

        # Recitals ("considerando") are a partition type only for EU legislative acts.
        if row["partition"] and "considerando-" in row["partition"] and not (
                row["ref-scope"] == "comunitario" and row["doc-type"] in ("REG", "DIR", "DECIS")):
            row["partition"] = ""

        # region is a recognition field: a regional law's region comes from the citation,
        # else the document's default region. Resolve it here (phase 1) so the identifier
        # phase needs only the row, never the spans.
        if is_regional:
            ru = (doctype.attrs.get("region_urn") if doctype else "") or \
                context.regional_law_region or ""
            if ru:
                row["region"] = ru

        # case-law docket numbers are never zero-padded ("Cass. n. 08508/2019" -> 8508).
        if row["ref-type"] == "caselaw" and row["number"]:
            row["number"] = row["number"].lstrip("0") or row["number"]
        return row

    # phase 2 (urn building + legacy url / cited-doc-simple-id derivation) lives in urn.py
    # (build_urn / compat_fields), called from extract().
