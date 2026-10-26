"""
Convenzioni contro la doppia imposizione (bilateral tax treaties Italy ↔ another country).

These are cited as "Convenzione Italia-Francia", "Convenzione contro le doppie imposizioni
tra Italia e Spagna", "Convenzione Italo Tedesca", etc. The standard identifier is the
**annex to the Italian ratification law** (a `legge`), so e.g. Italy–France resolves to
`urn:nir:stato:legge:1992;20:1`.

The country→code and code→ratification-law tables below are internalized from the project's
``conv_doppia_imp_parsing.py`` (NOT imported, to keep linkengine dependency-free). Only
countries with a known ratification law produce a URN; others (e.g. San Marino, Holy See)
are recognized as a treaty but left without an identifier, matching the source module.

The Italian-text annexes were checked on Normattiva for 30 treaties (2026-10-26).
Unverified treaties default to annex 1; India, Greece and Czechoslovakia use annex 2.
China defaults to the 2019 agreement (law 182/2024), while explicit references to the
1986 agreement or law 376/1989 retain the historical identity. Availability of article
text in the corpus is separate from the identity of the cited treaty.
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
    "slovacca": "SVK", "ceca": "CZE", "repubblica slovacca": "SVK",
    "cecoslovacchia": "CZE",
    "grecia": "GRC", "irlanda": "IRL", "islanda": "ISL", "liechtenstein": "LIE",
    "lussemburgo": "LUX", "malta": "MLT", "monaco": "MCO", "norvegia": "NOR",
    "paesi bassi": "NLD", 'regno dei paesi bassi': "NLD", "polonia": "POL", "portogallo": "PRT", "portoghese": "PRT",
    "romania": "ROU", "san marino": "SMR", "spagna": "ESP", "svezia": "SWE",
    "svizzera": "CHE", "ucraina": "UKR", "ungheria": "HUN", "federazione russa": "RUS",
    "estonia": "EST", "lettonia": "LVA", "lituania": "LTU", "croazia": "HRV",
    "slovenia": "SVN", "bosnia-erzegovina": "BIH", "moldova": "MDA", "slovacchia": "SVK",
    "bielorussia": "BLR", "repubblica ceca": "CZE", "montenegro": "MNE", "serbia": "SRB",
    "serba": "SRB", "arabia saudita": "SAU", "bangladesh": "BGD", "sri lanka": "LKA",
    "cina": "CHN", "cinese": "CHN", "cipro": "CYP", "corea del sud": "KOR", "emirati arabi uniti": "ARE",
    "filippine": "PHL", "giappone": "JPN", "giapponese": "JPN", "giordania": "JOR", "india": "IND",
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
    "SAU": (159, 2009), "BGD": (301, 1995), "LKA": (314, 1989), "CHN": (182, 2024),
    "KOR": (15, 2014), "ARE": (309, 1997), "PHL": (312, 1989), "JPN": (855, 1972),
    "JOR": (160, 2009), "IND": (319, 1995), "IDN": (707, 1994), "ISR": (371, 1997),
    "KWT": (53, 1992), "LBN": (87, 2011), "MYS": (607, 1985), "OMN": (50, 2002),
    "PAK": (313, 1989), "QAT": (118, 2010), "SGP": (575, 1978), "SYR": (130, 2004),
    "THA": (202, 1980), "TUR": (195, 1993), "VNM": (474, 1998), "UZB": (22, 2004),
    "ARM": (190, 2007), "KGZ": (311, 1988), "TJK": (311, 1988), "DZA": (711, 1994),
    "CIV": (293, 1985), "COG": (288, 2005), "EGY": (387, 1981), "ETH": (242, 2003),
    "GHA": (48, 2006), "MAR": (504, 1981), "MOZ": (110, 2003), "SEN": (417, 2000),
    "TUN": (388, 1981), "UGA": (18, 2005), "JAM": (93, 2020), "MEX": (710, 1994),
    "PAN": (208, 2016), "USA": (20, 2009), "ARG": (282, 1982), "COL": (92, 2020),
    "TTO": (167, 1973), "VEN": (200, 1992), "AUS": (292, 1985), "NZL": (566, 1982),"BGR":(389,1990),
    # Italy–Switzerland (1976) ratified by l. 23 dic. 1978, n. 943; Italy–Czechoslovakia (1981,
    # honoured by both successor states) ratified by l. 2 mag. 1983, n. 303.
    "CHE": (943, 1978), "SVK": (303, 1983), "CZE": (303, 1983),
}

# Official annex of the Italian treaty text, keyed by act rather than country so
# successor states and historical versions share the same numbering.
ANNEX_OVERRIDES = {(445, 1989): 2, (319, 1995): 2, (303, 1983): 2}
_CHINA_HISTORICAL = (376, 1989)
_JAPAN_PROTOCOL = (413, 1981)

_CONV_KW_RE = re.compile(r"\b(?:convenzione|accordo|trattato)\b", I)
_ITAL_RE = re.compile(r"\bital(?:ia|o|ian[ao])\b", I)
# match the longest country names first ("regno unito" before "unito" fragments)
_COUNTRY_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in sorted(COUNTRIES, key=len, reverse=True)) + r")\b", I)

# Only dates that qualify the treaty name are version cues. An unrelated year in
# the surrounding discussion (e.g. a tax period or a judgment) must not select it.
_DATE_TEXT = (
    r"(?:(?:\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre)\s+)|(?:\d{1,2}[./-]\d{1,2}[./-]))?\d{4}"
)
_TREATY_DATE_RE = re.compile(
    r"\b(?:del(?:l['’]anno)?|(?:firmat[oa]|stipulat[oa]|sottoscritt[oa]|fatt[oa])"
    r"(?:\s+a\s+(?:Pechino|Tokyo))?\s+il)\s+(" + _DATE_TEXT + r")\b", I)
_BARE_DATE_RE = re.compile(r"(" + _DATE_TEXT + r")\b", I)
_RATIFICATION_RE = re.compile(
    r"^[\s,(]*(?:(?:ratificat[oa](?:\s+e\s+res[oa]\s+esecutiv[oa])?|"
    r"res[oa]\s+esecutiv[oa]|approvat[oa])\s+)?"
    r"(?:(?:con(?:\s+la)?|dalla|con\s+l[’'])\s*)?(?:legge|l\.)\s*"
    r"(?:(?:n\.?\s*)?(\d+)\s*/\s*(\d{4})\b|"
    r"(" + _DATE_TEXT + r")\s*,?\s*n\.?\s*(\d+)\b|"
    r"(?:n\.?\s*)?(\d+)\s+del\s+(" + _DATE_TEXT + r")\b)", I)
_PROTOCOL_PREFIX_RE = re.compile(
    r"\bprotocollo(?:\s+modificativo)?(?:\s+del\s+" + _DATE_TEXT + r")?\s+"
    r"(?:alla|della|di\s+modifica\s+della)\s*$", I)


def _version_cues(text: str, start: int, end: int):
    """Return the treaty year, ratification law and end of the date-qualified name.

    The law itself stays outside the name span: an explicit citation to the law
    remains a separate reference to the ratification act, without a treaty annex.
    """
    named_date = _TREATY_DATE_RE.search(text[start:end])
    tail = text[end:end + 180]
    stripped = tail.lstrip(" ,(")
    trailing_date = _TREATY_DATE_RE.match(stripped) or _BARE_DATE_RE.match(stripped)
    if trailing_date:
        named_date = trailing_date
        end += len(tail) - len(stripped) + trailing_date.end()
        tail = stripped[trailing_date.end():]
    year = int(named_date.group(1)[-4:]) if named_date else None
    ratification = _RATIFICATION_RE.match(tail)
    law = None
    if ratification:
        num1, year1, date2, num2, num3, date3 = ratification.groups()
        law = (int(num1 or num2 or num3), int(year1 or (date2 or date3)[-4:]))
    return year, law, end


def recognize_conventions(text: str) -> List[Span]:
    """Emit a law identity with its treaty annex; articles attach downstream.

    "Convenzione Italia-Giappone, art. 15" -> ``urn:nir:stato:legge:1972;855:1~art15``.
    The annex travels on the identity span so every article in a list inherits it.
    """
    spans: List[Span] = []
    for km in _CONV_KW_RE.finditer(text):
        win = text[km.start(): km.start() + 95]
        if not _ITAL_RE.search(win):
            continue
        cm = _COUNTRY_RE.search(win)
        if not cm:
            continue
        country = COUNTRIES.get(cm.group(1).lower(), "")
        nl = RATIFICA.get(country)
        if not nl:
            continue
        s, e = km.start(), km.start() + cm.end()
        cited_year, cited_law, e = _version_cues(text, s, e)
        if country == "CHN":
            if cited_law in {_CHINA_HISTORICAL, RATIFICA["CHN"]}:
                nl = cited_law
            elif cited_year in {1986, 1989}:
                nl = _CHINA_HISTORICAL
        elif country == "JPN":
            # The 1980 protocol is not the Convention ratified by law 855/1972.
            prefix_start = max(0, s - 100)
            protocol = _PROTOCOL_PREFIX_RE.search(text[prefix_start:s])
            if protocol:
                protocol_start = prefix_start + protocol.start()
                cited_year, cited_law, e = _version_cues(text, protocol_start, e)
                if cited_year in {1980, 1981} or cited_law == _JAPAN_PROTOCOL:
                    s, nl = protocol_start, _JAPAN_PROTOCOL
        num, yr = nl
        spans.append(Span(s, e, Entity.DOCTYPE, "L", text[s:e],
                          {"scope": "nazionale", "treaty": "1",
                           "annex": str(ANNEX_OVERRIDES.get(nl, 1))}))
        spans.append(Span(s, e, Entity.NUM_YEAR, f"{num}/{yr}", text[s:e],
                          {"number": str(num), "year": str(yr), "treaty": "1"}))
    return spans
