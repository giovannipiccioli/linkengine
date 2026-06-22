"""Correctness gates: linkengine must keep clearing the hand-verified gold sets
(``tests/gold/``). See ``tests/goldeval.py`` for the scorers."""
import os

import pytest

import goldeval

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
