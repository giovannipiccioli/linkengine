"""Corte EDU: citations written with the names of the parties, resolved to the ECLI."""
import json
import os

import pytest

from linkengine import LinkEngine, annotate_html, urn_to_text
from linkengine import echr

ENG = LinkEngine()


def _urns(text):
    return [r["urn"] for r in ENG.extract(text).rows]


# --- the identifier is the ECLI --------------------------------------------------------
def test_ecli_is_date_and_application():
    assert echr.ecli_from_application("2017-02-23", "43395/09") == "ECLI:CE:ECHR:2017:0223JUD004339509"
    assert echr.ecli_from_application("2017-02-23", "43395/09", "DEC").endswith("DEC004339509")
    assert echr.ecli_from_application("2017-02", "43395/09") == ""


@pytest.mark.parametrize("text", [
    "Corte EDU, Grande Camera, sentenza 23 febbraio 2017, de Tommaso c. Italia",
    "Corte EDU, sentenza del 23 febbraio 2017, ricorso n. 43395/09",
    "de Tommaso contro Italia, 23 febbraio 2017",
    "sentenza 23/02/2017 De Tommaso v. Italy",
    "Corte EDU, De Tommaso c. Italia, ric. n. 43395/09",       # one judgment of that application
])
def test_one_judgment_many_citations_one_string(text):
    assert _urns(text) == ["ECLI:CE:ECHR:2017:0223JUD004339509"]


def test_name_alone_resolves_when_it_names_one_judgment():
    assert _urns("la sentenza De Tommaso c. Italia ha affermato") == ["ECLI:CE:ECHR:2017:0223JUD004339509"]


def test_co_applicants_and_ordinals():
    assert _urns("Corte EDU, 4 marzo 2014, Grande Stevens e altri c. Italia") == \
        ["ECLI:CE:ECHR:2014:0304JUD001864010"]
    assert _urns("Corte EDU, 4 marzo 2014, Grande Stevens e a. c. Italia") == \
        ["ECLI:CE:ECHR:2014:0304JUD001864010"]
    assert _urns("Corte EDU, 17 settembre 2009, Scoppola c. Italia (n. 2)") == \
        ["ECLI:CE:ECHR:2009:0917JUD001024903"]


def test_eu_court_style_with_slash():
    assert _urns("sentenza del 12 febbraio 2008, Kafkaris/Cipro [GC]") == \
        ["ECLI:CE:ECHR:2008:0212JUD002190604"]


def test_list_of_judgments_each_with_its_date():
    text = "(sentenze del 19 febbraio 1998, Dalia c. Francia; 9 ottobre 2003, Slivenko c. Lettonia)"
    assert len(_urns(text)) == 2 and all(u.startswith("ECLI:CE:ECHR:") for u in _urns(text))


# --- no identifier rather than a wrong or an ambiguous one ------------------------------------
def test_ambiguous_citation_has_no_urn_and_lists_the_candidates():
    result = ENG.extract("Corte EDU, Scoppola c. Italia, sentenza della Grande Camera")
    assert [r["urn"] for r in result.rows] == [""]
    assert len(result.references[0].attrs["candidates"]) >= 2


def test_date_that_matches_no_judgment_is_not_the_neighbouring_one():
    assert _urns("Corte EDU, 2 giugno 2009, Daddi c. Italia") == [""]         # an inadmissibility decision


def test_unknown_application_is_not_resolved_to_the_namesake():
    assert _urns("Giza c. Polonia, (dee), n. 1997/11") == [""]


def test_bare_judgment_number_is_not_an_application():
    assert _urns("Corte EDU n. 123/2020") == [""]


def test_pseudonymised_applicant_resolves_by_date_and_state():
    assert _urns("Corte EDU, 29/11/2005, Per_1 c. Portogallo") == ["ECLI:CE:ECHR:2005:1129JUD007508801"]


def test_weak_candidate_is_kept_only_if_the_dictionary_names_it():
    assert _urns("le due amichevoli contro l'Irlanda a B.") == []
    assert _urns("Si veda Ferrazzini c. Italia.") == ["ECLI:CE:ECHR:2001:0712JUD004475998"]


# --- what is not Strasbourg --------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Corte di giustizia, 17 giugno 2010, Commissione c. Italia, C-423/08",
    "causa C-41/04, Levob Verzekeringen BV c. Paesi Bassi",
    "l'aggressione della Russia contro l'Ucraina",
    "la procedura d'infrazione (n. 2017/2114) contro l'Italia",
])
def test_not_a_strasbourg_citation(text):
    assert [u for u in _urns(text) if u.startswith("ECLI:CE")] == []


# --- the anchor is the whole citation ------------------------------------------------------
def test_anchor_includes_the_court_words():
    text = "Si veda Corte EDU, Grande Camera, sentenza 23 febbraio 2017, de Tommaso c. Italia, § 5."
    row = ENG.extract(text).rows[0]
    assert row["text"] == "Corte EDU, Grande Camera, sentenza 23 febbraio 2017, de Tommaso c. Italia"
    assert row["authority"] == "CEDU" and row["parties"] == "de-tommaso:ITA"
    assert 'data-urn="ECLI:CE:ECHR:2017:0223JUD004339509"' in annotate_html(text)


# --- urn_to_text ---------------------------------------------------------------------
def test_urn_to_text():
    assert urn_to_text("ECLI:CE:ECHR:2017:0223JUD004339509") == \
        "Corte EDU, sentenza 23 febbraio 2017, De Tommaso c. Italia, ricorso n. 43395/09"
    assert urn_to_text("ECLI:CE:ECHR:2018:0628JUD000182806") == \
        "Corte EDU, sentenza 28 giugno 2018, G.I.E.M. S.r.l. e altri c. Italia, ricorso n. 1828/06"
    # a judgment the dictionary does not hold still renders from the identifier alone
    assert urn_to_text("ECLI:CE:ECHR:2030:0101JUD000001230") == \
        "Corte EDU, sentenza 1° gennaio 2030, ricorso n. 12/30"


# --- the benchmark of real citations ----------------------------------------------------
GOLD = os.path.join(os.path.dirname(__file__), "gold", "gold_echr.jsonl")


def test_echr_gold():
    rows = [json.loads(l) for l in open(GOLD, encoding="utf-8")]
    bad = []
    for r in rows:
        urns = {u for u in _urns(r["text"]) if u.startswith("ECLI:CE:ECHR:")}
        if r["ecli"] and r["ecli"] not in urns or not r["ecli"] and urns:
            bad.append((r["text"], r["ecli"], urns))
    assert len(rows) >= 50
    assert len(bad) <= 1, bad
