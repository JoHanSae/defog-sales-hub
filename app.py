import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, timedelta
import io

# --- KST 절대 시간 함수 (날짜만) ---
def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")

# 1. 페이지 설정 및 시각적 테마
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    .summary-banner {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 15px 25px; border-radius: 8px; color: white;
        display: flex; justify-content: space-between; align-items: center;
        margin: 15px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .summary-banner h3 { margin: 0; color: white !important; font-weight: 700; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# 2. 로그인 세션 관리
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
                else: st.error("정보 불일치")
    st.stop()

# 3. 데이터베이스 설정 (v21 무결점 구조)
DB_PATH = "defog_v21_master.db"
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

def safe_get(df, possible_keywords, default_val):
    for col in df.columns:
        norm_col = str(col).lower().replace(' ', '').replace('(', '').replace(')', '').strip()
        for k in possible_keywords:
            if k in norm_col: return df[col].fillna(default_val)
    return pd.Series([default_val] * len(df))

init_db()

# 4. 사이드바 네비게이션
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    menu = st.radio("메뉴 이동", ["📝 파이프라인 관리", "🤝 영업 회의", "📊 성과 대시보드", "⚙️ 데이터 동기화"])
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800;'>{menu}</h2>", unsafe_allow_html=True)

# 5. 메뉴별 기능
if menu == "📝 파이프라인 관리":
    df = get_db_data()
    # 수주금액 천단위 콤마 처리
    df['display_amount'] = df['amount'].apply(lambda x: f"{int(x):,}")
    
    # 요청하신 최적의 순서 배치
    ORDERED_COLS = ["pjt_no", "company", "pjt_name", "product_family", "status", "manager", "client_manager", "quote_date", "display_amount", "remarks", "updated_at"]
    
    edited_df = st.data_editor(df, use_container_width=True, height=500, column_order=ORDERED_COLS, num_rows="dynamic",
                               column_config={
                                   "amount": None, 
                                   "display_amount": st.column_config.TextColumn("수주금액 (원) ✏️", width="medium"),
                                   "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
                                   "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True)
                               }, key="v21_editor")
    
    # 하단 요약 배너 (에러 없이 합계 계산)
    total_pipeline = df['amount'].sum()
    st.markdown(f'<div class="summary-banner"><div><h4>📊 파이프라인 종합 요약</h4></div><h3>₩ {total_pipeline:,} ({len(df)}건)</h3></div>', unsafe_allow_html=True)
    
    if st.button("💾 모든 변경사항 데이터베이스에 저장", type="primary", use_container_width=True):
        try:
            edited_df['amount'] = edited_df['display_amount'].astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0').astype(int)
            final_df = edited_df.drop(columns=['display_amount']).fillna("-")
            final_df['updated_at'] = get_kst_date()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.close(); st.success("성공적으로 저장되었습니다."); st.rerun()
        except Exception as e: st.error(f"저장 중 오류 발생: {e}")

elif menu == "⚙️ 데이터 동기화":
    st.info("🚨 엑셀 업로드 시 '합계' 행은 자동으로 감지하여 제외합니다.")
    h_row = st.number_input("📌 표 제목(Header)이 있는 엑셀 행 번호", min_value=1, value=1)
    f = st.file_uploader("엑셀 파일 선택", type=['xlsx'])
    if f and st.button("🚀 데이터 동기화 시작"):
        try:
            raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')
            mapped = pd.DataFrame()
            mapped["pjt_no"] = safe_get(raw, ['pjt', 'no', '번호'], '-')
            mapped["company"] = safe_get(raw, ['업체', '고객사', '수주업체'], '-')
            mapped["pjt_name"] = safe_get(raw, ['프로젝트', '사업명', '건명'], '-')
            mapped["category"] = safe_get(raw, ['구분', '종류'], 'PRODUCT')
            mapped["product_family"] = safe_get(raw, ['제품군', '품목', '아이템'], '-')
            mapped["status"] = safe_get(raw, ['상태', '진행'], '견적').apply(clean_status)
            mapped["manager"] = safe_get(raw, ['우리담당', '우리측담당', '매니저'], '-')
            mapped["client_manager"] = safe_get(raw, ['상대담당', '고객담당', '업체담당'], '-')
            mapped["quote_date"] = safe_get(raw, ['견적일', '날짜', '최초견적'], get_kst_date())
            mapped["remarks"] = safe_get(raw, ['비고', '특이'], '-')
            
            amt_s = safe_get(raw, ['금액', '매출', '수주금액'], 0)
            if amt_s.dtype == object: amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
            mapped["updated_at"] = get_kst_date()
            
            # 합계 찌꺼기 2중 필터링
            bad_k = ['합계', '총계', 'total', '계']
            mapped = mapped[~mapped['company'].astype(str).str.contains('|'.join(bad_k), na=False)]
            mapped = mapped[~mapped['pjt_name'].astype(str).str.contains('|'.join(bad_k), na=False)]
            
            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.close(); st.success("데이터 동기화 완료!"); st.rerun()
        except Exception as e: st.error(f"오류: {e}")
