"""The Method registry: a plug-in point for geophysical inversion methods.

Each registered `MethodSpec` bundles everything the generic pipeline
(orchestrator, sandbox, GeminiModeler, GenericOfflineModeler, Interpretation
Agent) needs to run a NEW method without touching that generic machinery:
the LLM system prompt (formula baked in), a numpy reference forward model
(used for synthetic-truth generation and the contract test), a sandbox-script
renderer for the offline solver, parameter metadata (also the Interpretation
Agent's glossary), and a synthetic demo/test scenario.

`orchestrator.run_inversion_agent`'s loop itself stays completely
method-agnostic — it only ever asks the registry for per-method overrides
(tolerance, iteration caps, timeout) and falls back to the global `settings`
when a spec leaves them unset, so TDEM's env-driven behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True)
class ParamSpec:
    """One inverted parameter's metadata — also the Interpretation Agent's
    per-method glossary entry."""

    name: str
    unit: str
    description: str
    bounds: tuple[float, float]
    log_space: bool = True


@dataclass(frozen=True)
class SyntheticScenario:
    """A demo/test 'ground truth' — mirrors buildEmpymodTdem/buildBiexpTdem
    on the Node side."""

    truth_params: dict[str, float]
    x_obs: list[float]
    n_corrupt: int = 4
    aux_arrays: dict[str, list[float]] | None = None


@dataclass(frozen=True)
class MethodSpec:
    id: str
    display_name: str
    x_label: str
    d_label: str
    system_prompt_template: str
    params: list[ParamSpec]
    # Two-arg (x_obs, params) for every curve-fit method; a needs_aux method
    # (currently only EARTHQUAKE_LOCATION) takes a third positional arg, the
    # aux arrays dict, since its forward model needs fixed station geometry
    # the sandbox loads separately from t_obs/d_obs (see tools/sandbox.py).
    forward_fn: Callable[..., np.ndarray]
    render_code: Callable[[dict[str, float]], str]
    x0: list[float]
    expand: Callable[[list[float]], dict[str, float]]
    synthetic: SyntheticScenario
    needs_aux: bool = False
    aux_keys: tuple[str, ...] = ()
    summarize_fn: Callable[[np.ndarray, np.ndarray], dict[str, Any]] | None = None
    l2_tolerance: float | None = None
    max_iterations: int | None = None
    offline_max_iterations: int | None = None
    sandbox_timeout_s: int | None = None


METHOD_REGISTRY: dict[str, MethodSpec] = {}


def register(spec: MethodSpec) -> MethodSpec:
    if spec.id in METHOD_REGISTRY:
        raise ValueError(f"duplicate method id {spec.id!r}")
    METHOD_REGISTRY[spec.id] = spec
    return spec
