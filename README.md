# COMMANINE 재고/주문 통합 관리 시스템

카페24 + 스마트스토어 + 입고 + 출하 + 재고를 이지어드민 코드 기준으로 통합 관리.

> 📋 전체 기획: [PROJECT_PLAN.md](PROJECT_PLAN.md)
> 📺 화면 미리보기: `../commanine_inventory_mockup/mockup.html`

## 빠른 시작

### 1. Supabase 가입 (5분)
[docs/setup_supabase.md](docs/setup_supabase.md) 가이드 참조

### 2. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일 편집 (Supabase URL/Key 입력)
```

### 3. DB 스키마 생성
Supabase SQL Editor에서 `sql/01_schema.sql` 실행

### 4. 마스터 데이터 import
```bash
python scripts/import_master.py
```

### 5. 앱 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

→ http://localhost:8501

## 운영 배포 (Streamlit Cloud)

[docs/setup_streamlit_cloud.md](docs/setup_streamlit_cloud.md) 참조

## 직원 사용 가이드

[docs/employee_guide.md](docs/employee_guide.md) 참조

## 폴더 구조

[PROJECT_PLAN.md §12](PROJECT_PLAN.md#12-폴더-구조-예정) 참조
