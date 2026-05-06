"""해외 직구 (배대지) 감지.

3-tier 감지:
1. name_allowlist 정확 매칭 (사용자 분류 95개 명단)
2. forwarder_keywords (회사명) 부분 매칭
3. 영문 이름 + 숫자코드 패턴

반환: True/False — 표시는 단순히 '직구' 한 단어
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "forwarder_dict.json"


@lru_cache(maxsize=1)
def _load_dict() -> dict:
    if not DICT_PATH.exists():
        return {"name_allowlist": [], "address_fingerprints": [], "forwarder_keywords": []}
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _addr_fp(s: str) -> str:
    """Normalize address fingerprint (앞 50자, 공백/특수문자 제거)."""
    s = re.sub(r"[\s,()（）\-_]+", "", s or "")
    return s[:50].lower()


def _norm_name(s: str) -> str:
    return (s or "").strip().lstrip("\t").strip()


def _looks_like_korean_name(name: str) -> bool:
    """한국 일반 성+이름 패턴 (2~4자, 한글)."""
    if not name:
        return False
    if not re.fullmatch(r"[가-힣]{2,4}", name):
        return False
    d = _load_dict()
    surnames = d.get("korean_surnames", "")
    return bool(surnames) and name[0] in surnames


def is_overseas_proxy(receiver_name: str | None, receiver_address: str | None = None) -> bool:
    """주문이 해외 직구 (배대지) 여부.

    True 조건:
      1) 사용자 분류 명단에 정확히 등록된 이름
      2) 주소가 사전에 등록된 배대지 주소와 (앞 30자) 일치
      3) 이름 또는 주소에 명확한 배대지 회사명 (단, 한국 일반인 이름이면 키워드 단독으로 판정 X)
      4) 이름 = 영문+숫자 코드 패턴 (AG무역(BQ131) 같은)
      5) 영문 only 이름 (3자 이상)
    """
    if not receiver_name and not receiver_address:
        return False

    d = _load_dict()
    name = _norm_name(receiver_name or "")
    addr = receiver_address or ""

    # 1) 이름 allowlist (정확 매칭) — 가장 강력한 신호
    if name and name in set(d.get("name_allowlist", [])):
        return True

    # 2) 주소 fingerprint 매칭 — 등록된 배대지 주소
    if addr:
        fp = _addr_fp(addr)
        for known_fp in d.get("address_fingerprints", []):
            if fp == known_fp or (len(fp) >= 30 and fp[:30] == known_fp[:30]):
                return True

    is_korean = _looks_like_korean_name(name)

    # 3) 배대지 회사 키워드 매칭
    #    한국 일반인 이름이면 키워드 매칭은 주소에서만 (이름은 무시 — false positive 방지)
    haystack = addr.lower() if is_korean else (name + " " + addr).lower()
    for kw in d.get("forwarder_keywords", []):
        if len(kw) >= 4 and kw.lower() in haystack:
            return True

    # 4) 패턴: 영문 + 숫자/괄호 코드 (한국 이름에는 안 잡힘)
    if name and not is_korean and re.search(r"[A-Z]{2,}.*[\d()]|[\d()].*[A-Z]{2,}", name):
        return True

    # 5) 영문 only 이름 (3자 이상)
    if name and not is_korean and len(name) >= 3 and re.fullmatch(r"[A-Za-z\s\-_.()0-9]+", name):
        return True

    return False


def stats() -> dict:
    """현재 사전 통계."""
    d = _load_dict()
    return {
        "names": len(d.get("name_allowlist", [])),
        "addresses": len(d.get("address_fingerprints", [])),
        "keywords": len(d.get("forwarder_keywords", [])),
    }
