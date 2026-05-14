import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# ─── 1. 페이지 설정 및 디자인 (블루/그레이 테마) ──────────────────────────────────
st.set_page_config(page_title="DEFOG PROJECT HUB", page_icon="🚀", layout="wide")

# 디자인 테마 적용 (CSS)
st.markdown("""
    <style>
    /* 메인 배경 및 폰트 */
    .stApp { background-color: #f8fafc; }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Pretendard', sans-serif; }
    
    /* 대시보드 카드 스타일 */
    .metric-container {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #2563eb;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        background-color: #2563eb;
        color: white;
        font-weight: bold;
        height: 3em;
        border: none;
    }
    .stButton>button:hover { background-color: #1e40af; border: none; }
    
    /* 테이블 헤더 색상 */
    .stDataFrame { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 보안 및 로그인 설정 ──────────────────────────────────────────────────
USERS = {
    "manager": ("조한세 매니저", "defog!manager"),
    "leader":  ("영업팀장", "defog!leader"),
    "ceo":     ("대표님", "defog!ceo")
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login():
    st.markdown("<div style='text-align: center; padding: 100px 0;'><h1>🚀 DEFOG PROJECT HUB</h1><p>내부 팀원 전용 로그인</p></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            u_id = st.text_input("아이디")
            u_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = USERS[u_id][0]
                    st.rerun()
                else: st.error("계정 정보가 일치하지 않습니다.")
    st.stop()

if not st.session_state['logged_in']:
    login()

# ─── 3. 데이터베이스 초기화 (컬럼명 100% 일치) ──────────────────────────────────
DB_PATH = "defog_final_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            pjt_no TEXT,
            company TEXT,
            pjt_name TEXT,
            category TEXT,
            status TEXT,
            manager TEXT,
            proposed_product TEXT,
            amount INTEGER,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

init_db()

# ─── 4. 메인 화면 구성 ───────────────────────────────────────────────────────
# 상단 헤더
c_head1, c_head2 = st.columns([9, 1])
with c_head1:
    st.markdown(f"## 🚀 DEFOG 영업 파이프라인 관리 <span style='font-size:15px; color:gray;'>({st.session_state['user_name']} 접속중)</span>", unsafe_allow_html=True)
with c_head2:
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

tab1, tab2 = st.tabs(["📊 대시보드 현황", "📝 프로젝트 편집 (수정/삭제/등록)"])

# --- TAB 1: 대시보드 ---
with tab1:
    df = get_data()
    if df.empty:
        st.info("데이터가 없습니다. 편집 탭에서 프로젝트를 추가하거나 엑셀을 업로드하세요.")
    else:
        # 요약 카드
        won_df = df[df['status'] == '완료']
        total_p = len(df)
        total_amt = df['amount'].sum()
        won_amt = won_df['amount'].sum()

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"<div class='metric-container'><p style='color:gray; font-size:14px; margin-bottom:5px;'>총 등록 프로젝트</p><h2 style='margin:0;'>{total_p} 건</h2></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-container' style='border-left-color:#10b981;'><p style='color:gray; font-size:14px; margin-bottom:5px;'>총 예상 수주액</p><h2 style='margin:0;'>₩ {total_amt:,}</h2></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-container' style='border-left-color:#f59e0b;'><p style='color:gray; font-size:14px; margin-bottom:5px;'>수주 완료 금액</p><h2 style='margin:0;'>₩ {won_amt:,}</h2></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 차트
        g1, g2 = st.columns(2)
        with g1:
            fig1 = px.bar(df.groupby('manager')['amount'].sum().reset_index(), x='manager', y='amount', title="담당자별 수주 현황", color_discrete_sequence=['#2563eb'])
            st.plotly_chart(fig1, use_container_width=True)
        with g2:
            fig2 = px.pie(df.groupby('status').size().reset_index(name='count'), names='status', values='count', hole=0.4, title="진행 상태 비중", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig2, use_container_width=True)

# --- TAB 2: 프로젝트 편집 (핵심 기능) ---
with tab2:
    st.markdown("#### 📝 실시간 데이터 편집")
    st.markdown("💡 **Tip:** 엑셀처럼 더블클릭해서 수정하세요. 행을 지우려면 왼쪽 끝 숫자를 클릭 후 **Delete** 키를 누르세요.")
    
    df_editor = get_data()
    
    # 엑셀 시각자료와 동일한 컬럼 설정
    edited_df = st.data_editor(
        df_editor,
        num_rows="dynamic",
        use_container_width=True,
        height=600,
        column_config={
            "pjt_no": st.column_config.TextColumn("PJT No", help="프로젝트 고유 번호"),
            "company": st.column_config.TextColumn("수주업체"),
            "pjt_name": st.column_config.TextColumn("프로젝트명", width="large"),
            "category": st.column_config.SelectboxColumn("구분", options=["PRODUCT", "SOLUTION", "기타"]),
            "status": st.column_config.SelectboxColumn("상태", options=["견적", "진행중", "납품대기중", "완료", "Drop"]),
            "manager": st.column_config.TextColumn("관리자"),
            "proposed_product": st.column_config.TextColumn("제안제품"),
            "amount": st.column_config.NumberColumn("수주금액", format="₩ %d"),
            "updated_at": st.column_config.TextColumn("업데이트", disabled=True)
        },
        key="main_editor"
    )

    col_btn1, col_btn2 = st.columns([8, 2])
    with col_btn2:
        if st.button("💾 변경사항 최종 저장하기", type="primary"):
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DELETE FROM projects") # 기존꺼 비우고
                # 업데이트 시간 기록
                edited_df['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                edited_df.to_sql('projects', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
                st.success("데이터베이스에 완벽하게 저장되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")

    st.markdown("---")
    
    # 엑셀 업로드 섹션 (항목 매핑 자동화)
    with st.expander("📥 기존 엑셀(2026 프로젝트.csv) 대량 업로드"):
        up_file = st.file_uploader("파일을 선택하세요", type=['csv', 'xlsx'])
        if up_file and st.button("🚀 데이터 일괄 넣기"):
            try:
                if up_file.name.endswith('.csv'):
                    raw_df = pd.read_csv(up_file, encoding='utf-8-sig')
                else:
                    raw_df = pd.read_excel(up_file)
                
                # 매니저님의 엑셀 헤더명을 우리 시스템 컬럼명으로 변환
                mapped_df = pd.DataFrame({
                    "pjt_no": raw_df.get('프로젝트 번호', '-'),
                    "company": raw_df.get('프로젝트 수주 업체', '-'),
                    "pjt_name": raw_df.get('프로젝트 명', '-'),
                    "category": raw_df.get('구분', 'PRODUCT'),
                    "status": raw_df.get('상태', '견적'),
                    "manager": raw_df.get('관리자', '-'),
                    "proposed_product": raw_df.get('SNX AI-S421260', '-'), # 제안제품 컬럼 예시
                    "amount": pd.to_numeric(raw_df.get('수주 금액', 0), errors='coerce').fillna(0),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                
                conn = sqlite3.connect(DB_PATH)
                mapped_df.to_sql('projects', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
                st.success("엑셀 데이터가 성공적으로 통합되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"업로드 실패: {e}")
