"""A second vertical slice, sharing the fraud slice's evaluator without changing it.

This module exists to prove one claim: the executable evaluator is domain-neutral. It
declares a different input schema, a different pinned model artifact, and a different
downstream agent, and then runs through exactly the same SQL -> model -> agent -> witness
machinery. No evaluator code is duplicated here.

ponytail: the shared evidence contract still names its record key `transaction_id` and its
positive-class flag `predicted_fraud`, because those names are the fraud slice's and every
previously published Change Passport must stay byte-verifiable. Generalizing them is a
schema 2.0 change, not a demo change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tripwire.demo.fraud import SliceSpec, _parse_bool, register_slice

INVENTORY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sku_id", "VARCHAR PRIMARY KEY"),
    ("days_of_stock", "INTEGER NOT NULL"),
    ("lead_time_days", "INTEGER"),
    ("supplier_reliability", "VARCHAR NOT NULL"),
    ("open_backorders", "INTEGER NOT NULL"),
    ("unit_cost_usd", "DOUBLE NOT NULL"),
    ("is_seasonal", "BOOLEAN NOT NULL"),
    ("is_discontinued", "BOOLEAN NOT NULL"),
)

INVENTORY_MODEL_ARTIFACT = Path(__file__).with_name("inventory_logistic_v1.json")


def _inventory_parse(raw: dict[str, str]) -> dict[str, Any]:
    return {
        "sku_id": raw["sku_id"],
        "days_of_stock": int(raw["days_of_stock"]),
        "lead_time_days": (int(raw["lead_time_days"]) if raw["lead_time_days"] else None),
        "supplier_reliability": raw["supplier_reliability"],
        "open_backorders": int(raw["open_backorders"]),
        "unit_cost_usd": float(raw["unit_cost_usd"]),
        "is_seasonal": _parse_bool(raw["is_seasonal"]),
        "is_discontinued": _parse_bool(raw["is_discontinued"]),
    }


def _inventory_report(
    feature_row: dict[str, Any],
    values: dict[str, float],
) -> dict[str, Any]:
    return {
        "stockout_signal": values["stockout_signal"],
        "days_of_stock": int(feature_row["days_of_stock"]),
        "lead_time_days": feature_row["lead_time_days"],
        "supplier_reliability": {"low": 0, "medium": 1, "high": 2}[
            str(feature_row["supplier_reliability"])
        ],
        "open_backorders": int(feature_row["open_backorders"]),
        "unit_cost_usd": float(feature_row["unit_cost_usd"]),
    }


INVENTORY_SLICE = register_slice(
    SliceSpec(
        name="inventory",
        table="raw_inventory",
        key="sku_id",
        columns=INVENTORY_COLUMNS,
        artifact_path=INVENTORY_MODEL_ARTIFACT,
        agent_version="replenishment-agent/1.0.0",
        parse=_inventory_parse,
        report=_inventory_report,
        simplifications=(
            ("is_discontinued", (False,)),
            ("is_seasonal", (False,)),
            ("unit_cost_usd", (10.0,)),
            ("supplier_reliability", ("high",)),
            ("lead_time_days", (30,)),
            ("days_of_stock", (30,)),
            ("open_backorders", (3,)),
        ),
    )
)
