"""
Corte EDU (European Court of Human Rights): the identifier, the dictionary and the renderer.

A Strasbourg judgment is cited by its parties, not by a number and a year::

    Corte EDU, Grande Camera, sentenza 23 febbraio 2017, de Tommaso c. Italia

Its identifier is the official ECLI, ``ECLI:CE:ECHR:2017:0223JUD004339509``: one string per
judgment, equal for every citation of it. Two things make that possible.

* The ECLI is a function of the delivery date and the first application number (year, month,
  day, ``JUD`` or ``DEC``, the number padded to 7 digits, the year of lodging on 2 digits):
  ``ecli_from_application``. It reproduces 21,758 of the 21,760 judgments of the HUDOC
  metadata, so a citation that gives both needs no data.
* A citation that gives only the parties is looked up in ``data/echr_judgments.tsv.gz``, one
  line per judgment of the HUDOC metadata (built by ``tools/build_echr_index.py``, about
  270 KB). The lookup key is the *parties field* ``<applicant>[_<n>]:<STATE>[+<STATE>…]`` with
  the date: the first applicant folded to lower-case ASCII, the Court's own ordinal when
  there is one, the respondent as the HUDOC three-letter code. The same function folds the
  citation and the HUDOC case name, so the two meet. The parties field is a lookup key, not
  an identifier: when it does not name exactly one judgment the citation has no ``urn``.

Resolution statuses: ``resolved`` (one judgment), ``probable`` (the date and the state fix one
judgment, and the name is alike or is a pseudonymisation placeholder), ``ambiguous`` (several
judgments fit: the candidates are returned, none is guessed), ``not_found``.
"""
from __future__ import annotations

import gzip
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ── states ────────────────────────────────────────────────────────────────────
# HUDOC respondent code -> spellings met in Italian prose, English and French; the first is
# the Italian name used when a citation is rendered.
STATE_NAMES: Dict[str, List[str]] = {
    "ITA": ["Italia", "Italy", "Italie", "Repubblica italiana"],
    "FRA": ["Francia", "France", "Repubblica francese"],
    "DEU": ["Germania", "Germany", "Allemagne", "Repubblica federale di Germania",
            "Repubblica federale tedesca"],
    "GBR": ["Regno Unito", "Regno Unito di Gran Bretagna e Irlanda del Nord",
            "Regno Unito di Gran Bretagna", "Gran Bretagna", "Great Britain", "United Kingdom",
            "U.K.", "UK", "Royaume-Uni"],
    "CHE": ["Svizzera", "Switzerland", "Suisse"],
    "AUT": ["Austria", "Autriche"],
    "BEL": ["Belgio", "Belgium", "Belgique"],
    "NLD": ["Paesi Bassi", "Olanda", "Netherlands", "Pays-Bas"],
    "LUX": ["Lussemburgo", "Luxembourg"],
    "ESP": ["Spagna", "Spain", "Espagne"],
    "PRT": ["Portogallo", "Portugal"],
    "GRC": ["Grecia", "Greece", "Grèce", "Grece"],
    "TUR": ["Turchia", "Turkey", "Turquie", "Türkiye"],
    "CYP": ["Cipro", "Cyprus", "Chypre"],
    "MLT": ["Malta"],
    "IRL": ["Irlanda", "Ireland", "Irlande"],
    "DNK": ["Danimarca", "Denmark", "Danemark"],
    "SWE": ["Svezia", "Sweden", "Suède", "Suede"],
    "NOR": ["Norvegia", "Norway", "Norvège", "Norvege"],
    "FIN": ["Finlandia", "Finland", "Finlande"],
    "ISL": ["Islanda", "Iceland", "Islande"],
    "LIE": ["Liechtenstein"],
    "SMR": ["San Marino", "Saint-Marin"],
    "AND": ["Andorra", "Andorre"],
    "MCO": ["Monaco"],
    "POL": ["Polonia", "Poland", "Pologne"],
    "CZE": ["Repubblica ceca", "Repubblica Ceca", "Rep. ceca", "Czech Republic",
            "République tchèque", "Republique tcheque"],
    "SVK": ["Slovacchia", "Slovakia", "Slovaquie", "Repubblica slovacca"],
    "HUN": ["Ungheria", "Hungary", "Hongrie"],
    "ROU": ["Romania", "Roumanie"],
    "BGR": ["Bulgaria", "Bulgarie"],
    "HRV": ["Croazia", "Croatia", "Croatie"],
    "SVN": ["Slovenia", "Slovénie", "Slovenie"],
    "SRB": ["Serbia", "Serbie"],
    "MNE": ["Montenegro"],
    "BIH": ["Bosnia-Erzegovina", "Bosnia ed Erzegovina", "Bosnia e Erzegovina",
            "Bosnia Erzegovina", "Bosnia and Herzegovina", "Bosnie-Herzégovine", "Bosnia"],
    "ALB": ["Albania", "Albanie"],
    "MKD": ["Macedonia del Nord", "ex Repubblica jugoslava di Macedonia",
            "ex Repubblica Jugoslava di Macedonia", "North Macedonia", "Macedonia"],
    "MDA": ["Moldavia", "Repubblica di Moldova", "Repubblica di Moldavia", "Moldova"],
    "UKR": ["Ucraina", "Ukraine"],
    "RUS": ["Russia", "Federazione russa", "Federazione Russa", "Russian Federation", "Russie"],
    "GEO": ["Georgia", "Géorgie", "Georgie"],
    "ARM": ["Armenia", "Arménie"],
    "AZE": ["Azerbaigian", "Azerbaijan", "Azerbaïdjan", "Azerbaidjan"],
    "LTU": ["Lituania", "Lithuania", "Lituanie"],
    "LVA": ["Lettonia", "Latvia", "Lettonie"],
    "EST": ["Estonia", "Estonie"],
}

