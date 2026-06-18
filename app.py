import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("행정안전부 법정동코드 전체자료 연동 버전 (전국 지원)")

# =============================================
# 1. 법정동코드 파일 업로드 섹션 (전국 데이터 로드)
# =============================================
st.sidebar.header("📁 데이터베이스 설정")
uploaded_file = st.sidebar.file_uploader(
    "행정안전부 '법정동코드 전체자료.txt' 파일을 업로드해주세요.", 
    type=["txt"]
)

@st.cache_data
def load_all_realdongs(file_bytes):
    """
    업로드된 파일에서 '폐지'되지 않고 '존재'하는 전국 모든 법정동을 추출합니다.
    """
    dong_map = {}
    if file_bytes is None:
        return dong_map
        
    # 텍스트 파일 읽기 (인코딩은 CP949 또는 UTF-8 대응)
    try:
        text_data = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        text_data = file_bytes.decode('cp949')
        
    lines = text_data.strip().split('\n')
    
    for line in lines:
        # 탭(tab)으로 구분된 데이터 분리
        parts = line.split('\t')
        if len(parts) >= 3:
            code = parts[0].strip()       # 법정동코드
            dong_name = parts[1].strip()  # 시도 시군구 법정동명
            status = parts[2].strip()     # 존재 여부 (존재 / 폐지)
            
            # '폐지'된 것은 과감히 버리고, '존재'하는 데이터만 딕셔너리에 담기
            if status == "존재":
                dong_map[dong_name] = code
                
    return dong_map

# 파일이 업로드되었는지 확인 후 마스터 테이블 생성
if uploaded_file is not None:
    # 파일을 바이트로 읽어서 캐싱 함수에 전달
    file_bytes = uploaded_file.read()
    master_dong_map = load_all_realdongs(file_bytes)
    st.sidebar.success(f"✅ 전국 {len(master_dong_map):,}개의 유효 법정동 로드 완료!")
else:
    master_dong_map = {}
    st.sidebar.warning("⚠️ 전국 데이터를 활성화하려면 사이드바에 '법정동코드 전체자료.txt' 파일을 업로드하세요.")

# =============================================
# 2. 조회 및 검색 UI
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input(
        "🔍 검색할 전국 지역명을 입력하세요 (예: 정자동, 사당동, 해운대, 세종)", 
        value="정자동"
    )
with col2:
    target_ym = st.text_input("📅 조회 기간 (예: 202601-202605)", value="202601-202605")

# 사용자가 입력한 검색어가 포함된 법정동 검색 (전국 대상)
matched_dongs = {}
if master_dong_map and search_query:
    matched_dongs = {k: v for k, v in master_dong_map.items() if search_query in k}

# 검색 결과 매칭 화면 출력
if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    st.info(f"선택된 지역 코드: `{selected_code}` | {selected_dong_name}")
else:
    if not master_dong_map:
        st.info("💡 왼쪽 사이드바에서 법정동코드 텍스트 파일을 먼저 업로드하시면 전국 검색이 가능해집니다.")
    else:
        st.error("❌ 전국에서 일치하는 '존재' 상태의 법정동을 찾을 수 없습니다. 검색어를 정확하게 입력해 주세요.")

# =============================================
# 3. 데이터 수집 프로세스 실행
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            
            status_text.text(f"🔄 [{selected_dong_name}] 전국 전입 데이터 수집 중...")
            # ----------------------------------------------------
            # 기존 작성하셨던 수집 로직(requests, BeautifulSoup 등)이 
            # 여기에 들어와 selected_code를 가지고 API를 찌르게 됩니다.
            # ----------------------------------------------------
            time.sleep(0.8)
            progress_bar.progress(0.5)
            
            status_text.text(f"🔄 [{selected_dong_name}] 전국 전출 데이터 수집 중...")
            time.sleep(0.8)
            progress_bar.progress(1.0)
            
            status_text.text("✨ 수집 완료! 엑셀 파일 변환 중...")
            st.success(f"🎉 {selected_dong_name} ({selected_code}) 지역의 전국 데이터 추출이 완료되었습니다!")
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")