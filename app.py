import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import io

# ─── KST 한국 시간 날짜 함수 (YYYY-MM-DD) ──────────────────────────────────
def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")

# ─── 1. 페이지 설정 및 시각적 테마 ──────────────────────────────────────────
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    .metric-card { 
        background: white; padding: 25px; border-radius: 15px; 
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05); border-top: 5px solid #1e3a8a;
        text-align: center;
    }
    .metric-card h3 { color: #1e3a8a !important; font-size: 32px !important; margin: 10px 0 0 0 !important; }
    .metric-card small { color: #64748b; font-size: 16px; font-weight: 600; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    .top-project-table {
        background: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0;
    }
    .edit-panel {
        background: #f0f7ff; border: 1px solid #bfdbfe;
        border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 및 로그인 관리 ─────────────────────────────────────────────
USERS = {"ceo": ("대표님", "defog!ceo"), "leader1": ("김원중 팀장님", "defog!leader1"),
         "leader2": ("김용신 팀장님", "defog!leader2"), "manager": ("팀원", "defog!manager")}

if 'logged_in' not in st.session_state:
    ticket = st.query_params.get("ticket", "")
    for uid in USERS:
        if ticket == f"defog_auth_{uid}_valid":
            st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[uid][0]
            break
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login"):
            u_id, u_pw = st.text_input("ID"), st.text_input("PW", type="password")
            if st.form_submit_button("시스템 접속", use_container_width=True):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[u_id][0]
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

# ─── 3. 데이터베이스 ───────────────────────────────────────────────────────────
DB_PATH = "defog_v33_master.db"
STATUS_LIST = ["🔵 견적(🔥고확률)", "🔵 견적(일반)", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

PRODUCT_COLS = {
    "Racking":  "rack_system",
    "Power":    "power_system",
    "Cooling":  "cooling_system",
    "DCIM":     "snx_spec",
}
PRODUCT_COLORS = {
    "Racking": "#2563eb",
    "Power":   "#f59e0b",
    "Cooling": "#10b981",
    "DCIM":    "#8b5cf6",
}
STATUS_COLORS = {
    "🟢 완료":           "#10b981",
    "🔴 Drop":          "#ef4444",
    "🔵 견적(🔥고확률)": "#2563eb",
    "🔵 견적(일반)":     "#93c5fd",
    "🟡 진행중":         "#facc15",
    "🟠 납품대기중":     "#f97316",
}

# 4대 카테고리 세부 품목 키워드 매핑
ITEM_MAP = {
    "Racking System": {
        "RACK":         ["rack", "h2000", "42u", "프레임"],
        "Containment":  ["containment", "컨테인"],
        "Cable Tray":   ["cable tray", "케이블트레이", "cable"],
        "Ceiling Grid": ["ceiling", "실링", "천장"],
    },
    "Power Solution": {
        "Busway": ["busway", "버스웨이", "380v", "230v"],
        "iPDU":   ["ipdu", "pdu", "raritan", "px4", "px3"],
    },
    "Cooling Solution": {
        "In-Row Cooler":     ["in-row", "inrow", "인로우", "35kw"],
        "Rear Door Cooling": ["rear door", "리어도어", "후면", "90kw"],
        "Chiller":           ["chiller", "칠러"],
    },
    "Management Solution": {
        "DCIM": ["dcim", "snx", "모니터링", "감시"],
    },
}
CAT_COL_MAP = {
    "Racking System":      "rack_system",
    "Power Solution":      "power_system",
    "Cooling Solution":    "cooling_system",
    "Management Solution": "snx_spec",
}
CAT_COLORS = {
    "Racking System":      "#2563eb",
    "Power Solution":      "#f59e0b",
    "Cooling Solution":    "#10b981",
    "Management Solution": "#8b5cf6",
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            sort_order TEXT, division TEXT, quote_date TEXT, pjt_no TEXT,
            company TEXT, pjt_name TEXT, category TEXT, expected_timeline TEXT,
            status TEXT, target_date TEXT, progress TEXT, manager TEXT,
            rack_system TEXT, power_system TEXT, cooling_system TEXT, snx_spec TEXT,
            quantity TEXT, amount INTEGER, client_manager TEXT, key_issue TEXT,
            folder_link TEXT, legrand TEXT, updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_settings (
            key TEXT PRIMARY KEY, value TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_db_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

def get_dash_setting(key, default):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value FROM dashboard_settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return row[0] if row else default
    except: return default

def set_dash_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO dashboard_settings VALUES (?,?)", (key, str(value)))
    conn.commit(); conn.close()

def safe_get(df, keywords, default_val):
    for col in df.columns:
        norm = str(col).lower().replace(' ', '').replace('(', '').replace(')', '').strip()
        for k in keywords:
            if k in norm: return df[col].fillna(default_val)
    return pd.Series([default_val] * len(df))

def clean_status(text):
    text = str(text)
    if "고확률" in text or "🔥" in text: return "🔵 견적(🔥고확률)"
    elif "완료" in text or "🟢" in text: return "🟢 완료"
    elif "대기" in text or "🟠" in text: return "🟠 납품대기중"
    elif "진행" in text or "🟡" in text: return "🟡 진행중"
    elif "Drop" in text or "취소" in text or "🔴" in text: return "🔴 Drop"
    else: return "🔵 견적(일반)"

def parse_progress(val):
    if pd.isna(val) or val == '' or str(val).strip() == '-': return '-'
    val_str = str(val).strip()
    if val_str.endswith('%'): return val_str
    try:
        num = float(val); return f"{int(round(num * 100))}%" if 0.0 <= num <= 1.0 else f"{int(num)}%"
    except: return val_str

def parse_quantity(val):
    if pd.isna(val) or val == '' or str(val).strip() == '-': return '-'
    try:
        num = float(val); return str(int(num)) if num.is_integer() else str(num)
    except: return str(val)

init_db()

# ─── 4. 사이드바 및 네비게이션 ────────────────────────────────────────────────
MENU_1 = "📝 프로젝트 파이프라인 관리"
MENU_2 = "🤝 주간 영업 회의 보드"
MENU_3 = "📊 경영진 성과 대시보드"
MENU_4 = "⚙️ 시스템 및 데이터 관리"

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    menu = st.radio("메뉴 이동", [MENU_1, MENU_2, MENU_3, MENU_4], label_visibility="collapsed")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()
    st.info("🔗 **안전 링크**\n\nhttps://defog-sales-app.streamlit.app/")

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 파이프라인 관리
# ═════════════════════════════════════════════════════════════════════════════
if menu == MENU_1:
    with st.expander("🚀 스마트 신규 프로젝트 직접 등록"):
        with st.form("quick_add"):
            c1, c2, c3, c4 = st.columns(4)
            f_no = c1.text_input("프로젝트 번호")
            f_comp = c2.text_input("수주 업체 *")
            f_name = c3.text_input("프로젝트 명 *")
            f_amt = c4.number_input("수주 금액", min_value=0)
            f_cat = st.selectbox("분류", ["PRODUCT", "SOLUTION"])
            f_stat = st.selectbox("상태", STATUS_LIST)
            f_qty = st.text_input("수량")
            if st.form_submit_button("등록"):
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO projects (pjt_no, company, pjt_name, category, status, quantity, amount, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (f_no, f_comp, f_name, f_cat, f_stat, f_qty, int(f_amt), get_kst_date()))
                conn.commit(); conn.close(); st.rerun()

    df = get_db_data()
    ORDERED_COLS = ["sort_order", "division", "quote_date", "pjt_no", "company", "pjt_name", "category",
                    "expected_timeline", "status", "target_date", "progress", "manager",
                    "rack_system", "power_system", "cooling_system", "snx_spec",
                    "quantity", "amount", "client_manager", "key_issue", "folder_link", "legrand", "updated_at"]
    if df.empty: df = pd.DataFrame(columns=ORDERED_COLS)

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=550,
                               column_order=ORDERED_COLS,
                               column_config={
                                   "amount": st.column_config.NumberColumn("수주 금액", format="%,d"),
                                   "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
                                   "rack_system":    st.column_config.TextColumn("Racking"),
                                   "power_system":   st.column_config.TextColumn("Power"),
                                   "cooling_system": st.column_config.TextColumn("Cooling"),
                                   "snx_spec":       st.column_config.TextColumn("DCIM"),
                               }, key="main_editor")

    if st.button("💾 변경사항 및 삭제 저장"):
        try:
            final_df = edited_df.fillna("-")
            final_df['amount'] = pd.to_numeric(final_df['amount'], errors='coerce').fillna(0).astype(int)
            final_df['updated_at'] = get_kst_date()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close(); st.rerun()
        except Exception as e: st.error(f"저장 오류: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    df_m = get_db_data()
    if not df_m.empty:
        sel_s = st.multiselect("📌 상태 필터", STATUS_LIST, default=STATUS_LIST)
        df_f = df_m[df_m['status'].isin(sel_s)].copy()
        df_f['수주 금액'] = df_f['amount'].apply(lambda x: f"₩ {int(x):,}")
        st.dataframe(df_f[['quote_date', 'status', 'company', 'pjt_name', 'amount', 'key_issue']].sort_values('quote_date', ascending=False), use_container_width=True)
    else: st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_d = get_db_data()

    if df_d.empty:
        st.warning("분석할 데이터가 없습니다. 엑셀을 업로드해 주세요.")
    else:
        # ── 편집 모드 토글 ──────────────────────────────────────────────────
        edit_mode = st.toggle("✏️ 대시보드 편집 모드", value=False)

        # ── 저장된 설정 불러오기 ─────────────────────────────────────────────
        saved_target          = int(get_dash_setting("target_amount",   "50000000000"))
        saved_top_n           = int(get_dash_setting("top_n",           "5"))
        saved_h_title         = get_dash_setting("header_title",        "2026 DEFOG 전사 수주 목표 달성 현황")
        saved_top_title       = get_dash_setting("top_title",           "🏆 주간 집중 관리 대상 (TOP N 대형 프로젝트)")
        saved_show_funnel     = get_dash_setting("show_funnel",         "True") == "True"
        saved_show_bar        = get_dash_setting("show_bar",            "True") == "True"
        saved_show_product    = get_dash_setting("show_product",        "True") == "True"
        saved_show_manager    = get_dash_setting("show_manager",        "True") == "True"
        saved_show_top        = get_dash_setting("show_top",            "True") == "True"
        saved_show_status_pie = get_dash_setting("show_status_pie",     "True") == "True"

        # ── 편집 패널 ────────────────────────────────────────────────────────
        if edit_mode:
            st.markdown("<div class='edit-panel'>", unsafe_allow_html=True)
            st.markdown("#### ⚙️ 대시보드 설정")
            ep1, ep2, ep3 = st.columns(3)
            with ep1:
                new_title  = st.text_input("📌 상단 제목", value=saved_h_title)
                new_target = st.number_input("🎯 연간 수주 목표 (원)", min_value=0,
                                              value=saved_target, step=1_000_000_000)
            with ep2:
                new_top_title = st.text_input("📌 TOP 프로젝트 제목", value=saved_top_title)
                new_top_n     = st.slider("TOP N 표시 수", 3, 20, saved_top_n)
            with ep3:
                st.markdown("**📊 차트 표시 여부**")
                new_show_funnel     = st.checkbox("영업 단계 Funnel",      value=saved_show_funnel)
                new_show_bar        = st.checkbox("사업 분류별 파이프라인", value=saved_show_bar)
                new_show_product    = st.checkbox("4대 제품 포트폴리오",    value=saved_show_product)
                new_show_manager    = st.checkbox("담당자별 파이프라인",    value=saved_show_manager)
                new_show_top        = st.checkbox("TOP 프로젝트 테이블",    value=saved_show_top)
                new_show_status_pie = st.checkbox("상태별 금액 파이",       value=saved_show_status_pie)

            if st.button("💾 설정 저장", type="primary"):
                set_dash_setting("target_amount",   str(new_target))
                set_dash_setting("top_n",           str(new_top_n))
                set_dash_setting("header_title",    new_title)
                set_dash_setting("top_title",       new_top_title)
                set_dash_setting("show_funnel",     str(new_show_funnel))
                set_dash_setting("show_bar",        str(new_show_bar))
                set_dash_setting("show_product",    str(new_show_product))
                set_dash_setting("show_manager",    str(new_show_manager))
                set_dash_setting("show_top",        str(new_show_top))
                set_dash_setting("show_status_pie", str(new_show_status_pie))
                st.success("✅ 저장되었습니다!"); st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
            TARGET = new_target; top_n = new_top_n; h_title = new_title; top_title = new_top_title
            show_funnel = new_show_funnel; show_bar = new_show_bar; show_product = new_show_product
            show_manager = new_show_manager; show_top = new_show_top; show_status_pie = new_show_status_pie
        else:
            TARGET = saved_target; top_n = saved_top_n; h_title = saved_h_title; top_title = saved_top_title
            show_funnel = saved_show_funnel; show_bar = saved_show_bar; show_product = saved_show_product
            show_manager = saved_show_manager; show_top = saved_show_top; show_status_pie = saved_show_status_pie

        # ── 4대 제품 대카테고리 집계 (건수) ──────────────────────────────────
        for col in PRODUCT_COLS.values():
            if col not in df_d.columns: df_d[col] = "-"

        product_rows = []
        for _, row in df_d.iterrows():
            for prod_name, col in PRODUCT_COLS.items():
                val = str(row.get(col, "-")).strip()
                if val and val not in ["-", "", "nan"]:
                    product_rows.append({
                        "product":  prod_name,
                        "status":   row.get("status", "-"),
                        "amount":   int(row.get("amount", 0)),
                        "manager":  row.get("manager", "-"),
                        "company":  row.get("company", "-"),
                        "pjt_name": row.get("pjt_name", "-"),
                    })
        df_product = pd.DataFrame(product_rows) if product_rows else pd.DataFrame(
            columns=["product", "status", "amount", "manager", "company", "pjt_name"])

        # ── 세부 품목 건수 집계 ───────────────────────────────────────────────
        item_rows = []
        for _, row in df_d.iterrows():
            for cat, col in CAT_COL_MAP.items():
                cell_val = str(row.get(col, "-")).lower().strip()
                if not cell_val or cell_val in ["-", "", "nan"]: continue
                matched = False
                for item_name, keywords in ITEM_MAP[cat].items():
                    if any(kw in cell_val for kw in keywords):
                        item_rows.append({"대카테고리": cat, "품목": item_name})
                        matched = True
                        break
                if not matched:
                    item_rows.append({"대카테고리": cat, "품목": "(기타)"})
        df_items = pd.DataFrame(item_rows) if item_rows else pd.DataFrame(columns=["대카테고리", "품목"])

        # ── KPI 계산 ──────────────────────────────────────────────────────────
        won_amt       = df_d[df_d['status'] == "🟢 완료"]['amount'].sum()
        active_amt    = df_d[df_d['status'].isin(["🔵 견적(🔥고확률)", "🔵 견적(일반)", "🟡 진행중", "🟠 납품대기중"])]['amount'].sum()
        drop_amt      = df_d[df_d['status'] == "🔴 Drop"]['amount'].sum()
        high_prob_amt = df_d[df_d['status'] == "🔵 견적(🔥고확률)"]['amount'].sum()

        # ── 헤더 & 달성률 ──────────────────────────────────────────────────────
        st.markdown(f"### 🎖️ {h_title}")
        pct = (won_amt / TARGET * 100) if TARGET > 0 else 0
        col_bar, col_pct = st.columns([8, 2])
        with col_bar: st.progress(min(won_amt / TARGET, 1.0) if TARGET > 0 else 0)
        with col_pct: st.markdown(f"#### **{pct:.1f}%** 달성")

        # ── KPI 카드 ──────────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><small>올해 확정 매출(완료)</small><h3>₩ {won_amt/1e8:.1f}억</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#2563eb;'><small>확보 가망 파이프라인</small><h3>₩ {active_amt/1e8:.1f}억</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>🔥 고확률 견적</small><h3>₩ {high_prob_amt/1e8:.1f}억</h3></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='metric-card' style='border-top-color:#ef4444;'><small>미수주(Drop) 규모</small><h3 style='color:#ef4444 !important;'>₩ {drop_amt/1e8:.1f}억</h3></div>", unsafe_allow_html=True)

        st.markdown("<br><hr>", unsafe_allow_html=True)

        # ── TOP 프로젝트 테이블 ────────────────────────────────────────────────
        if show_top:
            st.markdown(f"### {top_title.replace('N', str(top_n))}")
            df_top = df_d[df_d['status'] != "🟢 완료"].sort_values('amount', ascending=False).head(top_n)
            if not df_top.empty:
                df_top_view = df_top[['company', 'pjt_name', 'status', 'amount', 'manager', 'expected_timeline', 'key_issue']].copy()
                df_top_view['amount'] = df_top_view['amount'].apply(lambda x: f"₩ {int(x):,}")
                df_top_view.columns = ['고객사', '프로젝트명', '상태', '수주금액', '담당자', '예상일정', '핵심이슈']
                st.table(df_top_view.reset_index(drop=True))
            else: st.info("현재 대기중인 프로젝트가 없습니다.")
            st.markdown("<br>", unsafe_allow_html=True)

        # ── 차트 ──────────────────────────────────────────────────────────────
        df_chart = df_d.copy()
        df_chart['금액(억원)'] = df_chart['amount'] / 1e8

        # 행 1: Funnel + 사업분류 Bar
        if show_funnel or show_bar:
            c1, c2 = st.columns(2)
            if show_funnel:
                with c1:
                    fun_df = df_chart.groupby('status')['금액(억원)'].sum().reset_index()
                    order = {"🔵 견적(일반)":0,"🔵 견적(🔥고확률)":1,"🟡 진행중":2,"🟠 납품대기중":3,"🟢 완료":4,"🔴 Drop":5}
                    fun_df['sort'] = fun_df['status'].map(order).fillna(99)
                    fun_df = fun_df.sort_values('sort')
                    fig_fun = px.funnel(fun_df, x='금액(억원)', y='status',
                                        title="💰 영업 단계별 자금 흐름 (Funnel) <br><span style='font-size:13px; color:#64748b;'>* 단위: 억원</span>",
                                        color_discrete_sequence=['#1e3a8a'])
                    fig_fun.update_traces(textinfo="none")
                    st.plotly_chart(fig_fun, use_container_width=True)
            if show_bar:
                with (c2 if show_funnel else c1):
                    fig_bar = px.bar(df_chart, x='category', y='금액(억원)', color='status',
                                     title="🏢 사업 분류별 파이프라인 분포 <br><span style='font-size:13px; color:#64748b;'>* 단위: 억원</span>",
                                     color_discrete_map=STATUS_COLORS, barmode='group')
                    st.plotly_chart(fig_bar, use_container_width=True)

        # 행 2: 4대 제품 포트폴리오(건수) + 상태별 파이
        if show_product or show_status_pie:
            c3, c4 = st.columns(2)

            if show_product:
                with c3:
                    if not df_product.empty:
                        # ── 대카테고리 도넛 (건수 기준) ──────────────────────
                        prod_cnt_sum = df_product.groupby('product').size().reset_index(name='건수')
                        fig_prod = px.pie(
                            prod_cnt_sum, values='건수', names='product',
                            title="📦 4대 제품 포트폴리오 (건수 기준) <br><span style='font-size:13px; color:#64748b;'>Racking / Power / Cooling / DCIM</span>",
                            hole=0.5, color='product', color_discrete_map=PRODUCT_COLORS
                        )
                        fig_prod.update_traces(textinfo='label+percent', textfont_size=13)
                        st.plotly_chart(fig_prod, use_container_width=True)

                        # ── 세부 품목 건수 바 차트 ────────────────────────────
                        if not df_items.empty:
                            item_cnt = df_items.groupby(['대카테고리', '품목']).size().reset_index(name='건수')
                            fig_item = px.bar(
                                item_cnt, x='품목', y='건수', color='대카테고리',
                                title="📋 세부 품목별 건수",
                                color_discrete_map=CAT_COLORS,
                                text='건수'
                            )
                            fig_item.update_traces(textposition='outside')
                            fig_item.update_layout(
                                plot_bgcolor='rgba(0,0,0,0)',
                                xaxis_tickangle=-30,
                                legend_title_text='카테고리'
                            )
                            st.plotly_chart(fig_item, use_container_width=True)

                            # ── 세부 품목 건수 요약 테이블 ────────────────────
                            tbl = df_items.groupby(['대카테고리', '품목']).size().reset_index(name='건수')
                            tbl.columns = ['대카테고리', '품목', '건수']
                            st.markdown("**📋 4대 제품 세부 품목 건수 요약**")
                            st.table(tbl.reset_index(drop=True))
                    else:
                        st.info("Racking / Power / Cooling / DCIM 컬럼에 데이터가 없습니다.")

            if show_status_pie:
                with (c4 if show_product else c3):
                    status_sum = df_d.groupby('status')['amount'].sum().reset_index()
                    status_sum['금액(억원)'] = status_sum['amount'] / 1e8
                    fig_sp = px.pie(status_sum, values='금액(억원)', names='status',
                                    title="🟢 상태별 금액 비중", hole=0.45,
                                    color='status', color_discrete_map=STATUS_COLORS)
                    fig_sp.update_traces(textinfo='label+percent', textfont_size=12)
                    st.plotly_chart(fig_sp, use_container_width=True)

        # 행 3: 담당자별
        if show_manager:
            fig_mgr = px.bar(df_chart[df_chart['status'] != "🔴 Drop"],
                             x='manager', y='금액(억원)', color='status',
                             title="👨‍💼 담당자별 파이프라인 보유 현황 <br><span style='font-size:13px; color:#64748b;'>* 단위: 억원</span>",
                             color_discrete_map=STATUS_COLORS)
            fig_mgr.update_layout(plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_mgr, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 데이터 동기화
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    h_row = st.number_input("📌 헤더 행 번호", min_value=1, value=1)
    f = st.file_uploader("엑셀 선택", type=['xlsx'])
    if f and st.button("동기화"):
        raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')
        mapped = pd.DataFrame()
        mapped["sort_order"]        = safe_get(raw, ['정렬'], '-')
        mapped["division"]          = safe_get(raw, ['구분'], '-')
        mapped["quote_date"]        = safe_get(raw, ['견적일'], get_kst_date()).astype(str).str.split(' ').str[0]
        mapped["pjt_no"]            = safe_get(raw, ['프로젝트번호'], '-')
        mapped["company"]           = safe_get(raw, ['수주업체'], '-')
        mapped["pjt_name"]          = safe_get(raw, ['프로젝트명'], '-')
        mapped["category"]          = safe_get(raw, ['분류'], '기타')
        mapped["expected_timeline"] = safe_get(raw, ['예상일정'], '-')
        mapped["status"]            = safe_get(raw, ['상태'], '🔵 견적(일반)').apply(clean_status)
        mapped["target_date"]       = safe_get(raw, ['목표완료일'], '-')
        mapped["progress"]          = safe_get(raw, ['진행률'], '-').apply(parse_progress)
        mapped["manager"]           = safe_get(raw, ['관리자'], '-')
        mapped["rack_system"]       = safe_get(raw, ['rack', 'racking', '랙'], '-')
        mapped["power_system"]      = safe_get(raw, ['power', '파워', '전원'], '-')
        mapped["cooling_system"]    = safe_get(raw, ['cooling', '쿨링', '냉각'], '-')
        mapped["snx_spec"]          = safe_get(raw, ['snx', 'dcim'], '-')
        mapped["quantity"]          = safe_get(raw, ['수량'], '-').apply(parse_quantity)
        amt_s = safe_get(raw, ['수주금액'], 0)
        if amt_s.dtype == object: amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
        mapped["amount"]            = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
        mapped["client_manager"]    = safe_get(raw, ['업체담당자'], '-')
        mapped["key_issue"]         = safe_get(raw, ['핵심이슈'], '-')
        mapped["folder_link"]       = safe_get(raw, ['폴더'], '-')
        mapped["legrand"]           = safe_get(raw, ['르그랑'], '-')
        mapped["updated_at"]        = get_kst_date()
        conn = sqlite3.connect(DB_PATH)
        mapped.to_sql('projects', conn, if_exists='append', index=False)
        conn.commit(); conn.close(); st.success("동기화 완료!"); st.rerun()
