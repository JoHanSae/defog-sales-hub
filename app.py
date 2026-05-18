import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
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
        background: white; padding: 20px; border-radius: 12px; 
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05); border-top: 5px solid #2563eb; 
    }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 및 로그인 관리 ─────────────────────────────────────────────
USERS = {
    "ceo":     ("대표님", "defog!ceo"),
    "leader1": ("김원중 팀장님", "defog!leader1"),
    "leader2": ("김용신 팀장님", "defog!leader2"),
    "manager": ("팀원", "defog!manager")
}

if 'logged_in' not in st.session_state:
    ticket = st.query_params.get("ticket", "")
    is_valid_ticket = False
    for uid in USERS:
        if ticket == f"defog_auth_{uid}_valid":
            st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[uid][0]
            is_valid_ticket = True
            break
    if not is_valid_ticket: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login"):
            u_id = st.text_input("ID")
            u_pw = st.text_input("PW", type="password")
            if st.form_submit_button("시스템 접속", use_container_width=True):
                if u_id in USERS and USERS[u_id][1] == u_pw:
                    st.session_state['logged_in'], st.session_state['user_name'] = True, USERS[u_id][0]
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

# ─── 3. 데이터베이스 초기화 (v26 무결점 구조) ─────────────────────────────────
DB_PATH = "defog_v26_final.db"
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

def safe_get(df, keywords, default_val):
    for col in df.columns:
        norm = str(col).lower().replace(' ', '').replace('(', '').replace(')', '').strip()
        for k in keywords:
            if k in norm: return df[col].fillna(default_val)
    return pd.Series([default_val] * len(df))

def clean_status(text):
    text = str(text)
    if "완료" in text: return "🟢 완료"
    elif "대기" in text: return "🟠 납품대기중"
    elif "진행" in text: return "🟡 진행중"
    elif "Drop" in text or "취소" in text: return "🔴 Drop"
    else: return "🔵 견적"

init_db()

# ─── 4. 사이드바 및 네비게이션 명칭 완벽 통일 ───────────────────────────────
MENU_1 = "📝 프로젝트 파이프라인 관리"
MENU_2 = "🤝 주간 영업 회의 보드"
MENU_3 = "📊 경영진 성과 대시보드"
MENU_4 = "⚙️ 시스템 및 데이터 관리"

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    st.markdown("---")
    menu = st.radio("메뉴 이동", [MENU_1, MENU_2, MENU_3, MENU_4], label_visibility="collapsed")
    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리 (수정 / 삭제 / 추가 전체 구현)
