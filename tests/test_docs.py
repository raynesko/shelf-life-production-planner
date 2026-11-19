"""T7.1.1/T7.2.1: numbers in README/portfolio come from headline_numbers.json; relative links resolve."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results" / "headline_numbers.json"
DOCS = [ROOT / "README.md", ROOT / "docs" / "assumptions.md", *sorted((ROOT / "docs" / "results").glob("*.md")),
        *sorted((ROOT / "docs" / "methods").glob("*.md")), *sorted((ROOT / "docs" / "decisions").glob("*.md")),
        ROOT / "docs" / "portfolio" / "portfolio_pack.md", ROOT / "docs" / "app_guide.md"]


def renderer():
    spec = importlib.util.spec_from_file_location("render_results", ROOT / "scripts" / "render_results.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not H.exists(), reason="headline numbers not built")
def test_rendered_blocks_are_current():
    r = renderer()
    h = json.loads(H.read_text(encoding="utf-8"))
    for path, tag, fn in r.BLOCKS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if f"<!-- {tag}:START -->" in text:
            assert r.render(text, tag, fn(h)) == text, f"{path.name}: run python scripts/render_results.py"


@pytest.mark.parametrize("doc", [d for d in DOCS if d.exists()], ids=lambda p: p.name)
def test_relative_links_resolve(doc):
    text = doc.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
        if re.match(r"^[a-z]+:", target):
            continue
        assert (doc.parent / target).exists(), f"{doc.name}: broken link {target}"
