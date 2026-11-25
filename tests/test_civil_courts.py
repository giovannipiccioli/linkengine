"""BDP civil office names, their citation spellings and canonical identifiers."""
import csv
from pathlib import Path

import pytest

from linkengine import LinkEngine, civil_court_ecli, urn_to_text
from linkengine.urn import build_urn


ENGINE = LinkEngine()
with (Path(__file__).parent / "gold" / "bdp_civil_offices.csv").open(encoding="utf-8") as f:
    OFFICES = list(csv.DictReader(f))


def urns(text):
    return [row["urn"] for row in ENGINE.extract(text).rows if row["urn"]]


@pytest.mark.parametrize("office", OFFICES, ids=[row["ufficio"] for row in OFFICES])
def test_bdp_office(office):
    name = office["ufficio"]
    expected = f"ECLI:IT:{office['court_code']}:2025:123"
    if name == "TRIBUNALE PER I MINORENNI":
        # Only BDP metadata provides the district for this cityless label.
        assert civil_court_ecli(name, 2025, 123) is None
        assert urns(name + ", sentenza n. 123/2025") == []
        name += " DI FIRENZE"
    assert civil_court_ecli(name, 2025, 123) == expected
    assert urns(name + ", sentenza n. 123/2025") == [expected]
    assert urns(urn_to_text(expected)) == [expected]


@pytest.mark.parametrize("name", (
    "Corte di Appello di Roma", "Corte d'Appello di Roma", "Corte d’Appello Roma",
    "Corte d Appello di Roma", "Corte appello Roma", "Corte App. Roma",
    "Corte d’App. di Roma", "C. d'App. Roma", "C. App. Roma", "C.App. di Roma",
))
def test_appeal_court_spellings(name):
    row, = ENGINE.extract(name + ", sentenza n. 42/2025").rows
    assert (row["authority"], row["city"], row["urn"]) == (
        "CORTE_APPELLO", "RM", "ECLI:IT:CAPPRM:2025:42")


@pytest.mark.parametrize("name", (
    "appello proposto a Roma", "C.A. Roma", "consiglio di amministrazione di Roma",
    "App.", "C. App.", "Corte d'Assise d'Appello di Roma",
))
def test_appeal_court_precision(name):
    rows = ENGINE.extract(name + ", sentenza n. 42/2025").rows
    assert all(row["authority"] != "CORTE_APPELLO" for row in rows)
    if "Assise" in name:
        assert [row["urn"] for row in rows] == ["ECLI:IT:ASSAPPRM:2025:42"]


def test_court_addressed_by_party_does_not_own_challenged_ruling():
    text = ("Voglia l'Ill.ma Corte di Appello di Trento, in parziale riforma "
            "dell'impugnata sentenza del Tribunale di Trento n. 391/2022")
    assert urns(text) == ["ECLI:IT:TRIBTN:2022:391"]


def test_separate_citations_keep_both_courts():
    text = "Tribunale di Cremona n. 5/2020; Tribunale di Crema n. 6/2021"
    assert urns(text) == ["ECLI:IT:TRIBCR:2020:5", "ECLI:IT:TRIBD142:2021:6"]


@pytest.mark.parametrize("name", (
    "TRIBUNALE DI NAPOLI SEDE IGNOTA", "TRIBUNALE DI NAPOLI EX TRIBUNALE DI SEDE IGNOTA",
    "TRIBUNALE DI NAPOLI SEZIONE DISTACCATA DI SEDE IGNOTA", "COMUNE DI NAPOLI NORD",
))
def test_unresolved_office_never_takes_parent_code(name):
    assert civil_court_ecli(name, 2025, 42) is None


