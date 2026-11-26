"""Forms the Corte costituzionale's reference lists use, found by comparing linkengine with
the references a corpus check could not verify (refs_questioni_hallu.csv, 2026-11)."""
import pytest

from linkengine import LinkEngine

ENG = LinkEngine()


def _urns(text):
    return [r["urn"] for r in ENG.extract(text).rows]


@pytest.mark.parametrize("text, urn", [
    # statuti speciali: article and "Regione" are optional
    ("art. 6, Statuto speciale per la Sardegna", "urn:nir:stato:legge.costituzionale:1948;3~art6"),
    ("art. 57 Statuto speciale Trentino-Alto Adige", "urn:nir:stato:legge.costituzionale:1948;5~art57"),
    ("art. 14 Statuto speciale per la Regione siciliana", "urn:nir:stato:legge.costituzionale:1948;2~art14"),
    ("art. 5 Statuto Valle d’Aosta", "urn:nir:stato:legge.costituzionale:1948;4~art5"),
    ("art. 44 statuto speciale Friuli-Venezia Giulia", "urn:nir:stato:legge.costituzionale:1963;1~art44"),
    # legge cost. abbreviated
    ("art. 117 legge cost. 18 ottobre 2001 n. 3", "urn:nir:stato:legge.costituzionale:2001;3~art117"),
    ("art. 3 l. cost. n. 1/1963", "urn:nir:stato:legge.costituzionale:1963;1~art3"),
    # regional laws: hyphenated region, "autonoma", bilingual Aosta, demonym
    ("legge regionale Friuli-Venezia Giulia 13 novembre 2006, n. 22",
     "urn:nir:regione.friuli.venezia.giulia:legge:2006;22"),
    ("art. 2, legge della Regione autonoma Friuli-Venezia Giulia 21 aprile 2017, n. 9",
     "urn:nir:regione.friuli.venezia.giulia:legge:2017;9~art2"),
    ("art. 4 legge Regione Valle d’Aosta/Vallée d’Aoste 17 giugno 2009, n. 18",
     "urn:nir:regione.valle.aosta:legge:2009;18~art4"),
    ("legge Regione siciliana 16 maggio 1995, n. 5", "urn:nir:regione.sicilia:legge:1995;5"),
    # testo unico with a date: the year says the kind of act
    ("art. 39 T.U. 12 luglio 1934 n. 1214", "urn:nir:stato:regio.decreto:1934;1214~art39"),
    ("art. 67 T.U. 10 gennaio 1957 n. 3", "urn:nir:presidente.repubblica:decreto:1957;3~art67"),
    # the Convention under its official title
    ("art. 6, paragrafo 1, Convenzione europea per la salvaguardia dei diritti dell’uomo "
     "e delle libertà fondamentali", "CONV_EU_DIR_UOMO~art6-num1"),
    # the 1957 treaty
    ("art. 189, secondo comma, Trattato di Roma", "CELEX:11957E/TXT~art189-num2"),
    ("art. 192 Trattato istitutivo della CEE", "CELEX:11957E/TXT~art192"),
    ("art. 174 Trattato istitutivo della Comunità europea", "CELEX:12002E/TXT~art174"),
    # the year before the number
    ("art. 21 legge 1958, n. 311", "urn:nir:stato:legge:1958;311~art21"),
])
def test_form_is_read(text, urn):
    assert _urns(text) == [urn]


@pytest.mark.parametrize("text", [
    # a protocol's articles are not the Convention's
    "art. 1 Protocollo addizionale alla Convenzione per la salvaguardia dei diritti dell’uomo "
    "e delle libertà fondamentali",
    # Euratom is not the EEC
    "art. 164 Trattato istitutivo della CEEA",
    # the years between the kingdom and the republic say nothing about the kind of act
    "T.U. 10 gennaio 1947 n. 3",
])
def test_form_is_left_alone(text):
    assert _urns(text) == []


def test_costituzione_abbreviation_still_a_cost():
    assert _urns("art. 3 Cost.") == ["urn:nir:stato:costituzione~art3"]


def test_second_act_keeps_its_own_kind():
    # "l. n." used to swallow the number's "n.", and the second act took the first one's kind
    assert _urns("art. 5 d.lgs. n. 1/2012 e art. 11 l. n. 243/2012") == [
        "urn:nir:stato:decreto.legislativo:2012;1~art5", "urn:nir:stato:legge:2012;243~art11"]
    assert _urns("art. 11 l. n. 243/2012") == ["urn:nir:stato:legge:2012;243~art11"]


@pytest.mark.parametrize("text", [
    "art. 25 legge provinciale di Bolzano 29 marzo 1954, n. 1, modificata con legge provinciale 2 settembre 1955, n. 4",
    "legge prov. Bolzano 26 marzo 1982 n. 10",
    "legge della Provincia autonoma di Bolzano 12 dicembre 2016, n. 25",
])
def test_provincial_law_is_not_a_state_law(text):
    assert [u for u in _urns(text) if u] == []
