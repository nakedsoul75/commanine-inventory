"""End-to-end smoke test in dry_run mode (no network, no DB writes)."""
import json
import os

from vault_seed.agents import apply as apply_agent
from vault_seed.agents import diff as diff_agent
from vault_seed.agents import fetch as fetch_agent
from vault_seed.agents import map as map_agent
from vault_seed.config import ARTIFACTS_DIR, Settings


def test_pipeline_dry_run_end_to_end(monkeypatch):
    monkeypatch.setenv("VAULT_SEED_DRY_RUN", "1")
    # Clear any inherited Supabase env so Settings.from_env exercises dry-run.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = Settings.from_env()
    assert settings.dry_run is True

    fetch_agent.run(settings)
    map_agent.run()
    diff_agent.run()
    apply_agent.run(settings)

    for name in ("01_fetch.json", "02_map.json", "03_diff.json", "04_apply.json"):
        path = ARTIFACTS_DIR / name
        assert path.exists(), f"{name} missing"
        json.loads(path.read_text(encoding="utf-8"))  # valid JSON

    rendered = (ARTIFACTS_DIR / "secrets.rendered.toml").read_text(encoding="utf-8")
    assert "SUPABASE_URL" in rendered
    assert "<SET_ME>" in rendered  # placeholders preserved in dry-run


def test_apply_refuses_when_secrets_missing(monkeypatch, tmp_path):
    """Non-dry-run apply must bail out if required secrets are missing."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.delenv("VAULT_SEED_DRY_RUN", raising=False)

    diff_path = ARTIFACTS_DIR / "03_diff.json"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(json.dumps({
        "plan": {
            "products_insert": [], "products_update": [],
            "products_unchanged": 0,
            "users_insert": [], "users_update": [],
            "users_unchanged": 0,
            "secrets_present": ["SUPABASE_URL"],
            "secrets_missing": ["SUPABASE_SERVICE_ROLE_KEY"],
        },
        "summary": {},
        "dry_run": False,
    }), encoding="utf-8")

    settings = Settings.from_env(dry_run=False)
    try:
        apply_agent.run(settings)
        assert False, "apply should have refused"
    except RuntimeError as e:
        assert "Required secrets missing" in str(e)
