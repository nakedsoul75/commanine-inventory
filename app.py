"""COMMANINE 재고/주문 통합 관리 — Streamlit 메인 앱."""
from __future__ import annotations

import io
import sys
from pathlib import Path

# UTF-8 stdout (Windows)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.auth import login_screen, logout
from src.db import fetch_all, get_client
from src.mapping import add_manual_mapping
from src.inbound import (
    add_inbound,
    commit_inbound_rows,
    get_recent_inbound,
    parse_inbound_excel,
    preview_inbound_rows,
    search_products,
)
from src.shipments import (
    commit_shipments,
    get_valid_ea_codes,
    parse_shipment_excel,
    preview_shipments,
)

st.set_page_config(
    page_title="COMMANINE 재고/주문",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===== 로그인 =====
user = login_screen()
if not user:
    st.stop()

# ===== 사이드바 =====
with st.sidebar:
    st.markdown(f"### 👤 {user['name']}")
    st.caption(f"역할: {user['role']}")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()

    st.divider()
    page = st.radio(
        "메뉴",
        ["🏠 대시보드", "📦 주문 현황", "📥 입고 등록", "📤 출하 import", "📊 재고", "🔗 매핑 관리"],
        label_visibility="collapsed",
    )

# ===== 페이지 라우팅 =====
client = get_client()


def page_dashboard():
    st.title("🏠 대시보드")
    col1, col2, col3, col4 = st.columns(4)

    # KPIs
    o_total = client.table("orders").select("count", count="exact").limit(0).execute().count or 0
    o_shipped = client.table("orders").select("count", count="exact").limit(0).eq("status", "SHIPPED").execute().count or 0
    o_delayed = client.table("orders").select("count", count="exact").limit(0).eq("status", "DELAYED").execute().count or 0

    inv_low = 0
    try:
        inv_rows = client.table("inventory").select("ea_code,current_stock,stock_status").execute().data
        inv_low = sum(1 for r in inv_rows if r.get("stock_status") == "LOW")
    except Exception:
        pass

    col1.metric("총 주문", f"{o_total:,}건", delta=f"🌏 직구 {o_overseas}건" if o_overseas else None, delta_color="off")
    col2.metric("출하 완료", f"{o_shipped:,}건")
    col3.metric("출하 지연", f"{o_delayed:,}건", delta="확인 필요" if o_delayed else None, delta_color="inverse")
    col4.metric("재고 부족", f"{inv_low:,}개 SKU")

    st.divider()
    st.subheader("최근 주문 10건")
    res = client.table("orders").select("order_date,sub_channel,order_no,product_name,qty,amount,status,ea_code")\
        .order("order_date", desc=True).limit(10).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 주문 데이터가 없습니다.")


def page_orders():
    st.title("📦 주문 현황")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        days = st.selectbox("기간", [1, 3, 7, 14, 30], index=2)
    with col2:
        status_filter = st.selectbox("상태", ["전체", "NEW", "SHIPPED", "DELAYED", "CANCELED"])
    with col3:
        overseas_filter = st.selectbox("직구", ["전체", "🌏 직구만", "일반만"])
    with col4:
        search = st.text_input("🔍 검색 (주문번호/상품명/이지코드)")

    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    q = client.table("orders").select("*").gte("order_date", cutoff).order("order_date", desc=True).limit(500)
    if status_filter != "전체":
        q = q.eq("status", status_filter)
    if overseas_filter == "🌏 직구만":
        q = q.eq("is_overseas_proxy", True)
    elif overseas_filter == "일반만":
        q = q.eq("is_overseas_proxy", False)
    res = q.execute()
    rows = res.data or []
    if search:
        s = search.lower()
        rows = [r for r in rows if s in str(r.get("order_no", "")).lower()
                or s in str(r.get("product_name", "")).lower()
                or s in str(r.get("ea_code", "") or "").lower()]

    overseas_count = sum(1 for r in rows if r.get("is_overseas_proxy"))
    st.caption(f"{len(rows)}건 (🌏 직구 {overseas_count}건)")
    if rows:
        df = pd.DataFrame(rows)
        # Add 직구 indicator column
        if "is_overseas_proxy" in df.columns:
            df["직구"] = df["is_overseas_proxy"].apply(lambda x: "🌏" if x else "")
        cols_show = [c for c in ["order_date", "sub_channel", "order_no", "직구", "ea_code",
                                  "product_name", "option_name", "qty", "amount",
                                  "tracking_no", "status"] if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True, hide_index=True)
    else:
        st.info("조건에 맞는 주문 없음")


def page_shipment_import():
    st.title("📤 출하내역 import")
    st.caption("직원이 카톡으로 보내준 출하내역 엑셀을 업로드하세요. 자동 매칭 + 송장 갱신됩니다.")

    uploaded = st.file_uploader("엑셀 파일 (.xls / .xlsx)", type=["xls", "xlsx"])
    if not uploaded:
        st.info("파일을 업로드하세요.")
        return

    try:
        df = parse_shipment_excel(uploaded)
    except Exception as e:
        st.error(f"엑셀 파싱 실패: {e}")
        return

    st.success(f"✅ {len(df)}행 로드됨")

    if "valid_ea_cache" not in st.session_state:
        with st.spinner("마스터 SKU 캐시 로드..."):
            st.session_state["valid_ea_cache"] = get_valid_ea_codes()
    valid_ea = st.session_state["valid_ea_cache"]

    preview = preview_shipments(df, valid_ea)

    # 검증 결과
    st.subheader("📊 검증 결과")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ 적재 가능", preview["valid"])
    c2.metric("⚠️ 미등록 SKU", preview["unknown_ea"], delta_color="off")
    c3.metric("❌ 필수 누락", preview["missing_required"], delta_color="off")
    c4.metric("총 행", preview["total"])

    with st.expander("채널 분포"):
        for ch, cnt in sorted(preview["by_channel"].items(), key=lambda x: -x[1]):
            st.text(f"  {ch}: {cnt}건")

    if preview["sample_unknown"]:
        with st.expander("⚠️ 미등록 이지어드민 코드 샘플"):
            for s in preview["sample_unknown"]:
                st.text(f"  {s['ea_code']} — {s.get('name', '?')}")

    # 미리보기 테이블
    st.subheader("📋 미리보기 (첫 20행)")
    preview_df = pd.DataFrame(preview["rows"][:20])
    if not preview_df.empty:
        cols = ["row_idx", "ea_code", "sub_channel", "order_no", "tracking", "qty", "product_name", "option"]
        cols = [c for c in cols if c in preview_df.columns]
        st.dataframe(preview_df[cols], use_container_width=True, hide_index=True)

    # 적재
    st.divider()
    if preview["valid"] > 0:
        if st.button(f"💾 {preview['valid']}건 적재 + 매핑 학습 + 송장 매칭", type="primary"):
            with st.spinner("적재 중..."):
                result = commit_shipments(preview["rows"], imported_by=st.session_state["user"]["name"])
            st.success("✅ 완료")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("출하 적재", result["shipments_inserted"])
            r2.metric("매핑 학습", result["mappings_learned"])
            r3.metric("주문↔송장 매칭", result["orders_matched"])
            r4.metric("재매칭", result["orders_rematched"])
            st.session_state.pop("valid_ea_cache", None)
    else:
        st.warning("적재 가능한 행이 없습니다.")


def page_inventory():
    st.title("📊 재고 현황")
    try:
        rows = fetch_all("inventory")
    except Exception as e:
        st.error(f"재고 조회 실패: {e}")
        return

    if not rows:
        st.info("재고 데이터 없음. 입고 등록 + 출하내역 import 후 표시됩니다.")
        return

    df = pd.DataFrame(rows)
    # Filter
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        status_filter = st.selectbox("상태", ["전체", "LOW", "WARN", "OK"])
    with col2:
        sort_by = st.selectbox("정렬", ["current_stock asc (적은 순)", "current_stock desc (많은 순)", "name"])
    with col3:
        search = st.text_input("🔍 검색 (이지코드/품명)")

    if status_filter != "전체":
        df = df[df["stock_status"] == status_filter]
    if search:
        s = search.lower()
        df = df[df.apply(lambda r: s in str(r.get("ea_code", "")).lower()
                                  or s in str(r.get("name", "")).lower(), axis=1)]

    sort_col = "current_stock" if "stock" in sort_by else "name"
    asc = "asc" in sort_by or sort_by == "name"
    df = df.sort_values(sort_col, ascending=asc)

    st.caption(f"{len(df):,}개 SKU")
    cols = ["ea_code", "code", "name", "option_name", "color", "inbound_total", "outbound_total",
            "current_stock", "stock_status", "last_inbound_date", "last_shipment_date"]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True, height=600)


