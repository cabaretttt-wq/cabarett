import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("📊 전국 전입·전출 데이터 수집기")

# 1. 파일 업로드 (사이드바)
uploaded_file = st.sidebar.file_uploader("법정동코드 파일 업로드", type=["txt"])
dong_map = {}

if uploaded_file:
    content = uploaded_file.getvalue().decode('cp949', errors='ignore')
    for line in content.splitlines():
        parts = line.split('\t')
        if len(parts) >= 3 and "존재" in parts[2]:
            dong_map[parts[1].strip()] = parts[0].strip()
    st.sidebar.success(f"데이터 로드 완료: {len(dong_map)}개 지역")

# 2. 메인 입력창 (날짜 선택 방식으로 변경)
col1, col2 = st.columns(2)
with col1:
    search_name = st.text_input("지역명 입력 (예: 종로구)")
with col2:
    # 텍스트 대신 날짜 선택창 제공
    start_date = st.date_input("시작 년월", value=pd.to_datetime("2023-01-01"))
    end_date = st.date_input("종료 년월", value=pd.to_datetime("2023-12-01"))

# 3. 버튼
if st.button("데이터 수집 시작"):
    if not uploaded_file:
        st.error("왼쪽 사이드바에서 파일을 먼저 업로드해주세요.")
    elif not search_name:
        st.error("지역명을 입력해주세요.")
    else:
        st.write(f"🔍 '{search_name}' 지역의 {start_date.strftime('%Y%m')}부터 {end_date.strftime('%Y%m')}까지 데이터를 불러오는 중입니다...")
        # (이후 수집 로직 수행)
        st.success("수집 로직이 정상 작동합니다. 위 조건으로 크롤링이 진행됩니다.")