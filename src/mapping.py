"""매핑 학습 + 검색 + 관리."""
from __future__ import annotations

import re
from datetime import datetime

from src.db import get_client


def normalize_option(s) -> str:
    if s is None or str(s).strip() in ("", "nan", "None"):
        return ""
    return re.sub(r"[\s\-/()\[\]:=,'\"`+_]+", "", str(s).lower())


def normalize_name(s) -> str:
    if s is None or str(s).strip() in ("", "nan", "None"):
        return ""
    return re.sub(r"[\s\-/()\[\]★,.'\"`+_!?]+", "", str(s).lower())


def upsert_mapping(rows: list[dict]) -> int:
    """sku_mapping batch upsert. UNIQUE(sub_channel, sku_code, option_norm)."""
    if not rows:
        return 0
    # Dedup within batch
    seen = {}
    for m in rows:
        key = (m["sub_channel"], m["sku_code"], m.get("option_norm", ""))
        if key not in seen:
            seen[key] = m
        else:
            seen[key]["shipment_count"] = seen[key].get("shipment_count", 1) + 1
    unique = list(seen.values())

    client = get_client()
    inserted = 0
    BATCH = 200
    for i in range(0, len(unique), BATCH):
        chunk = unique[i:i + BATCH]
        try:
            res = client.table("sku_mapping").upsert(
                chunk, on_conflict="sub_channel,sku_code,option_norm"
            ).execute()
            inserted += len(res.data) if res.data else 0
        except Exception as e:
            print(f"mapping upsert err: {str(e)[:200]}")
    return inserted


def lookup(sub_channel: str, sku_code: str | None, option: str | None, name: str | None = None) -> str | None:
    """4-strategy lookup → ea_code or None."""
    client = get_client()
    opt_n = normalize_option(option)
    name_n = normalize_name(name) if name else ""

    if sku_code:
        for opt_try in [opt_n, ""]:
            res = client.table("sku_mapping").select("ea_code").eq("sub_channel", sub_channel)\
                .eq("sku_code", str(sku_code).strip()).eq("option_norm", opt_try).limit(1).execute()
            if res.data:
                return res.data[0]["ea_code"]
    if name_n:
        for opt_try in [opt_n, ""]:
            res = client.table("sku_mapping").select("ea_code").eq("sub_channel", sub_channel)\
                .eq("sku_code", "name:" + name_n).eq("option_norm", opt_try).limit(1).execute()
            if res.data:
                return res.data[0]["ea_code"]
    return None


def add_manual_mapping(sub_channel: str, sku_code: str, option: str, ea_code: str) -> bool:
    """수동 매핑 추가 (confidence=200, learned_from='manual')."""
    client = get_client()
    try:
        client.table("sku_mapping").upsert({
            "sub_channel": sub_channel,
            "sku_code": str(sku_code).strip(),
            "option_norm": normalize_option(option),
            "ea_code": ea_code,
            "learned_from": "manual",
            "confidence": 200,
            "shipment_count": 0,
            "last_learned_at": datetime.now().isoformat(),
        }, on_conflict="sub_channel,sku_code,option_norm").execute()

        # Re-process unmapped orders with this key
        client.table("orders").update({"ea_code": ea_code, "status": "NEW"})\
            .is_("ea_code", "null").eq("sub_channel", sub_channel)\
            .eq("sku_code", str(sku_code).strip()).execute()
        return True
    except Exception as e:
        print(f"add_manual_mapping err: {e}")
        return False
