import pytest

from solarbench.eval.stats import bootstrap_ci, summarize, wilson_ci


@pytest.mark.unit
def test_wilson_matches_reference_values():
    lo, hi = wilson_ci(7, 10)  # reference: [0.3968, 0.8922]
    assert lo == pytest.approx(0.3968, abs=1e-3) and hi == pytest.approx(0.8922, abs=1e-3)
    assert wilson_ci(0, 10)[0] == 0.0 and wilson_ci(10, 10)[1] == pytest.approx(1.0)


@pytest.mark.unit
def test_bootstrap_contains_mean():
    m, lo, hi = bootstrap_ci([1.0, 2.0, 3.0, 4.0])
    assert lo <= m <= hi and m == 2.5


@pytest.mark.unit
def test_summarize_excludes_sim_errors():
    rec = dict(stage_a=True, success=True, safe_success=True, damage=False, duration_s=5.0)
    out = summarize([rec, {**rec, "sim_error": True, "success": False}], stages=["a"])
    assert out["valid_episodes"] == 1 and out["success"]["rate"] == 1.0 and out["sim_error_rate"] == 0.5
