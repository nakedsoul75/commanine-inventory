"""PDF 파일에서 텍스트를 추출하여 raw-data/<slug>.md로 저장."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader

from _lib import slugify, vault_root


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"\n\n<!-- page {i} -->\n\n{text.strip()}")
    return "\n".join(parts).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF → vault raw-data 마크다운 변환")
    parser.add_argument("pdf", type=Path, help="입력 PDF 파일")
    parser.add_argument("--slug", help="출력 슬러그 (생략 시 파일명에서 자동)")
    parser.add_argument(
        "--brand",
        default="factory-nine",
        help="브랜드 식별자 (기본: factory-nine)",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"파일 없음: {args.pdf}", file=sys.stderr)
        return 1

    slug = args.slug or slugify(args.pdf.stem)
    text = extract_pdf_text(args.pdf)
    if not text:
        print("경고: 추출된 텍스트가 비어있습니다.", file=sys.stderr)

    out_dir = vault_root() / "02.projects" / "factory9-pipeline" / "raw-data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.md"

    frontmatter = (
        "---\n"
        f"source_pdf: {args.pdf.name}\n"
        f"brand: {args.brand}\n"
        f"slug: {slug}\n"
        "---\n\n"
    )
    out_path.write_text(frontmatter + text, encoding="utf-8")
    print(f"saved: {out_path}")
    print(f"slug: {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
