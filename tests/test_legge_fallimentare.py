"""Legge fallimentare (annex 1 of R.D. 267/1942): every way it is cited resolves to one identifier.

The alias follows the rules of the other codes. The full name is a reference by itself; an
abbreviation (``l. fall.``, ``legge fall.``, ``L.F.``, ``LF``) needs a partition, exactly like
``c.c.``, so a party's initials ("ricorso proposto da L.F.") are not a citation; and the text
cited through its decree (``art. 216 r.d. 267/1942``) is the same provision as ``art. 216 l. fall.``.
The excerpts are shortened from Cassazione decisions.
"""
import pytest

from linkengine import LinkEngine, urn_to_text
from linkengine.aliases import ALIASES
from linkengine.catalog import ALIAS_BY_DECREE

ENG = LinkEngine()
LF = "urn:nir:stato:regio.decreto:1942;267:1"        # the legge fallimentare (annex of the decree)
DECREE = "urn:nir:stato:regio.decreto:1942;267"      # the approving decree itself


def _urns(text):
    return sorted({r["urn"] for r in ENG.extract(text).rows if r["urn"]})


def _lf(*partitions):
    return sorted(f"{LF}~{p}" for p in partitions)


FULL_NAMES = ["legge fallimentare", "Legge Fallimentare", "l. fallimentare"]
ABBREVIATIONS = ["legge fall.", "legge fallim.", "l. fall.", "l.fall.", "L. Fall.", "L. fall",
                 "L.F.", "L. F.", "LF", "l.f.", "L.f."]
DECREE_FORMS = ["R.D. 16 marzo 1942 n. 267", "r.d. 16 marzo 1942, n. 267",
                "regio decreto 16 marzo 1942, n. 267", "r.d. n. 267/1942", "R.D. 267/42",
                "RD 267/1942", "r.d. n. 267 del 1942", "r.d. 16.3.1942 n. 267"]


# ── every spelling of the name, with a partition ─────────────────────────────

@pytest.mark.parametrize("name", FULL_NAMES + ABBREVIATIONS)
def test_spelling_resolves_to_the_annex(name):
    assert _urns(f"art. 216 {name}") == _lf("art216")


@pytest.mark.parametrize("name", FULL_NAMES + ABBREVIATIONS)
def test_spelling_is_the_alias(name):
    rows = ENG.extract(f"violazione dell'art. 67 {name}").rows
    assert [r["alias"] for r in rows] == ["LEGGE_FALL"]


@pytest.mark.parametrize("name", FULL_NAMES)
def test_period_closing_the_sentence_is_not_part_of_the_full_name(name):
    rows = ENG.extract(f"Si applica l'art. 216 {name}. Il ricorso e' fondato.").rows
    assert [r["urn"] for r in rows] == [f"{LF}~art216"]
    assert rows[0]["text"].lower().endswith("fallimentare")


@pytest.mark.parametrize("name", ["legge fall.", "l. fall.", "L. Fall."])
def test_period_of_an_abbreviation_belongs_to_it(name):
    rows = ENG.extract(f"Si applica l'art. 216 {name} Il ricorso e' fondato.").rows
    assert rows[0]["text"].endswith(name)


@pytest.mark.parametrize("name", ["legge fallimentare", "legge fall.", "l. fall.", "L.F."])
def test_name_before_the_partition(name):
    assert _urns(f"{name}, art. 216, comma 1") == _lf("art216-comma1")


