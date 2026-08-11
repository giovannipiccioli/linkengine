"""Focused tests for the opt-in internal-reference rules used on legislation."""
import pytest

from linkengine import LinkEngine


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
