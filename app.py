import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="행정동 코드 조회기", page_icon="📍")
st.title("📍 행정동 코드 조회 서비스")

# 2. 데이터 불러오기 (파일명이 dongcode.xlsx로 변경됨)
@st.cache_data
def load_data():
    df = pd.read_excel("dongcode.xlsx")
    return df

try:
    df = load_data()

    # 3. 데이터 구조에 따라 선택박스 구성
    # 엑셀의 실제 열 이름이 '시도명', '시군구명', '읍면동명', '행정동코드'가 맞는지 확인해 주세요!
    sido_list = df['시도명'].unique()
    sido = st.selectbox("1. 시도를 선택하세요", sido_list)

    sigungu_list = df[df['시도명'] == sido]['시군구명'].unique()
    sigungu = st.selectbox("2. 시군구를 선택하세요", sigungu_list)

    dong_list = df[(df['시도명'] == sido) & (df['시군구명'] == sigungu)]['읍면동명'].unique()
    dong = st.selectbox("3. 읍면동을 선택하세요", dong_list)

    # 4. 결과 출력
    if st.button("행정동 코드 조회"):
        result = df[(df['시도명'] == sido) & (df['시군구명'] == sigungu) & (df['읍면동명'] == dong)]
        if not result.empty:
            code = result['행정동코드'].values[0]
            st.success(f"선택하신 {sido} {sigungu} {dong}의 코드는 **{code}** 입니다.")
        else:
            st.warning("해당하는 코드를 찾을 수 없습니다.")

except Exception as e:
    st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
    st.info("파일 이름이 'dongcode.xlsx'가 맞는지, 엑셀의 열 제목이 코드와 일치하는지 확인해 주세요.")