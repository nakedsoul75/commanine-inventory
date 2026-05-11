"""블로그 생성 4-에이전트 파이프라인.

흐름: Outline (Sonnet 4.6) → Draft (Opus 4.7) → QA (Sonnet 4.6) → Revise (Opus 4.7, 최대 1회).

각 단계의 사용량과 비용은 cost-log.jsonl에 기록됩니다.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import anthropic

from _lib import (
    load_env,
    log_cost,
    max_rewrites,
    qa_model,
    vault_root,
    writer_model,
)


@dataclass
class PipelineResult:
    draft_markdown: str
    qa_report: dict
    passed: bool
    rewrites_used: int
    total_cost_usd: float


def _read_quality_standards() -> str:
    path = vault_root() / "agents" / "quality-standards" / "blog.md"
    return path.read_text(encoding="utf-8")


def _outline(client: anthropic.Anthropic, source_text: str, brand: str) -> tuple[str, float]:
    """간단한 outliner: 핵심 메시지·구조 잡기. Sonnet 4.6."""
    system = (
        "You are an outliner for a Korean business blog. "
        f"Brand context: {brand}. "
        "Given a source document, return a tight outline: "
        "1) 핵심 메시지 한 문장, "
        "2) 도입에서 약속할 것, "
        "3) 본문 섹션 3-4개의 제목, "
        "4) 결론·CTA. "
        "Korean only. No prose around it."
    )
    resp = client.messages.create(
        model=qa_model(),
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": source_text}],
    )
    cost = log_cost(
        script="blog_agent_pipeline.outline",
        model=qa_model(),
        usage=resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage),
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text, cost


def _draft(
    client: anthropic.Anthropic,
    source_text: str,
    outline: str,
    brand: str,
    revision_feedback: str | None = None,
) -> tuple[str, float]:
    """초안 작성 (또는 재작성). Opus 4.7."""
    system = (
        "You are a Korean small-business owner writing a first-person blog post. "
        f"Brand: {brand}. "
        "Write in '저는/제가' voice. Avoid marketing buzzwords. "
        "Length: 1,500-2,500 Korean characters (공백 제외). "
        "Output ONLY the blog body in Markdown — no frontmatter, no commentary."
    )

    user_parts = [
        "<source_document>\n" + source_text + "\n</source_document>",
        "<outline>\n" + outline + "\n</outline>",
    ]
    if revision_feedback:
        user_parts.append(
            "<revision_feedback>\n"
            "이전 초안이 다음 사유로 QA를 통과하지 못했습니다. 반영해서 다시 작성하세요.\n"
            + revision_feedback
            + "\n</revision_feedback>"
        )

    resp = client.messages.create(
        model=writer_model(),
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": "\n\n".join(user_parts)}],
    )
    cost = log_cost(
        script="blog_agent_pipeline.draft",
        model=writer_model(),
        usage=resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage),
        note="revision" if revision_feedback else "first",
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text.strip(), cost


def _qa(
    client: anthropic.Anthropic,
    draft: str,
    source_text: str,
    quality_standards: str,
) -> tuple[dict, float]:
    """QA 채점. Sonnet 4.6. JSON으로 반환."""
    system = (
        "You are a strict QA reviewer for Korean business blog posts. "
        "Use the provided quality standards verbatim. "
        "Respond ONLY with a single JSON object matching the schema in the standards. "
        "No prose, no markdown fences."
    )
    user = (
        "<quality_standards>\n" + quality_standards + "\n</quality_standards>\n\n"
        "<source>\n" + source_text + "\n</source>\n\n"
        "<draft>\n" + draft + "\n</draft>"
    )

    resp = client.messages.create(
        model=qa_model(),
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    cost = log_cost(
        script="blog_agent_pipeline.qa",
        model=qa_model(),
        usage=resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage),
    )

    text = next((b.text for b in resp.content if b.type == "text"), "").strip()
    # 모델이 ```json 펜스를 둘러쌌을 경우 제거
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        report = json.loads(text)
    except json.JSONDecodeError:
        report = {
            "pass": False,
            "score": 0,
            "instant_fails": ["QA 응답 JSON 파싱 실패"],
            "improvements": [],
            "verdict": text[:500],
        }
    return report, cost


def run_pipeline(source_text: str, brand: str = "factory-nine") -> PipelineResult:
    load_env()
    client = anthropic.Anthropic()
    standards = _read_quality_standards()

    outline, c1 = _outline(client, source_text, brand)
    draft, c2 = _draft(client, source_text, outline, brand)
    report, c3 = _qa(client, draft, source_text, standards)
    total = c1 + c2 + c3
    rewrites = 0

    while not report.get("pass") and rewrites < max_rewrites():
        rewrites += 1
        feedback = "\n".join(
            ["- " + s for s in report.get("instant_fails", [])]
            + ["- " + s for s in report.get("improvements", [])]
        )
        draft, cr = _draft(client, source_text, outline, brand, revision_feedback=feedback)
        report, cq = _qa(client, draft, source_text, standards)
        total += cr + cq

    return PipelineResult(
        draft_markdown=draft,
        qa_report=report,
        passed=bool(report.get("pass")),
        rewrites_used=rewrites,
        total_cost_usd=round(total, 4),
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="블로그 4-agent 파이프라인 (단일 실행)")
    parser.add_argument("source_md", type=Path, help="raw-data 마크다운 입력")
    parser.add_argument("--brand", default="factory-nine")
    parser.add_argument("--output", type=Path, help="출력 마크다운 경로 (생략 시 stdout)")
    args = parser.parse_args()

    if not args.source_md.exists():
        print(f"파일 없음: {args.source_md}", file=sys.stderr)
        return 1

    source_text = args.source_md.read_text(encoding="utf-8")
    result = run_pipeline(source_text, brand=args.brand)

    print(f"[passed={result.passed}] [rewrites={result.rewrites_used}] [cost=${result.total_cost_usd}]")
    print(json.dumps(result.qa_report, ensure_ascii=False, indent=2))

    if args.output:
        args.output.write_text(result.draft_markdown, encoding="utf-8")
        print(f"saved: {args.output}")
    else:
        print("\n---\n")
        print(result.draft_markdown)

    return 0 if result.passed else 2


if __name__ == "__main__":
    sys.exit(main())
