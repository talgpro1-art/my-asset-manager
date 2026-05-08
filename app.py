import streamlit as st
import pandas as pd
import json
import os

# --- 1. 데이터 관리 ---
DATA_FILE = "pension_data_v2.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

st.set_page_config(page_title="연금 자산 매니저", layout="wide")
data = load_data()

# --- 2. 사이드바: 프로필 관리 ---
st.sidebar.title("👥 프로필 관리")
profile_names = list(data.keys())
new_profile = st.sidebar.text_input("새 프로필 추가 (예: 본인, 아내)")

if st.sidebar.button("프로필 등록"):
    if new_profile and new_profile not in data:
        data[new_profile] = []
        save_data(data)
        st.rerun()

selected_profile = st.sidebar.selectbox("관리할 프로필 선택", profile_names if profile_names else ["프로필을 먼저 등록하세요"])

# --- 3. 메인: 상품 등록 폼 ---
st.title(f"📊 {selected_profile}의 연금 관리 대시보드")

if selected_profile != "프로필을 먼저 등록하세요":
    with st.expander("➕ 기존 가입 및 신규 연금 상품 등록", expanded=True):
        with st.form("add_pension_form"):
            col1, col2 = st.columns(2)
            p_type = col1.selectbox("상품 종류", ["연금저축보험 (기존가입)", "연금저축펀드", "IRP"])
            p_name = col2.text_input("상품 이름", placeholder="예: 행복한동행 연금보험")
            
            # 기존 보험일 경우 추가 정보 입력 (만기 파악용)
            if p_type == "연금저축보험 (기존가입)":
                st.caption("📌 기존 가입된 보험의 핵심 정보만 입력하세요.")
                c1, c2, c3, c4 = st.columns(4)
                total_months = c1.number_input("총 납입기간 (개월)", min_value=1, value=120)
                current_month = c2.number_input("현재 납입회차 (회)", min_value=1, value=111)
                monthly_pay = c3.number_input("월 납입액 (원)", min_value=0, value=100000, step=10000)
                current_fund = c4.number_input("현재 적립금 (원)", min_value=0, value=11100000, step=100000)
                annual_extra = 0 # 기존 보험은 일시납 없음
            else:
                c1, c2 = st.columns(2)
                monthly_pay = c1.number_input("월 납입액 (원)", min_value=0, step=10000)
                annual_extra = c2.number_input("올해 추가 납입액(일시납)", min_value=0, step=100000)
                total_months, current_month, current_fund = 0, 0, 0
            
            if st.form_submit_button("상품 저장"):
                new_item = {
                    "id": len(data[selected_profile]) + 1,
                    "type": p_type,
                    "name": p_name,
                    "monthly": monthly_pay,
                    "extra": annual_extra,
                    "total_months": total_months,
                    "current_month": current_month,
                    "current_fund": current_fund
                }
                data[selected_profile].append(new_item)
                save_data(data)
                st.success("등록 완료!")
                st.rerun()

    # --- 4. 대시보드 계산 ---
    items = data[selected_profile]
    df = pd.DataFrame(items)
    
    if not df.empty:
        df['annual_total'] = (df['monthly'] * 12) + df['extra']
        
        # 보험과 펀드 모두 '연금저축' 한도로 묶임
        total_pension = df[df['type'].str.contains("연금저축")]['annual_total'].sum()
        total_irp = df[df['type'] == "IRP"]['annual_total'].sum()
        
        limit_pension = 6000000
        limit_total = 9000000
        
        deduct_pension = min(total_pension, limit_pension)
        deduct_irp = min(total_irp, limit_total - deduct_pension)
        total_deduct = deduct_pension + deduct_irp
        
        # 메트릭 표시
        m1, m2, m3 = st.columns(3)
        m1.metric("올해 총 납입액", f"{total_pension + total_irp:,}원")
        m2.metric("세액공제 충족액", f"{total_deduct:,}원", f"한도 {limit_total:,}원")
        m3.metric("💸 환급 예상액", f"{int(total_deduct * 0.165):,}원", "16.5% 세율 기준")
        
        st.progress(total_deduct / limit_total)
        st.markdown("---")
        
        # --- 5. 등록 리스트 & AI 인사이트 (전략 제시) ---
        st.subheader("📋 내 자산 리스트 및 AI 인사이트")
        
        for i, row in df.iterrows():
            with st.container():
                st.markdown(f"**[{row['type']}] {row['name']}** (연 납입: {row['annual_total']:,}원)")
                
                # 기존 보험에 대한 특별 인사이트 로직
                if row['type'] == "연금저축보험 (기존가입)":
                    remain_months = row['total_months'] - row['current_month']
                    principal = row['monthly'] * row['current_month']
                    yield_rate = ((row['current_fund'] - principal) / principal) * 100 if principal > 0 else 0
                    
                    st.write(f"▸ 진행률: {row['current_month']}/{row['total_months']}회차 (잔여 {remain_months}개월) | 총 납입원금: {principal:,}원 | 현재 적립금: {row['current_fund']:,}원 (수익률: {yield_rate:.1f}%)")
                    
                    # 만기 1년 이내 알림
                    if 0 < remain_months <= 12:
                        st.warning(f"🚨 **Action Required:** 납입 만료가 {remain_months}개월 남았습니다! 완납 즉시 증권사 '연금저축펀드'로 계좌 이전(연금 이전)을 신청하여, 묶여있는 적립금을 AI 관련 ETF에 재투자할 준비를 하세요.")
                    # 수익률 저조 알림
                    elif yield_rate < 0:
                        st.info("💡 **Insight:** 원금보다 적립금이 적습니다. 이는 초기 사업비(수수료) 차감 때문입니다. 납입 완료 후 ETF 직접 투자가 가능한 증권사로 이전하면 수익률을 방어할 수 있습니다.")
                
                if st.button("삭제", key=f"del_{i}"):
                    data[selected_profile].pop(i)
                    save_data(data)
                    st.rerun()
                st.write("") # 간격 띄우기
else:
    st.info("왼쪽에서 프로필을 먼저 등록해주세요.")
