"""Allergen-aware changeover matrix (T2.2.2).

Rule (docs/assumptions.md A-06): changeover i -> j costs
    base + allergen_clean   if allergens(i) - allergens(j) is non-empty
                            (residue of i would be an undeclared allergen on j)
    base + routine_clean    otherwise (flavour/format change, no allergen implication)
    0                       on the diagonal (no changeover).
The matrix is therefore asymmetric: milk -> milk+soy needs no allergen clean, the reverse does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from shelflife.plant.config import PlantConfig

ALLERGEN, ROUTINE, NONE = "allergen", "routine", "none"


@dataclass(frozen=True)
class ChangeoverMatrix:
    sku_ids: list[str]
    hours: np.ndarray          # [i, j] changeover hours
    clean_type: np.ndarray     # [i, j] one of ALLERGEN / ROUTINE / NONE (dtype object)

    @property
    def needs_allergen_clean(self) -> np.ndarray:
        return self.clean_type == ALLERGEN

    def index(self, sku_id: str) -> int:
        return self.sku_ids.index(sku_id)


def needs_allergen_clean(from_allergens: set[str] | list[str],
                         to_allergens: set[str] | list[str]) -> bool:
    return bool(set(from_allergens) - set(to_allergens))


def build_matrix(cfg: PlantConfig, scale: float = 1.0) -> ChangeoverMatrix:
    """`scale` multiplies all changeover times (sensitivity sweep x0.5-2)."""
    co = cfg.changeover_hours
    base, routine, allergen = co.base.value, co.routine_clean.value, co.allergen_clean.value
    n = len(cfg.skus)
    hours = np.zeros((n, n))
    kind = np.full((n, n), NONE, dtype=object)
    for i, a in enumerate(cfg.skus):
        for j, b in enumerate(cfg.skus):
            if i == j:
                continue
            if needs_allergen_clean(a.allergens, b.allergens):
                hours[i, j], kind[i, j] = base + allergen, ALLERGEN
            else:
                hours[i, j], kind[i, j] = base + routine, ROUTINE
    return ChangeoverMatrix([s.id for s in cfg.skus], hours * scale, kind)


def plot_heatmap(m: ChangeoverMatrix, cfg: PlantConfig, path: Path | str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"{s.id} {s.name} [{','.join(s.allergens) or '-'}]" for s in cfg.skus]
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(m.hours, cmap="Greys")
    ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_xlabel("to SKU (j)")
    ax.set_ylabel("from SKU (i)")
    for i in range(len(labels)):
        for j in range(len(labels)):
            if i != j:
                txt = f"{m.hours[i, j]:.1f}" + ("*" if m.clean_type[i, j] == ALLERGEN else "")
                ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                        color="white" if m.hours[i, j] > m.hours.max() / 2 else "black")
    fig.colorbar(im, ax=ax, label="changeover hours")
    ax.set_title("Changeover hours i -> j (* = allergen clean)\nsynthetic plant model; times are assumptions")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    from shelflife.plant.config import DEFAULT_PATH, load

    cfg = load()
    m = build_matrix(cfg)
    out = DEFAULT_PATH.parents[1] / "docs" / "figures" / "changeover_heatmap.png"
    plot_heatmap(m, cfg, out)
    n_all = int(m.needs_allergen_clean.sum())
    print(f"{len(m.sku_ids)} SKUs; allergen-clean transitions: {n_all}/{len(m.sku_ids) ** 2 - len(m.sku_ids)}")
    print(f"asymmetric pairs: {int((m.needs_allergen_clean != m.needs_allergen_clean.T).sum() // 2)}")
    print(f"wrote {out}")
