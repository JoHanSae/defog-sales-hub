import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime
import io

# ─── 1. 페이지 설정 ──────────────────────────────────────────────────────────
st.set_page_config(page_title="DEFOG 영업 허브", page_icon="🚀", layout="wide")

# (CSS 스타일은 이전과 동일)
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    [data-testid="stDataFrame"] svg { stroke: #475569 !important; fill: #475569 !important; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); border-top: 5px solid #2563eb; }
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

# ⭐ 보안 패치: 세션 상태와 티켓의 유효성 검사
if 'logged_in' not in st.session_state:
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

def show_login():
    if os.path.exists("logo.png"):
        col_logo1, col_logo2, col_logo3 = st.columns([2, 1, 2])
        with col_logo2: st.image("logo.png", use_container_width=True)
            
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
                    # ⭐ 로그인 성공 시 티켓 발급 후 즉시 리런 (내부적으로 유지됨)
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

if not st.session_state['logged_in']:
    show_login()

# ─── 3. 데이터베이스 및 전역 변수 (이하 로직 동일) ─────────────────────────────
DB_PATH = "defog_v9_final.db"
# (기존 데이터베이스 초기화 및 데이터 로드 함수들...)
# ... (생략된 부분은 이전 V9 코드와 동일)

# ─── 4. 사이드바 네비게이션 ──────────────────────────────────────────────────
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
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
        st.query_params.clear() # 로그아웃 시 티켓 완전 삭제
        st.rerun()

# (이하 각 메뉴별 화면 구현 로직 동일)
# ... (생략된 부분은 이전 V9 코드와 동일)

# ⭐ 보안 추가 아이디어: 설정 탭에 '팀원용 깨끗한 주소 복사' 기능 추가
if menu == MENU_4:
    st.markdown("---")
    st.markdown("#### 🔗 팀원 공유용 링크")
    base_url = "https://defog-sales-app.streamlit.app/" # 실제 매니저님 주소로 수정 가능
    st.code(base_url, language="text")
    st.caption("위의 주소를 복사해서 팀원들에게 전달하면 보안 로그인 화면이 정상적으로 나타납니다.")
