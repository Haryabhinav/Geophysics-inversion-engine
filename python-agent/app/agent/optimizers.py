"""Shared derivative-free optimization primitives.

Extracted out of modeler.py so both `OfflineHeuristicModeler` (TDEM-specific)
and `GenericOfflineModeler` (methods/offline_generic.py, used by every other
registered method) can share one Nelder-Mead implementation without a
circular import between `modeler.py` and the `methods` package.
"""

from __future__ import annotations

from typing import Generator

_PENALTY = 1e18  # substitute for a non-finite misfit so the simplex stays sane


def _nelder_mead(
    x0: list[float], step: float
) -> Generator[list[float], float, None]:
    """Nelder–Mead simplex as a coroutine.

    Yields a candidate point; the caller sends back its scalar objective value.
    Standard reflection / expansion / contraction / shrink with the usual
    coefficients. Works with function values only (no gradients), which matches
    the sandbox contract (it returns just the L2 norm).
    """
    alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
    n = len(x0)

    simplex = [list(x0)] + [
        [x0[d] + (step if d == i else 0.0) for d in range(n)] for i in range(n)
    ]
    fvals: list[float] = []
    for vertex in simplex:
        fvals.append((yield vertex))

    while True:
        order = sorted(range(n + 1), key=lambda i: fvals[i])
        simplex = [simplex[i] for i in order]
        fvals = [fvals[i] for i in order]

        centroid = [sum(simplex[i][d] for i in range(n)) / n for d in range(n)]
        worst = simplex[-1]

        reflected = [centroid[d] + alpha * (centroid[d] - worst[d]) for d in range(n)]
        f_ref = yield reflected

        if fvals[0] <= f_ref < fvals[-2]:
            simplex[-1], fvals[-1] = reflected, f_ref
            continue

        if f_ref < fvals[0]:
            expanded = [centroid[d] + gamma * (reflected[d] - centroid[d]) for d in range(n)]
            f_exp = yield expanded
            if f_exp < f_ref:
                simplex[-1], fvals[-1] = expanded, f_exp
            else:
                simplex[-1], fvals[-1] = reflected, f_ref
            continue

        # Contraction (outside if reflection helped a little, else inside).
        if f_ref < fvals[-1]:
            contracted = [centroid[d] + rho * (reflected[d] - centroid[d]) for d in range(n)]
            f_con = yield contracted
            accept = f_con <= f_ref
        else:
            contracted = [centroid[d] - rho * (centroid[d] - worst[d]) for d in range(n)]
            f_con = yield contracted
            accept = f_con < fvals[-1]

        if accept:
            simplex[-1], fvals[-1] = contracted, f_con
            continue

        # Shrink toward the best vertex.
        best = simplex[0]
        for i in range(1, n + 1):
            simplex[i] = [best[d] + sigma * (simplex[i][d] - best[d]) for d in range(n)]
            fvals[i] = yield simplex[i]
