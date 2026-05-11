# Operating Guide

## 매일 사용 흐름

### 세션 시작

1. Claude Code에 다음과 같이 말함: **"옵시디언으로"** 또는 vault 디렉토리에서 세션 시작
2. Claude가 자동으로 `05.claude-context/CLAUDE.md`를 읽고 `current-state.md`를 확인합니다
3. 진행 중인 작업이 보이면 그대로 이어서 진행

### 작업 중

- 자유롭게 메모하고 코드 작성. 어디에 둘지 고민되면 `00.inbox/`에 던지고 나중에 분류.
- 특정 프로젝트 작업 중이면 해당 `02.projects/<프로젝트>/_context.md`를 갱신.
- 결정사항 (운영 방식·아키텍처 변경)은 `05.claude-context/evolution-log.md`에 한 줄 추가.

### 세션 종료

다음 중 하나로 마무리:

- **"마무리하자"** / **"끝"** → Claude가 자동으로 다음을 수행:
  - `02.projects/sessions/YYYY-MM-DD-<slug>.md` 작성
  - `current-state.md` 갱신
  - git add, commit, push

- 수동:
  ```bash
  python agents/save_session.py --slug "오늘 작업 한 줄" --summary "..."
  # current-state.md 직접 편집
  git add . && git commit -m "..." && git push
  ```

## 블로그 자동화

### 단발 실행

```bash
python agents/pipeline_runner.py /path/to/source.pdf --brand factory-nine
```

결과: `02.projects/factory9-pipeline/blog-queue/<slug>.md`에 frontmatter + 본문 저장.

- `status: draft` → QA 통과, 발행 검토용
- `status: needs-human-review` → 재작성 1회 후에도 QA 실패. 사람이 보고 결정.

### 큐 상태 확인

```bash
python agents/pipeline_runner.py --status
```

### 품질 기준 조정

`agents/quality-standards/blog.md` 직접 편집. 다음 실행부터 반영됩니다.

## 신규 프로젝트

```bash
python agents/create_project.py "프로젝트 이름" --brand factory-nine
```

`02.projects/<슬러그>/`에 README와 `_context.md` 시드 생성.

## 비용 모니터링

매 API 호출은 `02.projects/factory9-pipeline/_logs/cost-log.jsonl`에 한 줄씩 누적.

오늘 비용 합계:
```bash
python -c "import json,datetime,sys,pathlib; \
today=datetime.date.today().isoformat(); \
p=pathlib.Path('02.projects/factory9-pipeline/_logs/cost-log.jsonl'); \
total=sum(json.loads(l)['cost_usd'] for l in p.read_text().splitlines() if l.startswith('{') and today in l) if p.exists() else 0; \
print(f'${total:.4f}')"
```

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ANTHROPIC_API_KEY` not set | `.env` 미설치 | `cp agents/.env.example agents/.env` 후 키 입력 |
| `ModuleNotFoundError: anthropic` | 의존성 미설치 | `pip install -r agents/requirements.txt` |
| QA 응답 JSON 파싱 실패 | 모델이 펜스를 둘러쌌거나 prose 추가 | 다시 실행하면 대개 해결. 반복되면 시스템 프롬프트 강화. |
| 푸시 거부 (403) | GitHub App 권한 부족 | Settings → Installed GitHub Apps → Claude 설치 |
