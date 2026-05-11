"""Cloud-only configuration loader.

Reads everything from environment variables. No local file paths, no .env
discovery (a .env IS loaded if python-dotenv is installed AND a .env exists
next to the workflow checkout, but it is never required). This is what makes
the package portable across sessions and CI runs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
ARTIFACTS_DIR = PKG_DIR / "artifacts"

REQUIRED_SECRETS = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
OPTIONAL_SECRETS = ("SUPABASE_ANON_KEY", "KAKAO_REST_API_KEY")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str | None
    dry_run: bool
    products_csv: Path
    users_csv: Path
    secrets_template: Path

    @classmethod
    def from_env(cls, *, dry_run: bool | None = None) -> "Settings":
        url = os.environ.get("SUPABASE_URL", "").strip()
        srv = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        anon = os.environ.get("SUPABASE_ANON_KEY", "").strip() or None
        if dry_run is None:
            dry_run = os.environ.get("VAULT_SEED_DRY_RUN", "").lower() in ("1", "true", "yes")

        if not dry_run and (not url or not srv):
            missing = [k for k in REQUIRED_SECRETS if not os.environ.get(k, "").strip()]
            raise RuntimeError(
                f"Missing required secrets: {missing}. "
                "Set them as GitHub Actions secrets or export locally. "
                "Use VAULT_SEED_DRY_RUN=1 to skip Supabase calls."
            )

        return cls(
            supabase_url=url,
            supabase_service_role_key=srv,
            supabase_anon_key=anon,
            dry_run=dry_run,
            products_csv=DATA_DIR / "products.seed.csv",
            users_csv=DATA_DIR / "users.seed.csv",
            secrets_template=DATA_DIR / "secrets.template.toml",
        )


def ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR
