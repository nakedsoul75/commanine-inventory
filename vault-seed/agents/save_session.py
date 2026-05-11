"""세션 저장: 02.projects/sessions/에 로그 작성 + current-state.md 갱신 안내.

사용:
  python agents/save_session.py --slug "vault-셋업" --summary "옵션 C 시드 패키지 생성"
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from _lib import slugify, vault_root


TEMPLATE_FALLBACK = """---
date: "{date}"
slug: "{slug}"
---

# 세션 로그 — {date} {slug}

## 작업한 것

- {summary}

## 결정한 것

-

## 미해결·다음 세션 이어갈 것

-

## 컨텍스트 메모

-
"""


def _load_template() -> str:
    p = vault_root() / "03.resources" / "templates" / "session-log.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return TEMPLATE_FALLBACK


def main() -> int:
    parser = argparse.ArgumentParser(description="세션 로그 저장")
    parser.add_argument("--slug", required=True, help="세션 슬러그 (한 줄 요약)")
    parser.add_argument("--summary", default="", help="작업 요약 (옵션)")
    parser.add_argument("--cost", type=float, default=0.0, help="세션 비용 USD")
    parser.add_argument("--duration", type=int, default=0, help="세션 시간(분)")
    args = parser.parse_args()

    today = dt.date.today().isoformat()
    slug = slugify(args.slug)
    sessions_dir = vault_root() / "02.projects" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    fname = f"{today}-{slug}.md"
    out = sessions_dir / fname

    template = _load_template()
    body = (
        template.replace("{{date}}", today)
        .replace("{{slug}}", slug)
        .replace("{{cost_usd}}", str(args.cost))
        .replace("{{duration_min}}", str(args.duration))
        .replace("{date}", today)
        .replace("{slug}", slug)
        .replace("{summary}", args.summary or "(요약 없음)")
    )

    if out.exists():
        print(f"이미 존재: {out}", file=sys.stderr)
        return 1
    out.write_text(body, encoding="utf-8")
    print(f"saved: {out}")

    state_file = vault_root() / "05.claude-context" / "current-state.md"
    if state_file.exists():
        print(f"\n다음 단계: {state_file}를 편집하여 다음 세션 컨텍스트를 갱신하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
