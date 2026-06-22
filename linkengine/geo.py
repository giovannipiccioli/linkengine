"""
Geographic code lists for case-law ECLI building.

Province (2-letter targa) and region (3-letter) codes, plus the full ~8k Italian comuni ->
catastale code map, are baked in so identifier building needs no external service at
runtime. A few provinces are represented via their catastale code (Verbania, Pesaro,
Forlì, Massa-Carrara).

ECLI usage:
  * CTR / Corte Giust. Trib. 2º grado -> needs ``region`` (3-letter)
  * CTP / Corte Giust. Trib. 1º grado / Tribunale / Corte d'Appello / Assise / Giudice di
    Pace -> needs ``city`` (2-letter province)
"""
from __future__ import annotations

import re
import unicodedata


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower().strip()


PROVINCE_NAME_TO_CODE = {
    'agrigento': 'AG', 'alessandria': 'AL', 'ancona': 'AN', 'aosta': 'AO', 'aquila': 'AQ',
    'arezzo': 'AR', 'ascoli piceno': 'AP', 'asti': 'AT', 'avellino': 'AV', 'bari': 'BA',
    'barletta': 'BT', 'belluno': 'BL', 'benevento': 'BN', 'bergamo': 'BG', 'biella': 'BI',
    'bologna': 'BO', 'brescia': 'BS', 'brindisi': 'BR', 'cagliari': 'CA',
    'caltanissetta': 'CL', 'campobasso': 'CB', 'caserta': 'CE', 'catania': 'CT',
    'catanzaro': 'CZ', 'chieti': 'CH', 'como': 'CO', 'cosenza': 'CS', 'cremona': 'CR',
    'crotone': 'KR', 'cuneo': 'CN', 'enna': 'EN', 'fermo': 'FM', 'ferrara': 'FE',
    'firenze': 'FI', 'foggia': 'FG', 'frosinone': 'FR', 'genova': 'GE', 'gorizia': 'GO',
    'grosseto': 'GR', 'imperia': 'IM', 'isernia': 'IS', 'la spezia': 'SP', 'latina': 'LT',
    'lecce': 'LE', 'lecco': 'LC', 'livorno': 'LI', 'lodi': 'LO', 'lucca': 'LU',
    'macerata': 'MC', 'mantova': 'MN', 'matera': 'MT', 'messina': 'ME', 'milano': 'MI',
    'modena': 'MO', 'monza': 'MB', 'napoli': 'NA', 'novara': 'NO', 'nuoro': 'NU',
    'oristano': 'OR', 'padova': 'PD', 'palermo': 'PA', 'parma': 'PR', 'pavia': 'PV',
    'perugia': 'PG', 'pescara': 'PE', 'piacenza': 'PC', 'pisa': 'PI', 'pistoia': 'PT',
    'pordenone': 'PN', 'potenza': 'PZ', 'prato': 'PO', 'ragusa': 'RG', 'ravenna': 'RA',
    'reggio calabria': 'RC', 'reggio emilia': 'RE', 'rieti': 'RI', 'rimini': 'RN',
    'roma': 'RM', 'rovigo': 'RO', 'salerno': 'SA', 'sassari': 'SS', 'savona': 'SV',
    'siena': 'SI', 'siracusa': 'SR', 'sondrio': 'SO', 'taranto': 'TA', 'teramo': 'TE',
    'terni': 'TR', 'torino': 'TO', 'trapani': 'TP', 'treviso': 'TV', 'trieste': 'TS',
    'udine': 'UD', 'varese': 'VA', 'venezia': 'VE', 'vercelli': 'VC', 'verona': 'VR',
    'vibo valentia': 'VV', 'vicenza': 'VI', 'viterbo': 'VT',
    # provinces represented via their catastale code (added by hand)
    'verbania': 'VB', 'pesaro': 'PU', 'forli': 'FC', 'massa carrara': 'MS',
    'massa': 'MS', 'carrara': 'MS',
}

REGION_NAME_TO_CODE = {
    'abruzzo': 'ABR', 'basilicata': 'BAS', 'calabria': 'CAL', 'campania': 'CAM',
    'emilia romagna': 'EMR', 'friuli venezia giulia': 'FVG', 'lazio': 'LAZ',
    'liguria': 'LIG', 'lombardia': 'LOM', 'marche': 'MAR', 'molise': 'MOL',
    'piemonte': 'PIE', 'puglia': 'PUG', 'sardegna': 'SAR', 'sicilia': 'SIC',
    'toscana': 'TOS', 'trentino alto adige': 'TAA', 'umbria': 'UMB',
    "valle d'aosta": 'VDA', 'veneto': 'VEN',
}


