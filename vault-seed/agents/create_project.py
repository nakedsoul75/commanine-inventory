"""신규 프로젝트 폴더 생성: 02.projects/<slug>/에 readme + _context.md 시드."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from _lib import slugify, vault_root


def main() -> int:
    parser = argparse.ArgumentParser(description="신규 프로젝트 폴더 생성")
    parser.add_argument("name", help="프로젝트명 (한국어 가능, 자동 슬러그화)")
    parser.add_argument(
        "--brand",
        default="",
        help="연관 브랜드 (선택). 01.brands/ 하위 슬러그.",
    )
    args = parser.parse_args()

    slug = slugify(args.name)
    today = dt.date.today().isoformat()
    root = vault_root() / "02.projects" / slug

    if root.exists():
        print(f"이미 존재: {root}", file=sys.stderr)
        return 1

    root.mkdir(parents=True)

    template_path = vault_root() / "03.resources" / "templates" / "project-readme.md"
    if template_path.exists():
        readme_body = (
            template_path.read_text(encoding="utf-8")
            .replace("{{project_name}}", args.name)
            .replace("{{date}}", today)
        )
    else:
        readme_body = f"# {args.name}\n\nCreated: {today}\n"

    (root / "README.md").write_text(readme_body, encoding="utf-8")

    context_body = (
        f"# {args.name} — 공유 컨텍스트\n\n"
        f"Brand: {args.brand or '(none)'}\n"
        f"Created: {today}\n\n"
        "## 최근 작업\n\n-\n\n"
        "## 미해결\n\n-\n"
    )
    (root / "_context.md").write_text(context_body, encoding="utf-8")

    print(f"created: {root}")
    print("  README.md")
    print("  _context.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
