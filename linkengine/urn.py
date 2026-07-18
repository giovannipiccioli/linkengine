"""
URN generation and rendering for linkengine.

* ``build_urn(row)``    — from a feature row produce the final identifier
  (``urn:nir:...`` / ``ECLI:IT:...`` / ``CELEX:...`` / ``PRAX:AE:...``). Row-based: it needs only
  the fields linkengine produces (no DataFrame, no ``filename`` / ``original_text``). This is the
  single implementation of the URN layer.
* ``urn_to_text(urn)`` — the inverse: a standardized human-readable citation from a URN **alone**
  (``ECLI:IT:CASS:2020:1234CIV`` -> "Cassazione civile n. 1234/2020").

Reference data (courts, doctypes, regions, provinces, aliases) is centralized in ``catalog.py``
and ``geo.py``.
"""
from __future__ import annotations

import re
import unicodedata

from . import catalog
from .geo import (AUTONOMOUS_TAX_CITY_TO_GEO, AUTONOMOUS_TAX_GEO_NAMES, city_name,
                  region_name)
from .normalize import (build_nir, build_regional_nir, build_celex, build_celex_caselaw,
                        normattiva_url, partition_to_locator)
from .aliases import ALIAS_NIR, ALIAS_CELEX, alias_nir

_CASE_ID_RE = re.compile(r"([ct])\D*(\d+)\s*/\s*(\d{4})", re.I)


