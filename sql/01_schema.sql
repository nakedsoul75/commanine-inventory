-- ============================================================
-- COMMANINE 재고/주문 통합 관리 시스템 — DB 스키마
-- ============================================================
-- 사용법: Supabase 대시보드 → SQL Editor → 이 파일 전체 복사 → Run
-- ============================================================

-- 0. 확장 (UUID 등 필요 시)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. products (마스터 — price_tool 엑셀에서 import)
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    ea_code         TEXT PRIMARY KEY,           -- 이지어드민 코드 (마스터키)
    code            TEXT,                        -- 자체 품번 (C01-A-04)
    barcode         TEXT,                        -- CMM900056
    name            TEXT NOT NULL,
    option_name     TEXT,
    price           INTEGER,
    color           TEXT,                        -- 코드 끝자리 (00=무블, 50=스텐 등)
    is_excluded     BOOLEAN DEFAULT FALSE,
    eng_name        TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_code ON products(code);

-- ============================================================
-- 2. orders (주문 — daily-report 봇이 자동 적재)
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    id              BIGSERIAL PRIMARY KEY,
    channel         TEXT NOT NULL,               -- 'cafe24' | 'smartstore'
    sub_channel     TEXT,                        -- '자사몰' | '사업자몰' | '콤마캠핑'
    order_no        TEXT NOT NULL,               -- 20260502-0193
    ea_code         TEXT REFERENCES products(ea_code),  -- NULL이면 unmapped
    product_name    TEXT,
    option_name     TEXT,
    sku_code        TEXT,                        -- 판매처 상품코드 (688-000E)
    qty             INTEGER NOT NULL,
    amount          INTEGER,                     -- 매출 (실 주문가)
    cash_paid       INTEGER,                     -- 실 카드결제
    buyer_name      TEXT,                        -- 마스킹된 이름
    order_date      TIMESTAMPTZ NOT NULL,

    -- 배송 정보 (출하내역 import 후 채워짐)
    tracking_no     TEXT,
    courier         TEXT,
    shipped_at      TIMESTAMPTZ,

    -- 상태
    status          TEXT DEFAULT 'NEW',          -- NEW | SHIPPED | DELAYED | CANCELED
    is_first_order  BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(channel, order_no, sku_code, qty)
);

CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_ea_code ON orders(ea_code);
CREATE INDEX IF NOT EXISTS idx_orders_unmapped
    ON orders(channel, sku_code, option_name)
    WHERE ea_code IS NULL;

-- ============================================================
-- 3. shipments (출하 — 엑셀 import)
-- ============================================================
CREATE TABLE IF NOT EXISTS shipments (
    id              BIGSERIAL PRIMARY KEY,
    order_no        TEXT NOT NULL,
    ea_code         TEXT REFERENCES products(ea_code),
    qty             INTEGER NOT NULL,
    tracking_no     TEXT,
    courier         TEXT,                        -- CJ대한통운
    receiver_name   TEXT,
    shipped_at      TIMESTAMPTZ,
    sub_channel     TEXT,                        -- 자사몰/사업자몰/스토어
    sku_code        TEXT,                        -- 판매처 상품코드 (매핑 학습용)
    raw_product_name TEXT,                       -- 출하내역 엑셀의 원본 상품명
    raw_option_name  TEXT,
    imported_at     TIMESTAMPTZ DEFAULT NOW(),
    imported_by     TEXT,
    UNIQUE(tracking_no, ea_code, qty)
);

CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_no);
CREATE INDEX IF NOT EXISTS idx_shipments_ea_code ON shipments(ea_code);

-- ============================================================
-- 4. inbound (입고 — 직원 등록)
-- ============================================================
CREATE TABLE IF NOT EXISTS inbound (
    id              BIGSERIAL PRIMARY KEY,
    ea_code         TEXT NOT NULL REFERENCES products(ea_code),
    qty             INTEGER NOT NULL CHECK (qty > 0),
    inbound_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    supplier        TEXT,
    note            TEXT,
    photo_url       TEXT,
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inbound_date ON inbound(inbound_date DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_ea_code ON inbound(ea_code);

-- ============================================================
-- 5. sku_mapping (매핑 학습 — 자동 + 수동)
-- ============================================================
CREATE TABLE IF NOT EXISTS sku_mapping (
    id              BIGSERIAL PRIMARY KEY,
    sub_channel     TEXT NOT NULL,               -- 자사몰/사업자몰/콤마캠핑
    sku_code        TEXT NOT NULL,               -- 판매처 상품코드
    option_norm     TEXT,                        -- 정규화된 옵션
    ea_code         TEXT NOT NULL REFERENCES products(ea_code),
    learned_from    TEXT DEFAULT 'shipment',     -- shipment | manual | override
    confidence      INTEGER DEFAULT 100,         -- 자동=100, 수동=200
    shipment_count  INTEGER DEFAULT 0,
    last_learned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sub_channel, sku_code, option_norm)
);

CREATE INDEX IF NOT EXISTS idx_mapping_lookup
    ON sku_mapping(sub_channel, sku_code, option_norm);

-- ============================================================
-- 6. users (직원)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    pin_hash        TEXT NOT NULL,               -- bcrypt hash of 4-digit PIN
    role            TEXT DEFAULT 'staff',        -- 'admin' | 'staff'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

-- ============================================================
-- 7. inventory_view (자동 계산)
-- ============================================================
CREATE OR REPLACE VIEW inventory AS
SELECT
    p.ea_code,
    p.code,
    p.barcode,
    p.name,
    p.option_name,
    p.color,
    p.price,
    COALESCE(in_total.qty, 0) AS inbound_total,
    COALESCE(out_total.qty, 0) AS outbound_total,
    COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) AS current_stock,
    CASE
        WHEN COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) <= 5 THEN 'LOW'
        WHEN COALESCE(in_total.qty, 0) - COALESCE(out_total.qty, 0) <= 10 THEN 'WARN'
        ELSE 'OK'
    END AS stock_status,
    in_total.last_inbound_date,
    out_total.last_shipment_date
FROM products p
LEFT JOIN (
    SELECT ea_code, SUM(qty) qty, MAX(inbound_date) last_inbound_date
    FROM inbound GROUP BY ea_code
) in_total USING (ea_code)
LEFT JOIN (
    SELECT ea_code, SUM(qty) qty, MAX(shipped_at::date) last_shipment_date
    FROM shipments GROUP BY ea_code
) out_total USING (ea_code)
WHERE p.is_excluded = FALSE;

-- ============================================================
-- 8. orders_dashboard (대시보드용 뷰)
-- ============================================================
CREATE OR REPLACE VIEW orders_dashboard AS
SELECT
    o.*,
    p.name AS master_name,
    p.option_name AS master_option,
    CASE
        WHEN o.status = 'CANCELED' THEN 'CANCELED'
        WHEN o.tracking_no IS NOT NULL THEN 'SHIPPED'
        WHEN o.order_date < NOW() - INTERVAL '5 days' THEN 'DELAYED'
        ELSE 'NEW'
    END AS computed_status
FROM orders o
LEFT JOIN products p ON o.ea_code = p.ea_code;

-- ============================================================
-- 9. RLS (Row Level Security) — 추후 활성화
-- ============================================================
-- ALTER TABLE inbound ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE shipments ENABLE ROW LEVEL SECURITY;
-- (현재는 모든 직원이 모든 데이터 조회 가능)

-- ============================================================
-- 완료
-- ============================================================
SELECT 'Schema created successfully' AS status;
