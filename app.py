import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, timedelta
import io

# ─── KST 절대 시간 함수 (날짜만) ──────────────────────────────────────────
def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")

# ─── 1. 페이지 설정 및 시각적 테마 ──────────────────────────────────────────
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    [data-testid="stDataFrame"] svg { stroke: #475569 !important; fill: #475569 !important; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); border-top: 5px solid #2563eb; transition: transform 0.2s; }
    .metric-card:hover { transform: translateY(-2px); }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    
    /* 프리미엄 하단 요약 배너 */
    .summary-banner {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 15px 25px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin-top: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .summary-banner h4, .summary-banner h3 { margin: 0; color: white !important; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 설정 ─────────────────────────────────────────────────────────
USERS = {
    "ceo":     ("대표님", "defog!ceo"),
    "leader1": ("김원중 팀장님", "defog!leader1"),
    "leader2": ("김용신 팀장님", "defog!leader2"),
    "manager": ("팀원", "defog!manager")
}

# ─── 3. 로그인 및 F5 방어 ─────────────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    ticket = st.query_params.get("ticket", "")
    is_valid_ticket = False
    for uid in USERS:
        if ticket == f"defog_auth_{uid}_valid":
            st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[uid][0]
            is_valid_ticket = True
            break
    if not is_valid_ticket: st.session_state['logged_in'] = False

def show_login():
    if os.path.exists("logo.png"):
        col_logo1, col_logo2, col_logo3 = st.columns([2, 1, 2])
        with col_logo2: st.image("logo.png", use_container_width=True)
    st.markdown("<div style='text-align: center; padding: 30px 0;'><h1 style='color:#1e3a8a;'>🚀 DEFOG Sales Hub</h1><p style='color:#64748b;'>사내 통합 파이프라인 관리 시스템</p></div>", unsafe_allow_html=True)
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

if not st.session_state['logged_in']: show_login()

# ─── 4. 데이터베이스 및 전역 설정 ───────────────────────────────────────────────
DB_PATH = "defog_v20_final.db"
DEFAULT_MANAGERS = ["김형권", "김원중", "김용신", "이승호", "김민태", "한민혁", "조한새", "김혜지", "홍정희", "이수빈"]
STATUS_LIST = ["🔵 견적", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            pjt_no TEXT, company TEXT, pjt_name TEXT, category TEXT, product_family TEXT,
            status TEXT, manager TEXT, client_manager TEXT, quote_date TEXT,
            amount INTEGER, remarks TEXT, updated_at TEXT
        )
    """)
    conn.close()

def get_db_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

def clean_status(text):
    text = str(text)
    if "완료" in text: return "🟢 완료"
    elif "대기" in text: return "🟠 납품대기중"
    elif "진행" in text: return "🟡 진행중"
    elif "Drop" in text or "취소" in text: return "🔴 Drop"
    else: return "🔵 견적"

def safe_get(df, possible_keywords, default_val):
    for col in df.columns:
        norm_col = str(col).lower().replace(' ', '').replace('_', '').replace('(', '').replace(')', '').replace('원', '').strip()
        for keyword in possible_keywords:
            if keyword in norm_col:
                return df[col].fillna(default_val)
    return pd.Series([default_val] * len(df))

init_db()

# ─── 5. 사이드바 네비게이션 ──────────────────────────────────────────────────
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    menu = st.radio("메뉴 이동", ["📝 파이프라인 관리", "🤝 주간 영업 회의", "📊 성과 대시보드", "⚙️ 시스템 및 데이터 관리"])
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()
    st.info("🔗 **팀원 초대용 링크**\n\nhttps://defog-sales-app.streamlit.app/")

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리
# ═════════════════════════════════════════════════════════════════════════════
if menu == "📝 파이프라인 관리":
    with st.expander("🚀 신규 프로젝트 직접 등록"):
        with st.form("add_form"):
            c1, c2, c3 = st.columns(3)
            p_no = c1.text_input("PJT No")
            p_comp = c2.text_input("수주업체 *")
            p_name = c3.text_input("프로젝트명 *")
            c4, c5, c6 = st.columns(3)
            p_pf = c4.text_input("제품군 (예: Rack, Inrow)")
            p_stat = c5.selectbox("상태", STATUS_LIST)
            p_mgr = c6.selectbox("우리측 담당자", DEFAULT_MANAGERS)
            c7, c8, c9 = st.columns(3)
            p_clt = c7.text_input("고객사 담당자")
            p_date = c8.date_input("최초 견적일", value=datetime.now())
            p_amt = c9.number_input("수주금액 (원)", min_value=0, step=1000000)
            p_rem = st.text_input("비고")
            if st.form_submit_button("등록 완료"):
                if p_comp and p_name:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (p_no, p_comp, p_name, "기타", p_pf, p_stat, p_mgr, p_clt, p_date.strftime("%Y-%m-%d"), int(p_amt), p_rem, get_kst_date()))
                    conn.commit(); conn.close(); st.success("등록 완료!"); st.rerun()

    df = get_db_data()
    df['display_amount'] = df['amount'].apply(lambda x: f"{int(x):,}")
    
    # 매니저님 요청 순서: 담당자 -> 제품군 -> 상대담당 -> 견적일 -> 금액 -> 비고
    ORDERED_COLS = ["pjt_no", "company", "pjt_name", "product_family", "status", "manager", "client_manager", "quote_date", "display_amount", "remarks", "updated_at"]
    
    edited_df = st.data_editor(df, use_container_width=True, height=500, column_order=ORDERED_COLS, num_rows="dynamic",
                               column_config={
                                   "amount": None, "display_amount": "수주금액 ✏️",
                                   "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
                                   "quote_date": st.column_config.DateColumn("견적일"),
                                   "updated_at": st.column_config.TextColumn("업데이트", disabled=True)
                               })
    
    # 프리미엄 하단 요약 배너
    total_pipeline = df['amount'].sum()
    st.markdown(f'<div class="summary-banner"><div><h4>📊 현재 파이프라인 종합 요약</h4></div><h3>₩ {total_pipeline:,} ({len(df)}건)</h3></div>', unsafe_allow_html=True)
    
    if st.button("💾 데이터베이스 저장 (변경사항 확정)", type="primary", use_container_width=True):
        edited_df['amount'] = edited_df['display_amount'].astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0').astype(int)
        final_df = edited_df.drop(columns=['display_amount']).fillna("-")
        final_df['updated_at'] = get_kst_date()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM projects")
        final_df.to_sql('projects', conn, if_exists='append', index=False)
        conn.close(); st.success("저장 완료!"); st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 (VIP & HOT 뱃지)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == "🤝 주간 영업 회의":
    df_m = get_db_data()
    if not df_m.empty:
        search = st.text_input("🔍 빠른 검색", placeholder="업체명 또는 프로젝트명")
        if search: df_m = df_m[df_m['company'].str.contains(search, na=False) | df_m['pjt_name'].str.contains(search, na=False)]
        
        def get_badge(amt):
            if amt >= 1000000000: return "👑 VIP"
            elif amt >= 100000000: return "🔥 HOT"
            else: return "⭐ 일반"
            
        df_m['중요도'] = df_m['amount'].apply(get_badge)
        df_m['수주금액'] = df_m['amount'].apply(lambda x: f"₩ {int(x):,}")
        
        show_cols = ['updated_at', 'status', '중요도', 'company', 'pjt_name', 'product_family', 'manager', 'client_manager', '수주금액', 'remarks']
        st.dataframe(df_m[show_cols].sort_values('updated_at', ascending=False), use_container_width=True)
    else: st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 성과 대시보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == "📊 성과 대시보드":
    df_d = get_db_data()
    if not df_d.empty:
        won = df_d[df_d['status'] == "🟢 완료"]['amount'].sum()
        active = df_d[~df_d['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>현재 진행 금액</small><h3>₩ {active:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 완료액</small><h3>₩ {won:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인</small><h3>{len(df_d)}건</h3></div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df_d, values='amount', names='product_family', title="📦 제품군별 비중", hole=0.4), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df_d, x='manager', y='amount', color='status', title="👨‍💼 담당자별 성과"), use_container_width=True)
    else: st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 시스템 및 데이터 관리 (초강력 엑셀 필터)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == "⚙️ 시스템 및 데이터 관리":
    st.info("🚨 엑셀 업로드 시 '합계' 행은 자동으로 필터링되어 제외됩니다.")
    h_row = st.number_input("📌 표 제목(Header)이 있는 행 번호", min_value=1, value=1)
    f = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xls'])
    if f and st.button("🚀 데이터 동기화"):
        try:
            raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')
            mapped = pd.DataFrame()
            mapped["pjt_no"] = safe_get(raw, ['pjt', 'no', '번호'], '-')
            mapped["company"] = safe_get(raw, ['업체', '고객사', '수주업체', '기관'], '-')
            mapped["pjt_name"] = safe_get(raw, ['프로젝트', '사업명', '건명'], '-')
            mapped["category"] = safe_get(raw, ['구분', '종류'], 'PRODUCT')
            mapped["product_family"] = safe_get(raw, ['제품군', '품목', '아이템'], '-')
            mapped["status"] = safe_get(raw, ['상태', '진행'], '견적').apply(clean_status)
            mapped["manager"] = safe_get(raw, ['우리담당', '영업대표', '우리측담당'], '-')
            mapped["client_manager"] = safe_get(raw, ['상대담당', '고객담당', '업체담당'], '-')
            mapped["quote_date"] = safe_get(raw, ['견적일', '날짜', '최초견적'], get_kst_date())
            mapped["remarks"] = safe_get(raw, ['비고', '특이', '메모'], '-')
            
            amt_s = safe_get(raw, ['금액', '매출', '수주금액'], 0)
            if amt_s.dtype == object: amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
            mapped["updated_at"] = get_kst_date()
            
            # ⭐ 엑셀 합계 데이터 원천 차단 필터
            keywords = ['합계', '총계', 'total', '계']
            mapped = mapped[~mapped['company'].astype(str).str.contains('|'.join(keywords), na=False)]
            mapped = mapped[~mapped['pjt_name'].astype(str).str.contains('|'.join(keywords), na=False)]
            
            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.close(); st.success("🎉 동기화 완료!"); st.rerun()
        except Exception as e: st.error(f"오류 발생: {e}")