# ── partitions ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("art. 216, comma 1, n. 2, L.F.", _lf("art216-comma1-num2")),
    ("art. 216, comma 1, n. 2, legge fall.", _lf("art216-comma1-num2")),
    ("art. 216, ult. comma, L.F.", _lf("art216")),
    ("art. 216 u.c. L.F.", _lf("art216")),
    ("art. 67, comma 3, lett. d), L.F.", _lf("art67-comma3-letd")),
    ("art. 67, II comma L.F.", _lf("art67-comma2")),
    ("art. 182-bis L.F.", _lf("art182bis")),
    ("art. 72 quater L.F.", _lf("art72quater")),
    ("artt. 216 e 223 L.F.", _lf("art216", "art223")),
    ("artt. 216 e 223 legge fall.", _lf("art216", "art223")),
    ("artt. 182 bis e 182 ter L.F.", _lf("art182bis", "art182ter")),
    ("art. 216 L.F.; art. 223 L.F.", _lf("art216", "art223")),
    ("(art. 216, comma 1, n. 2, e 223 L.F.)", _lf("art216-comma1-num2", "art223")),
    ("bancarotta fraudolenta (art. 216 L.F.)", _lf("art216")),
    ("l. fall., art. 216 e 223", _lf("art216", "art223")),
])
def test_partition_shapes(text, expected):
    assert _urns(text) == expected


# ── abbreviations alone are not citations (party initials) ───────────────────

@pytest.mark.parametrize("text", [
    "L.F.", "LF", "l.f.", "legge fall.", "legge fallim.", "l. fall.",
    "Svolgimento del processo L.F. propone ricorso per cassazione con",
    "ricorso proposto da L.F., elettivamente domiciliato in ROMA",
    "contro CURATELA FALLIMENTARE L.F. (C.F. (OMISSIS)), in persona del curatore",
    "Hanno presentato ricorso tramite i rispettivi difensori L. F., L.F., Sa.Li., L.G.",
    "il Tribunale dichiarava non doversi procedere nei confronti di L.F. in ordine al reato",
    "il teste L.F., poi, ha riferito solo cose apprese",
    "l'imputato LF ha proposto ricorso",
    "condannati in solido L.F. e G.V. al pagamento delle spese",
    "la vedova di L.F., G.V., nonche' i figli L.G. e L.B.",
    "il fratello del L.F. aveva esploso i colpi",
])
def test_bare_abbreviation_is_not_a_citation(text):
    assert _urns(text) == []


@pytest.mark.parametrize("name", ["legge fallimentare", "Legge Fallimentare"])
def test_full_name_alone_is_a_citation(name):
    assert _urns(f"si applica la {name} nella specie") == [LF]


# ── look-alikes that are not the legge fallimentare ──────────────────────────

@pytest.mark.parametrize("text", [
    "la legge fallimento",
    "legge fallimentari",
    "art. 216 legge fallimentarmente",
    "art. 5 del fallimento",
    "art. 216 fall",
])
def test_not_the_legge_fallimentare(text):
    assert LF not in _urns(text) and not any(u.startswith(LF + "~") for u in _urns(text))


def test_tuel_has_the_same_number_and_is_another_act():
    assert _urns("art. 5 d.lgs. 267/2000") == ["urn:nir:stato:decreto.legislativo:2000;267~art5"]
    assert _urns("art. 50 TUEL") == ["urn:nir:stato:decreto.legislativo:2000;267~art50"]
    assert _urns("art. 50 del d.lgs. 18 agosto 2000, n. 267") == [
        "urn:nir:stato:decreto.legislativo:2000;267~art50"]


def test_a_law_of_the_same_number_is_another_act():
    assert _urns("art. 5 legge 267/1942") == ["urn:nir:stato:legge:1942;267~art5"]


def test_budget_law_by_year_is_not_the_legge_fallimentare():
    # "legge finanziaria 2008" is law 244/2007 (budget_laws), never the L.F.
    assert _urns("art. 1, comma 335, della legge finanziaria 2005") == [
        "urn:nir:stato:legge:2004;311~art1-comma335"]


# ── cited through its decree ─────────────────────────────────────────────────

@pytest.mark.parametrize("decree", DECREE_FORMS)
def test_decree_form_with_article_is_the_annex(decree):
    assert _urns(f"art. 216 {decree}") == _lf("art216")


