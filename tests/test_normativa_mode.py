"""Focused tests for the opt-in internal-reference rules used on legislation."""
import pytest

from linkengine import LinkEngine
from linkengine.normativa import INTERNAL_ATTR


ENGINE = LinkEngine()
TUIR_ART8 = "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art8"
GDPR_ART17 = "CELEX:32016R0679~art17"


def _result(text, unit=TUIR_ART8):
    return ENGINE.extract(text, mode="normativa", current_unit_urn=unit)


def _urns(text, unit=TUIR_ART8):
    return [row["urn"] for row in _result(text, unit).rows]


def test_standard_mode_remains_conservative_for_bare_partitions():
    text = "Salvo quanto stabilito dall'articolo 15. Resta fermo il comma 2."
    assert ENGINE.extract(text).rows == []
    assert _urns(text) == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art15",
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art8-comma2",
    ]


def test_article_lists_ranges_and_deep_partition_paths():
    assert _urns("Si applicano gli articoli 5-7.") == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art5",
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art6",
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art7",
    ]
    assert _urns("Si applica l'articolo 10, comma 2, lettera b), numero 3.") == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art10-comma2-letb-num3"
    ]


def test_backward_deictic_article_owns_the_preceding_comma():
    text = "Si applicano l'articolo 84, comma 2, e il comma 3 del medesimo articolo 84."
    assert _urns(text) == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art84-comma2",
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art84-comma3",
    ]


def test_present_article_and_present_comma_use_the_unit_locator():
    assert _urns("Per quanto non disposto dal presente articolo.") == [TUIR_ART8]
    comma_unit = TUIR_ART8 + "-comma3"
    assert _urns("Le regole del presente comma restano ferme.", comma_unit) == [comma_unit]


def test_subarticle_reference_inherits_current_article_but_not_an_unknown_parent():
    assert _urns("Si applicano i commi 1 e 3.") == [
        TUIR_ART8 + "-comma1",
        TUIR_ART8 + "-comma3",
    ]
    # An article unit does not tell us which comma contains an isolated letter.
    assert _urns("Si applica la lettera b).") == []
    assert _urns("Si applica il comma 2, lettera b).") == [TUIR_ART8 + "-comma2-letb"]


def test_explicit_external_act_keeps_precedence():
    text = "Si applica l'articolo 2 del decreto legislativo 31 dicembre 1992, n. 546."
    assert _urns(text) == ["urn:nir:stato:decreto.legislativo:1992;546~art2"]


@pytest.mark.parametrize("unit", [TUIR_ART8, GDPR_ART17])
@pytest.mark.parametrize("text", [
    "Si applica l'articolo 2 del decreto legislativo 31 dicembre 1992, n. 546.",
    "Si applica l'articolo 3, paragrafo 1, del regolamento (CE) n. 258/97.",
    "Si veda la direttiva (UE) 2019/1937.",
    "Si veda Cass. civ., sentenza n. 123/2020.",
])
def test_complete_external_citations_are_identical_in_both_modes(text, unit):
    standard = ENGINE.extract(text)
    normativa = ENGINE.extract(text, mode="normativa", current_unit_urn=unit)
    assert normativa.rows == standard.rows


def test_eu_unit_resolves_articles_paragraphs_and_letters_to_celex():
    assert _urns(
        "Si applicano l'articolo 6, paragrafo 1, lettera a), e il paragrafo 2.",
        GDPR_ART17,
    ) == [
        "CELEX:32016R0679~art6-num1-leta",
        "CELEX:32016R0679~art6-num2",
    ]


def test_eu_unit_resolves_recitals_and_annexes():
    assert _urns("Restano fermi il considerando 12 e l'allegato IV.", GDPR_ART17) == [
        "CELEX:32016R0679~cons12",
        "CELEX:32016R0679~all4",
    ]


def test_present_act_qualifier_routes_the_partition_to_the_current_act():
    assert _urns(
        "Si applica l'articolo 22, paragrafo 1, del presente regolamento.",
        GDPR_ART17,
    ) == ["CELEX:32016R0679~art22-num1"]

    text = (
        "La direttiva 87/402/CEE è modificata conformemente all'allegato IV "
        "della presente direttiva."
    )
    result = _result(text, "CELEX:32010L0022~art4")
    assert [row["urn"] for row in result.rows] == [
        "CELEX:31987L0402",
        "CELEX:32010L0022~all4",
    ]
    assert result.rows[0] == ENGINE.extract(text).rows[0]


def test_eu_internal_row_uses_eu_identity_fields():
    row = _result("Si applica il paragrafo 1.", GDPR_ART17).rows[0]
    assert row["ref-type"] == "legislation"
    assert row["ref-scope"] == "comunitario"
    assert row["doc-type"] == "REG"
    assert row["number"] == "679"
    assert row["year"] == "2016"
    assert row["partition"] == "paragrafo-1"
    assert row["urn"] == "CELEX:32016R0679~art17-num1"


