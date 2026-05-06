# Supabase 셋업 가이드 (5분)

## 1. 가입 (1분)

1. https://supabase.com 접속
2. 우측 상단 **Start your project** 클릭
3. **Continue with GitHub** 선택 (본인 nakedsoul75 계정)
4. GitHub 권한 승인

## 2. 프로젝트 생성 (2분)

1. **New Project** 클릭
2. 입력:

| 항목 | 입력값 |
|---|---|
| **Organization** | (자동 생성된 본인 organization 선택) |
| **Project name** | `commanine-inventory` |
| **Database Password** | 강한 비밀번호 (메모장에 임시 저장 — 잊으면 재설정 가능commanine2026++ ) |
| **Region** | **Northeast Asia (Seoul)** 또는 Tokyo |
| **Pricing Plan** | **Free** |
3. **Create new project** 클릭
4. 1-2분 대기 (DB 초기화)

## 3. 발급되는 정보 메모 (2분)

프로젝트 생성 완료 후:

### 3-1. Project URL + Keys
- 좌측 메뉴 **Settings → API**
- 다음 값을 복사 (메모장에 임시 저장):

| 항목 | 위치 | 용도 |
|---|---|---|
| **Project URL=https://qzxfptcqcwyayfnffgze.supabase.co
| **anon / public** | Project API keys | 클라이언트용 (공개 가능) |
| **service_role** | Project API keys | 서버용 (비밀, 절대 노출 X) |

### 3-2. Database Password
- 가입 시 입력한 비밀번호
- 잊었으면 **Settings → Database → Reset database password**로 재설정

## 4. SQL 스키마 실행 (1분)

1. 좌측 메뉴 **SQL Editor** 클릭
2. **+ New query** 클릭
3. 본인 PC의 다음 파일 내용을 통째로 복사:
   ```
   C:\Users\naked\Documents\agent\commanine_inventory\sql\01_schema.sql
   ```
4. SQL Editor에 붙여넣기 → 우측 하단 **Run** (또는 Ctrl+Enter)
5. 결과 확인: "Schema created successfully" 메시지

## 5. 테이블 생성 확인

- 좌측 메뉴 **Table Editor**
- 다음 테이블이 보여야 함:
  - products
  - orders
  - shipments
  - inbound
  - sku_mapping
  - users

## 6. 다음 단계

`commanine_inventory/.env` 파일에 위 정보 입력:

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

→ 그 다음 마스터 데이터 import 진행:
```bash
python scripts/import_master.py
```

## 무료 플랜 한도 (충분함)

- DB 용량: 500 MB → 우리 데이터 ~50 MB/년
- API 요청: 50,000 monthly active users
- Storage: 1 GB
- **단점**: 7일 비활성 시 일시정지 (매일 사용하면 자동 해결)

## 문제 해결

- **이메일 인증 못 받음** → 스팸함 확인
- **프로젝트 생성 멈춤** → 새로고침 후 재시도
- **SQL 에러** → 메시지 그대로 알려주세요

---

> 이 단계 완료 후 알려주세요:
> - Supabase URL / Key 발급 완료 ✅
> - 스키마 실행 완료 ✅
>
> ⚠️ Project URL은 안전합니다 (공개되어도 무관).
> ⚠️ service_role key는 시크릿입니다 — 채팅에 절대 올리지 마세요. .env에만 저장.
