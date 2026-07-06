"""Regression tests for linkengine: the canonical tax-law citation patterns and the URN
strings they must produce."""
import pytest

from linkengine import DocumentContext, LinkEngine
from linkengine.runner import run_linkengine_string

ENG = LinkEngine()


def _one(text):
    rows = ENG.extract(text).rows
    assert len(rows) == 1, f"expected 1 ref for {text!r}, got {len(rows)}"
    return rows[0]


def _urn(row):
    return row.get("urn", "")


def test_dpr_with_partition():
    r = _one("art. 43 comma 1 dpr n. 600/1973")
    assert r["doc-type"] == "DECR" and r["authority"] == "PRES_REP"
    assert r["number"] == "600" and r["year"] == "1973"
    assert r["partition"] == "articolo-43_comma-1"
    assert _urn(r) == "urn:nir:presidente.repubblica:decreto:1973;600~art43-comma1"


def test_decreto_legge():
    r = _one("art. 10, comma 12, del d.l. n. 201/2011")
    assert _urn(r) == "urn:nir:stato:decreto.legge:2011;201~art10-comma12"


def test_decreto_legislativo():
    r = _one("articolo 2 del dlgs. n. 446/1997")
    assert _urn(r) == "urn:nir:stato:decreto.legislativo:1997;446~art2"


def test_legge_full_word_and_date():
    r = _one("legge 27 luglio 2000, n. 212")
    assert r["doc-type"] == "L" and r["year"] == "2000" and r["doc-date"] == "2000-07-27"
    assert _urn(r) == "urn:nir:stato:legge:2000;212"


def test_legge_abbreviation_with_latin_partition():
    r = _one("art. 10 bis, l. n. 212/2000")
    assert r["doc-type"] == "L"
    assert r["partition"] == "articolo-10-bis"
    assert _urn(r) == "urn:nir:stato:legge:2000;212~art10bis"


def test_codice_civile_alias():
    # alias feature + the final (year-trimmed) urn via the shared URN layer
    assert _one("art. 2697 c.c.")["alias"] == "COD_CIV"
    assert _urns("art. 2697 c.c.") == ["urn:nir:stato:regio.decreto:1942;262:2~art2697"]


def test_codice_proc_civile_alias():
    assert _urns("art. 160 c.p.c.") == ["urn:nir:stato:regio.decreto:1940;1443:1~art160"]


def test_tuir_alias():
    assert _urns("art. 9 del TUIR") == ["urn:nir:presidente.repubblica:decreto:1986;917~art9"]


def test_eu_regulation_celex():
    r = _one("Regolamento (UE) n. 1215/2012")
    assert r["ref-scope"] == "comunitario"
    assert r["urn"] == "CELEX:32012R1215"


def test_cassazione_caselaw_features():
    r = _one("Cass. n. 12345/2020")
    assert r["ref-type"] == "caselaw" and r["authority"] == "CORTE_CASS"
    assert r["number"] == "12345" and r["year"] == "2020"


def test_two_digit_year_and_no_n_prefix():
    # "DPR 602/73" — number right after doctype, no "n.", 2-digit year
    r = _one("art. 26 DPR 602/73")
    assert r["number"] == "602" and r["year"] == "1973"
    assert _urn(r) == "urn:nir:presidente.repubblica:decreto:1973;602~art26"


def test_costituzione_alias():
    assert _one("art. 117 Cost.")["alias"] == "COST"
    assert _urns("art. 117 Cost.") == ["urn:nir:stato:costituzione~art117"]


def test_cassazione_number_list_split():
    # one authority governing a list of numbers -> one reference each
    urns = sorted({r["urn"] for r in ENG.extract("Cass. 10266/2018, 30927/2018").rows if r["urn"]})
    assert urns == ["ECLI:IT:CASS:2018:10266CIV", "ECLI:IT:CASS:2018:30927CIV"]


def test_date_not_mistaken_for_number_year():
    # "31/12/2020" must not yield a spurious 31/2012 or 12/2020 citation
    assert ENG.extract("il contratto del 31/12/2020 per euro 588.000").rows == []


def test_no_reference_in_plain_prose():
    assert ENG.extract("il giudice ha ritenuto fondato il ricorso").rows == []


def test_runner_emits_parseable_csv():
    from linkengine.model import FEATURE_FIELDS
    raw = run_linkengine_string("art. 43 dpr n. 600/1973")
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    assert len(lines) == 1
    row = dict(zip(FEATURE_FIELDS, [c.strip('"') for c in lines[0].split("|")]))
    assert row["doc-type"] == "DECR"
    assert run_linkengine_string("buongiorno a tutti") == "ERROR: No data in output"


def test_citation_ids_follow_text_order_and_restart_per_document():
    first = ENG.extract("legge 241/1990 e Cass. n. 100/2020").rows
    second = ENG.extract("D.P.R. 600/1973").rows

    assert [(row["id"], row["number"]) for row in first] == [("1", "241"), ("2", "100")]
    assert [(row["id"], row["number"]) for row in second] == [("1", "600")]


# --- case-law courts with geo (ECLI built directly by the engine) -----------


def _urns(text):
    # the engine classifies (legislation/caselaw/prassi) and builds each row's `urn` itself
    return sorted({r["urn"] for r in ENG.extract(text).rows if r["urn"]})


def test_ctr_uses_region():
    assert _urns("C.T.R. Lazio Roma Sez. V n. 2291/2022") == ["ECLI:IT:CTRLAZ:2022:2291"]


def test_modern_and_historical_tax_court_authorities_are_distinct():
    cases = {
        "CGT 1 Roma n. 123/2024": "CORTE_GIUST_TRIBUT_1",
        "CGT 2 Lombardia n. 123/2024": "CORTE_GIUST_TRIBUT_2",
        "CTP Roma n. 123/2024": "COMM_TRIBUT_PROV",
        "CTR Lombardia n. 123/2024": "COMM_TRIBUT_REG",
    }
    for text, authority in cases.items():
        assert _one(text)["authority"] == authority


def test_trento_bolzano_second_grade_tax_court_ecli_exception():
    cases = {
        "CGT 2 Bolzano n. 1234/2020":
            ("CORTE_GIUST_TRIBUT_2", "BZ", "ECLI:IT:CGT2BZ:2020:1234"),
        "Corte di Giustizia Tributaria di secondo grado di Trento n. 55/2021":
            ("CORTE_GIUST_TRIBUT_2", "TN", "ECLI:IT:CGT2TN:2021:55"),
        "CTR Bolzano n. 1234/2020":
            ("COMM_TRIBUT_REG", "BZ", "ECLI:IT:CTRBZ:2020:1234"),
        "Commissione Tributaria Regionale di Trento n. 55/2021":
            ("COMM_TRIBUT_REG", "TN", "ECLI:IT:CTRTN:2021:55"),
    }
    for text, (authority, geo, urn) in cases.items():
        row = _one(text)
        assert row["authority"] == authority
        assert row["region"] == geo
        assert row["urn"] == urn


def test_trento_bolzano_first_grade_tax_court_ecli_exception():
    cases = {
        "CGT 1 Bolzano n. 99/2018":
            ("CORTE_GIUST_TRIBUT_1", "ECLI:IT:CGT1BZ:2018:99"),
        "Corte di Giustizia Tributaria di primo grado di Trento n. 7/2020":
            ("CORTE_GIUST_TRIBUT_1", "ECLI:IT:CGT1TN:2020:7"),
        "Commissione Tributaria Provinciale di Bolzano n. 1234/2020":
            ("COMM_TRIBUT_PROV", "ECLI:IT:CTPBZ:2020:1234"),
    }
    for text, (authority, urn) in cases.items():
        row = _one(text)
        assert row["authority"] == authority
        assert row["urn"] == urn


def test_trento_bolzano_second_grade_tax_court_document_context():
    text = "sentenza n. 1234/2020 di questa Corte"
    for city, geo in (("Bolzano", "BZ"), ("Trento", "TN")):
        context = DocumentContext(
            authority="CORTE_GIUST_TRIBUT_2", city=city, region="Trentino Alto Adige")
        row = ENG.extract(text, context=context).rows[0]
        assert row["region"] == geo
        assert row["urn"] == f"ECLI:IT:CGT2{geo}:2020:1234"


def test_trentino_alto_adige_second_grade_tax_court_needs_province():
    row = _one("CGT 2 Trentino Alto Adige n. 101/2024")
    assert row["authority"] == "CORTE_GIUST_TRIBUT_2"
    assert row["region"] == "TAA"
    assert row["urn"] == ""


def test_autonomous_tax_court_geo_does_not_change_other_courts():
    row = _one("Tribunale di Bolzano n. 1234/2020")
    assert row["authority"] == "TRIB"
    assert row["city"] == "A952"
    assert row["urn"] == "ECLI:IT:TRIBA952:2020:1234"


def test_tax_court_rga_number_is_docket_not_citation():
    assert _urns("giudizio pendente dinnanzi alla CTR Emilia Romagna RGA 1202/2021") == []


def test_bdgt_rgr_numbers_are_dockets_not_citations():
    samples = (
        "questa Corte si e' gia' pronunciata (procedimento RGR 223/2022) e la sentenza",
        "CTP di Alessandria con ricorso\nRGR n. 460/2019",
        "DECISIONE\nIn esito al ricorso R.G.R. n. 162/24",
        "ha pronunciato la seguente SENTENZA - sul ricorso in riassunzione n. 286/2023",
    )
    for text in samples:
        assert ENG.extract(text).rows == [], text


def test_ctp_uses_province_city():
    assert _urns("Commissione Tributaria Provinciale di Udine n. 26924/2019") == \
        ["ECLI:IT:CTPUD:2019:26924"]


def test_cgt_ambiguous_resolves_by_geo_type():
    # a province name -> first grade; a region name -> second grade
    assert _urns("C.G.T. Udine Sez. II n. 229/2022") == ["ECLI:IT:CGT1UD:2022:229"]


def test_corte_appello_and_tribunale_and_gdp():
    assert _urns("Corte d'Appello di Milano n. 5/2019") == ["ECLI:IT:CAPPMI:2019:5"]
    assert _urns("Tribunale di Roma sent. n. 100/2020") == ["ECLI:IT:TRIBRM:2020:100"]
    assert _urns("Giudice di Pace di Napoli n. 3/2021") == ["ECLI:IT:GDPNA:2021:3"]


