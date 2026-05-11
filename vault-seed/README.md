# dlnine-vault (시드 패키지)

옵션 C 풀 클라우드 운영 체계의 vault 시드입니다. 이 디렉토리는 `commanine-inventory` 리포에 임시로 위치한 패키지이며, 실제 운영 시에는 별도의 `dlnine-vault` 리포로 복사·이동하여 사용합니다.

## 빠른 시작

1. GitHub UI에서 새 private 리포 `dlnine-vault` 생성
2. `vault-seed/` 내용 전체를 새 리포 루트로 복사 후 커밋·푸시
3. 로컬에서 새 리포 클론 → Obsidian이 그 폴더를 열도록 설정
4. `agents/.env.example` 복사 → `.env`로 두고 `ANTHROPIC_API_KEY` 채우기
5. `pip install -r agents/requirements.txt`

## 디렉토리 규약

| 폴더 | 용도 | 형태 |
|---|---|---|
| `00.inbox/` | 분류 전 임시 메모 | 자유롭게 적고 주기적으로 분류 |
| `01.brands/` | 브랜드별 상시 정보 | 브랜드당 1개 폴더, 안에 자유 |
| `02.projects/` | 진행 중인 프로젝트 | 프로젝트당 1개 폴더, 종료 시 `04.archive/`로 |
| `02.projects/factory9-pipeline/` | 블로그 자동화 공용 작업 폴더 | `raw-data/`, `blog-queue/`, `_context.md` |
| `02.projects/sessions/` | 세션 로그 (날짜별) | `agents/save_session.py`가 자동 생성 |
| `03.resources/` | 영속적 참고자료, 템플릿 | `templates/` 하위에 시드 템플릿 |
| `04.archive/` | 종료된 프로젝트 보관 | 삭제하지 말고 여기로 이동 |
| `05.claude-context/` | Claude가 세션 시작 시 읽는 컨텍스트 | `current-state.md` 매 세션 갱신 |
| `06.workspace/` | 로컬 작업 디렉토리 (junction) | 리포에는 placeholder만, 실파일은 로컬 |
| `07.memory/` | 로컬 영속 메모리 (junction) | 리포에는 placeholder만, 실파일은 로컬 |
| `agents/` | 자동화 스크립트 | Python, 도커 없이 직접 실행 |
| `docs/` | 운영 가이드 | `operating-guide.md`부터 |

## 규칙

- `05.claude-context/CLAUDE.md`는 세션 시작 시 Claude가 자동으로 읽습니다.
- `current-state.md`는 매 세션 종료 시 갱신하여 다음 세션이 컨텍스트를 잇도록 합니다.
- `agents/quality-standards/blog.md`는 블로그 품질 기준입니다. 사용자가 직접 진화시킵니다 (Claude가 멋대로 바꾸지 않음).
- `_context.md` 파일은 해당 폴더 작업의 공유 메모입니다. 세션 간 단기 메모리 역할.
