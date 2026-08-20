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
from .act_kinds import URN_DOCTYPE_NAME as _ACT_KIND_URN_DOCTYPE_NAME

# ── Courts ────────────────────────────────────────────────────────────────────
# authority code -> ECLI prefix (None when the court has no ECLI), the geo it carries
# ('city' / 'region' / None), and a human display name.
COURTS = {
    "CORTE_CASS":              {"ecli": "CASS",      "geo": None,     "name": "Cassazione"},
    "CORTE_COST":              {"ecli": "COST",      "geo": None,     "name": "Corte Costituzionale"},
    "CONS_STATO":              {"ecli": "CDS",       "geo": None,     "name": "Consiglio di Stato"},
    "CORTE_CONTI":             {"ecli": "CONT",      "geo": None,     "name": "Corte dei Conti"},
    "TRIB":                    {"ecli": "TRIB",      "geo": "city",   "name": "Tribunale"},
    "COMM_TRIBUT_REG":         {"ecli": "CTR",       "geo": "region", "name": "Commissione Tributaria Regionale"},
    "CORTE_GIUST_TRIBUT_2":    {"ecli": "CGT2",      "geo": "region", "name": "Corte di Giustizia Tributaria di secondo grado"},
    "COMM_TRIBUT_PROV":        {"ecli": "CTP",       "geo": "city",   "name": "Commissione Tributaria Provinciale"},
    "CORTE_GIUST_TRIBUT_1":    {"ecli": "CGT1",      "geo": "city",   "name": "Corte di Giustizia Tributaria di primo grado"},
    "COMM_TRIBUT_CEN":         {"ecli": "CTC",       "geo": "city",   "name": "Commissione Tributaria Centrale"},
    "CORTE_APPELLO":           {"ecli": "CAPP",      "geo": "city",   "name": "Corte d'Appello"},
    "CORTE_ASSISE_APPELLO":    {"ecli": "ASSAPP",    "geo": "city",   "name": "Corte d'Assise d'Appello"},
    "CORTE_ASSISE":            {"ecli": "ASS",       "geo": "city",   "name": "Corte d'Assise"},
    "GIUDICE_PACE":            {"ecli": "GDP",       "geo": "city",   "name": "Giudice di Pace"},
    "TRIBUNALE_SORVEGLIANZA":  {"ecli": "TRIBSORV",  "geo": "city",   "name": "Tribunale di Sorveglianza"},
    "CGUE":                    {"ecli": None,        "geo": None,     "name": "Corte di Giustizia UE"},
    "CEDU":                    {"ecli": None,        "geo": None,     "name": " Corte europea dei diritti dell'uomo"},
    # The administrative courts. A TAR ECLI names the SEAT that decided, not the region:
    # "TARBS" is Brescia, "TARNA" Napoli. The Trentino tribunals are a separate court, and
    # the Sicilian appeal instance is the CGA, not the Consiglio di Stato.
    "TRIB_AMM_REG":            {"ecli": "TAR",       "geo": "city",   "name": "TAR"},
    "TRIB_REG_GIUST_AMM":      {"ecli": "TRGA",      "geo": "city",   "name": "TRGA"},
    "CGARS":                   {"ecli": "CGARS",     "geo": None,
                                "name": "Consiglio di Giustizia Amministrativa per la Regione Siciliana"},
}
# every court is a case-law authority; "THIS_COURT" (a self-reference resolved to the document's
# own authority) is one too. This is THE set — assembler and the eval dispatch derive from it.
CASELAW_AUTH = set(COURTS) | {"THIS_COURT"}
FIRST_GRADE_TAX_AUTHORITIES = {"COMM_TRIBUT_PROV", "CORTE_GIUST_TRIBUT_1"}
SECOND_GRADE_TAX_AUTHORITIES = {"COMM_TRIBUT_REG", "CORTE_GIUST_TRIBUT_2"}


