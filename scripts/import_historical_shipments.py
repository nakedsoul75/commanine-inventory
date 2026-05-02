"""
과거 출하내역 일괄 import 스크립트.

지정 폴더에서 "출하내역" 패턴의 엑셀 파일 모두 찾아서:
  1. shipments 테이블에 적재 (이미 있는 송장은 skip)
  2. sku_mapping 테이블에 자동 학습 (sub_channel + sku_code + option → ea_code)

CS 출하내역은 다른 양식(CJ 송장 양식)이라 스킵.

사용법:
  python scripts/import_historical_shipments.py [폴더경로]

기본 폴더: C:\\Users\\naked\\Documents\\카카오톡 받은 파일
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from datetime import datetime

# UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Channel name normalization (출하내역 판매처 → 우리 sub_channel)
CHANNEL_MAP = {
    "카페24 (자사몰)": "자사몰",
    "카페24 (사업자몰)": "사업자몰",
    "스마트스토어": "콤마캠핑",
    "스토어팜": "콤마캠핑",
    "CS(수동)": "수동",
    "CS (수동)": "수동",
}


def normalize_option(s: str) -> str:
    """옵션 정규화: 소문자 + 공백/특수문자 제거 → 매핑 안정화."""
    if not s or pd.isna(s):
        return ""
    s = str(s).strip().lower()
    return re.sub(r"[\s\-/()\[\]:=,'\"`+_]+", "", s)


def normalize_name(s: str) -> str:
    """상품명 정규화."""
    if not s or pd.isna(s):
        return ""
    s = str(s).strip().lower()
    return re.sub(r"[\s\-/()\[\]★,.'\"`+_!?]+", "", s)


def normalize_ea_code(v):
    """5자리 zero-pad."""
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if s in ("nan", "#N/A", "None", ""):
        return None
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and len(s) < 5:
        s = s.zfill(5)
    return s


def parse_dt(v):
    """엑셀 timestamp → ISO."""
    if v is None or pd.isna(v) or str(v).strip() in ("", "nan", "NaT"):
        return None
    try:
        if isinstance(v, str):
            return pd.to_datetime(v).isoformat()
        return v.isoformat() if hasattr(v, "isoformat") else str(v)
    except Exception:
        return None


def is_shipment_file(name: str) -> bool:
    """파일명이 일반 출하내역인지 (CS 제외)."""
    name_low = name.lower()
    if "출하내역" not in name:
        return False
    if "cs" in name_low:
        return False
    if not name_low.endswith((".xls", ".xlsx")):
        return False
    return True


def main() -> int:
    folder_arg = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\naked\Documents\카카오톡 받은 파일"
    folder = Path(folder_arg)
    if not folder.exists():
        print(f"[ERROR] 폴더 없음: {folder}")
        return 1

    files = sorted([f for f in folder.iterdir() if is_shipment_file(f.name)])
    if not files:
        print(f"[INFO] 출하내역 파일 없음 in {folder}")
        return 0

    print(f"=== 발견된 일반 출하내역 ({len(files)}개) ===")
    for f in files:
        print(f"  • {f.name}  ({f.stat().st_size:,} bytes)")
    print()

    # Supabase
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("[ERROR] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing in .env")
        return 1
    client = create_client(url, key)

    # Load existing products to validate ea_codes
    print("Loading products master...")
    all_products = []
    page = 0
    while True:
        res = client.table("products").select("ea_code").range(page * 1000, (page + 1) * 1000 - 1).execute()
        if not res.data:
            break
        all_products.extend([r["ea_code"] for r in res.data])
        if len(res.data) < 1000:
            break
        page += 1
    valid_ea_codes = set(all_products)
    print(f"  {len(valid_ea_codes):,}개 SKU loaded\n")

    # Stats
    total_rows = 0
    total_inserted_ship = 0
    total_skipped_ship = 0
    total_mappings_added = 0
    total_unknown_ea = 0
    channel_counts = {}

    for f in files:
        print(f"=== Processing {f.name} ===")
        try:
            df = pd.read_excel(f, dtype=str)
            df.columns = [c.strip() for c in df.columns]
        except Exception as e:
            print(f"  ERROR reading: {e}")
            continue

        rows = len(df)
        total_rows += rows
        ship_rows = []
        mapping_rows = []
        unknown_in_file = 0

        for _, r in df.iterrows():
            ea_code = normalize_ea_code(r.get("상품코드"))
            sku_code = r.get("판매처 상품코드")
            order_no = r.get("주문번호")
            tracking = r.get("송장번호")
            channel_raw = r.get("판매처") or ""
            qty_raw = r.get("주문수량") or r.get("상품수량") or "1"
            option_raw = r.get("판매처 옵션") or r.get("옵션명") or ""
            product_name = r.get("상품명")
            receiver = r.get("수령자이름")
            shipped_at = parse_dt(r.get("송장입력일") or r.get("배송일"))
            courier = r.get("택배사")

            try:
                qty = int(float(qty_raw)) if qty_raw and not pd.isna(qty_raw) else 1
            except (ValueError, TypeError):
                qty = 1

            sub_channel = CHANNEL_MAP.get(str(channel_raw).strip(), str(channel_raw).strip() or None)
            channel_counts[sub_channel or "?"] = channel_counts.get(sub_channel or "?", 0) + 1

            # Validate ea_code
            if ea_code and ea_code not in valid_ea_codes:
                unknown_in_file += 1
                ea_code = None  # NULL로 적재 (FK 위반 방지)

            # Shipment record
            if ea_code and tracking and order_no:
                ship_rows.append({
                    "order_no": str(order_no).strip(),
                    "ea_code": ea_code,
                    "qty": qty,
                    "tracking_no": str(tracking).strip(),
                    "courier": str(courier).strip() if courier and not pd.isna(courier) else None,
                    "receiver_name": str(receiver).strip() if receiver and not pd.isna(receiver) else None,
                    "shipped_at": shipped_at,
                    "sub_channel": sub_channel,
                    "sku_code": str(sku_code).strip() if sku_code and not pd.isna(sku_code) else None,
                    "raw_product_name": str(product_name).strip() if product_name and not pd.isna(product_name) else None,
                    "raw_option_name": str(option_raw).strip() if option_raw and not pd.isna(option_raw) else None,
                    "imported_by": "historical_import",
                })

            # Mapping learning — 두 가지 키 동시 학습
            # (a) sku_code 기반 (출하내역의 판매처 상품코드)
            # (b) name 기반 (상품명 정규화) — 카페24/스마트스토어 응답이 sku_code 안 줄 때 fallback
            if ea_code and sub_channel:
                option_norm = normalize_option(option_raw)
                # (a) sku_code 매핑
                if sku_code and not pd.isna(sku_code):
                    mapping_rows.append({
                        "sub_channel": sub_channel,
                        "sku_code": str(sku_code).strip(),
                        "option_norm": option_norm,
                        "ea_code": ea_code,
                        "learned_from": "shipment",
                        "confidence": 100,
                        "shipment_count": 1,
                        "last_learned_at": datetime.now().isoformat(),
                    })
                # (b) name 매핑 (sku_code 필드에 "name:" 접두사로 저장)
                # 출하내역의 "판매처 상품명" 우선, 없으면 "상품명"
                seller_name = r.get("판매처 상품명") or r.get("상품명")
                if seller_name and not pd.isna(seller_name):
                    name_norm = normalize_name(seller_name)
                    if name_norm:
                        mapping_rows.append({
                            "sub_channel": sub_channel,
                            "sku_code": "name:" + name_norm,
                            "option_norm": option_norm,
                            "ea_code": ea_code,
                            "learned_from": "shipment",
                            "confidence": 100,
                            "shipment_count": 1,
                            "last_learned_at": datetime.now().isoformat(),
                        })

        # Upsert shipments (UNIQUE constraint will skip duplicates)
        ship_inserted = 0
        ship_skipped = 0
        if ship_rows:
            BATCH = 200
            for i in range(0, len(ship_rows), BATCH):
                chunk = ship_rows[i:i + BATCH]
                try:
                    res = client.table("shipments").upsert(
                        chunk, on_conflict="tracking_no,ea_code,qty"
                    ).execute()
                    ship_inserted += len(res.data) if res.data else 0
                except Exception as e:
                    msg = str(e)[:100]
                    print(f"  shipment batch err: {msg}")

        # Upsert mappings (UNIQUE constraint handles dedup, increment count)
        mapping_added = 0
        if mapping_rows:
            # Group by (sub_channel, sku_code, option_norm)
            seen = {}
            for m in mapping_rows:
                key = (m["sub_channel"], m["sku_code"], m["option_norm"])
                if key not in seen:
                    seen[key] = m
                else:
                    seen[key]["shipment_count"] += 1
            unique_maps = list(seen.values())

            BATCH = 200
            for i in range(0, len(unique_maps), BATCH):
                chunk = unique_maps[i:i + BATCH]
                try:
                    res = client.table("sku_mapping").upsert(
                        chunk, on_conflict="sub_channel,sku_code,option_norm"
                    ).execute()
                    mapping_added += len(res.data) if res.data else 0
                except Exception as e:
                    msg = str(e)[:100]
                    print(f"  mapping batch err: {msg}")

        total_inserted_ship += ship_inserted
        total_mappings_added += mapping_added
        total_unknown_ea += unknown_in_file
        print(f"  rows={rows}  shipments+={ship_inserted}  mappings+={mapping_added}  unknown_ea={unknown_in_file}")

    # Final summary
    print()
    print("=" * 60)
    print("=== 최종 요약 ===")
    print(f"  처리 파일       : {len(files)}개")
    print(f"  총 행          : {total_rows:,}")
    print(f"  shipments 적재 : {total_inserted_ship:,}건 (중복 제외)")
    print(f"  매핑 학습      : {total_mappings_added:,}개 (unique)")
    print(f"  마스터 미등록 SKU: {total_unknown_ea}건 (NULL로 처리)")
    print()
    print("  채널별 분포:")
    for ch, cnt in sorted(channel_counts.items(), key=lambda x: -x[1]):
        print(f"    {ch:15s}  {cnt:,}건")

    # Verify
    print()
    print("=== Supabase 최종 상태 ===")
    s_count = client.table("shipments").select("count", count="exact").limit(0).execute().count
    m_count = client.table("sku_mapping").select("count", count="exact").limit(0).execute().count
    print(f"  shipments  : {s_count:,}건")
    print(f"  sku_mapping: {m_count:,}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