@pytest.mark.parametrize("city, cadastral, province", [
    ("Trento", "L378", "TN"), ("Bolzano", "A952", "BZ"),
])
def test_province_on_courts_and_cadastral_code_on_municipalities(city, cadastral, province):
    assert urns(f"Giudice di pace di {city}, sentenza n. 42/2025") == [
        f"ECLI:IT:GDP{province}:2025:42"]
    assert urns(f"Comune di {city}, delibera n. 42/2025") == [f"DEL:CO{cadastral}:2025:42"]
    assert build_urn({"ref-type": "caselaw", "authority": "TRIB", "city": cadastral,
                      "year": "2025", "number": "42"}) == f"ECLI:IT:TRIB{province}:2025:42"
    assert urn_to_text(f"ECLI:IT:TRIB{cadastral}:2025:42") == f"Tribunale di {city} n. 42/2025"


@pytest.mark.parametrize("name", ("Corte di Appello di L’Aquila", "Corte d'Appello dell'Aquila"))
def test_aquila_articles(name):
    assert urns(f"{name}, sentenza n. 42/2025") == ["ECLI:IT:CAPPAQ:2025:42"]


@pytest.mark.parametrize("number", (None, "", "1.5", "inf", "non numerata"))
def test_structured_record_needs_a_decision_number(number):
    assert civil_court_ecli("Tribunale di Trento", 2025, number) is None


@pytest.mark.parametrize("name", (
    "TRIBUNALE SUPERIORE DELLE ACQUE PUBBLICHE", "Tribunale superiore delle acque pubbliche",
))
def test_superior_water_court_record(name):
    assert civil_court_ecli(name, 2024, 12) == "ECLI:IT:TSAP:2024:12"


@pytest.mark.parametrize("name", ("TRIBUNALE SUPERIORE DELLE ACQUE PUBBLICHE DI ROMA", "TRIBUNALE SUPERIORE"))
def test_superior_water_court_record_needs_its_exact_name(name):
    assert civil_court_ecli(name, 2024, 12) is None


def test_superior_water_court_record_needs_a_number():
    assert civil_court_ecli("TRIBUNALE SUPERIORE DELLE ACQUE PUBBLICHE", 2024, None) is None


@pytest.mark.parametrize("text", (
    "Tribunale Superiore delle Acque Pubbliche, sentenza n. 12/2024",
    "Tribunale superiore acque, sent. n. 12/2024",
    "Tribunale superiore delle acque, n. 12/2024",
    "T.S.A.P. n. 12/2024", "TSAP, sentenza n. 12/2024", "T. S. A. P., sent. n. 12/2024",
    "Trib. sup. acque pubbl., n. 12/2024", "Trib. sup. acque, sentenza n. 12/2024",
    "Tribunale superiore delle acque pubbliche, sent. 3 marzo 2024, n. 12",
    "sentenza del Tribunale superiore delle acque pubbliche n. 12 del 2024",
    "TSAP 3 marzo 2024 n. 12",
))
def test_superior_water_court_citations(text):
    row, = ENGINE.extract(text).rows
    assert (row["authority"], row["city"], row["urn"]) == ("TRIB_SUP_ACQUE", "", "ECLI:IT:TSAP:2024:12")


def test_superior_water_court_renders_and_reads_back():
    urn = "ECLI:IT:TSAP:2024:12"
    assert urn_to_text(urn) == "Tribunale Superiore delle Acque Pubbliche n. 12/2024"
    assert urns(urn_to_text(urn)) == [urn]


@pytest.mark.parametrize("text", (
    "TSAPP n. 12/2024",                                  # another word
    "il Tribunale superiore ha deciso, n. 12/2024",      # no court named
    "ricorso al Tribunale superiore delle acque pubbliche",  # no decision
))
def test_superior_water_court_precision(text):
    assert all("TSAP" not in u for u in urns(text))
    assert all(row["authority"] != "TRIB" for row in ENGINE.extract(text).rows)


def test_regional_water_court_is_not_the_superior_court():
    assert all("TSAP" not in u for u in urns(
        "Tribunale regionale delle acque pubbliche di Roma, sentenza n. 12/2024"))


@pytest.mark.xfail(strict=True, reason="Known gap: the regional water courts have no authority of "
                   "their own, so one sitting at a Corte d'appello takes that court's numbering.")
