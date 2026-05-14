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

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리
# ═════════════════════════════════════════════════════════════════════════════
if menu == MENU_1:
    with st.expander("🚀 [클릭] 스마트 신규 프로젝트 등록", expanded=False):
        with st.form("quick_add_form"):
            f1, f2, f3, f4 = st.columns(4)
            with f1: f_no = st.text_input("PJT No (예: PJT-26-001)")
            with f2: f_comp = st.text_input("수주업체 *")
            with f3: f_name = st.text_input("프로젝트명 *")
            with f4: f_amt = st.number_input("수주금액 (원)", min_value=0, step=1000000)
            
            f5, f6, f7, f8 = st.columns(4)
            with f5: f_cat = st.selectbox("구분", ["PRODUCT", "SOLUTION", "기타"])
            with f6: f_stat = st.selectbox("상태", STATUS_LIST)
            with f7: f_mgr_sel = st.selectbox("담당자 선택", DEFAULT_MANAGERS + ["== 직접 입력 =="])
            with f8: f_mgr_cust = st.text_input("담당자 직접 입력 (선택 시)")
                
            f9, f10 = st.columns([1, 2])
            with f9: f_prod = st.text_input("제안제품 (예: INROW / RDC)")
            with f10: f_rem = st.text_input("비고 (특이사항)")
            
            if st.form_submit_button("등록 완료", use_container_width=True):
                if f_comp and f_name:
                    final_mgr = f_mgr_cust if f_mgr_sel == "== 직접 입력 ==" and f_mgr_cust else f_mgr_sel
                    final_mgr = final_mgr if final_mgr != "== 직접 입력 ==" else "-"
                    
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO projects (pjt_no, company, pjt_name, category, status, manager, proposed_product, amount, remarks, updated_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (f_no, f_comp, f_name, f_cat, f_stat, final_mgr, f_prod, int(f_amt), f_rem, datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit()
                    conn.close()
                    st.success("✅ 신규 프로젝트가 등록되었습니다!")
                    st.rerun()
                else: st.error("수주업체와 프로젝트명은 필수입니다.")

    st.markdown("<p style='color:#64748b;'>💡 <b>Tip:</b> 표 안을 더블클릭해 직접 수정할 수 있습니다. 금액은 숫자만 치면 알아서 콤마가 붙습니다.</p>", unsafe_allow_html=True)
    
    df_current = get_db_data()
    df_current['display_amount'] = df_current['amount'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) and str(x).strip() != '' else "0")
    
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        height=600,
        column_config={
            "amount": None, 
            "display_amount": st.column_config.TextColumn("수주금액 (원) ✏️", width="medium"), 
            "pjt_no": st.column_config.TextColumn("PJT No", width="small"),
            "company": st.column_config.TextColumn("수주업체", width="medium"),
            "pjt_name": st.column_config.TextColumn("프로젝트명", width="large"),
            "category": st.column_config.SelectboxColumn("구분", options=["PRODUCT", "SOLUTION", "기타"], width="small"),
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST, width="small"),
            "manager": st.column_config.TextColumn("담당자 (자유입력)", width="small"),
            "proposed_product": st.column_config.TextColumn("제안제품", width="medium"),
            "remarks": st.column_config.TextColumn("비고 (특이사항)", width="large"),
            "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True, width="small")
        },
        key="main_editor"
    )

    if st.button("💾 데이터베이스 저장 (변경사항 확정)", type="primary", use_container_width=True):
        try:
            edited_df['amount'] = edited_df['display_amount'].astype(str).str.replace(r'[^\d\-]', '', regex=True)
            edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0).astype(int)
            edited_df = edited_df.drop(columns=['display_amount'])
            edited_df.fillna("-", inplace=True)
            edited_df['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            edited_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            st.success("✅ 저장 완료! 데이터가 완벽하게 업데이트되었습니다.")
            st.rerun()
        except Exception as e: st.error(f"저장 중 오류: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 보드 
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    st.markdown("<p style='color:gray;'>💡 데이터 손상 걱정 없는 <b>읽기 전용 모드</b>입니다. 미팅 시 즉시 검색하여 보고하세요.</p>", unsafe_allow_html=True)
    
    df_meet = get_db_data()
    if not df_meet.empty:
        search_query = st.text_input("🔍 수주업체 또는 프로젝트명 빠른 검색", placeholder="예: 네이버, 서강대 등 키워드 입력")
        
        col_f1, col_f2 = st.columns([7, 3])
        with col_f1: sel_status = st.multiselect("📌 보고할 상태(Status) 필터링", STATUS_LIST, default=STATUS_LIST)
        with col_f2:
            unique_mgr = df_meet['manager'].unique().tolist()
            sel_mgr = st.multiselect("👨‍💼 담당자 필터링", unique_mgr, default=unique_mgr)
            
        meet_filtered = df_meet[df_meet['status'].isin(sel_status) & df_meet['manager'].isin(sel_mgr)]
        
        if search_query:
            meet_filtered = meet_filtered[meet_filtered['company'].str.contains(search_query, na=False) | meet_filtered['pjt_name'].str.contains(search_query, na=False)]
            
        meet_filtered['수주금액'] = meet_filtered['amount'].apply(lambda x: f"₩ {int(x):,}")
        
        # 비고(remarks) 컬럼 추가 노출
        meet_show = meet_filtered[['updated_at', 'status', 'company', 'pjt_name', 'manager', '수주금액', 'proposed_product', 'remarks']]
        meet_show.columns = ['최종업데이트', '상태', '수주업체', '프로젝트명', '담당자', '수주금액', '제안제품', '비고']
        
        meet_show = meet_show.sort_values(by='최종업데이트', ascending=False).reset_index(drop=True)
        
        st.dataframe(meet_show, use_container_width=True, height=500)
        st.markdown(f"**총 조회 건수:** <span style='color:#2563eb; font-weight:bold;'>{len(meet_show)}건</span> | **조회된 총액:** <span style='color:#10b981; font-weight:bold;'>₩ {meet_filtered['amount'].sum():,}원</span>", unsafe_allow_html=True)
    else:
        st.info("데이터가 없습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_dash = get_db_data()
    if df_dash.empty:
        st.info("현재 등록된 데이터가 없습니다.")
    else:
        won_amt = df_dash[df_dash['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_dash[~df_dash['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><small>현재 진행/견적 금액</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 확정액 (완료)</small><h3 style='color:#10b981;'>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인 관리 건수</small><h3 style='color:#f59e0b;'>{len(df_dash)} 건</h3></div>", unsafe_allow_html=True)
        
        closed_won = len(df_dash[df_dash['status'] == "🟢 완료"])
        closed_lost = len(df_dash[df_dash['status'] == "🔴 Drop"])
        win_rate = (closed_won / (closed_won + closed_lost) * 100) if (closed_won + closed_lost) > 0 else 0
        m4.markdown(f"<div class='metric-card' style='border-top-color:#8b5cf6;'><small>프로젝트 수주 성공률</small><h3 style='color:#8b5cf6;'>{win_rate:.1f}%</h3></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            funnel_data = df_dash.groupby('status')['amount'].sum().reset_index()
            order = {"🔵 견적": 1, "🟡 진행중": 2, "🟠 납품대기중": 3, "🟢 완료": 4, "🔴 Drop": 5}
            funnel_data['order'] = funnel_data['status'].map(order)
            funnel_data = funnel_data.sort_values('order').drop(columns=['order'])
            
            fig_funnel = px.funnel(funnel_data, x='amount', y='status', title="💰 영업 단계별 퍼널 (금액 규모)", color_discrete_sequence=['#2563eb'])
            st.plotly_chart(fig_funnel, use_container_width=True)
            
        with col_g2:
            fig_bar = px.bar(df_dash, x='manager', y='amount', color='status', title="👨‍💼 담당자별 영업 현황 (금액)", 
                             color_discrete_map={"🟢 완료":"#10b981", "🔵 견적":"#3b82f6", "🟡 진행중":"#f59e0b", "🟠 납품대기중":"#f97316", "🔴 Drop":"#ef4444"})
            st.plotly_chart(fig_bar, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 시스템 및 데이터 관리
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    st.info("🚨 클라우드 서버 특성상 장기간 미접속 시 데이터가 초기화될 수 있습니다. **매주 금요일 엑셀 백업을 생활화** 해주세요!")
    c_up, c_down = st.columns(2)
    with c_up:
        st.markdown("#### 📥 엑셀 대량 등록")
        excel_file = st.file_uploader("파일을 선택하세요", type=['csv', 'xlsx'])
        if excel_file and st.button("🚀 데이터 동기화", use_container_width=True):
            try:
                raw = pd.read_csv(excel_file, encoding='utf-8-sig') if excel_file.name.endswith('.csv') else pd.read_excel(excel_file)
                mapped = pd.DataFrame({
                    "pjt_no": raw.get('프로젝트 번호', '-'),
                    "company": raw.get('프로젝트 수주 업체', raw.get('업체명', '-')),
                    "pjt_name": raw.get('프로젝트 명', raw.get('사업명', '-')),
                    "category": raw.get('구분', 'PRODUCT'),
                    "status": raw.get('상태', '견적').apply(clean_status),
                    "manager": raw.get('관리자', raw.get('담당자', '-')),
                    "proposed_product": raw.get('제안 제품', raw.get('제안제품', '-')),
                    "amount": pd.to_numeric(raw.get('수주 금액', raw.get('수주금액', 0)), errors='coerce').fillna(0).astype(int),
                    "remarks": raw.get('비고', raw.get('특이사항', raw.get('핵심 이슈', '-'))),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                mapped.fillna("-", inplace=True)
                conn = sqlite3.connect(DB_PATH)
                mapped.to_sql('projects', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
                st.success("완벽하게 통합되었습니다!")
                st.rerun()
            except Exception as e: st.error(f"업로드 에러: {e}")
                
    with c_down:
        st.markdown("#### 📤 엑셀 백업 다운로드")
        if st.button("🔄 최신 엑셀 백업본 생성", use_container_width=True):
            df_export = get_db_data()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="파이프라인")
                worksheet = writer.sheets['파이프라인']
                amount_col_idx = df_export.columns.get_loc('amount') + 1 
                for row in range(2, len(df_export) + 2):
                    cell = worksheet.cell(row=row, column=amount_col_idx)
                    cell.number_format = '"₩" #,##0'
                    
            st.download_button("📥 백업 다운로드", output.getvalue(), f"DEFOG_Master_DB_{datetime.now().strftime('%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
    st.markdown("---")
    st.markdown("#### 🔗 팀원 공유용 링크 (보안 전용)")
    base_url = "https://defog-sales-app.streamlit.app/" 
    st.code(base_url, language="text")
    st.caption("위의 깨끗한 주소를 복사해서 팀원들에게 전달하세요. (자동 로그인 방지용)")
