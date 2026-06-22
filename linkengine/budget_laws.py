"""
Legge finanziaria / legge di bilancio: the annual budget law named by its *budget year*
resolves to the enacting ``legge`` (number/year). The budget law for year Y is enacted in
(usually December of) Y-1, so "legge finanziaria 2008" -> legge 244/2007 and "legge di
bilancio 2023" -> legge 197/2022.

Like ``conventions.py``, this is a compact lookup **table + one recognizer**, NOT a per-entry
alias: the citation is parametrized by a year, so a single dict is clearer and lighter than
~50 alias records (see the module note in ``aliases.py``). The "finanziaria" (1979–2010) and
"di bilancio" (2000–2026) series are merged here — they coincide on the overlap (2000–2010).
"""
from __future__ import annotations

import re
from typing import List

from .model import Entity, Span

I = re.IGNORECASE

# budget year -> (legge number, enacting year)
BUDGET_LAW = {
    1979: (843, 1978), 1980: (146, 1980), 1981: (119, 1981), 1982: (181, 1982),
    1983: (130, 1983), 1984: (730, 1983), 1985: (887, 1984), 1986: (41, 1986),
    1987: (910, 1986), 1988: (67, 1988), 1989: (541, 1988), 1990: (407, 1989),
    1991: (405, 1990), 1992: (415, 1991), 1993: (500, 1992), 1994: (538, 1993),
    1995: (725, 1994), 1996: (550, 1995), 1997: (663, 1996), 1998: (450, 1997),
    1999: (449, 1998), 2000: (488, 1999), 2001: (388, 2000), 2002: (448, 2001),
    2003: (289, 2002), 2004: (350, 2003), 2005: (311, 2004), 2006: (266, 2005),
    2007: (296, 2006), 2008: (244, 2007), 2009: (203, 2008), 2010: (191, 2009),
    2011: (220, 2010), 2012: (183, 2011), 2013: (228, 2012), 2014: (148, 2013),
    2015: (190, 2014), 2016: (208, 2015), 2017: (232, 2016), 2018: (205, 2017),
    2019: (145, 2018), 2020: (160, 2019), 2021: (178, 2020), 2022: (234, 2021),
    2023: (197, 2022), 2024: (213, 2023), 2025: (207, 2024), 2026: (199, 2025),
}

# "legge finanziaria YYYY" / "finanziaria YYYY" / "legge (di) bilancio YYYY". A bare
# "bilancio YYYY" (no "legge") is too generic (a balance sheet / budget) and is NOT matched.
_BUDGET_RE = re.compile(
    r"\b(?:legge\s+(?:di\s+)?(?:finanziaria|bilancio)|finanziaria)\s+((?:19|20)\d{2})\b", I)


def recognize_budget_laws(text: str) -> List[Span]:
    """Emit a (DOCTYPE L + NUM_YEAR) pair for each budget law cited by year. The spans are
    flagged ``budget`` so the engine's overlap resolver drops the plain "legge" doctype / the
    bare year that otherwise match inside the same citation."""
    spans: List[Span] = []
    for m in _BUDGET_RE.finditer(text):
        nl = BUDGET_LAW.get(int(m.group(1)))
        if not nl:
            continue
        num, yr = nl
        s, e = m.start(), m.end()
        spans.append(Span(s, e, Entity.DOCTYPE, "L", text[s:e],
                          {"scope": "nazionale", "budget": "1"}))
        spans.append(Span(s, e, Entity.NUM_YEAR, f"{num}/{yr}", text[s:e],
                          {"number": str(num), "year": str(yr), "budget": "1"}))
    return spans