def test_regional_water_court_is_not_the_appeal_court():
    assert urns("Tribunale regionale delle acque pubbliche presso la Corte d'appello di Napoli, "
                "n. 45/2024") == []


def test_named_and_detached_courts_render_the_judicial_name():
    assert urns("Tribunale Napoli Nord n. 2/2025") == ["ECLI:IT:TRIBNAN:2025:2"]
    assert urn_to_text("ECLI:IT:TRIBNAN:2025:2") == "Tribunale di Napoli Nord n. 2/2025"
    assert urn_to_text("ECLI:IT:CAPPSS:2025:2") == (
        "Corte d'Appello di Cagliari, sezione distaccata di Sassari n. 2/2025")


# ── Registers: each register of a court numbers on its own ───────────────────────────────
# A tribunale or corte d'appello keeps several registers (contenzioso, lavoro, volontaria
# giurisdizione, ...) and each numbers its sentenze from 1 every year, so one ECLI could name
# two decisions. The register is a suffix on the number; the contenzioso register is the
# default and adds nothing (see catalog.CIVIL_REGISTERS).
from linkengine import catalog  # noqa: E402

BDP_RUOLI = {   # every ruolo of the BDP drop-down (read 2026-11-24) -> expected suffix; None = unresolved
    "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI": "",
    "CONTROVERSIE IN MATERIA DI LAVORO, PREV., ASSIST. OBBLIG.": "LAV",
    "GENERALE DEGLI AFFARI DI VOLONTARIA GIURISDIZIONE": "VG",
    # the sentenze of this ruolo (possessori, convalida di sfratto) are numbered with the contenzioso
    # register: 0.3% and 0.0% of them share a number with a contenzioso decision, against 16% for lavoro
    "PROCEDIMENTI SPECIALI SOMMARI": "",
    "MINORENNI": "",
    # almost no sentenze (6,327, 17, 2 and 14 in 2016-26) and not measured: no identifier
    "CONTROVERSIE AGRARIE": None,
    "GENERALE DELLE ESECUZIONI CIVILI": None,
    "GENERALE DELLE ESPROPRIAZIONI IMMOBILIARI": None,
    "GENERALE DEGLI AFFARI AMMINISTRATIVI, STRAGIUDIZIALI E NON CONTENZIOSI": None,
    # returned no decision when queried: whether it numbers with the contenzioso register
    # is unknown, so it must not silently take its identifiers
    "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI (CARTABIA)": None,
}


@pytest.mark.parametrize("ruolo, suffix", BDP_RUOLI.items(), ids=[r[:28] for r in BDP_RUOLI])
@pytest.mark.parametrize("court, code", (("Tribunale di Milano", "TRIBMI"), ("Corte di Appello di Roma", "CAPPRM"),
                                         ("TRIBUNALE DI NAPOLI NORD", "TRIBNAN"), ("CORTE DI APPELLO DI L'AQUILA", "CAPPAQ")))
def test_bdp_ruolo_gives_the_register_suffix(ruolo, suffix, court, code):
    expected = None if suffix is None else f"ECLI:IT:{code}:2025:123{suffix}"
    assert civil_court_ecli(court, 2025, 123, ruolo) == expected


@pytest.mark.parametrize("register", ("", None, "AC"))
def test_contenzioso_is_the_default_and_adds_nothing(register):
    assert civil_court_ecli("Tribunale di Milano", 2025, 123, register) == "ECLI:IT:TRIBMI:2025:123"


@pytest.mark.parametrize("code", sorted(catalog.CIVIL_REGISTERS))
def test_register_codes_are_accepted_as_they_are(code):
    assert civil_court_ecli("Tribunale di Milano", 2025, 123, code) == f"ECLI:IT:TRIBMI:2025:123{code}"


@pytest.mark.parametrize("register", ("LAVORO", "lav", "CIV", "SEZIONE LAVORO", "123", "GENERALE", "Lavoro e previdenza",
                                       "PS", "AG", "ESE", "ESP", "NC"))   # the last five are not series of the standard
