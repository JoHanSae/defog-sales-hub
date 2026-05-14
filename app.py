import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
from datetime import datetime, timedelta
import io

# ─── KST 절대 시간 함수 (시간 빼고 날짜만!) ───────────────────────────────
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
    
    /* 프리미엄 배너 스타일 */
    .summary-banner {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 15px 25px;
        border-radius: 8px;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 10px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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

# ─── 3. 로그인 및 F5 새로고침 방어 티켓 유지 ──────────────────────────────────
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
        st.session_state['user_name'] = ""

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
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

if not st.session_state['logged_in']: show_login()

# ─── 4. 데이터베이스 및 전역 변수 설정 ──────────────────────────────────────────
DB_PATH = "defog_v17_master.db" 
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

def safe_get(df, possible_keywords, default_val):
    for col in df.columns:
        norm_col = str(col).lower().replace(' ', '').replace('_', '').replace('(', '').replace(')', '').replace('원', '').strip()
        for keyword in possible_keywords:
            if keyword in norm_col:
                return df[col].fillna(default_val)
    return pd.Series([default_val] * len(df))

init_db()

# ─── 5. 사이드바 및 네비게이션 메뉴 ──────────────────────────────────────────
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    else: st.markdown("<h2 style='text-align: center; color: #1e3a8a;'>DEFOG</h2>", unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    st.markdown("---")
    
    MENU_1 = "📝 프로젝트 파이프라인 관리"
    MENU_2 = "🤝 주간 영업 회의 보드"
    MENU_3 = "📊 성과 대시보드"
    MENU_4 = "⚙️ DB 불러오기 / 내보내기"
    
    menu = st.radio("메뉴 이동", [MENU_1, MENU_2, MENU_3, MENU_4], label_visibility="collapsed")
    
    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear() 
        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("🔗 **팀원 초대용 안전 링크**\n\n아래 주소를 복사해서 공유하세요.")
    st.code("https://defog-sales-app.streamlit.app/", language="text")

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리
# ═════════════════════════════════════════════════════════════════════════════
if menu == MENU_1:
    with st.expander("🚀 [클릭] 스마트 신규 프로젝트 등록", expanded=False):
        with st.form("quick_add_form"):
            f1, f2, f3, f4 = st.columns(4)
            with f1: f_no = st.text_input("PJT No")
            with f2: f_comp = st.text_input("수주업체 *")
            with f3: f_name = st.text_input("프로젝트명 *")
            with f4: f_amt = st.number_input("수주금액 (원)", min_value=0, step=1000000)
            
            f5, f6, f7, f8 = st.columns(4)
            with f5: f_cat = st.selectbox("구분", ["PRODUCT", "SOLUTION", "기타"])
            with f6: f_stat = st.selectbox("상태", STATUS_LIST)
            with f7: f_mgr_sel = st.selectbox("담당자 선택", DEFAULT_MANAGERS + ["== 직접 입력 =="])
            with f8: f_mgr_cust = st.text_input("담당자 직접 입력 (선택 시)")
                
            f9, f10 = st.columns([1, 2])
            with f9: f_prod = st.text_input("제안제품")
            with f10: f_rem = st.text_input("비고 (특이사항)")
            
            if st.form_submit_button("등록 완료", use_container_width=True):
                if f_comp and f_name:
                    final_mgr = f_mgr_cust if f_mgr_sel == "== 직접 입력 ==" and f_mgr_cust else f_mgr_sel
                    final_mgr = final_mgr if final_mgr != "== 직접 입력 ==" else "-"
                    
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO projects (pjt_no, company, pjt_name, category, status, manager, proposed_product, amount, remarks, updated_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (f_no, f_comp, f_name, f_cat, f_stat, final_mgr, f_prod, int(f_amt), f_rem, get_kst_date()))
                    conn.commit()
                    conn.close()
                    st.success("✅ 프로젝트가 등록되었습니다!")
                    st.rerun()
                else: st.error("수주업체와 프로젝트명은 필수입니다.")

    st.markdown("<p style='color:#64748b;'>💡 <b>Tip:</b> 표 안을 더블클릭해 직접 수정할 수 있습니다. 금액은 숫자만 치면 알아서 콤마가 붙습니다.</p>", unsafe_allow_html=True)
    
    df_current = get_db_data()
    df_current['display_amount'] = df_current['amount'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) and str(x).strip() != '' else "0")
    
    ORDERED_COLS = ["pjt_no", "company", "pjt_name", "category", "status", "manager", "proposed_product", "display_amount", "remarks", "updated_at"]
    
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        height=550,
        column_order=ORDERED_COLS,
        column_config={
            "amount": None, 
            "display_amount": st.column_config.TextColumn("수주금액 (원) ✏️", width="medium"), 
            "pjt_no": st.column_config.TextColumn("PJT No", width="small"),
            "company": st.column_config.TextColumn("수주업체", width="medium"),
            "pjt_name": st.column_config.TextColumn("프로젝트명", width="large"),
            "category": st.column_config.SelectboxColumn("구분", options=["PRODUCT", "SOLUTION", "기타"], width="small"),
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST, width="small"),
            "manager": st.column_config.TextColumn("담당자", width="small"),
            "proposed_product": st.column_config.TextColumn("제안제품", width="medium"),
            "remarks": st.column_config.TextColumn("비고", width="large"),
            "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True, width="small")
        },
        key="main_editor"
    )

    # ⭐ 핵심 디테일: 고급스러운 종합 요약 배너 추가
    total_pipeline_amt = df_current['amount'].sum()
    total_project_cnt = len(df_current)
    
    st.markdown(f"""
        <div class="summary-banner">
            <div>
                <h4 style="opacity: 0.9; margin-bottom: 5px;">📊 현재 파이프라인 종합 요약</h4>
                <span style="font-size: 14px;">저장된 전체 프로젝트 기준</span>
            </div>
            <div style="text-align: right;">
                <h3 style="font-size: 28px; letter-spacing: 1px;">₩ {total_pipeline_amt:,} <span style="font-size: 18px; font-weight: 400; opacity: 0.9;">({total_project_cnt}건)</span></h3>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("💾 데이터베이스 저장 (변경사항 확정)", type="primary", use_container_width=True):
        try:
            edited_df['amount'] = edited_df['display_amount'].astype(str).str.replace(r'[^\d\-]', '', regex=True)
            edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0).astype(int)
            edited_df = edited_df.drop(columns=['display_amount'])
            edited_df.fillna("-", inplace=True)
            edited_df['updated_at'] = get_kst_date()
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            edited_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            st.success("✅ 저장이 완벽하게 완료되었습니다.")
            st.rerun()
        except Exception as e: st.error(f"저장 중 오류: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 보드 
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    st.markdown("<p style='color:gray;'>💡 미팅 시 즉시 검색하여 보고하세요. 큰 건은 👑 VIP, 🔥 HOT 뱃지가 자동으로 붙습니다.</p>", unsafe_allow_html=True)
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
            
        def get_badge(amt):
            if amt >= 1000000000: return "👑 VIP"
            elif amt >= 100000000: return "🔥 HOT"
            else: return "⭐ 일반"
            
        meet_filtered['중요도'] = meet_filtered['amount'].apply(get_badge)
        meet_filtered['수주금액'] = meet_filtered['amount'].apply(lambda x: f"₩ {int(x):,}")
        
        meet_show = meet_filtered[['updated_at', 'status', '중요도', 'company', 'pjt_name', 'manager', 'proposed_product', '수주금액', 'remarks']]
        meet_show.columns = ['최종업데이트', '상태', '중요도', '수주업체', '프로젝트명', '담당자', '제안제품', '수주금액', '비고']
        
        st.dataframe(meet_show.sort_values(by='최종업데이트', ascending=False).reset_index(drop=True), use_container_width=True, height=500)
    else: st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_dash = get_db_data()
    if df_dash.empty: st.info("데이터가 없습니다.")
    else:
        won_amt = df_dash[df_dash['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_dash[~df_dash['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        
        TARGET_AMOUNT = 10000000000 
        progress_pct = min(won_amt / TARGET_AMOUNT, 1.0) if TARGET_AMOUNT > 0 else 0
        
        st.markdown(f"#### 🎯 2026년 DEFOG 팀 수주 목표 달성률 <span style='font-size:16px; color:#64748b;'>(목표: 100억)</span>", unsafe_allow_html=True)
        st.progress(progress_pct)
        st.markdown(f"<p style='text-align:right; font-weight:bold; color:#10b981;'>{progress_pct*100:.1f}% 달성 (₩ {won_amt:,}원)</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><small>현재 진행/견적 금액</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 확정액</small><h3 style='color:#10b981;'>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인 건수</small><h3 style='color:#f59e0b;'>{len(df_dash)} 건</h3></div>", unsafe_allow_html=True)
        closed_won = len(df_dash[df_dash['status'] == "🟢 완료"])
        closed_lost = len(df_dash[df_dash['status'] == "🔴 Drop"])
        win_rate = (closed_won / (closed_won + closed_lost) * 100) if (closed_won + closed_lost) > 0 else 0
        m4.markdown(f"<div class='metric-card' style='border-top-color:#8b5cf6;'><small>수주 성공률</small><h3 style='color:#8b5cf6;'>{win_rate:.1f}%</h3></div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            fun_d = df_dash.groupby('status')['amount'].sum().reset_index().sort_values('amount', ascending=False)
            st.plotly_chart(px.funnel(fun_d, x='amount', y='status', title="단계별 규모 퍼널"), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(df_dash, x='manager', y='amount', color='status', title="담당자별 성과"), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 시스템 및 데이터 관리
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    c_up, c_down = st.columns(2)
    with c_up:
        st.markdown("#### 📥 기존 엑셀 대량 등록")
        
        header_row = st.number_input("📌 엑셀 파일에서 '수주업체', '금액' 등 제목이 있는 행(Row) 번호를 입력하세요.", min_value=1, value=1)
        st.caption("예: 1~2행에 '파이프라인 현황' 같은 큰 제목이 있고, 3행부터 진짜 표 제목이 시작된다면 '3'을 입력하세요.")
        
        excel_file = st.file_uploader("파일을 선택하세요", type=['csv', 'xlsx'])
        if excel_file and st.button("🚀 데이터 동기화", use_container_width=True):
            try:
                skip_rows = header_row - 1
                if excel_file.name.endswith('.csv'):
                    raw = pd.read_csv(excel_file, encoding='utf-8-sig', skiprows=skip_rows)
                else:
                    raw = pd.read_excel(excel_file, skiprows=skip_rows)
                
                raw = raw.dropna(how='all')
                
                mapped = pd.DataFrame()
                mapped["pjt_no"] = safe_get(raw, ['pjt', 'no', '번호', '순번', 'id'], '-')
                mapped["company"] = safe_get(raw, ['company', '업체', '고객사', '발주처', '기관', '회사'], '-')
                mapped["pjt_name"] = safe_get(raw, ['name', '프로젝트', '사업명', '건명', '내용', '타이틀'], '-')
                mapped["category"] = safe_get(raw, ['category', '구분', '종류', '분야'], 'PRODUCT')
                
                status_series = safe_get(raw, ['status', '상태', '진행', '현황'], '견적')
                mapped["status"] = status_series.apply(clean_status)
                
                mapped["manager"] = safe_get(raw, ['manager', '담당자', '관리자', '영업', '대표', '이름', '사원'], '-')
                mapped["proposed_product"] = safe_get(raw, ['product', '제품', '품목', '장비', '모델', '제안'], '-')
                
                amt_series = safe_get(raw, ['amount', '금액', '매출', '규모', '원', '예산', 'price'], 0)
                if amt_series.dtype == object:
                    amt_series = amt_series.astype(str).str.replace(r'[^\d\-]', '', regex=True)
                mapped["amount"] = pd.to_numeric(amt_series, errors='coerce').fillna(0).astype(int)
                
                mapped["remarks"] = safe_get(raw, ['remarks', '비고', '특이', '이슈', '메모'], '-')
                mapped["updated_at"] = get_kst_date() 
                
                # ⭐ 핵심 패치: 엑셀 파일 맨 밑에 있던 '합계' 줄이 데이터로 들어가지 않게 완벽 차단!
                mapped = mapped[~mapped['company'].astype(str).str.contains('합계|총계|총액', na=False)]
                mapped = mapped[~mapped['pjt_name'].astype(str).str.contains('합계|총계|총액', na=False)]
                
                conn = sqlite3.connect(DB_PATH)
                mapped.to_sql('projects', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
                st.success("🎉 합계 데이터 등 찌꺼기 없이 완벽하게 데이터가 통합되었습니다!"); st.rerun()
            except Exception as e:
                st.error(f"업로드 중 에러가 발생했습니다: {e}")
                
    with c_down:
        st.markdown("#### 📤 엑셀 전체 백업 다운로드")
        if st.button("🔄 최신 백업본 생성", use_container_width=True):
            df_e = get_db_data(); out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                df_e.to_excel(w, index=False, sheet_name="파이프라인")
                sh = w.sheets['파이프라인']; idx = df_e.columns.get_loc('amount') + 1 
                for r in range(2, len(df_e) + 2): sh.cell(row=r, column=idx).number_format = '"₩" #,##0'
            st.download_button("📥 백업 파일 다운로드", out.getvalue(), f"DEFOG_DB_{get_kst_date()}.xlsx", use_container_width=True)