def page_mapping():
    st.title("🔗 매핑 관리")

    tab1, tab2 = st.tabs(["🔴 미매칭 주문", "🟢 학습된 매핑"])

    with tab1:
        st.caption("ea_code = NULL 인 주문. 수동 매핑하면 모든 같은 키 주문 자동 채워집니다.")
        res = client.table("orders").select("id,sub_channel,order_no,product_name,option_name,sku_code,qty,order_date")\
            .is_("ea_code", "null").order("order_date", desc=True).limit(100).execute()
        rows = res.data or []
        st.caption(f"{len(rows)}건 (최근 100건)")
        if not rows:
            st.success("✅ 모든 주문이 매핑되어 있습니다.")
            return

        for r in rows[:30]:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"**{r.get('product_name', '?')}**")
                    st.caption(f"옵션: {r.get('option_name') or '—'}")
                with c2:
                    st.caption(f"채널: {r['sub_channel']}")
                    st.caption(f"주문: {r['order_no']}")
                    st.caption(f"sku: `{r.get('sku_code', '?')}`")
                with c3:
                    new_ea = st.text_input("이지어드민 코드", key=f"ea_{r['id']}",
                                           placeholder="예: 00056")
                    if st.button("💾 저장", key=f"save_{r['id']}", type="primary", use_container_width=True):
                        if new_ea and r.get("sku_code"):
                            ok = add_manual_mapping(r["sub_channel"], r["sku_code"],
                                                    r.get("option_name", "") or "", new_ea.strip())
                            if ok:
                                st.success(f"매핑 추가 + 같은 키 주문 일괄 갱신")
                                st.rerun()
                            else:
                                st.error("저장 실패")
                        else:
                            st.warning("이지어드민 코드 + sku_code 필요")

    with tab2:
        res = client.table("sku_mapping").select("*").order("shipment_count", desc=True).limit(200).execute()
        rows = res.data or []
        st.caption(f"학습된 매핑 {len(rows)}개 (상위 200건)")
        if rows:
            df = pd.DataFrame(rows)
            cols = [c for c in ["sub_channel", "sku_code", "option_norm", "ea_code", "learned_from",
                                 "shipment_count", "last_learned_at"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True, height=500)


def page_inbound():
    st.title("📥 입고 등록")
    tab_single, tab_excel, tab_history = st.tabs(["📝 단건 등록", "📑 엑셀 일괄", "📜 입고 이력"])

    # === 단건 등록 ===
    with tab_single:
        st.caption("이지어드민 코드 또는 품명으로 검색해서 등록하세요.")
        query = st.text_input("🔍 검색", placeholder="예: 00056 또는 r행어 또는 BS-L-50",
                              key="search_q")

        if query:
            results = search_products(query, limit=10)
            if not results:
                st.warning("매칭 없음")
            else:
                # 첫 결과를 기본 선택
                options = [f"{r['ea_code']} | {r.get('name', '')[:30]} {r.get('option_name') or ''}"
                          for r in results]
                idx = st.radio("선택", range(len(options)), format_func=lambda i: options[i], key="prod_sel")
                sel = results[idx]

                st.success(f"**{sel.get('name', '')}** {sel.get('option_name') or ''}")
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"이지어드민: `{sel['ea_code']}`")
                with col2:
                    st.caption(f"품번: `{sel.get('code', '-')}`")

                with st.form("inbound_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        from datetime import date as _date
                        qty = st.number_input("📦 수량", min_value=1, value=1, step=1)
                    with c2:
                        in_date = st.date_input("📅 입고일", value=_date.today())
                    supplier = st.text_input("🏭 공급사", placeholder="예: 제루트")
                    note = st.text_input("📝 비고 (선택)", placeholder="예: 검수 OK")
                    if st.form_submit_button("💾 입고 저장", type="primary", use_container_width=True):
                        result = add_inbound(sel["ea_code"], int(qty), in_date,
                                            supplier or None, note or None,
                                            st.session_state["user"]["name"])
                        if result["ok"]:
                            st.success(f"✅ {result['name']} +{qty}개 등록 완료")
                            st.balloons()
                        else:
                            st.error(result["error"])

    # === 엑셀 일괄 ===
    with tab_excel:
        st.caption("필수 컬럼: 이지어드민코드, 수량 / 선택: 공급사, 입고일, 비고")
        c1, c2 = st.columns(2)
        with c1:
            template = pd.DataFrame([
                {"이지어드민코드": "00056", "수량": 30, "공급사": "제루트", "입고일": "2026-05-02", "비고": "검수 OK"},
                {"이지어드민코드": "00254", "수량": 20, "공급사": "제루트", "입고일": "2026-05-02", "비고": ""},
            ])
            buf = io.BytesIO()
            template.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button("📥 빈 템플릿", buf,
                              file_name="입고_템플릿.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            uploaded = st.file_uploader("엑셀 파일 (.xlsx / .xls)", type=["xlsx", "xls"],
                                        key="inbound_upload")

        if uploaded:
            try:
                df, info = parse_inbound_excel(uploaded)
            except Exception as e:
                st.error(f"파싱 실패: {e}")
                return
            if info["issues"]:
                for i in info["issues"]:
                    st.error(i)
                return

            st.success(f"✅ {info['total_rows']}행 로드")
            with st.spinner("검증 중..."):
                valid_ea = get_valid_ea_codes()
            preview = preview_inbound_rows(df, info["col_map"], valid_ea)

            ok = sum(1 for r in preview if r["status"] == "✅")
            err = len(preview) - ok
            c1, c2 = st.columns(2)
            c1.metric("✅ 등록 가능", ok)
            c2.metric("❌ 오류", err)

            preview_df = pd.DataFrame(preview)
            st.dataframe(preview_df[["row_idx", "ea_code", "qty", "supplier",
                                     "inbound_date", "note", "status"]],
                        use_container_width=True, hide_index=True, height=300)

            if ok > 0:
                if st.button(f"💾 {ok}건 등록", type="primary"):
                    with st.spinner("등록 중..."):
                        result = commit_inbound_rows(preview, st.session_state["user"]["name"])
                    st.success(f"✅ {result['inserted']}건 등록 완료 (오류 {result['errors']})")
                    st.balloons()

    # === 입고 이력 ===
    with tab_history:
        only_mine = st.checkbox("내 입고만", value=False)
        rows = get_recent_inbound(limit=50,
                                 by_user=st.session_state["user"]["name"] if only_mine else None)
        st.caption(f"최근 {len(rows)}건")
        if rows:
            df = pd.DataFrame(rows)
            # Flatten products name
            df["product_name"] = df.apply(
                lambda r: (r.get("products") or {}).get("name") if r.get("products") else "?", axis=1
            )
            cols = ["created_at", "inbound_date", "ea_code", "product_name", "qty",
                   "supplier", "note", "created_by"]
            cols = [c for c in cols if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("이력 없음")


# Routing
if page == "🏠 대시보드":
    page_dashboard()
elif page == "📦 주문 현황":
    page_orders()
elif page == "📥 입고 등록":
    page_inbound()
elif page == "📤 출하 import":
    page_shipment_import()
elif page == "📊 재고":
    page_inventory()
elif page == "🔗 매핑 관리":
    page_mapping()
