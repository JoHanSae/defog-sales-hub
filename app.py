import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import io
import json
import requests
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

st.set_page_config(page_title="DEFOG 영업팀 허브", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")

# ─── 팀원 계정 관리 ────────────────────────────────────────────────────────────
# 비밀번호 변경하려면 아래 USERS 딕셔너리를 수정하세요
# 형식: "아이디": ("이름", "비밀번호")
USERS = {
    "ceo":      ("CEO 대표님", "defog!ceo"),
    "leader":   ("팀장",       "defog!leader"),
    "manager":  ("매니저",     "defog!manager"),
}

def check_login(user_id, password):
    if user_id in USERS:
        name, pw = USERS[user_id]
        if pw == password:
            return name
    return None

def show_login():
    st.markdown("""
    <style>
    .stApp { background: #0f1117; }
    .login-wrap {
        max-width: 400px; margin: 80px auto;
        background: #1a1f2e; border: 1px solid #2d3748;
        border-radius: 16px; padding: 40px 36px;
    }
    .login-logo { font-size: 36px; font-weight: 900; color: #f1f5f9; margin-bottom: 4px; }
    .login-sub  { font-size: 13px; color: #64748b; margin-bottom: 32px; letter-spacing: 0.08em; }
    </style>
    <div class="login-wrap">
        <div class="login-logo">🚀 DEFOG</div>
        <div class="login-sub">영업팀 허브 · 로그인</div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            user_id  = st.text_input("아이디", placeholder="아이디 입력", key="login_id")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력", key="login_pw")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("로그인", use_container_width=True, key="login_btn"):
                name = check_login(user_id.strip(), password.strip())
                if name:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = name
                    st.session_state["user_id"]   = user_id.strip()
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

# ─── 로그인 체크 ───────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login()
    st.stop()  # 로그인 안 되면 아래 코드 전혀 실행 안 됨

# ─── Supabase REST API 설정 (requests 방식 - 추가 설치 불필요) ───
SUPABASE_URL = "https://sicwkainipbnowfenwgz.supabase.co"
SUPABASE_KEY = "sb_publishable_xXKluRjtdt4r55X5H68zRQ_SE5FcMPg"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def db_select(table, order_col="id", desc=False):
    try:
        order = f"{order_col}.desc" if desc else f"{order_col}.asc"
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*&order={order}", headers=HEADERS)
        data = res.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 조회 오류: {e}")
        return pd.DataFrame()

def db_insert(table, data):
    try:
        res = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False

def db_update(table, data, match_col, match_val):
    try:
        res = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}", headers=HEADERS, json=data)
        return res.status_code in [200, 204]
    except Exception as e:
        st.error(f"수정 오류: {e}")
        return False

def db_filter(table, col, op, val):
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*&{col}={op}.{val}", headers=HEADERS)
        data = res.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except:
        return pd.DataFrame()

def log_activity(company, action, detail, author="매니저"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    db_insert("activity_log", {"company": company, "action": action, "detail": detail, "logged_at": now, "author": author})

STAGES = ["잠재고객", "견적요청", "기술협의", "최종조율", "계약완료", "실패/보류"]
STAGE_COLORS = {
    "잠재고객": "#64748b", "견적요청": "#3b82f6", "기술협의": "#f59e0b",
    "최종조율": "#8b5cf6", "계약완료": "#10b981", "실패/보류": "#ef4444",
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Pretendard', -apple-system, sans-serif; }
.stApp { background: #0f1117; color: #e2e8f0; }
[data-testid="stSidebar"] { background: #1a1f2e !important; border-right: 1px solid #2d3748; }
.metric-card { background: linear-gradient(135deg, #1e2535 0%, #252d3d 100%); border: 1px solid #2d3748; border-radius: 12px; padding: 20px 24px; margin-bottom: 12px; }
.metric-label { font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.metric-value { font-size: 28px; font-weight: 800; color: #f1f5f9; }
.metric-sub { font-size: 12px; color: #64748b; margin-top: 4px; }
.section-header { font-size: 22px; font-weight: 800; color: #f1f5f9; margin-bottom: 4px; }
.section-sub { font-size: 14px; color: #64748b; margin-bottom: 20px; }
.alert-urgent { background: #450a0a; border: 1px solid #ef4444; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px; color: #fca5a5; }
.alert-soon { background: #431407; border: 1px solid #f97316; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px; color: #fdba74; }
.stButton > button { background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: 600; }
.stButton > button:hover { background: #2563eb; }
.log-item { background: #1a1f2e; border: 1px solid #2d3748; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }
.log-time { font-size: 11px; color: #64748b; }
.log-action { font-weight: 700; color: #f1f5f9; font-size: 14px; }
.log-detail { color: #94a3b8; font-size: 13px; margin-top: 3px; }
div[data-testid="stSelectbox"] label, div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label, div[data-testid="stTextArea"] label,
div[data-testid="stDateInput"] label { color: #94a3b8 !important; font-size: 13px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──
with st.sidebar:
    user_name = st.session_state.get("user_name", "팀원")
    st.markdown(f"""
    <div style="padding:8px 0 20px;border-bottom:1px solid #2d3748;margin-bottom:20px;">
        <div style="font-size:22px;font-weight:800;color:#f1f5f9;">🚀 DEFOG</div>
        <div style="font-size:11px;color:#64748b;letter-spacing:0.12em;font-weight:600;">영업팀 허브</div>
        <div style="margin-top:12px;background:#252d3d;border-radius:8px;padding:8px 12px;">
            <div style="font-size:12px;color:#94a3b8;">접속 중</div>
            <div style="font-size:14px;font-weight:700;color:#f1f5f9;">👤 {user_name}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    if st.button("🔓 로그아웃", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["user_name"] = ""
        st.rerun()

    menu = st.radio("메뉴", ["📊 대시보드","📋 파이프라인","📄 견적 관리","📝 활동 로그","🔔 팔로업 알림","⚙️ 설정"], label_visibility="collapsed")

    today_str = date.today().strftime("%Y-%m-%d")
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/projects?select=company&follow_up_date=lte.{today_str}&stage=neq.계약완료&stage=neq.실패/보류",
            headers=HEADERS
        )
        urgent_list = [r["company"] for r in res.json()] if res.status_code == 200 else []
    except:
        urgent_list = []

    if urgent_list:
        st.markdown(f"""<div style="margin-top:16px;background:#450a0a;border:1px solid #ef4444;border-radius:8px;padding:10px 14px;font-size:12px;color:#fca5a5;">
            🔴 <b>긴급 팔로업</b> {len(urgent_list)}건<br><span style="opacity:0.7">{', '.join(urgent_list)}</span></div>""", unsafe_allow_html=True)

    st.markdown(f"<div style='margin-top:20px;font-size:11px;color:#475569;'>{datetime.now().strftime('%Y.%m.%d %H:%M')}</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 📊 대시보드
# ══════════════════════════════════════════════════════
if menu == "📊 대시보드":
    st.markdown('<div class="section-header">📊 영업 대시보드</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">전체 파이프라인 현황 및 주요 지표</div>', unsafe_allow_html=True)

    df = db_select("projects")
    quotes_df = db_select("quotes")

    active = df[~df['stage'].isin(['계약완료','실패/보류'])] if len(df) > 0 else pd.DataFrame()
    won    = df[df['stage'] == '계약완료'] if len(df) > 0 else pd.DataFrame()
    total_pipeline = int(active['expected_revenue'].sum()) if len(active) > 0 else 0
    weighted       = int((active['expected_revenue'] * active['close_prob'] / 100).sum()) if len(active) > 0 else 0
    won_revenue    = int(won['expected_revenue'].sum()) if len(won) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">활성 파이프라인</div><div class="metric-value">₩{total_pipeline:,}</div><div class="metric-sub">진행 중 {len(active)}건</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">가중 예상 수익</div><div class="metric-value" style="color:#3b82f6;">₩{weighted:,}</div><div class="metric-sub">클로징 확률 반영 금액</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">계약 완료</div><div class="metric-value" style="color:#10b981;">₩{won_revenue:,}</div><div class="metric-sub">{len(won)}건 클로징</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">발송 견적서</div><div class="metric-value" style="color:#f59e0b;">{len(quotes_df)}</div><div class="metric-sub">누적 견적 건수</div></div>', unsafe_allow_html=True)

    col_a, col_b = st.columns([3,2])
    with col_a:
        if len(active) > 0:
            stage_order = [s for s in STAGES if s not in ['계약완료','실패/보류']]
            sc = active.groupby('stage').agg(합계=('expected_revenue','sum')).reindex(stage_order, fill_value=0).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=sc['stage'], y=sc['합계'], marker_color=[STAGE_COLORS.get(s,'#3b82f6') for s in sc['stage']], text=[f"₩{v:,}" for v in sc['합계']], textposition='outside', textfont=dict(color='#94a3b8', size=11)))
            fig.update_layout(title=dict(text="단계별 파이프라인 금액", font=dict(color='#f1f5f9', size=14)), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'), xaxis=dict(showgrid=False, color='#64748b'), yaxis=dict(showgrid=True, gridcolor='#1e2535', color='#64748b'), margin=dict(t=40,b=20,l=10,r=10), height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("등록된 프로젝트가 없습니다.")
    with col_b:
        if len(df) > 0:
            cat_data = df.groupby('stage')['expected_revenue'].sum().reset_index()
            fig2 = go.Figure(go.Pie(labels=cat_data['stage'], values=cat_data['expected_revenue'], hole=0.55, marker_colors=[STAGE_COLORS.get(s,'#64748b') for s in cat_data['stage']], textfont=dict(size=11, color='white')))
            fig2.update_layout(title=dict(text="단계 비중", font=dict(color='#f1f5f9', size=14)), paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'), legend=dict(font=dict(color='#94a3b8', size=11)), margin=dict(t=40,b=10,l=10,r=10), height=280)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### 📌 최근 영업 활동")
    logs = db_select("activity_log", order_col="id", desc=True)
    if len(logs) == 0:
        st.info("아직 기록된 활동이 없습니다.")
    else:
        for _, row in logs.head(5).iterrows():
            st.markdown(f'<div class="log-item"><div class="log-time">{row["logged_at"]} · {row.get("author","팀원")}</div><div class="log-action">{row["company"]} — {row["action"]}</div><div class="log-detail">{row["detail"]}</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 📋 파이프라인
# ══════════════════════════════════════════════════════
elif menu == "📋 파이프라인":
    st.markdown('<div class="section-header">📋 세일즈 파이프라인</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">딜 진행 현황 및 프로젝트 관리</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["보드 뷰","리스트 뷰 / 편집"])

    with tab1:
        df = db_select("projects")
        cols = st.columns(5)
        board_stages = ["잠재고객","견적요청","기술협의","최종조율","계약완료"]
        for i, stage in enumerate(board_stages):
            stage_df = df[df['stage'] == stage] if len(df) > 0 else pd.DataFrame()
            total = int(stage_df['expected_revenue'].sum()) if len(stage_df) > 0 else 0
            color = STAGE_COLORS.get(stage,'#64748b')
            with cols[i]:
                st.markdown(f'<div style="border-top:3px solid {color};background:#1a1f2e;border-radius:10px;padding:14px;min-height:300px;"><div style="font-size:12px;font-weight:700;color:{color};margin-bottom:4px;">{stage}</div><div style="font-size:11px;color:#64748b;margin-bottom:12px;">{len(stage_df)}건 · ₩{total:,}</div>', unsafe_allow_html=True)
                for _, row in stage_df.iterrows():
                    st.markdown(f'<div style="background:#252d3d;border-left:3px solid {color};border-radius:6px;padding:10px 12px;margin-bottom:8px;"><div style="font-weight:700;color:#f1f5f9;font-size:14px;">{row["company"]}</div><div style="color:#94a3b8;font-size:11px;">{row.get("contact","")}</div><div style="color:#10b981;font-weight:600;font-size:13px;margin-top:6px;">₩{int(row["expected_revenue"]):,}</div><div style="color:#64748b;font-size:11px;">클로징 확률 {row["close_prob"]}%</div></div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        df = db_select("projects")
        col_l, col_r = st.columns([3,2])
        with col_l:
            st.markdown("##### 프로젝트 목록")
            if len(df) > 0:
                disp = df[['company','contact','stage','expected_revenue','close_prob','follow_up_date']].copy()
                disp.columns = ['고객사','담당자','단계','예상매출(만)','클로징%','팔로업일']
                st.dataframe(disp, use_container_width=True, hide_index=True)
                st.markdown("##### ✏️ 단계 변경")
                proj_options = {f"{r['company']} ({r['stage']})": r['id'] for _, r in df.iterrows()}
                sel = st.selectbox("변경할 프로젝트", list(proj_options.keys()), key="stage_sel")
                new_stage = st.selectbox("새 단계", STAGES, key="new_stage")
                if st.button("단계 업데이트"):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db_update("projects", {"stage": new_stage, "updated_at": now}, "id", proj_options[sel])
                    log_activity(sel.split(" (")[0], "단계 변경", f"→ {new_stage}")
                    st.success("✅ 완료!")
                    st.rerun()
            else:
                st.info("등록된 프로젝트가 없습니다.")
        with col_r:
            st.markdown("##### ➕ 프로젝트 추가")
            with st.form("project_form"):
                company   = st.text_input("고객사명 *")
                contact   = st.text_input("담당자")
                stage     = st.selectbox("단계", STAGES)
                revenue   = st.number_input("예상 매출 (만원)", min_value=0, step=100)
                prob      = st.slider("클로징 확률 (%)", 0, 100, 50)
                category  = st.selectbox("업종", ["데이터센터","IDC","금융","제조","유통","공공","기타"])
                follow_up = st.date_input("팔로업 예정일", value=date.today() + timedelta(days=7))
                note      = st.text_area("메모", height=80)
                if st.form_submit_button("💾 저장", use_container_width=True) and company:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    ok = db_insert("projects", {"company":company,"contact":contact,"stage":stage,"expected_revenue":revenue,"close_prob":prob,"category":category,"note":note,"created_at":now,"updated_at":now,"follow_up_date":follow_up.strftime("%Y-%m-%d")})
                    if ok:
                        log_activity(company, "프로젝트 등록", f"단계: {stage}, 예상매출: ₩{revenue:,}만")
                        st.success(f"✅ {company} 등록 완료!")
                        st.rerun()

# ══════════════════════════════════════════════════════
# 📄 견적 관리
# ══════════════════════════════════════════════════════
elif menu == "📄 견적 관리":
    st.markdown('<div class="section-header">📄 견적 관리</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">견적서 생성 · PDF 출력 · 이력 조회</div>', unsafe_allow_html=True)

    tab_q1, tab_q2 = st.tabs(["새 견적 생성","견적 이력"])

    with tab_q1:
        products_df = db_select("products")
        projects_df = db_select("projects")
        col1, col2 = st.columns([2,3])

        with col1:
            st.markdown("##### 📋 기본 정보")
            company_list = projects_df['company'].unique().tolist() if len(projects_df) > 0 else []
            company_select = st.selectbox("고객사", company_list + ["직접 입력"])
            if company_select == "직접 입력":
                company_name = st.text_input("고객사명 직접 입력")
                contact_name = st.text_input("담당자명")
            else:
                company_name = company_select
                c_row = projects_df[projects_df['company'] == company_select]
                contact_name = st.text_input("담당자명", value=c_row['contact'].values[0] if len(c_row) > 0 else "")
            quote_note = st.text_area("특이사항 / 메모", height=80)

        with col2:
            st.markdown("##### 🛒 품목 선택")
            selected_items = []
            if len(products_df) > 0:
                for cat in products_df['category'].unique():
                    cat_p = products_df[products_df['category'] == cat]
                    with st.expander(f"📦 {cat}"):
                        for _, prod in cat_p.iterrows():
                            cc, cq = st.columns([3,1])
                            with cc:
                                checked = st.checkbox(f"**{prod['name']}** — {prod['spec']}\n₩{int(prod['unit_price']):,}/{prod['unit']}", key=f"p_{prod['id']}")
                            with cq:
                                qty = st.number_input("수량", min_value=1, value=1, key=f"q_{prod['id']}", label_visibility="collapsed")
                            if checked:
                                selected_items.append({'name':prod['name'],'spec':prod['spec'],'unit_price':int(prod['unit_price']),'unit':prod['unit'],'qty':int(qty),'total':int(prod['unit_price'])*int(qty)})
            with st.expander("➕ 커스텀 품목 추가"):
                cn = st.text_input("품목명", key="cn")
                cs = st.text_input("사양", key="cs")
                cp_col, cq_col = st.columns(2)
                with cp_col: cp = st.number_input("단가(원)", min_value=0, step=10000, key="cp")
                with cq_col: cqty = st.number_input("수량", min_value=1, value=1, key="cqty")
                if cn:
                    selected_items.append({'name':cn,'spec':cs,'unit_price':int(cp),'unit':'식','qty':int(cqty),'total':int(cp)*int(cqty)})

        if selected_items:
            st.markdown("---")
            st.markdown("##### 📊 견적 요약")
            st.dataframe(pd.DataFrame(selected_items)[['name','spec','qty','unit_price','total']], use_container_width=True, hide_index=True)
            grand_total = sum(i['total'] for i in selected_items)
            vat = int(grand_total * 0.1)
            st.markdown(f"""<div style="background:#1e2535;border:1px solid #2d3748;border-radius:10px;padding:16px 20px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;"><span style="color:#94a3b8;">공급가액</span><span style="color:#f1f5f9;">₩{grand_total:,}</span></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:10px;"><span style="color:#94a3b8;">부가세 (10%)</span><span style="color:#f1f5f9;">₩{vat:,}</span></div>
                <div style="display:flex;justify-content:space-between;border-top:1px solid #2d3748;padding-top:10px;"><span style="color:#f1f5f9;font-weight:700;font-size:16px;">총 합계</span><span style="color:#10b981;font-weight:700;font-size:18px;">₩{grand_total+vat:,}</span></div>
            </div>""", unsafe_allow_html=True)

            col_save, col_pdf = st.columns(2)
            with col_save:
                if st.button("💾 견적 저장", use_container_width=True) and company_name:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    ok = db_insert("quotes", {"company":company_name,"contact":contact_name,"items":json.dumps(selected_items, ensure_ascii=False),"total":grand_total,"status":"발송완료","created_at":now,"note":quote_note})
                    if ok:
                        log_activity(company_name, "견적 발송", f"총액 ₩{grand_total:,}원, {len(selected_items)}개 품목")
                        st.success("✅ 견적 저장 완료!")
                        st.rerun()
            with col_pdf:
                if st.button("📑 PDF 견적서 생성", use_container_width=True):
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
                    styles = getSampleStyleSheet()
                    story = []
                    story.append(Paragraph("견 적 서", ParagraphStyle('t', parent=styles['Title'], fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1e293b'))))
                    story.append(Spacer(1, 4*mm))
                    info_t = Table([["수신",company_name,"담당자",contact_name],["작성일",datetime.now().strftime("%Y년 %m월 %d일"),"유효기간","30일"],["공급사","㈜ 디포그","연락처",""]], colWidths=[25*mm,65*mm,25*mm,55*mm])
                    info_t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#1e293b')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#1e293b')),('TEXTCOLOR',(0,0),(0,-1),colors.white),('TEXTCOLOR',(2,0),(2,-1),colors.white),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cbd5e1')),('PADDING',(0,0),(-1,-1),6)]))
                    story.append(info_t)
                    story.append(Spacer(1, 8*mm))
                    rows = [["품목명","사양","수량","단가","합계"]]
                    for item in selected_items:
                        rows.append([item['name'],item['spec'],str(item['qty']),f"₩{item['unit_price']:,}",f"₩{item['total']:,}"])
                    rows += [["","","","공급가액",f"₩{grand_total:,}"],["","","","부가세(10%)",f"₩{vat:,}"],["","","","합 계",f"₩{grand_total+vat:,}"]]
                    it = Table(rows, colWidths=[45*mm,55*mm,15*mm,30*mm,30*mm])
                    it.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1e293b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cbd5e1')),('ALIGN',(2,0),(-1,-1),'RIGHT'),('PADDING',(0,0),(-1,-1),6),('BACKGROUND',(0,-3),(-1,-1),colors.HexColor('#f8fafc')),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#dbeafe'))]))
                    story.append(it)
                    if quote_note:
                        story.append(Spacer(1,6*mm))
                        story.append(Paragraph(f"비고: {quote_note}", styles['Normal']))
                    doc.build(story)
                    buffer.seek(0)
                    st.download_button("⬇️ PDF 다운로드", data=buffer, file_name=f"견적서_{company_name}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)

    with tab_q2:
        quotes_df = db_select("quotes", order_col="id", desc=True)
        if len(quotes_df) == 0:
            st.info("저장된 견적이 없습니다.")
        else:
            fc = st.text_input("🔍 고객사 검색", placeholder="고객사명 입력...")
            filtered = quotes_df[quotes_df['company'].str.contains(fc, na=False)] if fc else quotes_df
            for _, row in filtered.iterrows():
                with st.expander(f"📄 {row['company']} — ₩{int(row['total']):,} | {str(row['created_at'])[:10]} | {row['status']}"):
                    try:
                        st.dataframe(pd.DataFrame(json.loads(row['items']))[['name','spec','qty','unit_price','total']], hide_index=True)
                    except:
                        st.write(row['items'])
                    if row['note']:
                        st.markdown(f"**메모:** {row['note']}")

# ══════════════════════════════════════════════════════
# 📝 활동 로그
# ══════════════════════════════════════════════════════
elif menu == "📝 활동 로그":
    st.markdown('<div class="section-header">📝 영업 활동 로그</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">팀 활동 기록 및 히스토리 관리</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2,3])
    with col1:
        st.markdown("##### ✏️ 활동 기록 추가")
        with st.form("log_form"):
            projects_df = db_select("projects")
            companies = projects_df['company'].unique().tolist() if len(projects_df) > 0 else []
            log_company = st.selectbox("고객사", companies + ["직접 입력"])
            if log_company == "직접 입력":
                log_company = st.text_input("고객사명")
            log_author = st.text_input("작성자", value=st.session_state.get("user_name", "매니저"))
            log_action = st.selectbox("활동 유형", ["전화 통화","미팅 진행","견적 발송","기술 문의 응대","현장 방문","계약 협의","팔로업 연락","기타"])
            log_detail = st.text_area("내용 상세", height=100)
            if st.form_submit_button("📌 기록 저장", use_container_width=True) and log_company and log_detail:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                ok = db_insert("activity_log", {"company":log_company,"action":log_action,"detail":log_detail,"logged_at":now,"author":log_author})
                if ok:
                    st.success("✅ 활동 기록 완료!")
                    st.rerun()

    with col2:
        st.markdown("##### 📋 활동 이력")
        logs = db_select("activity_log", order_col="id", desc=True)
        if len(logs) == 0:
            st.info("기록된 활동이 없습니다.")
        else:
            search = st.text_input("🔍 검색", placeholder="고객사 또는 내용 검색...")
            if search:
                logs = logs[logs['company'].str.contains(search, na=False) | logs['detail'].str.contains(search, na=False)]
            icons = {"전화 통화":"📞","미팅 진행":"🤝","견적 발송":"📄","기술 문의 응대":"🔧","현장 방문":"🏢","계약 협의":"✍️","팔로업 연락":"🔔","프로젝트 등록":"➕","기타":"📌","단계 변경":"🔄"}
            for _, row in logs.iterrows():
                icon = icons.get(row['action'],"📌")
                st.markdown(f'<div class="log-item"><div style="display:flex;justify-content:space-between;"><div class="log-action">{icon} {row["company"]} — {row["action"]}</div><div class="log-time">{row["logged_at"]}</div></div><div class="log-detail">{row["detail"]}</div><div style="font-size:11px;color:#475569;margin-top:4px;">작성: {row.get("author","")}</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 🔔 팔로업 알림
# ══════════════════════════════════════════════════════
elif menu == "🔔 팔로업 알림":
    st.markdown('<div class="section-header">🔔 팔로업 알림</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">놓치면 안 되는 고객 팔로업 일정</div>', unsafe_allow_html=True)

    df = db_select("projects")
    if len(df) > 0:
        df = df[~df['stage'].isin(['계약완료','실패/보류'])].copy()
        today = date.today()
        df['follow_up_date'] = pd.to_datetime(df['follow_up_date'], errors='coerce').dt.date
        df['days_left'] = df['follow_up_date'].apply(lambda x: (x - today).days if pd.notna(x) else 999)

        overdue   = df[df['days_left'] < 0].sort_values('days_left')
        today_due = df[df['days_left'] == 0]
        soon      = df[(df['days_left'] > 0) & (df['days_left'] <= 7)].sort_values('days_left')
        upcoming  = df[df['days_left'] > 7].sort_values('days_left')

        if len(overdue) > 0:
            st.markdown(f"#### 🔴 기한 초과 ({len(overdue)}건)")
            for _, row in overdue.iterrows():
                st.markdown(f'<div class="alert-urgent"><b>{row["company"]}</b> · {row["contact"]} &nbsp;|&nbsp; {row["stage"]} &nbsp;|&nbsp; ₩{int(row["expected_revenue"]):,}만<br><span style="font-size:11px;">📅 {row["follow_up_date"]} ({abs(int(row["days_left"]))}일 초과)</span></div>', unsafe_allow_html=True)
        if len(today_due) > 0:
            st.markdown(f"#### 🟠 오늘 팔로업 ({len(today_due)}건)")
            for _, row in today_due.iterrows():
                st.markdown(f'<div class="alert-soon"><b>{row["company"]}</b> · {row["contact"]} &nbsp;|&nbsp; {row["stage"]} &nbsp;|&nbsp; ₩{int(row["expected_revenue"]):,}만<br><span style="font-size:11px;">📅 오늘이 팔로업 예정일입니다!</span></div>', unsafe_allow_html=True)
        if len(soon) > 0:
            st.markdown(f"#### 🟡 이번 주 내 ({len(soon)}건)")
            for _, row in soon.iterrows():
                st.markdown(f'<div style="background:#1a2535;border:1px solid #f59e0b;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#fde68a;"><b>{row["company"]}</b> · {row["contact"]} &nbsp;|&nbsp; {row["stage"]} &nbsp;|&nbsp; ₩{int(row["expected_revenue"]):,}만<br><span style="font-size:11px;color:#94a3b8;">📅 {row["follow_up_date"]} (D-{int(row["days_left"])})</span></div>', unsafe_allow_html=True)
        if len(upcoming) > 0:
            st.markdown(f"#### 📅 예정 일정 ({len(upcoming)}건)")
            disp = upcoming[['company','contact','stage','expected_revenue','follow_up_date','days_left']].copy()
            disp.columns = ['고객사','담당자','단계','예상매출(만)','팔로업일','D-day']
            st.dataframe(disp, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("##### 📅 팔로업 일정 변경")
        all_proj = db_select("projects")
        active_proj = all_proj[~all_proj['stage'].isin(['계약완료','실패/보류'])] if len(all_proj) > 0 else pd.DataFrame()
        if len(active_proj) > 0:
            with st.form("fu_form"):
                proj_opts = {f"{r['company']} ({r['stage']})": r['id'] for _, r in active_proj.iterrows()}
                sel_proj = st.selectbox("프로젝트 선택", list(proj_opts.keys()))
                new_date = st.date_input("새 팔로업 날짜", value=date.today() + timedelta(days=7))
                if st.form_submit_button("📅 날짜 업데이트", use_container_width=True):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    db_update("projects", {"follow_up_date": new_date.strftime("%Y-%m-%d"), "updated_at": now}, "id", proj_opts[sel_proj])
                    st.success("✅ 팔로업 날짜 업데이트 완료!")
                    st.rerun()
    else:
        st.info("등록된 프로젝트가 없습니다.")

# ══════════════════════════════════════════════════════
# ⚙️ 설정
# ══════════════════════════════════════════════════════
elif menu == "⚙️ 설정":
    st.markdown('<div class="section-header">⚙️ 설정</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">제품 DB 관리 · 데이터 가져오기/내보내기</div>', unsafe_allow_html=True)

    tab_s1, tab_s2, tab_s3 = st.tabs(["제품 DB","데이터 가져오기","데이터 내보내기"])

    with tab_s1:
        prod_df = db_select("products")
        col_pl, col_pr = st.columns([3,2])
        with col_pl:
            st.markdown("##### 현재 제품 목록")
            if len(prod_df) > 0:
                st.dataframe(prod_df[['category','name','spec','unit_price','unit']], use_container_width=True, hide_index=True)
            else:
                st.info("등록된 제품이 없습니다.")
        with col_pr:
            st.markdown("##### ➕ 제품 추가")
            with st.form("prod_form"):
                p_cat   = st.selectbox("카테고리", ["서버 랙","쿨링 시스템","PDU","UPS","케이블 관리","기타"])
                p_name  = st.text_input("제품명 *")
                p_spec  = st.text_input("사양")
                p_price = st.number_input("단가 (원)", min_value=0, step=10000)
                p_unit  = st.selectbox("단위", ["EA","식","m","set"])
                if st.form_submit_button("저장", use_container_width=True) and p_name:
                    ok = db_insert("products", {"category":p_cat,"name":p_name,"spec":p_spec,"unit_price":p_price,"unit":p_unit})
                    if ok:
                        st.success("✅ 제품 추가 완료!")
                        st.rerun()

    with tab_s2:
        st.markdown("##### 📥 CSV / Excel로 프로젝트 일괄 가져오기")
        st.markdown("`고객사, 담당자, 단계, 예상매출, 클로징%, 업종, 메모, 팔로업일` 형식")
        uploaded = st.file_uploader("파일 선택", type=['csv','xlsx'])
        if uploaded:
            try:
                import_df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                st.dataframe(import_df.head(10))
                if st.button("📥 가져오기 실행"):
                    col_map = {'고객사':'company','담당자':'contact','단계':'stage','예상매출':'expected_revenue','클로징%':'close_prob','업종':'category','메모':'note','팔로업일':'follow_up_date'}
                    import_df = import_df.rename(columns=col_map)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    count = sum(1 for _, row in import_df.iterrows() if db_insert("projects", {"company":row.get('company',''),"contact":row.get('contact',''),"stage":row.get('stage','잠재고객'),"expected_revenue":int(row.get('expected_revenue',0)),"close_prob":int(row.get('close_prob',50)),"category":row.get('category','기타'),"note":row.get('note',''),"created_at":now,"updated_at":now,"follow_up_date":str(row.get('follow_up_date',''))}))
                    st.success(f"✅ {count}건 가져오기 완료!")
                    st.rerun()
            except Exception as e:
                st.error(f"파일 처리 오류: {e}")

    with tab_s3:
        st.markdown("##### 📤 전체 데이터 Excel 내보내기")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            db_select("projects").to_excel(writer, sheet_name='파이프라인', index=False)
            db_select("quotes").to_excel(writer, sheet_name='견적이력', index=False)
            db_select("activity_log").to_excel(writer, sheet_name='활동로그', index=False)
        output.seek(0)
        st.download_button("⬇️ 전체 데이터 Excel 다운로드", data=output, file_name=f"DEFOG_영업데이터_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