@pytest.mark.parametrize("decree", DECREE_FORMS[:3])
def test_decree_form_keeps_the_whole_partition(decree):
    assert _urns(f"art. 216, comma 1, n. 2, {decree}") == _lf("art216-comma1-num2")
    assert _urns(f"artt. 216 e 223 {decree}") == _lf("art216", "art223")
    assert _urns(f"art. 67, comma 3, lett. d), {decree}") == _lf("art67-comma3-letd")


@pytest.mark.parametrize("decree", DECREE_FORMS)
def test_decree_alone_stays_the_decree(decree):
    assert _urns(f"ai sensi del {decree}") == [DECREE]


@pytest.mark.parametrize("name", FULL_NAMES + ABBREVIATIONS)
@pytest.mark.parametrize("decree", DECREE_FORMS[:4])
def test_alias_form_and_decree_form_are_one_identifier(name, decree):
    assert _urns(f"art. 124 {name}") == _urns(f"art. 124 {decree}") == _lf("art124")


def test_decree_and_alias_named_together():
    # "art. 216 del R.D. ... n. 267 (legge fallimentare)": the article and the name agree
    urns = _urns("art. 216 del R.D. 16 marzo 1942, n. 267 (c.d. legge fallimentare - LF)")
    assert urns == sorted([f"{LF}~art216", LF])


def test_via_decree_only_for_the_declared_aliases():
    # another code approved by a decree keeps the decree identity until it is declared
    assert _urns("art. 2043 c.c.") == ["urn:nir:stato:regio.decreto:1942;262:2~art2043"]
    assert _urns("art. 4 r.d. 28 ottobre 1940, n. 1443") == [
        "urn:nir:stato:regio.decreto:1940;1443~art4"]


# ── registry ─────────────────────────────────────────────────────────────────

def test_via_decree_aliases_are_annexes_with_a_unique_decree():
    declared = [a for a in ALIASES if a.via_decree]
    assert [a.code for a in declared] == ["LEGGE_FALL"]
    for a in declared:
        assert a.nir.rsplit(":", 1)[1].isdigit(), f"{a.code} is not an annex of its decree"
    assert len(ALIAS_BY_DECREE) == len(declared)
    assert ALIAS_BY_DECREE == {"stato:regio.decreto:1942;267": "LEGGE_FALL"}


def test_alias_names_its_own_display():
    legge = next(a for a in ALIASES if a.code == "LEGGE_FALL")
    assert legge.display == "legge fallimentare"
    assert legge.nir == "stato:regio.decreto:1942-03-16;267:1"


# ── identifier -> text -> identifier ─────────────────────────────────────────

@pytest.mark.parametrize("partition", ["art216", "art67-comma1", "art182bis", "art124"])
def test_urn_to_text_round_trip(partition):
    urn = f"{LF}~{partition}"
    assert "legge fallimentare" in urn_to_text(urn)
    assert _urns(urn_to_text(urn)) == [urn]


def test_urn_to_text_of_the_act():
    assert urn_to_text(LF) == "legge fallimentare"
    assert urn_to_text(f"{LF}~art216") == "art. 216 legge fallimentare"


# ── context: the alias behaves like the other codes ──────────────────────────

def test_bare_article_inherits_the_legge_fallimentare():
    assert _urns("Si richiama l'art. 216 L.F. e, in particolare, l'art. 223.") == _lf("art216", "art223")
    assert _urns("Il giudice richiama la legge fallimentare e l'art. 67.") == _lf("art67")


def test_neighbouring_codes_do_not_mix():
    assert _urns("art. 360 c.p.c. e art. 216 L.F.") == sorted([
        "urn:nir:stato:regio.decreto:1940;1443:1~art360", f"{LF}~art216"])
    assert _urns("artt. 216 L.F. e 2043 c.c.") == sorted([
        f"{LF}~art216", "urn:nir:stato:regio.decreto:1942;262:2~art2043"])
    assert _urns("art. 10 d.lgs. 74/2000 e art. 216 l.fall.") == sorted([
        "urn:nir:stato:decreto.legislativo:2000;74~art10", f"{LF}~art216"])


