import streamlit as st
import pandas as pd
import json
import os

# --- 1. 데이터베이스 셋업 ---
DATA_FILE = "v4_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

st.set_page_config(page_title="택스 히어로(Tax Hero) 프로토타입", layout="wide", page_icon="💸")
data = load_data()

# --- 2. 앱스토어 배포를 고려한 UX: 사이드바 프로필 등록/관리 ---
st.sidebar.title("👥 유저 관리")
st.sidebar.markdown("가족 구성원의 소득과 연금을 개별 관리합니다.")

with st.sidebar.expander("➕ 새 유저 등록하기", expanded=False):
    with st.form("new_profile_form"):
        new_profile = st.text_input("유저 이름 (예: 나, 아내)")
        income_level = st.radio(
            "유저의 근로소득(총급여) 수준", 
            ["5,500만원 이하 (공제율 16.5%)", "5,500만원 초과 (공제율 13.2%)"],
            help="소득 구간에 따라 국가에서 돌려주는 환급 비율이 달라집니다."
        )
        if st.form_submit_button("등록"):
            if new_profile and new_profile not in data:
                rate = 0.165 if "이하" in income_level else 0.132
                data[new_profile] = {"income_rate": rate, "pension": []}
                save_data(data)
                st.rerun()

profile_names = list(data.keys())
selected_profile = st.sidebar.selectbox("현재 접속 중인 유저", profile_names if profile_names else ["유저를 등록해주세요"])

if selected_profile != "유저를 등록해주세요":
    
    # 해당 유저의 소득 기반 세액공제율 가져오기
    user_rate = data[selected_profile].get("income_rate", 0.132)
    rate_text = "16.5%" if user_rate == 0.165 else "13.2%"
    
    # 기초 연산 로직
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
    
    # 손실 회피 마케팅 로직 (환급액 계산)
    max_refund = int(total_limit * user_rate)         # 받을 수 있는 최대 금액
    current_refund = int(total_valid * user_rate)     # 현재 받을 금액
    lost_money = max_refund - current_refund          # 공중에 날리고 있는 금액
    
    # --- 3. 메인 화면: 손실 회피(Loss Aversion) 대시보드 ---
    st.title(f"🎯 {selected_profile}님의 연말정산 최적화 리포트")
    st.caption(f"적용된 세액공제율: {rate_text} (소득 구간에 따라 자동 적용됨)")
    st.markdown("---")
    
    # 시각적 충격(Hook)을 주는 히어로 섹션
    if lost_money > 0:
        st.error(f"🚨 **비상!** 올해 국가에서 확정적으로 받을 수 있는 **{max_refund:,}원** 중, 아무것도 하지 않아 **{lost_money:,}원**을 허공에 날리고 있습니다!")
    else:
        st.success(f"🎉 **완벽합니다!** 올해 국가에서 받을 수 있는 최대 환급액 **{max_refund:,}원**을 100% 확보하셨습니다!")

    col1, col2, col3 = st.columns(3)
    col1.metric("총 한도액", f"{total_limit:,}원")
    col2.metric("🟢 현재 채운 금액", f"{total_valid:,}원")
    col3.metric("🔴 남은 한도 (버려지는 중)", f"{total_limit - total_valid:,}원")
    
    st.progress(total_valid / total_limit)
    st.write("")

    # --- 4. 계좌 등록 및 관리 폼 ---
    st.markdown("### 🏦 내 연금 계좌 관리")
    with st.expander("➕ 새로운 연금 상품 등록 (기존 가입 포함)", expanded=True if df.empty else False):
        with st.form("pension_form"):
            c1, c2, c3 = st.columns(3)
            p_type = c1.selectbox("상품 종류", ["연금저축(보험/펀드)", "IRP"])
            p_name = c2.text_input("계좌명", placeholder="예: 미래에셋 연저펀A")
            annual_pay = c3.number_input("올해 총 납입 예상액 (원)", min_value=0, step=100000, value=1200000)
            
            # 전략적 인사이트용 정보
            is_old_ins = st.checkbox("이 계좌가 납입이 끝나가는 '기존 보험'인가요? (연금 이전 추천용)")
            remain_m = st.number_input("남은 납입 개월 수", min_value=0, value=9) if is_old_ins else 0
            
            if st.form_submit_button("상품 등록"):
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

    # --- 5. 등록된 계좌 리스트 및 AI 코칭 ---
    if not df.empty:
        st.markdown("#### 📋 등록된 자산 목록 및 파트너 코칭")
        for i, row in df.iterrows():
            with st.container():
                st.markdown(f"**[{row['type']}] {row['name']}** (연 납입: {row['annual_total']:,}원)")
                
                # 기존 보험 리밸런싱 경고
                if row.get('is_insurance', False) and row['remain_months'] <= 12:
                    st.warning(f"💡 **파트너 봇 인사이트:** 이 보험은 완납까지 **{row['remain_months']}개월** 남았습니다! 납입 완료 즉시 증권사 '연금저축펀드'로 이전하여 비과세 ETF 투자를 시작하세요.")
                
                if st.button("삭제", key=f"del_{i}"):
                    data[selected_profile]["pension"].pop(i)
                    save_data(data)
                    st.rerun()
                st.markdown("---")
else:
    st.info("👈 왼쪽 사이드바에서 본인 또는 가족의 유저 프로필을 먼저 생성해 주세요.")