# ── Giustizia amministrativa ──────────────────────────────────────────────────
# A TAR identifier names the seat that decided. Eleven regions have one TAR and spell it with
# the region code; the eight that also have a *sezione staccata* spell both seats with the
# province targa — except Lazio, whose seat keeps LAZ. There is no rule under that, so this
# is a table: the seat's city code -> the ECLI component.
TAR_SEAT = {
    "RM": "LAZ", "LT": "LT",                      # Lazio
    "MI": "MI",  "BS": "BS",                      # Lombardia
    "NA": "NA",  "SA": "SA",                      # Campania
    "PA": "PA",  "CT": "CT",                      # Sicilia
    "BA": "BA",  "LE": "LE",                      # Puglia
    "CZ": "CZ",  "RC": "RC",                      # Calabria
    "AQ": "AQ",  "PE": "PE",                      # Abruzzo
    "BO": "BO",  "PR": "PR",                      # Emilia-Romagna
    "FI": "TOS", "VE": "VEN", "TO": "PIE", "GE": "LIG", "AN": "MAR", "CA": "SAR",
    "CB": "MOL", "PZ": "BAS", "PG": "UMB", "TS": "FVG", "AO": "VDA",
}
# A region named on its own means its seat: a sezione staccata is always named when it is the
# one that decided ("TAR Sicilia" is Palermo, "TAR Sicilia sezione staccata di Catania" is not).
TAR_REGION_SEAT = {
    "LAZ": "RM", "LOM": "MI", "CAM": "NA", "SIC": "PA", "PUG": "BA", "CAL": "CZ",
    "ABR": "AQ", "EMR": "BO", "TOS": "FI", "VEN": "VE", "PIE": "TO", "LIG": "GE",
    "MAR": "AN", "SAR": "CA", "MOL": "CB", "BAS": "PZ", "UMB": "PG", "FVG": "TS",
    "VDA": "AO",
}
# Trentino-Alto Adige has no TAR: the TRGA sits in Trento with an autonomous section in Bolzano.
TRGA_SEAT = {"TN": "TN", "BZ": "BZ"}

# The last component of an administrative identifier is the DOCUMENT TYPE, because each type
# numbers independently — 41.5% of court+year+number triples in the Council's archive carry
# more than one, so number and year alone name no decision.
#
# A citation names the family, not the code, and the family has more than one member: these
# are the shares each takes when only the family is known — sentenza SENT 85.7% (SENB 13.7%),
# ordinanza OCAU 75.8% (OCOL 22.4%), decreto DDEC 87.7%, parere PDEF 71.0%. A citation naming
# no type at all is read as a sentenza; legal prose cites sentenze, and 78% of the typed
# citations in the sampled decisions say so.
#
# Measured over 272 identifiers built from 106 real decisions: 85.3% are exactly right and
# 11.8% carry the wrong type, most of them a sentenza breve read as an ordinary sentenza,
# which no citation saying only "sentenza" can distinguish. That cost buys the other 85%, and
# it is the cheap kind of wrong: the court, the year and the number are never guessed, so a
# wrong type resolves to nothing rather than to somebody else's ruling.
ADMIN_DOCTYPE = {"SENT": "SENT", "ORD": "OCAU", "DECR": "DDEC", "PARERE": "PDEF", "": "SENT"}
# ...and the qualifiers a citation does spell out when they apply, which settle the family.
# Checked in order, before the default above.
ADMIN_DOCTYPE_QUALIFIED = {
    "SENT": ((r"sentenz\w*\s+brev", "SENB"), (r"in\s+forma\s+semplificata", "SENB")),
    "ORD":  ((r"ordinanz\w*\s+collegial", "OCOL"), (r"ordinanz\w*\s+presidenzial", "OPRE")),
    "PARERE": ((r"parer\w*\s+interlocutori", "PINTE"),),
}
ADMIN_AUTHORITIES = {"CONS_STATO", "TRIB_AMM_REG", "TRIB_REG_GIUST_AMM", "CGARS"}


