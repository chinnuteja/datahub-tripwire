"""Deterministic, public demo systems used for end-to-end proof."""

from tripwire.demo.fraud import (
    DEFAULT_MODEL_ARTIFACT,
    FRAUD_SLICE,
    DeterministicFraudModel,
    DuckDBTransformationRuntime,
    SliceSpec,
    TriageAgent,
    build_demo_world,
    load_model_artifact,
    load_transactions,
    register_slice,
)

# Importing the slice registers it; both slices run on the fraud module's evaluator.
from tripwire.demo.inventory import INVENTORY_SLICE

SLICES: dict[str, SliceSpec] = {
    FRAUD_SLICE.name: FRAUD_SLICE,
    INVENTORY_SLICE.name: INVENTORY_SLICE,
}


def resolve_slice(name: str) -> SliceSpec:
    """Resolve a registered vertical slice by name, or raise KeyError."""

    return SLICES[name]


__all__ = [
    "DEFAULT_MODEL_ARTIFACT",
    "FRAUD_SLICE",
    "INVENTORY_SLICE",
    "SLICES",
    "DeterministicFraudModel",
    "DuckDBTransformationRuntime",
    "SliceSpec",
    "TriageAgent",
    "build_demo_world",
    "load_model_artifact",
    "load_transactions",
    "register_slice",
    "resolve_slice",
]
