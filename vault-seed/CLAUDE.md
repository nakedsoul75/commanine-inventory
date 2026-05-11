# CLAUDE.md

이 파일은 Claude Code 세션 시작 시 자동으로 로드됩니다. 매 세션에서 가장 먼저 읽고 따르세요.

## 1. 세션 시작 시 필수 행동

1. `05.claude-context/current-state.md`를 **반드시 먼저 읽으세요**. 이 파일은 가장 최근 세션의 상태와 미해결 항목을 담고 있습니다.
2. 사용자가 작업 중인 프로젝트가 명시되어 있으면, 해당 프로젝트 폴더의 `_context.md`도 읽으세요.
3. 그 다음 사용자 요청을 처리하세요.

## 2. 세션 종료 시 필수 행동

사용자가 "마무리", "세션 저장", "끝", "save session" 등을 말하면:

1. `agents/save_session.py`를 실행하거나, 직접 다음을 수행:
   - `02.projects/sessions/YYYY-MM-DD-<slug>.md`에 세션 로그 작성 (템플릿: `03.resources/templates/session-log.md`)
   - `05.claude-context/current-state.md`를 최신 상태로 갱신
   - 변경사항 git commit & push

## 3. 핵심 컨텍스트 파일

다음 파일들은 필요 시 참조하세요:

- `05.claude-context/vision.md` — 사용자의 장기 비전·목표
- `05.claude-context/sustainable-os.md` — 운영 철학·원칙
- `05.claude-context/evolution-log.md` — 시스템 진화 기록
- `05.claude-context/context-index.md` — 어떤 정보가 어디 있는지 인덱스

## 4. 절대 하지 말 것

- **`agents/quality-standards/blog.md` 자동 수정 금지.** 이 파일은 사용자가 직접 진화시킵니다. 사용자가 명시적으로 요청하지 않는 한 변경 금지.
- **`04.archive/` 파일 자동 삭제 금지.** 보관 목적이므로 옮기지도 지우지도 마세요.
- **API 키·시크릿을 vault 파일에 작성 금지.** 키는 `agents/.env` (gitignore됨)에만.

## 5. 자주 쓰는 명령

| 사용자 발화 | 의도 | 실행 |
|---|---|---|
| "옵시디언으로", "vault로" | 작업물을 vault에 기록 | 적절한 폴더의 `_context.md` 또는 새 파일에 추가 |
| "마무리", "끝" | 세션 종료 | `agents/save_session.py` |
| "블로그 만들어줘" | PDF → 블로그 초안 자동화 | `agents/pipeline_runner.py <pdf>` |
| "프로젝트 만들어줘 X" | 신규 프로젝트 폴더 생성 | `agents/create_project.py X` |

## 6. 비용 가드레일

- 블로그 파이프라인은 재작성 1회 한계 (무한 루프 방지).
- 모든 API 호출은 `02.projects/factory9-pipeline/_logs/cost-log.jsonl`에 기록.
- 세션당 누적 비용이 $5 초과 시 사용자에게 확인 요청.