# ── excerpts from Cassazione decisions ───────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("Con il secondo motivo si denuncia la violazione dell'art. 67 L.F.; art. 360 n. 3 CPC; omessa motivazione.",
     _lf("art67") + ["urn:nir:stato:regio.decreto:1940;1443:1~art360-num3"]),
    ("il reclamo previsto dall'art. 26 LF che costituisce un rimedio di tipo residuale",
     _lf("art26")),
    ("ha chiesto revocarsi ex art. 67 primo comma n. 2 L.F. il pagamento meglio indicato",
     _lf("art67-comma1-num2")),
    ("in opposizione allo stato passivo ex art. 98 L.F., infatti, la societa' ha dedotto",
     _lf("art98")),
    ("condannato per i delitti di cui agli artt. 216, comma 1, n. 2, e 223, comma 1, L.F. (fatti commessi in Pordenone)",
     _lf("art216-comma1-num2", "art223-comma1")),
    ("il giudizio ex art. 98 della L.F., ribadi' il rigetto della domanda",
     _lf("art98")),
    ("revoca ex art. 67 del R.D. 16 marzo 1942, n. 267 (l.f.) e dell'art. 2901 c.c.",
     _lf("art67") + ["urn:nir:stato:regio.decreto:1942;262:2~art2901"]),
    ("in relazione all'art. 216, comma 1, n. 2 L.F. (capo A) e, in relazione all'art. 216, comma 1, n. 1 L.F. (capo B)",
     _lf("art216-comma1-num2", "art216-comma1-num1")),
    ("la domanda ex art. 98 legge fall. contro lo stato passivo del fallimento",
     _lf("art98")),
    ("art. 161, comma 8, legge fall. come novellato dal D.Lgs. n. 5 del 2006",
     _lf("art161-comma8") + ["urn:nir:stato:decreto.legislativo:2006;5"]),
])
def test_excerpts_with_the_legge_fallimentare(text, expected):
    assert _urns(text) == sorted(expected)


@pytest.mark.parametrize("text, expected", [
    ("il Tribunale ha dichiarato L.F. colpevole dei reati di cui agli artt. 216, comma 1, n. 2, e 223 L.F.",
     _lf("art216-comma1-num2", "art223")),
    ("ricorso di L.F. avverso la sentenza, per violazione dell'art. 217 L.F.", _lf("art217")),
    ("Il ricorso di L.F., articolato in due motivi, e' fondato.", []),
    ("nei confronti di L.F. imputato del reato di cui all'art. 640 c.p.",
     ["urn:nir:stato:regio.decreto:1930;1398:1~art640"]),
])
def test_excerpts_with_party_initials(text, expected):
    assert _urns(text) == sorted(expected)


# ── known gaps (strict xfail: the day one is fixed the marker must go) ───────

@pytest.mark.xfail(strict=True, reason="an abbreviation read as a party's initials still lends its act "
                   "to a following bare article (propagation), as C.C. does")
@pytest.mark.parametrize("initials", ["C.C.", "L.F."])
def test_initials_do_not_lend_their_act_to_a_bare_article(initials):
    assert _urns(f"il ricorrente {initials} denuncia la violazione dell'art. 360 n. 3") == []


@pytest.mark.xfail(strict=True, reason="'l. f)' for lettera f) reads as the L.F.")
def test_lettera_f_is_not_the_legge_fallimentare():
    assert LF not in _urns("art. 5, comma 1, l. f)") and not any(
        u.startswith(LF + "~") for u in _urns("art. 5, comma 1, l. f)"))


@pytest.mark.xfail(strict=True, reason="'L.F. 2005' is the legge finanziaria, read as the L.F.")
def test_legge_finanziaria_abbreviated_is_not_the_legge_fallimentare():
    assert not any(u.startswith(LF) for u in _urns("art. 1, comma 335, della L.F. 2005"))
