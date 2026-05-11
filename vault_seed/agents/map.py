"""Agent 2 — Map.

Normalizes the raw seed CSV rows into validated payloads:
  - ea_code zero-padded to 5 digits when numeric (preserves the "01130" form)
  - price coerced to int, blanks dropped
  - is_excluded coerced from "true"/"1"/"yes"
  - user rows attach a pin_env_var pointer (PIN is resolved later in apply)
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vault_seed.config import ARTIFACTS_DIR, ensure_artifacts_dir
from vault_seed.schemas import ProductRow, UserRow


def _norm_ea(v: str | None) -> str:
    if not v:
        return ""
    s = str(v).strip()
    if s in ("nan", "#N/A", "None", ""):
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and len(s) < 5:
        s = s.zfill(5)
    return s


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None


def _to_bool(v: Any) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("true", "1", "yes", "y", "t")


def _clean_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s not in ("nan", "#N/A", "None") else None


def map_products(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for i, raw in enumerate(rows, start=2):  # row 1 is header
        ea = _norm_ea(raw.get("ea_code"))
        if not ea:
            errors.append(f"row {i}: missing ea_code (skipped)")
            continue
        if ea in seen:
            errors.append(f"row {i}: duplicate ea_code {ea} (kept first)")
            continue
        seen.add(ea)
        name = _clean_str(raw.get("name")) or "(미입력)"
        row = ProductRow(
            ea_code=ea,
            code=_clean_str(raw.get("code")),
            name=name,
            option_name=_clean_str(raw.get("option_name")),
            price=_to_int(raw.get("price")),
            color=_clean_str(raw.get("color")),
            is_excluded=_to_bool(raw.get("is_excluded")),
            eng_name=_clean_str(raw.get("eng_name")),
            note=_clean_str(raw.get("note")),
        )
        out.append(asdict(row))
    return out, errors


def map_users(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for i, raw in enumerate(rows, start=2):
        name = _clean_str(raw.get("name"))
        if not name:
            errors.append(f"row {i}: missing name (skipped)")
            continue
        if name in seen:
            errors.append(f"row {i}: duplicate name {name} (kept first)")
            continue
        seen.add(name)
        role = (_clean_str(raw.get("role")) or "staff").lower()
        if role not in ("admin", "staff"):
            errors.append(f"row {i}: invalid role '{role}', defaulted to staff")
            role = "staff"
        out.append(asdict(UserRow(
            name=name,
            role=role,
            pin_env_var=_clean_str(raw.get("pin_env_var")),
        )))
    return out, errors


def run() -> dict[str, Any]:
    fetched_path = ARTIFACTS_DIR / "01_fetch.json"
    if not fetched_path.exists():
        raise FileNotFoundError(f"{fetched_path} missing — run fetch agent first")
    fetched = json.loads(fetched_path.read_text(encoding="utf-8"))

    mapped_products, p_errors = map_products(fetched["seed"]["products"])
    mapped_users, u_errors = map_users(fetched["seed"]["users"])

    payload = {
        "products": mapped_products,
        "users": mapped_users,
        "errors": {"products": p_errors, "users": u_errors},
        "remote": fetched["remote"],
        "secrets_state": fetched["secrets_state"],
        "dry_run": fetched["dry_run"],
    }
    out = ensure_artifacts_dir() / "02_map.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[map] products={len(mapped_products)} users={len(mapped_users)}")
    if p_errors:
        print(f"[map] product warnings: {len(p_errors)}")
        for e in p_errors[:5]:
            print(f"  - {e}")
    if u_errors:
        print(f"[map] user warnings: {len(u_errors)}")
        for e in u_errors[:5]:
            print(f"  - {e}")
    print(f"[map] wrote {out}")
    return payload


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
