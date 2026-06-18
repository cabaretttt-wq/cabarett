import streamlit as st
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("🛡️ 최종 수정된 데이터 수집기")

# 1. 파일 업로드
uploaded_file = st.file_uploader("법정동코드 파일을 올려주세요", type=["txt"])

if uploaded_file:
    # 2. 아주 안전하게 한 줄씩 읽는 방식
    dong_map = {}
    # 한글 깨짐 방지를 위해 cp949 인코딩 사용
    content = uploaded_file.getvalue().decode('cp949', errors='ignore')
    
    for line in content.splitlines():
        # 탭으로 분리
        parts = line.split('\t')
        
        # '존재'라는 단어가 포함된 줄만 골라내기 (형식 체크보다 이게 훨씬 안전합니다)
        if len(parts) >= 3 and "존재" in parts[2]:
            code = parts[0].strip()
            name = parts[1].strip()
            dong_map[name] = code

    st.success(f"✅ {len(dong_map):,}개의 지역 데이터를 성공적으로 불러왔습니다.")

    # 3. 검색 및 데이터 확인
    query = st.text_input("지역명 검색 (예: 종로구)")
    if query:
        results = {k: v for k, v in dong_map.items() if query in k}
        st.write(results)
        
        if results:
            st.info("이제 아래에서 기간을 입력하여 데이터를 수집하세요.")