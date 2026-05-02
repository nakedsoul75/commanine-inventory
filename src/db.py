"""Supabase 클라이언트 — Streamlit 캐시 활용."""
from __future__ import annotations

import os
from functools import lru_cache

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def _get_secret(key: str) -> str | None:
    """st.secrets 먼저, 없으면 .env."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, Exception):
        pass
    return os.getenv(key)


@st.cache_resource
def get_client() -> Client:
    """Streamlit 세션 동안 같은 클라이언트 재사용."""
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        st.error("Supabase 설정 누락 — .env 또는 .streamlit/secrets.toml 확인")
        st.stop()
    return create_client(url, key)


def fetch_all(table: str, select_cols: str = "*", **filters) -> list[dict]:
    """전체 페이지 자동 fetch (1000개씩)."""
    client = get_client()
    out = []
    page = 0
    while True:
        q = client.table(table).select(select_cols).range(page * 1000, (page + 1) * 1000 - 1)
        for k, v in filters.items():
            q = q.eq(k, v)
        res = q.execute()
        if not res.data:
            break
        out.extend(res.data)
        if len(res.data) < 1000:
            break
        page += 1
    return out