# ── Corte dei conti sections ──────────────────────────────────────────────────
# The Corte dei conti ECLI carries its section as a suffix on the decision NUMBER
# ("ECLI:IT:CONT:2023:89SGCAL"), the way the Cassazione carries CIV/PEN — not as an ECLI
# geo component, which is why COURTS["CORTE_CONTI"]["geo"] stays None. A controllo
# deliberation adds its procedural type after a hyphen ("…:102SRCPIE-PAR"); the type is
# part of the identifier, so a controllo citation that omits it stays unresolved.
#
# Sentenze and ordinanze share one number series per section, so the giurisdizionale
# identifier carries no doc-type marker, and the rubrics that decorate such a citation
# ("n. 7/2007/QM", "n. 11/2023/RGC", "n. 653/2013-A") are NOT part of it.
def _corte_conti_regional():
    """The regional sections, one entry per region on each side, so a region is spelled
    once. Trentino-Alto Adige is excluded: it sits in two seats and is spelled out below.

    Every geographic component of a section code is the standard code from ``geo.py`` — the
    three-letter region code, or the two-letter province targa for a section that sits in a
    seat rather than a region. The Corte dei conti's own archive is not consistent about
    this (it writes SRCERO for Emilia-Romagna, SGTAB for Bolzano, SSRRTN for the Trentino
    REGION); those identifiers are therefore ours, not the portal's, and the payoff is that
    a caller who knows a region knows its section code. Change it here, not in the caller,
    if they ever have to match the portal exactly."""
    out = {}
    for code, name in REGION_CODE_TO_NAME.items():
        if code == "TAA":
            continue
        out["SG" + code] = f"Sezione giurisdizionale {name}"
        out["SRC" + code] = f"Sezione regionale di controllo {name}"
    return out


# code -> display name, for every section that can appear in a Corte dei conti identifier.
CORTE_CONTI_SECTIONS = {
    **_corte_conti_regional(),
    # Trentino-Alto Adige has one section per seat on each side, so these four carry the
    # province targa (TN/BZ) where every other regional code carries a region.
    "SGTN":   "Sezione giurisdizionale Trentino-Alto Adige, sede di Trento",
    "SGBZ":   "Sezione giurisdizionale Trentino-Alto Adige, sede di Bolzano",
    "SRCTN":  "Sezione regionale di controllo Trentino-Alto Adige, sede di Trento",
    "SRCBZ":  "Sezione regionale di controllo Trentino-Alto Adige, sede di Bolzano",
    # giurisdizionale — central
    "APP1":   "Prima Sezione centrale d'appello",
    "APP2":   "Seconda Sezione centrale d'appello",
    "APP3":   "Terza Sezione centrale d'appello",
    "APPSIC": "Sezione d'appello per la Regione Siciliana",
    "SSR":    "Sezioni riunite in sede giurisdizionale",
    # controllo — central
    "SEZAUT": "Sezione delle Autonomie",
    "SSRRCO": "Sezioni riunite in sede di controllo",
    "SCE":    "Sezione del controllo sugli enti",
    "SCCGAS": "Sezione centrale di controllo sulla gestione delle amministrazioni dello Stato",
    "SCCLEG": "Sezione centrale di controllo di legittimità sugli atti del Governo",
    "CCC":    "Collegio del controllo concomitante",
    "SACEI":  "Sezione di controllo affari comunitari e internazionali",
    "SCAEI":  "Sezione di controllo per gli affari europei e internazionali",
    "SCCS":   "Sezione centrale per il controllo dei contratti secretati",
    "CONS":   "Sezioni riunite in sede consultiva",
    # ...and the regional benches of those two, which are the central code plus the region.
    "SSRRCOSIC": "Sezioni riunite per la Regione Siciliana in sede di controllo",
    "SSRRCOTAA": "Sezioni riunite per la Regione Trentino-Alto Adige in sede di controllo",
    "SSRRCOSAR": "Sezioni riunite per la Regione Sardegna in sede di controllo",
    "CONSSIC":   "Sezioni riunite per la Regione Siciliana in sede consultiva",
}
# The sections whose identifier needs a deliberation type. Everything else is
# giurisdizionale and is complete with number + year alone.
CORTE_CONTI_CONTROLLO = {c for c in CORTE_CONTI_SECTIONS if c.startswith("SRC")} | {
    "SEZAUT", "SSRRCO", "SCE", "SCCGAS", "SCCLEG", "CCC", "SACEI", "SCAEI", "SCCS",
    "CONS", "SSRRCOSIC", "SSRRCOTAA", "SSRRCOSAR", "CONSSIC",
}
# Procedural type codes a controllo deliberation can carry, from the whole 1991-2026
# archive. A flat set: an unrecognized token simply fails to classify, which is the
# behaviour we want.
CORTE_CONTI_DELIB_TYPES = {
    "PRSE", "PRSP", "PAR", "VSG", "FRG", "PRNO", "REG", "RGES", "VSGO", "PASP", "CSE",
    "INPR", "GEST", "PRSS", "PREV", "VSGC", "PARI", "VSGF", "SUCC", "RQ", "QMIG", "CCR",
    "DEL", "OICERT", "CCN", "PNRR", "SSR", "AUD", "DORG", "CONS", "IADC", "DASS", "COMP",
    "RSUE", "REF", "PRS", "FUEFC", "AFC", "CEPAR", "OICERN", "PENS", "RCFP", "RCL",
    "PRAS", "CCSE",
}
# Doc-types that mean something else everywhere else and are a court's pronouncements only
# when paired with that court: the Corte dei conti's controllo channel deliberates and gives
# pareri, its giurisdizionale benches still call some rulings "decisione" (elsewhere an EU
# act), and the Consiglio di Stato advises. The pairing is what licenses them — never the
# doc-type on its own, so a bare "delibera n. 60/2021" stays a local act and a "decisione
# 2011/278/UE" stays an EU act.
COURT_EXTRA_DOCTYPES = {
    "CORTE_CONTI": {"DEL", "PARERE", "DECIS"},
    # the Consiglio di Stato and the CGA also advise, in sede consultiva
    "CONS_STATO": {"PARERE"},
    "CGARS": {"PARERE"},
}
# ...of which these two are the controllo channel's own, and these three the giurisdizionale
# one's. Which side a bare "Sezioni riunite" sits on is readable from nothing else.
CORTE_CONTI_CONTROLLO_DOCTYPES = {"DEL", "PARERE"}
CORTE_CONTI_GIUR_DOCTYPES = {"SENT", "ORD", "DECIS"}
# Rubrics that decorate a GIURISDIZIONALE citation and are absent from its identifier:
# "n. 7/2007/QM" is ECLI:IT:CONT:2007:7SSR, not "…7SSR-QM".
CORTE_CONTI_GIUR_RUBRICS = {"QM", "QMI", "RGC", "EL", "RIS", "DELC", "A", "M", "ADS", "PENS"}
# ECLI prefix -> (court name, geo kind), longest prefix first so "ASSAPP"/"CONSSTATO"/"TRIBSORV"
# win over "ASS"/"CTC"/"TRIB". "COST" is handled specially (Corte Costituzionale).
ECLI_PREFIX_TO_COURT = {}
for _auth, _info in COURTS.items():
    if _info["ecli"] and _info["ecli"] not in ECLI_PREFIX_TO_COURT:
        ECLI_PREFIX_TO_COURT[_info["ecli"]] = (_info["name"], _info["geo"])
