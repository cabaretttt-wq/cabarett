import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

st.set_page_config(layout="wide")
st.title("📅 달력 선택형 데이터 수집기")

# 1. 입력부: 달력 기능 사용
col1, col2, col3 = st.columns(3)
with col1:
    target_code = st.text_input("행정동 코드 (예: 3611025000)")
with col2:
    start_date = st.date_input("시작 날짜 선택")
with col3:
    end_date = st.date_input("종료 날짜 선택")

# 2. 수집 로직 (날짜 형식 자동 변환)
def get_data_from_site(dong_code, start_d, end_d, gubun):
    # 날짜를 서버가 원하는 YYYYMM 형식으로 변환
    start_ym = start_d.strftime("%Y%m")
    end_ym = end_d.strftime("%Y%m")
    
    mvin = dong_code if gubun == "in" else "1000000000"
    mvt = "1000000000" if gubun == "in" else dong_code
    
    url = "https://rdoa.jumin.go.kr/openStats/selectConPpltnData"
    params = {
        "paramUrl": f"mvinAdmmCd={mvin}&mvtAdmmCd={mvt}&lv=3&srchFrYm={start_ym}&srchToYm={end_ym}",
        "curPage": "1"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    res = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    
    rows_data = []
    # 데이터가 없을 경우를 대비해 테이블 확인
    table = soup.select_one("div.bbs_list table tbody")
    if table:
        for row in table.find_all("tr"):
            tds = row.find_all("td")
            if len(tds) >= 12:
                rows_data.append([t.text.strip() for t in tds])
    return rows_data

# 3. 버튼 클릭 및 다운로드
if st.button("수집 시작 및 엑셀 다운로드"):
    if not target_code:
        st.error("행정동 코드를 입력해주세요.")
    else:
        with st.spinner("수집 중..."):
            in_data = get_data_from_site(target_code, start_date, end_date, "in")
            out_data = get_data_from_site(target_code, start_date, end_date, "out")
            
            if not in_data and not out_data:
                st.warning("데이터를 찾을 수 없습니다. 코드나 기간을 다시 확인해주세요.")
            else:
                cols = ["통계년월", "전입코드", "전출코드", "전입시도", "전입시군구", "전입동", 
                        "전출시도", "전출시군구", "전출동", "총인구", "남자", "여자"]
                df_in = pd.DataFrame(in_data, columns=cols)
                df_out = pd.DataFrame(out_data, columns=cols)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df_in.to_excel(writer, index=False, sheet_name="전입_원본")
                    df_out.to_excel(writer, index=False, sheet_name="전출_원본")
                
                st.success("수집 성공!")
                st.download_button("📥 엑셀 파일 다운로드", buffer.getvalue(), "data.xlsx")