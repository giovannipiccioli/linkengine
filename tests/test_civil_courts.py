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
    "App. Roma", "C. App.", "Corte d'Assise d'Appello di Roma",
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
