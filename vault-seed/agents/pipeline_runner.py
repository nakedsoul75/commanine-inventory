"""오케스트레이션: PDF → raw-data → 블로그 초안 → blog-queue.

사용:
  python agents/pipeline_runner.py <pdf_path> [--brand factory-nine]
  python agents/pipeline_runner.py --status     # 큐 카운트
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from _lib import slugify, vault_root
from blog_agent_pipeline import run_pipeline
from pdf_to_vault import extract_pdf_text


def _save_draft(slug: str, brand: str, source_pdf: str, body: str, report: dict, rewrites: int) -> Path:
    out_dir = vault_root() / "02.projects" / "factory9-pipeline" / "blog-queue"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slug}.md"

    today = dt.date.today().isoformat()
    title_line = next((ln for ln in body.splitlines() if ln.startswith("# ")), "")
    title = title_line.lstrip("# ").strip() or slug

    frontmatter = (
        "---\n"
        f"title: \"{title}\"\n"
        f"slug: \"{slug}\"\n"
        f"brand: \"{brand}\"\n"
        f"status: {'draft' if report.get('pass') else 'needs-human-review'}\n"
        f"source_pdf: \"{source_pdf}\"\n"
        f"created: \"{today}\"\n"
        f"qa_pass: {str(bool(report.get('pass'))).lower()}\n"
        f"qa_iteration: {rewrites}\n"
        "qa_notes: |\n"
        f"  {json.dumps(report, ensure_ascii=False)}\n"
        "---\n\n"
    )
    out.write_text(frontmatter + body, encoding="utf-8")
    return out


def _status() -> None:
    queue_dir = vault_root() / "02.projects" / "factory9-pipeline" / "blog-queue"
    if not queue_dir.exists():
        print("blog-queue 디렉토리가 비어있습니다.")
        return
    by_status: dict[str, int] = {}
    for p in queue_dir.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        status = "unknown"
        for line in text.splitlines():
            if line.startswith("status:"):
                status = line.split(":", 1)[1].strip()
                break
            if line == "---" and status != "unknown":
                break
        by_status[status] = by_status.get(status, 0) + 1
    if not by_status:
        print("(파일 없음)")
        return
    for k, v in sorted(by_status.items()):
        print(f"  {k}: {v}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF → 블로그 초안 오케스트레이션")
    parser.add_argument("pdf", type=Path, nargs="?", help="입력 PDF (--status 시 생략 가능)")
    parser.add_argument("--brand", default="factory-nine")
    parser.add_argument("--slug", help="출력 슬러그 (생략 시 자동)")
    parser.add_argument("--status", action="store_true", help="큐 상태만 표시하고 종료")
    args = parser.parse_args()

    if args.status:
        _status()
        return 0

    if not args.pdf or not args.pdf.exists():
        print("PDF 경로가 필요합니다.", file=sys.stderr)
        parser.print_help()
        return 1

    slug = args.slug or slugify(args.pdf.stem)

    # 1. PDF 추출
    raw_text = extract_pdf_text(args.pdf)
    raw_dir = vault_root() / "02.projects" / "factory9-pipeline" / "raw-data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{slug}.md"
    raw_path.write_text(
        f"---\nsource_pdf: {args.pdf.name}\nbrand: {args.brand}\nslug: {slug}\n---\n\n{raw_text}",
        encoding="utf-8",
    )
    print(f"[1/2] raw saved: {raw_path}")

    # 2. 파이프라인
    print("[2/2] running 4-agent pipeline...")
    result = run_pipeline(raw_text, brand=args.brand)

    out_path = _save_draft(
        slug=slug,
        brand=args.brand,
        source_pdf=args.pdf.name,
        body=result.draft_markdown,
        report=result.qa_report,
        rewrites=result.rewrites_used,
    )
    print(f"draft saved: {out_path}")
    print(
        f"passed={result.passed} rewrites={result.rewrites_used} "
        f"cost=${result.total_cost_usd}"
    )
    return 0 if result.passed else 2


if __name__ == "__main__":
    sys.exit(main())