_FOLD_MAP = str.maketrans({
    "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ð": "d", "þ": "th",
    "ı": "i", "İ": "I", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss", "ħ": "h"})


def fold(text: str) -> str:
    """Lower-case, accent-free (ł ø ß þ ı included)."""
    text = unicodedata.normalize("NFKD", text.translate(_FOLD_MAP))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


_ALIAS_TO_STATE: Dict[str, str] = {}
for _iso, _names in STATE_NAMES.items():
    for _n in _names:
        _ALIAS_TO_STATE[re.sub(r"[^a-z]+", "", fold(_n))] = _iso


def state_code(name: str) -> str:
    """HUDOC code of a state named in Italian, English or French; '' when it is not one."""
    name = re.sub(r"^(?:(?:the|la|lo|le)\s+|l['’]\s*)", "", name.strip(), flags=re.I)
    return _ALIAS_TO_STATE.get(re.sub(r"[^a-z]+", "", fold(name)), "")


def state_name(code: str) -> str:
    return STATE_NAMES[code][0] if code in STATE_NAMES else code


def _alt(names: Iterable[str]) -> str:
    return "|".join(re.escape(n).replace(r"\ ", r"\s+").replace(r"\-", r"[\-‑]")
                    for n in sorted(names, key=len, reverse=True))


#: a regex alternation of every state spelling, longest first
STATE_ALT = _alt(n for names in STATE_NAMES.values() for n in names)

# ── the applicant ─────────────────────────────────────────────────────────────
_LEGAL_FORMS = {"srl", "spa", "sa", "sas", "snc", "sarl", "ltd", "limited", "gmbh", "inc",
                "as", "ag", "bv", "nv", "oy", "ab", "ooo", "zao", "oao", "sro", "kft", "sl",
                "plc", "llc", "co", "cie", "scarl", "arl", "sapa", "sasu", "eood", "ood", "ad"}
# the first applicant ends where a conjunction, a comma or a semicolon begins
_FIRST_APPLICANT_END = re.compile(
    r"\s*[,;]\s*|\s+(?:e|ed|and|et|und|y|&)\s+|\s&\s|\s+(?:con|with|vs?\.?)\s+", re.I)
_PARENS = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_OTHERS_TAIL = re.compile(
    r"\b(?:e|ed|and|et|und)\s+(?:\d+\s+)?(?:altri|altre|altro|others?|autres?|a\.)(?:\b|\s|$).*$", re.I)
#: what the pseudonymisers of the merito corpora leave for a name
PLACEHOLDER = re.compile(r"^(?:per|sogg|parte|controparte|nominativo|pt|cp|lgn|persona|societa|"
                         r"azienda|ricorrente|resistente)(?:-?\d+)?(?:-\d+)?$")


def _slug_of(s: str) -> str:
    s = s.replace(".", "")                       # G.I.E.M. -> GIEM, S.r.l. -> srl
    toks = re.sub(r"[^a-z0-9]+", " ", s).split()
    while len(toks) > 1 and toks[-1] in _LEGAL_FORMS:
        toks.pop()
    merged: List[str] = []                       # "S. H." and "S.H." are the same initials
    for t in toks:
        if merged and len(t) == 1 and len(merged[-1]) == 1 and t.isalpha() and merged[-1].isalpha():
            merged[-1] += t
        else:
            merged.append(t)
    slug = "-".join(merged)
    # a state as applicant (an inter-state case) is the same state in any language
    state = _ALIAS_TO_STATE.get(slug.replace("-", ""))
    return state.lower() if state else slug


def applicant_slug(name: str) -> str:
    """The first applicant of a case name: 'Grande Stevens e altri' -> 'grande-stevens',
    'G.I.E.M. S.r.l.' -> 'giem', 'Sporrong e Lönnroth' -> 'sporrong'. Cutting at the first
    conjunction is symmetrical (it is applied to HUDOC names too), so it can only make two
    judgments share a slug, never make a citation miss its judgment."""
    s = _PARENS.sub(" ", fold(name)).replace("’", "'").replace("`", "'")
    return _slug_of(_FIRST_APPLICANT_END.split(s.strip(), maxsplit=1)[0])


def applicant_segments(name: str) -> List[str]:
    """Every applicant named, in order ('Sporrong e Lönnroth' -> ['sporrong', 'lonnroth'])."""
    s = _PARENS.sub(" ", fold(name)).replace("’", "'").replace("`", "'")
    s = _OTHERS_TAIL.sub("", s)
    segs = [_slug_of(x) for x in _FIRST_APPLICANT_END.split(s.strip()) if x and x.strip()]
    return [x for x in segs if x and x not in ("e", "and", "et")]


def parties_field(applicant: str, states: Iterable[str], ordinal: int = 0) -> str:
    """``de-tommaso:ITA``, ``scoppola_2:ITA``, ``a:NOR``: the lookup key of a citation, or ''
    when the applicant or the state is missing."""
    slug = applicant_slug(applicant)
    resp = sorted({s for s in states if s})
    if not slug or not resp:
        return ""
    return f"{slug}{'_%d' % ordinal if ordinal else ''}:{'+'.join(resp)}"


def split_parties(parties: str) -> Tuple[str, int, Tuple[str, ...]]:
    """'scoppola_2:ITA' -> ('scoppola', 2, ('ITA',))."""
    m = re.fullmatch(r"([a-z0-9][a-z0-9-]*?)(?:_(\d+))?:([A-Z]{3}(?:\+[A-Z]{3})*)", parties or "")
    if not m:
        return "", 0, ()
    return m.group(1), int(m.group(2) or 0), tuple(m.group(3).split("+"))


# ── the ECLI by rule ──────────────────────────────────────────────────────────
def ecli_from_application(date: str, appno: str, kind: str = "JUD") -> str:
    """``ECLI:CE:ECHR:2017:0223JUD004339509`` from ``2017-02-23`` and ``43395/09``."""
    m = re.fullmatch(r"(\d{1,5})\s*/\s*(\d{2})", (appno or "").strip())
    d = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date or "")
    if not (m and d):
        return ""
    return f"ECLI:CE:ECHR:{d[1]}:{d[2]}{d[3]}{kind}{int(m[1]):07d}{m[2]}"


_ECLI = re.compile(r"ECLI:CE:ECHR:(\d{4}):(\d{2})(\d{2})(JUD|DEC)(\d{7})(\d{2})")


def parse_ecli(ecli: str):
    """(date, kind, application number) of an ECHR ECLI, or None."""
    m = _ECLI.fullmatch((ecli or "").strip())
    if not m:
        return None
    return f"{m[1]}-{m[2]}-{m[3]}", m[4], f"{int(m[5])}/{m[6]}"


# ── the dictionary ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Judgment:
    ecli: str
    respondents: Tuple[str, ...]
    ordinal: int
    applicant: str                  # slug of the first applicant
    alts: Tuple[str, ...]           # slugs of the others
    appnos: Tuple[str, ...]         # every application of the case, "43395/09"
    display: str                    # the case name for rendering, "De Tommaso"
    date: str = ""                  # delivery date, from the ECLI
    kind: str = "JUD"               # JUD | DEC


DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "echr_judgments.tsv.gz")


