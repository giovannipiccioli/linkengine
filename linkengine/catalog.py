"""
Centralized reference catalog — the single source of truth for **courts**, **document types**
and **alias display names**, shared by the recognizers, the URN builder (``urn.build_urn``) and
the human-readable renderer (``urn.urn_to_text``). Geographic data (provinces / regions /
comuni) lives in ``geo.py`` and is re-exported here for convenience.

Edit this file to add a court (ECLI prefix + geo kind + display name), a doctype display name,
or an alias display name — every component picks the change up automatically.
"""
from .geo import (PROVINCE_CODE_TO_NAME, REGION_CODE_TO_NAME, REGION_URN_TO_NAME,  # noqa: F401
                  city_name, region_name)

# ── Courts ────────────────────────────────────────────────────────────────────
# authority code -> ECLI prefix (None when the court has no ECLI), the geo it carries
# ('city' / 'region' / None), and a human display name.
COURTS = {
    "CORTE_CASS":              {"ecli": "CASS",      "geo": None,     "name": "Cassazione"},
    "CORTE_COST":              {"ecli": "COST",      "geo": None,     "name": "Corte Costituzionale"},
    "CONS_STATO":              {"ecli": "CONSSTATO", "geo": None,     "name": "Consiglio di Stato"},
    "CORTE_CONTI":             {"ecli": "CCONTI",    "geo": None,     "name": "Corte dei Conti"},
    "TRIB":                    {"ecli": "TRIB",      "geo": "city",   "name": "Tribunale"},
    "COMM_TRIBUT_REG":         {"ecli": "CTR",       "geo": "region", "name": "Corte di Giustizia Tributaria di secondo grado"},
    "CORTE_GIUST_TRIBUT_REG":  {"ecli": "CTR",       "geo": "region", "name": "Corte di Giustizia Tributaria di secondo grado"},
    "COMM_TRIBUT_PROV":        {"ecli": "CTP",       "geo": "city",   "name": "Corte di Giustizia Tributaria di primo grado"},
    "CORTE_GIUST_TRIBUT_PROV": {"ecli": "CTP",       "geo": "city",   "name": "Corte di Giustizia Tributaria di primo grado"},
    "COMM_TRIBUT_CEN":         {"ecli": "CTC",       "geo": "city",   "name": "Commissione Tributaria Centrale"},
    "CORTE_APPELLO":           {"ecli": "CAPP",      "geo": "city",   "name": "Corte d'Appello"},
    "CORTE_ASSISE_APPELLO":    {"ecli": "ASSAPP",    "geo": "city",   "name": "Corte d'Assise d'Appello"},
    "CORTE_ASSISE":            {"ecli": "ASS",       "geo": "city",   "name": "Corte d'Assise"},
    "GIUDICE_PACE":            {"ecli": "GDP",       "geo": "city",   "name": "Giudice di Pace"},
    "TRIBUNALE_SORVEGLIANZA":  {"ecli": "TRIBSORV",  "geo": "city",   "name": "Tribunale di Sorveglianza"},
    "CGUE":                    {"ecli": None,        "geo": None,     "name": "Corte di Giustizia UE"},
    "CEDU":                    {"ecli": None,        "geo": None,     "name": "Corte EDU"},
    "TRIB_AMM_REG":            {"ecli": "TAR",       "geo": "region", "name": "TAR"},
}
# every court is a case-law authority; "THIS_COURT" (a self-reference resolved to the document's
# own authority) is one too. This is THE set — assembler and the eval dispatch derive from it.
CASELAW_AUTH = set(COURTS) | {"THIS_COURT"}
# ECLI prefix -> (court name, geo kind), longest prefix first so "ASSAPP"/"CONSSTATO"/"TRIBSORV"
# win over "ASS"/"CTC"/"TRIB". "COST" is handled specially (Corte Costituzionale).
ECLI_PREFIX_TO_COURT = {}
for _auth, _info in COURTS.items():
    if _info["ecli"] and _info["ecli"] not in ECLI_PREFIX_TO_COURT:
        ECLI_PREFIX_TO_COURT[_info["ecli"]] = (_info["name"], _info["geo"])
ECLI_PREFIXES = sorted(ECLI_PREFIX_TO_COURT, key=len, reverse=True)


# ── Document types (urn:nir "authority:doctype" -> display name) ────────────────
URN_DOCTYPE_NAME = {
    "stato:legge": "legge",
    "stato:legge.costituzionale": "legge costituzionale",
    "stato:decreto.legge": "decreto-legge",
    "stato:decreto.legislativo": "decreto legislativo",
    "stato:regolamento": "regolamento",
    "stato:regio.decreto": "regio decreto",
    "presidente.repubblica:decreto": "D.P.R.",
    "presidente.consiglio.ministri:decreto": "D.P.C.M.",
    "ministero:decreto": "decreto ministeriale",
    "luogotenente:decreto.legislativo": "decreto legislativo luogotenenziale",
    "luogotenente:decreto.legge": "decreto-legge luogotenenziale",
    "capo.provvisorio.stato:decreto.legislativo": "decreto legislativo del Capo provvisorio dello Stato",
    "capo.provvisorio.stato:decreto.legge": "decreto-legge del Capo provvisorio dello Stato",
}
# EU CELEX provision letter -> doctype display.
CELEX_DOCTYPE_NAME = {"R": "regolamento", "L": "direttiva", "D": "decisione", "H": "raccomandazione"}


# ── Aliases (urn:nir base, year-only -> display name) ───────────────────────────
# ALIAS_NIR (base) and ALIAS_DISPLAY (display name) both live in aliases.py — one place per
# alias. Here we just build the reverse map base -> display for urn_to_text.
def _year_only_base(base: str) -> str:
    """Reduce a urn:nir base to year-only form ("stato:regio.decreto:1942-03-16;262:2" ->
    "stato:regio.decreto:1942;262:2") so it matches a row's date-trimmed identifier."""
    import re
    return re.sub(r":(\d{4})-\d{2}-\d{2};", r":\1;", base)


def _build_alias_base_to_name():
    from .aliases import ALIAS_NIR, ALIAS_DISPLAY
    out = {}
    for code, base in ALIAS_NIR.items():
        name = ALIAS_DISPLAY.get(code)
        if name:
            out[_year_only_base(base)] = name
    return out


ALIAS_BASE_TO_NAME = _build_alias_base_to_name()   # "stato:regio.decreto:1942;262:2" -> "codice civile"
