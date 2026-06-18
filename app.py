import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

st.set_page_config(layout="wide")
st.title("🎯 수동 입력 방식 전입·전출 데이터 수집기")

# 1. 입력창 (검색 불필요, 직접 기입)
col1, col2, col3 = st.columns(3)
with col1:
    target_code = st.text_input("행정동 코드 입력 (예: 3611025000)")
with col2:
    start_ym = st.text_input("시작 년월 (예: 202501)")
with col3:
    end_ym = st.text_input("종료 년월 (예: 202512)")

# 2. 수집 로직 (기존 스크립트 v9의 핵심 로직 이식)
def get_data_from_site(dong_code, fr, to, gubun):
    # gubun: '1000000000'(전체)이면 mvt_dong에 입력, 전입/전출에 따라 위치 변경
    mvin = dong_code if gubun == "in" else "1000000000"
    mvt = "1000000000" if gubun == "in" else dong_code
    
    url = "https://rdoa.jumin.go.kr/openStats/selectConPpltnData"
    params = {
        "paramUrl": f"mvinAdmmCd={mvin}&mvtAdmmCd={mvt}&lv=3&srchFrYm={fr}&srchToYm={to}",
        "curPage": "1"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    res = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    
    rows_data = []
    rows = soup.select("div.bbs_list table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if len(tds) >= 12:
            rows_data.append([t.text.strip() for t in tds])
    return rows_data

# 3. 버튼 클릭 시 동작
if st.button("수집 시작 및 엑셀 다운로드"):
    if not all([target_code, start_ym, end_ym]):
        st.error("모든 칸을 채워주세요.")
    else:
        with st.spinner("데이터를 수집 중입니다..."):
            in_data = get_data_from_site(target_code, start_ym, end_ym, "in")
            out_data = get_data_from_site(target_code, start_ym, end_ym, "out")
            
            # DataFrame 생성
            cols = ["통계년월", "전입코드", "전출코드", "전입시도", "전입시군구", "전입동", 
                    "전출시도", "전출시군구", "전출동", "총인구", "남자", "여자"]
            df_in = pd.DataFrame(in_data, columns=cols)
            df_out = pd.DataFrame(out_data, columns=cols)
            
            # 엑셀 다운로드 파일 생성
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_in.to_excel(writer, index=False, sheet_name="전입_원본")
                df_out.to_excel(writer, index=False, sheet_name="전출_원본")
            
            st.success("수집 완료!")
            st.download_button(
                label="📥 엑셀 파일 다운로드",
                data=buffer.getvalue(),
                file_name=f"데이터_{target_code}_{start_ym}_{end_ym}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )