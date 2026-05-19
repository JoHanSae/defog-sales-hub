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
    
    /* 브리핑용 TOP 5 테이블 스타일 */
    .top-project-table {
        background: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0;
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

# ─── 3. 데이터베이스 (v33 master 버전 유지) ──────────────────────────────────
DB_PATH = "defog_v33_master.db"
STATUS_LIST = ["🔵 견적(🔥고확률)", "🔵 견적(일반)", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

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
    conn.close()

def get_db_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

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
            f_no, f_comp, f_name, f_amt = c1.text_input("프로젝트 번호"), c2.text_input("수주 업체 *"), c3.text_input("프로젝트 명 *"), c4.number_input("수주 금액", min_value=0)
            f_cat, f_stat, f_qty = st.selectbox("분류", ["PRODUCT", "SOLUTION"]), st.selectbox("상태", STATUS_LIST), st.text_input("수량")
            if st.form_submit_button("등록"):
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO projects (pjt_no, company, pjt_name, category, status, quantity, amount, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                            (f_no, f_comp, f_name, f_cat, f_stat, f_qty, int(f_amt), get_kst_date()))
                conn.commit(); conn.close(); st.rerun()

    df = get_db_data()
    ORDERED_COLS = ["sort_order", "division", "quote_date", "pjt_no", "company", "pjt_name", "category", "expected_timeline", "status", "target_date", "progress", "manager", "rack_system", "power_system", "cooling_system", "snx_spec", "quantity", "amount", "client_manager", "key_issue", "folder_link", "legrand", "updated_at"]
    if df.empty: df = pd.DataFrame(columns=ORDERED_COLS)
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=550, column_order=ORDERED_COLS,
                               column_config={"amount": st.column_config.NumberColumn("수주 금액", format="%,d"), "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST)}, key="main_editor")
    
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
        df_f = df_m[df_m['status'].isin(sel_s)]
        df_f['수주 금액'] = df_f['amount'].apply(lambda x: f"₩ {int(x):,}")
        st.dataframe(df_f[['quote_date', 'status', 'company', 'pjt_name', 'amount', 'key_issue']].sort_values('quote_date', ascending=False), use_container_width=True)
    else: st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드 (⭐ V34 브리핑 특화 고도화 영역)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_d = get_db_data()
    if df_d.empty:
        st.warning("분석할 데이터가 없습니다. 엑셀을 업로드해 주세요.")
    else:
        # 1. 상단 브리핑 핵심 요약 (KPI)
        TARGET = 50000000000
        won_amt = df_d[df_d['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_d[df_d['status'].isin(["🔵 견적(🔥고확률)", "🔵 견적(일반)", "🟡 진행중", "🟠 납품대기중"])]['amount'].sum()
        drop_amt = df_d[df_d['status'] == "🔴 Drop"]['amount'].sum()
        
        st.markdown(f"### 🎖️ 2026 DEFOG 전사 수주 목표 달성 현황")
        
        # 목표 달성률 프리미엄 게이지 바
        pct = (won_amt / TARGET) * 100
        cols_gauge = st.columns([8, 2])
        with cols_gauge[0]:
            st.progress(min(won_amt / TARGET, 1.0))
        with cols_gauge[1]:
            st.markdown(f"#### **{pct:.1f}%** 달성")

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><small>올해 확정 매출(완료)</small><h3>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#3b82f6;'><small>확보 가망 파이프라인</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#eab308;'><small>전체 등록 건수</small><h3>{len(df_d)} 건</h3></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='metric-card' style='border-top-color:#ef4444;'><small>미수주(Drop) 규모</small><h3 style='color:#ef4444 !important;'>₩ {drop_amt:,}</h3></div>", unsafe_allow_html=True)

        st.markdown("<br><hr>", unsafe_allow_html=True)

        # 2. 브리핑의 꽃: TOP 5 Must-Win 프로젝트 (대형 건)
        st.markdown("### 🏆 주간 집중 관리 대상 (TOP 5 대형 프로젝트)")
        df_top = df_d[df_d['status'] != "🟢 완료"].sort_values('amount', ascending=False).head(5)
        if not df_top.empty:
            df_top_view = df_top[['company', 'pjt_name', 'status', 'amount', 'manager', 'expected_timeline']]
            df_top_view.columns = ['고객사', '프로젝트명', '상태', '수주금액(원)', '관리자', '예상일정']
            st.table(df_top_view.reset_index(drop=True))
        else:
            st.info("현재 대기중인 프로젝트가 없습니다.")

        st.markdown("<br>", unsafe_allow_html=True)

        # 3. 정밀 시각화 레이아웃 (2x2 Grid)
        c1, c2 = st.columns(2)
        
        with c1:
            # 파이프라인 건전성 (퍼널)
            fun_df = df_d.groupby('status')['amount'].sum().reset_index()
            order = {"🔵 견적(일반)":0, "🔵 견적(🔥고확률)":1, "🟡 진행중":2, "🟠 납품대기중":3, "🟢 완료":4, "🔴 Drop":5}
            fun_df['sort'] = fun_df['status'].map(order).fillna(99)
            fun_df = fun_df.sort_values('sort')
            fig_fun = px.funnel(fun_df, x='amount', y='status', title="💰 영업 단계별 자금 흐름 (Funnel)",
                                color_discrete_sequence=['#1e3a8a'])
            st.plotly_chart(fig_fun, use_container_width=True)

        with c2:
            # 분류별/상태별 분석
            fig_bar = px.bar(df_d, x='category', y='amount', color='status', 
                             title="🏢 사업 분류별 파이프라인 분포",
                             color_discrete_map={"🟢 완료":"#10b981", "🔴 Drop":"#ef4444", "🔵 견적(🔥고확률)":"#2563eb", "🔵 견적(일반)":"#93c5fd", "🟡 진행중":"#facc15", "🟠 납품대기중":"#f97316"},
                             barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)

        c3, c4 = st.columns(2)

        with c3:
            # 인프라 믹스 분석 (Racking, Power, Cooling 등 제안 비중)
            # '-'가 아닌 실제 텍스트가 있는 경우를 카운트
            infra_counts = {
                "Rack": len(df_d[df_d['rack_system'] != "-"]),
                "Power": len(df_d[df_d['power_system'] != "-"]),
                "Cooling": len(df_d[df_d['cooling_system'] != "-"]),
                "SNX": len(df_d[df_d['snx_spec'] != "-"]),
                "Legrand": len(df_d[df_d['legrand'] != "-"]),
            }
            df_infra = pd.DataFrame(list(infra_counts.items()), columns=['System', 'Count'])
            fig_infra = px.pie(df_infra, values='Count', names='System', title="📦 인프라 솔루션 제안 포트폴리오", hole=0.5,
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_infra, use_container_width=True)

        with c4:
            # 담당자별 성과 (미래 가치 중심)
            fig_mgr = px.bar(df_d[df_d['status'] != "🔴 Drop"], x='manager', y='amount', color='status',
                             title="👨‍💼 담당자별 파이프라인 보유 현황",
                             color_discrete_map={"🟢 완료":"#10b981", "🔵 견적(🔥고확률)":"#2563eb", "🔵 견적(일반)":"#93c5fd", "🟡 진행중":"#facc15", "🟠 납품대기중":"#f97316"})
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
        mapped["sort_order"] = safe_get(raw, ['정렬'], '-')
        mapped["division"] = safe_get(raw, ['구분'], '-')
        mapped["quote_date"] = safe_get(raw, ['견적일'], get_kst_date()).astype(str).str.split(' ').str[0]
        mapped["pjt_no"] = safe_get(raw, ['프로젝트번호'], '-')
        mapped["company"] = safe_get(raw, ['수주업체'], '-')
        mapped["pjt_name"] = safe_get(raw, ['프로젝트명'], '-')
        mapped["category"] = safe_get(raw, ['분류'], '기타')
        mapped["expected_timeline"] = safe_get(raw, ['예상일정'], '-')
        mapped["status"] = safe_get(raw, ['상태'], '🔵 견적(일반)').apply(clean_status)
        mapped["target_date"] = safe_get(raw, ['목표완료일'], '-')
        mapped["progress"] = safe_get(raw, ['진행률'], '-').apply(parse_progress)
        mapped["manager"] = safe_get(raw, ['관리자'], '-')
        mapped["rack_system"] = safe_get(raw, ['rack'], '-')
        mapped["power_system"] = safe_get(raw, ['power'], '-')
        mapped["cooling_system"] = safe_get(raw, ['cooling'], '-')
        mapped["snx_spec"] = safe_get(raw, ['snx'], '-')
        mapped["quantity"] = safe_get(raw, ['수량'], '-').apply(parse_quantity)
        amt_s = safe_get(raw, ['수주금액'], 0)
        if amt_s.dtype == object: amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
        mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
        mapped["client_manager"] = safe_get(raw, ['업체담당자'], '-')
        mapped["key_issue"] = safe_get(raw, ['핵심이슈'], '-')
        mapped["folder_link"] = safe_get(raw, ['폴더'], '-')
        mapped["legrand"] = safe_get(raw, ['르그랑'], '-')
        mapped["updated_at"] = get_kst_date()
        conn = sqlite3.connect(DB_PATH)
        mapped.to_sql('projects', conn, if_exists='append', index=False)
        conn.commit(); conn.close(); st.success("동기화 완료!"); st.rerun()
