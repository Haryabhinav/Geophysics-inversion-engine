"""The Method registry package. Importing this package registers every
built-in method (see `specs/`) as a side effect."""

from . import specs  # noqa: F401 — triggers registration of every built-in method
from .registry import METHOD_REGISTRY, MethodSpec, ParamSpec, SyntheticScenario, register

__all__ = ["METHOD_REGISTRY", "MethodSpec", "ParamSpec", "SyntheticScenario", "register"]
