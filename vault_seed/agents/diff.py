"""Agent 3 — Diff.

Compares the mapped seed payloads against the Supabase snapshot and produces
an idempotent plan: which rows are new, which need an update, which are
already in sync. Also flags missing vault secrets.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from vault_seed.config import ARTIFACTS_DIR, REQUIRED_SECRETS, ensure_artifacts_dir
from vault_seed.schemas import DiffPlan

PRODUCT_FIELDS = ("ea_code", "code", "name", "price", "is_excluded")


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {r[key]: r for r in rows if r.get(key)}


def _product_changed(seed: dict[str, Any], remote: dict[str, Any]) -> bool:
    for f in PRODUCT_FIELDS:
        if f == "ea_code":
            continue
        if (seed.get(f) or None) != (remote.get(f) or None):
            return True
    return False


def diff_products(seed: list[dict[str, Any]], remote: list[dict[str, Any]]) -> tuple[list, list, int]:
    remote_idx = _index_by(remote, "ea_code")
    inserts, updates = [], []
    unchanged = 0
    for row in seed:
        existing = remote_idx.get(row["ea_code"])
        if existing is None:
            inserts.append(row)
        elif _product_changed(row, existing):
            updates.append(row)
        else:
            unchanged += 1
    return inserts, updates, unchanged


def diff_users(seed: list[dict[str, Any]], remote: list[dict[str, Any]]) -> tuple[list, list, int]:
    remote_idx = _index_by(remote, "name")
    inserts, updates = [], []
    unchanged = 0
    for row in seed:
        existing = remote_idx.get(row["name"])
        if existing is None:
            inserts.append(row)
        elif existing.get("role") != row.get("role"):
            updates.append(row)
        else:
            unchanged += 1
    return inserts, updates, unchanged


def run() -> dict[str, Any]:
    mapped_path = ARTIFACTS_DIR / "02_map.json"
    if not mapped_path.exists():
        raise FileNotFoundError(f"{mapped_path} missing — run map agent first")
    mapped = json.loads(mapped_path.read_text(encoding="utf-8"))

    p_ins, p_upd, p_unch = diff_products(mapped["products"], mapped["remote"]["products"])
    u_ins, u_upd, u_unch = diff_users(mapped["users"], mapped["remote"]["users"])

    plan = DiffPlan(
        products_insert=p_ins,
        products_update=p_upd,
        products_unchanged=p_unch,
        users_insert=u_ins,
        users_update=u_upd,
        users_unchanged=u_unch,
        secrets_present=mapped["secrets_state"]["required_present"],
        secrets_missing=mapped["secrets_state"]["required_missing"],
    )

    payload = {
        "plan": {
            "products_insert": plan.products_insert,
            "products_update": plan.products_update,
            "products_unchanged": plan.products_unchanged,
            "users_insert": plan.users_insert,
            "users_update": plan.users_update,
            "users_unchanged": plan.users_unchanged,
            "secrets_present": plan.secrets_present,
            "secrets_missing": plan.secrets_missing,
        },
        "summary": plan.summary(),
        "dry_run": mapped["dry_run"],
    }

    out = ensure_artifacts_dir() / "03_diff.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    s = plan.summary()
    print(f"[diff] products insert={s['products']['insert']} "
          f"update={s['products']['update']} unchanged={s['products']['unchanged']}")
    print(f"[diff] users insert={s['users']['insert']} "
          f"update={s['users']['update']} unchanged={s['users']['unchanged']}")
    print(f"[diff] secrets missing={plan.secrets_missing}")
    print(f"[diff] wrote {out}")
    return payload


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
