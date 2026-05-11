"""Agent 4 — Apply.

Executes the diff plan against Supabase (idempotent upsert) and renders a
Streamlit Cloud secrets.toml template populated from the current environment.

Safety:
  - dry_run mode prints the plan and exits without DB writes.
  - apply fails fast if required secrets are missing (no partial seed).
  - user PINs are resolved from env vars (VAULT_SEED_PIN_<NAME_UPPER>) and
    hashed at apply-time; never read or written from CSV.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from vault_seed.config import ARTIFACTS_DIR, Settings, ensure_artifacts_dir


def _hash_pin(pin: str) -> str:
    import bcrypt
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _resolve_user_pin(name: str, env_var: str | None) -> str | None:
    var = env_var or f"VAULT_SEED_PIN_{name.upper()}"
    pin = os.environ.get(var, "").strip()
    if not pin:
        return None
    if len(pin) != 4 or not pin.isdigit():
        raise ValueError(f"{var}: PIN must be 4 digits")
    return _hash_pin(pin)


def _render_secrets_template(template_path: Path, settings: Settings) -> str:
    template = template_path.read_text(encoding="utf-8")
    return template.format(
        SUPABASE_URL=settings.supabase_url or "<SET_ME>",
        SUPABASE_SERVICE_ROLE_KEY=settings.supabase_service_role_key or "<SET_ME>",
        SUPABASE_ANON_KEY=settings.supabase_anon_key or "<SET_ME>",
    )


def _upsert(client, table: str, rows: list[dict[str, Any]], conflict: str) -> int:
    if not rows:
        return 0
    BATCH = 500
    total = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        client.table(table).upsert(chunk, on_conflict=conflict).execute()
        total += len(chunk)
    return total


def run(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    diff_path = ARTIFACTS_DIR / "03_diff.json"
    if not diff_path.exists():
        raise FileNotFoundError(f"{diff_path} missing — run diff agent first")
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    plan = diff["plan"]

    if plan["secrets_missing"] and not settings.dry_run:
        raise RuntimeError(
            f"Required secrets missing: {plan['secrets_missing']}. Refusing to apply."
        )

    artifacts = ensure_artifacts_dir()
    rendered = _render_secrets_template(settings.secrets_template, settings)
    secrets_out = artifacts / "secrets.rendered.toml"
    secrets_out.write_text(rendered, encoding="utf-8")
    print(f"[apply] rendered secrets template -> {secrets_out}")

    # Resolve PINs (skipped for inserts where no env var is provided).
    users_to_apply = []
    for u in plan["users_insert"] + plan["users_update"]:
        pin_hash = _resolve_user_pin(u["name"], u.get("pin_env_var"))
        payload = {"name": u["name"], "role": u["role"]}
        if pin_hash:
            payload["pin_hash"] = pin_hash
        users_to_apply.append(payload)

    users_skipped_no_pin = [u for u in plan["users_insert"] if "pin_hash" not in next(
        (x for x in users_to_apply if x["name"] == u["name"]), {}
    )]

    result: dict[str, Any] = {
        "dry_run": settings.dry_run,
        "products_upserted": 0,
        "users_upserted": 0,
        "users_skipped_no_pin": [u["name"] for u in users_skipped_no_pin],
        "secrets_rendered_path": str(secrets_out),
        "summary": diff["summary"],
    }

    if settings.dry_run:
        print(f"[apply] DRY_RUN — would upsert "
              f"products={len(plan['products_insert']) + len(plan['products_update'])} "
              f"users={len(users_to_apply)}")
    else:
        from supabase import create_client
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        result["products_upserted"] = _upsert(
            client, "products",
            plan["products_insert"] + plan["products_update"],
            conflict="ea_code",
        )
        # Only upsert users that have a resolved PIN (first insert needs it).
        users_with_pin = [u for u in users_to_apply if "pin_hash" in u]
        result["users_upserted"] = _upsert(
            client, "users", users_with_pin, conflict="name",
        )
        print(f"[apply] upserted products={result['products_upserted']} "
              f"users={result['users_upserted']}")
        if result["users_skipped_no_pin"]:
            print(f"[apply] users without PIN env var (skipped): "
                  f"{result['users_skipped_no_pin']}")

    out = artifacts / "04_apply.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[apply] wrote {out}")
    return result


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
