"""직원 PIN 로그인."""
from __future__ import annotations

import bcrypt
import streamlit as st

from src.db import get_client


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except Exception:
        return False


def list_active_users() -> list[dict]:
    client = get_client()
    res = client.table("users").select("name, role").eq("is_active", True).execute()
    return res.data or []


def authenticate(name: str, pin: str) -> dict | None:
    client = get_client()
    res = client.table("users").select("*").eq("name", name).eq("is_active", True).limit(1).execute()
    if not res.data:
        return None
    user = res.data[0]
    if not verify_pin(pin, user["pin_hash"]):
        return None
    # Touch last_login_at
    try:
        from datetime import datetime
        client.table("users").update({"last_login_at": datetime.now().isoformat()}).eq("id", user["id"]).execute()
    except Exception:
        pass
    return {"id": user["id"], "name": user["name"], "role": user["role"]}


def login_screen() -> dict | None:
    """로그인 UI. 로그인 성공 시 user dict 반환, 실패 시 None."""
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    st.title("📦 콤마나인 재고/주문 시스템")
    st.markdown("##### 로그인")

    users = list_active_users()
    if not users:
        st.warning("등록된 사용자가 없습니다. `python scripts/create_admin.py` 실행하세요.")
        st.stop()

    with st.form("login"):
        col1, col2 = st.columns([2, 1])
        with col1:
            name = st.selectbox("이름", [u["name"] for u in users])
        with col2:
            pin = st.text_input("PIN (4자리)", type="password", max_chars=4)

        if st.form_submit_button("🔐 로그인", type="primary", use_container_width=True):
            if not pin or len(pin) != 4:
                st.error("PIN 4자리를 입력하세요.")
                return None
            user = authenticate(name, pin)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("PIN이 틀렸습니다.")
    return None


def logout():
    if "user" in st.session_state:
        del st.session_state["user"]
    st.rerun()