ECLI_PREFIXES = sorted(ECLI_PREFIX_TO_COURT, key=len, reverse=True)


# ── Who can emit what ───────────────────────────────────────────────────────────
# Doc-types an authority can plausibly *issue*, used to reject impossible bindings (a court
# does not enact a legge; the Agenzia delle Entrate does not hand down a sentenza). Keep this
# small and obvious — it only has to catch the gross category errors that create false
# positives, not model the full administrative taxonomy.
#
# A **court** (any authority in COURTS / CASELAW_AUTH) issues pronouncements only:
COURT_DOCTYPES = {"SENT", "ORD", "DECR"}            # sentenza, ordinanza, decreto
# administrative authorities issue these practice documents. DEL and DIR are handled
# contextually because they can also identify municipal/EU acts.
AGENCY_DOCTYPES = {
    "CIRC", "RIS", "INTERPELLO", "PROVV", "PARERE", "NOTA", "DET",
    "CS", "TEL", "LCIRC",
}
CONDITIONAL_AGENCY_DOCTYPES = {"DEL", "DIR"}


# ── Document types (urn:nir "authority:doctype" -> display name) ────────────────
URN_DOCTYPE_NAME = {**_ACT_KIND_URN_DOCTYPE_NAME, "stato:regolamento": "regolamento"}
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