def read_judgments(path: str = DATA_FILE) -> List[Judgment]:
    out: List[Judgment] = []
    try:
        fh = gzip.open(path, "rt", encoding="utf-8")
    except OSError:
        return out
    with fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 7 or not _ECLI.fullmatch(p[0]):
                continue
            date, kind, _ = parse_ecli(p[0])
            out.append(Judgment(p[0], tuple(p[1].split("+")), int(p[2] or 0), p[3],
                                tuple(x for x in p[4].split("|") if x),
                                tuple(x for x in p[5].split("|") if x), p[6], date, kind))
    return out


@dataclass
class Resolution:
    status: str                      # resolved | probable | ambiguous | not_found
    how: str = ""
    candidates: List[Judgment] = field(default_factory=list)

    @property
    def ecli(self) -> str:
        return self.candidates[0].ecli if self.status in ("resolved", "probable") else ""


def name_score(cited: str, actual: str) -> float:
    """0..1: 1 for equal slugs or one inside the other (a given name, a particle), else the
    best character-level likeness of the slug or of one word of each (Zolotoukhine/Zolotukhin)."""
    if cited == actual:
        return 1.0
    a, b = set(cited.split("-")), set(actual.split("-"))
    if a <= b or b <= a:
        return 1.0
    best = SequenceMatcher(None, cited, actual).ratio()
    for x in a:
        for y in b:
            if len(x) >= 5 and len(y) >= 5:
                best = max(best, SequenceMatcher(None, x, y).ratio())
    return best


