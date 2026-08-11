"""Regression tests for normativa identifiers and the semantic act-kind registry."""
import re

import pytest

from linkengine import LinkEngine, urn_to_text
from linkengine.act_kinds import ACT_KINDS, act_kind_for_nir, canonical_nir_pair
from linkengine.aliases import ALIASES
from linkengine.catalog import ALIAS_BASE_TO_NAME


ENGINE = LinkEngine()
NIR_IDENTITY_RE = re.compile(
    r"^urn:nir:(.+?):(\d{4})(?:-\d{2}-\d{2})?;(\d+)(?::[^~!]+)?(?:~.*)?$"
)


def _one_urn(text):
    urns = [row["urn"] for row in ENGINE.extract(text).rows if row["urn"]]
    assert len(urns) == 1, (text, urns)
    return urns[0]


def _nir_identity(urn):
    match = NIR_IDENTITY_RE.match(urn)
    assert match, urn
    authority, doctype = match.group(1).rsplit(":", 1)
    kind = act_kind_for_nir(authority, doctype)
    return (kind.code if kind else "", match.group(2), match.group(3))


def _registered_kind_cases():
    """Exercise every finite registry mapping without depending on generated audit files."""
    cases = []
    historical = {"DLGS_LGT", "DL_LGT", "DECR_LGT", "DLGS_CPS", "DL_CPS", "DECR_CPS",
                  "DLGS_PRES", "RDLGS", "RDL", "RD"}
    for kind in ACT_KINDS:
        year = "1945" if kind.code in historical else "2020"
        for authority, doctype in (kind.nir_pair,) + kind.nir_aliases:
            urn = f"urn:nir:{authority}:{doctype}:{year};1"
            cases.append(pytest.param(
                urn, kind.code, id=f"{kind.code}-{authority}-{doctype}"))
    return cases


def test_act_kind_registry_keys_are_unique():
    assert len({kind.code for kind in ACT_KINDS}) == len(ACT_KINDS)
    assert len({kind.engine_pair for kind in ACT_KINDS}) == len(ACT_KINDS)
    assert len({kind.nir_pair for kind in ACT_KINDS}) == len(ACT_KINDS)
    aliases = {}
    for kind in ACT_KINDS:
        for pair in (kind.nir_pair,) + kind.nir_aliases:
            assert pair not in aliases or aliases[pair] == kind.code
            aliases[pair] = kind.code


@pytest.mark.parametrize(("source_pair", "canonical_pair"), [
    (("stato", "decreto.del.capo.provvisorio.dello.stato"),
     ("capo.provvisorio.stato", "decreto")),
    (("stato", "decreto.luogotenenziale"), ("luogotenente", "decreto")),
    (("ministero.sanita", "ordinanza"), ("ministero", "ordinanza")),
    (("comitato.interministeriale.programmazione.economica", "deliberazione"),
     ("comitato.interministeriale", "deliberazione")),
    (("ministero.ambiente.e.tutela.territorio.e.mare", "decreto"),
     ("ministero", "decreto")),
])
def test_source_pairs_canonicalize_through_the_semantic_registry(
        source_pair, canonical_pair):
    assert canonical_nir_pair(*source_pair) == canonical_pair


def test_unknown_source_pair_is_not_rewritten():
    pair = ("autorita.sconosciuta", "provvedimento")
    assert canonical_nir_pair(*pair) == pair


@pytest.mark.parametrize(("source_urn", "expected_kind"), _registered_kind_cases())
def test_every_registered_nir_pair_round_trips_semantically(
        source_urn, expected_kind):
    citation_urn = re.sub(r":(\d{4})-\d{2}-\d{2};", r":\1;", source_urn)
    expected = _nir_identity(source_urn)
    assert expected[0] == expected_kind
    parsed = [row["urn"] for row in ENGINE.extract(urn_to_text(citation_urn)).rows if row["urn"]]
    assert expected in {_nir_identity(urn) for urn in parsed}


