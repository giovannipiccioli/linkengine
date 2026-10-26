"""Treaty identities checked against Normattiva on 2026-10-26.

Expected values are independent of the recognizer's tables. The 30-act audit includes
the historical China agreement; the new agreement and both Czech/Slovak names are
also covered. Article availability in the corpus is deliberately not tested here.
"""
import pytest

from linkengine import LinkEngine
from linkengine.urn import build_urn


ENG = LinkEngine()


def urns(text):
    return [row["urn"] for row in ENG.extract(text).rows if row["urn"]]


@pytest.mark.parametrize("name, act", [
    ("Svizzera", "1978;943:1"),
    ("Francia", "1992;20:1"),
    ("Germania", "1992;459:1"),
    ("Regno Unito", "1990;329:1"),
    ("Stati Uniti d'America", "2009;20:1"),
    ("Lussemburgo", "1982;747:1"),
    ("Giappone", "1972;855:1"),
    ("Paesi Bassi", "1993;305:1"),
    ("Portogallo", "1982;562:1"),
    ("Spagna", "1980;663:1"),
    ("Austria", "1984;762:1"),
    ("Romania", "2017;78:1"),
    ("Bulgaria", "1990;389:1"),
    ("Argentina", "1982;282:1"),
    ("Irlanda", "1974;583:1"),
    ("Cecoslovacchia", "1983;303:2"),
    ("Repubblica Ceca", "1983;303:2"),
    ("Repubblica Slovacca", "1983;303:2"),
    ("Cina del 1986", "1989;376:1"),
    ("Cina", "2024;182:1"),
    ("Polonia", "1989;97:1"),
    ("Tunisia", "1981;388:1"),
    ("Belgio", "1989;148:1"),
    ("India", "1995;319:2"),
    ("Malta", "1983;304:1"),
    ("Algeria", "1994;711:1"),
    ("Emirati Arabi Uniti", "1997;309:1"),
    ("Arabia Saudita", "2009;159:1"),
    ("Grecia", "1989;445:2"),
    ("Panama", "2016;208:1"),
    ("Venezuela", "1992;200:1"),
    ("Norvegia", "1987;108:1"),
    ("Singapore", "1978;575:1"),
    # Outside the audit: annex 1 is the explicitly requested default assumption.
    ("Albania", "1998;175:1"),
    ("Danimarca", "2002;170:1"),
])
@pytest.mark.parametrize("template, locator", [
    ("Convenzione Italia-{name}", ""),
    ("art. 15 della Convenzione Italia-{name}", "~art15"),
    ("Convenzione Italia-{name}, art. 15", "~art15"),
])
def test_treaty_annexes(name, act, template, locator):
    assert urns(template.format(name=name)) == [f"urn:nir:stato:legge:{act}{locator}"]


def test_annex_survives_article_lists_and_subpartitions():
    assert urns("artt. 4 e 15 della Convenzione Italia-India") == [
        "urn:nir:stato:legge:1995;319:2~art4",
        "urn:nir:stato:legge:1995;319:2~art15",
    ]
    rows = ENG.extract("art. 15, comma 2, della Convenzione Italia-Francia").rows
    assert len(rows) == 1
    row = rows[0]
    assert row["partition"] == "allegato-1_articolo-15_comma-2"
    assert row["urn"] == build_urn(row) == "urn:nir:stato:legge:1992;20:1~art15-comma2"
    assert row["url"].endswith(row["urn"])


def test_explicit_annex_is_not_duplicated():
    assert urns("allegato 2 della Convenzione Italia-Francia") == [
        "urn:nir:stato:legge:1992;20:2",
    ]


@pytest.mark.parametrize("law", ["20/1992", "319/1995", "855/1972", "413/1981",
                                      "376/1989", "182/2024"])
def test_ratification_law_citations_keep_their_own_identity(law):
    number, year = law.split("/")
    assert urns(f"art. 1 della legge n. {law}") == [
        f"urn:nir:stato:legge:{year};{number}~art1",
    ]


