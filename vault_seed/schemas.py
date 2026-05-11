"""Data shapes used across the 4 agents.

Plain dataclasses to keep dependencies thin — the existing project pins
pandas/supabase, and we deliberately avoid pydantic to keep the CI job lean.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProductRow:
    ea_code: str
    code: str | None
    name: str
    option_name: str | None = None
    price: int | None = None
    color: str | None = None
    is_excluded: bool = False
    eng_name: str | None = None
    note: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserRow:
    name: str
    role: str = "staff"
    pin_env_var: str | None = None
    pin_hash: str | None = None

    def to_payload(self) -> dict[str, Any]:
        out = {"name": self.name, "role": self.role}
        if self.pin_hash:
            out["pin_hash"] = self.pin_hash
        return out


@dataclass
class DiffPlan:
    """Result of the diff agent. Targets are upserts keyed by primary key."""
    products_insert: list[dict[str, Any]] = field(default_factory=list)
    products_update: list[dict[str, Any]] = field(default_factory=list)
    products_unchanged: int = 0
    users_insert: list[dict[str, Any]] = field(default_factory=list)
    users_update: list[dict[str, Any]] = field(default_factory=list)
    users_unchanged: int = 0
    secrets_missing: list[str] = field(default_factory=list)
    secrets_present: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "products": {
                "insert": len(self.products_insert),
                "update": len(self.products_update),
                "unchanged": self.products_unchanged,
            },
            "users": {
                "insert": len(self.users_insert),
                "update": len(self.users_update),
                "unchanged": self.users_unchanged,
            },
            "secrets": {
                "present": self.secrets_present,
                "missing": self.secrets_missing,
            },
        }