def test_unknown_register_resolves_to_nothing_not_to_a_neighbour(register):
    assert civil_court_ecli("Tribunale di Milano", 2025, 123, register) is None


def test_every_bdp_register_code_has_a_name_and_every_ruolo_a_known_code():
    assert {code for code in catalog.BDP_RUOLO_REGISTER.values() if code} <= set(catalog.CIVIL_REGISTERS)
    assert set(catalog.CIVIL_REGISTERS) <= {code for code in catalog.BDP_RUOLO_REGISTER.values()}


@pytest.mark.parametrize("office", OFFICES, ids=[row["ufficio"] for row in OFFICES])
def test_every_bdp_office_takes_the_labour_suffix(office):
    name = office["ufficio"] + (" DI FIRENZE" if office["ufficio"] == "TRIBUNALE PER I MINORENNI" else "")
    assert civil_court_ecli(name, 2025, 123, "LAV") == f"ECLI:IT:{office['court_code']}:2025:123LAV"


def test_the_register_keeps_a_court_number_from_clashing_with_itself():
    ecli = {r: civil_court_ecli("Tribunale di Milano", 2024, 1234, r) for r in
            ("", "LAV", "VG")}
    assert len(set(ecli.values())) == len(ecli)


# ── Citations of a labour decision, as they are usually written ──────────────────────────
LABOUR_CITATIONS = (
    # tribunale: full name
    "Tribunale di Milano, sez. lav., 10 marzo 2020, n. 1234",
    "Tribunale di Milano, sezione lavoro, sentenza n. 1234/2020",
    "Tribunale di Milano, Sezione Lavoro, sent. n. 1234/2020",
    "Tribunale di Milano - Sezione Lavoro - sentenza n. 1234 del 2020",
    "Tribunale di Milano, sez. lavoro, sentenza del 10 marzo 2020, n. 1234",
    "Tribunale ordinario di Milano, sezione lavoro, sent. n. 1234/2020",
    "Tribunale di Milano, sezione lavoro e previdenza, sent. n. 1234/2020",
    "Tribunale di Milano, sezione controversie di lavoro, sentenza n. 1234/2020",
    "Tribunale di Milano, in funzione di giudice del lavoro, sentenza n. 1234/2020",
    # tribunale: "Trib." (the usual abbreviation)
    "Trib. Milano, sez. lav., 10 marzo 2020, n. 1234",
    "Trib. Milano, sez. lav., sent. n. 1234/2020",
    "Trib. Milano, Sez. Lav., 10.3.2020, n. 1234",
    "Trib. Milano, sez. lav., sent. 10/03/2020 n. 1234",
    "Trib. Milano, sez. lav., 10/3/2020, n. 1234",
    "Trib. Milano sez. lav. n. 1234/2020",
    "Trib. Milano, sez. lav., n. 1234/20",
    "Trib. Milano - sez. lavoro - sentenza n. 1234 del 2020",
    "Trib. di Milano, sez. lav., sent. n. 1234/2020",
    "Trib. Milano (sez. lav.), sent. n. 1234/2020",
    # a numbered or spelled-out section before "lavoro"
    "Trib. Milano, sez. II lav., sent. n. 1234/2020",
    "Trib. Milano, II sez. lav., sent. n. 1234/2020",
    "Trib. Milano, sez. 2 lav., sent. n. 1234/2020",
    "Tribunale di Milano, seconda sezione lavoro, sentenza n. 1234/2020",
    "Tribunale di Milano, sezione II lavoro, sentenza n. 1234/2020",
    "Tribunale di Milano, sezione seconda civile - lavoro, sentenza n. 1234/2020",
    # the judge instead of the section
    "Trib. Milano, Giudice del lavoro, sentenza n. 1234/2020",
    "Trib. Milano - Giudice del lavoro - sentenza n. 1234/2020",
    "Tribunale di Milano (Giudice del lavoro), sentenza n. 1234/2020",
    "Trib. Milano (lav.), n. 1234/2020",
    # the section before the court, as in running text
    "la sezione lavoro del Tribunale di Milano, con sentenza n. 1234/2020",
    "il Giudice del lavoro del Tribunale di Milano, con sentenza n. 1234/2020",
    "Sez. lav. del Tribunale di Milano, sent. n. 1234/2020",
    "la sezione lavoro presso il Tribunale di Milano, con sentenza n. 1234/2020",
)


