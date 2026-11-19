"""T6.1.1/T6.2.2: screenshots of the running dashboard at laptop width (1366 px) -> docs/figures/app_*.png.

Start the app first: streamlit run app/streamlit_app.py --server.port 8599 --server.headless true
Run: python scripts/screenshot_app.py [--url http://localhost:8599] [--channel msedge|chrome]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = [("", "app_overview.png", 1900), ("forecasts", "app_forecasts.png", 1300),
         ("plan_viewer", "app_plan_viewer.png", 1250), ("scenarios", "app_scenarios.png", 1300)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8599")
    ap.add_argument("--channel", default="msedge")
    a = ap.parse_args()
    out = ROOT / "docs" / "figures"
    with sync_playwright() as p:
        b = p.chromium.launch(channel=a.channel)
        for path, name, height in PAGES:     # Streamlit scrolls inside a container: use a tall viewport
            page = b.new_page(viewport={"width": 1366, "height": height})
            page.goto(f"{a.url}/{path}")
            page.wait_for_selector("h1", timeout=60_000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)                     # let Plotly finish drawing
            page.screenshot(path=str(out / name))
            page.close()
            print(out / name)
        b.close()


if __name__ == "__main__":
    main()
