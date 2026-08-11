"""Correctness gates: linkengine must keep clearing the hand-verified gold sets
(``tests/gold/``). See ``tests/goldeval.py`` for the scorers."""
import os

import pytest

import goldeval
from linkengine import LinkEngine

G = goldeval.GOLD_DIR


def _has(name):
    return os.path.exists(os.path.join(G, name))


@pytest.mark.skipif(not _has("gold_manual.csv"), reason="gold file missing")
def test_manual_gold():
    npass, total = goldeval.score_recall(os.path.join(G, "gold_manual.csv"))
    assert total >= 100, f"gold shrank unexpectedly ({total} rows)"
    assert npass == total, f"manual gold regression: {npass}/{total}"


@pytest.mark.skipif(not _has("gold_partitions.csv"), reason="gold file missing")
def test_partition_gold():
    npass, total = goldeval.score_recall(os.path.join(G, "gold_partitions.csv"))
    assert npass == total, f"partition gold regression: {npass}/{total}"


@pytest.mark.skipif(not _has("gold_precision.csv"), reason="gold file missing")
def test_precision_gold():
    tp, fp, fn = goldeval.score_precision(os.path.join(G, "gold_precision.csv"))
    assert fp == 0, f"precision gold false positives: {fp}"
    assert fn == 0, f"precision gold misses: {fn}"


@pytest.mark.skipif(not _has("gold_fields.jsonl"), reason="gold file missing")
def test_field_gold():
    npass, total = goldeval.score_fields(os.path.join(G, "gold_fields.jsonl"))
    assert total >= 40, f"field gold shrank unexpectedly ({total} entries)"
    assert npass == total, f"field gold regression: {npass}/{total}"


@pytest.mark.skipif(not _has("gold_normativa.jsonl"), reason="normativa gold file missing")
def test_normativa_gold():
    npass, total = goldeval.score_normativa(os.path.join(G, "gold_normativa.jsonl"))
    gold = goldeval._load_jsonl(os.path.join(G, "gold_normativa.jsonl"))
    years = {entry["act-year"] for entry in gold}
    doctypes = {entry["document-type"] for entry in gold}
    authorities = {entry["authority"] for entry in gold}
    units = {entry["current-unit-urn"] for entry in gold}
    acts = {unit.split("~", 1)[0] for unit in units}
    ids = {entry["id"] for entry in gold}
    famous = sum(entry["selection"] == "famous" for entry in gold)
    random = sum(entry["selection"] == "random" for entry in gold)
    known_misses = sum(entry.get("coverage") == "known-miss" for entry in gold)

    assert total >= 70, f"normativa gold shrank unexpectedly ({total} entries)"
    assert len(ids) == total, "normativa gold contains duplicate ids"
    assert len(units) >= 70 and len(acts) >= 60, \
        f"normativa source diversity narrowed ({len(units)} units, {len(acts)} acts)"
    assert famous >= 20 and random >= 45, \
        f"normativa selection mix shrank (famous={famous}, random={random})"
    assert len(years) >= 40 and min(years) <= 1940 and max(years) >= 2025, \
        f"normativa year coverage narrowed ({min(years)}-{max(years)}, {len(years)} years)"
    assert len(doctypes) >= 7, f"normativa document-type coverage narrowed ({doctypes})"
    assert len(authorities) >= 5, f"normativa authority coverage narrowed ({authorities})"
    assert known_misses >= 10, "normativa evaluation no longer represents known limitations"
    assert npass / total >= 0.80, f"normativa gold regression: {npass}/{total}"


@pytest.mark.skipif(not _has("gold_normativa_eu.jsonl"), reason="EU normativa gold file missing")
def test_normativa_eu_gold():
    path = os.path.join(G, "gold_normativa_eu.jsonl")
    npass, total = goldeval.score_normativa(path, title="GOLD NORMATIVA EU")
    gold = goldeval._load_jsonl(path)
    units = {entry["current-unit-urn"] for entry in gold}
    acts = {unit.split("~", 1)[0] for unit in units}
    years = {entry["act-year"] for entry in gold}
    doctypes = {entry["document-type"] for entry in gold}
    famous = sum(entry["selection"] == "famous" for entry in gold)
    random = sum(entry["selection"] == "random" for entry in gold)
    known_misses = sum(entry.get("coverage") == "known-miss" for entry in gold)

    assert total >= 30, f"EU normativa gold shrank unexpectedly ({total} entries)"
    assert len(units) >= 30 and len(acts) >= 25, \
        f"EU normativa diversity narrowed ({len(units)} units, {len(acts)} acts)"
    assert all(unit.startswith("CELEX:") for unit in units)
    assert famous >= 12 and random >= 15, \
        f"EU normativa selection mix shrank (famous={famous}, random={random})"
    assert len(years) >= 20 and min(years) <= 1958 and max(years) >= 2025, \
        f"EU normativa year coverage narrowed ({min(years)}-{max(years)}, {len(years)} years)"
    assert doctypes >= {"regulation", "directive", "decision"}
    assert known_misses >= 2, "EU normativa evaluation no longer represents known limitations"
    assert npass / total >= 0.85, f"EU normativa gold regression: {npass}/{total}"


@pytest.mark.skipif(not _has("gold_normativa_eu.jsonl"), reason="EU normativa gold file missing")
def test_normativa_eu_complete_external_citations_equal_standard_mode():
    gold = goldeval._load_jsonl(os.path.join(G, "gold_normativa_eu.jsonl"))
    external_only = []
    for entry in gold:
        current_act = entry["current-unit-urn"].split("~", 1)[0]
        if entry["refs"] and all(
                ref["urn"].split("~", 1)[0] != current_act for ref in entry["refs"]):
            external_only.append(entry)

    assert len(external_only) >= 3, "EU gold lost its complete external-citation sample"
    engine = LinkEngine()
    for entry in external_only:
        standard = engine.extract(entry["text"])
        normativa = engine.extract(
            entry["text"],
            mode="normativa",
            current_unit_urn=entry["current-unit-urn"],
        )
        assert normativa.rows == standard.rows, entry["id"]
