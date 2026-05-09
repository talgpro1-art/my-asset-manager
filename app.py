import streamlit as st
import pandas as pd
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# 🚨 페이지 셋팅은 무조건 가장 먼저!
st.set_page_config(page_title="택스 히어로(Tax Hero) - 클라우드 DB", layout="wide", page_icon="☁️")

# --- 1. 구글 시트 데이터베이스 셋업 ---
@st.cache_resource
def init_connection():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # 💡 [핵심 수정] 복잡한 변환 로직 삭제! Secrets에 통째로 넣은 JSON 텍스트를 바로 읽어옵니다.
        gcp_creds = json.loads(st.secrets["google_json"])
        
        creds = Credentials.from_service_account_info(gcp_creds, scopes=scope)
        client = gspread.authorize(creds)
        sheet_url = st.secrets["private"]["sheet_url"]
        return client.open_by_url(sheet_url).sheet1
    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {e}")
        st.stop()

# 시트 연결 변수 선언
sheet = init_connection()

def load_data():
    try:
        val = sheet.acell('A1').value
        if val:
            return json.loads(val)
        return {}
    except Exception:
        return {}

def save_data(data):
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        sheet.update_acell('A1', json_str)
        return True # 정상 저장됨
    except Exception as e:
        st.error(f"🚨 구글 시트 저장 실패! (실제 에러 내용: {e})")
        st.info("💡 체크포인트: 구글 시트 [공유] 설정에서 봇 이메일이 **'뷰어'**가 아닌 **'편집자'** 권한인지 꼭 확인하세요.")
        return False

def hash_pin(pin):
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

# --- 세션 초기화 및 DB 로드 ---
if 'db_data' not in st.session_state:
    st.session_state['db_data'] = load_data()

data = st.session_state['db_data']

if 'authenticated_user' not in st.session_state:
    st.session_state['authenticated_user'] = None
if 'current_selection' not in st.session_state:
    st.session_state['current_selection'] = None

# --- 2. 사이드바 프로필 등록 ---
st.sidebar.title("🔒 유저 로그인")

with st.sidebar.expander("➕ 새 유저 등록하기", expanded=False):
    new_profile = st.text_input("유저 이름 (예: 나, 아내)")
    new_pin = st.text_input("비밀번호 설정 (숫자 4자리 등)", type="password")
    income_level = st.radio(
        "유저의 근로소득(총급여) 수준", 
        ["5,500만원 이하 (공제율 16.5%)", "5,500만원 초과 (공제율 13.2%)"]
    )
    if st.button("유저 등록"):
        if new_profile and new_profile not in data:
            if new_pin:
                rate = 0.165 if "이하" in income_level else 0.132
                data[new_profile] = {"pin": hash_pin(new_pin), "income_rate": rate, "pension": []}
                
                is_saved = save_data(data)
                
                if is_saved:
                    st.session_state['db_data'] = data
                    st.success("등록 완료! 이제 로그인해주세요.")
                    st.rerun()
                else:
                    del data[new_profile]
            else:
                st.error("비밀번호를 반드시 입력해야 합니다.")
        elif new_profile in data:
            st.warning("이미 등록된 이름입니다.")

# --- 3. 로그인 및 인증 로직 ---
profile_names = list(data.keys())
selected_profile = st.sidebar.selectbox("접속할 유저 선택", profile_names if profile_names else ["유저를 등록해주세요"])

