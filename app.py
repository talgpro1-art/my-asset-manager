import streamlit as st
import pandas as pd
import json
import os

# 1. 데이터 저장 및 로드 함수 (데이터베이스 대용)
DATA_FILE = "pension_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# 페이지 설정
st.set_page_config(page_title="연금 매니저 3.0", layout="wide")
data = load_data()

# 2. 사이드바 - 프로필 관리
st.sidebar.title("👥 프로필 관리")
profile_names = list(data.keys())
new_profile = st.sidebar.text_input("새 프로필 추가 (예: 본인, 아내)")

if st.sidebar.button("프로필 등록"):
    if new_profile and new_profile not in data:
        data[new_profile] = []
        save_data(data)
        st.rerun()

selected_profile = st.sidebar.selectbox("관리할 프로필 선택", profile_names if profile_names else ["프로필을 먼저 등록하세요"])

# 3. 데이터 입력 섹션
st.title(f"📊 {selected_profile}의 연금 관리 대시보드")

if selected_profile != "프로필을 먼저 등록하세요":
    with st.expander("➕ 신규 연금 상품 등록"):
        with st.form("add_pension_form"):
            col1, col2 = st.columns(2)
            p_type = col1.selectbox("상품 종류", ["연금저축(보험/펀드)", "IRP"])
            p_name = col2.text_input("상품 이름(증권사/보험사)", placeholder="예: 삼성증권 연저펀A")
            
            col3, col4 = st.columns(2)
            monthly_pay = col3.number_input("월 납입액 (원)", min_value=0, step=10000)
            annual_extra = col4.number_input("올해 추가 납입액(일시납)", min_value=0, step=100000)
            
            submit_btn = st.form_submit_button("상품 저장")
            
            if submit_btn:
                new_item = {
                    "id": len(data[selected_profile]) + 1,
                    "type": p_type,
                    "name": p_name,
                    "monthly": monthly_pay,
                    "extra": annual_extra
                }
                data[selected_profile].append(new_item)
                save_data(data)
                st.success(f"{p_name} 등록 완료!")
                st.rerun()

    # 4. 데이터 계산 로직
    items = data[selected_profile]
    df = pd.DataFrame(items)
    
    if not df.empty:
        # 연간 총액 계산
        df['annual_total'] = (df['monthly'] * 12) + df['extra']
        
        total_pension = df[df['type'] == "연금저축(보험/펀드)"]['annual_total'].sum()
        total_irp = df[df['type'] == "IRP"]['annual_total'].sum()
        
        # 한도 적용 (2026 세법 기준)
        pension_limit = 6000000
        irp_limit = 3000000
        total_limit = 9000000
        
        # 세액공제 인정 금액 계산
        deduct_pension = min(total_pension, pension_limit)
        deduct_irp = min(total_irp, (total_limit - deduct_pension))
        total_deduct = deduct_pension + deduct_irp
        
        # 5. 대시보드 메트릭
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 납입액", f"{total_pension + total_irp:,}원")
        m2.metric("세액공제 인정액", f"{total_deduct:,}원", f"한도 {total_limit:,}원")
        m3.metric("충족률", f"{(total_deduct/total_limit)*100:.1f}%")
        m4.metric("예상 환급액 (16.5%)", f"{int(total_deduct * 0.165):,}원")

        st.markdown("---")
        
        # 6. 등록된 상품 리스트 및 삭제 기능
        st.subheader("📋 등록된 연금 상품 리스트")
        for i, row in df.iterrows():
            c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
            c1.write(f"**[{row['type']}]**")
            c2.write(f"{row['name']}")
            c3.write(f"연간 {row['annual_total']:,}원")
            if c4.button("삭제", key=f"del_{i}"):
                data[selected_profile].pop(i)
                save_data(data)
                st.rerun()
        
        # 시각화
        st.subheader("📉 한도 달성 현황")
        st.progress(total_deduct / total_limit)
        st.caption(f"현재 세액공제 가능 금액: {total_deduct:,} / {total_limit:,}")

    else:
        st.info("아직 등록된 상품이 없습니다. 위 폼을 이용해 상품을 등록해주세요.")

else:
    st.warning("왼쪽 사이드바에서 프로필을 먼저 등록하거나 선택해주세요.")
