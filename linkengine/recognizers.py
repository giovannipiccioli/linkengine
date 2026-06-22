"""
Recognizers: each scans the immutable input text and returns typed Spans. They are pure
functions (text -> [Span]); the pipeline runs them in order and records a debug trace.

v1 coverage is focused on the tax-litigation domain: national legislation (the largest and
highest-value class for URN building), plus the scaffolding for EU acts, case law, aliases
and partitions. Each recognizer is table/regex driven so coverage grows by extending tables.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional

from .model import Entity, Span, MONTHS
from .normalize import norm_latin_suffix, norm_year, valid_date, valid_year

I = re.IGNORECASE


def _nonoverlap(spans: List[Span]) -> List[Span]:
    """Keep spans greedily by (longer first), dropping any that overlap an accepted one."""
    out: List[Span] = []
    for s in sorted(spans, key=lambda x: (x.start, -(x.end - x.start))):
        if all(s.end <= o.start or s.start >= o.end for o in out):
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_MONTH_RE = re.compile(
    r"\b(\d{1,2})[°ºo]?\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\b", I)   # incl. "1° gennaio"
# numeric date; the year may be 2- or 4-digit ("D.P.R. 12/2/65 n. 162" -> 1965)
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})\s?[/.\-]\s?(\d{1,2})\s?[/.\-]\s?(\d{2}|\d{4})\b")


def recognize_dates(text: str) -> List[Span]:
    spans = []
    for m in _MONTH_RE.finditer(text):
        d, mon, y = m.group(1), m.group(2).lower(), m.group(3)
        yy = valid_year(y)                       # month name fixes mm; still range-check yyyy
        if yy and 1 <= int(d) <= 31:
            val = f"{yy}-{MONTHS[mon]}-{int(d):02d}"
            spans.append(Span(m.start(), m.end(), Entity.DATE, val, m.group(0), {"year": yy}))
    for m in _NUM_DATE_RE.finditer(text):
        # "n. 12/5/2020" is a docket number/section/year, not a date — leave it to the numbers
        if re.search(r"\bnn?\.?\s*$", text[max(0, m.start() - 5):m.start()], I):
            continue
        yy = valid_date(m.group(1), m.group(2), m.group(3))   # dd<=31, mm<=12, year in range
        if yy:
            val = f"{yy}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
            spans.append(Span(m.start(), m.end(), Entity.DATE, val, m.group(0), {"year": yy}))
    return _nonoverlap(spans)


# Partition element recognition lives in partitions.py (recognition + segmentation).
from .partitions import recognize_elements as recognize_partitions  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Numbers / years / case numbers
# ---------------------------------------------------------------------------
# number/year forms "A/B". Both sides are 1-5 digits; _order_num_year decides which is the
# number and which the year (IT number/year "137/1971" vs EU year/number "2006/112"), and
# rejects the token when neither part looks like a year. The (?![/.]\d) guard avoids
# matching the middle of a date ("31/12/2020").
# the "n." marker may be written "n°" / "n.°" (degree sign), "num." or plural "nn.".
_NUM_YEAR = re.compile(r"\bn(?:n|um(?:ero)?)?[.°]*\s*(\d{1,5})\s*/\s*(\d{1,5})(?![/.]\d)", I)
# plural docket list with no per-number year ("nn. 26636 e 26637 del 18.12.2009" — the year
# comes from the date); each bare number is a separate docket of the same court.
_NN_LIST = re.compile(r"\bnn\.?\s*", I)
_NN_NUM = re.compile(r"(\d{1,6})(?![\d/])")
_NN_SEP = re.compile(r"[\s,]*(?:e|ed)\s+(?=\d)", I)
# "del" makes the second part the year, so the "n." prefix is optional here
# ("d.lgs. 504 del 1992", "legge 241 del 1990"). The month-name lookahead stops "n. 53 del 18
# marzo 2013" from reading the *day* (18) as a 2-digit year.
_NUM_DEL_YEAR = re.compile(
    r"\b(?:n(?:um(?:ero)?)?\.?\s*)?(\d{1,5})\s+del\s+(\d{2}|\d{4})(?![/.\-]\d)\b"
    r"(?!\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|"
    r"novembre|dicembre))", I)
# a bare "number/year" not introduced by "n."/"del". The lookbehind forbids a preceding word
# char or "/" (it would be part of a larger token / a date), and a *decimal* dot (digit then
# dot, "12.05") — but ALLOWS an abbreviation dot ("Cass.1532/2012", "L.147/2013"), where a
# letter precedes the dot, so attached-citation forms (no space after the abbreviation) parse.
# the (?!\d) stops the second group truncating inside a 3-part date ("08/07/2022" must NOT
# yield "08/0"); (?![/.]\d) rejects a real date's third part. A trailing "." (sentence end) is
# still allowed.
_BARE_NUM_YEAR = re.compile(r"(?<![\w/])(?<!\d\.)(\d{1,5})\s*/\s*(\d{1,5})(?!\d)(?![/.]\d)")
# tax-court "number/section/year" ("n. 1234/5/2020", "1824/25/2020"): three "/"-parts. The full
# docket goes to `full-number`; the ECLI needs only number + year. With an "n."/"nn." marker the
# form is unambiguous; bare, it is accepted only when it cannot be a date (see _BARE_SEZ_YEAR).
_NUM_SEZ_YEAR = re.compile(r"\bn(?:n|um(?:ero)?)?\.?\s*(\d{1,5})\s*/\s*(\d{1,3})\s*/\s*(\d{2}|\d{4})\b", I)
_BARE_SEZ_YEAR = re.compile(r"(?<![\w/.])(\d{1,5})\s*/\s*(\d{1,3})\s*/\s*(\d{2}|\d{4})\b")
# "NNN del <day month>" -> NNN is the act number; the year comes from the DATE span
# ("D.P.R. 600 del 29 settembre 1973" -> number 600, year 1973).
_NUM_DEL_DATE = re.compile(
    r"\b(?:n(?:um(?:ero)?)?\.?\s*)?(\d{1,5})\s+del\s+(?=\d{1,2}[°ºo]?\s+(?:" +
    "|".join(MONTHS) + r")\b)", I)
_NUMBER = re.compile(r"\bn(?:um(?:ero)?)?[.°]*\s*(\d{1,6})\b", I)
_YEAR = re.compile(r"\b(?:del\s+)?((?:18|19|20)\d{2})\b", I)
# self-identifying CJEU case id: the dash is REQUIRED ("C-439/04", "T-45/20"). Without it a
# stray "C 198/01" (e.g. in a GUUE reference "(2014/C 198/01)") is NOT a case — only the dash
# distinguishes a case number from a column/series notation.
_CASE_CGUE = re.compile(r"\b([CT])\s?[\-‑]\s?(\d{1,4})\s*/\s*(\d{2,4})\b")
# with a "causa/cause" keyword the C-/T- prefix and the dash become optional: "causa 276/12",
# "causa 14-70", "cause 91/79 e 92/79". The keyword marks a CJEU case (default: Court of
# Justice, C); the number/year may be slash- or dash-separated.
_CAUSA_KW = re.compile(r"\bcaus[ae]\s+(?:riunit[ae]\s+)?", I)
_CAUSA_CASE = re.compile(r"\s*(?:(C|T)\s?[\-‑]\s?)?(\d{1,4})\s*[/\-]\s*(\d{2,4})\b", I)
_CAUSA_SEP = re.compile(r"[\s,]*(?:e|ed)\s+", I)
# joined cases: "cause riunite C-216 e 222/99" / "cause riunite C-279, 280 e 281/96" — a SINGLE
# reference whose number is the smallest, with the trailing year shared across all of them.
_RIUNITE = re.compile(r"\bcaus[ae]\s+riunit[ae]\b", I)
_RIUNITE_RUN = re.compile(r"[\s,]*(?:e|ed)?\s*(?:(C|T)\s?[\-‑]\s?)?(\d{1,4})(?:\s*/\s*(\d{2,4}))?\b", I)
# Agenzia Entrate "NNN/E[/YYYY]" docket (circolare/risoluzione). The "n." prefix is optional —
# the distinctive "/E" marker carries the form ("circolare 12/E/2020" with no "n."). A bare
# "NNN/E" only becomes a citation when a prassi doc-type is present, so dropping "n." is safe.
_ADE_NUM = re.compile(r"(?:\bn(?:um(?:ero)?)?\.?\s*)?(\d{1,5})\s*/\s*[eE]\b(?:\s*/\s*((?:18|19|20)\d{2}))?")
# historical Cassazione "number-year" with a dash ("Cass. 2968-73", "legge 392-78"). Heavily
# guarded (see _dash_year_ok): the 2nd part must be a real year, an act/court keyword must
# immediately precede, and no partition marker may precede — so partition ranges ("commi 5-7")
# and bare ranges ("pagine 10-15", "1970-1980") are never read as a citation number.
_NUM_DASH_YEAR = re.compile(r"(?<![\w./-])(\d{1,5})\s*-\s*(\d{2,4})(?![\d./-])")
_DASH_ACT_CTX = re.compile(
    r"(?:legg[ei]|\bl|d\.?\s?l(?:gs)?|d\.?\s?p\.?\s?r|\br\.?\s?d|decret[oi]|cass|sentenz|"
    r"ordinanz|cort[ei]|consiglio|\bnn?|s\.?\s?u|ss\.?\s?uu)[\s.,)]*$", I)
_DASH_PART_CTX = re.compile(r"(?:comm[ai]|artt?|articol[oi]|lett|numer[oi]|punt[oi]|paragraf)[\s.,)]*$", I)
# old EU acts use 2-digit-year/number order ("direttiva 77/388/CEE" = year 1977, number 388);
# the trailing EU acronym disambiguates it from the Italian number/year order.
_EU_NUM_YEAR = re.compile(r"\b(\d{2})\s*/\s*(\d{1,4})\s*/\s*(?:cee|ce|ue|ceca|euratom)\b", I)


def _is_year4(x: str) -> bool:
    return len(x) == 4 and valid_year(x) is not None


def _order_num_year(a: str, b: str):
    """Given the two parts of an "A/B" token, decide which is the number and which the year
    — without assuming order. Italian acts are number/year ("legge 137/1971"); EU acts are
    year/number ("direttiva 2006/112"). The 4-digit part within [MIN_YEAR, MAX_YEAR] is the
    year; failing that, a trailing 2-digit value ("602/73") is a 2-digit year. Returns None
    when neither part is a plausible year (e.g. "5/6"), so non-citations are rejected."""
    if _is_year4(b):
        return a, b
    if _is_year4(a):
        return b, a
    if len(b) == 2 and valid_year(b):
        return a, norm_year(b)        # "602/73" -> number 602, year 1973 (IT, year last)
    if len(a) == 2 and valid_year(a):
        return b, norm_year(a)        # "90/435" -> number 435, year 1990 (old EU dir, year first)
    return None


def recognize_numbers(text: str) -> List[Span]:
    spans: List[Span] = []
    taken: List[tuple] = []   # (start,end) ranges already consumed

    def overlaps(a, b):
        return not (a[1] <= b[0] or a[0] >= b[1])

    def free(s, e):
        return all(not overlaps((s, e), t) for t in taken)

    # 0) old EU "YY/NNN/CEE" (year/number) — claim before the general number/year forms
    for m in _EU_NUM_YEAR.finditer(text):
        yy, num = m.group(1), m.group(2)
        spans.append(Span(m.start(1), m.end(2), Entity.NUM_YEAR, f"{num}/{norm_year(yy)}",
                          text[m.start(1):m.end(2)], {"number": num, "year": norm_year(yy)}))
        taken.append((m.start(1), m.end(2)))

    # 0b) Agenzia Entrate "NNN/E[/YYYY]" forms (circolari/risoluzioni) — claim before others
    for m in _ADE_NUM.finditer(text):
        num, yr = m.group(1), (m.group(2) or "")
        full = f"{num}/E" + (f"/{yr}" if yr else "")
        spans.append(Span(m.start(), m.end(), Entity.NUM_YEAR, f"{num}/{yr}" if yr else num,
                          m.group(0), {"number": num, "year": yr, "full": full, "ade": "1"}))
        taken.append((m.start(), m.end()))

    # 0c) "cause riunite ..." -> ONE case (smallest number; the trailing year is shared). Must
    # run before the per-case handlers so they don't split the joined run.
    for rm in _RIUNITE.finditer(text):
        nums, year, s0, e0, p = [], None, None, None, rm.end()
        while True:
            cm = _RIUNITE_RUN.match(text, p)
            if not cm or not cm.group(2):
                break
            ns = cm.start(1) if cm.group(1) else cm.start(2)
            s0 = ns if s0 is None else s0
            e0 = cm.end()
            nums.append(((cm.group(1) or "C").upper(), int(cm.group(2))))
            if cm.group(3):
                year = norm_year(cm.group(3))
            p = cm.end()
        if nums and year and s0 is not None and free(s0, e0):
            kind, mn = nums[0][0], min(n for _, n in nums)
            spans.append(Span(s0, e0, Entity.CASE_NUMBER, f"{kind}-{mn}/{year}", text[s0:e0],
                              {"number": str(mn), "year": year, "kind": kind}))
            taken.append((s0, e0))

    # 1) CGUE case numbers (C-21/16) — distinctive; skip any already inside a "cause riunite" run
    for m in _CASE_CGUE.finditer(text):
        if not free(m.start(), m.end()):
            continue
        kind, n, y = m.group(1).upper(), m.group(2), norm_year(m.group(3))
        val = f"{kind}-{n}/{y}"
        spans.append(Span(m.start(), m.end(), Entity.CASE_NUMBER, val, m.group(0),
                          {"number": n, "year": y, "kind": kind}))
        taken.append((m.start(), m.end()))

    # 1a) "causa/cause [C-]NNN/YY" (incl. lists "cause 91/79 e 92/79") — the keyword licenses the
    # looser forms (no C- prefix, dash- or slash-separated); default kind is the Court of Justice.
    for km in _CAUSA_KW.finditer(text):
        pos = km.end()
        while True:
            cm = _CAUSA_CASE.match(text, pos)
            if not cm:
                break
            s = cm.start(1) if cm.group(1) else cm.start(2)
            if free(s, cm.end()):
                kind, n, y = (cm.group(1) or "C").upper(), cm.group(2), norm_year(cm.group(3))
                spans.append(Span(s, cm.end(), Entity.CASE_NUMBER, f"{kind}-{n}/{y}",
                                  text[s:cm.end()], {"number": n, "year": y, "kind": kind}))
                taken.append((s, cm.end()))
            pos = cm.end()
            sep = _CAUSA_SEP.match(text, pos)              # "... e 92/79"
            if sep and _CAUSA_CASE.match(text, sep.end()):
                pos = sep.end()
            else:
                break

    # 1b) tax-court "NNN/SEZ/YYYY" (number/section/year) — claim the 3-part form before the
    # 2-part number/year so the section is not mistaken for the year. The "n."/"nn." marked form
    # is unambiguous; a bare one is only a docket when it cannot be a date (number>31 or sez>12).
    for m in _NUM_SEZ_YEAR.finditer(text):
        if not free(m.start(), m.end()) or not valid_year(m.group(3)):
            continue
        num, y, full = m.group(1), valid_year(m.group(3)), f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        spans.append(Span(m.start(), m.end(), Entity.NUM_YEAR, f"{num}/{y}", m.group(0),
                          {"number": num, "year": y, "section": m.group(2), "full": full}))
        taken.append((m.start(), m.end()))
    for m in _BARE_SEZ_YEAR.finditer(text):
        if not free(m.start(), m.end()) or not valid_year(m.group(3)):
            continue
        if int(m.group(1)) <= 31 and int(m.group(2)) <= 12:    # could be a real dd/mm/yyyy date
            continue
        num, y, full = m.group(1), valid_year(m.group(3)), f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        spans.append(Span(m.start(), m.end(), Entity.NUM_YEAR, f"{num}/{y}", m.group(0),
                          {"number": num, "year": y, "section": m.group(2), "full": full}))
        taken.append((m.start(), m.end()))

    # 2) number/year bound forms ("A/B"): decide which part is the year (IT number/year vs
    # EU year/number), and normalize a 2-digit year.
    for pat in (_NUM_YEAR, _NUM_DEL_YEAR, _BARE_NUM_YEAR):
        for m in pat.finditer(text):
            if not free(m.start(), m.end()):
                continue
            ny = _order_num_year(m.group(1), m.group(2))
            if ny is None:
                continue
            n, y = ny
            spans.append(Span(m.start(), m.end(), Entity.NUM_YEAR, f"{n}/{y}", m.group(0),
                              {"number": n, "year": y}))
            taken.append((m.start(), m.end()))

    # 2a) historical dash "number-year" ("Cass. 2968-73"), context-guarded
    for m in _NUM_DASH_YEAR.finditer(text):
        if not free(m.start(), m.end()):
            continue
        y = valid_year(m.group(2))
        if not y:
            continue
        prefix = text[max(0, m.start() - 14):m.start()]
        if _DASH_PART_CTX.search(prefix) or not _DASH_ACT_CTX.search(prefix):
            continue
        num = m.group(1)
        spans.append(Span(m.start(), m.end(), Entity.NUM_YEAR, f"{num}/{y}", m.group(0),
                          {"number": num, "year": y}))
        taken.append((m.start(), m.end()))

    # 2b) "NNN del <date>": capture the act number; its year is supplied by the DATE span
    for m in _NUM_DEL_DATE.finditer(text):
        if not free(m.start(1), m.end(1)):
            continue
        spans.append(Span(m.start(1), m.end(1), Entity.NUMBER, m.group(1), m.group(1),
                          {"number": m.group(1)}))
        taken.append((m.start(1), m.end(1)))

    # 2d) plural "nn. X e Y" -> a bare NUMBER for each (num/year forms were already claimed above)
    for km in _NN_LIST.finditer(text):
        pos = km.end()
        while True:
            nm = _NN_NUM.match(text, pos)
            if not nm:
                break
            if free(nm.start(), nm.end()):
                spans.append(Span(nm.start(), nm.end(), Entity.NUMBER, nm.group(1),
                                  nm.group(1), {"number": nm.group(1)}))
                taken.append((nm.start(), nm.end()))
            pos = nm.end()
            sep = _NN_SEP.match(text, pos)
            if sep:
                pos = sep.end()
            else:
                break

    # 3) standalone document numbers (n. NNN)
    for m in _NUMBER.finditer(text):
        if not free(m.start(), m.end()):
            continue
        spans.append(Span(m.start(), m.end(), Entity.NUMBER, m.group(1), m.group(0),
                          {"number": m.group(1)}))
        taken.append((m.start(), m.end()))

    # 4) standalone years (range-validated: a bare 4-digit number is a year only in range)
    for m in _YEAR.finditer(text):
        if not free(m.start(), m.end()) or not valid_year(m.group(1)):
            continue
        spans.append(Span(m.start(), m.end(), Entity.YEAR, m.group(1), m.group(0),
                          {"year": m.group(1)}))
        taken.append((m.start(), m.end()))

    return spans


# ---------------------------------------------------------------------------
# Doc types (ordered: longest / most specific first)
# ---------------------------------------------------------------------------
# (regex, doc-type code, authority code, default ref-scope). Patterns carry their own
# boundaries; abbreviations end with (?!\w) so a trailing '.' doesn't break the match.
_DOCTYPE_PATTERNS = [
    # historical 1944–48 acts (before the plain DL/DLGS): luogotenenziale and del Capo
    # Provvisorio dello Stato -> luogotenente:... and capo.provvisorio.stato:...
    (r"\bdecreto\s+legislativo\s+luogotenenziale\b|\bd\.?\s?lgs\.?\s?lgt\.?(?!\w)", "DLGS_LGT", "", "nazionale"),
    (r"\bdecreto[-\s]?legge\s+luogotenenziale\b|\b(?:decreto\s+)?luogotenenziale\b|\bd\.?\s?l\.?\s?lgt\.?(?!\w)", "DL_LGT", "", "nazionale"),
    (r"\bdecreto\s+legislativo\s+del\s+capo\s+provvisorio\s+dello\s+stato\b|\bd\.?\s?lgs\.?\s?c\.?\s?p\.?\s?s\.?(?!\w)", "DLGS_CPS", "", "nazionale"),
    (r"\bdecreto[-\s]?legge\s+del\s+capo\s+provvisorio\s+dello\s+stato\b|\bd\.?\s?l\.?\s?c\.?\s?p\.?\s?s\.?(?!\w)", "DL_CPS", "", "nazionale"),
    # DPCM (decreto del Presidente del Consiglio dei Ministri) — before D.P.R.
    (r"\bdecreto\s+del\s+presidente\s+del\s+consiglio\s+dei\s+ministri\b|\bd\.?\s?p\.?\s?c\.?\s?m\.?(?!\w)", "DECR", "PRES_CONS_MIN", "nazionale"),
    (r"\bdecreto\s+del\s+presidente\s+della\s+repubblica\b", "DECR", "PRES_REP", "nazionale"),
    (r"\bd\.?\s?p\.?\s?r\.?(?!\w)", "DECR", "PRES_REP", "nazionale"),
    (r"\bdecreto\s+legislativo\b", "DLGS", "", "nazionale"),
    (r"\bd\.?\s?l\.?gs\.?(?!\w)", "DLGS", "", "nazionale"),
    (r"\bd\.?\s?lgs\.?(?!\w)", "DLGS", "", "nazionale"),
    # "...vo" variants of decreto legislativo: d.l.vo / D.Lg.vo / D. Lgv. / d.lgv.
    (r"\bd\.?\s?lg?\.?\s?v\.?o?\.?(?!\w)", "DLGS", "", "nazionale"),
    (r"\bdecreto[-\s]?legge\b", "DL", "", "nazionale"),
    (r"\blegge\s+costituzionale\b", "LC", "", "nazionale"),
    (r"\bregio\s+decreto\b", "RD", "", "nazionale"),
    (r"\br\.?\s?d\.?(?!\w)", "RD", "", "nazionale"),
    (r"\bdecreto\s+ministeriale\b", "DECR", "MINISTERO", "nazionale"),
    # "decreto MEF/MiSE/MIT …" — a ministry acronym after "decreto" makes it a D.M.
    (r"\bdecreto\s+(?:del\s+)?(?:m\.?e\.?f\.?|mef|m\.?i\.?s\.?e\.?|mise|mit|mims|m\.?i\.?u\.?r\.?|miur)\b",
     "DECR", "MINISTERO", "nazionale"),
    (r"\bd\.?\s?m\.?(?!\w)", "DECR", "MINISTERO", "nazionale"),
    (r"\bd\.?\s?l\.?(?!gs)(?!\w)", "DL", "", "nazionale"),
    (r"\bl\.\s*n[.°]*(?=\s*\d)", "L", "", "nazionale"),     # "l. n. 212" / "l. n° 212"
    (r"\bl\.(?=\s*\d)", "L", "", "nazionale"),               # "l. 212"
    (r"\bl\s+(?=\d{1,5}\s*/\s*\d{2,4}\b)", "L", "", "nazionale"),   # dot-less "L 197/2022"
    # plain legge, but not "legge regionale / della Regione" (handled by recognize_regional_laws)
    (r"\blegg[ei]\b(?!\s+(?:regional|(?:della\s+)?regione))", "L", "", "nazionale"),
    # a nationally-qualified regolamento is always national (never follows the EU default flag)
    (r"\bregolament[oi]\s+(?:ministerial[ei]|comunal[ei]|regional[ei]|governativ[oi]|"
     r"di\s+(?:esecuzione|attuazione))", "REG", "", "nazionale"),
    (r"\bregolament[oi]\b", "REG", "", "comunitario"),
    # "Reg. (CE) n. ..." / "Reg. UE 2017/2093" — match just "Reg." (lookahead keeps the acronym
    # free for the EU detector, which is what flags the act as comunitario).
    (r"\breg\.?(?=\s*\(?\s*(?:ce|ue|cee)\b|\s*n?\.?\s*\d)", "REG", "", "comunitario"),
    (r"\bdirettiv[ae]\b", "DIR", "", "comunitario"),
    # "Dir. 69/335/CEE" has the acronym AFTER the number, so accept a bare digit too (a
    # directive is inherently an EU act, so this stays comunitario regardless).
    (r"\bdir\.?(?=\s*\(?\s*(?:ce|ue|cee)\b|\s*n?\.?\s*\d)", "DIR", "", "comunitario"),
    (r"\bdecision[ei]\b", "DECIS", "", "comunitario"),
    (r"\braccomandazion[ei]\b", "RACC", "", "comunitario"),
    (r"\bcircolar[ei]\b|\bcirc\.", "CIRC", "", "nazionale"),
    (r"\brisoluzion[ei]\b|\brisol?\.", "RIS", "", "nazionale"),
    (r"\binterpell[oi]\b|risposta\s+a\s+quesito|\bquesit[oi]\b", "INTERPELLO", "", "nazionale"),
    (r"\bdeliberazion[ei]\b|\bdeliber[ae]\b|\bdelib\.", "DEL", "", "nazionale"),
    (r"\bprovvediment[oi]\b", "PROVV", "", "nazionale"),
    (r"\bsentenz[ae]\b", "SENT", "", "caselaw"),
    (r"\bsent\.", "SENT", "", "caselaw"),
    (r"\bordinanz[ae]\b", "ORD", "", "nazionale"),
    (r"\bord\.", "ORD", "", "nazionale"),
]
_DOCTYPE_COMPILED = [(re.compile(p, I), code, auth, scope)
                     for p, code, auth, scope in _DOCTYPE_PATTERNS]


def recognize_doctypes(text: str) -> List[Span]:
    spans = []
    for pat, code, auth, scope in _DOCTYPE_COMPILED:
        for m in pat.finditer(text):
            spans.append(Span(m.start(), m.end(), Entity.DOCTYPE, code, m.group(0),
                              {"authority": auth, "scope": scope}))
    return _nonoverlap(spans)


# ---------------------------------------------------------------------------
# EU acronyms
# ---------------------------------------------------------------------------
_EU_ACRONYM = re.compile(r"\(?\b(UE|CEE|CECA|CE|EU|EURATOM)\b\)?")


def recognize_eu_acronyms(text: str) -> List[Span]:
    spans = []
    for m in _EU_ACRONYM.finditer(text):
        spans.append(Span(m.start(), m.end(), Entity.EU_ACRONYM, m.group(1).upper(),
                          m.group(0)))
    return spans


# ---------------------------------------------------------------------------
# Authorities / courts (case law + agencies), with geo binding for ECLI.
# Each court pattern declares whether it needs a trailing geo: 'region' (CTR),
# 'city' (CTP / tribunale / corte d'appello / ...), 'either' (bare CGT -> decide by the
# geo type) or None.
# ---------------------------------------------------------------------------
_ACCENTS = str.maketrans("àáâãèéêëìíîïòóôõùúûüÀÁÈÉÌÍÒÓÙÚ", "aaaaeeeeiiiioooouuuuAAEEIIOOUU")
_GEO_LEAD = re.compile(
    r"^[\s,.:;]*(?:di\s+|della\s+|del\s+|d['’]\s*|presso\s+)?"
    r"(?:sez(?:ione)?\.?\s*[ivxlcdm0-9]+[°ªa-z]*[,\s]*)?", I)

_COURT_PATTERNS = [
    # self-references ("questa Corte", "questo Tribunale", ...) -> THIS_COURT, resolved to
    # the document's authority via default_authority (e.g. a Cassazione decision citing its
    # own prior sentences: "sentenza n. 123/2020 di questa Corte").
    (r"quest[ao]\s+(?:suprema\s+|ecc(?:ellentissima|\.?)\s+)?cort[ei]", "THIS_COURT", None),
    (r"codesta\s+(?:suprema\s+)?cort[ei]", "THIS_COURT", None),
    (r"\bla\s+suprema\s+corte\b", "THIS_COURT", None),
    (r"quest[ao]\s+tribunal[ei]", "THIS_COURT", None),
    (r"quest[ao]\s+commission[ei](?:\s+tributaria)?", "THIS_COURT", None),
    (r"quest[ao]\s+(?:collegio|consiglio)", "THIS_COURT", None),
    (r"comm(?:issione)?\.?\s+trib(?:utaria)?\.?\s+reg(?:ionale)?\.?", "COMM_TRIBUT_REG", "region"),
    (r"\bc\.?\s?t\.?\s?r\.?\b", "COMM_TRIBUT_REG", "region"),
    (r"comm(?:issione)?\.?\s+trib(?:utaria)?\.?\s+prov(?:inciale|\.?\s?le)?\.?", "COMM_TRIBUT_PROV", "city"),
    (r"\bc\.?\s?t\.?\s?p\.?\b", "COMM_TRIBUT_PROV", "city"),
    (r"comm(?:issione)?\.?\s+trib(?:utaria)?\.?\s+centr(?:ale)?\.?|\bc\.?\s?t\.?\s?c\.?\b",
     "COMM_TRIBUT_CEN", None),
    # Corte di Giustizia Tributaria (2022 reform). The grade (primo/secondo) decides
    # CTP/city vs CTR/region; resolved in _cgt_resolve.
    # Full and abbreviated spellings: "Corte di Giustizia Tributaria", "Cort. Giust. Trib.",
    # "Corte Giust. Trib." — a trailing "Reg."/"Prov." scope is consumed by _cgt_resolve.
    (r"corte\s+di\s+giustizia\s+tributaria", "CGT", "cgt"),
    (r"cort[e'’]?\.?\s*giust(?:izia)?\.?\s*trib(?:utaria)?\.?", "CGT", "cgt"),
    (r"\bc\.?\s?g\.?\s?t\.?\b", "CGT", "cgt"),
    (r"corte\s+d['’]?\s?assise\s+d['’]?\s?appello", "CORTE_ASSISE_APPELLO", "city"),
    (r"corte\s+d['’]?\s?appello", "CORTE_APPELLO", "city"),
    (r"corte\s+d['’]?\s?assise", "CORTE_ASSISE", "city"),
    (r"corte\s+di\s+cassazione", "CORTE_CASS", None),
    # "Sezioni Unite" / "SS.UU." (the Cassazione's united sections): cited on their own as a
    # synonym for the Court of Cassation ("le Sezioni Unite, sent. n. 2281/1990"). The bare
    # section abbreviation "sez. un." is left to the section mechanism (section="un").
    (r"sezioni\s+unite|\bss\.?\s?uu\.?", "CORTE_CASS", None),
    (r"\bcass(?:azione)?\.?", "CORTE_CASS", None),
    (r"corte\s+cost(?:ituzionale)?", "CORTE_COST", None),
    # "C. Cost." (Corte abbreviated to "C.") -> the Court, not the COST/'Cost.' alias; the
    # overlapping alias is dropped by _resolve_overlaps, so "C. Cost. n. 188/2018" -> ECLI.
    (r"\bc\.\s?cost(?:ituzionale)?\b\.?", "CORTE_COST", None),
    (r"consiglio\s+di\s+stato|cons\.?\s+stato", "CONS_STATO", None),
    (r"corte\s+dei\s+conti", "CORTE_CONTI", None),
    # Court of Justice EU/EC — the former "Corte di Giustizia CE / delle Comunità europee"
    # (and its CGCE abbreviation) is mapped to CGUE: it is the same court, renamed in 2009.
    (r"corte\s+di\s+giustizia\s+(?:dell[e'’\s]\s?unione\s+europea|dell[e'’\s]\s?ue\b|"
     r"dell[e'’]\s?comunit[aà]\s+europee?|dell[ae]\s+comunit[aà]\s+economica\s+europea|"
     r"ue\b|c\.?e\.?e?\.?\b|europea\b)", "CGUE", None),
    # word-order / spelling variants: "Corte Europea di Giustizia", "Corte (di) Giustizia CEE/CE"
    (r"corte\s+europea\s+di\s+giustizia", "CGUE", None),
    (r"corte\s+(?:di\s+)?giustizia\s+c\.?e\.?e?\.?\b", "CGUE", None),
    (r"\bc\.?\s?g\.?\s?u\.?\s?e\.?\b|\bc\.?\s?g\.?\s?c\.?\s?e\.?\b", "CGUE", None),
    # Corte EDU (European Court of Human Rights); bare "CEDU" stays the convention alias
    (r"corte\s+e\.?\s?d\.?\s?u\.?|corte\s+europea\s+dei\s+diritti\s+dell['’]?\s?uomo", "CEDU", None),
    # TAR — administrative regional court (region-qualified, like CTR)
    (r"tribunale\s+amministrativo\s+regionale|\bt\.?\s?a\.?\s?r\.?\b", "TRIB_AMM_REG", "region"),
    (r"tribunale\s+di\s+sorveglianza", "TRIBUNALE_SORVEGLIANZA", "city"),
    (r"tribunale(?!\s+amministrativo|\s+superiore)", "TRIB", "city"),
    (r"giudice\s+di\s+pace", "GIUDICE_PACE", "city"),
    # comune (for a delibera comunale -> DEL:CO{city}); "di <City>" is required by the geo step
    (r"comune\s+di", "COMUNE", "city"),
]
_COURT_COMPILED = [(re.compile(r"\b" + p if p[0] == "c" or p[0] == "t" or p[0] == "g"
                               else p, I), v, want) for p, v, want in _COURT_PATTERNS]

_OTHER_AUTH_PATTERNS = [
    (r"agenzia\s+delle\s+entrate(?:\s+e\s+delle\s+dogane)?", "AG_ENTRATE"),
    (r"agenzia\s+entrate", "AG_ENTRATE"),
    # common abbreviations: AdE / A.d.E. / Ag. Entrate
    (r"\bade\b|\ba\.\s?d\.\s?e\.?|\bag\.?\s+entrate\b", "AG_ENTRATE"),
    (r"agenzia\s+delle\s+dogane(?:\s+e\s+dei\s+monopoli)?", "AG_DOGANE"),
]
_OTHER_AUTH_COMPILED = [(re.compile(p, I), v) for p, v in _OTHER_AUTH_PATTERNS]

from .geo import CITY_RE, REGION_RE, REGION_NAME_TO_CODE, city_code  # noqa: E402


def _geo_after(text: str, pos: int, want: str):
    """Look just past a court keyword for a province/region/comune name. Returns
    (kind, code, new_end) where kind in {'region','city',None}. City resolves to a 2-letter
    targa code for a capoluogo (Roma->RM) or the comune catastale code (Tivoli->L182)."""
    win = text[pos:pos + 55]
    lead = _GEO_LEAD.match(win)
    off = lead.end() if lead else 0
    sub = win[off:].translate(_ACCENTS)
    if want in ("region", "either"):
        # tolerate a hyphen between region-name words ("Emilia-Romagna", "Friuli-Venezia Giulia");
        # hyphen->space is length-preserving so the match offset still maps back into `sub`.
        m = REGION_RE.match(sub.replace("-", " "))
        if m:
            return "region", REGION_NAME_TO_CODE[m.group(1).lower()], pos + off + m.end()
    if want in ("city", "either"):
        m = CITY_RE.match(sub)
        if m:
            code = city_code(m.group(1))
            if code:
                return "city", code, pos + off + m.end()
    return None, None, pos


# case-law section just after a court keyword ("Cass. sez. trib.", "C.T.R. … Sez. V"). The
# section does not change the ECLI (which is …CIV) but completes the `section` feature field.
_SEZ_SEARCH = re.compile(
    r"\bsez(?:ione|\.)?\.?\s*(?:n\.?\s*)?"
    r"(trib(?:ut(?:aria)?)?|lavoro|lav|unit[ei]|un|penal[ei]|pen|civil[ei]|civ|feriale|"
    r"[ivxlcdm]{1,4}|\d{1,2})\b", I)
_SEZ_NORM = {"trib": "trib", "tributaria": "trib", "tribut": "trib", "lavoro": "lav", "lav": "lav",
             "unite": "un", "uniti": "un", "un": "un", "penale": "pen", "penali": "pen",
             "pen": "pen", "civile": "civ", "civili": "civ", "civ": "civ", "feriale": "feriale"}
_ROMAN_VAL = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman(s: str):
    """Convert a roman numeral to an int (subtractive), or None if not a clean roman."""
    if not s or any(ch not in _ROMAN_VAL for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VAL[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _section_after(text: str, pos: int) -> str:
    m = _SEZ_SEARCH.search(text[pos:pos + 45])
    if not m:
        return ""
    raw = m.group(1).lower()
    if raw in _SEZ_NORM:
        return _SEZ_NORM[raw]
    r = _roman(raw)                # "V" -> "5", "XVII" -> "17"
    return str(r) if r else raw


# Cassazione sezione: the section field combines the chamber NUMBER with its kind. Numbered
# civil sections render "<n>CIV" ("sesta sez. civ." -> "6CIV", "sez. V" -> "5CIV"); the
# tributaria is the fifth civil section ("sez. trib." -> "5CIV"); Sezioni Unite -> "UNITE";
# "lavoro"/"feriale" carry their own name. Cassazione-specific (other courts keep _section_after).
_CASS_ORDINAL = {"prima": "1", "primo": "1", "seconda": "2", "secondo": "2",
                 "terza": "3", "terzo": "3", "quarta": "4", "quarto": "4",
                 "quinta": "5", "quinto": "5", "sesta": "6", "sesto": "6"}
# chamber kind, highest precedence first (so "civ., sez. trib." reads as tributaria)
_CASS_KIND = [(r"sezioni\s+unite|\bss\.?\s?uu\b|\bs\.\s?u\.?\b|\bsez(?:ione|\.)?\.?\s*u(?:n(?:ite|iti)?)?\.?\b", "UNITE"),
              (r"\bferiale\b", "FERIALE"), (r"\blavoro\b|\blav\b", "LAVORO"),
              (r"\btribut(?:aria)?\b|\btrib\b", "TRIB"), (r"\bpenal[ei]\b|\bpen\b", "PEN"),
              (r"\bcivil[ei]\b|\bciv\b", "CIV")]
_CASS_KIND_RE = [(re.compile(p, I), k) for p, k in _CASS_KIND]
_CASS_SEZ_MARK = re.compile(r"\bsez(?:ione|\.)?\.?", I)
_CASS_SEZ_NUM = re.compile(r"\s*(?:n\.?\s*)?(\d{1,2}|[ivxlcdm]{1,4})\b", I)


def _cass_section(text: str, pos: int) -> str:
    """The Cassazione `section` value just after the court keyword. Empty when neither a
    "sez(ione)" marker nor a chamber keyword is present."""
    win = text[pos:pos + 50]
    kind = next((k for rx, k in _CASS_KIND_RE if rx.search(win)), None)
    msez = _CASS_SEZ_MARK.search(win)
    if not msez and kind is None:
        return ""
    if kind == "UNITE":
        return "UNITE"
    if kind == "FERIALE":
        return "FERIALE"
    if kind == "LAVORO":
        return "LAVORO"
    if kind == "TRIB":
        return "5CIV"
    suffix = "PEN" if kind == "PEN" else "CIV"
    # the chamber number: an ordinal word ("sesta") anywhere, else the token right after "sez"
    # (arabic or roman; a range "5-6"/"5^6" keeps the first).
    num = ""
    mo = re.search(r"\b(" + "|".join(_CASS_ORDINAL) + r")\b", win, I)
    if mo:
        num = _CASS_ORDINAL[mo.group(1).lower()]
    elif msez:
        mn = _CASS_SEZ_NUM.match(win[msez.end():])
        if mn:
            tok = mn.group(1).lower()
            num = tok if tok.isdigit() else (str(_roman(tok)) if _roman(tok) else "")
    if num:
        return f"{num}{suffix}"
    return suffix if kind in ("CIV", "PEN") else ""


# Corte di Giustizia Tributaria grade: "primo grado" (-> provincial / city, CTP) vs "secondo
# grado" (-> regional / region, CTR). The 2022 reform renamed CTP/CTR to CGT-I/CGT-II grado;
# the grade is the reliable discriminator (primo grado -> CTP/city, secondo -> CTR/region).
_CGT_GRADE = re.compile(
    r"^[\s,.:;)\-–—]*(?:di\s+|del\s+|della\s+)?"
    r"(?:(?P<p1>prim[oa])|(?P<s1>second[oa])|(?P<p2>1|i)\s*[°ª]?\s*(?=grad)|"
    r"(?P<s2>2|ii)\s*[°ª]?\s*(?=grad))\s*[°ª]?\s*grad[oi]\b", I)
# bare "CGT 1 <geo>" / "CGT 2 <geo>" with no "grado": accept the digit/roman as the grade only
# when a geo immediately follows (so "CGT 126/2024" is not read as grade 126).
_CGT_GRADE_BARE = re.compile(r"^[\s,.:;)\-–—]*(?:(?P<p>1|i)|(?P<s>2|ii))\s*[°ª]?[\s,.:;)\-–—]+", I)


def _cgt_resolve(text: str, pos: int):
    """Resolve a Corte di Giustizia Tributaria reference: detect the grade (primo -> CTP/city,
    secondo -> CTR/region) and the geo. Returns (authority, attrs, new_end)."""
    win = text[pos:pos + 70]
    # explicit "Reg."/"Prov." scope ("CGT Reg. Toscana", "Cort. Giust. Trib. Prov. Milano")
    ms = re.match(r"^[\s,.:;)\-–—]*(reg(?:ionale)?|prov(?:inciale)?)\.?(?=[\s,.:]|$)", win, I)
    if ms:
        b = pos + ms.end()
        kind, code, new_end = _geo_after(text, b, "either")
        if ms.group(1).lower().startswith("reg"):
            return "COMM_TRIBUT_REG", ({"region": code} if kind == "region" else
                                       ({"city": code} if kind else {})), (new_end if kind else b)
        return "COMM_TRIBUT_PROV", ({"city": code} if kind == "city" else
                                    ({"region": code} if kind else {})), (new_end if kind else b)
    grade, off = None, 0
    m = _CGT_GRADE.match(win)
    if m:
        grade = "primo" if (m.group("p1") or m.group("p2")) else "secondo"
        off = m.end()
    else:
        mb = _CGT_GRADE_BARE.match(win)
        if mb:
            k2, code2, _ = _geo_after(text, pos + mb.end(), "either")
            if k2:                          # only a grade if a real geo follows the digit
                grade = "primo" if mb.group("p") else "secondo"
                off = mb.end()
    base = pos + off
    kind, code, new_end = _geo_after(text, base, "either")
    if grade == "secondo":
        attrs = {"region": code} if kind == "region" else ({"city": code} if kind else {})
        return "COMM_TRIBUT_REG", attrs, (new_end if kind else base)
    if grade == "primo":
        attrs = {"city": code} if kind == "city" else ({"region": code} if kind else {})
        return "COMM_TRIBUT_PROV", attrs, (new_end if kind else base)
    # no explicit grade: decide by geo type (a region implies II grado, a city implies I grado)
    if kind == "region":
        return "COMM_TRIBUT_REG", {"region": code}, new_end
    if kind == "city":
        return "COMM_TRIBUT_PROV", {"city": code}, new_end
    return "COMM_TRIBUT_PROV", {}, base


def recognize_authorities(text: str) -> List[Span]:
    spans = []
    for pat, value, want in _COURT_COMPILED:
        for m in pat.finditer(text):
            end, attrs = m.end(), {}
            sec = _section_after(text, m.end())
            if sec:
                attrs["section"] = sec
            # Cassazione sections use the chamber "<n>CIV/PEN" / "UNITE" form (item 3): the
            # match itself may be "Sezioni Unite"/"SS.UU.", else parse what follows the keyword.
            if value == "CORTE_CASS":
                mtext = text[m.start():m.end()]
                cs = ("UNITE" if re.search(r"sezioni\s+unite|\bss\.?\s?uu", mtext, I)
                      else _cass_section(text, m.end()))
                if cs:
                    attrs["section"] = cs
                else:
                    attrs.pop("section", None)
            if want == "cgt":
                value, geo_attrs, end = _cgt_resolve(text, m.end())
                attrs.update(geo_attrs)
            elif want:
                kind, code, new_end = _geo_after(text, m.end(), want)
                if want == "region" and kind == "region":
                    attrs["region"] = code; end = new_end
                elif want == "city" and kind == "city":
                    attrs["city"] = code; end = new_end
                elif want == "either":
                    if kind == "region":
                        value, attrs["region"], end = "COMM_TRIBUT_REG", code, new_end
                    elif kind == "city":
                        value, attrs["city"], end = "COMM_TRIBUT_PROV", code, new_end
                    else:
                        value = "COMM_TRIBUT_PROV"
            spans.append(Span(m.start(), end, Entity.AUTHORITY, value,
                              text[m.start():end], attrs))
    for pat, value in _OTHER_AUTH_COMPILED:
        for m in pat.finditer(text):
            spans.append(Span(m.start(), m.end(), Entity.OTHER_AUTH, value, m.group(0)))
    return _nonoverlap(spans)


# Legislative aliases live in aliases.py (data + recognition + urn resolution).
from .aliases import EU_ALIASES, INTL_ALIASES, recognize_aliases as _recognize_aliases  # noqa: E402,F401
from .conventions import recognize_conventions  # noqa: E402
from .budget_laws import recognize_budget_laws  # noqa: E402
from .geo import REGION_NAME_TO_CODE, region_urn as _region_urn  # noqa: E402


def recognize_aliases(text: str) -> List[Span]:
    return _recognize_aliases(text, _nonoverlap)


# --- regional laws ("l. reg. Campania", "legge regionale Lombardia", "L.R. Veneto") ---------
# "reg\b" (abbreviation) is kept distinct from "regola"/"regolamento"/"registro". "L.R." /
# "l.r." is the most common abbreviation (legge regionale).
_LREG_MARKER = re.compile(
    r"\bl(?:egge)?\.?\s*(?:della\s+)?(?:regional[ei]|region[ei]|reg\b)\.?"
    r"|\bl\.?\s?r\.?(?!\w)", I)
_REGION_NAMES_RE = re.compile(
    r"^[\s,.:]*(?:della\s+|regione\s+)?(" +
    "|".join(sorted((re.escape(k) for k in REGION_NAME_TO_CODE), key=len, reverse=True)) +
    r")\b", I)
# the region may instead appear shortly after, in a "(Regione Lombardia)" tail, or simply
# trailing the number ("L.R. n. 2/1971 Toscana") — search for a bare region name in a window.
_REGION_ALT = "|".join(sorted((re.escape(k) for k in REGION_NAME_TO_CODE), key=len, reverse=True))
_REGION_PAREN_RE = re.compile(r"\(?\s*regione\s+(" + _REGION_ALT + r")\b", I)
_REGION_SEARCH_RE = re.compile(r"\b(" + _REGION_ALT + r")\b", I)


def recognize_regional_laws(text: str) -> List[Span]:
    """A regional-law marker -> a DOCTYPE L tagged ``scope=regionale`` with the region's urn
    segment (from a region name right after the marker, or a nearby "(Regione X)" tail, else
    empty, to be filled from the engine's ``default_region``)."""
    spans = []
    for m in _LREG_MARKER.finditer(text):
        end, ru = m.end(), ""
        rm = _REGION_NAMES_RE.match(text[m.end():])
        if rm:
            ru = _region_urn(rm.group(1)) or ""
            end = m.end() + rm.end()
        else:
            win = text[m.end():m.end() + 45].replace("-", " ")    # tolerate "Emilia-Romagna"
            pm = _REGION_PAREN_RE.search(win) or _REGION_SEARCH_RE.search(win)  # "(Regione X)" / trailing "X"
            if pm:
                ru = _region_urn(pm.group(1)) or ""
        spans.append(Span(m.start(), end, Entity.DOCTYPE, "L", text[m.start():end],
                          {"scope": "regionale", "region_urn": ru}))
    return spans


# The ordered pipeline of recognizers.
RECOGNIZERS: List[tuple] = [
    ("dates", recognize_dates),
    ("partitions", recognize_partitions),
    ("numbers", recognize_numbers),
    ("doctypes", recognize_doctypes),
    ("eu_acronyms", recognize_eu_acronyms),
    ("authorities", recognize_authorities),
    ("aliases", recognize_aliases),
    ("conventions", recognize_conventions),
    ("budget_laws", recognize_budget_laws),
    ("regional_laws", recognize_regional_laws),
]