@pytest.mark.parametrize("text", LABOUR_CITATIONS)
def test_labour_citation_of_a_tribunale(text):
    assert urns(text) == ["ECLI:IT:TRIBMI:2020:1234LAV"]


APPEAL_LABOUR_CITATIONS = (
    "Corte d'Appello di Milano, sez. lav., sent. n. 1234/2020",
    "Corte di Appello di Milano, sezione lavoro, 10 marzo 2020, n. 1234",
    "Corte d'appello di Milano, Sez. Lavoro, sentenza n. 1234 del 2020",
    "Corte d’Appello di Milano - Sezione Lavoro - sentenza n. 1234/2020",
    "Corte App. Milano, sez. lav., n. 1234/2020",
    "C. App. Milano, sez. lav., 10 marzo 2020, n. 1234",
    "C. d'App. Milano, sez. lav., n. 1234/2020",
    "Corte d'Appello di Milano, sez. lav., 10.3.2020, n. 1234",
    "Corte d'Appello di Milano, in funzione di giudice del lavoro, sentenza n. 1234/2020",
    "la sezione lavoro della Corte d'appello di Milano, con sentenza n. 1234/2020",
    "Corte d'appello di Milano, sez. lav., n. 1234/2020",
)


@pytest.mark.parametrize("text", APPEAL_LABOUR_CITATIONS)
def test_labour_citation_of_a_corte_d_appello(text):
    assert urns(text) == ["ECLI:IT:CAPPMI:2020:1234LAV"]


@pytest.mark.parametrize("text, expected", (
    ("Trib. Napoli Nord, sez. lav., n. 5/2023", "ECLI:IT:TRIBNAN:2023:5LAV"),
    ("Tribunale di Napoli Nord, sezione lavoro, sent. n. 5/2023", "ECLI:IT:TRIBNAN:2023:5LAV"),
    ("Trib. Roma, sez. IV lav., sent. n. 7/2022", "ECLI:IT:TRIBRM:2022:7LAV"),
    ("Tribunale di Roma, quarta sezione lavoro, sentenza n. 7/2022", "ECLI:IT:TRIBRM:2022:7LAV"),
    ("Trib. L'Aquila, sez. lav., n. 7/2022", "ECLI:IT:TRIBAQ:2022:7LAV"),
    ("Trib. Reggio Emilia, sez. lav., n. 7/2022", "ECLI:IT:TRIBRE:2022:7LAV"),
    ("Corte d'Appello di Roma, sezione lavoro, 22/6/2020, n. 3796", "ECLI:IT:CAPPRM:2020:3796LAV"),
))
def test_labour_citation_other_courts(text, expected):
    assert urns(text) == [expected]


# ── ...and the citations that must keep the bare number ──────────────────────────────────
BARE_CITATIONS = (
    "Tribunale di Milano n. 1234/2020",
    "Tribunale di Milano, sentenza n. 1234/2020",
    "Tribunale di Milano, sentenza 10 marzo 2020, n. 1234",
    "Trib. Milano n. 1234/2020",
    "Trib. Milano, sent. n. 1234/2020",
    "Trib. Milano, 10 marzo 2020, n. 1234",
    "Trib. Milano, 10.3.2020, n. 1234",
    "Trib. di Milano n. 1234/2020",
    # benches of the contenzioso register: the section does not change the number
    "Tribunale di Milano, sezione II civile, sentenza n. 1234/2020",
    "Trib. Milano, sez. II civ., n. 1234/2020",
    "Trib. Milano, sez. I, n. 1234/2020",
    "Tribunale di Milano, sezione specializzata in materia di impresa, sent. n. 1234/2020",
    "Tribunale di Milano, sez. fallimentare, sent. n. 1234/2020",
    "Tribunale di Milano, sezione immigrazione, sent. n. 1234/2020",
    # "lavoro" in the subject, not in the court's name
    "Tribunale di Milano, sentenza n. 1234/2020, in materia di lavoro",
    "Tribunale di Milano, sentenza n. 1234/2020 sul contratto di lavoro subordinato",
    "Tribunale di Milano n. 1234/2020 (licenziamento per giusta causa)",
)


