"""Agent 1 — Fetch.

Reads the repo-committed seed CSVs and a Supabase snapshot of the current
state (products + users). Writes raw artifacts so the next agent can run as
an isolated CI step.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from vault_seed.config import REQUIRED_SECRETS, Settings, ensure_artifacts_dir


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _fetch_supabase_snapshot(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    if settings.dry_run:
        return {"products": [], "users": []}

    # Import inside the function so dry-run runs without the supabase pkg.
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    products = client.table("products").select("ea_code,name,code,price,is_excluded").execute().data or []
    users = client.table("users").select("name,role").execute().data or []
    return {"products": products, "users": users}


def run(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    artifacts = ensure_artifacts_dir()

    seed_products = _read_csv(settings.products_csv)
    seed_users = _read_csv(settings.users_csv)
    remote = _fetch_supabase_snapshot(settings)

    import os
    secrets_state = {
        "required_present": [k for k in REQUIRED_SECRETS if os.environ.get(k, "").strip()],
        "required_missing": [k for k in REQUIRED_SECRETS if not os.environ.get(k, "").strip()],
    }

    payload = {
        "seed": {"products": seed_products, "users": seed_users},
        "remote": remote,
        "secrets_state": secrets_state,
        "dry_run": settings.dry_run,
    }

    out = artifacts / "01_fetch.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[fetch] seed products={len(seed_products)} users={len(seed_users)}")
    print(f"[fetch] remote products={len(remote['products'])} users={len(remote['users'])}")
    print(f"[fetch] secrets present={secrets_state['required_present']}")
    print(f"[fetch] wrote {out}")
    return payload


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
