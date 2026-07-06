"""
Normalization + identifier construction for linkengine.

The key responsibility: build the URN-NIR for national/regional legislation (``build_nir`` /
``build_regional_nir``) and the CELEX for EU acts (``build_celex`` / ``build_celex_caselaw``),
directly from the recognized doc-type / authority / number / year fields. The URN layer
(``urn.build_urn``) calls these to populate the canonical ``urn`` column.

The (doc-type, authority) -> (urn authority, urn doctype) table and the partition->locator
transform are verified against the hand-checked gold URNs.
"""
from __future__ import annotations

import datetime as _datetime
import re
from typing import Optional, Tuple

NORMATTIVA_PREFIX = "http://www.normattiva.it/uri-res/N2Ls?"

# (doc-type code, authority code) -> (urn authority, urn doctype).
# authority "" means "any / unspecified". URN forms use dotted doctypes, with DPR mapped
# to presidente.repubblica:decreto.
EMANANTE_TIPO = {
    ("L", ""):            ("stato", "legge"),
    ("LC", ""):           ("stato", "legge.costituzionale"),
    ("DL", ""):           ("stato", "decreto.legge"),
    ("DLGS", ""):         ("stato", "decreto.legislativo"),
    ("DECR", "PRES_REP"): ("presidente.repubblica", "decreto"),
    ("DECR", "PRES_CONS_MIN"): ("presidente.consiglio.ministri", "decreto"),  # numbered DPCM
    ("DECR", "MINISTERO"): ("ministero", "decreto"),   # numbered D.M. (date-only -> DM{date})
    ("RD", ""):           ("stato", "regio.decreto"),
    # historical 1944–48 acts: luogotenenziali / del Capo Provvisorio dello Stato
    ("DLGS_LGT", ""):     ("luogotenente", "decreto.legislativo"),
    ("DL_LGT", ""):       ("luogotenente", "decreto.legge"),
    ("DLGS_CPS", ""):     ("capo.provvisorio.stato", "decreto.legislativo"),
    ("DL_CPS", ""):       ("capo.provvisorio.stato", "decreto.legge"),
    # a bare "regolamento N/YYYY" (no EU acronym) defaults to a *national* regolamento
    # (urn:nir:stato:regolamento). With "(UE)/(CE)" it goes EU (CELEX).
    ("REG", ""):          ("stato", "regolamento"),
}
MINISTRY_NIR = {"ECONOMIA_FINANZE": "ministero.economia.finanze"}

# doc-types whose default scope is EU and the CELEX provision letter.
EU_PROV_LETTER = {"REG": "R", "DIR": "L", "DECIS": "D", "RACC": "H"}

# Alias -> urn:nir resolution lives in aliases.py (alias_nir).


