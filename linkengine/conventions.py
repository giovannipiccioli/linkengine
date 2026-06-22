"""
Convenzioni contro la doppia imposizione (bilateral tax treaties Italy ↔ another country).

These are cited as "Convenzione Italia-Francia", "Convenzione contro le doppie imposizioni
tra Italia e Spagna", "Convenzione Italo Tedesca", etc. The standard identifier is the
**Italian ratification law** (a `legge`), so e.g. Italy–France resolves to
`urn:nir:stato:legge:1992;20`.

The country→code and code→ratification-law tables below are internalized from the project's
``conv_doppia_imp_parsing.py`` (NOT imported, to keep linkengine dependency-free). Only
countries with a known ratification law produce a URN; others (e.g. Switzerland, Holy See)
are recognized as a treaty but left without an identifier, matching the source module.
"""
from __future__ import annotations

import re
from typing import List

from .model import Entity, Span

I = re.IGNORECASE

# country (Italian name / adjective) -> ISO-3 code
COUNTRIES = {
    "albania": "ALB", "albanese": "ALB", "andorra": "AND", "austria": "AUT", "belgio": "BEL",
    "bulgaria": "BGR", "danimarca": "DNK", "finlandia": "FIN", "francia": "FRA",
    "francese": "FRA", "germania": "DEU", "tedesca": "DEU", "regno unito": "GBR",
    "gran bretagna": "GBR", "britannica": "GBR", "austriaca": "AUT", "svizzero": "CHE", 
    "slovacca": "SVK", "ceca": "CZE",
    "grecia": "GRC", "irlanda": "IRL", "islanda": "ISL", "liechtenstein": "LIE",
    "lussemburgo": "LUX", "malta": "MLT", "monaco": "MCO", "norvegia": "NOR",
    "paesi bassi": "NLD", "polonia": "POL", "portogallo": "PRT", "portoghese": "PRT",
    "romania": "ROU", "san marino": "SMR", "spagna": "ESP", "svezia": "SWE",
    "svizzera": "CHE", "ucraina": "UKR", "ungheria": "HUN", "federazione russa": "RUS",
    "estonia": "EST", "lettonia": "LVA", "lituania": "LTU", "croazia": "HRV",
    "slovenia": "SVN", "bosnia-erzegovina": "BIH", "moldova": "MDA", "slovacchia": "SVK",
    "bielorussia": "BLR", "repubblica ceca": "CZE", "montenegro": "MNE", "serbia": "SRB",
    "serba": "SRB", "arabia saudita": "SAU", "bangladesh": "BGD", "sri lanka": "LKA",
    "cina": "CHN", "cipro": "CYP", "corea del sud": "KOR", "emirati arabi uniti": "ARE",
    "filippine": "PHL", "giappone": "JPN", "giordania": "JOR", "india": "IND",
    "indonesia": "IDN", "israele": "ISR", "kuwait": "KWT", "libano": "LBN",
    "malaysia": "MYS", "oman": "OMN", "pakistan": "PAK", "qatar": "QAT", "singapore": "SGP",
    "siria": "SYR", "thailandia": "THA", "turchia": "TUR", "vietnam": "VNM",
    "uzbekistan": "UZB", "armenia": "ARM", "georgia": "GEO", "kazakhstan": "KAZ",
    "kirghizistan": "KGZ", "tagikistan": "TJK", "algeria": "DZA", "costa d'avorio": "CIV",
    "congo": "COG", "egitto": "EGY", "etiopia": "ETH", "ghana": "GHA", "marocco": "MAR",
    "mozambico": "MOZ", "senegal": "SEN", "tunisia": "TUN", "uganda": "UGA",
    "sudafrica": "ZAF", "giamaica": "JAM", "messico": "MEX", "panama": "PAN",
    "stati uniti d'america": "USA", "stati uniti": "USA", "usa": "USA", "argentina": "ARG",
    "colombia": "COL", "trinidad e tobago": "TTO", "venezuela": "VEN", "australia": "AUS",
    "nuova zelanda": "NZL", "santa sede": "VAT", "stato della città del vaticano": "VAT",
}