@pytest.mark.parametrize("name", [
    "Convenzione Italia-Cina del 1986",
    "Convenzione del 1986 tra Italia e Cina",
    "Convenzione Italia-Cina del 13 ottobre 1986",
    "Convenzione Italia-Cina del 13.10.1986",
    "Convenzione Italia-Cina del 1989",
    "Convenzione Italia-Cina 1986",
    "Convenzione Italia-Cina 13 ottobre 1986",
    "Accordo Italia-Cina, fatto a Pechino il 13 ottobre 1986",
    "Convenzione italo-cinese del 1986",
])
def test_china_historical_agreement_by_date(name):
    assert urns(name + ", art. 15") == ["urn:nir:stato:legge:1989;376:1~art15"]


@pytest.mark.parametrize("ratification", [
    "ratificata con legge 31 ottobre 1989, n. 376",
    "ratificata e resa esecutiva con legge n. 376 del 1989",
    "ratificata dalla legge 376/1989",
    "resa esecutiva con la legge 376 del 1989",
    "(l. 376/1989)",
])
def test_china_historical_agreement_by_ratification(ratification):
    assert urns("art. 15 della Convenzione Italia-Cina, " + ratification) == [
        "urn:nir:stato:legge:1989;376:1~art15",
        "urn:nir:stato:legge:1989;376",
    ]


@pytest.mark.parametrize("name", [
    "Convenzione Italia-Cina",
    "Convenzione Italia-Cina del 2019",
    "Convenzione del 2019 tra Italia e Cina",
    "Convenzione Italia-Cina del 23 marzo 2019",
    "Convenzione Italia-Cina del 2024",
])
def test_china_new_agreement(name):
    assert urns(name + ", art. 15") == ["urn:nir:stato:legge:2024;182:1~art15"]


def test_china_new_agreement_with_ratification():
    assert urns("art. 15 della Convenzione Italia-Cina, "
                "ratificata con legge 18 novembre 2024, n. 182") == [
        "urn:nir:stato:legge:2024;182:1~art15",
        "urn:nir:stato:legge:2024;182",
    ]


def test_signing_date_does_not_become_ratification_date():
    row, = ENG.extract("Convenzione Italia-Cina del 23 marzo 2019").rows
    assert row["year"] == "2024"
    assert row["doc-date"] == ""
    assert row["text"] == "Convenzione Italia-Cina del 23 marzo 2019"


def test_china_versions_stay_local_to_each_citation():
    assert urns("art. 15 della Convenzione Italia-Cina del 1986; "
                "art. 4 della Convenzione Italia-Cina del 2019") == [
        "urn:nir:stato:legge:1989;376:1~art15",
        "urn:nir:stato:legge:2024;182:1~art4",
    ]
    assert urns("Nel periodo d'imposta 1986 si richiama la Convenzione Italia-Cina.") == [
        "urn:nir:stato:legge:2024;182:1",
    ]
    assert urns("Convenzione Italia-Cina. La legge 376/1989 è citata separatamente.") == [
        "urn:nir:stato:legge:2024;182:1",
        "urn:nir:stato:legge:1989;376",
    ]


@pytest.mark.parametrize("name", [
    "Protocollo alla Convenzione Italia-Giappone del 1980",
    "Protocollo del 1980 alla Convenzione Italia-Giappone",
    "Protocollo modificativo della Convenzione Italia-Giappone del 1981",
])
def test_japan_1980_protocol_is_distinct(name):
    assert urns("art. 1 del " + name) == ["urn:nir:stato:legge:1981;413:1~art1"]


def test_japan_protocol_by_ratification():
    assert urns("art. 1 del Protocollo alla Convenzione Italia-Giappone, "
                "ratificato con legge 25 maggio 1981, n. 413") == [
        "urn:nir:stato:legge:1981;413:1~art1",
        "urn:nir:stato:legge:1981;413",
    ]


def test_unknown_ratification_law_is_not_invented():
    assert urns("Convenzione Italia-San Marino, art. 15") == []
