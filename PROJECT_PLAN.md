# COMMANINE 재고/주문 통합 관리 시스템 — 프로젝트 계획서

> 작성일: 2026-05-02
> 위치: `C:\Users\naked\Documents\agent\commanine_inventory\`
> 미리보기: `C:\Users\naked\Documents\agent\commanine_inventory_mockup\mockup.html`
> 기존 봇: `C:\Users\naked\Documents\agent\daily-order-report\` (운영 중)

---

## 1. 배경

### 현재 운영 중인 시스템
- **daily-order-report 봇**: 카페24 + 스마트스토어 주문을 매일 3회(08:30/12:30/18:00) 카톡 발송
- 위치: `C:\Users\naked\Documents\agent\daily-order-report\`
- 상태: 라이브 운영 중 (Windows 작업 스케줄러)

### 기존 commanine_price_tool
- 위치: `C:\Users\naked\Documents\agent\claude\commanine_price_tool\`
- 기능: 자연어 품명 검색 + 다품목 견적 + 마스터 엑셀 직접 수정
- 마스터 데이터: `data/품번기준_*.xlsx`
- **이지어드민 코드 컬럼 보유** ← 새 시스템의 마스터키 소스

### 기존 워크플로우 빈틈
| 단계 | 현재 | 문제 |
|---|---|---|
| 입고 | 현물 수령, 눈으로 확인 | ❌ 전산화 X — 재고 정확도 무너짐 |
| 재고 | 이지어드민에 수동 등록 | 🟡 분산 |
| 출고 | 이지어드민이 자동 차감 | ✅ |
| 배송 | 이지어드민에 송장번호 수동 입력 | 🟡 분산 |
| 출하 보고 | 직원이 매일 카톡으로 출하내역 엑셀 발송 | 🟡 사람이 봐야 함 |

---

## 2. 새 시스템 목적

1. **입고 전산화**: 직원이 폰 또는 PC에서 즉시 등록
2. **출하 자동 매칭**: 직원의 출하내역 엑셀을 시스템에 업로드하면 주문번호↔송장번호 자동 매칭
3. **출하 지연 자동 감지**: 5일+ 미출하 RED 표시 + 카톡 알림
4. **재고 실시간 추적**: 입고 - 출하 = 현재 재고 (이지어드민 코드별)
5. **모든 매칭 = 이지어드민 코드 (마스터키)**

---

## 3. 결정된 사양

### 결정 사항
- **호스팅**: Supabase (PostgreSQL 무료) + Streamlit Cloud (무료)
- **DB**: NAS 사용 안 함 → 클라우드 (Supabase)
- **마스터키**: 이지어드민 상품 코드 (반드시)
- **사용자**: 본인 + 직원 (모두 동일 권한, ②③번 답변)
- **인증**: 이름 선택 + PIN 4자리 (간단)
- **출하 처리 방식**: 본인이 받은 엑셀을 웹앱에 업로드 (옵션 ②-A)
- **기존 price_tool과 분리**: 별도 신규 앱 (옵션 ③)
- **매핑 방식**: 옵션 D — 출하내역 자동 학습 (수동 보완 가능)

### 비즈니스 룰 (기본값으로 진행, 운영 중 조정)
- 출하내역: 매일 그날치 (직원 발송분)
- 5일 지연 기준: **주문일 + 5 달력일** (주말/공휴일 미구분)
- 부분 출하: orders ↔ shipments 1:N 지원
- 취소: 회색 표시 + 지연 체크 제외
- 권한: 본인 + 직원 동일
- 신상품: 출하내역 첫 import 시 자동 매핑 학습
- 재고 실사: 월 1회 화면에서 수동 보정

### 입고 등록 옵션
- **단건**: 폰에서 검색 → 수량 → 저장 (3초)
- **일괄**: PC에서 엑셀 템플릿 다운로드 → 작성 → 업로드 → 자동 검증 → 적재

---

## 4. 시스템 아키텍처

```
[데이터 소스]
   카페24 자사몰      카페24 사업자몰     스마트스토어 콤마캠핑
        │                  │                    │
        └──────────────────┴────────────────────┘
                           ▼
              [daily-report 봇] (기존, Day 2에 수정)
                           │
                           ▼
                      Supabase orders 테이블
                           ▲
                           │
   ┌───────────────────────┼─────────────────────────┐
   │                       │                         │
[직원 폰/PC]          [직원 PC]                 [본인 PC]
입고 등록             출하 import (엑셀)         관리/조회
   │                  │                         │
   ▼                  ▼                         ▼
