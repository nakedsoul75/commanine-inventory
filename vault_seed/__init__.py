"""vault-seed: cloud-only integrated seed package for COMMANINE.

Seeds Supabase (products, users) and validates the Streamlit secrets vault
through a 4-agent pipeline: Fetch -> Map -> Diff -> Apply.

Entry points:
  python -m vault_seed.pipeline          # run all 4 agents in-process
  python -m vault_seed.agents.fetch      # individual agent (cloud step)
  python -m vault_seed.agents.map
  python -m vault_seed.agents.diff
  python -m vault_seed.agents.apply
"""

__version__ = "0.1.0"
