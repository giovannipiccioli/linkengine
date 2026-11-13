"""Partition numbers: one grammar for Latin ordinals, one glued spelling.

The spelling is shared with the VELEGART corpus (``utils/nir.py`` imports
``partition_number``), so a citation and the stored unit it names meet on the same key.
"""
import re

import pytest

from linkengine import LinkEngine, urn_to_text
from linkengine.normalize import LATIN_ORDINAL, PARTITION_NUMBER, partition_number

ENGINE = LinkEngine()


def _urns(text):
    return [row.get("urn") for row in ENGINE.extract(text).rows]


@pytest.mark.parametrize("raw, canonical", [
    ("360-bis", "360bis"),
    ("360 bis", "360bis"),
    ("360bis", "360bis"),
    ("360-BIS", "360bis"),
    ("2­ter", "2ter"),
    ("380-bis.1", "380bis.1"),
    ("380 bis.1", "380bis.1"),
    ("69-vicies-semel", "69viciessemel"),
    ("69-vicies semel", "69viciessemel"),
    ("2409-noviesdecies", "2409noviesdecies"),
    ("314/2", "314.2"),
    ("a-bis)", "abis"),
    ("1.", "1"),
    ("V-bis", "vbis"),
])
def test_partition_number_spelling(raw, canonical):
    assert partition_number(raw) == canonical
    assert partition_number(canonical) == canonical       # idempotent


# Every ordinal spelling in the Italian and EU corpora (articles, 2026-11-13), including
# the compound ones Normattiva writes with hyphens.
CORPUS_ORDINALS = """
bis ter quater quinquies sexies septies octies novies nonies decies undecies duodecies
terdecies quaterdecies quindecies quinquiesdecies sexdecies sexiesdecies sedecies septdecies
septiesdecies octodecies octiesdecies novodecies noviesdecies vicies unvicies univicies
duovicies tervicies quatervicies quinvicies sexvicies septvicies octovicies novovicies
duodevicies undevicies tricies undetricies duodetricies semel viciessemel viciesbis viciester
viciesquater viciesquinquies viciessexies viciessepties vicessemel vicesbis triciessemel
triciesbis vicies-semel septies-decies quater-quaterdecies bis-bis
""".split()


@pytest.mark.parametrize("word", CORPUS_ORDINALS)
def test_every_corpus_ordinal_is_recognized(word):
    assert re.fullmatch(LATIN_ORDINAL, word)


@pytest.mark.parametrize("word", ["terzo", "bisogna", "decimo", "sex", "un"])
def test_ordinary_words_are_not_ordinals(word):
    assert not re.fullmatch(LATIN_ORDINAL, word)


@pytest.mark.parametrize("text, urn", [
    # Before the shared grammar each of these named a different, existing article.
    ("art. 380-bis.1 c.p.c.", "urn:nir:stato:regio.decreto:1940;1443:1~art380bis.1"),
    ("art. 473-bis.12 c.p.c.", "urn:nir:stato:regio.decreto:1940;1443:1~art473bis.12"),
    ("art. 416-bis.1 c.p.", "urn:nir:stato:regio.decreto:1930;1398:1~art416bis.1"),
    ("art. 19-bis.1 del d.P.R. n. 633 del 1972",
     "urn:nir:presidente.repubblica:decreto:1972;633~art19bis.1"),
    ("art. 69-vicies semel del d.lgs. n. 385 del 1993",
     "urn:nir:stato:decreto.legislativo:1993;385~art69viciessemel"),
    ("art. 2409-noviesdecies c.c.", "urn:nir:stato:regio.decreto:1942;262:2~art2409noviesdecies"),
    ("art. 2-quaterdecies del d.lgs. n. 196 del 2003",
     "urn:nir:stato:decreto.legislativo:2003;196~art2quaterdecies"),
    # every level is glued, not only the article
    ("art. 1, comma 1, lettera a-bis), del d.lgs. n. 74 del 2000",
     "urn:nir:stato:decreto.legislativo:2000;74~art1-comma1-letabis"),
])
def test_suffixed_citations(text, urn):
    assert _urns(text) == [urn]


def test_a_plain_dotted_number_stays_article_and_comma():
    """In judgments "606.1 c.p.p." is shorthand for art. 606, comma 1, so only a dotted
    level that follows an ordinal belongs to the article number."""
    assert re.fullmatch(PARTITION_NUMBER, "380-bis.1")
    assert not re.fullmatch(PARTITION_NUMBER, "606.1")


@pytest.mark.parametrize("urn, text", [
    ("urn:nir:stato:legge:2000;212~art6bis-comma3bis", "art. 6-bis comma 3-bis"),
    ("urn:nir:stato:regio.decreto:1940;1443:1~art380bis.1", "art. 380-bis.1"),
    ("urn:nir:stato:decreto.legislativo:2000;74~art1-comma1-letabis", "art. 1 comma 1 let. a-bis"),
])
def test_urn_to_text_writes_the_ordinal_as_printed(urn, text):
    assert urn_to_text(urn).startswith(text)