@pytest.mark.parametrize(("source_urn", "expected_kind", "canonical_urn"), [
    ("urn:nir:stato:decreto.del.capo.provvisorio.dello.stato:1947;1833",
     "DECR_CPS", "urn:nir:capo.provvisorio.stato:decreto:1947;1833"),
    ("urn:nir:stato:regio.decreto.legge:1944;61",
     "RDL", "urn:nir:stato:regio.decreto.legge:1944;61"),
    ("urn:nir:stato:regio.decreto.legislativo:1946;604",
     "RDLGS", "urn:nir:stato:regio.decreto.legislativo:1946;604"),
    ("urn:nir:stato:decreto.luogotenenziale:1944;504",
     "DECR_LGT", "urn:nir:luogotenente:decreto:1944;504"),
    ("urn:nir:stato:decreto.legislativo.presidenziale:1946;98",
     "DLGS_PRES", "urn:nir:stato:decreto.legislativo.presidenziale:1946;98"),
    ("urn:nir:ministero.sanita:ordinanza:1988;57",
     "ORD_MIN", "urn:nir:ministero:ordinanza:1988;57"),
    ("urn:nir:comitato.interministeriale.programmazione.economica:deliberazione:1988;245",
     "DELIB_INTERMIN", "urn:nir:comitato.interministeriale:deliberazione:1988;245"),
    ("urn:nir:ministero.ambiente.e.tutela.territorio.e.mare:decreto:2020;78",
     "DM", "urn:nir:ministero:decreto:2020;78"),
])
def test_source_nir_renders_and_reparses_to_same_semantic_kind(
        source_urn, expected_kind, canonical_urn):
    source_body = source_urn[len("urn:nir:"):]
    authority, doctype, _identity = source_body.rsplit(":", 2)
    assert act_kind_for_nir(authority, doctype).code == expected_kind
    assert _one_urn(urn_to_text(source_urn)) == canonical_urn


@pytest.mark.parametrize(("base", "label"), sorted(ALIAS_BASE_TO_NAME.items()))
def test_every_nir_alias_emitted_by_urn_to_text_is_valid_standalone(base, label):
    urn = "urn:nir:" + base
    assert urn_to_text(urn) == label
    assert _one_urn(label) == urn


def test_alias_urn_bases_use_the_act_kind_canonical_pair():
    for alias in ALIASES:
        if not alias.nir:
            continue
        act_base = re.split(r":\d{4}(?:-\d{2}-\d{2})?;", alias.nir, maxsplit=1)[0]
        authority, doctype = act_base.rsplit(":", 1)
        kind = act_kind_for_nir(authority, doctype)
        if kind:
            assert (authority, doctype) == kind.nir_pair, alias.code


def test_broader_alias_phrase_is_not_promoted_to_a_standalone_act():
    assert ENGINE.extract("imposta sulle successioni e donazioni").rows == []


def test_numbered_mef_decree_keeps_metadata_out_of_its_minimal_urn():
    row = ENGINE.extract(
        "decreto del Ministro dell'economia e delle finanze 23 dicembre 2013, n. 163"
    ).rows[0]
    assert row["ministry"] == "ECONOMIA_FINANZE"
    assert row["urn"] == "urn:nir:ministero:decreto:2013;163"


@pytest.mark.parametrize(("text", "ministry"), [
    ("DM MEF n. 1/2020", "ECONOMIA_FINANZE"),
    ("decreto MiSE n. 1/2020", "SVILUPPO_ECONOMICO"),
    ("decreto MIT n. 1/2020", "INFRASTRUTTURE_TRASPORTI"),
    ("decreto MIMS n. 1/2020", "INFRASTRUTTURE_MOBILITA_SOSTENIBILI"),
    ("decreto MIUR n. 1/2020", "ISTRUZIONE_UNIVERSITA_RICERCA"),
])
def test_known_ministry_marker_is_metadata_not_identity(text, ministry):
    row = ENGINE.extract(text).rows[0]
    assert row["ministry"] == ministry
    assert row["urn"] == "urn:nir:ministero:decreto:2020;1"


