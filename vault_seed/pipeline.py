"""In-process orchestrator: runs fetch -> map -> diff -> apply sequentially.

Use this for local smoke tests. The cloud workflow runs each agent as its
own job so artifacts are inspectable independently.
"""
from __future__ import annotations

import sys

from vault_seed.agents import apply as apply_agent
from vault_seed.agents import diff as diff_agent
from vault_seed.agents import fetch as fetch_agent
from vault_seed.agents import map as map_agent
from vault_seed.config import Settings


def run() -> int:
    settings = Settings.from_env()
    print("=" * 60)
    print(f"vault-seed pipeline  dry_run={settings.dry_run}")
    print("=" * 60)
    fetch_agent.run(settings)
    map_agent.run()
    diff_agent.run()
    apply_agent.run(settings)
    print("=" * 60)
    print("vault-seed pipeline OK")
    return 0


if __name__ == "__main__":
    sys.exit(run())
