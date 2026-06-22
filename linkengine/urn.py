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

from . import catalog
from .geo import city_name, region_name
from .normalize import (build_nir, build_regional_nir, build_celex, build_celex_caselaw,
                        normattiva_url)
from .aliases import ALIAS_NIR, ALIAS_CELEX, alias_nir

_CASE_ID_RE = re.compile(r"([ct])\D*(\d+)\s*/\s*(\d{4})", re.I)


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


def partition_to_locator(partition, extra_num=()):
    """linkengine partition field -> urn:nir / CELEX locator suffix. ``articolo``->``art``,
    ``lettera``->``let``, ``numero``/``paragrafo``->``num`` always; names in ``extra_num``
    (``comma`` for EU, ``punto`` for CJEU) collapse to ``num`` too."""
    if not partition:
        return ''
    s = (partition.replace('articolo', 'art').replace('lettera', 'let')
                  .replace('numero', 'num').replace('paragrafo', 'num'))
    for name in extra_num:
        s = s.replace(name, 'num')
    return s.replace('-', '').replace('_', '-')


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
_CTP_PROVINCE_FIXUP = {"G479": "PU", "D704": "FC", "F023": "MS", "B832": "MS", "L746": "VB"}
_TWO_LETTER_GEO = {"COMM_TRIBUT_PROV", "CORTE_GIUST_TRIBUT_PROV", "CORTE_APPELLO"}


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
    if rtype == 'other' or _g(row, 'doc-type') == 'DEL':
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
    nir = build_nir(_g(row, 'doc-type'), _g(row, 'authority'), _ns(row, 'number'), _ns(row, 'year'), part)
    if nir:
        return nir
    if _g(row, 'doc-type') == "DECR" and _g(row, 'authority') == "MINISTERO" and _g(row, 'doc-date'):
        loc = partition_to_locator(part)
        return f"DM{_g(row, 'doc-date')}" + (f"~{loc}" if loc else "")
    # last-resort named EU acts recognized only by their text
    t = _g(row, 'text').lower()
    if 'tariffa doganale comune' in t or 'nomenclatura combinata' in t:
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
    year = _ns(row, 'year') or (_g(row, 'doc-date').split('-')[0] if _g(row, 'doc-date') else '')
    celex = (ALIAS_CELEX.get(_g(row, 'alias'))
             or build_celex(_g(row, 'doc-type'), _ns(row, 'number'), year))
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
        if _g(row, 'authority') in ("COMM_TRIBUT_PROV", "CORTE_GIUST_TRIBUT_PROV"):
            val = _CTP_PROVINCE_FIXUP.get(val, val)
        if _g(row, 'authority') in _TWO_LETTER_GEO and len(val) > 2:
            return None
        geo = val
    suffix = "CIV" if _g(row, 'authority') == "CORTE_CASS" else ""
    return f"ECLI:IT:{prefix}{geo}:{year}:{number}{suffix}"


def _prassi_urn(row):
    if _g(row, 'other-authority') != "AG_ENTRATE":
        return None
    year = _int(row, 'year') or (int(_g(row, 'doc-date').split('-')[0]) if _g(row, 'doc-date') else None)
    full = _g(row, 'full-number')
    if full:
        number = full
        if year and str(year) in number:
            number = number.replace(str(year), '').rstrip('/')
    else:
        number = _int(row, 'number')
    if not (year and number):
        return None
    kind = {"CIRC": "CIRC", "RIS": "RIS", "INTERPELLO": "INT"}.get(_g(row, 'doc-type'))
    return f"PRAX:AE:{kind}:{year}:{number}" if kind else None


def _other_urn(row):
    if _g(row, 'authority') == "COMUNE" and _g(row, 'city') and _int(row, 'year') and _int(row, 'number'):
        return f"DEL:CO{_g(row, 'city')}:{_int(row, 'year')}:{_int(row, 'number')}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# urn_to_text: identifier -> human-readable citation (URN alone, no other input)
# ══════════════════════════════════════════════════════════════════════════════
_LOC_LABEL = {"art": "art.", "comma": "comma", "let": "let.", "num": "num.",
              "allegato": "allegato"}
# longest first so "comma"/"allegato" win over a bare prefix scan
_LOC_PREFIX_RE = re.compile(r'^(allegato|comma|art|let|num)(.*)$')


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
    if urn.startswith("PRAX:AE:"):
        return _prax_to_text(urn[len("PRAX:AE:"):])
    if urn.startswith("CONV_EU_DIR_UOMO"):
        _, loc = _split_locator(urn)
        return f"{loc + ' ' if loc else ''}CEDU".strip()
    if urn.startswith("TARIFFA_DOGANALE_COM"):
        _, loc = _split_locator(urn)
        return f"{loc + ' ' if loc else ''}tariffa doganale comune".strip()
    m = re.match(r'DM(\d{4})-(\d{2})-(\d{2})(?:~(.*))?$', urn)   # date-only ministerial decree
    if m:
        loc = _render_locator(m.group(4)) if m.group(4) else ""
        return f"{loc + ' ' if loc else ''}decreto ministeriale del {m.group(3)}/{m.group(2)}/{m.group(1)}".strip()
    return urn


def _split_locator(body):
    """Split an identifier body on the first '~' into (base, rendered locator text)."""
    if '~' not in body:
        return body, ''
    base, loc = body.split('~', 1)
    return base, _render_locator(loc)


def _ecli_to_text(body):
    # body: "CASS:2020:1234CIV" | "CTRLAZ:2024:100" | "COST:2018:188" | "CTCIT:1989:123"
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
                if geo_kind == "region":
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
    m = re.match(r'3(\d{4})([RLDH])(\d+)', base)
    if m:
        year, letter, num = m.group(1), m.group(2), int(m.group(3))
        doc = catalog.CELEX_DOCTYPE_NAME.get(letter, "atto")
        return f"{head}{doc} {year}/{num}/CE".strip()
    treaties = {"12012E/TXT": "TFUE", "12016ME/TXT": "TUE", "11957E/TXT": "Trattato CEE",
                "12002E/TXT": "Trattato CE", "12012P/TXT": "Carta dei diritti fondamentali UE"}
    if base in treaties:
        return f"{head}{treaties[base]}".strip()
    return f"{head}{base}".strip()


def _prax_to_text(body):
    # body: "CIRC:2005:47" | "RIS:2004:91" | "INT:2021:342"
    parts = body.split(':')
    if len(parts) < 3:
        return "PRAX:AE:" + body
    kind = {"CIRC": "circolare", "RIS": "risoluzione", "INT": "interpello"}.get(parts[0], parts[0])
    return f"{kind} Agenzia delle Entrate n. {parts[2]}/{parts[1]}"
