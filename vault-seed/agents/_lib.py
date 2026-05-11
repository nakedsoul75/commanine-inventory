"""공유 유틸리티: vault root 탐지, .env 로드, 비용 로깅."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


WRITER_MODEL_DEFAULT = "claude-opus-4-7"
QA_MODEL_DEFAULT = "claude-sonnet-4-6"


def vault_root() -> Path:
    """vault 루트 디렉토리를 반환.

    탐지 순서:
    1. VAULT_ROOT 환경변수
    2. 이 파일의 부모의 부모 (agents/ 위)
    """
    env = os.environ.get("VAULT_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent


def load_env() -> None:
    """agents/.env 또는 vault root의 .env 로드."""
    here = Path(__file__).resolve().parent
    for candidate in (here / ".env", vault_root() / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
            return


def writer_model() -> str:
    return os.environ.get("WRITER_MODEL", WRITER_MODEL_DEFAULT)


def qa_model() -> str:
    return os.environ.get("QA_MODEL", QA_MODEL_DEFAULT)


def max_rewrites() -> int:
    return int(os.environ.get("MAX_REWRITES", "1"))


def log_cost(
    *,
    script: str,
    model: str,
    usage: dict,
    note: str = "",
) -> float:
    """API 사용량을 cost-log.jsonl에 기록하고 추정 비용(USD)을 반환."""
    rates = {
        "claude-opus-4-7": {"in": 5.0, "out": 25.0},
        "claude-opus-4-6": {"in": 5.0, "out": 25.0},
        "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
        "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
    }
    rate = rates.get(model, {"in": 5.0, "out": 25.0})

    in_tok = usage.get("input_tokens", 0) or 0
    out_tok = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_create = usage.get("cache_creation_input_tokens", 0) or 0

    cost = (
        in_tok * rate["in"] / 1_000_000
        + out_tok * rate["out"] / 1_000_000
        + cache_read * rate["in"] * 0.1 / 1_000_000
        + cache_create * rate["in"] * 1.25 / 1_000_000
    )

    log_dir = vault_root() / "02.projects" / "factory9-pipeline" / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cost-log.jsonl"

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "script": script,
        "model": model,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cache_read": cache_read,
        "cache_create": cache_create,
        "cost_usd": round(cost, 6),
        "note": note,
    }
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return cost


def slugify(text: str, max_len: int = 60) -> str:
    """파일명 안전한 slug."""
    out = []
    for ch in text.strip().lower():
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch in " /":
            out.append("-")
    s = "".join(out).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:max_len] or "untitled"
