import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

st.set_page_config(page_title="행정동 데이터 수집기", page_icon="📊")
st.title("📊 2025년 행정동 데이터 자동 수집기")

# 1. 데이터 로드
@st.cache_data
def load_data():
    return pd.read_excel("dongcode.xlsx")

df = load_data()

# 2. 선택창 구성
sido = st.selectbox("시도 선택", df['시도명'].unique())
sigungu = st.selectbox("시군구 선택", df[df['시도명'] == sido]['시군구명'].unique())
dong = st.selectbox("읍면동 선택", df[(df['시도명'] == sido) & (df['시군구명'] == sigungu)]['읍면동명'].unique())

code = df[(df['시도명'] == sido) & (df['시군구명'] == sigungu) & (df['읍면동명'] == dong)]['행정동코드'].values[0]

# 3. 수집 로직 (v9.py 로직 통합)
if st.button("2025년 데이터 수집 시작"):
    st.write(f"선택한 코드: {code}로 수집을 시작합니다...")
    
    driver = webdriver.Chrome()
    driver.get("https://rdoa.jumin.go.kr/openStats/selectConPpltnData.do")
    time.sleep(3)
    
    # 조치원 코드 입력 예시 로직 (사장님의 v9.py 방식을 그대로 적용)
    # 실제 input name이 'mvinAdmmCd'라면:
    input_box = driver.find_element(By.NAME, "mvinAdmmCd")
    input_box.clear()
    input_box.send_keys(str(code))
    driver.find_element(By.CLASS_NAME, "btn_search").click()
    
    time.sleep(5) # 데이터 로딩 대기
    
    # 데이터 추출 로직
    rows = driver.find_elements(By.CSS_SELECTOR, "div.bbs_list table tbody tr")
    data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 12:
            data.append({"통계년월": cols[0].text, "인구수": cols[9].text})
    
    driver.quit()
    
    # 4. 결과 저장 및 다운로드
    result_df = pd.DataFrame(data)
    st.dataframe(result_df)
    csv = result_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("엑셀 파일 다운로드", csv, "result_2025.csv", "text/csv")