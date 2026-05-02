"""
COMMANINE 마스터 데이터 import 스크립트.

기존 commanine_price_tool의 품번기준 엑셀 → Supabase products 테이블.

사용법:
  1. .env 파일에 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, MASTER_EXCEL_PATH 설정
  2. 가상환경/패키지 설치: pip install -r requirements.txt
  3. python scripts/import_master.py

출력:
  - 총 행 수
  - 이지어드민 코드 채워진 비율
  - 빈 코드 행 (수동 보정 필요)
  - upsert 결과
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# UTF-8 output on Windows (cp949 default cannot handle Korean + em-dash)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def main() -> int:
    excel_path = Path(os.environ.get("MASTER_EXCEL_PATH", ""))
    if not excel_path.exists():
        print(f"[ERROR] MASTER_EXCEL_PATH not found: {excel_path}")
        print("Set MASTER_EXCEL_PATH in .env")
        return 1

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print("[ERROR] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing in .env")
        return 1

    try:
        from supabase import create_client
    except ImportError:
        print("[ERROR] supabase package not installed. Run: pip install -r requirements.txt")
        return 1

    print(f"[1/4] Reading Excel: {excel_path.name}")
    # IMPORTANT: dtype=str preserves leading zeros in ea_code ("01130" not 1130.0)
    df = pd.read_excel(excel_path, engine="openpyxl", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    print(f"  Total rows: {len(df)}")
    print(f"  Columns found: {list(df.columns)[:8]}...")

    # Map columns flexibly
    col_map = {}
    for c in df.columns:
        cs = c.strip()
        if "중복" in cs:
            continue
        if cs == "품목코드" and "code" not in col_map:
            col_map["code"] = c
        elif "품목명" in cs and "name" not in col_map:
            col_map["name"] = c
        elif "이지어드민" in cs and "ea_code" not in col_map:
            col_map["ea_code"] = c
        elif "기준" in cs and "판매" in cs and "가격" in cs and "price" not in col_map:
            col_map["price"] = c
        elif cs == "영문" and "eng_name" not in col_map:
            col_map["eng_name"] = c
        elif cs == "비고" and "note" not in col_map:
            col_map["note"] = c

    print(f"\n[2/4] Column mapping detected:")
    for k, v in col_map.items():
        print(f"  {k:12s} ← '{v}'")

    if "ea_code" not in col_map:
        print("[ERROR] '이지어드민' column not found in Excel.")
        return 1

    df = df.rename(columns={v: k for k, v in col_map.items()})

    # Stats — preserve leading zeros + strip
    def normalize_ea(v):
        if v is None or pd.isna(v):
            return ""
        s = str(v).strip()
        if s in ("nan", "#N/A", "None", ""):
            return ""
        # Strip "1130.0" → "1130"
        if s.endswith(".0"):
            s = s[:-2]
        # Zero-pad to 5 chars if all digits and shorter
        if s.isdigit() and len(s) < 5:
            s = s.zfill(5)
        return s
    df["ea_code"] = df["ea_code"].apply(normalize_ea)

    total = len(df)
    has_ea = (df["ea_code"] != "").sum()
    print(f"\n[3/4] Master data quality:")
    print(f"  Total rows: {total}")
    print(f"  이지어드민 코드 채워짐: {has_ea} ({has_ea/total*100:.1f}%)")
    print(f"  빈 이지코드 (제외됨): {total - has_ea}")
    print(f"  샘플 ea_code: {df[df['ea_code']!=''].iloc[0]['ea_code']!r} (5자리 zero-pad 확인)")

    if "is_excluded" not in df.columns:
        if "note" in df.columns:
            df["is_excluded"] = df["note"].apply(lambda x: "제외" in str(x) if pd.notna(x) else False)
        else:
            df["is_excluded"] = False

    # Color: parse from code last segment after "-"
    if "code" in df.columns:
        def parse_color(c):
            if pd.isna(c):
                return None
            parts = str(c).strip().split("-")
            return parts[-1] if len(parts) >= 2 else None
        df["color"] = df["code"].apply(parse_color)
    else:
        df["color"] = None

    # Filter rows with ea_code
    df_valid = df[df["ea_code"] != ""].copy()
    excluded = df_valid[df_valid["is_excluded"] == True]
    if len(excluded) > 0:
        print(f"  '제외' 표시된 행: {len(excluded)} (그래도 import — is_excluded=true)")

    # Build payload
    rows = []
    for _, r in df_valid.iterrows():
        def safe_int(v):
            try:
                if v is None or v == "" or str(v).strip() in ("nan", "#N/A", "None"):
                    return None
                return int(float(v))
            except (ValueError, TypeError):
                return None

        def safe_str(v):
            if v is None:
                return None
            s = str(v).strip()
            return s if s and s not in ("nan", "#N/A", "None") else None

        def safe_bool(v):
            if v is None or pd.isna(v):
                return False
            s = str(v).strip().lower()
            return s in ("true", "1", "yes")

        rows.append({
            "ea_code": str(r["ea_code"]).strip(),
            "code": safe_str(r.get("code")),
            "name": safe_str(r.get("name")) or "(미입력)",
            "option_name": None,
            "price": safe_int(r.get("price")),
            "color": safe_str(r.get("color")),
            "is_excluded": safe_bool(r.get("is_excluded")) if "is_excluded" in r.index else False,
            "eng_name": safe_str(r.get("eng_name")),
            "note": safe_str(r.get("note")),
        })

    # Deduplicate by ea_code (keep first)
    seen = set()
    unique_rows = []
    for row in rows:
        if row["ea_code"] not in seen:
            seen.add(row["ea_code"])
            unique_rows.append(row)
    if len(unique_rows) < len(rows):
        print(f"  중복 제거: {len(rows)} → {len(unique_rows)}")

    print(f"\n[4/4] Upserting to Supabase ({len(unique_rows)} rows)...")
    client = create_client(supabase_url, service_key)

    # Batch upsert (Supabase has request size limits)
    BATCH = 500
    total_upserted = 0
    for i in range(0, len(unique_rows), BATCH):
        chunk = unique_rows[i:i + BATCH]
        try:
            res = client.table("products").upsert(chunk, on_conflict="ea_code").execute()
            total_upserted += len(chunk)
            print(f"  Batch {i//BATCH + 1}: {len(chunk)} rows ✓")
        except Exception as e:
            print(f"  Batch {i//BATCH + 1} FAILED: {e}")
            return 1

    print(f"\n[OK] Imported {total_upserted} products to Supabase.")
    print(f"\nNext: python -c \"from supabase import create_client; import os; from dotenv import load_dotenv; load_dotenv(); c = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY']); print(c.table('products').select('count', count='exact').execute())\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
