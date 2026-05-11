# Context Index

> 어떤 정보가 어디 있는지의 인덱스. Claude는 검색 전에 이 파일을 먼저 확인.

## 자주 찾는 정보

| 찾는 것 | 위치 |
|---|---|
| "지금 진행 중인 것" | `05.claude-context/current-state.md` |
| "장기 비전" | `05.claude-context/vision.md` |
| "왜 이렇게 결정했지" | `05.claude-context/evolution-log.md` |
| "운영 원칙" | `05.claude-context/sustainable-os.md` |
| 블로그 품질 기준 | `agents/quality-standards/blog.md` |
| factory9 파이프라인 메모 | `02.projects/factory9-pipeline/_context.md` |
| 세션 템플릿 | `03.resources/templates/session-log.md` |
| 블로그 템플릿 | `03.resources/templates/blog-draft.md` |
| 운영 가이드 | `docs/operating-guide.md` |
| 아키텍처 | `docs/architecture.md` |

## 자동화 스크립트

| 용도 | 스크립트 |
|---|---|
| PDF → vault 진입 | `agents/pdf_to_vault.py` |
| 블로그 4-agent 파이프라인 | `agents/blog_agent_pipeline.py` |
| PDF → 블로그 (오케스트레이션) | `agents/pipeline_runner.py` |
| 세션 종료·저장 | `agents/save_session.py` |
| 신규 프로젝트 생성 | `agents/create_project.py` |

## 브랜드별 폴더

- `01.brands/factory-nine/`
- `01.brands/commanine/`
- (필요 시 추가)
