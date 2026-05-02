"""입고 등록 — 단건 + 엑셀 일괄."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from src.db import get_client


def search_products(query: str, limit: int = 10) -> list[dict]:
    """검색: 이지코드 / 품번 / 품명 일치."""
    if not query or len(query.strip()) < 1:
        return []
    client = get_client()
    q = query.strip()

    # 1) 이지코드 정확
    res = client.table("products").select("ea_code,code,name,option_name,color,price")\
        .eq("ea_code", q).limit(1).execute()
    if res.data:
        return res.data

    # 2) 이지코드 like
    res = client.table("products").select("ea_code,code,name,option_name,color,price")\
        .ilike("ea_code", f"%{q}%").limit(limit).execute()
    by_ea = res.data or []

    # 3) 품번 like
    res = client.table("products").select("ea_code,code,name,option_name,color,price")\
        .ilike("code", f"%{q}%").limit(limit).execute()
    by_code = res.data or []

    # 4) 품명 like
    res = client.table("products").select("ea_code,code,name,option_name,color,price")\
        .ilike("name", f"%{q}%").limit(limit).execute()
    by_name = res.data or []

    # 합치기 (중복 제거 — ea_code 기준, 우선순위: ea > code > name)
    seen = set()
    out = []
    for source in (by_ea, by_code, by_name):
        for r in source:
            if r["ea_code"] not in seen:
                seen.add(r["ea_code"])
                out.append(r)
                if len(out) >= limit:
                    return out
    return out


def add_inbound(
    ea_code: str,
    qty: int,
    inbound_date: date,
    supplier: str | None,
    note: str | None,
    created_by: str,
) -> dict:
    """단건 입고 등록."""
    client = get_client()

    # ea_code 검증
    chk = client.table("products").select("ea_code,name").eq("ea_code", ea_code).limit(1).execute()
    if not chk.data:
        return {"ok": False, "error": f"이지어드민 코드 '{ea_code}'가 마스터에 없습니다."}

    if qty <= 0:
        return {"ok": False, "error": "수량은 1 이상"}

    try:
        res = client.table("inbound").insert({
            "ea_code": ea_code,
            "qty": int(qty),
            "inbound_date": inbound_date.isoformat(),
            "supplier": supplier,
            "note": note,
            "created_by": created_by,
        }).execute()
        return {"ok": True, "id": res.data[0]["id"], "name": chk.data[0]["name"]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def parse_inbound_excel(file) -> tuple[pd.DataFrame, dict]:
    """엑셀 → DataFrame + 검증 결과."""
    df = pd.read_excel(file, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    # 컬럼 매핑 (유연)
    col_map = {}
    for c in df.columns:
        cs = c.strip().lower()
        if "이지" in c or "ea_code" in cs or cs == "ea":
            col_map.setdefault("ea_code", c)
        elif cs == "수량" or "qty" in cs or "quantity" in cs:
            col_map.setdefault("qty", c)
        elif "공급" in c or "supplier" in cs:
            col_map.setdefault("supplier", c)
        elif "입고일" in c or cs == "date":
            col_map.setdefault("inbound_date", c)
        elif "비고" in c or "note" in cs or "memo" in cs:
            col_map.setdefault("note", c)
        elif "품명" in c or cs == "name":
            col_map.setdefault("name_check", c)

    issues = []
    if "ea_code" not in col_map:
        issues.append("'이지어드민코드' 또는 'ea_code' 컬럼 필수")
    if "qty" not in col_map:
        issues.append("'수량' 컬럼 필수")

    return df, {"col_map": col_map, "issues": issues, "total_rows": len(df)}


def preview_inbound_rows(df: pd.DataFrame, col_map: dict, valid_ea_codes: set[str]) -> list[dict]:
    """각 행 검증 (DB 적재 X)."""
    rows = []
    for idx, r in df.iterrows():
        ea_raw = r.get(col_map.get("ea_code", ""))
        if pd.isna(ea_raw) or str(ea_raw).strip() in ("", "nan"):
            ea = ""
        else:
            ea = str(ea_raw).strip()
            if ea.endswith(".0"):
                ea = ea[:-2]
            if ea.isdigit() and len(ea) < 5:
                ea = ea.zfill(5)

        qty_raw = r.get(col_map.get("qty", ""))
        try:
            qty = int(float(qty_raw)) if qty_raw and not pd.isna(qty_raw) else 0
        except (ValueError, TypeError):
            qty = 0

        supplier = r.get(col_map.get("supplier", "")) if "supplier" in col_map else None
        note = r.get(col_map.get("note", "")) if "note" in col_map else None
        date_raw = r.get(col_map.get("inbound_date", "")) if "inbound_date" in col_map else None
        try:
            inbound_dt = pd.to_datetime(date_raw).date() if date_raw and not pd.isna(date_raw) else date.today()
        except Exception:
            inbound_dt = date.today()
        name_check = r.get(col_map.get("name_check", "")) if "name_check" in col_map else None

        # Validation
        if not ea:
            status = "❌ 이지코드 없음"
        elif ea not in valid_ea_codes:
            status = "❌ 미등록 코드"
        elif qty <= 0:
            status = "❌ 수량 오류"
        else:
            status = "✅"

        rows.append({
            "row_idx": int(idx) + 2,
            "ea_code": ea,
            "qty": qty,
            "supplier": str(supplier).strip() if supplier and not pd.isna(supplier) else None,
            "note": str(note).strip() if note and not pd.isna(note) else None,
            "inbound_date": inbound_dt,
            "name_check": str(name_check).strip() if name_check and not pd.isna(name_check) else None,
            "status": status,
        })
    return rows


def commit_inbound_rows(rows: list[dict], created_by: str) -> dict:
    """검증 통과한 행만 inbound 테이블에 적재."""
    client = get_client()
    valid = [r for r in rows if r["status"] == "✅"]
    if not valid:
        return {"inserted": 0, "errors": 0}

    payload = [{
        "ea_code": r["ea_code"],
        "qty": r["qty"],
        "inbound_date": r["inbound_date"].isoformat() if hasattr(r["inbound_date"], "isoformat") else str(r["inbound_date"]),
        "supplier": r["supplier"],
        "note": r["note"],
        "created_by": created_by,
    } for r in valid]

    inserted = 0
    errors = 0
    BATCH = 200
    for i in range(0, len(payload), BATCH):
        chunk = payload[i:i + BATCH]
        try:
            res = client.table("inbound").insert(chunk).execute()
            inserted += len(res.data) if res.data else 0
        except Exception as e:
            errors += len(chunk)
            print(f"inbound batch err: {str(e)[:200]}")
    return {"inserted": inserted, "errors": errors}


def get_recent_inbound(limit: int = 20, by_user: str | None = None) -> list[dict]:
    client = get_client()
    q = client.table("inbound").select("*, products(name)").order("created_at", desc=True).limit(limit)
    if by_user:
        q = q.eq("created_by", by_user)
    res = q.execute()
    return res.data or []
