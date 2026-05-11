# vault-seed

Cloud-only integrated seed package for COMMANINE.

Seeds the Supabase **products** + **users** tables and validates the Streamlit
Cloud **secrets vault** through a 4-agent pipeline:

```
fetch ─▶ map ─▶ diff ─▶ apply
```

Each agent runs as a separate GitHub Actions job and passes state through
JSON artifacts in `vault_seed/artifacts/` (gitignored). No local file paths,
no Excel imports — everything the package needs lives inside the repo, so it
runs reproducibly on a fresh CI runner.

## Layout

```
vault_seed/
├── __init__.py
├── config.py            # env-only settings
├── schemas.py           # ProductRow / UserRow / DiffPlan
├── pipeline.py          # in-process orchestrator (smoke test)
├── agents/
│   ├── fetch.py         # 1. read seed CSVs + Supabase snapshot
│   ├── map.py           # 2. normalize + validate rows
│   ├── diff.py          # 3. compute insert/update/unchanged plan
│   └── apply.py         # 4. idempotent upsert + render secrets.toml
├── data/
│   ├── products.seed.csv
│   ├── users.seed.csv
│   └── secrets.template.toml
└── tests/               # unit tests (no network)
```

## Run locally (smoke test, no DB writes)

```bash
VAULT_SEED_DRY_RUN=1 python -m vault_seed.pipeline
```

Outputs land in `vault_seed/artifacts/`:

```
01_fetch.json   02_map.json   03_diff.json   04_apply.json
secrets.rendered.toml
```

## Run in CI

Push to any branch — `.github/workflows/vault-seed.yml` runs the 4 agents as
4 separate jobs. On `main` (or via `workflow_dispatch` with `dry_run=false`)
the apply step performs the actual Supabase upsert.

### Required GitHub Actions secrets

| Secret | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side key for upserts |
| `SUPABASE_ANON_KEY` | Optional — rendered into the secrets template |
| `VAULT_SEED_PIN_<NAME>` | 4-digit PIN per user listed in `users.seed.csv` |

User PINs are **never** stored in CSV. The apply agent reads each user's PIN
from `VAULT_SEED_PIN_<NAME_UPPER>` (or the `pin_env_var` column override) and
bcrypt-hashes it at apply time. Users without a PIN env var are skipped — add
the secret later and rerun the workflow to seed them.

## Replacing the sample seed

`vault_seed/data/products.seed.csv` ships with 4 sample rows so the pipeline
runs end-to-end out of the box. Replace it with your real master export
(same columns) and commit. The diff agent will compute the delta against
the current Supabase state — only changed rows are upserted.
