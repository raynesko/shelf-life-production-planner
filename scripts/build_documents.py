"""T7.1.2 / T7.2.1: two-page plan memo and five-slide summary as PDF, every number read from
results/headline_numbers.json (and results/ablation.csv, results/sensitivity/summary.csv). Printed by the installed
Edge/Chrome through Playwright.

Outputs: docs/results/plan_memo.pdf, docs/portfolio/summary_slides.pdf
Run: python scripts/build_documents.py [--channel msedge|chrome]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "results" / "logs" / "documents"
LABEL = "Simulation on a synthetic plant model"

CSS = """
:root { --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --rule:#e1e0d9; --blue:#2a78d6; --orange:#eb6834; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: var(--ink); margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4pt; } h2 { font-size: 12pt; margin: 12pt 0 4pt; color: var(--ink); }
p, li, td, th { font-size: 9.6pt; line-height: 1.38; } .muted { color: var(--muted); font-size: 8.4pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0; }
th, td { border-bottom: 1px solid var(--rule); padding: 3pt 5pt; text-align: left; vertical-align: top; }
th { color: var(--ink2); font-weight: 600; } td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.nums th:not(:first-child) { text-align: right; }
ul { margin: 2pt 0 2pt 14pt; padding: 0; } .tag { color: var(--ink2); font-style: italic; }
"""


def red(v: dict, d: int = 0) -> str:
    if f"{v['ci_lo']:.{d}f}" == f"{v['ci_hi']:.{d}f}":
        d += 1  # a CI that rounds to one value at this precision gets one more decimal
    f = f"{{:.{d}f}}"
    if v["estimate"] >= 0:
        return f"{f.format(v['estimate'])}% lower (95% CI {f.format(v['ci_lo'])}-{f.format(v['ci_hi'])}%)"
    return f"{f.format(-v['estimate'])}% higher (95% CI {f.format(-v['ci_hi'])}-{f.format(-v['ci_lo'])}%)"


def pts(v: dict) -> str:
    return f"{v['estimate']:+.2f} pts (95% CI {v['ci_lo']:+.2f} to {v['ci_hi']:+.2f})"


def rp(x: float) -> str:
    return f"{x:.0f}% lower" if x >= 0 else f"{-x:.0f}% higher"


def img(name: str) -> str:
    return (ROOT / "results" / "figures" / name).as_uri()


def facts(h: dict) -> dict:
    """Every number the memo and slides quote, derived from headline_numbers.json and the sensitivity summary."""
    am = h["monte_carlo_arm_means"]
    sens = pd.read_csv(ROOT / "results" / "sensitivity" / "summary.csv").query("base == 'B1_TUNED'")

    def cell(param: str, value: float) -> pd.Series:
        return sens[(sens.parameter == param) & ((sens.value - value).abs() < 1e-9)].iloc[0]

    co2, co15 = cell("changeover_scale", 2.0), cell("changeover_scale", 1.5)
    sl05, sl075 = cell("shelf_life_scale", 0.5), cell("shelf_life_scale", 0.75)
    return {
        "freed_h": am["B1_TUNED"]["changeover_hours_per_week"] - am["OPT"]["changeover_hours_per_week"],
        "h_opt": am["OPT"]["changeover_hours_per_week"], "h_tuned": am["B1_TUNED"]["changeover_hours_per_week"],
        "h_rot": am["B1"]["changeover_hours_per_week"],
        "u_opt": 100 * am["OPT"]["utilisation"], "u_tuned": 100 * am["B1_TUNED"]["utilisation"],
        "x_opt": am["OPT"]["expired_pct"], "x_tuned": am["B1_TUNED"]["expired_pct"], "x_rot": am["B1"]["expired_pct"],
        "f_opt": 100 * am["OPT"]["fill_rate"], "f_tuned": 100 * am["B1_TUNED"]["fill_rate"],
        "f_rot": 100 * am["B1"]["fill_rate"],
        "co2_fill_tuned": 100 * co2.base_fill_rate, "co2_fill_opt": 100 * co2.opt_fill_rate,
        "co15_fill_tuned": 100 * co15.base_fill_rate, "co15_fill_opt": 100 * co15.opt_fill_rate,
        "sl_waste_pts": (sl075.waste_pts, sl05.waste_pts),
        "cost_range": h["sensitivity"]["cost_reduction_range_pct"], "n_cells": h["sensitivity"]["n_cells"],
        "share_cost": 100 * h["sensitivity"]["share_cells_cost_improved"],
    }


def memo(h: dict, abl: pd.DataFrame) -> str:
    mc, mcd = h["monte_carlo"], h["monte_carlo_vs_b1_default"]
    f = facts(h)
    a = abl.set_index("arm")
    return f"""<html><head><style>{CSS}
@page {{ size: Letter; margin: 0.6in 0.7in; }} .page2 {{ page-break-before: always; }}</style></head><body>
<p class="muted">MEMO &middot; Production planning &middot; {LABEL.lower()}, real Favorita demand</p>
<h1>Optimised weekly planning frees about {f['freed_h']:.0f} line hours a week; a well-tuned simple rule still wins on waste</h1>
<p><b>To:</b> Plant manager, planning lead &nbsp; <b>Re:</b> should the weekly production plan be optimised for shelf
life and allergen changeovers, or is a tuned spreadsheet rule enough?</p>
<h2>Situation</h2>
<p>One refrigerated filling line (72 h a week) makes 12 dairy, deli and prepared-food SKUs with 14-56 days of shelf
life. Product must leave with at least half its life remaining, and switching to a product that does not declare the
previous product's allergen needs a 3.5-hour wet clean. Two simple planning rules were tested against a 13-week
optimiser on the same demand: the common <b>two-week cycle</b> per SKU, and the same rule with its cover
<b>tuned</b> on a past year, which ends up making nearly every SKU every week.</p>
<h2>Results (simulation, test year April 2016 - March 2017, {h['n_paths']} demand scenarios)</h2>
<table class="nums"><tr><th>Average per scenario</th><th>Two-week cycle</th><th>Tuned rule</th><th>Optimiser</th></tr>
<tr><td>Expired product, % of production</td><td class="num">{f['x_rot']:.1f}%</td><td class="num">{f['x_tuned']:.1f}%</td><td class="num">{f['x_opt']:.1f}%</td></tr>
<tr><td>Fill rate</td><td class="num">{f['f_rot']:.1f}%</td><td class="num">{f['f_tuned']:.1f}%</td><td class="num">{f['f_opt']:.1f}%</td></tr>
<tr><td>Changeover hours per week</td><td class="num">{f['h_rot']:.1f}</td><td class="num">{f['h_tuned']:.1f}</td><td class="num">{f['h_opt']:.1f}</td></tr></table>
<p>Optimiser vs the tuned rule, paired across scenarios: changeover hours {red(mc['changeover_hours_reduction_pct'])},
allergen wet-clean hours {red(mc['allergen_clean_hours_reduction_pct'])}, expired product
{red(mc['expired_waste_reduction_pct'])}, fill rate {pts(mc['fill_rate_delta_pts'])}, total planning cost on the
model's weights {red(mc['evaluated_cost_reduction_pct'], 1)}. Against the two-week cycle the optimiser cuts expired
product {red(mcd['expired_waste_reduction_pct'])}.</p>
<h2>Recommendation</h2>
<ul><li><b>If the line is short of hours</b> (growth, new SKUs, downtime) or cleans are long: use the optimiser. It
runs the line at about {f['u_opt']:.0f}% instead of {f['u_tuned']:.0f}%. When cleaning times were doubled in the
stress test, the tuned rule's fill rate fell to {f['co2_fill_tuned']:.0f}% against the optimiser's
{f['co2_fill_opt']:.0f}%.</li>
<li><b>If hours are plentiful and cleans are short:</b> switch from the two-week cycle to the tuned short-cover rule.
It is simple and gives the lowest waste, at the cost of about {f['h_tuned']:.0f} changeover hours a week.</li>
<li><b>Short shelf lives</b> favour the optimiser: with shelf lives cut by 25-50% it expired
{f['sl_waste_pts'][0]:.0f}-{f['sl_waste_pts'][1]:.0f} percentage points less of production than the tuned rule.</li></ul>
<div class="page2"></div>
<h2>Why these results can be trusted, and where they cannot</h2>
<ul><li>Both rules and the optimiser had their one free setting chosen on the year before the test year, with the
same rule; nothing was tuned on the test year.</li>
<li>An independent checker re-validated every executed plan: capacity, allergen cleans and shelf life at shipment
({h['checker_violations_total']} violations in the main experiment).</li>
<li>Across {f['n_cells']} one-at-a-time stress tests the optimiser's total planning cost stayed lower than the tuned
rule's in {f['share_cost']:.0f}% of them ({f['cost_range'][0]:.1f}% to {f['cost_range'][1]:.1f}% lower).</li>
<li>The gain is planning logic, not forecasting: with the current moving-average forecast the optimiser already cuts
expired product {a.loc['OPT_MA4', 'expired_cases_reduction_vs_B1_pct']:.0f}% against the two-week cycle; better
forecast models did not beat the moving average on one-week accuracy.</li>
<li><b>Assumed plant data:</b> cleaning times, rates, costs and shelf lives are estimates, swept but not measured.
The model gives spare hours no value beyond the changeover cost, and ignores breakdowns.</li></ul>
<h2>Recommended rollout</h2>
<ol><li><b>Measure first:</b> 3 months of line logs for changeover and clean durations, and actual weekly line hours
used. This decides which recommendation applies.</li>
<li><b>Shadow mode, 8 weeks, 3 SKUs</b> (one short-life salad, one dip, one dairy cup): produce the optimised plan
next to the real plan each week; compare expiry, fill rate and changeover hours.</li>
<li><b>Go live</b> on those SKUs with planner override and a weekly review; extend if line hours are freed without
losing service.</li></ol>
<h2>What I would validate on real plant data</h2>
<ul><li>Changeover and allergen-clean durations by product pair (line logs, sanitation records).</li>
<li>Run rates, minimum runs, yield, downtime and OEE losses.</li>
<li>Customer minimum-remaining-shelf-life agreements (assumed 50%) and real code dates.</li>
<li>Distribution-centre orders instead of retail sales as the demand signal.</li>
<li>The value of a freed line hour and the cost of a lost vs an expired case.</li></ul>
<p class="muted">{LABEL}. Demand: Corporacion Favorita (Kaggle). Plant, costs and cleaning times are documented
assumptions; no real savings are claimed. Numbers: results/headline_numbers.json (run {h['experiment_run_id']}).</p>
</body></html>"""


def slides(h: dict) -> str:
    mc, mcd = h["monte_carlo"], h["monte_carlo_vs_b1_default"]
    f = facts(h)
    page = "width: 13.333in; height: 7.5in; padding: 0.5in 0.65in; page-break-after: always; position: relative;"
    foot = f'<p class="muted" style="position:absolute; bottom:0.3in;">{LABEL}. Real Favorita demand; documented plant assumptions.</p>'
    return f"""<html><head><style>{CSS}
@page {{ size: 13.333in 7.5in; margin: 0; }} .s {{ {page} }} h1 {{ font-size: 28pt; }} p, li, td, th {{ font-size: 14pt; }}
.cols {{ display: flex; gap: 0.4in; }} .cols > div {{ flex: 1; }} img {{ max-width: 100%; max-height: 4.7in; }}</style></head><body>
<div class="s"><h1>Perishable production planning: waste, service and line time</h1>
<div class="cols"><div><ul><li>One refrigerated line, 12 dairy, deli and prepared-food SKUs, 14-56 days shelf life</li>
<li>Product must ship with at least half its life left</li><li>Allergen changeovers need a 3.5 h wet clean</li>
<li>Make too much: expiry. Too little: lost orders. Switch too often: lost line hours</li>
<li>Question: what does a shelf-life-aware optimiser change, against a planner tuned just as carefully?</li></ul></div>
<div><img src="{(ROOT / 'docs' / 'figures' / 'changeover_heatmap.png').as_uri()}"></div></div>{foot}</div>
<div class="s"><h1>Approach</h1><ul>
<li><b>Data:</b> Favorita grocery sales, 125M rows, 12 perishable items, weekly, scaled to plant cases</li>
<li><b>Forecast:</b> naive, moving average, ETS, ARIMA, Prophet; rolling origin; chosen on a validation year</li>
<li><b>Optimise:</b> 13-week rolling mixed-integer program (OR-Tools) with stock tracked by age, soft safety stock;
CP-SAT for the allergen-aware run order</li>
<li><b>Fair baseline:</b> (s, S) planner with allergen ladder; its cover tuned on the validation year by the same
rule as the optimiser</li>
<li><b>Compare:</b> real test-year replay + {h['n_paths']} paired demand scenarios with bootstrap CIs; {f['n_cells']}
stress cells; ablation; independent plan checker</li></ul>{foot}</div>
<div class="s"><h1>The frontier: waste and line time against service</h1><div class="cols">
<div style="flex:0.55"><ul><li>Each planner swept along its own lever: B1 cover 0.5-3 weeks, optimiser service
target 80-99%</li><li>Tuned B1 (boxed): lowest waste, highest fill, but {f['h_tuned']:.0f} changeover h/week</li>
<li>Optimiser: low waste <i>and</i> about {f['h_opt']:.0f} h/week; cannot reach B1's fill rate at any target tested</li></ul></div>
<div><img src="{img('frontier.png')}"></div></div>{foot}</div>
<div class="s"><h1>Results: a trade-off, not a free lunch</h1><div class="cols"><div style="flex:0.8">
<table><tr><th>Optimiser vs</th><th>tuned B1</th><th>two-week-cycle B1</th></tr>
<tr><td>Changeover hours</td><td>{red(mc['changeover_hours_reduction_pct'])}</td><td>{red(mcd['changeover_hours_reduction_pct'])}</td></tr>
<tr><td>Expired waste</td><td>{red(mc['expired_waste_reduction_pct'])}</td><td>{red(mcd['expired_waste_reduction_pct'])}</td></tr>
<tr><td>Fill rate</td><td>{pts(mc['fill_rate_delta_pts'])}</td><td>{pts(mcd['fill_rate_delta_pts'])}</td></tr>
<tr><td>Planning cost</td><td>{red(mc['evaluated_cost_reduction_pct'], 1)}</td><td>{red(mcd['evaluated_cost_reduction_pct'], 1)}</td></tr></table>
<p>{h['n_paths']} paired scenarios; {h['checker_violations_total']} plan violations. Frees about {f['freed_h']:.0f} of
72 line hours a week vs the tuned rule.</p></div>
<div><img src="{img('kpi_comparison.png')}"></div></div>{foot}</div>
<div class="s"><h1>Where it helps, where it does not, next steps</h1><div class="cols"><div style="flex:0.6"><ul>
<li>Helps: long cleans (x2: fill {f['co2_fill_opt']:.0f}% vs {f['co2_fill_tuned']:.0f}%), short shelf lives,
any plant short of line hours</li>
<li>Does not help: plentiful hours and short cleans, where the tuned simple rule is better on waste and service</li>
<li>Limits: synthetic plant, retail demand as proxy, weekly buckets, no downtime</li>
<li>Next: measure clean times and line hours; shadow pilot on 3 SKUs; stochastic planning</li></ul></div>
<div><img src="{img('tornado.png')}"></div></div>{foot}</div>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="msedge")
    a = ap.parse_args()
    h = json.loads((ROOT / "results" / "headline_numbers.json").read_text(encoding="utf-8"))
    abl = pd.read_csv(ROOT / "results" / "ablation.csv")
    TMP.mkdir(parents=True, exist_ok=True)
    jobs = [(memo(h, abl), ROOT / "docs" / "results" / "plan_memo.pdf", {"format": "Letter"}),
            (slides(h), ROOT / "docs" / "portfolio" / "summary_slides.pdf", {"width": "13.333in", "height": "7.5in"})]
    with sync_playwright() as p:
        b = p.chromium.launch(channel=a.channel)
        for html, out, size in jobs:
            src = TMP / (out.stem + ".html")
            src.write_text(html, encoding="utf-8")
            page = b.new_page()
            page.goto(src.as_uri())
            page.wait_for_load_state("networkidle")
            page.pdf(path=str(out), print_background=True, prefer_css_page_size=True, **size)
            page.close()
            print(out)
        b.close()


if __name__ == "__main__":
    main()
