# factory9-pipeline — 공유 컨텍스트

> 이 폴더는 블로그 자동화 파이프라인의 공용 작업 공간입니다. 단기 메모, 큐 상태, 데이터 위치를 추적.

## 폴더 구조

- `raw-data/` — 입력 PDF·소스 자료
- `blog-queue/` — 생성된 블로그 초안 (status: draft → reviewed → published)
- `_logs/` — 파이프라인 실행 로그·비용 (gitignore됨)

## 파이프라인 흐름

```
PDF → pdf_to_vault.py → raw-data/<slug>.md (텍스트 추출)
                    ↓
       blog_agent_pipeline.py
                    ↓
       Writer (Opus 4.7) → 초안
                    ↓
       QA (Sonnet 4.6) → 점수·피드백
                    ↓
       (QA 실패 시 1회 재작성)
                    ↓
       blog-queue/<slug>.md (status: draft)
```

## 현재 큐 상태

- 대기 중: 0
- 작성 중: 0
- QA 통과: 0
- 발행됨: 0

(이 카운트는 사람이 갱신하거나 `pipeline_runner.py --status` 명령으로 확인)

## 알려진 이슈·메모

- (없음 — 첫 실행 전)