@pytest.mark.parametrize("text", BARE_CITATIONS)
def test_citation_without_a_register_keeps_the_bare_number(text):
    assert urns(text) == ["ECLI:IT:TRIBMI:2020:1234"]


@pytest.mark.parametrize("text, expected", (
    ("Corte d'Appello di Milano, sentenza n. 1234/2020", "ECLI:IT:CAPPMI:2020:1234"),
    ("Corte d'Appello di Milano, sezione II civile, sentenza n. 1234/2020", "ECLI:IT:CAPPMI:2020:1234"),
    ("C. App. Milano, sez. I civ., n. 1234/2020", "ECLI:IT:CAPPMI:2020:1234"),
))
def test_appeal_citation_without_a_register_keeps_the_bare_number(text, expected):
    assert urns(text) == [expected]


# ── Neighbouring citations do not lend each other their section ──────────────────────────
@pytest.mark.parametrize("text, expected", (
    ("Trib. Milano n. 1234/2020 e Trib. Roma, sez. lav., n. 55/2021",
     ["ECLI:IT:TRIBMI:2020:1234", "ECLI:IT:TRIBRM:2021:55LAV"]),
    ("Trib. Milano, sez. lav., n. 1234/2020 e Trib. Roma n. 55/2021",
     ["ECLI:IT:TRIBMI:2020:1234LAV", "ECLI:IT:TRIBRM:2021:55"]),
    ("Trib. Milano, sez. lav., n. 1234/2020; Trib. Roma, sez. lav., n. 55/2021",
     ["ECLI:IT:TRIBMI:2020:1234LAV", "ECLI:IT:TRIBRM:2021:55LAV"]),
    ("Trib. Milano, sent. n. 1234/2020; Cass., sez. lav., n. 5/2020",
     ["ECLI:IT:TRIBMI:2020:1234", "ECLI:IT:CASS:2020:5CIV"]),
    ("Cass., sez. lav., n. 5/2020; Trib. Milano n. 1234/2020",
     ["ECLI:IT:CASS:2020:5CIV", "ECLI:IT:TRIBMI:2020:1234"]),
    ("Cass. civ., sez. lav., 10 marzo 2020, n. 5; Trib. Milano, sez. lav., n. 1234/2020",
     ["ECLI:IT:CASS:2020:5CIV", "ECLI:IT:TRIBMI:2020:1234LAV"]),
    ("Trib. Milano n. 1234/2020, confermata da Corte d'Appello di Milano, sez. lav., n. 77/2021",
     ["ECLI:IT:TRIBMI:2020:1234", "ECLI:IT:CAPPMI:2021:77LAV"]),
))
def test_each_citation_takes_its_own_section(text, expected):
    assert urns(text) == expected


# ── "Trib." abbreviates tributaria too: it must not read tax courts as a tribunale ───────
@pytest.mark.parametrize("text", (
    "Comm. trib. Milano n. 1234/2020",
    "Comm. trib. reg. Milano n. 1234/2020",
    "Commissione trib. Milano, sent. n. 1234/2020",
    "Cass., sez. trib. Milano n. 1234/2020",
    "sez. trib. Milano, sentenza n. 1234/2020",
    "Corte giust. trib. Milano, sent. n. 1234/2020",
))
def test_trib_before_a_city_inside_a_tax_court_is_not_a_tribunale(text):
    assert not any(":TRIB" in u for u in urns(text))


