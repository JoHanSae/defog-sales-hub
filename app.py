import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
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
    
    .meeting-card {
        background: #ffffff; padding: 15px; border-radius: 8px;
        border-left: 5px solid #f59e0b; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 설정 (매니저님 요청사항 완벽 반영) ──────────────────────────────
USERS = {
    "ceo":     ("대표님", "defog!ceo"),
    "leader1": ("김원중 팀장님", "defog!leader1"),
    "leader2": ("김용신 팀장님", "defog!leader2"),
    "manager": ("팀원", "defog!manager")
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def show_login():
    st.markdown("<div style='text-align: center; padding: 100px 0;'><h1 style='color:#1e3a8a;'>🚀 DEFOG Hub</h1><p style='color:#64748b;'>사내 통합 파이프라인 관리 시스템 (Master)</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login"):
            u_id = st.text_input("ID")
            u_pw = st.text_input("PW", type="password")
            if st.form_submit_button("시스템 접속", use_container_width=True):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = USERS[u_id][0]
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

if not st.session_state['logged_in']:
    show_login()

# ─── 3. 데이터베이스 및 전역 변수 설정 ──────────────────────────────────────────
DB_PATH = "defog_v7_master.db" 
DEFAULT_MANAGERS = ["김형권", "김원중", "김용신", "이승호", "김민태", "한민혁", "조한새", "김혜지", "홍정희", "이수빈"]
STATUS_LIST = ["🔵 견적", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            pjt_no TEXT, company TEXT, pjt_name TEXT, 
            category TEXT, status TEXT, manager TEXT, 
            proposed_product TEXT, amount INTEGER, updated_at TEXT
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

# ─── 4. 메인 화면 헤더 ────────────────────────────────────────────────────────
c_h1, c_h2 = st.columns([9, 1])
with c_h1:
    st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800;'>🚀 DEFOG 영업 파이프라인 허브 <span style='font-size:16px; color:#64748b;'>({st.session_state['user_name']} 접속중)</span></h2>", unsafe_allow_html=True)
with c_h2:
    if st.button("로그아
