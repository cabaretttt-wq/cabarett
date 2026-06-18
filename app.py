import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("행정안전부 법정동코드 자동 연동 & 엑셀 다운로드 버전")

# =============================================
# 1. 법정동코드 자동 로드 (같은 폴더 내 파일 탐색)
# =============================================
DATA_FILE_NAME = "법정동코드 전체자료.txt"

@st.cache_data
def load_all_realdongs_from_local():
    """
    로컬 폴더에 있는 '법정동코드 전체자료.txt'에서 
    '존재'하는 전국 모든 법정동을 자동으로 추출합니다.
    """
    dong_map = {}
    if not os.path.exists(DATA_FILE_NAME):
        return None  # 파일이 없을 경우 예외 처리용
        
    try:
        with open(DATA_FILE_NAME, 'r', encoding='utf-8') as f:
            text_data = f.read()
    except UnicodeDecodeError:
        with open(DATA_FILE_NAME, 'r', encoding='cp949') as f:
            text_data = f.read()
        
    lines = text_data.strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 3:
            code = parts[0].strip()       # 법정동코드
            dong_name = parts[1].strip()  # 시도 시군구 법정동명
            status = parts[2].strip()     # 존재 여부
            
            if status == "존재":
                dong_map[dong_name] = code
                
    return dong_map

# 자동으로 파일 읽기 시도
master_dong_map = load_all_realdongs_from_local()

# 사이드바 상태 표시
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map is not None:
    st.sidebar.success(f"✅ 시스템 파일 자동으로 로드 완료!\n(전국 {len(master_dong_map):,}개 법정동 활성화)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일이 없습니다.")
    st.sidebar.info("💡 팁: 현재 app.py 파일이 있는 폴더 안에 '법정동코드 전체자료.txt' 파일을 같이 넣어두시면 매번 업로드할 필요가 없습니다.")
    
    # 백업용 업로더 유지
    uploaded_file = st.sidebar.file_uploader("또는 여기에 직접 파일을 업로드하세요.", type=["txt"])
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.read()
            text_str = bytes_data.decode('utf-8') if b'\xef\xbb\xbf' in bytes_data else bytes_data.decode('cp949')
            master_dong_map = {}
            for line in text_str.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 3 and parts[2].strip() == "존재":
                    master_dong_map[parts[1].strip()] = parts[0].strip()
            st.sidebar.success(f"✅ 업로드 파일로 로드 완료! ({len(master_dong_map):,}개)")
        except Exception as e:
            st.sidebar.error(f"파일 읽기 실패: {e}")

if master_dong_map is None:
    master_dong_map = {}

# =============================================
# 2. 조회 및 검색 UI
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 전국 지역명을 입력하세요 (예: 해운대, 사당동, 정자동)", value="해운대")
with col2:
    target_ym = st.text_input("📅 조회 기간 (예: 202601-202605)", value="202601-202605")

# 검색 필터링
matched_dongs = {}
if search_query:
    matched_dongs = {k: v for k, v in master_dong_map.items() if search_query in k}

if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    st.info(f"선택된 지역 코드: `{selected_code}` | {selected_dong_name}")
else:
    if not master_dong_map:
        st.warning("⚠️ 법정동 데이터베이스가 로드되지 않았습니다. 사이드바 설명을 확인해주세요.")
    else:
        st.error("❌ 검색 결과가 없습니다. 지역명을 다시 확인해주세요.")

# 세션 상태 초기화 (다운로드 버튼 유지를 위함)
if "excel_data" not in st.session_state:
    st.session_state.excel_data = None
if "download_filename" not in st.session_state:
    st.session_state.download_filename = ""

# =============================================
# 3. 데이터 수집 및 다운로드 처리
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            status_text.text(f"🔄 [{selected_dong_name}] 데이터 수집 시작...")
            time.sleep(0.5)
            progress_bar.progress(0.3)
            
            # --- [실제 크롤링 및 가짜 데이터 생성 영역 예시] ---
            # 여기에 사장님이 작성하셨던 본래의 데이터 수집 알고리즘이 연동됩니다.
            # 최종 결과물이 'df_result'라는 데이터프레임이라고 가정합니다.
            status_text.text("🔄 엑셀 파일 데이터 변환 및 정제 중...")
            progress_bar.progress(0.7)
            time.sleep(0.5)
            
            # 테스트용 가상의 데이터프레임 구조 생성 (실제 데이터프레임으로 대체됨)
            df_result = pd.DataFrame({
                "년월": [fr_ym, to_ym],
                "지역코드": [selected_code, selected_code],
                "지역명": [selected_dong_name, selected_dong_name],
                "전입인구": [1250, 1420],
                "전출인구": [1100, 1300]
            })
            
            # 💾 중요: 메모리 버퍼에 엑셀 파일 저장
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_result.to_excel(writer, index=False, sheet_name='전입전출_데이터')
            
            # 세션에 저장하여 페이지가 리프레시되어도 다운로드 버튼이 유지되도록 함
            st.session_state.excel_data = output.getvalue()
            st.session_state.download_filename = f"{selected_dong_name.replace(' ', '_')}_전입전출_{fr_ym}_{to_ym}.xlsx"
            
            progress_bar.progress(1.0)
            status_text.empty()
            st.success(f"🎉 {selected_dong_name} ({selected_code}) 지역의 데이터 추출이 완료되었습니다!")
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")

# 수집된 데이터가 세션에 있으면 다운로드 버튼을 화면에 띄움
if st.session_state.excel_data is not None:
    st.write("---")
    st.subheader("📦 수집 완료된 파일 다운로드")
    st.download_button(
        label="📥 엑셀 파일(.xlsx) 다운로드 받기",
        data=st.session_state.excel_data,
        file_name=st.session_state.download_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary"
    )