"""Hand-checkable degenerate cases for the trickiest closed-form formulas.

The shared contract test (test_method_registry_contract.py) only checks each
formula against ITSELF at truth params, which can't catch a
sign/transcription bug baked in consistently. These tests check known
physical degeneracies independently.
"""

import numpy as np

from app.agent.methods import METHOD_REGISTRY


def test_ert_wenner_collapses_to_uniform_halfspace_when_rho1_equals_rho2():
    """If the two layers have equal resistivity, the sounding curve must be
    flat at that resistivity for every spacing — there's no interface to see."""
    spec = METHOD_REGISTRY["ERT_WENNER"]
    x_obs = np.asarray(spec.synthetic.x_obs)
    rho_a = spec.forward_fn(x_obs, {"rho1": 75.0, "rho2": 75.0, "h": 20.0})
    assert np.allclose(rho_a, 75.0, rtol=1e-9)


def test_mt_1d_collapses_to_uniform_halfspace_when_rho1_equals_rho2():
    """Same degeneracy for the MT recursive impedance: a uniform earth must
    report its own resistivity as the apparent resistivity at every frequency."""
    spec = METHOD_REGISTRY["MT_1D"]
    x_obs = np.asarray(spec.synthetic.x_obs)
    rho_a = spec.forward_fn(x_obs, {"rho1": 40.0, "rho2": 40.0, "h1": 300.0})
    assert np.allclose(rho_a, 40.0, rtol=1e-6)


def test_ip_cole_cole_decays_to_zero_chargeability_at_long_time():
    """A stretched exponential must decay toward zero, not diverge or
    plateau — a sanity check on the sign of the exponent."""
    spec = METHOD_REGISTRY["IP_COLE_COLE"]
    late = spec.forward_fn(np.array([100.0]), {"m0": 25.0, "tau": 0.5, "c": 0.6})
    early = spec.forward_fn(np.array([0.01]), {"m0": 25.0, "tau": 0.5, "c": 0.6})
    assert late[0] < early[0]
    assert late[0] < 1e-6