# ISO-3 code -> [number, year] of the Italian ratification law
RATIFICA = {
    "ALB": (175, 1998), "AUT": (762, 1984), "BEL": (148, 1989), "DNK": (170, 2002),
    "FIN": (38, 1983), "FRA": (20, 1992), "DEU": (459, 1992), "GBR": (329, 1990),
    "GRC": (445, 1989), "IRL": (583, 1974), "LUX": (747, 1982), "MLT": (304, 1983),
    "NOR": (108, 1987), "NLD": (305, 1993), "POL": (97, 1989), "PRT": (562, 1982),
    "ROU": (78, 2017), "ESP": (663, 1980), "SWE": (439, 1982), "UKR": (169, 2002),
    "HUN": (509, 1980), "EST": (427, 1999), "LVA": (73, 2008), "LTU": (31, 1999),
    "HRV": (75, 2009), "SVN": (768, 2009), "MDA": (8, 2011), "MNE": (974, 1984),
    "SAU": (159, 2009), "BGD": (301, 1995), "LKA": (314, 1989), "CHN": (376, 1989),
    "KOR": (15, 2014), "ARE": (309, 1997), "PHL": (312, 1989), "JPN": (413, 1981),
    "JOR": (160, 2009), "IND": (319, 1995), "IDN": (707, 1994), "ISR": (371, 1997),
    "KWT": (53, 1992), "LBN": (87, 2011), "MYS": (607, 1985), "OMN": (50, 2002),
    "PAK": (313, 1989), "QAT": (118, 2010), "SGP": (575, 1978), "SYR": (130, 2004),
    "THA": (202, 1980), "TUR": (195, 1993), "VNM": (474, 1998), "UZB": (22, 2004),
    "ARM": (190, 2007), "KGZ": (311, 1988), "TJK": (311, 1988), "DZA": (711, 1994),
    "CIV": (293, 1985), "COG": (288, 2005), "EGY": (387, 1981), "ETH": (242, 2003),
    "GHA": (48, 2006), "MAR": (504, 1981), "MOZ": (110, 2003), "SEN": (417, 2000),
    "TUN": (388, 1981), "UGA": (18, 2005), "JAM": (93, 2020), "MEX": (710, 1994),
    "PAN": (208, 2016), "USA": (20, 2009), "ARG": (282, 1982), "COL": (92, 2020),
    "TTO": (167, 1973), "VEN": (200, 1992), "AUS": (292, 1985), "NZL": (566, 1982),
    # Italy–Switzerland (1976) ratified by l. 23 dic. 1978, n. 943; Italy–Czechoslovakia (1981,
    # honoured by both successor states) ratified by l. 2 mag. 1983, n. 303.
    "CHE": (943, 1978), "SVK": (303, 1983), "CZE": (303, 1983),
}

_CONV_KW_RE = re.compile(r"\b(?:convenzione|accordo|trattato)\b", I)
_ITAL_RE = re.compile(r"\bital(?:ia|o|ian[ao])\b", I)
# match the longest country names first ("regno unito" before "unito" fragments)
_COUNTRY_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in sorted(COUNTRIES, key=len, reverse=True)) + r")\b", I)


def recognize_conventions(text: str) -> List[Span]:
    """Emit a (DOCTYPE L + NUM_YEAR) pair for each Italy↔country tax treaty whose ratification
    law is known. The article partition attaches to it downstream, so
    "Convenzione Italia-Giappone, art. 15" -> ``urn:nir:stato:legge:1981;413~art15``."""
    spans: List[Span] = []
    for km in _CONV_KW_RE.finditer(text):
        win = text[km.start(): km.start() + 95]
        if not _ITAL_RE.search(win):
            continue
        cm = _COUNTRY_RE.search(win)
        if not cm:
            continue
        nl = RATIFICA.get(COUNTRIES.get(cm.group(1).lower(), ""))
        if not nl:
            continue
        num, yr = nl
        s, e = km.start(), km.start() + cm.end()
        spans.append(Span(s, e, Entity.DOCTYPE, "L", text[s:e], {"scope": "nazionale"}))
        spans.append(Span(s, e, Entity.NUM_YEAR, f"{num}/{yr}", text[s:e],
                          {"number": str(num), "year": str(yr)}))
    return spans