def _norm_prax_label(value) -> str:
    text = unicodedata.normalize("NFKD", _g_value(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _g_value(value) -> str:
    if value is None or value != value:
        return ""
    return value if isinstance(value, str) else str(value)


_PRAX_AUTHORITY_ALIASES = {
    "Min. Finanze": "MEF", "M.E.F.": "MEF", "MEF": "MEF",
    "Agenzia delle Entrate": "AE", "Agenzia Entrate": "AE", "AG_ENTRATE": "AE",
    "Agenzia delle Dogane": "ADOG", "AG_DOGANE": "ADOG",
    "Agenzia delle Dogane e dei Monopoli": "ADM", "AG_DOGANE_MONOPOLI": "ADM",
    "Min. Economia e Finanze": "MEF", "Agenzia del Territorio": "ATER",
    "Dipartimento delle Finanze": "DIF", "Presidenza Consiglio dei Ministri": "PCM",
    "Dipartimento Politiche Fiscali": "DPF", "Min. Tesoro": "TES",
    "Ministero della Funzione Pubblica": "MFP", "Ministero Sviluppo Economico": "MSE",
    "Min. Attività Produttive": "MAP", "Min. Industria": "MIND",
    "Min. Giustizia": "MGIU", "Min. Agricoltura": "MAGR", "Rag. Gen. Stato": "RGS",
    "Banca d'Italia": "BI", "INPS": "INPS", "Monopoli": "AMON",
    "Cassa Depositi e Prestiti": "CDP", "Min. Comm. Estero": "MCEST",
    "Min. Trasporti": "MTRA", "ARAN": "ARAN", "Min. Interni": "MINT",
    "Motoriz. Civile": "AMTRC", "Agenzia per l'Italia digitale": "AGID",
    "Min. Sanità": "MSAL", "Garante Protezione Dati Personali": "GPDP",
    "Min. Difesa": "MDIF", "Min. Lavoro": "MLAV",
    "Min. Infrastrutture e Trasporti": "MINF",
    "MEFDF": "MEFDF",
}
PRAX_AUTHORITY_CODES = {
    _norm_prax_label(alias): code for alias, code in _PRAX_AUTHORITY_ALIASES.items()
}
PRAX_AUTHORITY_CODES.update({code.casefold(): code for code in set(PRAX_AUTHORITY_CODES.values())})
PRAX_AUTHORITY_NAMES = {
    "MEF": "Ministero dell'Economia e delle Finanze",
    "AE": "Agenzia delle Entrate",
    "ADOG": "Agenzia delle Dogane",
    "ADM": "Agenzia delle Dogane e dei Monopoli",
    "ATER": "Agenzia del Territorio",
    "DIF": "Dipartimento delle Finanze",
    "PCM": "Presidenza del Consiglio dei Ministri",
    "DPF": "Dipartimento delle Politiche Fiscali",
    "TES": "Ministero del Tesoro",
    "MFP": "Ministero della Funzione Pubblica",
    "MSE": "Ministero dello Sviluppo Economico",
    "MAP": "Ministero delle Attività Produttive",
    "MIND": "Ministero dell'Industria",
    "MGIU": "Ministero della Giustizia",
    "MAGR": "Ministero dell'Agricoltura",
    "RGS": "Ragioneria Generale dello Stato",
    "BI": "Banca d'Italia",
    "INPS": "INPS",
    "AMON": "Monopoli",
    "CDP": "Cassa Depositi e Prestiti",
    "MCEST": "Ministero del Commercio Estero",
    "MTRA": "Ministero dei Trasporti",
    "ARAN": "ARAN",
    "MINT": "Ministero dell'Interno",
    "AMTRC": "Motorizzazione Civile",
    "AGID": "Agenzia per l'Italia digitale",
    "MSAL": "Ministero della Sanità",
    "GPDP": "Garante per la protezione dei dati personali",
    "MDIF": "Ministero della Difesa",
    "MLAV": "Ministero del Lavoro",
    "MINF": "Ministero delle Infrastrutture e dei Trasporti",
    "MEFDF": "Dipartimento delle Finanze - MEF",
}

_PRAX_TYPE_ALIASES = {
    "risoluzione": "RIS", "circolare": "CIRC", "comunicato stampa": "CS",
    "interpello": "INT", "risposta": "INT", "telegramma": "TEL",
    "lettera circolare": "LCIRC", "delibera": "DEL", "nota": "NOTA",
    "direttiva": "DIR", "provvedimento": "PROVV", "parere": "PAR",
    "RIS": "RIS", "CIRC": "CIRC", "CS": "CS", "INTERPELLO": "INT",
    "INT": "INT", "TEL": "TEL", "LCIRC": "LCIRC", "DEL": "DEL",
    "NOTA": "NOTA", "DIR": "DIR", "PROVV": "PROVV", "PARERE": "PAR", "PAR": "PAR",
}
PRAX_TYPE_CODES = {_norm_prax_label(alias): code for alias, code in _PRAX_TYPE_ALIASES.items()}
_PRAX_DATE_TYPES = {"CS", "TEL", "LCIRC"}
PRAX_TYPE_NAMES = {
    "RIS": "risoluzione",
    "CIRC": "circolare",
    "CS": "comunicato stampa",
    "INT": "interpello",
    "TEL": "telegramma",
    "LCIRC": "lettera circolare",
    "DEL": "delibera",
    "NOTA": "nota",
    "DIR": "direttiva",
    "PROVV": "provvedimento",
    "PAR": "parere",
}


def _prax_date(value):
    """Return (year, YYYYMMDD), accepting ISO dates, CERDEF DD_MM_YYYY, or a bare year."""
    text = _g_value(value).strip()
    full = re.fullmatch(r"(\d{4})[-_/](\d{2})[-_/](\d{2})", text)
    if full:
        return full.group(1), "".join(full.groups())
    full = re.fullmatch(r"(\d{2})[-_/](\d{2})[-_/](\d{4})", text)
    if full:
        return full.group(3), full.group(3) + full.group(2) + full.group(1)
    year = re.fullmatch(r"(\d{4})", text)
    return (year.group(1), "") if year else ("", "")


def generate_prax_urn(authority, document_type, date, number=None) -> str:
    """Build a PRAX identifier from CERDEF-style authority/type/date/number metadata."""
    authority_code = PRAX_AUTHORITY_CODES.get(_norm_prax_label(authority), "")
    type_code = PRAX_TYPE_CODES.get(_norm_prax_label(document_type), "")
    year, compact_date = _prax_date(date)
    if not (authority_code and type_code and year and 1920 <= int(year) <= 2027):
        return ""
    if type_code in _PRAX_DATE_TYPES:
        return f"PRAX:{authority_code}:{type_code}:{compact_date}" if compact_date else ""

    number_text = _g_value(number).strip()
    if number_text.endswith(".0") and number_text[:-2].isdigit():
        number_text = number_text[:-2]
    if not number_text:
        return ""
    if authority_code == "AE" and type_code == "CIRC":
        number_text = re.sub(r"/E$", "", number_text, flags=re.I)
    elif authority_code == "MEFDF" and type_code == "CIRC":
        number_text = re.sub(r"/DF$", "", number_text, flags=re.I)
    numeric_head = number_text.split("/", 1)[0]
    if not numeric_head.isdigit() or int(numeric_head) > 10**18:
        return ""
    return f"PRAX:{authority_code}:{type_code}:{year}:{number_text}"


# ── small field helpers ───────────────────────────────────────────────────────
def _g(row, key):
    """A feature field as a clean string ('' for missing/None/NaN); dict or pandas Series."""
    try:
        v = row[key]
    except (KeyError, IndexError):
        return ''
    if v is None:
        return ''
    if v != v:                       # NaN
        return ''
    return v if isinstance(v, str) else str(v)


def _is_number(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _int(row, key):
    s = _g(row, key)
    return int(round(float(s))) if s and _is_number(s) else None


def _ns(row, key):
    """A number/year field as a clean digit string ("546.0" -> "546"), or ''."""
    s = _g(row, key)
    return s[:-2] if s.endswith('.0') and s[:-2].lstrip('-').isdigit() else s


def _year_only(urn):
    """Trim a full ``yyyy-mm-dd`` promulgation date in a urn:nir to its year (the identifier
    uses the year only): aliases carry the full date in their fixed base, e.g.
    ``urn:nir:stato:regio.decreto:1942-03-16;262:2`` -> ``...:1942;262:2``."""
    if not urn or not urn.startswith("urn:nir:"):
        return urn
    date_part = urn.split('~')[0].split(';')[0].split(':')[-1]
    return urn.replace(date_part, date_part[:4]) if len(date_part) == 10 else urn


# ── number/year recovery for case law ─────────────────────────────────────────
def _num_sez_year(text, min_year=1940, max_year=2030):
    """Parse ``n. number/section/year`` (the case-law docket form), or None."""
    m = re.search(r'\b(\d+)\s*/\s*(\d+)\s*/\s*(\d{2,4})\b', text or '')
    if not m:
        return None
    num, sez, yr = int(m.group(1)), m.group(2), int(m.group(3))
    if yr < 100:
        yr += 2000 if yr <= 30 else 1900
    if num <= 31 or not (min_year <= yr <= max_year):
        return None
    return num, yr


_GIP_GUP = re.compile(r'\bG\.?\s*(?:I|U)\.?\s*P\.?\b\s*(?:del\s+)?tr', re.IGNORECASE)
_TAX_CITY_CODE_FIXUP = {"G479": "PU", "D704": "FC", "F023": "MS", "B832": "MS", "L746": "VB"}
_TWO_LETTER_GEO = catalog.FIRST_GRADE_TAX_AUTHORITIES | {"CORTE_APPELLO"}
_DATE_ONLY_DECREE_PREFIX = {
    ("DECR", "MINISTERO"): "DM",
    ("DECR", "PRES_CONS_MIN"): "DPCM",
}


# ══════════════════════════════════════════════════════════════════════════════
# build_urn: feature row -> identifier
# ══════════════════════════════════════════════════════════════════════════════
def compat_url(urn: str) -> str:
    """The legacy Normattiva ``url`` derived *from* a national/regional ``urn:nir`` identifier
    (empty for ECLI / CELEX / PRAX, whose identifier already lives in the ``urn`` column)."""
    return normattiva_url(urn) if urn.startswith("urn:nir:") else ""


def build_urn(row) -> str:
    """The final identifier for one feature row, or '' if none is derivable. Dispatches on the
    engine-native ``ref-type`` (legislation/caselaw/prassi) or an optional caller-provided
    ``reference_type`` (norm/jur/prassi_amm/other)."""
    rtype = _g(row, 'reference_type') or _g(row, 'ref-type')
    if rtype in ('caselaw', 'jur'):
        return _caselaw_urn(row) or ''
    if rtype in ('prassi', 'prassi_amm'):
        return _prassi_urn(row) or ''
    if rtype in ('other', 'other acts') or _g(row, 'doc-type') == 'DEL':
        return _other_urn(row) or ''
    return _year_only(_legislation_urn(row) or '')


def _legislation_urn(row):
    """National / regional / EU / international legislation — built directly from the recognized
    fields (no url roundtrip): an alias code, else a doctype+authority+number+year act."""
    scope = _g(row, 'ref-scope')
    alias = _g(row, 'alias')
    part = _g(row, 'partition')
    if scope == 'regionale':
        return build_regional_nir(_g(row, 'region'), _ns(row, 'number'), _ns(row, 'year'), part)
    if scope == 'comunitario':
        return _eu_urn(row)
    if scope == 'internazionale':
        if alias == 'CONV_EU_DIR_UOMO':
            loc = partition_to_locator(part, ('comma',))
            return "CONV_EU_DIR_UOMO" + (f"~{loc}" if loc else "")
        return None
    # nazionale
    if alias in ALIAS_NIR:
        return alias_nir(alias, part)
    nir = build_nir(_g(row, 'doc-type'), _g(row, 'authority'), _ns(row, 'number'),
                    _ns(row, 'year'), part, ministry=_g(row, 'ministry'))
    if nir:
        return nir
    date_only_prefix = _DATE_ONLY_DECREE_PREFIX.get(
        (_g(row, 'doc-type'), _g(row, 'authority')))
    if date_only_prefix and _g(row, 'doc-date'):
        loc = partition_to_locator(part)
        return f"{date_only_prefix}{_g(row, 'doc-date')}" + (f"~{loc}" if loc else "")
    # last-resort named EU acts recognized only by their text ("nomenclatura combinata"
    # is not here: it has its own token-URN alias, NOMENCLATURA_COMBINATA)
    t = _g(row, 'text').lower()
    if 'tariffa doganale comune' in t:
        return "CELEX:31987R2658"
    if 'codice doganale comunitario' in t:
        return "CELEX:31992R2913"
    if 'codice doganale dell’unione' in t or "codice doganale dell'unione" in t:
        return "CELEX:32013R952"
    return None


def _eu_urn(row):
    """EU act CELEX: an alias with a known CELEX (ALIAS_CELEX), else built from doc-type +
    number/year, plus the partition locator."""
    if _g(row, 'alias') == 'TARIFFA_DOGANALE_COM':   # special: URN is the alias token itself
        loc = partition_to_locator(_g(row, 'partition'))
        return "TARIFFA_DOGANALE_COM" + (f"~{loc}" if loc else "")
    if _g(row, 'alias') == 'NOMENCLATURA_COMBINATA':
        # same token-URN scheme, but never with a locator: the CN is cited by
        # voci/note/sezioni/capitoli, which are not URN-able partitions.
        return "NOMENCLATURA_COMBINATA"
    year = _ns(row, 'year') or (_g(row, 'doc-date').split('-')[0] if _g(row, 'doc-date') else '')
    celex = (ALIAS_CELEX.get(_g(row, 'alias'))
             or build_celex(_g(row, 'doc-type'), _ns(row, 'number'), year,
                            acronym=_g(row, 'eu-acronym')))
    if not celex:
        return None
    loc = partition_to_locator(_g(row, 'partition'), ('comma',))
    return celex + (f"~{loc}" if loc else "")


def _caselaw_urn(row):
    """Case law: a CJEU judgment cited by case id -> sector-6 CELEX; otherwise an ECLI built
    from authority + geo + number/year (recovered from doc-date/full-number/text when absent)."""
    case = _g(row, 'case-number')
    if case:
        m = _CASE_ID_RE.search(case)
        if m:
            celex = build_celex_caselaw(m.group(1), m.group(2), m.group(3))
            if celex:
                loc = partition_to_locator(_g(row, 'partition'), ('punto', 'comma'))
                return celex + (f"~{loc}" if loc else "")
    number, year = _int(row, 'number'), _int(row, 'year')
    if not year and _g(row, 'doc-date'):
        m = re.fullmatch(r'(\d{4})-\d{2}-\d{2}', _g(row, 'doc-date'))
        if m:
            year = int(m.group(1))
    if not (number and year):
        for src in ('full-number', 'text'):
            res = _num_sez_year(_g(row, src))
            if res:
                number, year = res
                break
    if not (number and year):
        return None
    if _g(row, 'authority') == "CORTE_COST":
        return f"ECLI:IT:COST:{year}:{number}"
    # Corte EDU: the case identifier is the Strasbourg *application* number ("ricorso
    # n. 33804/96" -> CEDU:1996:33804). Only a number introduced by "ricorso" is that pair;
    # a bare "Corte EDU n. 123/2020" is a judgment number and stays unresolved rather than
    # being mislabelled as an application.
    if _g(row, 'authority') == "CEDU":
        if 'ricorso' not in _g(row, 'text').lower():
            return None
        return f"CEDU:{year}:{number}"
    # CGUE with the authority clearly stated but no "C-"/"causa": a bare "n. 123/2020" (or
    # "77/72") IS the case number -> sector-6 CELEX (default kind: Court of Justice).
    if _g(row, 'authority') == "CGUE":
        celex = build_celex_caselaw('C', str(number), str(year))
        if not celex:
            return None
        loc = partition_to_locator(_g(row, 'partition'), ('punto', 'comma'))
        return celex + (f"~{loc}" if loc else "")
    return _court_ecli(row, year, number)


def _court_ecli(row, year, number):
    info = catalog.COURTS.get(_g(row, 'authority'))
    if not info or not info["ecli"]:
        return None
    prefix, geo_kind = info["ecli"], info["geo"]
    geo = ""
    if geo_kind:
        val = _g(row, geo_kind)
        if not val:
            if _g(row, 'authority') == "COMM_TRIBUT_CEN":
                return f"ECLI:IT:CTCIT:{year}:{number}"
            return None
        if _g(row, 'authority') in catalog.SECOND_GRADE_TAX_AUTHORITIES and val == "TAA":
            return None
        if _g(row, 'authority') in catalog.FIRST_GRADE_TAX_AUTHORITIES:
            val = _TAX_CITY_CODE_FIXUP.get(val, val)
            # Trento/Bolzano first-grade tax courts: map the cadastral city code to the
            # BZ/TN province component (the second-grade path does this at line ~509).
            val = AUTONOMOUS_TAX_CITY_TO_GEO.get(val, val)
        if _g(row, 'authority') in _TWO_LETTER_GEO and len(val) > 2:
            return None
        geo = val
    suffix = "CIV" if _g(row, 'authority') == "CORTE_CASS" else ""
    return f"ECLI:IT:{prefix}{geo}:{year}:{number}{suffix}"


def _prassi_urn(row):
    date = _g(row, 'doc-date') or _ns(row, 'year')
    year = _int(row, 'year') or (int(date.split('-')[0]) if date else None)
    full = _g(row, 'full-number')
    if full:
        number = full
        if year and str(year) in number:
            number = number.replace(str(year), '').rstrip('/')
    else:
        number = _ns(row, 'number')
    return generate_prax_urn(
        _g(row, 'other-authority'), _g(row, 'doc-type'), date or str(year or ""), number
    ) or None


def _other_urn(row):
    if _g(row, 'authority') == "COMUNE" and _g(row, 'city') and _int(row, 'year') and _int(row, 'number'):
        urn = f"DEL:CO{_g(row, 'city')}:{_int(row, 'year')}:{_int(row, 'number')}"
        locator = partition_to_locator(_g(row, 'partition'))
        return urn + (f"~{locator}" if locator else "")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# urn_to_text: identifier -> human-readable citation (URN alone, no other input)
# ══════════════════════════════════════════════════════════════════════════════
_LOC_LABEL = {"art": "art.", "comma": "comma", "let": "let.", "num": "num.",
              "all": "allegato", "allegato": "allegato"}
# longest first so "comma"/"allegato" win over a bare prefix scan
_LOC_PREFIX_RE = re.compile(r'^(allegato|comma|art|let|num|all)(.*)$')


def _render_locator(locator: str, num_label: str = "num.") -> str:
    """``art14-comma4-letb-num1`` -> ``art. 14 comma 4 let. b num. 1``. ``num_label`` overrides
    the rendering of the ``num`` segment (CJEU judgments render it as "punto")."""
    parts = []
    for seg in locator.split('-'):
        m = _LOC_PREFIX_RE.match(seg)
        if not m:
            parts.append(seg)
            continue
        label = num_label if m.group(1) == "num" else _LOC_LABEL[m.group(1)]
        parts.append(f"{label} {m.group(2)}".strip())
    return " ".join(parts)


def urn_to_text(urn: str) -> str:
    """A standardized human-readable citation from a URN alone, e.g.
    ``ECLI:IT:CASS:2020:1234CIV`` -> "Cassazione civile n. 1234/2020";
    ``urn:nir:stato:legge:2010;200~art14-comma4-letb`` -> "art. 14 comma 4 let. b legge n. 200/2010".
    Returns '' for an empty/unrecognized identifier."""
    if not urn:
        return ''
    urn = urn.strip()
    if urn.startswith("ECLI:IT:"):
        return _ecli_to_text(urn[len("ECLI:IT:"):])
    if urn.startswith("urn:nir:"):
        return _nir_to_text(urn[len("urn:nir:"):])
    if urn.startswith("CELEX:"):
        return _celex_to_text(urn[len("CELEX:"):])
    if urn.startswith("PRAX:"):
        return _prax_to_text(urn[len("PRAX:"):])
    if urn.startswith("DEL:CO"):
        return _local_delibera_to_text(urn)
    if urn.startswith("CONV_EU_DIR_UOMO"):
        _, loc = _split_locator(urn)
        return f"{loc + ' ' if loc else ''}CEDU".strip()
    m = re.fullmatch(r'CEDU:(\d{4}):(\d+)', urn)
    if m:
        return f"Corte EDU, ricorso n. {m.group(2)}/{m.group(1)[2:]}"
    if urn.startswith("TARIFFA_DOGANALE_COM"):
        _, loc = _split_locator(urn)
        return f"{loc + ' ' if loc else ''}tariffa doganale comune".strip()
    if urn == "NOMENCLATURA_COMBINATA":
        return "nomenclatura combinata"
    m = re.match(r'(DPCM|DM)(\d{4})-(\d{2})-(\d{2})(?:~(.*))?$', urn)
    if m:
        decree_name = {
            "DM": "decreto ministeriale",
            "DPCM": "D.P.C.M.",
        }[m.group(1)]
        loc = _render_locator(m.group(5)) if m.group(5) else ""
        date = f"{m.group(4)}/{m.group(3)}/{m.group(2)}"
        return f"{loc + ' ' if loc else ''}{decree_name} del {date}".strip()
    return urn


def _split_locator(body):
    """Split an identifier body on the first '~' into (base, rendered locator text)."""
    if '~' not in body:
        return body, ''
    base, loc = body.split('~', 1)
    return base, _render_locator(loc)


def _ecli_to_text(body):
    # body: "CASS:2020:1234CIV" | "CGT2LAZ:2024:100" | "COST:2018:188"
    parts = body.split(':')
    if len(parts) < 3:
        return "ECLI:IT:" + body
    court_geo, year, number = parts[0], parts[1], parts[2]
    if court_geo.startswith("COST"):
        return f"Corte Costituzionale n. {number}/{year}"
    suffix = ""
    if number.endswith("CIV"):
        number, suffix = number[:-3], " civile"
    elif number.endswith("PEN"):
        number, suffix = number[:-3], " penale"
    for prefix in catalog.ECLI_PREFIXES:
        if court_geo.startswith(prefix):
            name, geo_kind = catalog.ECLI_PREFIX_TO_COURT[prefix]
            geo_code = court_geo[len(prefix):]
            place = ""
            if geo_code and geo_code != "IT":
                if prefix in {"CTR", "CGT2"} and geo_code in AUTONOMOUS_TAX_GEO_NAMES:
                    place = f" di {AUTONOMOUS_TAX_GEO_NAMES[geo_code]}"
                elif geo_kind == "region":
                    place = f" {region_name(geo_code)}"
                elif geo_kind == "city":
                    place = f" di {city_name(geo_code)}"
            return f"{name}{suffix}{place} n. {number}/{year}"
    return f"{court_geo} n. {number}/{year}"


def _nir_to_text(body):
    base, loc = _split_locator(body)
    # base: "authority:doctype:year;number[:annex]"  or alias bases / costituzione / regione.*
    alias_name = catalog.ALIAS_BASE_TO_NAME.get(base)
    if alias_name:
        return f"{loc + ' ' if loc else ''}{alias_name}".strip()
    m = re.match(r'(.+?):(\d{4});(\d+)', base)
    if not m:
        # costituzione / treaties without number
        if base.startswith("stato:costituzione"):
            return f"{loc + ' ' if loc else ''}Costituzione".strip()
        return base
    auth_doc, year, number = m.group(1), m.group(2), m.group(3)
    if auth_doc.startswith("regione."):
        region = auth_doc[len("regione."):].split(':')[0]
        doc = f"legge regionale {region_name(region)}"
    else:
        doc = catalog.URN_DOCTYPE_NAME.get(auth_doc, auth_doc.split(':')[-1].replace('.', ' '))
    head = f"{loc} " if loc else ""
    return f"{head}{doc} n. {number}/{year}".strip()


def _celex_to_text(body):
    base, rawloc = body.split('~', 1) if '~' in body else (body, '')
    # sector 6: case law (e.g. 62020CJ0123 -> causa C-123/2020 ; ...TJ... -> T-)
    m = re.match(r'6(\d{4})(CJ|TJ|CO|TO)(\d+)', base)
    if m:
        year, court, num = m.group(1), m.group(2), int(m.group(3))
        letter = "T" if court.startswith("T") else "C"
        loc = _render_locator(rawloc, num_label="punto") if rawloc else ""   # CJEU: ~num -> "punto"
        return f"{loc + ' ' if loc else ''}causa {letter}-{num}/{year}".strip()
    loc = _render_locator(rawloc) if rawloc else ""
    head = f"{loc} " if loc else ""
    # sectors 3 (legislation) and 1 (treaties)
    m = re.match(r'3(\d{4})([RLDHS])(\d+)', base)
    if m:
        year, letter, num = m.group(1), m.group(2), int(m.group(3))
        if letter == "S":   # ECSC general decisions are cited number-first with /CECA
            return f"{head}decisione n. {num}/{year}/CECA".strip()
        doc = catalog.CELEX_DOCTYPE_NAME.get(letter, "atto")
        return f"{head}{doc} {year}/{num}/CE".strip()
    treaties = {"12012E/TXT": "TFUE", "12016ME/TXT": "TUE", "11957E/TXT": "Trattato CEE",
                "12002E/TXT": "Trattato CE", "11951K": "Trattato CECA",
                "12012P/TXT": "Carta dei diritti fondamentali UE"}
    if base in treaties:
        return f"{head}{treaties[base]}".strip()
    return f"{head}{base}".strip()


def _prax_to_text(body):
    # body: "AE:CIRC:2005:47" | "MEF:TEL:19911203"
    parts = body.split(':')
    if len(parts) < 3:
        return "PRAX:" + body
    authority, kind = parts[0], parts[1]
    authority_name = PRAX_AUTHORITY_NAMES.get(authority, authority)
    kind_name = PRAX_TYPE_NAMES.get(kind, kind)
    if kind in _PRAX_DATE_TYPES and re.fullmatch(r"\d{8}", parts[2]):
        date = parts[2]
        return f"{kind_name} {authority_name} del {date[6:8]}/{date[4:6]}/{date[:4]}"
    if len(parts) < 4:
        return "PRAX:" + body
    return f"{kind_name} {authority_name} n. {parts[3]}/{parts[2]}"


def _local_delibera_to_text(urn):
    base, raw_locator = urn.split("~", 1) if "~" in urn else (urn, "")
    match = re.fullmatch(r"DEL:CO([^:]+):(\d{4}):(\d+)", base)
    if not match:
        return urn
    place = city_name(match.group(1))
    issuer = f"Comune di {place}" if place else f"Comune {match.group(1)}"
    locator = _render_locator(raw_locator) if raw_locator else ""
    head = f"{locator} " if locator else ""
    return f"{head}delibera del {issuer} n. {match.group(3)}/{match.group(2)}"