# ═════════════════════════════════════════════════════════════════════════════
if menu == MENU_1:
    with st.expander("🚀 스마트 신규 프로젝트 직접 등록", expanded=False):
        with st.form("quick_add_form"):
            f1, f2, f3, f4 = st.columns(4)
            with f1: f_no = st.text_input("PJT No")
            with f2: f_comp = st.text_input("수주업체 *")
            with f3: f_name = st.text_input("프로젝트명 *")
            with f4: f_amt = st.number_input("수주금액 (원)", min_value=0, step=1000000)
            
            f5, f6, f7, f8 = st.columns(4)
            with f5: f_cat = st.selectbox("구분", ["PRODUCT", "SOLUTION", "기타"])
            with f6: f_pf = st.text_input("제품군 (예: Rack, Inrow)")
            with f7: f_stat = st.selectbox("상태", STATUS_LIST)
            with f8: f_mgr = st.selectbox("우리측 담당자", DEFAULT_MANAGERS)
            
            f9, f10 = st.columns(2)
            with f9: f_clt = st.text_input("상대 담당자")
            with f10: f_date = st.date_input("최초 견적일", value=datetime.now())
            f_rem = st.text_input("비고 (특이사항)")
            
            if st.form_submit_button("등록 완료", use_container_width=True):
                if f_comp and f_name:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (f_no, f_comp, f_name, f_cat, f_pf, f_stat, f_mgr, f_clt, f_date.strftime("%Y-%m-%d"), int(f_amt), f_rem, get_kst_date()))
                    conn.commit(); conn.close()
                    st.success("✅ 프로젝트가 등록되었습니다!")
                    st.rerun()
                else: st.error("수주업체와 프로젝트명은 필수입니다.")

    df_current = get_db_data()
    
    # 정렬 및 에러 방지용 표준 컬럼 순서
    ORDERED_COLS = ["pjt_no", "company", "pjt_name", "product_family", "category", "status", "manager", "client_manager", "quote_date", "amount", "remarks", "updated_at"]
    
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        height=500,
        column_order=ORDERED_COLS,
        column_config={
            "pjt_no": "PJT No", "company": "수주업체", "pjt_name": "프로젝트명",
            "product_family": "제품군", "category": "구분",
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
            "manager": "우리측 담당", "client_manager": "상대 담당", "quote_date": "견적일",
            "amount": st.column_config.NumberColumn("수주금액 (원)", format="%d"),
            "remarks": "비고", "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True)
        },
        key="main_editor"
    )

    if st.button("💾 변경사항 및 삭제 내용 저장 (DB 확정)", type="primary", use_container_width=True):
        try:
            final_df = edited_df.fillna("-")
            final_df['amount'] = pd.to_numeric(final_df['amount'], errors='coerce').fillna(0).astype(int)
            final_df['updated_at'] = get_kst_date()
            final_df = final_df[ORDERED_COLS] # 컬럼 구조 동기화 보장
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()
            st.success("✅ 모든 변경사항 및 삭제가 완벽히 저장되었습니다.")
            st.rerun()
        except Exception as e: st.error(f"저장 중 오류: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 보드 (정상 복구 완료)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    st.markdown("<p style='color:gray;'>💡 미팅 시 즉시 검색하여 보고하세요. (읽기 전용)</p>", unsafe_allow_html=True)
    df_meet = get_db_data()
    if not df_meet.empty:
        search_query = st.text_input("🔍 수주업체 또는 프로젝트명 빠른 검색", placeholder="키워드 입력")
        col_f1, col_f2 = st.columns([7, 3])
        with col_f1: sel_status = st.multiselect("📌 상태 필터링", STATUS_LIST, default=STATUS_LIST)
        with col_f2:
            unique_mgr = df_meet['manager'].unique().tolist()
            sel_mgr = st.multiselect("👨‍💼 담당자 필터링", unique_mgr, default=unique_mgr)
            
        meet_filtered = df_meet[df_meet['status'].isin(sel_status) & df_meet['manager'].isin(sel_mgr)]
        if search_query:
            meet_filtered = meet_filtered[meet_filtered['company'].str.contains(search_query, na=False) | meet_filtered['pjt_name'].str.contains(search_query, na=False)]
            
        meet_filtered['수주금액'] = meet_filtered['amount'].apply(lambda x: f"₩ {int(x):,}")
        
        meet_show = meet_filtered[['updated_at', 'status', 'company', 'pjt_name', 'product_family', 'manager', 'client_manager', 'quote_date', '수주금액', 'remarks']]
        meet_show.columns = ['최종업데이트', '상태', '수주업체', '프로젝트명', '제품군', '우리담당', '상대담당', '견적일', '수주금액', '비고']
        st.dataframe(meet_show.sort_values(by='최종업데이트', ascending=False).reset_index(drop=True), use_container_width=True, height=500)
    else: st.info("데이터가 존재하지 않습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드 (정상 복구 완료)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_dash = get_db_data()
    if df_dash.empty: st.info("데이터가 존재하지 않습니다.")
    else:
        won_amt = df_dash[df_dash['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_dash[~df_dash['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>현재 진행 금액</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 확정액</small><h3>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인 건수</small><h3>{len(df_dash)} 건</h3></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            pf_data = df_dash.groupby('product_family')['amount'].sum().reset_index()
            st.plotly_chart(px.pie(pf_data, values='amount', names='product_family', title="📦 제품군별 비중 (금액 기준)", hole=0.4), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(df_dash, x='manager', y='amount', color='status', title="👨‍💼 담당자별 성과"), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 시스템 및 데이터 관리 (순수 엑셀 업로드 연동)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    st.markdown("### 📥 엑셀 데이터 불러오기")
    h_row = st.number_input("📌 표 제목(Header)이 있는 엑셀 행 번호", min_value=1, value=1)
    f = st.file_uploader("엑셀 파일 선택", type=['xlsx'])
    
    if f and st.button("🚀 데이터 동기화 시작", use_container_width=True):
        try:
            raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')
            
            mapped = pd.DataFrame()
            mapped["pjt_no"] = safe_get(raw, ['pjt', 'no', '번호'], '-')
            mapped["company"] = safe_get(raw, ['업체', '고객사', '수주업체'], '-')
            mapped["pjt_name"] = safe_get(raw, ['프로젝트', '사업명', '건명'], '-')
            mapped["category"] = safe_get(raw, ['구분', '종류'], 'PRODUCT')
            mapped["product_family"] = safe_get(raw, ['제품군', '품목', '아이템'], '-')
            mapped["status"] = safe_get(raw, ['상태', '진행'], '🔵 견적').apply(clean_status)
            mapped["manager"] = safe_get(raw, ['우리담당', '영업대표', '우리측담당', '담당자'], '-')
            mapped["client_manager"] = safe_get(raw, ['상대담당', '고객담당', '업체담당'], '-')
            
            q_date = safe_get(raw, ['견적일', '날짜', '최초견적'], get_kst_date())
            mapped["quote_date"] = q_date.astype(str).str.split(' ').str[0] # 시간 날리기
            
            amt_s = safe_get(raw, ['금액', '매출', '수주금액'], 0)
            if amt_s.dtype == object:
                amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
            
            mapped["remarks"] = safe_get(raw, ['비고', '특이'], '-')
            mapped["updated_at"] = get_kst_date()
            
            # DB 컬럼 순서 맞추기
            db_cols = ["pjt_no", "company", "pjt_name", "category", "product_family", "status", "manager", "client_manager", "quote_date", "amount", "remarks", "updated_at"]
            mapped = mapped[db_cols]
            
            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()
            
            st.success("🎉 데이터 동기화가 성공적으로 완료되었습니다! 1번 탭에서 확인 및 수동 편집(합계 삭제)을 진행해 주세요.")
            st.rerun()
        except Exception as e:
            st.error(f"동기화 오류 발생: {e}")