# --- Agenzia delle Entrate prassi -------------------------------------------
def test_ade_risoluzione_and_circolare():
    assert _urns("Risoluzione Agenzia Entrate n. 337/E/2002") == ["PRAX:AE:RIS:2002:337/E"]
    assert _urns("Circolare Agenzia delle Entrate n. 12/2009") == ["PRAX:AE:CIRC:2009:12"]
    # year recovered from a (dotted) date when absent from the number
    assert _urns("Circolare Ministeriale 12.5.1998 n. 124/E") == ["PRAX:AE:CIRC:1998:124"]


@pytest.mark.parametrize("text, authority, urn", [
    ("Circolare MEF n. 3/DF/2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
    ("Circolare MEF n. 3/DF del 18/05/2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
    ("Circolare Ministero delle Finanze n. 9/1993", "MEF", "PRAX:MEF:CIRC:1993:9"),
    ("Circolare M.E.F. n. 3/df del 18.05.2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
    ("Circolare MEF n. 3/DF del 18.5.2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
    ("circolare MEF n. 3/DF/2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
    ("Circolare MEF n. 1/DF del 19.2.2010", "MEFDF", "PRAX:MEFDF:CIRC:2010:1"),
    ("Circolare n. 3/DF/2012", "MEFDF", "PRAX:MEFDF:CIRC:2012:3"),
])
def test_mef_dipartimento_finanze_circulars(text, authority, urn):
    row = _one(text)
    assert row["doc-type"] == "CIRC"
    assert row["other-authority"] == authority
    assert row["urn"] == urn


def test_unattributed_circular_is_not_recognized():
    assert ENG.extract("Circolare n. 6/2012").rows == []


def test_agenzia_entrate_circular_urn_drops_e_suffix():
    row = _one("Circolare Agenzia delle entrate n.13/E 2006")
    assert row["full-number"] == "13/E"
    assert row["urn"] == "PRAX:AE:CIRC:2006:13"


def test_prax_generator_supports_cerdef_authorities_and_types():
    from linkengine import generate_prax_urn

    assert generate_prax_urn("Min. Finanze", "risoluzione", "1982-08-03", "271112") == \
        "PRAX:MEF:RIS:1982:271112"
    assert generate_prax_urn("Agenzia delle Dogane e dei Monopoli", "circolare",
                             "26_06_2020", 17) == "PRAX:ADM:CIRC:2020:17"
    # Date-based types deliberately ignore a CERDEF sequence number.
    assert generate_prax_urn("Agenzia delle Entrate", "comunicato stampa",
                             "2012-06-07", 83) == "PRAX:AE:CS:20120607"
    assert generate_prax_urn("Min. Finanze", "telegramma", "03_12_1991") == \
        "PRAX:MEF:TEL:19911203"
    assert generate_prax_urn("Autorita sconosciuta", "circolare", "2020-01-01", 1) == ""


def test_extended_prassi_citations_build_prax_urns():
    cases = {
        "Circolare Min. Finanze n. 160/1996": "PRAX:MEF:CIRC:1996:160",
        "Risoluzione Min. Finanze n. 271112 del 3 agosto 1982":
            "PRAX:MEF:RIS:1982:271112",
        "Comunicato stampa del 7 giugno 2012 Agenzia delle Entrate":
            "PRAX:AE:CS:20120607",
        "Telegramma del 3 dicembre 1991 Min. Finanze": "PRAX:MEF:TEL:19911203",
        "Lettera circolare del 22 febbraio 1989 Min. Finanze": "PRAX:MEF:LCIRC:19890222",
        "Circolare Agenzia delle Dogane e dei Monopoli n. 17/2020":
            "PRAX:ADM:CIRC:2020:17",
        "Delibera Banca d'Italia n. 16/2010": "PRAX:BI:DEL:2010:16",
        "Direttiva Dipartimento delle Finanze n. 2/2012": "PRAX:DIF:DIR:2012:2",
    }
    for text, expected in cases.items():
        assert _urns(text) == [expected], text


def test_prassi_authority_does_not_cross_sentence_boundary():
    text = ("Agenzia delle Dogane e dei Monopoli ne analizza la composizione. "
            "Al riguardo, con la circolare 32/E/2010 dell'Agenzia delle Entrate")
    assert _urns(text) == ["PRAX:AE:CIRC:2010:32"]


def test_prassi_date_range_is_not_a_document_number():
    assert _urns("provvedimenti 18/23 settembre 2024 dell'Agenzia delle Entrate") == []


def test_provvedimento_uses_protocol_number():
    text = ("Provvedimento del Direttore dell'Agenzia delle Entrate - "
            "prot. n. 183037/2020 del 30 aprile 2020")
    assert _urns(text) == ["PRAX:AE:PROVV:2020:183037"]


def test_prassi_uses_authority_nearest_to_document_type():
    text = "INPS, con la circolare dell'Agenzia Entrate n. 22/E/2020 ha chiarito"
    assert _urns(text) == ["PRAX:AE:CIRC:2020:22"]


def test_interpello_prefers_explicit_agenzia_entrate_over_applicant():
    text = ("interpello n. 958-587/2023, presentato dal Fondo di Previdenza del Mef, "
            "all'Agenzia delle Entrate")
    assert _urns(text) == ["PRAX:AE:INT:2023:587"]


def test_hyphenated_agenzia_protocol_does_not_emit_office_prefix():
    text = ("nota n. 954-87316 del 22 giugno 2006 della stessa "
            "Agenzia delle Entrate")
    assert _urns(text) == ["PRAX:AE:NOTA:2006:87316"]


def test_composite_number_exception_is_limited_to_agenzia_prassi():
    from linkengine.special_cases import is_agenzia_composite_number_prefix

    prassi = "nota n. 954-87316 del 22 giugno 2006 della stessa Agenzia delle Entrate"
    ordinary = "sentenza n. 954-87316 del 22 giugno 2006"
    start = prassi.index("n.")
    end = start + len("n. 954")
    assert is_agenzia_composite_number_prefix(prassi, start, end)
    start = ordinary.index("n.")
    end = start + len("n. 954")
    assert not is_agenzia_composite_number_prefix(ordinary, start, end)


def test_eu_directive_is_not_claimed_by_nearby_prassi_authority():
    text = ("Monopoli, ai sensi dell'art. 14 della Direttiva 12 dicembre 2006 "
            "n. 2006/123/CE")
    assert _urns(text) == ["CELEX:32006L0123~art14"]


def test_prassi_act_does_not_propagate_to_legal_articles():
    text = ("art. 11, comma 1, lett. c) e d) Statuto Agenzia delle entrate, "
            "approvato con delibera n. 6 del 2000; art. 14, comma 2")
    rows = ENG.extract(text).rows
    assert [r["urn"] for r in rows] == ["PRAX:AE:DEL:2000:6"]
    assert rows[0]["partition"] == ""


# --- partition lists --------------------------------------------------------
def test_article_list_splits_into_separate_refs():
    assert _urns("artt. 5 e 6 della legge 400/1988") == [
        "urn:nir:stato:legge:1988;400~art5", "urn:nir:stato:legge:1988;400~art6"]


def test_comma_list_plural_splits():
    # "commi" (plural) + a comma list, forward form
    assert _urns("art. 19, commi 1 e 2-bis, DPR 600/1973") == [
        "urn:nir:presidente.repubblica:decreto:1973;600~art19-comma1",
        "urn:nir:presidente.repubblica:decreto:1973;600~art19-comma2bis"]


def test_explicit_budget_law_and_alias_do_not_duplicate_partitions():
    text = "art. 6, commi da 13 a 17, della Legge 388/2000 - Finanziaria 2001"
    rows = ENG.extract(text).rows
    assert [r["partition"] for r in rows] == [
        "articolo-6_comma-13", "articolo-6_comma-14", "articolo-6_comma-15",
        "articolo-6_comma-16", "articolo-6_comma-17"]
    assert all(r["text"] for r in rows)


def test_unrecognized_dgc_number_is_not_stolen_by_preceding_dlgs():
    rows = ENG.extract("artt. 198 e 226 del D.Lgs. n. 152/06 e DGC n. 117/17").rows
    assert [r["urn"] for r in rows if r["urn"]] == [
        "urn:nir:stato:decreto.legislativo:2006;152~art198",
        "urn:nir:stato:decreto.legislativo:2006;152~art226"]
    local = [r for r in rows if r["authority"] == "COMUNE"]
    assert len(local) == 1
    assert local[0]["ref-type"] == "other acts"
    assert (local[0]["doc-type"], local[0]["number"], local[0]["year"]) == ("DEL", "117", "2017")
    assert all(r["text"] for r in rows)


def test_dcc_is_a_local_delibera_with_standard_text():
    row = _one("D.C.C. n. 34 del 31 luglio 2014 del Comune di Palestrina")
    assert row["ref-type"] == "other acts"
    assert row["urn"] == "DEL:COG274:2014:34"
    from linkengine import urn_to_text
    assert urn_to_text(row["urn"]) == "delibera del Comune di Palestrina n. 34/2014"


def test_elided_article_after_subpartition_starts_new_branch():
    assert _urns(
        "violazione degli artt. 2, comma 1, e 3, comma 1, lettera c), "
        "del d.lgs. n. 446/1997"
    ) == [
        "urn:nir:stato:decreto.legislativo:1997;446~art2-comma1",
        "urn:nir:stato:decreto.legislativo:1997;446~art3-comma1-letc",
    ]


# --- EU acts: year/number order, treaties, Corte Cost, small-city, DM --------
def test_eu_directive_year_number_order():
    # EU acts are year/number ("2006/112" = number 112, year 2006)
    assert _urns("Direttiva 2006/112/CE") == ["CELEX:32006L0112"]
    assert _urns("articolo 167 della direttiva 2006/112/CE") == ["CELEX:32006L0112~art167"]


def test_eu_treaty_aliases():
    assert _urns("articolo 267 TFUE") == ["CELEX:12012E/TXT~art267"]
    assert _urns("art. 6 TUE") == ["CELEX:12016ME/TXT~art6"]


def test_corte_costituzionale_ecli():
    assert _urns("Corte cost. n. 5/1990") == ["ECLI:IT:COST:1990:5"]


def test_numbered_ministerial_decree():
    assert _urns("decreto ministeriale n. 597/2018") == ["urn:nir:ministero:decreto:2018;597"]


def test_mef_ministerial_decree_has_specific_issuer():
    text = "decreto del Ministro dell'economia e delle finanze 23 dicembre 2013, n. 163"
    row = _one(text)
    assert row["text"] == text
    assert row["ref-type"] == "legislation"
    assert row["doc-type"] == "DECR"
    assert row["authority"] == "MINISTERO"
    assert row["ministry"] == "ECONOMIA_FINANZE"
    assert row["number"] == "163"
    assert row["doc-date"] == "2013-12-23"
    assert row["urn"] == "urn:nir:ministero.economia.finanze:decreto:2013;163"


def test_tribunale_small_city_catastale():
    # non-capoluogo comune -> catastale code (Tivoli -> L182)
    assert _urns("Tribunale di Tivoli sent. n. 5/2021") == ["ECLI:IT:TRIBL182:2021:5"]


def test_date_fragment_not_a_citation():
    # a bare day/month must not become a number/year citation
    assert ENG.extract("la scadenza del 31/12 e poi").rows == []


# --- alias resolution + intra-document context ------------------------------
def test_alias_acts_resolve_to_urns():
    assert _urns("art. 5 l. fall.") == ["urn:nir:stato:regio.decreto:1942;267:1~art5"]
    assert _urns("art. 50 del TUEL") == ["urn:nir:stato:decreto.legislativo:2000;267~art50"]
    assert _urns("art. 633 codice penale") == ["urn:nir:stato:regio.decreto:1930;1398:1~art633"]


def test_number_del_year_without_n_prefix():
    assert _urns("d.lgs. 504 del 1992") == ["urn:nir:stato:decreto.legislativo:1992;504"]
    assert _urns("legge 241 del 1990") == ["urn:nir:stato:legge:1990;241"]


def test_context_propagation_bare_article_inherits_alias():
    # a code named once, then bare articles -> inherit the act (intra-document context)
    urns = _urns("Il giudice richiama il codice civile e in particolare l'art. 1362 e l'art. 1366.")
    assert "urn:nir:stato:regio.decreto:1942;262:2~art1362" in urns
    assert "urn:nir:stato:regio.decreto:1942;262:2~art1366" in urns


# --- self-references ("questa Corte") + default_authority --------------------
def _urns_auth(text, authority):
    from linkengine import LinkEngine
    eng = LinkEngine(default_authority=authority)
    return sorted({r["urn"] for r in eng.extract(text).rows if r["urn"]})


def test_self_reference_needs_default_authority():
    t = "sentenza n. 123/2020 di questa Corte"
    assert _urns_auth(t, "") == []                       # unresolved without the flag
    assert _urns_auth(t, "CORTE_CASS") == ["ECLI:IT:CASS:2020:123CIV"]


def test_document_context_resolves_tax_court_self_references():
    first_grade = DocumentContext(
        authority="CORTE_GIUST_TRIBUT_1", city="Reggio Calabria", region="Calabria")
    second_grade = DocumentContext(authority="CORTE_GIUST_TRIBUT_2", region="Lombardia")
    text = "sentenza n. 123/2024 di questa Corte"

    first = ENG.extract(text, context=first_grade).rows[0]
    assert first["authority"] == "CORTE_GIUST_TRIBUT_1"
    assert first["city"] == "RC"
    assert first["urn"] == "ECLI:IT:CGT1RC:2024:123"

    second = ENG.extract(text, context=second_grade).rows[0]
    assert second["authority"] == "CORTE_GIUST_TRIBUT_2"
    assert second["region"] == "LOM"
    assert second["urn"] == "ECLI:IT:CGT2LOM:2024:123"


def test_document_context_region_defaults_unqualified_regional_laws():
    context = DocumentContext(
        authority="CORTE_GIUST_TRIBUT_1", city="Roma", region="Lazio")
    row = ENG.extract("art. 5 della l. reg. n. 4/2024", context=context).rows[0]
    assert row["region"] == "lazio"
    assert row["urn"] == "urn:nir:regione.lazio:legge:2024;4~art5"

    # A separate regional-law value can override the deciding court's region.
    context = DocumentContext(
        authority="CORTE_CASS", region="Lazio", regional_law_region="Campania")
    row = ENG.extract("art. 5 della l. reg. n. 4/2024", context=context).rows[0]
    assert row["urn"] == "urn:nir:regione.campania:legge:2024;4~art5"


def test_document_context_is_runtime_and_does_not_mutate_engine_defaults():
    engine = LinkEngine(default_context=DocumentContext(authority="CORTE_CASS"))
    text = "sentenza n. 123/2024 di questa Corte"
    tax_context = DocumentContext(
        authority="CORTE_GIUST_TRIBUT_2", region="emilia.romagna")

    assert engine.extract(text, context=tax_context).rows[0]["urn"] == \
        "ECLI:IT:CGT2EMR:2024:123"
    assert engine.extract(text).rows[0]["urn"] == "ECLI:IT:CASS:2024:123CIV"
    assert ENG.extract(text, default_authority="CORTE_CASS").rows[0]["urn"] == \
        "ECLI:IT:CASS:2024:123CIV"


def test_document_context_does_not_resolve_bare_decision_numbers():
    context = DocumentContext(
        authority="CORTE_GIUST_TRIBUT_1", city="Roma", region="Lazio")
    row = ENG.extract("Sentenza n. 123/2020", context=context).rows[0]
    assert row["authority"] == ""
    assert row["urn"] == ""


def test_document_context_normalizes_codes_and_rejects_unknown_values():
    context = DocumentContext(
        authority="CORTE_GIUST_TRIBUT_1", city="RC", region="CAL")
    assert context.city == "RC"
    assert context.region == "CAL"
    assert context.regional_law_region == "calabria"
    assert LinkEngine(default_region="LOM").default_region == "lombardia"

    with pytest.raises(ValueError, match="unknown document authority"):
        DocumentContext(authority="Cassazione")
    with pytest.raises(ValueError, match="unknown document authority"):
        LinkEngine(default_authority="Cassazione")
    with pytest.raises(ValueError, match="unknown document region"):
        DocumentContext(region="Atlantide")
    with pytest.raises(ValueError, match="unknown document city"):
        DocumentContext(city="Atlantide")


def test_unresolved_references_need_minimal_evidence():
    sent = ENG.extract("Sentenza n. 123/2020").rows
    assert len(sent) == 1
    assert sent[0]["urn"] == ""
    assert sent[0]["doc-type"] == "SENT"
    assert sent[0]["number"] == "123"
    assert sent[0]["year"] == "2020"

    cedu = ENG.extract("Corte EDU n. 123/2020").rows
    assert len(cedu) == 1
    assert cedu[0]["urn"] == ""
    assert cedu[0]["authority"] == "CEDU"
    assert cedu[0]["number"] == "123"

    assert ENG.extract("n. 23, posto che, come gia' statuito da questa Sezione").rows == []


def test_unresolved_heading_sentenza_does_not_bind_procedural_ricorso_date():
    rows = ENG.extract(
        "Sentenza n. 110/2022\nDepositato il 13/04/2022\n"
        "Con ricorso in data 25.05.2018 il contribuente impugnava l'atto."
    ).rows
    assert len(rows) == 1
    assert rows[0]["urn"] == ""
    assert rows[0]["doc-type"] == "SENT"
    assert rows[0]["number"] == "110"
    assert rows[0]["year"] == "2022"
    assert rows[0]["doc-date"] == ""
    assert rows[0]["text"] == "Sentenza n. 110/2022"


def test_bdgt_procedural_header_does_not_bridge_two_numbers():
    rows = ENG.extract(
        "n. 30/2025 depositato il 26/05/2025\nSentenza n. 119/2025"
    ).rows
    assert [(row["number"], row["year"], row["text"]) for row in rows] == [
        ("119", "2025", "Sentenza n. 119/2025")
    ]


def test_bdgt_decisione_heading_is_not_an_eu_act():
    for heading in ("DECISIONE", "SVOLGIMENTO DEL PROCESSO E MOTIVI DELLA DECISIONE"):
        assert ENG.extract(
            heading + "\nLa Societa' ricorrente impugnava la cartella di pagamento n. 10 2024"
        ).rows == []


def test_bdgt_object_number_does_not_reach_later_act_word():
    assert ENG.extract(
        'n. 2 fatture (riportanti la dicitura\n"esente IVA Legge Bersani")'
    ).rows == []


def test_bdgt_tax_document_and_invoice_numbers_are_not_citations():
    samples = (
        "Commissione Tributaria Provinciale di Messina avverso la cartella di "
        "pagamento n. 295 2011",
        "provvedimento gravato, ha argomentato che la fornitura oggetto della "
        "fattura n. 39/2017",
    )
    for text in samples:
        assert ENG.extract(text).rows == [], text


def test_bdgt_calendar_period_is_not_a_legal_partition():
    row = _one(
        "periodo 8/3/2020-31/8/2021 (ovvero dal 21 febbraio 2020 per i soggetti "
        "indicati al comma 2bis dell'art. 68 D.L. 18/2020"
    )
    assert row["urn"] == "urn:nir:stato:decreto.legge:2020;18~art68-comma2bis"
    assert "periodo" not in row["partition"]


def test_bdgt_narrative_date_does_not_extend_later_case_citation():
    row = _one(
        "13.12.2011, ritenuto legittimo all'esito del giudizio conclusosi con "
        "sentenza della C.T.R. Lazio n. 6508/2017"
    )
    assert row["urn"] == "ECLI:IT:CTRLAZ:2017:6508"
    assert row["text"] == "sentenza della C.T.R. Lazio n. 6508/2017"


def test_self_reference_with_date():
    assert _urns_auth("questa Corte, sent. n. 4091 dell'8 luglio 1985", "CORTE_CASS") == \
        ["ECLI:IT:CASS:1985:4091CIV"]


def test_own_pronouncement_not_a_citation():
    # the document's own pronouncement (self-ref + date, NO citation number) must not become
    # an ECLI even with default_authority set
    assert _urns_auth("questa Corte ha pronunciato la seguente sentenza il 15 marzo 2024",
                      "CORTE_CASS") == []


# --- citation series + bare article-of-code + old EU YY/NNN ------------------
def test_citation_series_split():
    assert _urns_auth("Cass. nn. 123/2020, 456/2023 e 678/2010", "") == [
        "ECLI:IT:CASS:2010:678CIV", "ECLI:IT:CASS:2020:123CIV", "ECLI:IT:CASS:2023:456CIV"]
    assert _urns_auth("Cass. n. 123/2020 n.456/2023, n. 678/2010", "") == [
        "ECLI:IT:CASS:2010:678CIV", "ECLI:IT:CASS:2020:123CIV", "ECLI:IT:CASS:2023:456CIV"]


def test_bare_article_of_code():
    assert _urns("342 c.p.c.") == ["urn:nir:stato:regio.decreto:1940;1443:1~art342"]
    assert _urns("1600 c.c.") == ["urn:nir:stato:regio.decreto:1942;262:2~art1600"]
    # a quantity not adjacent to the code must not become an article
    assert ENG.extract("il termine di 30 giorni e c.c.").rows == [] or \
        all("art30" not in (r.get("url", "") or "") for r in ENG.extract("il termine di 30 giorni e c.c.").rows)


def test_old_eu_directive_two_digit_year():
    assert _urns("Direttiva 77/388/CEE") == ["CELEX:31977L0388"]
    assert _urns("Direttiva 90/434/CEE") == ["CELEX:31990L0434"]


# --- full-document interaction fixes (Task-A gold) ---------------------------
def test_authority_binds_to_sentenza_not_nearer_legislation_alias():
    # "Questa Corte" must attach to the sentenza (case-law), NOT the nearer c.p.c. alias;
    # otherwise art. 115 loses its URN and the self-pronouncement loses its ECLI.
    urns = _urns_auth(
        "violazione dell'art. 115 c.p.c. Questa Corte, con sentenza n. 4091/1985, "
        "ha chiarito.", "CORTE_CASS")
    assert urns == ["ECLI:IT:CASS:1985:4091CIV",
                    "urn:nir:stato:regio.decreto:1940;1443:1~art115"]


def test_directive_is_eu_without_explicit_acronym():
    # a directive whose acronym binds elsewhere (or is absent) is still an EU act (CELEX),
    # not national legislation: "direttiva 2006/112/CE e della direttiva 77/388/CEE".
    assert _urns("art. 9, paragrafo 1, della direttiva 2006/112/CE e della direttiva "
                 "77/388/CEE") == ["CELEX:31977L0388", "CELEX:32006L0112~art9-num1"]


def test_lettered_partition_does_not_swallow_following_word():
    # "lett. b), del d.P.R." must yield only letter b — not a stray letter "d" from "del".
    assert _urns("art. 10, comma 1, lett. b), del d.P.R. 917/1986") == [
        "urn:nir:presidente.repubblica:decreto:1986;917~art10-comma1-letb"]
    # a conjunction "e" is a separator, not a value ("a e b" -> a, b); but a real value "e"
    # in a comma list is kept ("d, e, f" -> d, e, f).
    assert _urns("art. 5, lett. a, b e c, del d.lgs. 546/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art5-leta",
        "urn:nir:stato:decreto.legislativo:1992;546~art5-letb",
        "urn:nir:stato:decreto.legislativo:1992;546~art5-letc"]
    assert _urns("art. 5, lett. d, e, f, del d.lgs. 546/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art5-letd",
        "urn:nir:stato:decreto.legislativo:1992;546~art5-lete",
        "urn:nir:stato:decreto.legislativo:1992;546~art5-letf"]


def test_multi_article_list_distributes_act_base():
    assert _urns("artt. 14, 15 e 18 del d.lgs. 546/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art14",
        "urn:nir:stato:decreto.legislativo:1992;546~art15",
        "urn:nir:stato:decreto.legislativo:1992;546~art18"]


# --- partition ranges (one reference per element) ---------------------------
def test_comma_range_da_a():
    base = "urn:nir:stato:decreto.legislativo:1992;546~art23-comma"
    assert _urns("art. 23, commi da 5 a 8, del d.lgs. 546/1992") == [
        base + "5", base + "6", base + "7", base + "8"]


def test_comma_range_dash():
    base = "urn:nir:stato:decreto.legislativo:1992;546~art34-comma"
    assert _urns("art. 34, commi 5-7, del d.lgs. 546/1992") == [
        base + "5", base + "6", base + "7"]


def test_article_range_da_a():
    base = "urn:nir:stato:decreto.legislativo:1992;546~art"
    assert _urns("articoli da 34 a 36 del d.lgs. 546/1992") == [
        base + "34", base + "35", base + "36"]


def test_range_not_confused_with_latin_suffix():
    # "2-bis" is a suffix, not a range 2..bis
    assert _urns("art. 19, commi 1 e 2-bis, DPR 600/1973") == [
        "urn:nir:presidente.repubblica:decreto:1973;600~art19-comma1",
        "urn:nir:presidente.repubblica:decreto:1973;600~art19-comma2bis"]


def test_soft_hyphen_in_latin_partition_suffix():
    assert _urns("articolo 119, comma 13\u00adter, del decreto legge n. 34 del 2020") == [
        "urn:nir:stato:decreto.legge:2020;34~art119-comma13ter"]
    assert _urns("comma 8\u00adbis dell'articolo 119 del decreto legge n. 34 del 2020") == [
        "urn:nir:stato:decreto.legge:2020;34~art119-comma8bis"]


def test_letter_partition_stops_before_elided_article():
    assert _urns("art. 2, comma 1, lett. b), l'edificabilita', del d.lgs. n. 504/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;504~art2-comma1-letb"]


# --- CGUE case id -> CELEX (sector 6) ----------------------------------------
def test_cgue_case_number_builds_celex():
    # number/year of "C-123/20" are enough; no explicit "Corte di giustizia" needed
    assert _urns("causa C-123/20") == ["CELEX:62020CJ0123"]


def test_cgue_case_with_punti_range():
    base = "CELEX:62020CJ0123~num"
    assert _urns("causa C-123/20, punti 20-22") == [base + "20", base + "21", base + "22"]


def test_court_docket_number_not_attached_to_distant_act():
    # "(Cass. ..., n. 16189/2023)" is the court's docket number — it must not also be claimed
    # by the earlier "L. n. 53/1994", which would invent a phantom "legge 16189/2023".
    assert _urns_auth(
        "art. 9 L. n. 53/1994 e la giurisprudenza (Cass. civ. III Sez., n. 16189/2023)", "") == [
        "ECLI:IT:CASS:2023:16189CIV", "urn:nir:stato:legge:1994;53~art9"]


# --- context propagation: doctype+number act -> a later bare article ---------
def test_doctype_number_propagates_to_far_bare_article():
    # a fully-identified national act lends itself to a later bare article (out of the direct
    # attachment window), the same way a code alias does
    urns = _urns("Il d.lgs. 546/1992 regola il processo tributario in primo e secondo grado "
                 "di giudizio. L'art. 5 fissa la competenza.")
    assert "urn:nir:stato:decreto.legislativo:1992;546~art5" in urns


def test_conversion_law_is_not_bare_article_propagation_source():
    urns = _urns(
        "L'articolo 2 del decreto legge 16 febbraio 2023, n. 11, convertito con modificazioni "
        "dalla legge 11 aprile 2023, n. 38, ha introdotto una disciplina. In particolare, "
        "l'articolo 2 stabilisce il divieto.")
    assert "urn:nir:stato:legge:2023;38" in urns
    assert "urn:nir:stato:legge:2023;38~art2" not in urns
    assert "urn:nir:stato:decreto.legge:2023;11~art2" in urns


def test_propagation_never_from_caselaw():
    # an ECLI takes no partition: a bare article after a Cassazione cite must NOT inherit it
    assert _urns_auth(
        "Cass. n. 123/2020 ha deciso una questione di diritto societario assai complessa e "
        "molto articolata nei suoi passaggi. L'art. 5 prevede una regola.", "") == [
        "ECLI:IT:CASS:2020:123CIV"]


def test_bare_alias_propagates_to_far_article():
    # a bare code/TU named once, then a later bare article -> inherits the act
    assert "urn:nir:presidente.repubblica:decreto:1986;917~art109" in _urns(
        "Il TUIR disciplina la determinazione del reddito d'impresa secondo il principio di "
        "competenza economica. In particolare, l'art. 109 individua i criteri.")
    assert "urn:nir:stato:regio.decreto:1942;262:2~art1218" in _urns(
        "Il codice civile disciplina la responsabilita' contrattuale ed extracontrattuale del "
        "debitore. In tale quadro, l'art. 1218 regola l'inadempimento.")


def test_constitution_alias_does_not_propagate_to_later_bare_article():
    urns = _urns(
        "Si richiamano l'art. 53 Cost. e l'art. 97 Cost.; "
        "il termine di cui al citato art. 2, comma 8-bis non rileva.")
    assert "urn:nir:stato:costituzione~art53" in urns
    assert "urn:nir:stato:costituzione~art97" in urns
    assert "urn:nir:stato:costituzione~art2-comma8bis" not in urns


def test_costituzione_common_noun_is_not_the_constitution():
    # lowercase "costituzione in giudizio" (joining proceedings) is NOT the Constitution
    assert _urns("la costituzione in giudizio del convenuto") == []
    assert _urns("art. 117 Cost.") == ["urn:nir:stato:costituzione~art117"]


def test_range_not_captured_by_later_article_via_act_connector():
    # "commi da 5 a 7, del d.lgs. ... mentre l'art. 22" — the act's own "del" must not let the
    # later art. 22 swallow the comma range (backward-link only when 'del' is adjacent)
    base = "urn:nir:stato:decreto.legislativo:1992;546~"
    assert _urns("L'art. 23, commi da 5 a 7, del d.lgs. 546/1992 disciplina il deposito, "
                 "mentre l'art. 22 regola la costituzione in giudizio.") == [
        base + "art22", base + "art23-comma5", base + "art23-comma6", base + "art23-comma7"]


# --- text / context fields on multi-element citations -----------------------
def test_text_and_context_on_article_list():
    rows = ENG.extract("artt. 14, 15 e 18 del d.lgs. 546/1992").rows
    ctx = "artt. 14, 15 e 18 del d.lgs. 546/1992"
    assert [r["text"] for r in rows] == ["artt. 14", "15", "18 del d.lgs. 546/1992"]
    assert all(r["context"] == ctx for r in rows)        # context shared by every sibling


def test_text_on_range_uses_symbol_for_interpolated():
    rows = ENG.extract("art. 34, commi 5-7, del d.lgs. 546/1992").rows
    # the interpolated middle element renders as the range symbol only
    assert [r["text"] for r in rows] == ["art. 34, commi 5", "-", "7, del d.lgs. 546/1992"]


# --- real-world citation forms + regression fixes ---------------------------
def test_preleggi_normalized_as_codice_civile():
    assert _urns("art. 11 preleggi") == ["urn:nir:stato:regio.decreto:1942;262:2~art11"]


def test_statuto_contribuente_variants():
    base = "urn:nir:stato:legge:2000;212~art"
    assert _urns("art. 12 statuto contribuente") == [base + "12"]
    assert _urns("art. 7 comma 1 Statuto dei diritti dei contribuenti") == [base + "7-comma1"]
    assert _urns("Statuto del contribuente") == ["urn:nir:stato:legge:2000;212"]


def test_special_region_statute_aliases():
    cases = {
        "art. 14 Statuto Regione Sicilia":
            "urn:nir:stato:legge.costituzionale:1948;2~art14",
        "art. 14 Statuto della Regione Sicilia":
            "urn:nir:stato:legge.costituzionale:1948;2~art14",
        "art. 14 Statuto della Regione Siciliana":
            "urn:nir:stato:legge.costituzionale:1948;2~art14",
        "art. 3 Statuto della Regione Sardegna":
            "urn:nir:stato:legge.costituzionale:1948;3~art3",
        "art. 4 Statuto della Regione Sarda":
            "urn:nir:stato:legge.costituzionale:1948;3~art4",
        "art. 5 Statuto della Regione Valle d'Aosta":
            "urn:nir:stato:legge.costituzionale:1948;4~art5",
        "art. 6 Statuto Regione Trentino-Alto Adige":
            "urn:nir:stato:legge.costituzionale:1948;5~art6",
        "art. 7 Statuto della Regione Friuli-Venezia Giulia":
            "urn:nir:stato:legge.costituzionale:1963;1~art7",
    }
    for text, expected in cases.items():
        assert _urns(text) == [expected], text


def test_special_region_statute_is_self_valid_and_renderable():
    from linkengine import urn_to_text

    urn = _urns("Statuto speciale della Regione Siciliana")[0]
    assert urn == "urn:nir:stato:legge.costituzionale:1948;2"
    assert urn_to_text(urn) == "Statuto della Regione Siciliana"


def test_testo_unico_registro_and_doganale():
    assert _urns("art. 78 T.U. Registro") == ["urn:nir:stato:regio.decreto:1986;131~art78"]
    assert _urns("art. 303 comma 3 TULD") == [
        "urn:nir:presidente.repubblica:decreto:1973;43~art303-comma3"]


def test_eu_named_regulations():
    assert _urns("articolo 4, punto 1, GDPR") == ["CELEX:32016R0679~art4-punto1"]
    assert _urns("articolo 5, paragrafo 1, RGPD") == ["CELEX:32016R0679~art5-num1"]
    assert _urns("art. 32 Codice Doganale Comunitario (CDC)") == ["CELEX:31992R2913~art32"]
    assert _urns("art. 10 codice doganale dell’unione europea") == ["CELEX:32013R0952~art10"]


def test_trattato_ce_and_bare_ce_after_partition():
    assert _urns("art 12 Trattato CE") == ["CELEX:12002E/TXT~art12"]
    assert _urns("articolo 56 CE") == ["CELEX:12002E/TXT~art56"]
    assert _urns("articolo 58, paragrafo 3, CE") == ["CELEX:12002E/TXT~art58-num3"]
    # a bare "CE" with no preceding article must NOT become a citation
    assert _urns("la societa' CE ha presentato ricorso") == []


def test_decreto_legislativo_vo_abbreviations():
    base = "urn:nir:stato:decreto.legislativo:"
    assert _urns("art.17 D.Lg.vo n.472/97") == [base + "1997;472~art17"]
    assert _urns("art. 11 d.lgv. 504/92") == [base + "1992;504~art11"]


def test_letter_abbreviations_let_and_not_swallowing_initial():
    base = "urn:nir:stato:legge:2010;220~art1-comma66-let"
    assert _urns("art. 1 comma 66 let. b l. n. 220/2010") == [base + "b"]
    assert _urns("art. 1 comma 66 let b l. n. 220/2010") == [base + "b"]
    # "lett. g, D.Lgs." -> letter g only (not a stray letter d from the abbreviation)
    assert _urns("art. 59, comma 1, lett. g, D.Lgs. n. 446/1997") == [
        "urn:nir:stato:decreto.legislativo:1997;446~art59-comma1-letg"]


def test_interpello_and_ade_abbreviations():
    assert _urns("Risposta ad interpello n. 342 del 13 maggio 2021") == ["PRAX:AE:INT:2021:342"]
    assert _urns("Risoluzione Ag. Entrate n. 91/2004") == ["PRAX:AE:RIS:2004:91"]
    assert _urns("Circ. AdE n. 47/2005") == ["PRAX:AE:CIRC:2005:47"]


def test_two_digit_year_century_pivot():
    # a citation cannot postdate the current year: "r.d. 1611/33" is 1933, not 2033
    assert _urns("art. 2 del citato r.d. 1611/33") == [
        "urn:nir:stato:regio.decreto:1933;1611~art2"]


def test_day_not_read_as_year():
    # "n. 53 del 18 marzo 2013": the year is 2013, not 2018 (the day "18")
    assert _urns("D.P.R. n. 53 del 18 marzo 2013") == [
        "urn:nir:presidente.repubblica:decreto:2013;53"]
    assert _urns("art. 38 D.P.R. 600 del 29 settembre 1973") == [
        "urn:nir:presidente.repubblica:decreto:1973;600~art38"]


def test_leading_article_number_before_act():
    # Cassazione style: the article number precedes the act ("48 legge ... n. 833" -> art 48)
    assert "urn:nir:stato:legge:1978;833~art48" in _urns("48 legge 23.12.1978 n. 833")
    # a 4-digit year before an act must NOT become an article
    assert _urns("nel 2018 la legge 205 ha introdotto") == []


# --- convenzioni doppia imposizione, leggi regionali, caselaw section ---------
def test_convenzione_doppia_imposizione_to_ratification_law():
    # the treaty resolves to the Italian ratification law (Italy-France -> legge 20/1992)
    assert _urns("Convenzione Italia-Francia, art. 15") == ["urn:nir:stato:legge:1992;20~art15"]
    assert _urns("art. 19 Convenzione contro le doppie imposizioni tra Italia e Spagna") == [
        "urn:nir:stato:legge:1980;663~art19"]
    # Italy-Switzerland (1976) -> ratification law l. 943/1978
    assert _urns("Convenzione tra Italia e Svizzera") == ["urn:nir:stato:legge:1978;943"]
    # a country with no ratification law in the table yields no URN
    assert _urns("Convenzione tra Italia e San Marino") == []


def _urns_region(text, region):
    from linkengine import LinkEngine
    eng = LinkEngine(default_region=region)
    return sorted({r["urn"] for r in eng.extract(text).rows if r["urn"]})


def test_legge_regionale_with_region_name():
    assert _urns("L. reg. Campania n. 28 del 2003") == ["urn:nir:regione.campania:legge:2003;28"]
    assert _urns("art. 23 l. reg. Calabria n. 11/2003") == [
        "urn:nir:regione.calabria:legge:2003;11~art23"]
    assert _urns("L. Regione Campania n. 4/2007") == ["urn:nir:regione.campania:legge:2007;4"]


def test_legge_regionale_default_region():
    # no region named -> the document's default region fills it in
    assert _urns_region("art. 5 l. reg. n. 20/2010", "Campania") == [
        "urn:nir:regione.campania:legge:2010;20~art5"]
    # a "legge regola" / national legge must not be mistaken for regional
    assert _urns("la legge regola la materia") == []
    assert _urns("art. 5 della legge 241/1990") == ["urn:nir:stato:legge:1990;241~art5"]


def test_caselaw_section_captured():
    from linkengine import LinkEngine
    eng = LinkEngine(default_authority="CORTE_CASS")
    # Cassazione sections use the "<n>CIV/PEN" / "UNITE" chamber form (item 3); tributaria = 5CIV
    sec = {r["section"] for r in eng.extract("Cass., sez. trib., n. 5000/2019").rows if r["section"]}
    assert sec == {"5CIV"}
    sec = {r["section"] for r in eng.extract("Cass. sez. un. n. 12345/2018").rows if r["section"]}
    assert sec == {"UNITE"}
    sec = {r["section"] for r in eng.extract("Cassazione, sez. V, n. 5953/2021").rows if r["section"]}
    assert sec == {"5CIV"}                       # roman numeral -> arabic, civil chamber


# --- edge cases surfaced while growing the gold ------------------------------
def test_letto_word_not_read_as_letter():
    # "letto" (read) must not be parsed as "lett" + letter o
    assert _urns("art. 15 della Convenzione Italia-Francia, letto unitamente all'art. 23 "
                 "del TUIR") == ["urn:nir:presidente.repubblica:decreto:1986;917~art23",
                                 "urn:nir:stato:legge:1992;20~art15"]


def test_directive_and_cgue_case_in_adjacent_sentences_stay_separate():
    # the directive's article and the CGUE case's punti must not merge across sentences
    assert _urns_auth(
        "L'art. 167 della direttiva 2006/112/CE. La Corte, nella causa C-152/02, punti 35 "
        "e 36, ne ha precisato i limiti.", "CGUE") == [
        "CELEX:32006L0112~art167", "CELEX:62002CJ0152~num35", "CELEX:62002CJ0152~num36"]


# --- urn_generator path coverage: previously-missing paths -------------------
def test_legge_costituzionale_path():
    assert _urns("art. 1 della legge costituzionale n. 3/2001") == [
        "urn:nir:stato:legge.costituzionale:2001;3~art1"]


def test_delibera_comunale_other_path():
    # delibera del Comune -> DEL:CO{city} (urn_generator "other" dispatch)
    row = _one("delibera del Comune di Roma n. 50/2020")
    assert row["ref-type"] == "other acts"
    assert row["urn"] == "DEL:CORM:2020:50"
    # "delibera" as a verb (no Comune, no number) must not produce a citation
    assert _urns("Il Consiglio delibera l'approvazione del bilancio") == []


def test_delibera_comunale_accepts_partition():
    from linkengine import urn_to_text

    row = _one("art. 3 della delibera del Comune di Roma n. 50/2020")
    assert row["ref-type"] == "other acts"
    assert row["partition"] == "articolo-3"
    assert row["urn"] == "DEL:CORM:2020:50~art3"
    assert urn_to_text(row["urn"]) == "art. 3 delibera del Comune di Roma n. 50/2020"


def test_tribunale_sorveglianza_and_assise_ecli():
    # authority names must match urn_generator's dispatch
    assert _urns("Tribunale di Sorveglianza di Roma n. 100/2020") == [
        "ECLI:IT:TRIBSORVRM:2020:100"]
    assert _urns("Corte d'Assise di Milano n. 5/2019") == ["ECLI:IT:ASSMI:2019:5"]


def test_commissione_tributaria_centrale_path():
    assert _urns("Commissione Tributaria Centrale n. 123/1989") == ["ECLI:IT:CTCIT:1989:123"]


# --- ordinal comma, national regolamento, leading-article (resolvable-domain fixes) -------
def test_ordinal_comma_numeric_and_roman():
    assert _urns("art. 21, 1° comma, della legge 133/1999") == [
        "urn:nir:stato:legge:1999;133~art21-comma1"]
    assert _urns("art. 32, II comma, della legge 142/1990") == [
        "urn:nir:stato:legge:1990;142~art32-comma2"]
    # "i commi 1 e 2" must NOT read the article "i" as a roman comma
    assert _urns("i commi 1 e 2 del d.lgs. 546/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;546~comma1",
        "urn:nir:stato:decreto.legislativo:1992;546~comma2"]


def test_comma_abbreviation_c():
    # "c. 2" is comma 2 (followed by a digit); "c.c." stays the codice civile
    assert _urns("art. 7, c. 2, del d.P.R. 633/1972") == [
        "urn:nir:presidente.repubblica:decreto:1972;633~art7-comma2"]
    assert _urns("art. 2697 c.c.") == ["urn:nir:stato:regio.decreto:1942;262:2~art2697"]


def test_bare_regolamento_is_national():
    # a regolamento with no EU acronym defaults to a national regolamento
    assert _urns("regolamento 2913/92") == ["urn:nir:stato:regolamento:1992;2913"]
    assert _urns("regolamento (UE) 2016/679") == ["CELEX:32016R0679"]


def test_leading_article_with_del_connector():
    # Cassazione style "N del ACT": the leading number is the cited article
    assert "urn:nir:stato:legge:1978;833~art48" in _urns("48 della legge 833/1978")
    assert "urn:nir:presidente.repubblica:decreto:1972;633~art56" in _urns(
        "56 del D.P.R. n. 633 del 1972")


# --- broader-corpus patterns: cod. proc. amm. / cod. pen. mil. / regolamento flag --------
def test_codice_processo_amministrativo_abbreviation():
    base = "urn:nir:stato:decreto.legislativo:2010;104:2~art"
    assert _urns("art. 122 cod. proc. amm.") == [base + "122"]
    assert _urns("art. 123, comma 3, c.p.a.") == [base + "123-comma3"]


def test_codice_penale_militare_not_codice_penale():
    # "cod. pen. mil. pace" must be the military code, not the plain codice penale
    assert _urns("art. 264 cod. pen. mil. pace") == [
        "urn:nir:stato:relazione.e.regio.decreto:1941;303:1~art264"]
    assert _urns("art. 314 c.p.") == ["urn:nir:stato:regio.decreto:1930;1398:1~art314"]


def test_regolamento_default_scope_flag():
    from linkengine import LinkEngine

    def urns(text, **kw):
        eng = LinkEngine(**kw)
        return sorted({r["urn"] for r in eng.extract(text).rows if r["urn"]})
    # default: a bare regolamento is national; the flag makes it EU; an EU acronym always wins
    assert urns("regolamento n. 3950/1992") == ["urn:nir:stato:regolamento:1992;3950"]
    assert urns("regolamento n. 3950/1992", default_regolamento_scope="comunitario") == \
        ["CELEX:31992R3950"]
    assert urns("regolamento (UE) 2016/679", default_regolamento_scope="nazionale") == \
        ["CELEX:32016R0679"]


def test_ocr_accommodations_flag():
    from linkengine import LinkEngine

    ocr_law = "artt. 7 I. 212/00"
    ocr_dl = "art. 36, comma 2, d. I. n. 223 del 2006"
    assert _urns(ocr_law) == ["urn:nir:stato:legge:2000;212~art7"]
    assert _urns(ocr_dl) == ["urn:nir:stato:decreto.legge:2006;223~art36-comma2"]

    strict = LinkEngine(ocr_accommodations=False)
    assert strict.extract(ocr_law).rows == []
    assert strict.extract(ocr_dl).rows == []
    assert [r["urn"] for r in strict.extract("art. 7 l. 212/00").rows] == [
        "urn:nir:stato:legge:2000;212~art7"]

    assert [r["urn"] for r in strict.extract(ocr_law, ocr_accommodations=True).rows] == [
        "urn:nir:stato:legge:2000;212~art7"]
    assert ENG.extract(ocr_law, ocr_accommodations=False).rows == []


# --- older date-based caselaw + 2-digit-year dates (broader-corpus fixes) ----------------
def test_caselaw_year_from_date():
    # "Cass. 10.10.1962, n. 2920" — the ECLI year comes from the date, not an explicit year
    assert _urns_auth("Cass. 10.10.1962, n. 2920", "CORTE_CASS") == ["ECLI:IT:CASS:1962:2920CIV"]
    # a self-pronouncement (date, no citation number) must still NOT become a citation
    assert _urns_auth("questa Corte ha pronunciato la presente sentenza il 15 marzo 2024",
                      "CORTE_CASS") == []


def test_date_number_caselaw_series_pairs_correctly():
    # each "Cass. <date>, n. <num>" in a series keeps its own date+number pairing
    assert _urns_auth("Cass. 10.10.1962, n. 2920; Cass. 26.11.1977, n. 5157", "CORTE_CASS") == [
        "ECLI:IT:CASS:1962:2920CIV", "ECLI:IT:CASS:1977:5157CIV"]


def test_caselaw_date_after_number_does_not_hop_to_next_reference():
    assert _urns_auth(
        "Sez. 6-5, ord. n. 8131 del 3 aprile 2018 e Sez. 5 ord. n. 5459 del 13 giugno 2018",
        "CORTE_CASS") == [
        "ECLI:IT:CASS:2018:5459CIV", "ECLI:IT:CASS:2018:8131CIV"]


def test_split_caselaw_anchor_drops_next_number_marker():
    rows = LinkEngine(default_authority="CORTE_CASS").extract(
        "ordinanze della Sezione VI-5 n. 12018 del 13 aprile 2022, nn. 4307").rows
    row = next(r for r in rows if r["urn"] == "ECLI:IT:CASS:2022:12018CIV")
    assert row["text"] == "ordinanze della Sezione VI-5 n. 12018 del 13 aprile 2022"


def test_number_marker_trim_does_not_cut_codice_penale_anchor():
    rows = LinkEngine().extract("art. 240 cod. pen. e artt. 444 e 445 cod. proc. pen.").rows
    texts = {r["urn"]: r["text"] for r in rows}
    assert texts["urn:nir:stato:regio.decreto:1930;1398:1~art240"] == "art. 240 cod. pen."
    assert texts["urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art445"] == \
        "445 cod. proc. pen."


def test_two_digit_year_dates():
    assert _urns("art. 12 L. 3/8/78 n. 405") == ["urn:nir:stato:legge:1978;405~art12"]
    assert _urns("art. 39 del D.P.R. 12/2/65 n. 162") == [
        "urn:nir:presidente.repubblica:decreto:1965;162~art39"]
    # a full 4-digit date must still not be read as a citation on its own
    assert ENG.extract("il contratto del 31/12/2020 per euro 588.000").rows == []


# --- robust date validation, num/sez/year, historical acts, allegato abbreviation ---------
def test_date_year_range_validation():
    from linkengine.normalize import valid_year, valid_date, MIN_YEAR
    assert MIN_YEAR == 1861
    assert valid_year("1973") == "1973" and valid_year("65") == "1965"
    assert valid_year("2050") is None and valid_year("1800") is None  # out of [1861, 2030]
    assert valid_date("12", "2", "1965") == "1965"
    assert valid_date("45", "2", "1965") is None   # day > 31
    assert valid_date("12", "13", "1965") is None  # month > 12


def test_numeric_date_separators_and_2digit_year():
    base = "urn:nir:presidente.repubblica:decreto:1965;162"
    for sep in ("/", ".", "-"):
        assert _urns(f"art. 39 del D.P.R. 12{sep}2{sep}65 n. 162") == [base + "~art39"]
    assert _urns("D.P.R. 12.02.1965 n. 162") == [base]   # leading zeros tolerated


def test_caselaw_number_section_year():
    # "n. 1234/5/2020" = number 1234, section 5, year 2020 (not a date)
    assert _urns_auth("Cass. n. 1234/5/2020", "CORTE_CASS") == ["ECLI:IT:CASS:2020:1234CIV"]


def test_historical_luogotenenziale_and_cps_acts():
    assert _urns("d.l.lgt. n. 1501 del 1947") == ["urn:nir:luogotenente:decreto.legge:1947;1501"]
    assert _urns("decreto legislativo luogotenenziale n. 369/1944") == [
        "urn:nir:luogotenente:decreto.legislativo:1944;369"]
    assert _urns("art. 3 del d.l. C.P.S. n. 1501 del 1947") == [
        "urn:nir:capo.provvisorio.stato:decreto.legge:1947;1501~art3"]


def test_allegato_abbreviation_and_pre1900_act():
    assert _urns("All. A del D.P.R. n. 634 del 1972") == [
        "urn:nir:presidente.repubblica:decreto:1972;634:a"]
    # pre-1900 act resolves (MIN_YEAR 1861); "alla/della" are not read as allegato
    assert _urns("alleg. F della legge n. 2248 del 1865") == ["urn:nir:stato:legge:1865;2248:f"]
    assert _urns("ai sensi della legge 241/1990") == ["urn:nir:stato:legge:1990;241"]


# --- recognition for reference types that yield no URN (recognized but not normalizable) -
# These fill the feature fields (authority/region/section/number/year/doc-date) even when no
# identifier is built; the recognition fields below are still filled.

def test_tar_fills_region_section_number_year():
    r = _one("T.A.R. Lazio, sez. II, n. 1234/2020")
    assert r["ref-type"] == "caselaw" and r["authority"] == "TRIB_AMM_REG"
    assert r["region"] == "LAZ" and r["section"] == "2"
    assert r["number"] == "1234" and r["year"] == "2020"
    r2 = _one("TAR Campania n. 50/2019")
    assert r2["authority"] == "TRIB_AMM_REG" and r2["region"] == "CAM"
    assert r2["number"] == "50" and r2["year"] == "2019"


def test_dpcm_date_only_builds_urn():
    r = _one("D.P.C.M. 11 marzo 2020")
    assert r["ref-type"] == "legislation"
    assert r["doc-type"] == "DECR" and r["authority"] == "PRES_CONS_MIN"
    assert r["doc-date"] == "2020-03-11"
    assert r["urn"] == "DPCM2020-03-11"
    assert not r["url"]


def test_dpcm_date_only_partition_and_standard_text():
    from linkengine import urn_to_text

    urn = _urns("art. 2 del D.P.C.M. 11 marzo 2020")[0]
    assert urn == "DPCM2020-03-11~art2"
    assert urn_to_text(urn) == "art. 2 D.P.C.M. del 11/03/2020"


def test_dpcm_numbered_builds_urn():
    # numbered DPCM: both engines build urn:nir:presidente.consiglio.ministri:decreto
    assert _urns("D.P.C.M. n. 18 del 2020") == [
        "urn:nir:presidente.consiglio.ministri:decreto:2020;18"]


def test_cedu_sentenza_fills_authority_date_ricorso():
    r = _one("Corte EDU, sentenza del 23 febbraio 2017, ricorso n. 43395/09")
    assert r["ref-type"] == "caselaw"
    assert r["doc-type"] == "SENT" and r["authority"] == "CEDU"
    assert r["number"] == "43395" and r["year"] == "2009"   # ricorso n/year
    assert r["doc-date"] == "2017-02-23"
    assert not r["url"]            # a bare CEDU mention yields no URN


# --- harder recognition cases -----------------------------------------------------------

def test_partition_right_binds_to_genitive_act():
    # "art. 14, comma 3, del d.lgs. 546" binds article+comma to the d.lgs (on the right via
    # 'del'), NOT to the closer c.p.c. on the left.
    assert _urns_auth("art. 269 c.p.c. e dell'art. 14, comma 3, del dlgs. n. 546/1992",
                      "CORTE_CASS") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art14-comma3",
        "urn:nir:stato:regio.decreto:1940;1443:1~art269"]
    # a partition that simply follows its act stays bound left (no spurious right-bind)
    assert _urns("d.lgs. 546/1992, art. 5") == ["urn:nir:stato:decreto.legislativo:1992;546~art5"]


def test_partition_run_binds_to_bare_adjacent_act():
    # "art. 360, comma 1, n. 3, c.p.c." — the whole run binds to the c.p.c. on its right by
    # bare adjacency (no 'del'); article+comma+numero stay one hierarchical partition.
    assert _urns("art. 360, comma 1, n. 3, c.p.c.") == [
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num3"]


def test_series_segmentation_each_partition_to_its_own_act():
    # a series of citations must segment cleanly — no partition bleeding to the wrong act
    assert _urns("art. 13 del d.P.R. 600/1973, art. 54 del d.P.R. 633/1972 e art. 2697 c.c.") == [
        "urn:nir:presidente.repubblica:decreto:1972;633~art54",
        "urn:nir:presidente.repubblica:decreto:1973;600~art13",
        "urn:nir:stato:regio.decreto:1942;262:2~art2697"]
    assert _urns("artt. 1 e 2 del d.lgs. 546/1992 e art. 360, comma 1, n. 3, c.p.c.") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art1",
        "urn:nir:stato:decreto.legislativo:1992;546~art2",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num3"]
    assert _urns("violazione degli artt. 36 e 61 del d.lgs. 546/1992 nonche' dell'art. 132 c.p.c.") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art36",
        "urn:nir:stato:decreto.legislativo:1992;546~art61",
        "urn:nir:stato:regio.decreto:1940;1443:1~art132"]


def test_sentenza_authority_number_reclaim():
    # number hugging an authority already on a SENT anchor joins that pronouncement
    assert _urns("sentenza della Corte Costituzionale n. 348/2007") == ["ECLI:IT:COST:2007:348"]
    assert _urns("ordinanza del Consiglio di Stato n. 567/2018") == ["ECLI:IT:CONSSTATO:2018:567"]
    # a legislation alias in the same span keeps its own partition, separate from the ECLI
    assert _urns("art. 2697 c.c. e sentenza della Corte Cost. n. 200/2020") == [
        "ECLI:IT:COST:2020:200", "urn:nir:stato:regio.decreto:1942;262:2~art2697"]


def test_sezioni_unite_authority_and_multinumber():
    assert _urns("Sezioni Unite, sentenze n. 2281/1990 e n. 13446/1991") == [
        "ECLI:IT:CASS:1990:2281CIV", "ECLI:IT:CASS:1991:13446CIV"]
    assert _urns("SS.UU. n. 16412/2007") == ["ECLI:IT:CASS:2007:16412CIV"]
    # bare "Sezioni Unite" with no number is not a citation (no false positive)
    assert _urns("le Sezioni Unite hanno affermato il principio") == []
    # "sez. un." stays a section qualifier -> the UNITE chamber (item 3)
    sec = {r["section"] for r in ENG.extract("Cass. sez. un. n. 12345/2018").rows if r["section"]}
    assert sec == {"UNITE"}


def test_c_cost_abbrev_is_the_court_with_number():
    # "C. Cost. n. 188/2018" is the Court (ECLI), not the Constitution
    assert _urns("sentenza C. Cost. n. 188 del 2018") == ["ECLI:IT:COST:2018:188"]
    # but a bare/standalone "Cost." is still the Constitution
    assert _urns("art. 3 Cost.") == ["urn:nir:stato:costituzione~art3"]
    assert _urns("ai sensi dell'art. 24 della Costituzione") == [
        "urn:nir:stato:costituzione~art24"]


def test_attached_number_forms_no_space():
    # abbreviation directly followed by the number/year (no space): Cass.1532/2012, l.241/90,
    # and the dense art.N/co.N/della L.N form all parse
    assert _urns("Cass.1532/2012") == ["ECLI:IT:CASS:2012:1532CIV"]
    assert _urns("art.23 della l.241/90") == ["urn:nir:stato:legge:1990;241~art23"]
    assert _urns("art.1, co.707, della L.147/2013") == [
        "urn:nir:stato:legge:2013;147~art1-comma707"]
    # guards: a decimal / a money amount / a date must NOT be read as a number/year
    assert _urns("il 12.05/2012 non rileva") == []
    assert _urns("versamento di 1.532,00 euro") == []
    assert _urns("depositata il 31/12/2020") == []


def test_nospace_code_aliases():
    assert _urns("art. 69 cod.proc.civ.") == ["urn:nir:stato:regio.decreto:1940;1443:1~art69"]
    assert _urns("art. 2697 cod.civ.") == ["urn:nir:stato:regio.decreto:1942;262:2~art2697"]
    assert _urns("art. 81 cod.proc.pen.") == [
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art81"]
    # spaced + bare forms still work
    assert _urns("art. 360 c.p.c.") == ["urn:nir:stato:regio.decreto:1940;1443:1~art360"]
    assert _urns("art. 69 cod. proc. civ.") == ["urn:nir:stato:regio.decreto:1940;1443:1~art69"]


def test_eu_directive_year_number_order():
    # old EU directives are year/number (2-digit year first): 90/435 = number 435, year 1990
    assert _urns("direttiva 90/435") == ["CELEX:31990L0435"]
    assert _urns("art. 12 della direttiva 69/335") == ["CELEX:31969L0335~art12"]
    assert _urns("art. 5, n. 1, della direttiva 90/435") == ["CELEX:31990L0435~art5-num1"]
    # plural 'direttive' + a 4-digit-year-first form
    assert _urns("direttive 92/83/CEE e 92/84/CEE") == ["CELEX:31992L0083", "CELEX:31992L0084"]
    assert _urns("direttiva 2006/112") == ["CELEX:32006L0112"]
    # IT number/year (year last) must be unaffected
    assert _urns("legge 137/1971") == ["urn:nir:stato:legge:1971;137"]


def test_ade_prassi_number_without_n_prefix_and_plural():
    assert _urns("circolare 12/E/2020") == ["PRAX:AE:CIRC:2020:12"]
    assert _urns("risoluzione 22/E/2005") == ["PRAX:AE:RIS:2005:22/E"]
    assert _urns("circolari n. 34/E/2013") == ["PRAX:AE:CIRC:2013:34"]   # plural circolari
    assert _urns("circolare 21/E del 2020") == ["PRAX:AE:CIRC:2020:21"]  # 'del YEAR' variant


def test_dash_number_year_context_guarded():
    # historical Cassazione dash form resolves in an act/court context
    assert _urns("Cass. 2968-73") == ["ECLI:IT:CASS:1973:2968CIV"]
    assert _urns("Cass. S.U. 6477-84") == ["ECLI:IT:CASS:1984:6477CIV"]
    assert _urns("art. 37 della legge 300-1970") == ["urn:nir:stato:legge:1970;300~art37"]
    assert _urns("D.P.R. n. 873-78") == ["urn:nir:presidente.repubblica:decreto:1978;873"]
    # FP guards: partition ranges stay ranges, bare ranges produce nothing
    assert _urns("artt. 34-36 del d.lgs. 546/1992") == [
        "urn:nir:stato:decreto.legislativo:1992;546~art34",
        "urn:nir:stato:decreto.legislativo:1992;546~art35",
        "urn:nir:stato:decreto.legislativo:1992;546~art36"]
    assert _urns("commi 70-73 della legge 296/2006") == [
        "urn:nir:stato:legge:2006;296~comma70", "urn:nir:stato:legge:2006;296~comma71",
        "urn:nir:stato:legge:2006;296~comma72", "urn:nir:stato:legge:2006;296~comma73"]
    assert _urns("le pagine 10-15 del ricorso") == []
    assert _urns("gli anni 1970-1980") == []


def test_descriptive_aliases_tuir_and_codice_ambiente():
    assert _urns("art. 85 del T.U. imposte sui redditi") == [
        "urn:nir:presidente.repubblica:decreto:1986;917~art85"]
    assert _urns("testo unico delle imposte sui redditi, art. 109") == [
        "urn:nir:presidente.repubblica:decreto:1986;917~art109"]
    assert _urns("art. 256 del Codice dell'ambiente") == [
        "urn:nir:stato:decreto.legislativo:2006;152~art256"]


# --- integrated urn column + urn_to_text (URN <-> text) -----------------------------------
def test_extract_outputs_urn_column():
    from linkengine import LinkEngine
    r = LinkEngine().extract("art. 5 del d.lgs. 546/1992").rows[0]
    assert r["urn"] == "urn:nir:stato:decreto.legislativo:1992;546~art5"


def test_urn_to_text_round_of_forms():
    from linkengine.urn import urn_to_text
    cases = {
        "ECLI:IT:CASS:2020:1234CIV": "Cassazione civile n. 1234/2020",
        "ECLI:IT:CASS:1984:877PEN": "Cassazione penale n. 877/1984",
        "ECLI:IT:CGT2LAZ:2024:100": "Corte di Giustizia Tributaria di secondo grado Lazio n. 100/2024",
        "ECLI:IT:CGT1NA:2020:123": "Corte di Giustizia Tributaria di primo grado di Napoli n. 123/2020",
        "ECLI:IT:CTRLAZ:2024:100": "Commissione Tributaria Regionale Lazio n. 100/2024",
        "ECLI:IT:CTPNA:2020:123": "Commissione Tributaria Provinciale di Napoli n. 123/2020",
        "ECLI:IT:COST:2018:188": "Corte Costituzionale n. 188/2018",
        "ECLI:IT:GDPRM:2020:100": "Giudice di Pace di Roma n. 100/2020",
        "ECLI:IT:CTCIT:1989:123": "Commissione Tributaria Centrale n. 123/1989",
        "urn:nir:stato:legge:2010;200~art14-comma4-letb-num1":
            "art. 14 comma 4 let. b num. 1 legge n. 200/2010",
        "urn:nir:presidente.repubblica:decreto:1973;600~art43": "art. 43 D.P.R. n. 600/1973",
        "urn:nir:regione.campania:legge:2003;28~art13": "art. 13 legge regionale Campania n. 28/2003",
        "urn:nir:stato:regio.decreto:1942;262:2~art2697": "art. 2697 codice civile",
        "urn:nir:presidente.repubblica:decreto:1986;917~art109": "art. 109 TUIR",
        "urn:nir:stato:costituzione~art53": "art. 53 Costituzione",
        "CELEX:32006L0112~art2": "art. 2 direttiva 2006/112/CE",
        "CELEX:62020CJ0123~num12": "punto 12 causa C-123/2020",
        "CELEX:62020TJ0045": "causa T-45/2020",
        "PRAX:AE:CIRC:2005:47": "circolare Agenzia delle Entrate n. 47/2005",
        "PRAX:AE:INT:2021:342": "interpello Agenzia delle Entrate n. 342/2021",
    }
    for urn, text in cases.items():
        assert urn_to_text(urn) == text, urn
    assert urn_to_text("") == ""


def test_urn_to_text_autonomous_second_grade_tax_court():
    from linkengine import urn_to_text

    assert urn_to_text("ECLI:IT:CTRBZ:2020:1234").endswith(
        "di Bolzano n. 1234/2020")
    assert urn_to_text("ECLI:IT:CTRTN:2021:55").endswith(
        "di Trento n. 55/2021")
    assert urn_to_text("ECLI:IT:CGT2BZ:2020:1234").endswith(
        "di Bolzano n. 1234/2020")
    assert urn_to_text("ECLI:IT:CGT2TN:2021:55").endswith(
        "di Trento n. 55/2021")


def test_urn_to_text_supports_every_prax_authority_and_type():
    from linkengine.urn import PRAX_AUTHORITY_NAMES, PRAX_TYPE_NAMES, urn_to_text

    for code, name in PRAX_AUTHORITY_NAMES.items():
        assert urn_to_text(f"PRAX:{code}:CIRC:2020:1") == \
            f"circolare {name} n. 1/2020"

    date_types = {"CS", "TEL", "LCIRC"}
    for code, name in PRAX_TYPE_NAMES.items():
        urn = f"PRAX:AE:{code}:20200102" if code in date_types else \
            f"PRAX:AE:{code}:2020:1"
        expected_tail = "del 02/01/2020" if code in date_types else "n. 1/2020"
        assert urn_to_text(urn) == f"{name} Agenzia delle Entrate {expected_tail}"


def test_urn_column_equals_build_urn():
    # the engine's `urn` column is exactly build_urn(row) (the single source of identifiers)
    from linkengine import LinkEngine
    from linkengine.urn import build_urn
    eng = LinkEngine()
    for t in ["Cass. n. 100/2020", "art. 19 del d.lgs. 546/1992", "direttiva 2006/112/CE",
              "Circolare AdE n. 47/2005", "CGT 1 Napoli n. 123/2020"]:
        for r in eng.extract(t).rows:
            assert r["urn"] == build_urn(r)


def test_partitioned_multi_act_frames_do_not_form_cross_products():
    first = "art. 19, co. 3, D. lgs. 596/92 e art. 7 1. n. 212/2000"
    rows = ENG.extract(first).rows
    assert [(row["text"], row["urn"]) for row in rows] == [
        ("art. 19, co. 3, D. lgs. 596/92",
         "urn:nir:stato:decreto.legislativo:1992;596~art19-comma3"),
        ("art. 7 1. n. 212/2000", "urn:nir:stato:legge:2000;212~art7"),
    ]
    assert all(row["text"] for row in rows)

    second = ("art. 19, co. 2, e 20 del D.lgs 546/92, nonché dell'art. 3, "
              "co. 4, 1. 241/90")
    assert _urns(second) == [
        "urn:nir:stato:decreto.legislativo:1992;546~art19-comma2",
        "urn:nir:stato:decreto.legislativo:1992;546~art20",
        "urn:nir:stato:legge:1990;241~art3-comma4",
    ]

    # With OCR accommodations disabled, the damaged second act is sacrificed; it must not
    # inherit the preceding decreto legislativo and recreate a false branch.
    strict = LinkEngine(ocr_accommodations=False).extract(first).rows
    assert [row["urn"] for row in strict] == [
        "urn:nir:stato:decreto.legislativo:1992;596~art19-comma3"]


def test_regio_decreto_chronology_and_document_year_ceiling():
    assert _urns("artt. 69 e 70 R.D. n. 2440/23") == [
        "urn:nir:stato:regio.decreto:1923;2440~art69",
        "urn:nir:stato:regio.decreto:1923;2440~art70",
    ]
    assert _urns("R.D. n. 639/10") == ["urn:nir:stato:regio.decreto:1910;639"]

    impossible = _one("Regio Decreto 13/02/1986 n. 65")
    assert impossible["number"] == "65"
    assert impossible["year"] == impossible["doc-date"] == impossible["urn"] == ""

    future = ENG.extract(
        "Cass. Civ. n. 14874/2026", context=DocumentContext(document_year=2022)
    ).rows[0]
    assert future["number"] == "14874"
    assert future["year"] == future["urn"] == ""

    with pytest.raises(ValueError, match="invalid document year"):
        DocumentContext(document_year=1700)


def test_procedural_header_lines_bound_the_citation_anchor():
    text = ("Sentenza n. 156/2022\nDepositato il 04/07/2022\n"
            "Con ricorsi in data 12.02.18")
    row = _one(text)
    assert row["text"] == row["context"] == "Sentenza n. 156/2022"
    assert row["number"] == "156" and row["year"] == "2022"
    assert row["doc-date"] == ""


def test_bare_ce_treaty_alias_respects_article_range():
    assert ENG.extract("art. 2303 ce").rows == []
    assert _urns("art. 234 CE") == ["CELEX:12002E/TXT~art234"]
    assert _urns("art. 174 del Trattato CE") == ["CELEX:12002E/TXT~art174"]


def test_procedural_docket_runs_and_object_numbers_stay_unbound():
    samples = (
        "CTP di Vercelli RGR 138/18 e 2019/209 conclusi con esito sfavorevole",
        "Commissione Tributaria Provinciale Milano - Sez. 17 -- Rgr n. 24 73/2021",
        "legge, in relazione\nalle cartelle indicate dalla n. 1 alla n. 7",
        "DECISIONE\nRicorrente_1 ha impugnato l'avviso di accertamento n. 428 "
        "del 7 dicembre 2020",
    )
    for text in samples:
        assert ENG.extract(text).rows == [], text

    row = _one("n. 1312, ricorsi respinti dalla CTP di Novara con\nsentenza n. 36/09")
    assert row["text"] == "CTP di Novara con\nsentenza n. 36/09"
    assert row["urn"] == "ECLI:IT:CTPNO:2009:36"


# --- HTML highlighting (html.annotate_html, fragment + page=True) -----------------
import re as _re_html
from linkengine.html import annotate_html


def _strip_tags(html):
    """Recover the visible text from annotated HTML (tags removed, entities un-escaped)."""
    txt = _re_html.sub(r"<[^>]+>", "", html)
    return (txt.replace("&lt;", "<").replace("&gt;", ">")
               .replace("&quot;", '"').replace("&amp;", "&"))


def test_html_wraps_text_field_with_urn():
    html = annotate_html("art. 2697 c.c.")
    assert 'class="lkn-ref"' in html
    assert 'data-urn="urn:nir:stato:regio.decreto:1942;262:2~art2697"' in html
    # the wrapped text is exactly the row's `text` field
    assert ">art. 2697 c.c</span>" in html


def test_html_roundtrips_to_input():
    # the visible text (tags stripped) must reconstruct the original input verbatim
    for s in ["Visto l'art. 2697 c.c. e la Cass. n. 100/2020, si applica il DL 34/2020.",
              "Si vedano gli artt. 15-18 DPR 600/73.",
              "Se 1<2 & art. 3 c.c. vale, allora ok>fine"]:
        assert _strip_tags(annotate_html(s)) == s


def test_html_range_merges_on_hyphen():
    html = annotate_html("artt. 15-18 DPR 600/73")
    # endpoints anchored on their digits
    assert ">artt. 15</span>" in html and ">18 DPR 600/73</span>" in html
    # the inner articles (16, 17) collapse onto the single "-" as one merged tag
    assert 'data-refs="2"' in html
    assert ("data-partition=\"articolo-16 articolo-17\"") in html
    assert ("~art16 urn:nir:presidente.repubblica:decreto:1973;600~art17") in html
    # the visible "-" appears once (not duplicated by the two references)
    assert html.count(">-</span>") == 1


def test_html_only_with_urn_skips_urnless():
    s = "Cfr. Corte EDU n. 123/2020 e art. 3 c.c."
    full = annotate_html(s)
    only = annotate_html(s, only_with_urn=True)
    # Corte EDU has no urn (no ECLI): tagged by default, plain text when only_with_urn
    assert "Corte EDU n. 123/2020</span>" in full
    assert "Corte EDU n. 123/2020</span>" not in only
    assert ">art. 3 c.c</span>" in only          # the c.c. (has urn) is still tagged
    assert _strip_tags(only) == s


def test_html_escapes_non_reference_text():
    html = annotate_html("1<2 & 3>0")            # no references here
    assert html == "1&lt;2 &amp; 3&gt;0"


def test_html_page_is_standalone():
    doc = annotate_html("art. 2697 c.c.", page=True, only_with_urn=True)
    assert doc.startswith("<!doctype html>")
    assert "<style>" in doc and "lkn-ref" in doc
    assert "<pre class=\"lkn-doc\">" in doc
    assert "data-urn=" in doc


def test_html_no_inline_details():
    # the fragment carries details only in data-* attributes, never as a visible `title` tooltip
    html = annotate_html("art. 2697 c.c.")
    assert "title=" not in html
    assert "data-urn=" in html
