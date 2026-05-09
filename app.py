import streamlit as st
import pandas as pd
import json
import os
import hashlib  # 암호화를 위한 라이브러리 추가

# --- 1. 데이터베이스 셋업 ---
DATA_FILE = "v8_1_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- PIN 암호화 함수 ---
def hash_pin(pin):
    """비밀번호를 SHA-256 방식으로 암호화하여 반환합니다."""
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

st.set_page_config(page_title="택스 히어로(Tax Hero) - 강력 보안", layout="wide", page_icon="🛡️")
data = load_data()

# --- 세션 상태 초기화 ---
if 'authenticated_user' not in st.session_state:
    st.session_state['authenticated_user'] = None
if 'current_selection' not in st.session_state:
    st.session_state['current_selection'] = None

# --- 2. 사이드바 프로필 등록 (PIN 암호화 적용) ---
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
                # 날것의 PIN이 아닌, 암호화된 해시값(hash_pin)을 DB에 저장
                data[new_profile] = {"pin": hash_pin(new_pin), "income_rate": rate, "pension": []}
                save_data(data)
                st.success("등록 완료! 이제 로그인해주세요.")
                st.rerun()
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
            # 유저가 방금 입력한 값도 동일하게 암호화하여 DB의 암호화된 값과 비교
            if hash_pin(entered_pin) == data[selected_profile].get("pin"):
                st.session_state['authenticated_user'] = selected_profile
                st.rerun()
            else:
                st.sidebar.error("비밀번호가 일치하지 않습니다.")
        
        st.warning("👈 왼쪽 사이드바에서 비밀번호를 입력해 안전하게 로그인해주세요.")
        st.stop()

    # ==========================================
    # 인증 성공 시 (메인 대시보드 렌더링 시작)
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
    shortfall_irp = max(0, total_limit - valid_pen - valid_irp)
    
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
            total_m = col_a.number_input("총 약정 납입 개월 수 (예: 10년 납 = 120)", min_value=1, value=120)
            paid_m = col_b.number_input("현재까지 납입 완료한 횟수", min_value=0, value=0)
            
            remain_m = total_m - paid_m
            if remain_m < 0:
                remain_m = 0
                
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
                st.rerun()
            else:
                st.warning("계좌명을 입력해주세요.")

    if not df.empty:
        st.markdown("#### 📋 등록된 자산 목록")
        for i, row in df.iterrows():
            with st.container():
                st.markdown(f"**[{row['type']}] {row['name']}** (연 납입: {row['annual_total']:,}원)")
                if row.get('is_insurance', False) and 0 < row['remain_months'] <= 12:
                    st.warning(f"💡 이 보험은 완납까지 **{row['remain_months']}개월** 남았습니다! 완료 즉시 증권사 '연금저축펀드'로 이전하여 비과세 ETF 투자를 시작하세요.")
                if st.button("삭제", key=f"del_{i}"):
                    data[selected_profile]["pension"].pop(i)
                    save_data(data)
                    st.rerun()
        st.markdown("---")

    if shortfall > 0:
        st.markdown("### 🤖 파트너 봇의 맞춤형 액션 플랜")
        st.info(f"허공에 날리고 있는 **{lost_money:,}원**을 즉시 회수하기 위해, 남은 **{shortfall:,}원**을 아래 가이드에 따라 세팅하세요.")
        st.markdown("#### 1단계: 수수료 0원 증권사 비대면 개설")
        st.markdown("은행이나 보험사가 아닌, ETF 실시간 매매가 가능한 **대형 증권사 앱(삼성증권, 미래에셋 등)**을 설치하세요.")
        st.markdown("#### 2단계: 목적별 3개의 계좌 만들기 (핵심 전략)")
        if shortfall_pen > 0:
            st.checkbox(f"✅ **[연금저축펀드 A호] (세액공제 & 기존보험 이전용):** 개설 후 **{shortfall_pen:,}원** 입금하기.")
        st.checkbox("✅ **[연금저축펀드 B호] (초과납입 & 비상금 출금용):** 우선 개설만 해두기 (현재 0원).")
        if shortfall_irp > 0:
            st.checkbox(f"✅ **[다이렉트 IRP] (추가 세액공제용):** 개설 후 **{shortfall_irp:,}원** 입금하기.")
        st.markdown("#### 3단계: ETF 분할 매수")
        st.markdown("* **연금저축펀드 A, B호:** 미국 나스닥 100 ETF, S&P 500 ETF (100% 한도로 공격적 매수)\n* **IRP 계좌:** 미국 테크주 ETF (70%) + 달러 단기채권 또는 금(Gold) ETF (30% 리스크 헷징)")
