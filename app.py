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

def get_kst_datetime():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")

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
    .comment-box {
        background: #f8fafc; border-left: 3px solid #2563eb;
        border-radius: 0 8px 8px 0; padding: 10px 14px; margin-bottom: 8px;
    }
    .comment-meta { font-size: 11px; color: #94a3b8; margin-bottom: 3px; }
    .comment-text { font-size: 14px; color: #1e293b; }
    .log-row {
        background: white; border-radius: 8px; padding: 10px 14px;
        margin-bottom: 6px; border-left: 4px solid #2563eb;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .log-row-drop { border-left-color: #ef4444; }
    .log-row-done { border-left-color: #10b981; }
    .progress-wrap {
        background: white; border-radius: 12px; padding: 18px 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    .progress-bar-bg { background: #e2e8f0; border-radius: 999px; height: 14px; overflow: hidden; margin-top: 8px; }
    .progress-bar-fill { height: 14px; border-radius: 999px; }
    </style>
    """, unsafe_allow_html=True)

# ─── 2. 팀원 계정 및 로그인 관리 ─────────────────────────────────────────────
USERS = {
    "ceo":     ("대표님",       "defog!ceo",     "admin"),
    "leader1": ("김원중 팀장님", "defog!leader1", "leader"),
    "leader2": ("김용신 팀장님", "defog!leader2", "leader"),
    "manager": ("팀원",          "defog!manager", "member")
}
OUR_MEMBERS = ["김원중 팀장님", "김용신 팀장님", "팀원", "대표님", "-"]

if 'logged_in' not in st.session_state:
    ticket = st.query_params.get("ticket", "")
    is_valid_ticket = False
    for uid in USERS:
        if ticket == f"defog_auth_{uid}_valid":
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = USERS[uid][0]
            st.session_state['user_role'] = USERS[uid][2]
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
                    st.session_state['logged_in'] = True
                    st.session_state['user_name'] = USERS[u_id][0]
                    st.session_state['user_role'] = USERS[u_id][2]
                    st.query_params["ticket"] = f"defog_auth_{u_id}_valid"
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    st.stop()

# ─── 3. 데이터베이스 초기화 (v30 구조) ─────────────────────────────────────
DB_PATH = "defog_v30.db"
STATUS_LIST = ["🔵 견적", "🟡 진행중", "🟠 납품대기중", "🟢 완료", "🔴 Drop"]
DROP_REASONS = ["가격 경쟁 패배", "예산 삭감/취소", "경쟁사 선정", "고객 요구사항 불일치", "내부 사정", "기타"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 메인 프로젝트 테이블 (our_manager, drop_reason 컬럼 추가)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            pjt_no TEXT, company TEXT, pjt_name TEXT, category TEXT, product_family TEXT,
            status TEXT, our_manager TEXT, client_manager TEXT, quote_date TEXT,
            amount INTEGER, drop_reason TEXT, remarks TEXT, updated_at TEXT
        )
    """)
    # 상태 변경 이력 로그
    conn.execute("""
        CREATE TABLE IF NOT EXISTS status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pjt_no TEXT, company TEXT, pjt_name TEXT,
            from_status TEXT, to_status TEXT,
            changed_by TEXT, changed_at TEXT, drop_reason TEXT
        )
    """)
    # 프로젝트별 코멘트
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pjt_key TEXT, author TEXT, content TEXT, created_at TEXT
        )
    """)
    # 월별 목표
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_targets (
            year_month TEXT PRIMARY KEY, target_amount INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_db_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM projects", conn)
    conn.close()
    return df

def get_comments(pjt_key):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM comments WHERE pjt_key=? ORDER BY created_at DESC", conn, params=[pjt_key])
    conn.close()
    return df

def add_comment(pjt_key, author, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO comments (pjt_key, author, content, created_at) VALUES (?,?,?,?)",
                 (pjt_key, author, content, get_kst_datetime()))
    conn.commit(); conn.close()

def get_status_log():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM status_log ORDER BY changed_at DESC", conn)
    conn.close()
    return df

def log_status_change(pjt_no, company, pjt_name, from_s, to_s, changed_by, drop_reason=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO status_log (pjt_no,company,pjt_name,from_status,to_status,changed_by,changed_at,drop_reason)
                    VALUES (?,?,?,?,?,?,?,?)""",
                 (pjt_no, company, pjt_name, from_s, to_s, changed_by, get_kst_datetime(), drop_reason))
    conn.commit(); conn.close()

def get_monthly_target(ym):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT target_amount FROM monthly_targets WHERE year_month=?", (ym,)).fetchone()
    conn.close()
    return row[0] if row else 0

def set_monthly_target(ym, amount):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO monthly_targets VALUES (?,?)", (ym, amount))
    conn.commit(); conn.close()

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
    elif "Drop" in text or "취소" in text or "드롭" in text: return "🔴 Drop"
    else: return "🔵 견적"

init_db()

# ─── 4. 사이드바 및 네비게이션 설정 ──────────────────────────────────────────
MENU_1 = "📝 프로젝트 파이프라인 관리"
MENU_2 = "🤝 주간 영업 회의 보드"
MENU_3 = "📊 성과 대시보드"
MENU_4 = "💬 프로젝트 코멘트"
MENU_5 = "📋 상태 변경 이력"
MENU_6 = "📄 주간 리포트 생성"
MENU_7 = "⚙️ 데이터 불러오기 / 내보내기"

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.markdown(f"👤 **{st.session_state['user_name']}** 접속중")
    st.markdown("---")
    menu = st.radio("메뉴 이동", [MENU_1, MENU_2, MENU_3, MENU_4, MENU_5, MENU_6, MENU_7], label_visibility="collapsed")
    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.query_params.clear()
        st.rerun()

st.markdown(f"<h2 style='color:#1e3a8a; font-weight:800; margin-bottom: 30px;'>{menu}</h2>", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 1] 프로젝트 파이프라인 관리
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
            with f8: f_our = st.selectbox("우리 담당자 *", OUR_MEMBERS)

            f9, f10 = st.columns(2)
            with f9: f_clt = st.text_input("상대 담당자")
            with f10: f_date = st.date_input("최초 견적일", value=datetime.now())

            f_drop = ""
            if f_stat == "🔴 Drop":
                f_drop = st.selectbox("🔴 Drop 사유 *", DROP_REASONS)

            f_rem = st.text_input("비고 (특이사항)")

            if st.form_submit_button("등록 완료", use_container_width=True):
                if f_comp and f_name:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (f_no, f_comp, f_name, f_cat, f_pf, f_stat, f_our, f_clt,
                          f_date.strftime("%Y-%m-%d"), int(f_amt), f_drop, f_rem, get_kst_date()))
                    conn.commit(); conn.close()
                    log_status_change(f_no, f_comp, f_name, "-", f_stat, st.session_state['user_name'], f_drop)
                    st.success("✅ 프로젝트가 등록되었습니다!")
                    st.rerun()
                else: st.error("수주업체와 프로젝트명은 필수입니다.")

    df_current = get_db_data()

    # 담당자 / 상태 필터
    fc1, fc2 = st.columns([1, 3])
    with fc1: filter_mgr = st.selectbox("👤 담당자 필터", ["전체"] + OUR_MEMBERS[:-1])
    with fc2: filter_status = st.multiselect("📌 상태 필터", STATUS_LIST, default=STATUS_LIST)

    df_view = df_current.copy()
    if filter_mgr != "전체": df_view = df_view[df_view['our_manager'] == filter_mgr]
    df_view = df_view[df_view['status'].isin(filter_status)]

    ORDERED_COLS = ["pjt_no", "company", "pjt_name", "product_family", "category", "status",
                    "our_manager", "client_manager", "quote_date", "amount", "drop_reason", "remarks", "updated_at"]

    # 누락 컬럼 보정
    for col in ORDERED_COLS:
        if col not in df_view.columns: df_view[col] = "-"

    edited_df = st.data_editor(
        df_view,
        num_rows="dynamic",
        use_container_width=True,
        height=500,
        column_order=ORDERED_COLS,
        column_config={
            "pjt_no": "PJT No", "company": "수주업체", "pjt_name": "프로젝트명",
            "product_family": "제품군", "category": "구분",
            "status": st.column_config.SelectboxColumn("상태", options=STATUS_LIST),
            "our_manager": st.column_config.SelectboxColumn("우리 담당자", options=OUR_MEMBERS),
            "client_manager": "상대 담당", "quote_date": "견적일",
            "amount": st.column_config.NumberColumn("수주금액 (원)", format="%,d"),
            "drop_reason": st.column_config.SelectboxColumn("Drop 사유", options=[""] + DROP_REASONS),
            "remarks": "비고",
            "updated_at": st.column_config.TextColumn("최종 업데이트", disabled=True)
        },
        key="main_editor"
    )

    if st.button("💾 변경사항 및 삭제 내용 저장 (DB 확정)", type="primary", use_container_width=True):
        try:
            # 상태 변경 이력 감지
            if not df_current.empty:
                old_idx = df_current.set_index(['company', 'pjt_name'])
                for _, row in edited_df.iterrows():
                    key = (str(row.get('company', '')), str(row.get('pjt_name', '')))
                    if key in old_idx.index:
                        old_status = old_idx.loc[key, 'status']
                        if isinstance(old_status, pd.Series): old_status = old_status.iloc[0]
                        new_status = row.get('status', '')
                        if old_status != new_status:
                            drop_r = row.get('drop_reason', '') if new_status == "🔴 Drop" else ''
                            log_status_change(row.get('pjt_no',''), row.get('company',''), row.get('pjt_name',''),
                                              old_status, new_status, st.session_state['user_name'], drop_r)

            # Drop 사유 없는 건 경고
            drop_no_reason = edited_df[
                (edited_df['status'] == "🔴 Drop") &
                (edited_df['drop_reason'].isna() | edited_df['drop_reason'].isin(["", "-"]))
            ]
            if not drop_no_reason.empty:
                st.warning(f"⚠️ Drop 사유가 없는 프로젝트가 {len(drop_no_reason)}건 있습니다. 사유를 입력해 주세요.")

            final_df = edited_df.fillna("-")
            final_df['amount'] = pd.to_numeric(final_df['amount'], errors='coerce').fillna(0).astype(int)
            final_df['updated_at'] = get_kst_date()

            # 필터된 경우 나머지 행과 합치기
            if filter_mgr != "전체" or len(filter_status) < len(STATUS_LIST):
                remaining = df_current[~df_current.index.isin(df_view.index)]
                for col in ORDERED_COLS:
                    if col not in remaining.columns: remaining[col] = "-"
                final_df = pd.concat([final_df, remaining], ignore_index=True)

            for col in ORDERED_COLS:
                if col not in final_df.columns: final_df[col] = "-"
            final_df = final_df[ORDERED_COLS]

            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            final_df.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()
            st.success("✅ 모든 변경사항 및 삭제가 완벽히 저장되었습니다.")
            st.rerun()
        except Exception as e: st.error(f"저장 중 오류: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 2] 주간 영업 회의 보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_2:
    st.markdown("<p style='color:gray;'>💡 미팅 시 즉시 검색하여 보고하세요. (읽기 전용)</p>", unsafe_allow_html=True)
    df_meet = get_db_data()
    if not df_meet.empty:
        mc1, mc2, mc3 = st.columns([2, 1, 1])
        with mc1: search_query = st.text_input("🔍 수주업체, 프로젝트명 또는 상대담당자 검색", placeholder="키워드 입력")
        with mc2: filter_our = st.selectbox("👤 우리 담당자", ["전체"] + OUR_MEMBERS[:-1])
        with mc3: sel_status = st.multiselect("📌 상태 필터링", STATUS_LIST, default=STATUS_LIST)

        meet_filtered = df_meet[df_meet['status'].isin(sel_status)]
        if filter_our != "전체": meet_filtered = meet_filtered[meet_filtered['our_manager'] == filter_our]
        if search_query:
            meet_filtered = meet_filtered[
                meet_filtered['company'].str.contains(search_query, na=False, case=False) |
                meet_filtered['pjt_name'].str.contains(search_query, na=False, case=False) |
                meet_filtered['client_manager'].str.contains(search_query, na=False, case=False)
            ]

        meet_filtered = meet_filtered.copy()
        meet_filtered['수주금액'] = meet_filtered['amount'].apply(lambda x: f"₩ {int(x):,}")

        meet_show = meet_filtered[['updated_at', 'status', 'our_manager', 'company', 'pjt_name',
                                    'product_family', 'client_manager', 'quote_date', '수주금액', 'remarks']]
        meet_show.columns = ['최종업데이트', '상태', '우리담당', '수주업체', '프로젝트명', '제품군', '상대담당', '견적일', '수주금액', '비고']
        st.dataframe(meet_show.sort_values(by='최종업데이트', ascending=False).reset_index(drop=True),
                     use_container_width=True, height=500)
        st.markdown(f"<p style='color:gray; text-align:right; font-size:12px;'>총 {len(meet_filtered)}건 | 합계 ₩ {meet_filtered['amount'].sum():,}</p>",
                    unsafe_allow_html=True)
    else: st.info("데이터가 존재하지 않습니다.")

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 3] 경영진 성과 대시보드
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_3:
    df_dash = get_db_data()
    if df_dash.empty: st.info("데이터가 존재하지 않습니다.")
    else:
        this_ym = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m")
        current_target = get_monthly_target(this_ym)

        # 목표 설정 (팀장/대표)
        if st.session_state.get('user_role') in ['admin', 'leader']:
            with st.expander("🎯 이번 달 수주 목표 설정", expanded=(current_target == 0)):
                with st.form("target_form"):
                    new_target = st.number_input("목표 금액 (원)", min_value=0, value=current_target, step=10000000)
                    if st.form_submit_button("저장", use_container_width=True):
                        set_monthly_target(this_ym, int(new_target))
                        st.success("✅ 목표가 저장되었습니다!")
                        st.rerun()

        won_amt  = df_dash[df_dash['status'] == "🟢 완료"]['amount'].sum()
        active_amt = df_dash[~df_dash['status'].isin(["🟢 완료", "🔴 Drop"])]['amount'].sum()
        drop_cnt = len(df_dash[df_dash['status'] == "🔴 Drop"])
        drop_rate = round(drop_cnt / len(df_dash) * 100, 1) if len(df_dash) > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><small>현재 진행 금액</small><h3>₩ {active_amt:,}</h3></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card' style='border-top-color:#10b981;'><small>올해 수주 확정액</small><h3>₩ {won_amt:,}</h3></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card' style='border-top-color:#f59e0b;'><small>총 파이프라인 건수</small><h3>{len(df_dash)} 건</h3></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='metric-card' style='border-top-color:#ef4444;'><small>Drop 비율</small><h3>{drop_rate}%</h3></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 목표 달성률 바
        if current_target > 0:
            pct = min(won_amt / current_target * 100, 100)
            color = "#10b981" if pct >= 80 else "#f59e0b" if pct >= 50 else "#ef4444"
            st.markdown(f"""
            <div class='progress-wrap'>
                <div style='display:flex; justify-content:space-between;'>
                    <b>🎯 {this_ym} 목표 달성률</b>
                    <b style='color:{color};'>{pct:.1f}%</b>
                </div>
                <div style='color:gray; font-size:13px; margin:4px 0;'>₩ {won_amt:,} / 목표 ₩ {current_target:,}</div>
                <div class='progress-bar-bg'>
                    <div class='progress-bar-fill' style='width:{pct}%; background:{color};'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            pf_data = df_dash.groupby('product_family')['amount'].sum().reset_index()
            st.plotly_chart(px.pie(pf_data, values='amount', names='product_family',
                                   title="📦 제품군별 비중 (금액 기준)", hole=0.4), use_container_width=True)
        with c2:
            # 담당자별 수주 확정액
            mgr_data = df_dash[df_dash['status'] == "🟢 완료"].groupby('our_manager')['amount'].sum().reset_index()
            mgr_data.columns = ['담당자', '수주금액']
            if not mgr_data.empty:
                st.plotly_chart(px.bar(mgr_data, x='담당자', y='수주금액',
                                       title="👤 담당자별 수주 확정액",
                                       color='수주금액', color_continuous_scale='Blues'), use_container_width=True)

        st.plotly_chart(px.bar(df_dash, x='company', y='amount', color='status',
                                title="🏢 업체별 영업 성과 규모"), use_container_width=True)

        # Drop 사유 분석
        drop_df = df_dash[(df_dash['status'] == "🔴 Drop") & df_dash['drop_reason'].notna() & ~df_dash['drop_reason'].isin(["-", ""])]
        if not drop_df.empty:
            dr_data = drop_df['drop_reason'].value_counts().reset_index()
            dr_data.columns = ['사유', '건수']
            st.plotly_chart(px.bar(dr_data, x='사유', y='건수',
                                   title="🔴 Drop 사유 분석", color='건수',
                                   color_continuous_scale='Reds'), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 4] 프로젝트 코멘트
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_4:
    st.markdown("<p style='color:gray;'>💡 각 프로젝트에 맥락 메모를 남기세요. 팀원 모두가 볼 수 있습니다.</p>", unsafe_allow_html=True)
    df_cmt = get_db_data()

    if df_cmt.empty:
        st.info("등록된 프로젝트가 없습니다.")
    else:
        df_cmt['label'] = df_cmt['company'] + "  |  " + df_cmt['pjt_name']
        selected = st.selectbox("📂 프로젝트 선택", df_cmt['label'].tolist())

        if selected:
            row = df_cmt[df_cmt['label'] == selected].iloc[0]
            pjt_key = f"{row['company']}_{row['pjt_name']}"

            st.markdown(f"""
            <div style='background:white; border-radius:10px; padding:14px 18px; margin-bottom:16px;
                        border-left:5px solid #2563eb; box-shadow:0 2px 8px rgba(0,0,0,0.05);'>
                <b style='font-size:15px;'>{row['pjt_name']}</b><br>
                <span style='color:gray; font-size:13px;'>{row['company']} | {row['status']} | 담당: {row.get('our_manager','-')} | ₩ {int(row['amount']):,}</span>
            </div>
            """, unsafe_allow_html=True)

            with st.form("comment_form", clear_on_submit=True):
                new_cmt = st.text_area("💬 코멘트 작성", placeholder="특이사항, 다음 액션, 맥락 등을 남겨주세요.", height=80)
                if st.form_submit_button("등록", use_container_width=True):
                    if new_cmt.strip():
                        add_comment(pjt_key, st.session_state['user_name'], new_cmt.strip())
                        st.success("✅ 등록되었습니다!")
                        st.rerun()
                    else: st.error("내용을 입력해 주세요.")

            cmt_df = get_comments(pjt_key)
            if cmt_df.empty:
                st.markdown("<p style='color:gray;'>아직 코멘트가 없습니다.</p>", unsafe_allow_html=True)
            else:
                st.markdown(f"**💬 코멘트 {len(cmt_df)}개**")
                for _, c in cmt_df.iterrows():
                    st.markdown(f"""
                    <div class='comment-box'>
                        <div class='comment-meta'>👤 {c['author']} · {c['created_at']}</div>
                        <div class='comment-text'>{c['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 5] 상태 변경 이력
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_5:
    st.markdown("<p style='color:gray;'>💡 프로젝트 상태 변경 시 자동으로 기록됩니다.</p>", unsafe_allow_html=True)
    log_df = get_status_log()

    if log_df.empty:
        st.info("변경 이력이 없습니다. 프로젝트 상태를 변경하고 저장하면 자동으로 기록됩니다.")
    else:
        lc1, lc2 = st.columns(2)
        with lc1: filter_who = st.selectbox("변경자 필터", ["전체"] + OUR_MEMBERS[:-1])
        with lc2: filter_to  = st.multiselect("변경된 상태 필터", STATUS_LIST, default=STATUS_LIST)

        flog = log_df[log_df['to_status'].isin(filter_to)]
        if filter_who != "전체": flog = flog[flog['changed_by'] == filter_who]

        st.markdown(f"**총 {len(flog)}건의 변경 이력**")
        for _, row in flog.iterrows():
            drop_r = f" ({row.get('drop_reason','')})" if row.get('drop_reason') and row.get('to_status') == "🔴 Drop" else ""
            css_class = "log-row-drop" if "Drop" in str(row.get('to_status','')) else "log-row-done" if "완료" in str(row.get('to_status','')) else ""
            st.markdown(f"""
            <div class='log-row {css_class}'>
                <span style='font-size:14px;'>
                    <b>{row.get('company','')} | {row.get('pjt_name','')}</b>
                    &nbsp;&nbsp;{row.get('from_status','?')} → {row.get('to_status','?')}{drop_r}
                </span><br>
                <span style='font-size:12px; color:gray;'>👤 {row.get('changed_by','')} · {row.get('changed_at','')}</span>
            </div>
            """, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 6] 주간 리포트 생성
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_6:
    st.markdown("<p style='color:gray;'>💡 버튼 하나로 주간 현황을 뽑아 슬랙 / 카카오에 바로 복붙하세요.</p>", unsafe_allow_html=True)
    df_rep = get_db_data()
    log_rep = get_status_log()

    if df_rep.empty:
        st.info("데이터가 존재하지 않습니다.")
    else:
        today = datetime.utcnow() + timedelta(hours=9)
        week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        won_df   = df_rep[df_rep['status'] == "🟢 완료"]
        active_df = df_rep[~df_rep['status'].isin(["🟢 완료", "🔴 Drop"])]
        drop_df  = df_rep[df_rep['status'] == "🔴 Drop"]

        recent_log = log_rep[log_rep['changed_at'] >= week_ago] if not log_rep.empty else pd.DataFrame()
        new_wk  = recent_log[recent_log['from_status'] == "-"] if not recent_log.empty else pd.DataFrame()
        won_wk  = recent_log[recent_log['to_status'] == "🟢 완료"] if not recent_log.empty else pd.DataFrame()
        drop_wk = recent_log[recent_log['to_status'] == "🔴 Drop"] if not recent_log.empty else pd.DataFrame()

        lines = [
            f"📊 *DEFOG 주간 영업 현황 리포트*",
            f"📅 기준일: {today_str}",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📌 *전체 파이프라인 현황*",
            f"  • 총 프로젝트: {len(df_rep)}건",
            f"  • 진행중 금액: ₩ {active_df['amount'].sum():,}",
            f"  • 수주 확정액: ₩ {won_df['amount'].sum():,} ({len(won_df)}건)",
            f"  • Drop 건수: {len(drop_df)}건",
            f"",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📅 *이번 주 (최근 7일) 변동*",
            f"  • 신규 등록: {len(new_wk)}건",
            f"  • 수주 완료: {len(won_wk)}건",
            f"  • Drop 발생: {len(drop_wk)}건",
        ]

        if not drop_wk.empty:
            lines += ["", "🔴 *이번 주 Drop 건*"]
            for _, r in drop_wk.iterrows():
                rsn = f" ({r.get('drop_reason','')})" if r.get('drop_reason') else ""
                lines.append(f"  • {r.get('company','')} | {r.get('pjt_name','')}{rsn}")

        if not won_wk.empty:
            lines += ["", "🟢 *이번 주 수주 완료*"]
            for _, r in won_wk.iterrows():
                lines.append(f"  • {r.get('company','')} | {r.get('pjt_name','')}")

        if 'our_manager' in df_rep.columns:
            lines += ["", "━━━━━━━━━━━━━━━━━━━━", "👤 *담당자별 현황*"]
            for mgr in [m for m in OUR_MEMBERS if m != "-"]:
                m_df = df_rep[df_rep['our_manager'] == mgr]
                if m_df.empty: continue
                m_act = m_df[~m_df['status'].isin(["🟢 완료", "🔴 Drop"])]
                m_won = m_df[m_df['status'] == "🟢 완료"]
                lines.append(f"  • {mgr}: 진행 {len(m_act)}건 / 완료 {len(m_won)}건 (₩ {m_won['amount'].sum():,})")

        lines += ["", f"— DEFOG 영업 허브 자동 생성"]

        st.text_area("📋 리포트 (전체 선택 후 복사)", value="\n".join(lines), height=500)

        st.markdown("---")
        st.markdown("### 📥 전체 데이터 엑셀 다운로드")
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df_rep.to_excel(writer, index=False, sheet_name='파이프라인')
            if not log_rep.empty: log_rep.to_excel(writer, index=False, sheet_name='변경이력')
        st.download_button("📥 엑셀 다운로드", data=out.getvalue(),
                           file_name=f"defog_report_{today_str}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# [Menu 7] 시스템 및 데이터 관리
# ═════════════════════════════════════════════════════════════════════════════
elif menu == MENU_7:
    st.markdown("### 📥 엑셀 데이터 불러오기")
    h_row = st.number_input("📌 표 제목(Header)이 있는 엑셀 행 번호", min_value=1, value=1)
    f = st.file_uploader("엑셀 파일 선택", type=['xlsx'])

    if f and st.button("🚀 데이터 동기화 시작", use_container_width=True):
        try:
            raw = pd.read_excel(f, skiprows=h_row-1).dropna(how='all')

            mapped = pd.DataFrame()
            mapped["pjt_no"]         = safe_get(raw, ['pjt', 'no', '번호'], '-')
            mapped["company"]        = safe_get(raw, ['업체', '고객사', '수주업체'], '-')
            mapped["pjt_name"]       = safe_get(raw, ['프로젝트', '사업명', '건명'], '-')
            mapped["category"]       = safe_get(raw, ['구분', '종류'], 'PRODUCT')
            mapped["product_family"] = safe_get(raw, ['제품군', '품목', '아이템'], '-')
            mapped["status"]         = safe_get(raw, ['상태', '진행'], '🔵 견적').apply(clean_status)
            mapped["our_manager"]    = safe_get(raw, ['우리담당', '내부담당', '영업담당'], '-')
            mapped["client_manager"] = safe_get(raw, ['상대담당', '고객담당', '업체담당', '담당자'], '-')

            q_date = safe_get(raw, ['견적일', '날짜', '최초견적'], get_kst_date())
            mapped["quote_date"] = q_date.astype(str).str.split(' ').str[0]

            amt_s = safe_get(raw, ['금액', '매출', '수주금액'], 0)
            if amt_s.dtype == object:
                amt_s = amt_s.astype(str).str.replace(r'[^\d]', '', regex=True).replace('', '0')
            mapped["amount"] = pd.to_numeric(amt_s, errors='coerce').fillna(0).astype(int)

            mapped["drop_reason"] = safe_get(raw, ['drop사유', 'drop이유', '취소사유'], '-')
            mapped["remarks"]     = safe_get(raw, ['비고', '특이'], '-')
            mapped["updated_at"]  = get_kst_date()

            db_cols = ["pjt_no", "company", "pjt_name", "category", "product_family",
                       "status", "our_manager", "client_manager", "quote_date",
                       "amount", "drop_reason", "remarks", "updated_at"]
            mapped = mapped[db_cols]

            conn = sqlite3.connect(DB_PATH)
            mapped.to_sql('projects', conn, if_exists='append', index=False)
            conn.commit(); conn.close()

            st.success(f"🎉 {len(mapped)}건 데이터 동기화가 완료되었습니다! 1번 탭에서 내역을 확인해 주세요.")
            st.rerun()
        except Exception as e:
            st.error(f"동기화 오류 발생: {e}")

    if st.session_state.get('user_role') == 'admin':
        st.markdown("---")
        st.markdown("### 🗑️ 전체 데이터 초기화 (대표님 전용)")
        st.warning("⚠️ 아래 버튼은 모든 프로젝트 데이터를 삭제합니다. 신중히 사용하세요.")
        if st.button("🗑️ 전체 초기화", type="secondary", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM projects")
            conn.commit(); conn.close()
            st.success("초기화 완료")
            st.rerun()
