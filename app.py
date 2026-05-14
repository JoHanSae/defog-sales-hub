import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# ─── 1. 페이지 설정 및 보안 레이아웃 ──────────────────────────────────────────
st.set_page_config(page_title="DEFOG 영업 파이프라인 관리", page_icon="🔒", layout="wide")

# ─── 2. 팀원 계정 설정 (필요시 여기서 수정하세요) ────────────────────────────────
USERS = {
    "manager": ("조한세 매니저", "defog!manager"),
    "leader":  ("영업팀장", "defog!leader"),
    "ceo":     ("대표님", "defog!ceo")
}

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""

# ─── 3. 로그인 화면 구현 ────────────────────────────────────────────────────────
def login_screen():
    st.markdown("<div style='text-align: center; padding-top: 50px;'><h1>🚀 DEFOG 통합 관리 허브</h1><p>팀원 전용 시스템입니다. 로그인이 필요합니다.</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_box"):
            u_id = st.text_input("아이디 (ID)")
            u_pw = st.text_input("비밀번호 (PW)", type="password")
            login_btn = st.form_submit_button("시스템 접속", use_container_width=True)
            
            if login_btn:
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = USERS[u_id][0]
                    st.rerun()
                else:
                    st.error("계정 정보가 올바르지 않습니다.")

# ─── 4. 데이터베이스 관리 로직 (안정화 버전) ───────────────────────────────────────
DB_PATH = "defog_sales_secure.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pjt_no TEXT, company TEXT, pjt_name TEXT, 
            status TEXT DEFAULT '견적', manager TEXT, 
            amount INTEGER DEFAULT 0, expected_date TEXT,
            issue TEXT, updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

# ─── 5. 메인 애플리케이션 실행 ───────────────────────────────────────────────────
if not st.session_state['logged_in']:
    login_screen()
else:
    init_db()
    
    # 상단 헤더
    header_col1, header_col2 = st.columns([8, 2])
    with header_col1:
        st.markdown(f"<h2 style='color: #2563eb;'>🚀 DEFOG 통합 파이프라인 ({st.session_state['user_name']}님)</h2>", unsafe_allow_html=True)
    with header_col2:
        if st.button("로그아웃", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # 메뉴 탭 구성
    tab_dash, tab_excel, tab_setting = st.tabs([
        "📊 실적 대시보드", 
        "📝 엑셀 관리 (수정/삭제)", 
        "⚙️ 데이터 가져오기/백업"
    ])

    # 📊 1. 대시보드
    with tab_dash:
        df = get_data()
        if df.empty:
            st.info("데이터가 없습니다. [⚙️ 데이터 가져오기] 탭에서 엑셀을 업로드해주세요.")
        else:
            won = df[df['status'] == '완료']
            c1, c2, c3 = st.columns(3)
            c1.metric("진행 중인 프로젝트", f"{len(df[df['status'] != '완료'])} 건")
            c2.metric("수주 완료 총액", f"₩{int(won['amount'].sum()):,} 원")
            c3.metric("금년 수주 목표 달성률", "78%", "▲ 5%") # 예시 지표

            col_a, col_b = st.columns(2)
            with col_a:
                fig1 = px.bar(df.groupby('manager')['amount'].sum().reset_index(), x='manager', y='amount', title="담당자별 수주액")
                st.plotly_chart(fig1, use_container_width=True)
            with col_b:
                fig2 = px.pie(df.groupby('status').size().reset_index(name='count'), names='status', values='count', hole=0.4, title="프로젝트 상태 비중")
                st.plotly_chart(fig2, use_container_width=True)

    # 📝 2. 엑셀 관리 (핵심 기능)
    with tab_excel:
        st.markdown("💡 **Tip:** 표 안을 더블클릭해 수정하고, 왼쪽 숫자를 눌러 `Delete`로 삭제하세요. 작업 후 꼭 **저장** 버튼을 누르세요.")
        df = get_data()
        
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            height=500,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "status": st.column_config.SelectboxColumn("상태", options=["견적", "진행중", "납품대기중", "완료", "Drop"]),
                "amount": st.column_config.NumberColumn("수주금액(원)", format="₩ %d")
            }
        )
        
        if st.button("💾 모든 변경사항 저장하기", type="primary", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            edited_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            st.success("데이터가 안전하게 저장되었습니다.")
            st.rerun()

    # ⚙️ 3. 설정 및 데이터 관리
    with tab_setting:
        col_up, col_down = st.columns(2)
        with col_up:
            st.markdown("#### 📥 엑셀 업로드")
            uploaded_file = st.file_uploader("2026 프로젝트.csv 업로드", type=['csv', 'xlsx'])
            if uploaded_file and st.button("🚀 데이터 일괄 등록"):
                df_import = pd.read_csv(uploaded_file, encoding='utf-8-sig') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                conn = sqlite3.connect(DB_PATH)
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                for _, row in df_import.iterrows():
                    conn.execute("INSERT INTO projects (pjt_no, company, pjt_name, status, manager, amount, updated_at) VALUES (?,?,?,?,?,?,?)",
                                 (str(row.get('프로젝트 번호','')), str(row.get('프로젝트 수주 업체','')), str(row.get('프로젝트 명','')), '견적', str(row.get('관리자','')), pd.to_numeric(row.get('수주 금액',0), errors='coerce'), now))
                conn.commit()
                conn.close()
                st.success("데이터 업로드 완료!")
                st.rerun()
        
        with col_down:
            st.markdown("#### 📤 엑셀 백업")
            if st.button("🔄 백업 파일 생성"):
                df_export = get_data()
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False)
                st.download_button("📥 엑셀 다운로드", output.getvalue(), "DEFOG_BACKUP.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
