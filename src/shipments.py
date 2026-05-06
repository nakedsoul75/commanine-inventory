"""출하내역 엑셀 import 로직."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.db import fetch_all, get_client
from src.mapping import normalize_name, normalize_option, upsert_mapping

CHANNEL_MAP = {
    "카페24 (자사몰)": "자사몰",
    "카페24 (사업자몰)": "사업자몰",
    "스마트스토어": "콤마캠핑",
    "스토어팜": "콤마캠핑",
    "CS(수동)": "수동",
    "CS (수동)": "수동",
}


def normalize_ea(v):
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
    if v is None or pd.isna(v) or str(v).strip() in ("", "nan", "NaT"):
        return None
    try:
        if isinstance(v, str):
            return pd.to_datetime(v).isoformat()
        return v.isoformat() if hasattr(v, "isoformat") else str(v)
    except Exception:
        return None


def safe_str(v):
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    return s if s and s not in ("nan", "#N/A", "None") else None


def get_valid_ea_codes() -> set[str]:
    """마스터의 모든 ea_code 캐시."""
    rows = fetch_all("products", "ea_code")
    return {r["ea_code"] for r in rows}


def parse_shipment_excel(file) -> pd.DataFrame:
    """업로드된 엑셀 → DataFrame. 컬럼 검증."""
    df = pd.read_excel(file, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    required = ["상품코드", "주문번호"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")
    return df


def preview_shipments(df: pd.DataFrame, valid_ea_codes: set[str]) -> dict[str, Any]:
    """파싱 + 검증 (DB 적재 X). 결과만 반환."""
    rows = []
    unknown_ea = 0
    by_channel = {}
    sample_unknown = []

    for idx, r in df.iterrows():
        ea_code = normalize_ea(r.get("상품코드"))
        sku_code = safe_str(r.get("판매처 상품코드"))
        order_no = safe_str(r.get("주문번호"))
        tracking = safe_str(r.get("송장번호"))
        channel_raw = str(r.get("판매처") or "").strip()
        qty_raw = r.get("주문수량") or r.get("상품수량") or "1"
        option = safe_str(r.get("판매처 옵션") or r.get("옵션명"))
        product_name = safe_str(r.get("상품명"))
        seller_name = safe_str(r.get("판매처 상품명")) or product_name
        receiver = safe_str(r.get("수령자이름"))
        receiver_addr = safe_str(r.get("수령자주소"))
        shipped_at = parse_dt(r.get("송장입력일") or r.get("배송일"))
        courier = safe_str(r.get("택배사"))

        try:
            qty = int(float(qty_raw)) if qty_raw and not pd.isna(qty_raw) else 1
        except (ValueError, TypeError):
            qty = 1

        sub_channel = CHANNEL_MAP.get(channel_raw, channel_raw or None)
        by_channel[sub_channel or "?"] = by_channel.get(sub_channel or "?", 0) + 1

        valid_ea = ea_code and ea_code in valid_ea_codes
        if ea_code and not valid_ea:
            unknown_ea += 1
            if len(sample_unknown) < 5:
                sample_unknown.append({"ea_code": ea_code, "name": product_name})

        rows.append({
            "row_idx": int(idx) + 2,  # excel row (1-based + header)
            "ea_code": ea_code if valid_ea else None,
            "ea_unknown": ea_code and not valid_ea,
            "sku_code": sku_code,
            "order_no": order_no,
            "tracking": tracking,
            "courier": courier,
            "sub_channel": sub_channel,
            "qty": qty,
            "option": option,
            "product_name": product_name,
            "seller_name": seller_name,
            "receiver": receiver,
            "receiver_address": receiver_addr,
            "shipped_at": shipped_at,
        })

    return {
        "rows": rows,
        "total": len(rows),
        "valid": sum(1 for r in rows if r["ea_code"] and r["tracking"] and r["order_no"]),
        "unknown_ea": unknown_ea,
        "missing_required": sum(1 for r in rows if not (r["tracking"] and r["order_no"])),
        "by_channel": by_channel,
        "sample_unknown": sample_unknown,
    }


def commit_shipments(rows: list[dict], imported_by: str) -> dict:
    """미리보기 통과한 행을 DB에 적재 + 매핑 학습 + orders 송장 매칭."""
    client = get_client()

    # 1. shipments 테이블 적재 (직구 감지 포함)
    try:
        from src import forwarder
    except ImportError:
        forwarder = None

    ship_rows = []
    mapping_rows = []
    for r in rows:
        if not (r["ea_code"] and r["tracking"] and r["order_no"]):
            continue
        is_overseas = False
        if forwarder:
            is_overseas = forwarder.is_overseas_proxy(r["receiver"], r.get("receiver_address"))
        ship_rows.append({
            "order_no": r["order_no"],
            "ea_code": r["ea_code"],
            "qty": r["qty"],
            "tracking_no": r["tracking"],
            "courier": r["courier"],
            "receiver_name": r["receiver"],
            "receiver_address": r.get("receiver_address"),
            "is_overseas_proxy": is_overseas,
            "shipped_at": r["shipped_at"],
            "sub_channel": r["sub_channel"],
            "sku_code": r["sku_code"],
            "raw_product_name": r["seller_name"],
            "raw_option_name": r["option"],
            "imported_by": imported_by,
        })
        # mapping (a) sku_code
        if r["sub_channel"] and r["sku_code"]:
            mapping_rows.append({
                "sub_channel": r["sub_channel"],
                "sku_code": r["sku_code"],
                "option_norm": normalize_option(r["option"]),
                "ea_code": r["ea_code"],
                "learned_from": "shipment",
                "confidence": 100,
                "shipment_count": 1,
                "last_learned_at": datetime.now().isoformat(),
            })
        # mapping (b) name
        if r["sub_channel"] and r["seller_name"]:
            name_n = normalize_name(r["seller_name"])
            if name_n:
                mapping_rows.append({
                    "sub_channel": r["sub_channel"],
                    "sku_code": "name:" + name_n,
                    "option_norm": normalize_option(r["option"]),
                    "ea_code": r["ea_code"],
                    "learned_from": "shipment",
                    "confidence": 100,
                    "shipment_count": 1,
                    "last_learned_at": datetime.now().isoformat(),
                })

    # Dedup ship_rows by UNIQUE key
    seen = set()
    unique_ship = []
    for s in ship_rows:
        k = (s["tracking_no"], s["ea_code"], s["qty"])
        if k not in seen:
            seen.add(k)
            unique_ship.append(s)

    inserted_ship = 0
    BATCH = 200
    for i in range(0, len(unique_ship), BATCH):
        chunk = unique_ship[i:i + BATCH]
        try:
            res = client.table("shipments").upsert(chunk, on_conflict="tracking_no,ea_code,qty").execute()
            inserted_ship += len(res.data) if res.data else 0
        except Exception as e:
            print(f"shipments err: {str(e)[:200]}")

    # 2. 매핑 학습
    learned = upsert_mapping(mapping_rows)

    # 3. orders 매칭 — order_no + ea_code 일치하는 NULL 송장 채우기
    matched_orders = 0
    for s in unique_ship:
        try:
            res = client.table("orders").update({
                "tracking_no": s["tracking_no"],
                "courier": s["courier"],
                "shipped_at": s["shipped_at"],
                "status": "SHIPPED",
            }).eq("order_no", s["order_no"]).eq("ea_code", s["ea_code"])\
              .is_("tracking_no", "null").execute()
            matched_orders += len(res.data) if res.data else 0
        except Exception as e:
            print(f"orders match err: {str(e)[:100]}")

    # 4. UNMAPPED orders 재매칭 시도 (새로 학습된 매핑으로)
    rematched = 0
    for m in mapping_rows[:100]:  # 너무 많으면 부담 → 100개만
        try:
            res = client.table("orders").update({"ea_code": m["ea_code"]})\
                .is_("ea_code", "null").eq("sub_channel", m["sub_channel"])
            if not m["sku_code"].startswith("name:"):
                res = res.eq("sku_code", m["sku_code"])
            res = res.execute()
            rematched += len(res.data) if res.data else 0
        except Exception:
            pass

    return {
        "shipments_inserted": inserted_ship,
        "mappings_learned": learned,
        "orders_matched": matched_orders,
        "orders_rematched": rematched,
    }
