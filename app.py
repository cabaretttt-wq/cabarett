import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="데이터 추출기", layout="wide")
st.title("📊 전국 전입·전출 데이터 수집기")

# 1. 파일 강제 업로드 로직
st.sidebar.header("📁 필수: 데이터 파일 업로드")
st.sidebar.info("같은 폴더의 '법정동코드 전체자료.txt'를 업로드하세요.")
uploaded_file = st.sidebar.file_uploader("법정동코드 파일 업로드", type=["txt"])

dong_map = {}

if uploaded_file:
    try:
        # 파일 내용을 안전하게 읽기
        data = uploaded_file.getvalue().decode('cp949', errors='ignore')
        lines = data.split('\n')
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 3 and parts[2].strip() == "존재" and "법정동코드" not in parts[0]:
                dong_map[parts[1].strip()] = parts[0].strip().replace('\ufeff', '')
        st.sidebar.success(f"✅ {len(dong_map):,}개 지역 불러오기 완료!")
    except Exception as e:
        st.sidebar.error(f"파일 읽기 오류: {e}")
else:
    st.sidebar.warning("⚠️ 파일을 먼저 업로드해야 수집이 가능합니다.")

# 2. 크롤링 로직
def fetch_data(gubun, code, ym):
    url = "https://stat.moi.go.kr/WMO/stat/statMain.do"
    payload = {"searchType": "month", "searchGubun": gubun, "dongCode": code, "startInYm": ym, "endInYm": ym}
    try:
        res = requests.post(url, data=payload, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = []
        for tr in soup.select("#cubeGrid tbody tr"):
            tds = [t.get_text(strip=True) for t in tr.find_all("td")]
            if len(tds) >= 4: rows.append(tds)
        return rows
    except: return []

# 3. 화면 구성
search_name = st.text_input("지역명 입력 (예: 사당동)")
ym_range = st.text_input("기간 입력 (예: 202301-202312)")

if st.button("시작"):
    if not uploaded_file:
        st.error("파일을 업로드하세요.")
    elif '-' not in ym_range:
        st.error("기간은 YYYYMM-YYYYMM 형식입니다.")
    else:
        # 지역 매칭
        target_codes = [v for k, v in dong_map.items() if search_name in k]
        if not target_codes:
            st.error("지역을 찾을 수 없습니다.")
        else:
            code = target_codes[0]
            start, end = ym_range.split('-')
            months = [m.strftime('%Y%m') for m in pd.date_range(start, end, freq='MS')]
            
            all_data = []
            with st.spinner("수집 중..."):
                for m in months:
                    in_data = fetch_data("100", code, m)
                    for row in in_data: all_data.append([m] + row)
            
            df = pd.DataFrame(all_data, columns=["년월", "행정구역", "사유", "전입지", "건수"])
            st.dataframe(df)
            
            # 엑셀 저장
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            st.download_button("엑셀 다운로드", buf.getvalue(), "data.xlsx")