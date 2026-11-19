"""T7.1.1/T7.2.1: render the numbers blocks in README.md and docs/portfolio/portfolio_pack.md from
results/headline_numbers.json, so no result is ever hand-typed. Blocks sit between
<!-- RESULTS:START --> and <!-- RESULTS:END --> (README) or <!-- PORTFOLIO:START/END --> (portfolio pack).
tests/test_docs.py fails if a block is out of date.
Run: python scripts/render_results.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results" / "headline_numbers.json"


def ci(v: dict, fmt: str = "{:.1f}") -> str:
    return f"{fmt.format(v['estimate'])} (95% CI {fmt.format(v['ci_lo'])} to {fmt.format(v['ci_hi'])})"


def red(v: dict) -> str:
    """A reduction in % phrased by direction: '53.1% lower (95% CI 52.3 to 53.9)' or '49.1% higher (...)'."""
    if v["estimate"] >= 0:
        return f"{v['estimate']:.1f}% lower (95% CI {v['ci_lo']:.1f} to {v['ci_hi']:.1f})"
    return f"{-v['estimate']:.1f}% higher (95% CI {-v['ci_hi']:.1f} to {-v['ci_lo']:.1f})"


def red_point(x: float) -> str:
    return f"{x:.1f}% lower" if x >= 0 else f"{-x:.1f}% higher"


KPI_ROWS = (("Expired waste", "expired_waste_reduction_pct", "red"),
            ("Lost cases", "lost_cases_reduction_pct", "red"),
            ("Fill rate", "fill_rate_delta_pts", "pts"),
            ("Changeover hours", "changeover_hours_reduction_pct", "red"),
            ("Allergen-clean hours", "allergen_clean_hours_reduction_pct", "red"),
            ("Total planning cost (model weights)", "evaluated_cost_reduction_pct", "red"))


def _cell(v: dict | None, kind: str) -> str:
    if v is None:
        return "-"
    return red(v) if kind == "red" else f"{ci(v, '{:+.2f}')} pts"


def _point(x: float | None, kind: str) -> str:
    if x is None:
        return "-"
    return red_point(x) if kind == "red" else f"{x:+.2f} pts"


def results_block(h: dict) -> str:
    mc, r = h["monte_carlo"], h["replay_layer_a"]
    mcd = h.get("monte_carlo_vs_b1_default")
    tuned = h.get("baseline_headline") == "B1_TUNED"
    head = (f"vs B1 tuned on validation (cover {h['b1_tuned_cover_weeks']:g} wk)" if tuned else "vs B1")
    cols = [f"Monte Carlo {head}, N = {h['n_paths']}", "Historical replay, test year, same baseline"]
    if mcd:
        cols.insert(1, f"Monte Carlo vs rule-of-thumb B1 (2-week cycle), N = {h['n_paths']}")
    out = ["| KPI, optimiser vs baseline | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, key, kind in KPI_ROWS:
        cells = [_cell(mc.get(key), kind)]
        if mcd:
            cells.append(_cell(mcd.get(key), kind))
        cells.append(_point(r.get(key), kind))
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    am = h.get("monte_carlo_arm_means")
    if am:
        def lv(arm: str) -> str:
            x = am[arm]
            return (f"fill {100 * x['fill_rate']:.1f}%, expired {x['expired_pct']:.2f}% of production, "
                    f"{x['changeover_hours_per_week']:.1f} changeover h/week, line utilisation "
                    f"{100 * x['utilisation']:.0f}%")
        out += ["", "Levels (Monte Carlo means): " + "; ".join(
            f"**{lab}** {lv(arm)}" for arm, lab in (("OPT", "optimiser"), ("B1_TUNED", "tuned B1"),
                                                    ("B1", "rule-of-thumb B1")) if arm in am) + "."]
    fc, fsn = h["forecast_wape_improvement_pct"], h["forecast_wape_improvement_vs_seasonal_naive_pct"]
    out += ["", f"Forecast accuracy, test year (WAPE): selected model {fc['wape_selected_pct']:.2f}% vs 4-week moving "
            f"average {fc['wape_benchmark_pct']:.2f}% (relative change {ci(fc, '{:+.1f}')}%: no detectable gain); "
            f"vs seasonal naive {fsn['wape_benchmark_pct']:.2f}%: {red(fsn)}.", ""]
    s = h.get("sensitivity")
    if s and "cost_reduction_range_pct" in s:
        lo, hi = s["cost_reduction_range_pct"]
        out += [f"Sensitivity ({s['n_cells']} one-at-a-time cells, N = {s['n_paths_per_cell']} each, vs "
                f"{'tuned' if s['baseline'] == 'B1_TUNED' else 'rule-of-thumb'} B1): planning cost lower with CI above "
                f"zero in {100 * s['share_cells_cost_improved']:.0f}% of cells (range {red_point(lo)} to "
                f"{red_point(hi)}); changeover hours lower in {100 * s['share_cells_changeover_improved']:.0f}%; "
                f"expired waste lower in {100 * s['share_cells_waste_improved']:.0f}%.", ""]
    out += [f"Independent plan checker: {h['checker_violations_total']} violations; solver fallbacks: "
            f"{h['fallback_weeks_total']} weeks. Run `{h['experiment_run_id']}`, seed {h['seed']}. "
            f"*All figures: {h['label']}.*"]
    return "\n".join(out)


def portfolio_block(h: dict) -> str:
    mc, r = h["monte_carlo"], h["replay_layer_a"]
    lines = [f"- baseline for these numbers: {h.get('baseline_headline', 'B1')} (ADR-009)"]
    for _, key, kind in KPI_ROWS:
        v = mc[key]
        unit, f = (" pts", "{:+.2f}") if kind == "pts" else ("%", "{:+.1f}")
        lines.append(f"- {key} (Monte Carlo): {f.format(v['estimate'])}{unit} (95% CI {f.format(v['ci_lo'])} to "
                     f"{f.format(v['ci_hi'])}); historical replay: "
                     + (f"{f.format(r[key])}{unit}" if key in r else "-"))
    mcd = h.get("monte_carlo_vs_b1_default")
    if mcd:
        for key in ("expired_waste_reduction_pct", "changeover_hours_reduction_pct", "fill_rate_delta_pts"):
            v, f = mcd[key], ("{:+.2f}" if key.endswith("_pts") else "{:+.1f}")
            lines.append(f"- vs rule-of-thumb B1, {key}: {f.format(v['estimate'])} (95% CI {f.format(v['ci_lo'])} "
                         f"to {f.format(v['ci_hi'])})")
    am = h.get("monte_carlo_arm_means", {})
    for arm in ("OPT", "B1_TUNED", "B1"):
        if arm in am:
            lines.append(f"- {arm}: expired {am[arm]['expired_pct']:.2f}% of production; fill "
                         f"{100 * am[arm]['fill_rate']:.1f}%; changeover h/week {am[arm]['changeover_hours_per_week']:.1f}; "
                         f"utilisation {100 * am[arm]['utilisation']:.0f}%")
    fsn = h["forecast_wape_improvement_vs_seasonal_naive_pct"]
    lines.append(f"- forecast WAPE vs seasonal naive: {fsn['estimate']:.1f}% better; vs 4-week moving average: "
                 f"{h['forecast_wape_improvement_pct']['estimate']:+.1f}%")
    s = h.get("sensitivity")
    if s:
        lines.append(f"- sensitivity: {s['n_cells']} cells; cost improved in {100 * s['share_cells_cost_improved']:.0f}%; "
                     f"waste improved in {100 * s['share_cells_waste_improved']:.0f}%")
    lines.append(f"- n_paths: {h['n_paths']}; checker_violations_total: {h['checker_violations_total']}")
    return "\n".join(lines)


def targets_block(h: dict) -> str:
    """Charter targets (set before any result) vs results, against both baselines (ADR-009)."""
    mc, mcd = h["monte_carlo"], h.get("monte_carlo_vs_b1_default") or h["monte_carlo"]
    fc, fsn, cov = (h["forecast_wape_improvement_pct"], h["forecast_wape_improvement_vs_seasonal_naive_pct"],
                    h.get("forecast_interval_coverage", {}))

    def met(ok: bool) -> str:
        return "Met" if ok else "**Missed**"

    w_t, w_d = mc["expired_waste_reduction_pct"], mcd["expired_waste_reduction_pct"]
    f_t, f_d = mc["fill_rate_delta_pts"], mcd["fill_rate_delta_pts"]
    c_t, c_d = mc["changeover_hours_reduction_pct"], mcd["changeover_hours_reduction_pct"]
    rows = [
        ("Forecast WAPE >= 10% better than seasonal naive",
         f"{red(fsn)}; vs the 4-week moving average (the strong benchmark): {ci(fc, '{:+.1f}')}%",
         met(fsn["ci_lo"] >= 10) + " on paper; no gain over the strong benchmark"),
        ("Expired waste >= 25% lower, CI excluding 0",
         f"tuned B1: {red(w_t)}; rule-of-thumb B1: {red(w_d)}",
         f"tuned: {met(w_t['ci_lo'] >= 25)}; rule-of-thumb: {met(w_d['ci_lo'] >= 25)}"),
        ("Fill rate non-inferior (>= -0.5 pts)",
         f"tuned B1: {ci(f_t, '{:+.2f}')} pts; rule-of-thumb B1: {ci(f_d, '{:+.2f}')} pts",
         f"tuned: {met(f_t['ci_lo'] >= -0.5)}; rule-of-thumb: {met(f_d['ci_lo'] >= -0.5)}"),
        ("Changeover hours >= 20% lower",
         f"tuned B1: {red(c_t)}; rule-of-thumb B1: {red(c_d)}",
         f"tuned: {met(c_t['ci_lo'] >= 20)}; rule-of-thumb: {met(c_d['ci_lo'] >= 20)}"),
        ("0 violations in executed plans", f"{h['checker_violations_total']} in the main experiment"
         + (f"; {h['sensitivity']['checker_violations_total']} across sensitivity cells" if "sensitivity" in h else ""),
         met(h["checker_violations_total"] == 0 and h.get("sensitivity", {}).get("checker_violations_total", 0) == 0)),
    ]
    if cov:
        rows.append(("80% / 95% forecast intervals within +/-5 pts on the test year",
                     f"{100 * cov['80']:.1f}% / {100 * cov['95']:.1f}%",
                     met(abs(cov["80"] - 0.8) <= 0.05 and abs(cov["95"] - 0.95) <= 0.05)))
    if "replay_runtime_s" in h:
        rows.append(("52-week replay < 90 min", f"{h['replay_runtime_s'] / 60:.1f} min",
                     met(h["replay_runtime_s"] < 5400)))
    out = ["| Target (charter, set before any result) | Result | Met? |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(out)


BLOCKS = [(ROOT / "README.md", "RESULTS", results_block),
          (ROOT / "docs" / "results" / "summary.md", "RESULTS", results_block),
          (ROOT / "docs" / "results" / "summary.md", "TARGETS", targets_block),
          (ROOT / "docs" / "portfolio" / "portfolio_pack.md", "PORTFOLIO", portfolio_block)]


def render(text: str, tag: str, body: str) -> str:
    pat = re.compile(rf"(<!-- {tag}:START -->).*?(<!-- {tag}:END -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"markers <!-- {tag}:START/END --> not found")
    return pat.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(2), text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    h = json.loads(H.read_text(encoding="utf-8"))
    stale = []
    for path, tag, fn in BLOCKS:
        if not path.exists() or f"<!-- {tag}:START -->" not in path.read_text(encoding="utf-8"):
            continue
        old = path.read_text(encoding="utf-8")
        new = render(old, tag, fn(h))
        if new != old:
            stale.append(f"{path.name}:{tag}")
            if not a.check:
                path.write_text(new, encoding="utf-8")
    print(("stale: " if a.check else "updated: ") + (", ".join(stale) or "none"))
    if a.check and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
