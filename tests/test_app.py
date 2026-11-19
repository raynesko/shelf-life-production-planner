"""T6.1.1/T6.1.2/T6.2.1: dashboard runs on committed files, shows headline numbers verbatim, stays small."""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))
HEADLINE = ROOT / "results" / "headline_numbers.json"


def test_app_data_is_small():
    total = sum(f.stat().st_size for f in (ROOT / "results" / "app_data").rglob("*") if f.is_file())
    assert total <= 20e6


@pytest.mark.parametrize("page", ["overview", "forecast", "plan_viewer", "scenarios"])
def test_page_runs_without_exceptions(page):
    at = AppTest.from_file(str(APP / "views" / f"{page}.py"), default_timeout=60).run()
    assert not at.exception, at.exception


@pytest.mark.skipif(not HEADLINE.exists(), reason="headline numbers not built yet")
def test_overview_cards_equal_headline_json():
    h = json.loads(HEADLINE.read_text())
    at = AppTest.from_file(str(APP / "views" / "overview.py"), default_timeout=60).run()
    shown = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    # Reductions are shown by direction ("% lower" / "% higher") as absolute values; points keep their sign.
    for key, kind in (("expired_waste_reduction_pct", "red"), ("fill_rate_delta_pts", "pts"),
                      ("changeover_hours_reduction_pct", "red"), ("evaluated_cost_reduction_pct", "red"),
                      ("forecast_wape_improvement_pct", "red")):
        v = h[key] if key in h and "estimate" in h[key] else h["monte_carlo"][key]
        if kind == "pts":
            want = [f"{v[p]:+.2f}" for p in ("estimate", "ci_lo", "ci_hi")]
        elif v["estimate"] >= 0:
            want = [f"{v[p]:.1f}" for p in ("estimate", "ci_lo", "ci_hi")] + ["% lower"]
        else:
            want = [f"{-v[p]:.1f}" for p in ("estimate", "ci_lo", "ci_hi")] + ["% higher"]
        for s in want:
            assert s in shown, (key, s)
    assert "simulation on a synthetic plant model" in shown


def test_plan_viewer_switches_week_and_arm():
    at = AppTest.from_file(str(APP / "views" / "plan_viewer.py"), default_timeout=60).run()
    n0 = len(at.get("plotly_chart"))
    at.radio[0].set_value("Optimised").run()
    assert len(at.get("plotly_chart")) == n0 // 2 and not at.exception
    at.select_slider[0].set_value(at.select_slider[0].options[10]).run()
    assert not at.exception
