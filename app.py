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

# ─── 3. 데이터베이스 초기화 (v30 엑셀 22개 컬럼 완벽 매칭 구조) ──────────────────
DB_PATH = "defog_v30_final.db"
# 피드백 반영: 견적 가능성 높은 건 분류 기능 추가
STATUS_LIST = ["🔵 견적(🔥고확률)", "🔵 견적(일반)", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            sort_order TEXT, division TEXT, quote_date TEXT, pjt_no TEXT,
            company TEXT, pjt_name TEXT, category TEXT, expected_timeline TEXT,
            status TEXT, target_date TEXT, progress TEXT, manager TEXT,
            rack_system TEXT, power_system TEXT, cooling_system TEXT, snx_spec TEXT,
            quantity INTEGER, amount INTEGER, client_manager TEXT, key_issue TEXT,
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

init_db()

# ─── 4. 사이드바 및 네비게이션 설정 ──────────────────────────────────────────
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

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("⚠️ **보안 안내**\n\n팀원 초대 시 주소창 복사 금지! 아래 안전 링크를 활용하세요.")
    st.code("https://defog-sales-app.streamlit.app/", language="text")

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리 (22개 컬럼 완벽 구현)
# ═════════════════════════════════════════════════════════════════════════════
if menu == MENU_1:
    df_current = get_db_data()
    
    st.markdown("### 📝 파이프라인 실시간 편집 테이블")
    st.caption("💡 **수정/삭제 가이드:** 셀을 더블클릭하여 수정하거나 행 선택 후 'Delete' 키로 행 삭제가 가능합니다. 최종 저장을 꼭 눌러주세요.")
    
    # 엑셀과 100% 동일한 순서 배열 고정
    ORDERED_COLS = [
        "sort_order", "division", "quote_date", "pjt_no", "company", "pjt_name", "category", 
        "expected_timeline", "status", "target_date", "progress", "manager", 
        "rack_system", "power_system", "cooling_system", "snx_spec", "quantity", 
        "amount", "client_manager", "key_issue", "folder_link", "legrand", "updated_at"
    ]
    
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        height=550,
        column_order=ORDERED_COLS,
        column_config={
            "sort_order": "정렬", "division": "구분", "quote_date": "견적일", "pjt_no": "프로젝트 번호",
            "company": "프로젝트 수주 업체", "pjt_name": "프로젝트 명", "category": "분류",
            "expected_timeline": "예상 일정", "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
            "target_date": "목표 완료일", "progress": "진행률", "manager": "관리자",
            "rack_system": "Racking System", "power_system": "Power System", "cooling_system": "Cooling System",
            "snx_spec": "SNX AI-S421260", "quantity": st.column_config.NumberColumn("수량", format="%d"),
            "amount": st.column_config.NumberColumn("수주 금액 (원)", format="%,d"),
            "client_manager": "업체 담당자", "key_issue": "핵심 이슈", "folder_link": "폴더",
            "legrand": "르그랑", "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True)
        },
        key="main_editor"
    )

    if st.button("💾 변경사항 및 삭제 내용 저장 (DB 확정)", type="primary", use_container_width=True):
        try:
            final_df = edited_df.fillna("-")
            final_df['amount'] = pd.to_numeric(final_df['amount'], errors='coerce').fillna(0).astype(int)
            final_df['quantity'] = pd.to_numeric(final_df['quantity'], errors='coerce').fillna(0).astype(int)
            final_df['updated_at'] = get_kst_date()
            final_df = final_df[ORDERED_COLS]
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()
            st.success("✅ 대형 파이프라인 동기화 자산이 안전하게 저장되었습니다.")
            st.rerun()
        except Exception as e: st.error(f"저장 중 치명적 오류 발생: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 보드 (고확률 필터 탑재)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    st.markdown("<p style='color:gray;'>💡 주간 회의 보고용 화면입니다. 상단의 필터를 활용해 중요 건을 바로 추려내세요.</p>", unsafe_allow_html=True)
    df_meet = get_db_data()
    if not df_meet.empty:
        search_query = st.text_input("🔍 수주업체 또는 프로젝트명 빠른 검색", placeholder="검색어 입력")
        
        # 피드백 반영: 고확률 견적건 위주로 먼저 체크할 수 있는 multiselect 필터
        sel_status = st.multiselect("📌 상태 필터링 (고확률 견적 우선 선택 가능)", STATUS_LIST, default=STATUS_LIST)
        meet_filtered = df_meet[df_meet['status'].isin(sel_status)]
        
        if search_query:
            meet_filtered = meet_filtered[
                meet_filtered['company'].str.contains(search_query, na=False) | 
                meet_filtered['pjt_name'].str.contains(search_query, na=False)
            ]
            
        meet_filtered['수주 금액'] = meet_filtered['amount'].apply(lambda x: f"₩ {int(x):,}")
        
        meet_show = meet_filtered[['quote_date', 'status', 'company', 'pjt_name', 'rack_system', 'power_system', 'cooling_system', 'client_manager', '수주 금액', 'key_issue']]
        meet_show.columns = ['견적일', '상태', '프로젝트 수주 업체', '프로젝트 명', 'Racking', 'Power', 'Cooling', '업체 담당자', '수주 금액', '핵심 이슈']
        st.dataframe(meet_show.sort_values(by='견적일', ascending=False).reset_index(drop=True), use_container_width=True, height=500)
    else: st.info("데이터가 존재하지 않습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드 (차트 구체화 피드백 반영)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_dash = get_db_data()
    if df_dash.empty: st.info("분석할 데이터가 존재하지 않습니다.")
    else:
        won_amt = df_dash[df_dash['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_dash[~df_dash['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><small>현재 파이프라인 진행액</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 확정액</small><h3>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인 등록건수</small><h3>{len(df_dash)} 건</h3></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            # 피드백 반영: 세분화된 인프라 상태 분석 차트
            st.plotly_chart(px.bar(df_dash, x='status', y='amount', color='category', title="📈 파이프라인 상태별/분류별 규모 현황"), use_container_width=True)
        with c2:
            st.plotly_chart(px.box(df_dash, x='category', y='amount', title="🏢 분류별 프로젝트 금액 분포 대시보드"), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 시스템 및 데이터 관리 (22개 컬럼 완벽 맵퍼 시스템)
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    st.markdown("### 📥 엑셀 대량 동기화 파트")
    h_row = st.number_input("📌 표 제목(Header)이 있는 엑셀 실제 행 번호", min_value=1, value=1)
    f = st.file_uploader("동기화할 오리지널 엑셀 스펙 시트 선택", type=['xlsx'])
    
    if f and st.button("🚀 오리지널 데이터 1:1 매칭 시작", use_container_width=True):
        try:
            raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')
            
            mapped = pd.DataFrame()
            mapped["sort_order"] = safe_get(raw, ['정렬', '순번', 'no'], '-')
            mapped["division"] = safe_get(raw, ['구분', '파트'], '-')
            
            q_date = safe_get(raw, ['견적일', '날짜'], get_kst_date())
            mapped["quote_date"] = q_date.astype(str).str.split(' ').str[0]
            
            mapped["pjt_no"] = safe_get(raw, ['프로젝트번호', 'pjt번호', 'pjtno'], '-')
            mapped["company"] = safe_get(raw, ['프로젝트수주업체', '수주업체', '고객사', '업체명'], '-')
            mapped["pjt_name"] = safe_get(raw, ['프로젝트명', '사업명', '건명'], '-')
            mapped["category"] = safe_get(raw, ['분류', '타입'], '기타')
            mapped["expected_timeline"] = safe_get(raw, ['예상일정', '일정'], '-')
            
            mapped["status"] = safe_get(raw, ['상태', '진행현황'], '🔵 견적(일반)').apply(clean_status)
            mapped["target_date"] = safe_get(raw, ['목표완료일', '완료일'], '-')
            mapped["progress"] = safe_get(raw, ['진행률', '진행도'], '-')
            mapped["manager"] = safe_get(raw, ['관리자', '담당'], '-')
            
            # 인프라 세분화 스펙 매핑 파트
            mapped["rack_system"] = safe_get(raw, ['rackingsystem', 'racking', '렉', '랙'], '-')
            mapped["power_system"] = safe_get(raw, ['powersystem', 'power', '전력', 'pdu'], '-')
            mapped["cooling_system"] = safe_get(raw, ['coolingsystem', 'cooling', '쿨링', '공조'], '-')
            mapped["snx_spec"] = safe_get(raw, ['snxai-s421260', 'snx', 's421260'], '-')
            
            qty = safe_get(raw, ['수량', '개수'], 0)
            mapped["quantity"] = pd.to_numeric(qty, errors='coerce').fillna(0).astype(int)
            
            amt_s = safe_get(raw, ['수주금액', '금액', '매출'], 0)
            if amt_s.dtype == object:
                amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)
            
            mapped["client_manager"] = safe_get(raw, ['업체담당자', '고객담당자', '상대담당'], '-')
            mapped["key_issue"] = safe_get(raw, ['핵심이슈', '이슈', '비고'], '-')
            mapped["folder_link"] = safe_get(raw, ['폴더', '링크', '드라이브'], '-')
            mapped["legrand"] = safe_get(raw, ['르그랑', 'legrand'], '-')
            mapped["updated_at"] = get_kst_date()
            
            # 순서 재정렬 후 DB 인서트
            db_cols = [
                "sort_order", "division", "quote_date", "pjt_no", "company", "pjt_name", "category", 
                "expected_timeline", "status", "target_date", "progress", "manager", 
                "rack_system", "power_system", "cooling_system", "snx_spec", "quantity", 
                "amount", "client_manager", "key_issue", "folder_link", "legrand", "updated_at"
            ]
            mapped = mapped[db_cols]
            
            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()
            
            st.success("🎉 22개 컬럼 대형 데이터가 깨끗하게 완벽 싱크되었습니다! 1번 탭에서 합계 행 정리 등 최종 컨펌을 진행하세요.")
            st.rerun()
        except Exception as e:
            st.error(f"엑셀 맵핑 동기화 중 에러 발생: {e}")
