import streamlit as st
import pandas as pd
import json
import os

# --- 1. 데이터베이스 셋업 ---
DATA_FILE = "v6_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

st.set_page_config(page_title="택스 히어로(Tax Hero) - 액션 플랜", layout="wide", page_icon="💸")
data = load_data()

# --- 2. 사이드바 프로필 관리 ---
st.sidebar.title("👥 유저 관리")
st.sidebar.markdown("가족 구성원의 소득과 연금을 개별 관리합니다.")

with st.sidebar.expander("➕ 새 유저 등록하기", expanded=False):
    with st.form("new_profile_form"):
        new_profile = st.text_input("유저 이름 (예: 나, 아내)")
        income_level = st.radio(
            "유저의 근로소득(총급여) 수준", 
            ["5,500만원 이하 (공제율 16.5%)", "5,500만원 초과 (공제율 13.2%)"]
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
    
    shortfall = total_limit - total_valid
    shortfall_pen = max(0, limit_pen - valid_pen)
    shortfall_irp = max(0, total_limit - valid_pen - valid_irp)
    
    max_refund = int(total_limit * user_rate)         
    current_refund = int(total_valid * user_rate)     
    lost_money = max_refund - current_refund          
    
    # --- 3. 메인 화면: 손실 회피 대시보드 ---
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

    # --- 4. 계좌 등록 및 리스트 ---
    st.markdown("### 🏦 내 연금 계좌 관리")
    with st.expander("➕ 새로운 연금 상품 등록 (기존 가입 포함)", expanded=True if df.empty else False):
        with st.form("pension_form"):
            c1, c2, c3 = st.columns(3)
            p_type = c1.selectbox("상품 종류", ["연금저축(보험/펀드)", "IRP"])
            p_name = c2.text_input("계좌명", placeholder="예: 기존 회사 연금보험")
            annual_pay = c3.number_input("올해 총 납입 예상액 (원)", min_value=0, step=100000, value=1200000)
            
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

    if not df.empty:
        st.markdown("#### 📋 등록된 자산 목록")
        for i, row in df.iterrows():
            with st.container():
                st.markdown(f"**[{row['type']}] {row['name']}** (연 납입: {row['annual_total']:,}원)")
                if row.get('is_insurance', False) and row['remain_months'] <= 12:
                    st.warning(f"💡 이 보험은 완납까지 **{row['remain_months']}개월** 남았습니다! 완료 즉시 증권사 '연금저축펀드'로 이전하여 비과세 ETF 투자를 시작하세요.")
                if st.button("삭제", key=f"del_{i}"):
                    data[selected_profile]["pension"].pop(i)
                    save_data(data)
                    st.rerun()
        st.markdown("---")

    # --- 5. 🤖 AI 파트너 봇의 맞춤형 가이드 (맥락 강화 버전) ---
    if shortfall > 0:
        st.markdown("### 🤖 파트너 봇의 맞춤형 액션 플랜")
        st.info(f"허공에 날리고 있는 **{lost_money:,}원**을 즉시 회수하기 위해, 남은 **{shortfall:,}원**을 아래 가이드에 따라 세팅하세요.")
        
        st.markdown("#### 1단계: 수수료 0원 증권사 비대면 개설")
        st.markdown("""
        은행이나 보험사가 아닌, ETF 실시간 매매가 가능한 **대형 증권사 앱**을 설치하세요.
        * **1순위 추천: 삼성증권 (mPOP)** - 모바일 개설 시 IRP 자산관리 수수료 **'평생 무료'** 
        * **2순위 추천: 미래에셋증권 (M-STOCK)** - 연금이전 시스템이 가장 매끄럽고 ETF 라인업이 다양함
        > 💡 *Tip: 앱 실행 후 반드시 '진행 중인 이벤트' 탭에서 연금 개설 혜택을 먼저 신청하세요.*
        """)
        
        st.markdown("#### 2단계: 목적별 3개의 계좌 만들기 (핵심 전략)")
        st.markdown("페널티 없는 현금 출금(유동성 확보)과 다가올 **'기존 보험의 연금 이전'**을 대비해 계좌에 명확한 꼬리표를 달아야 합니다.")
        
        if shortfall_pen > 0:
            st.checkbox(f"✅ **[연금저축펀드 A호] (세액공제 & 기존보험 이전용):** 개설 후 **{shortfall_pen:,}원** 입금하기. \n\n 👉 *전략: 올해 세액공제를 완성하는 메인 계좌입니다. 내년 4월, 납입이 끝나는 '회사 연금보험(1,200만 원)'을 이 계좌로 고스란히 옮겨와 AI 주식에 재투자하는 베이스캠프가 됩니다.*")
        
        st.checkbox("✅ **[연금저축펀드 B호] (초과납입 & 비상금 출금용):** 우선 개설만 해두기 (현재 0원). \n\n 👉 *전략: 보유하신 1.5억 원 현금 중, 연 900만 원 한도를 초과해 투자할 때 쓰는 계좌입니다. 이 계좌에 넣은 원금은 세액공제를 받지 않았으므로, 나중에 급전이 필요할 때 세금 폭탄(16.5%) 없이 언제든 뺄 수 있는 '마이너스 통장' 역할을 합니다.*")
        
        if shortfall_irp > 0:
            st.checkbox(f"✅ **[다이렉트 IRP] (추가 세액공제용):** 개설 후 **{shortfall_irp:,}원** 입금하기. \n\n 👉 *전략: 펀드에서 못 채운 공제 한도를 여기서 마저 채웁니다. 단, 안전자산 30% 의무 비율이 있으니 주의하세요.*")
        
        st.markdown("#### 3단계: AI 생태계 분할 매수")
        st.markdown("""
        계좌 입금(세금 방어)이 끝났다면, 이제 그 돈으로 자산을 불릴 차례입니다.
        * **연금저축펀드 A, B호:** 마이크로소프트, 구글 등 밸류체인과 연결된 미국 나스닥 100 ETF, S&P 500 ETF (100% 한도로 공격적 매수)
        * **IRP 계좌:** 미국 AI 테크주 ETF (70%) + 달러 단기채권 또는 금(Gold) ETF (30% 리스크 헷징)
        """)
