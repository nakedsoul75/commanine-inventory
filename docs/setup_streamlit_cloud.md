# Streamlit Cloud 배포 가이드 (30분, 무료)

배포 후 외부 인터넷 어디서든 폰/PC로 접근 가능. URL 형식:
```
https://commanine-inventory-{난수}.streamlit.app
```

## 사전 조건
- ✅ Day 1~5 완료 (앱 로컬에서 동작 확인)
- ✅ Supabase 운영 중
- ⏳ GitHub Public 레포 필요 (이 가이드에서 만듦)

---

## 1. GitHub 레포 생성 + Push (10분)

### 1-1. GitHub Desktop으로 (가장 쉬움)
1. **GitHub Desktop 앱** 열기
2. **File → Add Local Repository...** → 폴더 선택:
   ```
   C:\Users\naked\Documents\agent\commanine_inventory
   ```
3. 우측 상단 **Publish repository** 클릭
4. 입력:
   - **Name**: `commanine-inventory`
   - **Description**: `COMMANINE 재고/주문 통합 관리`
   - **Keep this code private**: ⚪ **체크 해제** (Streamlit Cloud Free는 Public만)
5. **Publish Repository** 클릭

→ https://github.com/nakedsoul75/commanine-inventory 생성 완료

### 1-2. 또는 웹에서 직접
1. https://github.com/new 접속
2. Name: `commanine-inventory`, **Public**, README/gitignore 추가 X
3. Create repository
4. PowerShell:
   ```powershell
   cd "C:\Users\naked\Documents\agent\commanine_inventory"
   git remote add origin https://github.com/nakedsoul75/commanine-inventory.git
   git branch -M main
   git push -u origin main
   ```

### ⚠️ 시크릿 절대 안 올라감 확인
GitHub 레포에서 `.env` 파일이 **안 보여야** 정상 (`.gitignore`로 제외됨).
혹시 보이면 즉시 Supabase에서 키 재발급.

---

## 2. Streamlit Cloud 가입 + 배포 (15분)

### 2-1. 가입
1. https://share.streamlit.io 접속
2. **Continue with GitHub** 선택
3. nakedsoul75 GitHub 계정으로 로그인
4. 권한 승인 (Streamlit이 Public 레포 읽기)

### 2-2. 새 앱 배포
1. **Create app** 클릭
2. **Deploy a public app from GitHub** 선택
3. 입력:
   - **Repository**: `nakedsoul75/commanine-inventory`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL** (선택): `commanine-inventory` 같은 짧은 이름
4. **Deploy** 클릭

→ 2-3분 빌드 → 자동 실행 → 첫 화면 표시

### 2-3. Secrets 입력 (필수)
첫 실행 시 **Supabase 설정 누락** 에러가 나옵니다.

1. 앱 페이지 우측 상단 **⋮ (점 3개)** → **Settings**
2. 좌측 **Secrets** 탭
3. 다음 내용 붙여넣기 (실제 값으로):
   ```toml
   SUPABASE_URL = "https://xxxxx.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "eyJhbGc..."
   ```
4. **Save** 클릭
5. 앱 자동 재시작 (1-2분)

### 2-4. 접속 확인
- 발급된 URL: `https://commanine-inventory-{난수}.streamlit.app`
- PC/폰 어디서든 접근 가능
- 로그인 화면 → admin PIN 입력 → 사용 시작

---

## 3. 직원에게 URL 공유

카톡/문자로 다음 안내:
```
콤마나인 입고 시스템 사용 가이드

1. 폰 브라우저에서 접속:
   https://commanine-inventory-xxxxx.streamlit.app

2. 로그인:
   이름: 본인
   PIN: (별도 안내)

3. 입고 등록:
   📥 입고 등록 → 검색 → 수량 → 저장
```

(직원 추가는 PC에서 `python scripts/create_admin.py`로 본인이 등록)

---

## 4. 운영 시 알아두세요

### 무료 티어 한도
- 1개 private 앱 (우리는 Public이라 무관)
- 메모리 1GB, 스토리지 1GB
- **7일 비활성 시 sleep** → 트래픽 있으면 자동 깨어남 (10초 정도 첫 로딩 느림)

### 자동 배포
- GitHub `main` 브랜치에 push할 때마다 **자동 재배포**
- 코드 수정 → git commit + push → 1-2분 후 반영

### 주요 작업
| 작업 | 방법 |
|---|---|
| 코드 수정 후 반영 | git push → 자동 |
| 시크릿 변경 | Streamlit Cloud → Settings → Secrets |
| 직원 PIN 변경 | PC에서 `python scripts/create_admin.py` |
| 로그 확인 | Streamlit Cloud → Manage app → Logs |
| 앱 재시작 | Streamlit Cloud → Reboot |

### 문제 해결
- **로그인 안 됨** → users 테이블 비어 있나? `create_admin.py` 실행
- **검색 느림** → 첫 로딩만 느림 (캐시 워밍업). 두 번째부터 빠름
- **Sleep으로 멈춤** → 매일 자동 알림(daily-report 봇)이 Supabase ping → 데이터 활성. 단, Streamlit Cloud는 별개 → 직원이 매일 한 번 접속하면 깨어 있음

---

## 5. 체크리스트

배포 전:
- [ ] 로컬에서 `streamlit run app.py` 정상 동작
- [ ] `.env`에 시크릿 있음 (gitignored)
- [ ] `.streamlit/secrets.toml` 없음 (또는 gitignored)

배포 후:
- [ ] URL 접속 → 로그인 화면 보임
- [ ] PIN으로 로그인 성공
- [ ] 5개 페이지 정상 표시
- [ ] 입고 등록 1건 테스트
- [ ] 폰에서 같은 URL 접속 확인
- [ ] 직원에게 URL 공유

완료!
