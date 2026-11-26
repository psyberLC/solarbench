"""The task atlas loads, and its coverage numbers match what the README states."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("coverage", Path(__file__).resolve().parents[1] / "atlas" / "coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


def test_counts_match_the_readme():
    tasks = coverage.load()
    counts = dict(coverage.skill_counts(tasks))
    assert len(tasks) == 107
    assert (counts["open-door"], counts["torque-fastener"], counts["plug-unplug-connector"]) == (24, 20, 13)


def test_unlock_order_is_monotone_and_complete():
    order = coverage.unlock_order(coverage.load())
    doable = [n for _, n in order]
    assert doable == sorted(doable) and doable[-1] == 101
    assert dict(order)["visual-read"] == 22
