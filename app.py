import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime
import io

# ─── 1. 페이지 설정 및 다크모드 대응 UI/UX 최적화 ─────────────────────────────
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    [data-testid="stDataFrame"] svg { stroke: #475569 !important; fill: #475569 !important; }
    
    .metric-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); 
        border-top: 5px solid #2563eb; transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); }
    
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 설정 ─────────────────────────────────────────────────────────
USERS = {
    "ceo":     ("대표님", "defog!ceo"),
    "leader1": ("김원중 팀장님", "defog!leader1"),
    "leader2": ("김용신 팀장님", "defog!leader2"),
    "manager": ("팀원", "defog!manager")
}

# ─── 3. 보안 및 F5 새로고침 방어 로직 ─────────────────────────────────────────
if 'logged_in' not in st.session_state:
    # URL 주소창의 티켓(출입증) 확인
    ticket = st.query_params.get("ticket", "")
    is_valid_ticket = False
    
    for uid in USERS:
        if ticket == f"defog_auth_{uid}_valid":
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = USERS[uid][0]
            is_valid_ticket = True
            break
            
    if not is_valid_ticket:
        st.session_state['logged_in'] = False
        st.session_state['user_name'] = ""

def show_login():
    if os.path.exists("logo.png"):
        col_logo1, col_logo2, col_logo3 = st.columns([2, 1, 2])
        with col_logo2:
            st.image("logo.png", use_container_width=True)
            
    st.markdown("<div style='text-align: center; padding: 30px 0;'><h1 style='color:#1e3a8a;'>🚀 DEFOG Sales Hub</h1><p style='color:#64748b;'>사내 통합 파이프라인 관리 시스템</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login"):
            u_id = st.text_input("ID")
            u_pw = st.text_input("PW", type="password")
            if st.form_submit_button("시스템 접속", use_container_width=True):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = USERS[u_id][0]
                    # 로그인 성공 시 주소창에 티켓 발급 (F5 방어용)
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

if not st.session_state['logged_in']:
    show_login()

# ─── 4. 데이터베이스 및 전역 변수 설정 (비고란 포함) ─────────────────────────────
DB_PATH = "defog_v9_final.db" 
DEFAULT_MANAGERS = ["김형권", "김원중", "김용신", "이승호", "김민태", "한민혁", "조한새", "김혜지", "홍정희", "이수빈"]
STATUS_LIST = ["🔵 견적", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            pjt_no TEXT, company TEXT, pjt_name TEXT, 
            category TEXT, status TEXT, manager TEXT, 
            proposed_product TEXT, amount INTEGER, remarks TEXT, updated_at TEXT
        )
    """)
    conn.commit()
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

init_db()

# ─── 5. 사이드바 및 네비게이션 메뉴 ──────────────────────────────────────────
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center; color: #1e3a8a;'>DEFOG</h2>", unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    st.markdown("---")
    
    MENU_1 = "📝 프로젝트 파이프라인 관리"
    MENU_2 = "🤝 주간 영업 회의 보드"
    MENU_3 = "📊 경영진 성과 대시보드"
    MENU_4 = "⚙️ 시스템 및 데이터 관리"
    
    menu = st.radio("메뉴 이동", [MENU_1, MENU_2, MENU_3, MENU_4], label_visibility="collapsed")
    
    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear() # 로그아웃 시 주소창 티켓 완전 삭제
        st.rerun()

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
