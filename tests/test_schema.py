"""The result-file contract (solarbench.eval.schema), and every result file checked in under results/."""

import json
from pathlib import Path

import pytest

from solarbench.eval.schema import rankable, result_path, validate
from solarbench.eval.stats import summarize

RESULT_FILES = sorted((Path(__file__).resolve().parents[1] / "results").glob("*/*.json"))


def make_result(**overrides):
    episodes = [
        {"success": True, "safe_success": True, "damage": False, "duration_s": 10.0, "stage_a": True},
        {"success": True, "safe_success": False, "damage": True, "duration_s": 12.0, "stage_a": True},
        {"success": False, "safe_success": False, "damage": False, "duration_s": 30.0, "stage_a": False},
    ]
    provenance = {"date": "2026-01-01T00:00:00+00:00", "solarbench_git": "abc123", "solarbench_dirty": False,
                  "versions": {}, "gpu": "test", "physics": "NewtonCfg", "physics_dt": 1 / 600, "decimation": 20}
    result = {"task": "T", "policy": "zero", "split": "test", "provenance": provenance,
              "summary": summarize(episodes, ["a"]), "episodes": episodes}
    result.update(overrides)
    return result


def test_a_well_formed_result_is_valid_and_rankable():
    assert validate(make_result()) == []
    assert rankable(make_result()) == []


def test_summary_must_agree_with_the_episode_records():
    result = make_result()
    result["summary"]["success"]["k"] = 3
    assert any("episode records give 2" in e for e in validate(result))


def test_safe_success_with_damage_is_rejected():
    result = make_result()
    result["episodes"][1]["safe_success"] = True
    assert any("safe_success" in e for e in validate(result))


def test_dev_split_or_dirty_tree_is_not_rankable():
    assert any("split" in r for r in rankable(make_result(split="dev")))
    dirty = make_result()
    dirty["provenance"]["solarbench_dirty"] = True
    assert any("not clean" in r for r in rankable(dirty))


@pytest.mark.parametrize("path", RESULT_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_checked_in_results_are_valid(path):
    assert validate(json.loads(path.read_text())) == []


def test_an_existing_result_file_is_never_overwritten(tmp_path):
    first = result_path(tmp_path, "T", "oracle", "test", "newton", "abc1234def")
    assert first.name == "oracle_test_newton.json"
    first.parent.mkdir(parents=True)
    first.write_text("{}")
    second = result_path(tmp_path, "T", "oracle", "test", "newton", "abc1234def")
    assert second.name == "oracle_test_newton_abc1234.json"
    second.write_text("{}")
    third = result_path(tmp_path, "T", "oracle", "test", "newton", "abc1234def")
    assert third.name == "oracle_test_newton_abc1234_2.json"
