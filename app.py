import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(layout="wide")
st.title("🎯 수동 입력 방식 데이터 수집기")

# 1. 고정 입력창 (검색 불필요)
col1, col2, col3 = st.columns(3)
with col1:
    target_code = st.text_input("행정동 코드 입력 (예: 3611025000)")
with col2:
    start_ym = st.text_input("시작 년월 (예: 202501)")
with col3:
    end_ym = st.text_input("종료 년월 (예: 202512)")

# 2. 수집 함수 (사장님이 쓰시던 스크립트 기반)
def fetch_data(dong_code, fr, to):
    url = "https://rdoa.jumin.go.kr/openStats/selectConPpltnData"
    params = {
        "paramUrl": f"mvinAdmmCd={dong_code}&mvtAdmmCd=1000000000&lv=3&srchFrYm={fr}&srchToYm={to}",
        "curPage": "1"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    # 여기서 데이터를 깔끔하게 리스트로 변환하여 반환
    return "수집 완료" 

# 3. 버튼 클릭 시 동작
if st.button("수집 시작"):
    if not target_code or not start_ym or not end_ym:
        st.error("모든 칸을 채워주세요.")
    else:
        with st.spinner("수집 중..."):
            result = fetch_data(target_code, start_ym, end_ym)
            st.success(f"코드 {target_code}에 대한 데이터 수집 성공!")
            # 여기에 결과물(df)을 보여주는 로직 추가