@pytest.mark.parametrize("text, expected", (
    ("Comm. trib. prov. di Milano, sentenza n. 100/2015", "ECLI:IT:CTPMI:2015:100"),
    ("C.T.P. Milano, sent. n. 100/2015", "ECLI:IT:CTPMI:2015:100"),
    ("Cass., sez. trib., n. 5000/2019", "ECLI:IT:CASS:2019:5000CIV"),
    ("Cass. civ., sez. lav., n. 5000/2019", "ECLI:IT:CASS:2019:5000CIV"),
))
def test_other_courts_are_unchanged(text, expected):
    assert urns(text) == [expected]


@pytest.mark.parametrize("text", ("Trib. n. 1234/2020", "Trib. sez. lav. n. 1234/2020", "il Trib. ha deciso, n. 1234/2020",
                                  "Trib. sup. acque, n. 12/2024"))
def test_trib_without_a_seat_is_not_a_tribunale(text):
    assert not any(":TRIBMI" in u or ":TRIBRM" in u for u in urns(text))


# ── Writing a labour identifier back as a citation ───────────────────────────────────────
@pytest.mark.parametrize("urn, text", (
    ("ECLI:IT:TRIBMI:2020:1234LAV", "Tribunale di Milano, sezione lavoro n. 1234/2020"),
    ("ECLI:IT:CAPPNA:2021:55LAV", "Corte d'Appello di Napoli, sezione lavoro n. 55/2021"),
    ("ECLI:IT:TRIBNAN:2023:5LAV", "Tribunale di Napoli Nord, sezione lavoro n. 5/2023"),
    ("ECLI:IT:TRIBMI:2020:1234", "Tribunale di Milano n. 1234/2020"),
))
def test_labour_identifier_renders_and_reads_back(urn, text):
    assert urn_to_text(urn) == text
    assert urns(text) == [urn]


@pytest.mark.parametrize("code, name", sorted(catalog.CIVIL_REGISTERS.items()))
def test_every_register_renders_by_name(code, name):
    assert urn_to_text(f"ECLI:IT:TRIBMI:2020:1234{code}") == f"Tribunale di Milano, {name} n. 1234/2020"
    assert urn_to_text(f"ECLI:IT:CAPPRM:2020:1234{code}") == f"Corte d'Appello di Roma, {name} n. 1234/2020"


def test_register_suffix_is_not_taken_for_a_civil_court_it_does_not_belong_to():
    # a number that merely ends in letters on another court is left alone
    assert urn_to_text("ECLI:IT:CASS:2020:1234CIV") == "Cassazione civile n. 1234/2020"
    assert urn_to_text("ECLI:IT:CONT:2023:89SGCAL").startswith("Corte dei Conti")


