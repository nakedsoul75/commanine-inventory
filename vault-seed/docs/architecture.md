# Architecture

## 옵션 C — 풀 클라우드

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub: dlnine-vault                    │
│  단일 진실 원천. 모든 vault·코드·로그가 여기에 산다.        │
└────────────────┬─────────────────────────┬──────────────────┘
                 │                         │
        clone/pull│push                     │ Claude Code on web
                 │                         │ (claude.ai/code)
                 ▼                         ▼
   ┌─────────────────────────┐    ┌────────────────────────┐
   │   로컬 Windows          │    │  웹 세션 (격리 컨테이너)│
   │   Obsidian + Git        │    │  python agents/*.py    │
   │   06.workspace (junction)│    │  read/write vault     │
   │   07.memory (junction)   │    │  push to dlnine-vault │
   └─────────────────────────┘    └────────────────────────┘
```

## 4-Agent 블로그 파이프라인

```
PDF
 │
 ▼  pdf_to_vault.py (pypdf)
raw-data/<slug>.md
 │
 ▼  blog_agent_pipeline.run_pipeline()
 │
 ├─ Outliner (Sonnet 4.6) — 핵심 메시지·구조
 │
 ├─ Writer (Opus 4.7, adaptive thinking) — 1차 초안
 │
 ├─ QA (Sonnet 4.6, JSON output) — 점수·피드백
 │      │
 │      └─ pass: false → Writer 재호출 (최대 1회)
 │
 └─ blog-queue/<slug>.md (frontmatter + body)
        status: draft  →  발행 검토
        status: needs-human-review  →  재작성 후에도 실패
```

## 모델 선택 근거

| 단계 | 모델 | 이유 |
|---|---|---|
| Outline | Sonnet 4.6 | 빠르고 저렴. 구조 잡기엔 충분. |
| Writer | Opus 4.7 | 1인칭 톤·맥락 이해·문장 품질. 비용을 들일 가치 있음. |
| QA | Sonnet 4.6 | 규칙 기반 채점은 Sonnet으로 충분. JSON 출력 안정성 좋음. |

비용 (1회 생성, 추정):
- Outline: ~$0.005
- Draft: ~$0.10–0.20
- QA: ~$0.01
- 재작성 시 +$0.10
- **1회 평균: $0.12–0.32**

## 비용 가드레일

1. **`MAX_REWRITES=1`** — 환경변수. QA 실패해도 재작성 1회로 제한. 무한 루프 방지.
2. **`SESSION_COST_WARN_USD=5.0`** — 세션 누적 $5 초과 시 사용자에게 경고 (구현은 향후).
3. **`cost-log.jsonl`** — 모든 호출 기록. 매 세션 종료 시 합계 확인.

## 디렉토리 분리 원칙

| 레이어 | 위치 | 동기화 |
|---|---|---|
| 영속 자산 (브랜드·프로젝트·결정) | `00–05.*/` | git 동기화 |
| 작업 큐·로그 | `02.projects/factory9-pipeline/_logs/` | gitignore |
| 자동화 코드 | `agents/` | git 동기화 |
| 로컬 작업물 | `06.workspace/` (junction) | gitignore, 로컬 전용 |
| 로컬 메모리 | `07.memory/` (junction) | gitignore, 로컬 전용 |

## 향후 확장 후보

- 다국어 블로그 (영문 출력 모델 분기)
- Managed Agents로 전환 (Anthropic 호스팅 컨테이너에서 파이프라인 실행)
- Slack 알림 (큐에 새 초안 들어가면 알림)
- 자동 발행 (Ghost·Wordpress API 연동)