def _date_matches(cited: str, actual: str) -> bool:
    return bool(cited) and actual.startswith(cited)


class Index:
    """The judgments of the dictionary, searchable by what a citation gives."""

    def __init__(self, judgments: Iterable[Judgment]):
        self.all = list(judgments)
        self.by_resp_date: Dict[Tuple[str, str], List[Judgment]] = defaultdict(list)
        self.by_resp_name: Dict[Tuple[str, str], List[Judgment]] = defaultdict(list)
        self.by_appno: Dict[str, List[Judgment]] = defaultdict(list)
        self.by_ecli: Dict[str, Judgment] = {}
        for j in self.all:
            self.by_ecli[j.ecli] = j
            for a in j.appnos:
                self.by_appno[a].append(j)
            for r in j.respondents:
                self.by_resp_date[(r, j.date)].append(j)
                for name in (j.applicant,) + j.alts:
                    self.by_resp_name[(r, name)].append(j)

    @staticmethod
    def _uniq(js: Iterable[Judgment]) -> List[Judgment]:
        seen, out = set(), []
        for j in js:
            if j.ecli not in seen:
                seen.add(j.ecli)
                out.append(j)
        return out

    @staticmethod
    def _verdict(js: List[Judgment], how: str) -> Resolution:
        js = Index._uniq(js)
        if len(js) == 1:
            return Resolution("resolved", how, js)
        return Resolution("ambiguous", how, js) if js else Resolution("not_found")

    @staticmethod
    def _narrow(ordinal: int, js: List[Judgment]) -> List[Judgment]:
        # the ordinal is a soft filter: citers number the cases wrongly ("Hirst n. 1")
        if ordinal and len(js) > 1:
            by_n = [j for j in js if j.ordinal == ordinal]
            if by_n:
                return by_n
        return js

    def resolve(self, parties: str = "", date: str = "", appnos: Sequence[str] = (),
                kind: str = "") -> Resolution:
        """Resolve a citation. ``kind`` is "DEC" for an admissibility decision, "JUD" for a
        judgment, "" when the citation does not say (Italian prose calls judgments "decisioni")."""
        r = self._resolve(parties, date, tuple(appnos))
        if kind == "DEC":                  # a decision is never the judgment of the same case
            js = [j for j in r.candidates if j.kind == "DEC"]
            return self._verdict(js, r.how) if js else Resolution("not_found")
        return r

    def _resolve(self, parties: str, date: str, appnos: Tuple[str, ...]) -> Resolution:
        slug, ordinal, states = split_parties(parties)
        # 1. the application number names the case; the date picks among its judgments
        js = self._uniq(j for a in appnos for j in self.by_appno.get(a, ()))
        if js:
            if date:
                dated = [j for j in js if _date_matches(date, j.date)]
                if dated:
                    return self._verdict(dated, "appno+date")
                if len(date) == 10:
                    return Resolution("not_found", "appno-other-date")
            elif len(js) == 1:
                return Resolution("resolved", "appno", js)
            else:
                return Resolution("ambiguous", "appno", js)
        if appnos:
            # an application the dictionary does not hold (a decision, a Commission report):
            # never the namesake judgment
            return Resolution("not_found", "appno-unknown")
        if not slug:
            return Resolution("not_found")
        resp_ok = lambda j: set(states) <= set(j.respondents)    # noqa: E731
        # 2. full date + state: the date fixes a handful of judgments, the name confirms
        if len(date) == 10:
            pool = self._uniq(j for j in self.by_resp_date.get((states[0], date), ()) if resp_ok(j))
            exact = [j for j in pool if slug in (j.applicant,) + j.alts]
            if exact:
                return self._verdict(self._narrow(ordinal, exact), "date+name")
            scored = [(j, max(name_score(slug, n) for n in (j.applicant,) + j.alts)) for j in pool]
            close = [j for j, sc in scored if sc >= 0.82]
            if close:
                return self._verdict(self._narrow(ordinal, close), "date+similar-name")
            if len(pool) == 1 and (PLACEHOLDER.match(slug) or scored[0][1] >= 0.70):
                return Resolution("probable", "date+state", pool)
        # 3. by name and state; a partial date (a year, a month) narrows
        pool = self._uniq(j for j in self.by_resp_name.get((states[0], slug), ()) if resp_ok(j))
        if date:
            # a full date that matches nothing names a decision, a Commission report or a typo:
            # another judgment of that year is not a better guess
            pool = [j for j in pool if _date_matches(date, j.date)]
        return self._verdict(self._narrow(ordinal, pool), "name+date" if date else "name")