def test_only_structural_article_heading_is_suppressed_in_arbitrary_text():
    text = (
        "Art. 8.\nSi applica l'articolo 60.\n\n"
        "AGGIORNAMENTO (1)\nLa novella dispone che \"si applica l'articolo 99\"."
    )
    internal = [urn for urn in _urns(text) if "1986-12-22;917" in urn]
    assert internal == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art60",
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art99",
    ]
    assert _urns('La disposizione recita: «si applica l\'articolo 44».') == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art44"
    ]


def test_external_amendment_block_is_not_resolved_against_current_act():
    text = (
        "1. Al decreto-legge 10 gennaio 2020, n. 1 sono apportate le seguenti "
        "modificazioni: a) all'articolo 2 sono aggiunte le parole indicate."
    )
    assert not any("1986-12-22;917" in urn for urn in _urns(text))


def test_novella_selector_and_replacement_text_use_the_amended_act():
    text = (
        "Al decreto legislativo 19 giugno 1997, n. 218, sono apportate le seguenti "
        "modificazioni: all'articolo 5, il comma 1 è sostituito dal seguente: "
        "«1. Nei casi di cui all'articolo 6 si applica il comma 2.»"
    )
    assert _urns(text) == [
        "urn:nir:stato:decreto.legislativo:1997;218",
        "urn:nir:stato:decreto.legislativo:1997;218~art5-comma1",
        "urn:nir:stato:decreto.legislativo:1997;218~art6-comma2",
    ]


def test_inserted_article_heading_supplies_the_quote_local_article():
    text = (
        "Al decreto legislativo 19 giugno 1997, n. 218, sono apportate le seguenti "
        "modificazioni: dopo l'articolo 5-ter è inserito il seguente: "
        "«5-quater (Adesione). - 1. Nel caso di cui al comma 1 si applicano le "
        "indicazioni previste dall'articolo 7.»"
    )
    assert _urns(text) == [
        "urn:nir:stato:decreto.legislativo:1997;218",
        "urn:nir:stato:decreto.legislativo:1997;218~art5ter",
        "urn:nir:stato:decreto.legislativo:1997;218~art5quater-comma1",
        "urn:nir:stato:decreto.legislativo:1997;218~art7",
    ]


def test_structural_article_heading_inside_replacement_is_context_not_a_citation():
    text = (
        "Nel decreto del Presidente della Repubblica 29 settembre 1973, n. 600, "
        "l'articolo 38 è sostituito dal seguente: «Art. 38 (Accertamento). - 1. "
        "Si applica il comma 2.»"
    )
    urns = _urns(text)
    assert urns.count("urn:nir:presidente.repubblica:decreto:1973;600~art38") == 1
    assert "urn:nir:presidente.repubblica:decreto:1973;600~art38-comma2" in urns


def test_word_substitution_quotes_keep_the_amended_act_scope():
    text = (
        "Al testo unico approvato con decreto del Presidente della Repubblica "
        "23 gennaio 1973, n. 43, sono apportate le seguenti modificazioni: "
        "nell'articolo 307 le parole \"la pena stabilita nell'articolo 305\" sono "
        "sostituite dalle seguenti: \"la sanzione stabilita nell'articolo 305\"."
    )
    assert _urns(text).count(
        "urn:nir:presidente.repubblica:decreto:1973;43~art305") == 2
    assert "urn:nir:presidente.repubblica:decreto:1973;43~art307" in _urns(text)


def test_target_changes_at_the_next_real_numbered_paragraph_not_inside_quotes():
    text = (
        "1. Al decreto legislativo 19 giugno 1997, n. 218, sono apportate le seguenti "
        "modificazioni: all'articolo 5 il comma 1 è sostituito dal seguente: "
        "«1. Si applica l'articolo 7.»\n"
        "2. Al decreto del Presidente della Repubblica 29 settembre 1973, n. 600, "
        "sono apportate le seguenti modificazioni: all'articolo 31 è aggiunto il "
        "seguente comma: «Si applica l'articolo 32.»"
    )
    urns = _urns(text)
    assert "urn:nir:stato:decreto.legislativo:1997;218~art7" in urns
    assert "urn:nir:presidente.repubblica:decreto:1973;600~art32" in urns
    assert "urn:nir:stato:decreto.legislativo:1997;218~art32" not in urns


def test_present_decree_explicitly_escapes_the_amended_act_scope():
    text = (
        "Al decreto del Presidente della Repubblica 29 settembre 1973, n. 600, sono "
        "apportate le seguenti modificazioni; i richiami si intendono introdotti dal "
        "comma 2, lettera b), del presente decreto."
    )
    assert TUIR_ART8.rsplit("~", 1)[0] + "~art8-comma2-letb" in _urns(text)


