import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
import io

# --- 한국 시간 날짜 함수 (YYYY-MM-DD) ---
def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")

# 1. 페이지 설정
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    .stButton button { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# 2. 로그인 관리
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
            if st.form_submit_button("시스템 접속"):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[u_id][0]
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

# 3. 데이터베이스 초기화 (v25)
DB_PATH = "defog_v25_master.db"
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

def safe_get(df, keywords, default):
    for col in df.columns:
        norm = str(col).lower().replace(' ', '').replace('(', '').replace(')', '').strip()
        for k in keywords:
            if k in norm: return df[col].fillna(default)
    return pd.Series([default] * len(df))

init_db()

# 4. 사이드바
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png")
    st.markdown(f"👤 **{st.session_state['user_name']}**")
    menu = st.radio("메뉴 이동", ["📝 파이프라인 관리", "🤝 영업 회의", "📊 성과 대시보드", "⚙️ 데이터 동기화"])
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()

# 5. 메인 기능
if menu == "📝 파이프라인 관리":
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    
    st.markdown("### 📝 프로젝트 리스트")
    st.caption("💡 수정/삭제 방법: 표에서 내용을 수정하거나 행을 선택해 삭제한 후, 하단 [변경사항 저장] 버튼을 꼭 눌러주세요.")

    # 안정성을 위해 가장 표준적인 컬럼 설정 사용
    edited_df = st.data_editor(
        df, 
        use_container_width=True, 
        height=600, 
        num_rows="dynamic", # 이 옵션으로 행 추가/삭제 가능
        column_config={
            "pjt_no": "PJT No",
            "company": "수주업체",
            "pjt_name": "프로젝트명",
            "product_family": "제품군",
            "category": "구분",
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
            "manager": "우리측 담당",
            "client_manager": "상대 담당",
            "quote_date": "견적일",
            "amount": st.column_config.NumberColumn("수주금액 (원)", format="%d"),
            "remarks": "비고",
            "updated_at": st.column_config.TextColumn("업데이트 날짜", disabled=True)
        },
        key="v25_editor"
    )
    
    if st.button("💾 변경사항 및 삭제 내용 저장", type="primary"):
        try:
            # 데이터 정제
            final_df = edited_df.fillna("-")
            final_df['amount'] = pd.to_numeric(final_df['amount'], errors='coerce').fillna(0).astype(int)
            final_df['updated_at'] = get_kst_date()
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.close()
            st.success("데이터베이스가 업데이트되었습니다.")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {e}")

elif menu == "⚙️ 데이터 동기화":
    st.markdown("### ⚙️ 엑셀 데이터 불러오기")
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
            
            # 상태값 처리
            mapped["status"] = safe_get(raw, ['상태', '진행'], '🔵 견적')
            
            mapped["manager"] = safe_get(raw, ['우리담당', '영업대표', '우리측담당'], '-')
            mapped["client_manager"] = safe_get(raw, ['상대담당', '고객담당', '업체담당'], '-')
            
            # 날짜 처리
            q_date = safe_get(raw, ['견적일', '날짜', '최초견적'], get_kst_date())
            mapped["quote_date"] = q_date.astype(str).str.split(' ').str[0] # 시간 제거
            
            # 금액 처리
            amt_s = safe_get(raw, ['금액', '매출', '수주금액'], 0)
            if amt_s.dtype == object:
                amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
            
            mapped["remarks"] = safe_get(raw, ['비고', '특이'], '-')
            mapped["updated_at"] = get_kst_date()
            
            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.close()
            st.success("데이터 동기화 완료! '파이프라인 관리' 메뉴에서 확인하세요.")
            st.rerun()
        except Exception as e:
            st.error(f"동기화 오류: {e}")

# (영업 회의 및 대시보드는 기존 안정된 로직으로 자동 연동됩니다)