inbound 테이블     shipments 테이블          모든 테이블
                   + mapping 학습
                   + orders 송장 매칭
                           │
                           ▼
                   재고 = inbound 합 - shipments 합
                           │
                           ▼
                   카톡 알림 (일일/지연/재고부족)
```

### 호스팅
- **Supabase** (https://supabase.com): PostgreSQL DB + 인증 + Storage (무료 500MB)
- **Streamlit Cloud** (https://streamlit.io/cloud): Streamlit 앱 호스팅 (Public 레포 무료)
- **GitHub**: 소스 코드 관리 (Public 레포 — 시크릿은 별도)
- **기존 daily-report**: 그대로 유지 + Supabase 적재 코드만 추가

---

## 5. DB 스키마

### products (마스터)
```sql
CREATE TABLE products (
    ea_code TEXT PRIMARY KEY,        -- 이지어드민 코드 (마스터키)
    code TEXT,                       -- 자체 품번 (C01-A-04)
    barcode TEXT,                    -- CMM900056
    name TEXT NOT NULL,
    option_name TEXT,
    price INTEGER,
    color TEXT,                      -- 코드 끝자리 (00=무블, 50=스텐 등)
    is_excluded BOOLEAN DEFAULT FALSE,
    eng_name TEXT,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### orders (주문 — daily-report bot이 자동 적재)
```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,           -- 'cafe24' | 'smartstore'
    sub_channel TEXT,                -- '자사몰' | '사업자몰' | '콤마캠핑'
    order_no TEXT NOT NULL,          -- 주문번호 (20260502-0193)
    ea_code TEXT REFERENCES products,-- 이지어드민 코드 (NULL이면 unmapped)
    product_name TEXT,               -- 매칭 안 됐을 때 검색용
    option_name TEXT,
    sku_code TEXT,                   -- 판매처 상품코드 (688-000E)
    qty INTEGER NOT NULL,
    amount INTEGER,                  -- 매출 (실 주문가)
    cash_paid INTEGER,               -- 실 카드결제
    buyer_name TEXT,                 -- 마스킹된 이름
    order_date TIMESTAMPTZ NOT NULL,

    -- 배송 정보 (출하내역 import 후 채워짐)
    tracking_no TEXT,
    courier TEXT,
    shipped_at TIMESTAMPTZ,

    -- 상태
    status TEXT DEFAULT 'NEW',       -- NEW | SHIPPED | DELAYED | CANCELED
    is_first_order BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel, order_no, COALESCE(ea_code, ''), qty)
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_ea_code ON orders(ea_code);
CREATE INDEX idx_orders_unmapped ON orders(channel, sku_code, option_name) WHERE ea_code IS NULL;
```

### shipments (출하 — 엑셀 import)
```sql
CREATE TABLE shipments (
    id BIGSERIAL PRIMARY KEY,
    order_no TEXT NOT NULL,
    ea_code TEXT REFERENCES products,
    qty INTEGER NOT NULL,
    tracking_no TEXT NOT NULL,
    courier TEXT,                    -- CJ대한통운
    receiver_name TEXT,
    shipped_at TIMESTAMPTZ,
    sub_channel TEXT,                -- 자사몰/사업자몰/스토어
    sku_code TEXT,                   -- 판매처 상품코드 (매핑 학습용)
    raw_product_name TEXT,           -- 출하내역 엑셀의 원본 상품명
    raw_option_name TEXT,
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    imported_by TEXT,
    UNIQUE(tracking_no, ea_code, qty)
);

CREATE INDEX idx_shipments_order ON shipments(order_no);
```

### inbound (입고 — 직원 등록)
```sql
CREATE TABLE inbound (
    id BIGSERIAL PRIMARY KEY,
    ea_code TEXT NOT NULL REFERENCES products,
    qty INTEGER NOT NULL CHECK (qty > 0),
    inbound_date DATE NOT NULL DEFAULT CURRENT_DATE,
    supplier TEXT,
    note TEXT,
    photo_url TEXT,
    created_by TEXT,                 -- 직원 이름
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_inbound_date ON inbound(inbound_date);
CREATE INDEX idx_inbound_ea_code ON inbound(ea_code);
```

### sku_mapping (매핑 학습 — 자동 + 수동)
```sql
CREATE TABLE sku_mapping (
    id BIGSERIAL PRIMARY KEY,
    sub_channel TEXT NOT NULL,       -- 자사몰/사업자몰/콤마캠핑
    sku_code TEXT NOT NULL,          -- 판매처 상품코드
    option_norm TEXT,                -- 정규화된 옵션 (소문자, 공백 제거)
    ea_code TEXT NOT NULL REFERENCES products,
    learned_from TEXT,               -- 'shipment' | 'manual' | 'override'
    confidence INTEGER DEFAULT 100,  -- 자동=100, 수동=200 (수동이 우선)
    shipment_count INTEGER DEFAULT 0,
    last_learned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sub_channel, sku_code, option_norm)
);

CREATE INDEX idx_mapping_lookup ON sku_mapping(sub_channel, sku_code);
```

### users (직원)
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    pin_hash TEXT NOT NULL,          -- bcrypt hash of 4-digit PIN
    role TEXT DEFAULT 'staff',       -- 'admin' | 'staff'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### inventory (자동 계산 VIEW)
```sql
CREATE VIEW inventory AS
SELECT
    p.ea_code,
    p.code,
    p.barcode,
    p.name,
    p.option_name,
    p.color,
    COALESCE(in_total.qty, 0) AS inbound_total,
    COALESCE(out_total.qty, 0) AS outbound_total,
    COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) AS current_stock,
    CASE
        WHEN COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) <= 5 THEN 'LOW'
        WHEN COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) <= 10 THEN 'WARN'
        ELSE 'OK'
    END AS stock_status
FROM products p
LEFT JOIN (
    SELECT ea_code, SUM(qty) qty FROM inbound GROUP BY ea_code
) in_total USING (ea_code)
LEFT JOIN (
    SELECT ea_code, SUM(qty) qty FROM shipments GROUP BY ea_code
) out_total USING (ea_code);
```

---

## 6. 매핑 학습 시스템 (옵션 D)

### 동작 원리

**STEP 1. 새 주문 들어옴**
- daily-report bot이 카페24/스마트스토어 응답에서 (channel, sku_code, option) 추출
- `sku_mapping` 테이블 검색
- 발견 → `orders.ea_code` 채움
- 못 찾음 → `orders.ea_code = NULL` (UNMAPPED)

**STEP 2. 출하내역 엑셀 import**
- 직원이 매일 받은 출하내역 엑셀 업로드
- 각 행: `(sub_channel, 판매처상품코드, 판매처옵션, 이지어드민 상품코드)`
- `sku_mapping` 테이블 자동 갱신
- `shipments` 테이블 적재
- **UNMAPPED 큐 재처리**: NULL 상태 orders를 재매칭

**STEP 3. 누적 효과**
- 1일차: 0% → 1주차: ~95% → 1개월: ~99%
- **첫날부터 95%로 시작하려면**: 과거 1-2개월치 출하내역 일괄 import (1회 30분)

### 옵션 비교 (D 채택 이유)

| 항목 | A (자동) | B (수동 5-10시간) | **D (출하 학습) ⭐** |
|---|---|---|---|
| 초기 작업 | 0 | 5-10시간 | **30분 (과거 import)** |
| 첫날 매칭률 | 0% | 100% | **~95%** |
| 1주일 후 | ~80% | 100% | **~99%** |
| 신상품 | 자동 (학습) | 수동 추가 필요 | **자동** |
| 유지보수 | 자동 | 신상품마다 수동 | **자동** |

---

## 7. 화면 구성 (전체)

미리보기: `commanine_inventory_mockup/mockup.html`

| # | 화면 | 디바이스 | 사용자 |
|---|---|---|---|
| 1 | 메인 대시보드 | PC | 본인 |
| 2 | 주문 현황 (지연 RED) | PC | 본인 |
| 3 | 출하내역 import | PC | 본인 |
| 4 | 재고 현황 | PC + 폰 | 본인 + 직원 |
| 5 | 입고 등록 (단건) | 폰 | 직원 |
| 5b | 입고 등록 (엑셀 일괄) | PC | 본인 + 직원 |
| 6 | 카톡 알림 (3종) | 폰 | 본인 |
| 7 | 매핑 학습 + 관리 | PC | 본인 |

---

## 8. 카톡 알림 (3종)

기존 daily-report 봇 확장:
1. **매일 18:00 일일 통합 리포트**: 주문/매출/출하/지연/재고 요약 + URL
2. **매일 09:00 출하 지연 알림**: 5일+ 미출하 건 (있을 때만)
3. **매일 09:30 재고 부족 알림**: 5개 이하 SKU + 발주 권장량

---

## 9. 단계별 구현 (5일)

| Day | 작업 | 산출물 |
|---|---|---|
| **Day 1** | Supabase 셋업 + 스키마 SQL 실행 + 마스터 import + 직원 로그인 | DB 준비 + products 156개 적재 |
| **Day 2** | daily-report bot 수정: 주문 → Supabase orders 적재 (매핑 검색 포함) | 주문 자동 수집 시작 |
| **Day 3** | Streamlit: 출하 import + 매핑 학습 + 송장 매칭 + 재고 갱신 | 출하 자동 처리 |
| **Day 4** | 출하 지연 감지 (5일+) + RED 표시 + 카톡 알림 | 지연 알림 자동 |
| **Day 5** | 입고 등록 (폰 + PC 엑셀) + 재고 화면 + Streamlit Cloud 배포 | 직원 폰 접근 가능 |

---

## 10. 기술 스택

- **언어**: Python 3.13
- **웹 프레임워크**: Streamlit (모바일 친화)
- **DB**: Supabase PostgreSQL (무료 티어, 500MB)
- **호스팅**: Streamlit Community Cloud (무료, Public GitHub 레포)
- **인증**: 이름 + PIN 4자리 (bcrypt)
- **카톡**: 기존 daily-report 봇 재사용
- **Git**: GitHub Public 레포 (시크릿은 Streamlit Secrets)

---

## 11. 환경 변수 (.env)

```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...        # public, 클라이언트용
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...# secret, 서버용 (admin 작업)

# Streamlit Cloud는 .streamlit/secrets.toml 사용
```

---

## 12. 폴더 구조 (예정)

```
commanine_inventory/
├── PROJECT_PLAN.md              ← 이 문서
├── README.md
├── app.py                       ← Streamlit 메인 앱
├── requirements.txt
├── .env.example
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── src/
│   ├── db.py                    ← Supabase 클라이언트
│   ├── auth.py                  ← 직원 로그인 (PIN)
│   ├── mapping.py               ← 매핑 학습 + 검색
│   ├── shipments.py             ← 출하 import
│   ├── inbound.py               ← 입고 등록
│   ├── inventory.py             ← 재고 조회/계산
│   ├── orders.py                ← 주문 조회
│   └── notifications.py         ← 카톡 발송 (기존 봇 연동)
├── sql/
│   ├── 01_schema.sql            ← 테이블 생성
│   ├── 02_views.sql             ← 뷰 + 인덱스
│   └── 03_seed.sql              ← 초기 데이터 (직원, 등)
├── scripts/
│   ├── import_master.py         ← price_tool 엑셀 → products
│   ├── import_historical_shipments.py ← 과거 출하내역 일괄 import
│   └── sync_orders_from_bot.py  ← 기존 봇 데이터 백필
└── docs/
    ├── setup_supabase.md
    ├── setup_streamlit_cloud.md
    └── employee_guide.md        ← 직원용 사용 가이드
```

---

## 13. 위험 요소 + 대응

| 위험 | 대응 |
|---|---|
| Supabase 7일 비활성 sleep | 매일 ping (cron) — 실제로 매일 사용하면 자동 해결 |
| Streamlit Cloud Public 레포 시크릿 노출 | `.gitignore` + Streamlit Secrets로 분리 |
| 직원 PIN 분실 | 본인이 admin 화면에서 PIN 재설정 |
| 출하내역 엑셀 형식 변경 | 컬럼명 매핑 유연화 + 검증 화면에서 사용자 보정 |
| price_tool 엑셀 이지어드민 코드 빈 값 | import 시 빈 값 검출 → 보고 → 수동 채움 |
| 송장번호 중복 import | UNIQUE(tracking_no, ea_code, qty) 제약 |
| 카페24 매핑 학습 전 주문 누락 | UNMAPPED 큐 보관 + 출하내역 import 시 재처리 |

---

## 14. 향후 확장 (Phase 2+)

- CJ대한통운 API 연동 (송장 자동 추적, 배송 상태 자동 업데이트)
- 일/주/월 매출 트렌드 차트
- 베스트셀러/데드스톡 분석
- 발주 자동 추천 (평균 일일 출하량 × 리드타임)
- 환불/취소 처리 화면
- 정기 재고 실사 모드 (실재고 입력 → 자동 보정)
- 이지어드민 API 연동 (옵션, 월 20만원)

---

## 15. 진행 현황

- ✅ 2026-05-02: 미리보기 화면 7종 완성 + 사용자 승인
- ⏳ Day 1: Supabase 셋업 + 스키마 + 마스터 import (진행 중)
- ⏸ Day 2~5: 대기

---

**다음 단계**: `docs/setup_supabase.md` 가이드대로 Supabase 가입 → URL/Key 발급 후 알림 → 스키마 자동 실행