# All ~8k Italian comuni -> catastale code (e.g. "tivoli" -> "L182"), loaded from
# data/municipalities.txt. Used for tribunal/court ECLIs in non-capoluogo cities, which
# take the catastale code rather than a 2-letter province (targa) code.
def _load_municipalities():
    import os
    path = os.path.join(os.path.dirname(__file__), "data", "municipalities.txt")
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^([A-Z]\d{3})\s+(.+?)\s*$", line)
                if m:
                    out[strip_accents(m.group(2))] = m.group(1)
    except FileNotFoundError:
        pass
    return out


MUNICIPALITY_NAME_TO_CODE = _load_municipalities()


def _alt(names):
    # longest first so "reggio calabria" wins over "reggio"; allow accent/space variants
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


# Anchored matchers (used right after a court keyword). Case-insensitive; the source text
# is accent-stripped before matching so "Forlì" -> "forli" etc.
PROVINCE_RE = re.compile(r"^(" + _alt(PROVINCE_NAME_TO_CODE) + r")\b", re.IGNORECASE)
REGION_RE = re.compile(r"^(" + _alt(REGION_NAME_TO_CODE) + r")\b", re.IGNORECASE)
# Capoluogo (targa) names take precedence over the full comune list.
CITY_RE = re.compile(
    r"^(" + _alt(set(PROVINCE_NAME_TO_CODE) | set(MUNICIPALITY_NAME_TO_CODE)) + r")\b",
    re.IGNORECASE)


def province_code(name: str):
    return PROVINCE_NAME_TO_CODE.get(strip_accents(name))


def region_code(name: str):
    return REGION_NAME_TO_CODE.get(strip_accents(name))


# region code -> urn:nir region segment (e.g. "regione.campania")
REGION_CODE_TO_URN = {
    "ABR": "abruzzo", "BAS": "basilicata", "CAL": "calabria", "CAM": "campania",
    "EMR": "emilia.romagna", "FVG": "friuli.venezia.giulia", "LAZ": "lazio",
    "LIG": "liguria", "LOM": "lombardia", "MAR": "marche", "MOL": "molise",
    "PIE": "piemonte", "PUG": "puglia", "SAR": "sardegna", "SIC": "sicilia",
    "TOS": "toscana", "TAA": "trentino.alto.adige", "UMB": "umbria",
    "VDA": "valle.aosta", "VEN": "veneto",
}


def region_urn(name: str):
    """A region name (or already-normalized urn segment) -> its urn:nir segment, or None."""
    code = region_code(name)
    if code:
        return REGION_CODE_TO_URN.get(code)
    canon = strip_accents(name).replace(" ", ".")
    return canon if canon in set(REGION_CODE_TO_URN.values()) else None


def city_code(name: str):
    """Province 2-letter targa for a capoluogo (Roma->RM), else the comune catastale code
    (Tivoli->L182)."""
    n = strip_accents(name)
    return PROVINCE_NAME_TO_CODE.get(n) or MUNICIPALITY_NAME_TO_CODE.get(n)


# ── reverse lookups (code -> display name), used by urn_to_text ────────────────
def _reverse_longest(name_to_code):
    out = {}
    for name, code in name_to_code.items():
        if code not in out or len(name) > len(out[code]):
            out[code] = name
    return out


PROVINCE_CODE_TO_NAME = {c: n.title() for c, n in _reverse_longest(PROVINCE_NAME_TO_CODE).items()}
REGION_CODE_TO_NAME = {c: n.title() for c, n in _reverse_longest(REGION_NAME_TO_CODE).items()}
REGION_URN_TO_NAME = {urn: REGION_CODE_TO_NAME[code] for code, urn in REGION_CODE_TO_URN.items()}
_MUNI_CODE_TO_NAME = {code: name.title() for name, code in MUNICIPALITY_NAME_TO_CODE.items()}


def city_name(code: str) -> str:
    """A 2-letter targa or comune catastale code -> a display city name, else the code itself."""
    return PROVINCE_CODE_TO_NAME.get(code) or _MUNI_CODE_TO_NAME.get(code) or code


def region_name(code_or_urn: str) -> str:
    """A region 3-letter code (LAZ) or urn segment (emilia.romagna) -> its display name."""
    return (REGION_CODE_TO_NAME.get(code_or_urn) or REGION_URN_TO_NAME.get(code_or_urn)
            or code_or_urn)