if selected_profile != "유저를 등록해주세요":
    
    if st.session_state['current_selection'] != selected_profile:
        st.session_state['authenticated_user'] = None
        st.session_state['current_selection'] = selected_profile

    if st.session_state['authenticated_user'] != selected_profile:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔑 인증 필요")
        entered_pin = st.sidebar.text_input("비밀번호를 입력하세요", type="password")
        
        if st.sidebar.button("로그인"):
            if hash_pin(entered_pin) == data[selected_profile].get("pin"):
                st.session_state['authenticated_user'] = selected_profile
                st.rerun()
            else:
                st.sidebar.error("비밀번호가 일치하지 않습니다.")
        
        st.warning("👈 왼쪽 사이드바에서 비밀번호를 입력해 안전하게 로그인해주세요.")
        st.stop()

    # ==========================================
    # 인증 성공 시 메인 대시보드
    # ==========================================
    st.sidebar.success("✅ 로그인 성공")
    if st.sidebar.button("로그아웃"):
        st.session_state['authenticated_user'] = None
        st.rerun()

    user_rate = data[selected_profile].get("income_rate", 0.132)
    rate_text = "16.5%" if user_rate == 0.165 else "13.2%"
    
    items = data[selected_profile].get("pension", [])
    df = pd.DataFrame(items)
    
    # --- 한도 계산 로직 고도화 ---
    limit_pen = 6000000 # 연금저축 공제한도
    limit_irp = 3000000 # IRP 추가 공제한도
    tax_limit = 9000000 # 총 세액공제 한도
    total_annual_limit = 18000000 # 연간 총 납입 한도 (법정)

    total_pen = 0
    total_irp = 0
    if not df.empty:
        total_pen = df[df['type'] == "연금저축(보험/펀드)"]['annual_total'].sum()
        total_irp = df[df['type'] == "IRP"]['annual_total'].sum()
    
    # 1. 세액공제 인정 금액 계산
    valid_pen = min(total_pen, limit_pen)
    valid_irp = min(total_irp, tax_limit - valid_pen)
    total_tax_valid = valid_pen + valid_irp # 세액공제 대상 금액
    
    # 2. 전체 납입 및 추가 한도 계산
    total_actual_pay = total_pen + total_irp # 실제 총 납입액
    over_limit_pay = max(0, total_actual_pay - tax_limit) # 공제 한도 초과분 (B호 권장분)
    remaining_total_limit = max(0, total_annual_limit - total_actual_pay) # 1800만 원까지 남은 금액

    # --- 화면 표시 ---
    st.title(f"🎯 {selected_profile}님의 통합 자산 관리 리포트")
    
    # 첫 번째 줄: 세액공제 집중 (900만 한도)
    st.subheader("🛡️ 세액공제 트랙 (연 900만 원)")
    c1, c2, c3 = st.columns(3)
    c1.metric("공제 대상 금액", f"{total_tax_valid:,}원")
    c2.metric("남은 공제 한도", f"{max(0, tax_limit - total_tax_valid):,}원")
    c3.metric("예상 환급액", f"{int(total_tax_valid * user_rate):,}원")
    st.progress(min(1.0, total_tax_valid / tax_limit))

    # 두 번째 줄: 전체 투자 집중 (1,800만 한도)
    st.subheader("🚀 전략적 투자 트랙 (연 1,800만 원)")
    c4, c5, c6 = st.columns(3)
    c4.metric("총 납입 금액", f"{total_actual_pay:,}원")
    c5.metric("공제 초과 금액 (B호)", f"{over_limit_pay:,}원", help="세액공제는 못 받지만 언제든 비과세 인출이 가능한 금액입니다.")
    c6.metric("추가 납입 가능액", f"{remaining_total_limit:,}원", help="1,800만 원 한도까지 남은 금액입니다.")
    st.progress(min(1.0, total_actual_pay / total_annual_limit))
    st.write("")

    st.markdown("### 🏦 내 연금 계좌 관리")
    with st.expander("➕ 새로운 연금 상품 등록 (기존 가입 포함)", expanded=True if df.empty else False):
        c1, c2, c3 = st.columns(3)
        p_type = c1.selectbox("상품 종류", ["연금저축(보험/펀드)", "IRP"])
        p_name = c2.text_input("계좌명", placeholder="예: 미래에셋 연저펀A")
        annual_pay = c3.number_input("올해 총 납입 예상액 (원)", min_value=0, step=100000, value=0)
        
        is_old_ins = st.checkbox("이 계좌가 납입이 끝나가는 '기존 연금보험'인가요?")
        
        remain_m = 0
        if is_old_ins:
            col_a, col_b = st.columns(2)
            total_m = col_a.number_input("총 약정 납입 개월 수", min_value=1, value=120)
            paid_m = col_b.number_input("현재까지 납입 완료한 횟수", min_value=0, value=0)
            remain_m = max(0, total_m - paid_m)
            st.info(f"👉 이 보험의 남은 납입 개월 수는 **{remain_m}개월**로 자동 계산되었습니다.")
            
        if st.button("상품 등록", type="primary"):
            if p_name:
                data[selected_profile]["pension"].append({
                    "id": len(data[selected_profile]["pension"]) + 1,
                    "type": p_type,
                    "name": p_name,
                    "annual_total": annual_pay,
                    "remain_months": remain_m,
                    "is_insurance": is_old_ins
                })
                save_data(data)
                st.session_state['db_data'] = data
                st.rerun()
            else:
                st.warning("계좌명을 입력해주세요.")

    if not df.empty:
        st.markdown("#### 📋 등록된 자산 목록")
        for i, row in df.iterrows():
            with st.container():
                st.markdown(f"**[{row['type']}] {row['name']}** (연 납입: {row['annual_total']:,}원)")
                if row.get('is_insurance', False) and 0 < row['remain_months'] <= 12:
                    st.warning(f"💡 이 보험은 완납까지 **{row['remain_months']}개월** 남았습니다! 완료 즉시 증권사 '연금저축펀드'로 이전하세요.")
                if st.button("삭제", key=f"del_{i}"):
                    data[selected_profile]["pension"].pop(i)
                    save_data(data)
                    st.session_state['db_data'] = data
                    st.rerun()
        st.markdown("---")

    if shortfall > 0:
        st.markdown("### 🤖 파트너 봇의 맞춤형 액션 플랜")
        st.info(f"허공에 날리고 있는 **{lost_money:,}원**을 회수하기 위해, 남은 **{shortfall:,}원**을 아래 가이드에 따라 세팅하세요.")
        st.markdown("#### 1단계: 수수료 0원 증권사 비대면 개설")
        st.markdown("ETF 실시간 매매가 가능한 **대형 증권사 앱**을 설치하세요.")
        st.markdown("#### 2단계: 목적별 계좌 만들기")
        if shortfall_pen > 0:
            st.checkbox(f"✅ **[연금저축펀드 A호] (세액공제 & 기존보험 이전용):** 개설 후 **{shortfall_pen:,}원** 입금하기.")
        st.checkbox("✅ **[연금저축펀드 B호] (초과납입 & 비상금 출금용):** 우선 개설만 해두기 (현재 0원).")
        if shortfall_irp > 0:
            st.checkbox(f"✅ **[다이렉트 IRP] (추가 세액공제용):** 개설 후 **{shortfall_irp:,}원** 입금하기.")