def test_ambiguous_amendment_without_a_named_target_is_not_guessed():
    text = "All'articolo 12 le parole indicate sono sostituite dalle seguenti: «altre parole»."
    assert _urns(text) == []


def test_ha_disposto_parenthetical_uses_the_subject_act():
    text = (
        "Il D.L. 30 settembre 2015, n. 153, convertito con modificazioni dalla "
        "L. 20 novembre 2015, n. 187, ha disposto (con l'art. 2, comma 2, lettera a)) "
        "che il termine è prorogato."
    )
    assert "urn:nir:stato:decreto.legge:2015;153~art2-comma2-leta" in _urns(text)


def test_complete_external_rows_are_untouched_when_novella_rows_are_added():
    text = (
        "Al decreto legislativo 19 giugno 1997, n. 218, sono apportate le seguenti "
        "modificazioni: all'articolo 5 è aggiunto il richiamo all'articolo 24 della "
        "legge 7 gennaio 1929, n. 4."
    )
    standard = ENGINE.extract(text)
    normativa = _result(text)

    def without_id(row):
        return {key: value for key, value in row.items() if key != "id"}

    ordinary = [without_id(row) for row, ref in zip(normativa.rows, normativa.references)
                if not ref.attrs.get(INTERNAL_ATTR)]
    key = lambda row: (row["urn"], row["text"], row["partition"])
    assert sorted(ordinary, key=key) == sorted(
        (without_id(row) for row in standard.rows), key=key)


def test_eu_amendment_scope_uses_the_amended_celex_act():
    text = (
        "La direttiva 87/402/CEE è modificata come segue: l'articolo 2 è sostituito "
        "dal seguente: «Articolo 2. Si applica l'articolo 3.»"
    )
    urns = _urns(text, "CELEX:32010L0022~art4")
    assert "CELEX:31987L0402~art2" in urns
    assert "CELEX:31987L0402~art3" in urns
    assert not any(urn.startswith("CELEX:32010L0022~art2") for urn in urns)


def test_ha_disposto_after_conversion_law_still_uses_the_subject_decree():
    text = (
        "Il D.L. 30 aprile 2019, n. 34, convertito con modificazioni dalla L. 28 giugno "
        "2019, n. 58, ha disposto (con l'art. 4-octies, comma 2) che la modifica si applica."
    )
    assert "urn:nir:stato:decreto.legge:2019;34~art4octies-comma2" in _urns(text)


@pytest.mark.xfail(strict=False, reason="backward ownership across a quoted article list")
def test_known_miss_quoted_list_owned_by_trailing_external_act():
    text = (
        "La legge 23 dicembre 2014, n. 190 ha disposto che \"Le disposizioni di cui agli "
        "articoli 5, commi da 1-bis a 1-quinquies, e 11, comma 1-bis, del decreto "
        "legislativo 19 giugno 1997, n. 218, continuano ad applicarsi\"."
    )
    assert "urn:nir:stato:decreto.legislativo:1997;218~art5-comma1bis" in _urns(text)


def test_internal_rows_keep_exact_urn_fields_and_offsets():
    text = "Resta fermo quanto stabilito dall'articolo 15."
    result = _result(text)
    assert len(result.rows) == len(result.references) == 1
    row, ref = result.rows[0], result.references[0]
    assert row["text"] == text[ref.start:ref.end] == "articolo 15"
    assert row["ref-type"] == "legislation"
    assert row["ref-scope"] == "nazionale"
    assert row["doc-type"] == "DECR"
    assert row["authority"] == "PRES_REP"
    assert row["number"] == "917"
    assert row["year"] == "1986"
    assert row["doc-date"] == "1986-12-22"
    assert row["partition"] == "articolo-15"
    assert row["urn"].endswith("1986-12-22;917~art15")


def test_regional_unit_and_annex_targets():
    regional = "urn:nir:regione.lazio:legge:2020-02-01;10~art3"
    result = _result("Si applica il comma 2.", regional)
    assert result.rows[0]["urn"] == regional + "-comma2"
    assert result.rows[0]["ref-scope"] == "regionale"
    assert result.rows[0]["region"] == "lazio"
    assert _urns("Si veda l'allegato IV.") == [
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917:4"
    ]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"mode": "unknown"}, "unknown extraction mode"),
        ({"mode": "normativa"}, "current_unit_urn"),
        ({"mode": "normativa", "current_unit_urn":
          "urn:nir:stato:legge:2020-02-10;10"}, "NIR or CELEX unit identifier"),
        ({"mode": "normativa", "current_unit_urn": "CELEX:32016R0679"},
         "NIR or CELEX unit identifier"),
        ({"current_unit_urn": TUIR_ART8}, "only valid"),
    ],
)
def test_mode_arguments_are_validated(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ENGINE.extract("articolo 2", **kwargs)