_INDEX: Optional[Index] = None


def index() -> Index:
    """The packaged dictionary, loaded on first use."""
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(read_judgments())
    return _INDEX


def row_application(row) -> str:
    """The application number a feature row carries in ``number``/``year``: '43395/09'."""
    number, year = _g(row, "number"), _g(row, "year")
    if number.isdigit() and re.fullmatch(r"\d{4}", year):
        return f"{int(number)}/{year[2:]}"
    return ""


def _g(row, key: str) -> str:
    v = row.get(key) if hasattr(row, "get") else None
    return v if isinstance(v, str) else ("" if v is None or v != v else str(v))


def resolve_row(row) -> Resolution:
    """Resolution of the Corte EDU citation a feature row describes."""
    appno = row_application(row)
    return index().resolve(_g(row, "parties"), _g(row, "doc-date"), [appno] if appno else [],
                           "DEC" if _g(row, "doc-type") == "DEC" else "")


# ── rendering ─────────────────────────────────────────────────────────────────
_MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
              "settembre", "ottobre", "novembre", "dicembre"]


def ecli_to_text(ecli: str) -> str:
    """'ECLI:CE:ECHR:2017:0223JUD004339509' -> 'Corte EDU, sentenza 23 febbraio 2017,
    De Tommaso c. Italia, ricorso n. 43395/09'. The date and the application number come from
    the identifier; the parties from the dictionary when it knows the judgment."""
    parsed = parse_ecli(ecli)
    if not parsed:
        return ""
    date, kind, appno = parsed
    y, m, d = date.split("-")
    when = f"{int(d)}{'°' if int(d) == 1 else ''} {_MONTHS_IT[int(m) - 1]} {y}"
    parts = ["Corte EDU", f"{'sentenza' if kind == 'JUD' else 'decisione'} {when}"]
    j = index().by_ecli.get(ecli)
    if j:
        name = j.display + (f" (n. {j.ordinal})" if j.ordinal else "")
        parts.append(f"{name} c. {' e '.join(state_name(r) for r in j.respondents)}")
    parts.append(f"ricorso n. {appno}")
    return ", ".join(parts)


# ── display name of a HUDOC case name (used when the dictionary is built) ─────
_LEGAL_DISPLAY = {"srl": "S.r.l.", "spa": "S.p.A.", "sas": "S.a.s.", "snc": "S.n.c."}


def display_name(applicants: str) -> str:
    """'DE TOMMASO' -> 'De Tommaso'; 'G.I.E.M. S.R.L. AND OTHERS' -> 'G.I.E.M. S.r.l. e altri'."""
    s = _PARENS.sub(lambda m: m.group(0), applicants.strip())
    tail = ""
    m = _OTHERS_TAIL.search(s)
    if m:
        s, tail = s[:m.start()].rstrip(" ,"), " e altri"
    s = re.sub(r"\s+(?:AND|ET|&|and|et)\s+", " e ", s)

    def word(w: str) -> str:
        bare = re.sub(r"[^A-Za-z]", "", w).lower()
        if bare in _LEGAL_DISPLAY and w.isupper():
            return _LEGAL_DISPLAY[bare]
        if "." in w or not w.isupper():
            return w
        return w.title()

    return " ".join(word(w) for w in s.split()) + tail
