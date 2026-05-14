import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# ─── 1. 페이지 및 완벽한 시각적 테마 (하얀색 아이콘 버그 완전 해결) ─────────────
st.set_page_config(page_title="DEFOG PROJECT MANAGEMENT", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    
    /* 투명해지는 아이콘(휴지통, 플러스 버튼 등) 강제 진한 회색 처리 */
    [data-testid="stDataFrame"] svg { stroke: #475569 !important; fill: #475569 !important; }
    
    .metric-card {
        background: white; padding: 25px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); 
        border-top: 5px solid #2563eb;
    }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 보안 설정 ─────────────────────────────────────────────────────────
USERS = {
    "manager": ("조한세 매니저", "defog!manager"),
    "leader":  ("영업팀장", "defog!leader"),
    "ceo":     ("대표님", "defog!ceo")
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def show_login():
    st.markdown("<div style='text-align: center; padding: 100px 0;'><h1 style='color:#1e3a8a;'>🚀 DEFOG Hub</h1><p style='color:#64748b;'>사내 통합 파이프라인 시스템</p></div>", unsafe_allow_html=True)
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

# ─── 3. 데이터베이스 ────────────────────────────────────────────────────────
DB_PATH = "defog_v6_final.db"

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

init_db()

STATUS_LIST = ["🔵 견적", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]

def clean_status(text):
    text = str(text)
    if "완료" in text: return "🟢 완료"
    elif "대기" in text: return "🟠 납품대기중"
    elif "진행" in text: return "🟡 진행중"
    elif "Drop" in text or "취소" in text: return "🔴 Drop"
    else: return "🔵 견적"

# ─── 4. 메인 UI ──────────────────────────────────────────────────────────
c_h1, c_h2 = st.columns([9, 1])
with c_h1:
    st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800;'>🚀 DEFOG PROJECT MANAGEMENT <span style='font-size:16px; color:#64748b;'>({st.session_state['user_name']} 접속중)</span></h2>", unsafe_allow_html=True)
with c_h2:
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

tabs = st.tabs(["📝 파이프라인 엑셀 편집기", "📊 영업 현황 대시보드", "⚙️ 데이터 엑셀 동기화"])

# [Tab 1] 편집기 (금액 콤마 완벽 해결 버전)
with tabs[0]:
    st.markdown("<p style='color:#64748b;'>💡 <b>Tip:</b> 금액칸에 <b>123456789</b> 처럼 숫자만 대충 치고 [저장]을 누르시면 알아서 <b>123,456,789</b> 로 예쁘게 정리됩니다.</p>", unsafe_allow_html=True)
    
    df_current = get_db_data()
    
    # ⭐ 핵심 해결: 숫자를 강제로 콤마가 찍힌 문자로 변환하여 보여줌
    df_current['display_amount'] = df_current['amount'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) and str(x).strip() != '' else "0")
    
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        height=600,
        column_config={
            "amount": None, # 기존 숫자 전용 열은 안 보이게 숨김
            "display_amount": st.column_config.TextColumn("수주금액 (원)", width="medium"), # 콤마가 찍히는 새 열
            "pjt_no": st.column_config.TextColumn("PJT No", width="small"),
            "company": st.column_config.TextColumn("수주업체", width="medium"),
            "pjt_name": st.column_config.TextColumn("프로젝트명", width="large"),
            "category": st.column_config.SelectboxColumn("구분", options=["PRODUCT", "SOLUTION", "기타"], width="small"),
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST, width="small"),
            "manager": st.column_config.TextColumn("관리자", width="small"),
            "proposed_product": st.column_config.TextColumn("제안제품", width="medium"),
            "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True, width="small")
        },
        key="main_editor"
    )

    if st.button("💾 변경사항 안전하게 저장하기", type="primary", use_container_width=True):
        try:
            # ⭐ 핵심 로직: 사용자가 입력한 값에서 숫자 빼고 다 지운 뒤 다시 정수형으로 DB에 저장
            edited_df['amount'] = edited_df['display_amount'].astype(str).str.replace(r'[^\d\-]', '', regex=True)
            edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0).astype(int)
            edited_df = edited_df.drop(columns=['display_amount']) # 임시 열은 DB 가기 전에 삭제
            edited_df.fillna("-", inplace=True)
            edited_df['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            edited_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            st.success("✅ 금액 콤마 변환 및 데이터 저장이 완벽하게 완료되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")

# [Tab 2] 대시보드
with tabs[1]:
    df = get_db_data()
    if df.empty:
        st.info("현재 등록된 데이터가 없습니다.")
    else:
        won_amt = df[df['status'].str.contains("완료")]['amount'].sum()
        active_amt = df[~df['status'].str.contains("완료|Drop")]['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"<div class='metric-card'><small style='color:#64748b;'>현재 진행중인 사업</small><h2 style='margin:5px 0 0 0; color:#1e3a8a;'>₩ {active_amt:,}</h2></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small style='color:#64748b;'>올해 수주 확정액 (완료)</small><h2 style='margin:5px 0 0 0; color:#10b981;'>₩ {won_amt:,}</h2></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small style='color:#64748b;'>총 파이프라인 관리 건수</small><h2 style='margin:5px 0 0 0; color:#f59e0b;'>{len(df)} 건</h2></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_bar = px.bar(df, x='manager', y='amount', color='status', title="담당자별 누적 영업 금액", 
                             color_discrete_map={"🟢 완료":"#10b981", "🔵 견적":"#3b82f6", "🟡 진행중":"#f59e0b", "🟠 납품대기중":"#f97316", "🔴 Drop":"#ef4444"})
            fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)
        with col_g2:
            fig_pie = px.pie(df, names='status', values='amount', hole=0.5, title="금액 비중별 현재 상태")
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)

# [Tab 3] 데이터 동기화
with tabs[2]:
    c_up, c_down = st.columns(2)
    with c_up:
        st.markdown("#### 📥 기존 엑셀 일괄 업로드")
        excel_file = st.file_uploader("파일을 선택하세요", type=['csv', 'xlsx'])
        if excel_file and st.button("🚀 데이터 동기화 및 맵핑", use_container_width=True):
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
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                mapped.fillna("-", inplace=True)
                conn = sqlite3.connect(DB_PATH)
                mapped.to_sql('projects', conn, if_exists='append', index=False)
                conn.commit()
                conn.close()
                st.success("데이터가 완벽하게 통합되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"업로드 에러: {e}")
                
    with c_down:
        st.markdown("#### 📤 전체 데이터 백업")
        if st.button("🔄 엑셀 파일 만들기", use_container_width=True):
            df_export = get_db_data()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name="파이프라인")
            st.download_button("📥 다운로드 (클릭)", output.getvalue(), f"DEFOG_Pipeline_{datetime.now().strftime('%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