# ── "App. Milano", "CdA Milano", "Trib. Milano, lav.", procedimenti unitari ───────────────
@pytest.mark.parametrize("text, expected", (
    ("App. Milano, sez. lav., 12 marzo 2020, n. 245", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("App. Milano, sez. lavoro, sent. n. 245/2020", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("App. Milano, Sez. Lav., 12.3.2020, n. 245", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("App. Roma, n. 245/2020", "ECLI:IT:CAPPRM:2020:245"),
    ("App. Roma, sez. III civile, sentenza n. 245/2020", "ECLI:IT:CAPPRM:2020:245"),
    ("App. Roma, 12 marzo 2020, n. 245", "ECLI:IT:CAPPRM:2020:245"),
    ("App. Napoli, sez. lav., sent. n. 245/2020", "ECLI:IT:CAPPNA:2020:245LAV"),
    ("CdA Milano, sez. lav., n. 245/2020", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("C.d.A. Milano, sez. lav., 12.3.2020, n. 245", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("CdA Roma, sent. n. 245/2020", "ECLI:IT:CAPPRM:2020:245"),
    # the long forms are still read once, not twice
    ("C. App. Milano, sez. lav., n. 245/2020", "ECLI:IT:CAPPMI:2020:245LAV"),
    ("Corte App. Roma, n. 245/2020", "ECLI:IT:CAPPRM:2020:245"),
    ("Corte d'Appello di Milano, sez. lav., n. 245/2020", "ECLI:IT:CAPPMI:2020:245LAV"),
))
def test_short_appeal_court_citations(text, expected):
    assert urns(text) == [expected]


@pytest.mark.parametrize("text", (
    "App. n. 245/2020",                                   # no seat
    "il CdA ha deliberato n. 5/2020",                      # consiglio di amministrazione
    "il cda Milano n. 5/2020",                             # lower case is not the court
    "Corte dei conti, Sez. I App., sent. n. 653/2013-A",   # a Corte dei conti section
    "Corte dei conti, Sez. giur. App. Sicilia, n. 5/2020",
    "Corte dei conti, Sezione III centrale App. n. 12/2020",
))
def test_short_appeal_court_precision(text):
    assert all(not u.startswith("ECLI:IT:CAPP") for u in urns(text))


def test_a_short_appeal_court_does_not_lend_its_section_to_the_next_citation():
    assert urns("App. Roma, n. 5/2020; App. Milano, sez. lav., n. 6/2021") == [
        "ECLI:IT:CAPPRM:2020:5", "ECLI:IT:CAPPMI:2021:6LAV"]


@pytest.mark.parametrize("text, expected", (
    ("Trib. Milano, lav., n. 100/2020", "ECLI:IT:TRIBMI:2020:100LAV"),
    ("Trib. Milano, lavoro, n. 100/2020", "ECLI:IT:TRIBMI:2020:100LAV"),
    ("Trib. Milano - lav. - sent. n. 100/2020", "ECLI:IT:TRIBMI:2020:100LAV"),
    ("Tribunale di Milano, lav., sentenza n. 100/2020", "ECLI:IT:TRIBMI:2020:100LAV"),
    ("Trib. Milano, sent. n. 100/2020", "ECLI:IT:TRIBMI:2020:100"),
    ("Trib. Milano, sez. fallimentare, n. 100/2020", "ECLI:IT:TRIBMI:2020:100"),
))
def test_labour_written_without_the_word_section(text, expected):
    assert urns(text) == [expected]


def test_a_sentence_about_work_is_not_the_labour_section():
    assert not any(u.endswith("LAV") for u in urns("Il Tribunale di Milano ha riconosciuto il lavoro prestato, n. 100/2020"))


@pytest.mark.parametrize("text", (
    "Trib. Milano, P.U. n. 123/2024",
    "Trib. Milano, P.U. 123/2024",
    "Tribunale di Milano, procedimento unitario n. 123/2024",
    "Tribunale di Milano, proc. unitario n. 123/2024",
    "Trib. Milano, Proc. Unitario 123-1/2024",
    "App. Milano, procedimento unitario n. 123/2024",
))
def test_a_procedimento_unitario_is_not_taken_for_a_contenzioso_decision(text):
    """Numbered with the volontaria giurisdizione, which a citation is not read as: no identifier."""
    assert urns(text) == []


def test_a_procedimento_unitario_does_not_hide_the_next_citation():
    assert urns("Trib. Milano, P.U. n. 1/2024; Trib. Roma, n. 5/2023") == ["ECLI:IT:TRIBRM:2023:5"]


# ── Known gaps ───────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason="Known gap, left on purpose: only the labour register is read from a citation; "
                   "volontaria giurisdizione is rendered but never recognised.")
def test_volontaria_giurisdizione_reads_back():
    assert urns(urn_to_text("ECLI:IT:TRIBMI:2020:1234VG")) == ["ECLI:IT:TRIBMI:2020:1234VG"]


@pytest.mark.xfail(strict=True, reason="Known gap: the judge's title without any court name is not a court.")
def test_giudice_del_lavoro_without_a_court_name():
    assert urns("Giudice del lavoro di Milano, sent. n. 1234/2020") == ["ECLI:IT:TRIBMI:2020:1234LAV"]
