"""Per-week run sequencing with CP-SAT (decomposition approach; T4.2.1 / T4.2.3).

Shortest Hamiltonian path over the week's SKUs, starting from the line state carried over from the
previous week (no changeover if the first run is the same SKU) and ending anywhere. Modelled as a
circuit with a dummy depot node: depot -> j costs C[last, j], i -> depot costs 0.
"""
from __future__ import annotations

import numpy as np
from ortools.sat.python import cp_model

SCALE = 100  # CP-SAT needs integers: hours x 100


def sequence_week(skus: list[int], C: np.ndarray, last: int | None,
                  time_limit_s: float = 5.0) -> tuple[list[int], float]:
    """Return (run order, changeover hours incl. carry-over)."""
    skus = list(dict.fromkeys(skus))
    if not skus:
        return [], 0.0
    if len(skus) == 1:
        p = skus[0]
        return skus, (0.0 if last is None or last == p else float(C[last, p]))
    m = cp_model.CpModel()
    nodes = [None] + skus                    # node 0 = depot
    arcs, lits = [], {}
    for a in range(len(nodes)):
        for b in range(len(nodes)):
            if a == b:
                continue
            lit = m.NewBoolVar(f"a{a}_{b}")
            lits[a, b] = lit
            arcs.append((a, b, lit))
    m.AddCircuit(arcs)

    def cost(i, j):
        if j is None:
            return 0
        if i is None:
            return 0 if last is None or last == j else int(round(C[last, j] * SCALE))
        return int(round(C[i, j] * SCALE))

    m.Minimize(sum(cost(nodes[a], nodes[b]) * lit for (a, b), lit in lits.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    # single worker + fixed seed: among equal-cost orders the same one is returned every run (reproducible)
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    st = solver.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("sequencing failed")
    succ = {a: b for (a, b), lit in lits.items() if solver.Value(lit)}
    order, cur = [], succ[0]
    while cur != 0:
        order.append(nodes[cur])
        cur = succ[cur]
    return order, changeover_of(order, C, last)


def changeover_of(order: list[int], C: np.ndarray, last: int | None) -> float:
    h, prev = 0.0, last
    for p in order:
        if prev is not None and prev != p:
            h += C[prev, p]
        prev = p
    return float(h)


def brute_force(skus: list[int], C: np.ndarray, last: int | None) -> tuple[list[int], float]:
    from itertools import permutations
    best = min(permutations(skus), key=lambda o: changeover_of(list(o), C, last))
    return list(best), changeover_of(list(best), C, last)