@pytest.mark.parametrize(("text", "urn"), [
    ("R.D.L. n. 10/25", "urn:nir:stato:regio.decreto.legge:1925;10"),
    ("R.D.Lgs. n. 10/25", "urn:nir:stato:regio.decreto.legislativo:1925;10"),
])
def test_royal_decree_variants_use_historical_two_digit_year(text, urn):
    assert _one_urn(text) == urn


def test_date_only_decree_compatibility_tokens_are_unchanged():
    assert _one_urn("D.M. 23 dicembre 2013") == "DM2013-12-23"
    assert _one_urn("D.P.C.M. 11 marzo 2020") == "DPCM2020-03-11"


@pytest.mark.parametrize("urn", [
    "urn:nir:stato:legge:1973;633~allA",
    "urn:nir:stato:legge:1973;633~allA-art1",
    "urn:nir:stato:legge:1973;633~all-tabella-a",
])
def test_attachment_document_locator_round_trip(urn):
    assert _one_urn(urn_to_text(urn)) == urn


def test_non_article_locators_are_readable():
    assert urn_to_text("CELEX:32006L0112~cons12") == \
        "considerando 12 direttiva (CE) 112/2006"
    assert urn_to_text("urn:nir:stato:legge:1973;633~all-tabella-a") == \
        "Allegato «tabella-a» legge n. 633/1973"


@pytest.mark.parametrize(("urn", "text"), [
    ("CELEX:31992R2913", "regolamento (CEE) 2913/1992"),
    # Whole-year cut-offs are intentional: the URN has no adoption date.
    ("CELEX:31993R3031", "regolamento (CEE) 3031/1993"),
    ("CELEX:31994R0001", "regolamento (CE) 1/1994"),
    ("CELEX:32006L0112", "direttiva (CE) 112/2006"),
    ("CELEX:32009L0159", "direttiva (CE) 159/2009"),
    ("CELEX:32010L0001", "direttiva (UE) 1/2010"),
    ("CELEX:32015D2240", "decisione (UE) 2240/2015"),
    ("CELEX:32003H0361", "raccomandazione (CE) 361/2003"),
    ("CELEX:31993S3632", "decisione (CECA) 3632/1993"),
    ("CELEX:32006L0112~art167-num2-leta",
     "art. 167 paragrafo 2 let. a direttiva (CE) 112/2006"),
    ("CELEX:32023R1114~art3-num1-num7",
     "art. 3 paragrafo 1 numero 7 regolamento (UE) 1114/2023"),
    ("CELEX:32026R0283~all6", "Allegato 6 regolamento (UE) 283/2026"),
])
def test_sector_3_celex_uses_modern_best_guess_citation_and_round_trips(urn, text):
    assert urn_to_text(urn) == text
    assert _one_urn(text) == urn


@pytest.mark.parametrize("locator", [
    "allA",
    "allA-art1",
    "all-tabella-a",
    "all-note",
    "all-art-cp",
])
def test_representative_attachment_locators_round_trip(locator):
    urn = "urn:nir:stato:legge:2020;1~" + locator
    assert _one_urn(urn_to_text(urn)) == urn


def test_compact_attachment_text_and_nir_annex_remain_distinct():
    # The audit example had 600 in the label and 633 in the URN; use the coherent act number.
    compact = "urn:nir:stato:legge:1973;633~allA"
    assert urn_to_text(compact) == "Allegato A legge n. 633/1973"
    assert _one_urn("Allegato A l. 633/73") == compact
    assert _one_urn("All. A del D.P.R. n. 634 del 1972") == \
        "urn:nir:presidente.repubblica:decreto:1972;634:a"