_ROMAN_VAL = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman_to_int_token(s: str) -> str:
    s = (s or "").lower()
    if not s or any(ch not in _ROMAN_VAL for ch in s):
        return s
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VAL[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return str(total)


def partition_to_locator(partition_field: str, extra_num=()) -> str:
    """The partition-field -> URN-locator transform (the single implementation).

    ``"articolo-43_comma-1"`` -> ``"art43-comma1"``; ``"allegato-iv"`` -> ``"all4"``.
    ``articolo``->``art``, ``lettera``->``let``, ``numero``/``paragrafo``->``num`` always;
    names in ``extra_num`` (``comma`` for EU acts, ``punto`` for CJEU) collapse to ``num`` too.
    """
    if not partition_field:
        return ""
    partition_field = re.sub(
        r"allegato-([ivxlcdm]+)",
        lambda m: "allegato-" + _roman_to_int_token(m.group(1)),
        partition_field,
        flags=re.IGNORECASE)
    s = (partition_field
         .replace("articolo", "art").replace("lettera", "let")
         .replace("considerando", "cons")
         .replace("allegato", "all")
         .replace("numero", "num").replace("paragrafo", "num"))
    for name in extra_num:
        s = s.replace(name, "num")
    return s.replace("-", "").replace("_", "-")


def split_annex(partition_field: str):
    """An ``allegato`` (attachment) is an annex marker on the act number (``;50:a``), not a
    ``~`` locator. Return (annex, rest_field) where rest_field has the allegato removed."""
    if not partition_field or "allegato-" not in partition_field:
        return "", partition_field
    parts = [p for p in partition_field.split("_") if p]
    annex, rest = "", []
    for p in parts:
        if p.startswith("allegato-"):
            annex = p[len("allegato-"):]
        else:
            rest.append(p)
    return annex, "_".join(rest)


def build_nir(doctype: str, authority: str, number: str, year: str,
              partition_field: str = "", ministry: str = "") -> Optional[str]:
    """Build a national urn:nir string, or None if the (doctype, authority) is unmapped or
    number/year are missing."""
    em = EMANANTE_TIPO.get((doctype, authority or "")) or EMANANTE_TIPO.get((doctype, ""))
    if not em or not number or not year:
        return None
    authority_urn, doctype_urn = em
    if authority == "MINISTERO" and ministry in MINISTRY_NIR:
        authority_urn = MINISTRY_NIR[ministry]
    annex, rest = split_annex(partition_field)
    urn = f"urn:nir:{authority_urn}:{doctype_urn}:{year};{number}"
    if annex:
        urn += ":" + annex
    loc = partition_to_locator(rest)
    if loc:
        urn += "~" + loc
    return urn


def build_regional_nir(region_urn: str, number: str, year: str,
                       partition_field: str = "") -> Optional[str]:
    """Build a regional law urn:nir, e.g. ``urn:nir:regione.campania:legge:2003;28~art13``."""
    if not region_urn or not number or not year:
        return None
    urn = f"urn:nir:regione.{region_urn}:legge:{year};{number}"
    loc = partition_to_locator(partition_field)
    if loc:
        urn += "~" + loc
    return urn


def normattiva_url(nir: str) -> str:
    return NORMATTIVA_PREFIX + nir


def build_celex(doctype: str, number: str, year: str) -> Optional[str]:
    """Build a CELEX id for an EU legislative act (sector 3), e.g. REG 1234/2020 ->
    ``CELEX:32020R1234``. The partition is NOT appended here — the URN layer appends it from
    the ``partition`` field, so doing it here too would double it."""
    letter = EU_PROV_LETTER.get(doctype)
    if not letter or not number or not year:
        return None
    try:
        num = int(round(float(number)))
    except (TypeError, ValueError):
        return None
    return f"CELEX:3{int(year)}{letter}{num:04d}"


def build_celex_caselaw(kind: str, number: str, year: str) -> Optional[str]:
    """CELEX for a CJEU judgment (sector 6) from a case id: ``C-334/20`` -> ``62020CJ0334``
    (``C`` = Court of Justice -> ``CJ``; ``T`` = General Court -> ``TJ``)."""
    if not number or not year:
        return None
    try:
        num = int(round(float(number)))
    except (TypeError, ValueError):
        return None
    court = "TJ" if (kind or "").upper() == "T" else "CJ"
    return f"CELEX:6{int(year)}{court}{num:04d}"


# plausible range for any cited year. 1861 = Italian unification (the oldest acts still cited,
# e.g. legge 2248/1865); 2030 is a small forward margin. A number outside this range is never
# accepted as a year — the single guard behind every date / number-year decision.
MIN_YEAR, MAX_YEAR = 1861, 2030
REGIO_DECRETO_MIN_YEAR, REGIO_DECRETO_MAX_YEAR = 1861, 1946


def norm_year(raw: str) -> str:
    """Normalize a 2- or 4-digit year string to 4 digits. A citation cannot postdate the
    current year, so a 2-digit year above the current one is 19xx (``r.d. 1611/33`` -> 1933,
    not 2033); at or below it is 20xx (``n. 12/24`` -> 2024)."""
    raw = (raw or "").strip()
    if re.fullmatch(r"\d{4}", raw):
        return raw
    if re.fullmatch(r"\d{2}", raw):
        n = int(raw)
        return ("20" if n <= _datetime.date.today().year % 100 else "19") + raw
    return raw


def valid_year(raw: str):
    """Return the normalized 4-digit year if ``raw`` (2- or 4-digit) is a plausible year in
    [MIN_YEAR, MAX_YEAR], else None. Use this everywhere a number might be a year."""
    y = norm_year(raw)
    return y if re.fullmatch(r"\d{4}", y) and MIN_YEAR <= int(y) <= MAX_YEAR else None


def year_for_doctype(doctype: str, year: str, raw_year: str = "") -> str:
    """Apply chronology that is intrinsic to a document type.

    A two-digit Regio Decreto year is resolved inside the only possible interval, 1861-1946:
    ``2440/23`` is therefore 1923, while ``639/10`` is 1910. An explicit impossible year is
    left unresolved rather than silently rewritten.
    """
    year = (year or "").strip()
    if doctype != "RD" or not year:
        return year
    raw_year = (raw_year or "").strip()
    if re.fullmatch(r"\d{2}", raw_year):
        suffix = int(raw_year)
        candidates = [century + suffix for century in (1800, 1900)]
        plausible = [candidate for candidate in candidates
                     if REGIO_DECRETO_MIN_YEAR <= candidate <= REGIO_DECRETO_MAX_YEAR]
        return str(plausible[0]) if len(plausible) == 1 else ""
    return year if year.isdigit() and \
        REGIO_DECRETO_MIN_YEAR <= int(year) <= REGIO_DECRETO_MAX_YEAR else ""


def valid_date(day: str, month: str, year: str):
    """Return the normalized 4-digit year if (day, month, year) is a real date (1<=dd<=31,
    1<=mm<=12, year in range), else None. Tolerates leading zeros."""
    try:
        d, m = int(day), int(month)
    except (TypeError, ValueError):
        return None
    y = valid_year(year)
    return y if y and 1 <= d <= 31 and 1 <= m <= 12 else None


def norm_latin_suffix(value: str) -> str:
    """``"2 ter"`` / ``"2-ter"`` -> ``"2-ter"``; ``"2"`` -> ``"2"``."""
    v = value.strip().lower().replace("\u00ad", "-").replace(" ", "-")
    return re.sub(r"-+", "-", v)
