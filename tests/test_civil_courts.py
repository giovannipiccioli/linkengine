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


def test_named_and_detached_courts_render_the_judicial_name():
    assert urns("Tribunale Napoli Nord n. 2/2025") == ["ECLI:IT:TRIBNAN:2025:2"]
    assert urn_to_text("ECLI:IT:TRIBNAN:2025:2") == "Tribunale di Napoli Nord n. 2/2025"
    assert urn_to_text("ECLI:IT:CAPPSS:2025:2") == (
        "Corte d'Appello di Cagliari, sezione distaccata di Sassari n. 2/2025")
