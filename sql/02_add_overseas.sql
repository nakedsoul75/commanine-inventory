-- ============================================================
-- 02. 해외 직구 (배대지) 감지 컬럼 추가
-- ============================================================
-- Supabase SQL Editor에서 실행
-- ============================================================

-- orders 테이블 — 수령자 정보 + 직구 플래그
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS receiver_name TEXT,
    ADD COLUMN IF NOT EXISTS receiver_address TEXT,
    ADD COLUMN IF NOT EXISTS is_overseas_proxy BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_orders_overseas ON orders(is_overseas_proxy)
    WHERE is_overseas_proxy = TRUE;

-- shipments 테이블 — 수령자 주소 + 직구 플래그
ALTER TABLE shipments
    ADD COLUMN IF NOT EXISTS receiver_address TEXT,
    ADD COLUMN IF NOT EXISTS is_overseas_proxy BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_shipments_overseas ON shipments(is_overseas_proxy)
    WHERE is_overseas_proxy = TRUE;

SELECT 'Migration 02 complete' AS status;
