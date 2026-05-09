import streamlit as st
import pandas as pd
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# 🚨 [수정 1] 스트림릿 절대 규칙! 페이지 셋팅은 무조건 가장 먼저 와야 합니다.
st.set_page_config(page_title="택스 히어로(Tax Hero) - 클라우드 DB", layout="wide", page_icon="☁️")

# --- 1. 구글 시트 데이터베이스 셋업 ---
@st.cache_resource
def init_connection():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # 줄바꿈 기호(\n) 강제 변환 로직
        gcp_creds = dict(st.secrets["gcp_service_account"])
        gcp_creds["private_key"] = gcp_creds["private_key"].replace('\\n', '\n')
        
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
    
    limit_pen = 6000000
    limit_irp = 3000000
    total_limit = 9000000
    
    total_pen, total_irp = 0, 0
    if not df.empty:
        total_pen = df[df['type'] == "연금저축(보험/펀드)"]['annual_total'].sum()
        total_irp = df[df['type'] == "IRP"]['annual_total'].sum()
    
    valid_pen = min(total_pen, limit_pen)
    valid_irp = min(total_irp, total_limit - valid_pen)
    total_valid = valid_pen + valid_irp
    
    shortfall = total_limit - total_valid
    shortfall_pen = max(0, limit_pen - valid_pen)
    shortfall_irp = max(0, shortfall - shortfall_pen) 
    
    max_refund = int(total_limit * user_rate)         
    current_refund = int(total_valid * user_rate)     
    lost_money = max_refund - current_refund          
    
    st.title(f"🎯 {selected_profile}님의 연말정산 최적화 리포트")
    st.caption(f"적용된 세액공제율: {rate_text}")
    st.markdown("---")
    
    if lost_money > 0:
        st.error(f"🚨 **비상!** 올해 국가에서 확정적으로 받을 수 있는 **{max_refund:,}원** 중, 아무것도 하지 않아 **{lost_money:,}원**을 허공에 날리고 있습니다!")
    else:
        st.success(f"🎉 **완벽합니다!** 올해 국가에서 받을 수 있는 최대 환급액 **{max_refund:,}원**을 100% 확보하셨습니다!")

    col1, col2, col3 = st.columns(3)
    col1.metric("총 한도액", f"{total_limit:,}원")
    col2.metric("🟢 현재 채운 금액", f"{total_valid:,}원")
    col3.metric("🔴 남은 한도 (버려지는 중)", f"{shortfall:,}원")
    
    st.progress(total_valid / total_limit)
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
