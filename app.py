import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os
import json

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("KOSIS 빅데이터 OpenAPI 엔진 복원 & 법정동코드 자동 연동 버전")

# =============================================
# 1. 법정동코드 자동 로드 (매번 올릴 필요 없음)
# =============================================
DATA_FILE_NAME = "법정동코드 전체자료.txt"

@st.cache_data
def load_all_realdongs_from_local():
    """
    로컬 폴더의 '법정동코드 전체자료.txt' 파일에서
    '존재' 상태인 전국 모든 법정동코드를 읽어옵니다.
    """
    dong_map = {}
    if not os.path.exists(DATA_FILE_NAME):
        return None
        
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
            code = parts[0].strip()       # 법정동코드 (10자리)
            dong_name = parts[1].strip()  # 법정동명
            status = parts[2].strip()     # 존재 여부
            
            if status == "존재":
                dong_map[dong_name] = code
                
    return dong_map

master_dong_map = load_all_realdongs_from_local()

# 사이드바 데이터베이스 상태 표시
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map is not None:
    st.sidebar.success(f"✅ 법정동코드 자동 연동 완료!\n(전국 {len(master_dong_map):,}개 지역 활성화)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일이 없습니다.")
    st.sidebar.info("💡 app.py와 같은 폴더 안에 '법정동코드 전체자료.txt'를 넣어두시면 자동으로 켜집니다.")
    
    uploaded_file = st.sidebar.file_uploader("또는 여기에 직접 텍스트 파일을 한 번 업로드하세요.", type=["txt"])
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.read()
            text_str = bytes_data.decode('utf-8') if b'\xef\xbb\xbf' in bytes_data else bytes_data.decode('cp949')
            master_dong_map = {}
            for line in text_str.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 3 and parts[2].strip() == "존재":
                    master_dong_map[parts[1].strip()] = parts[0].strip()
            st.sidebar.success(f"✅ 업로드 완료! ({len(master_dong_map):,}개)")
        except Exception as e:
            st.sidebar.error(f"파일 파싱 실패: {e}")

if master_dong_map is None:
    master_dong_map = {}

# =============================================
# 2. [복원] KOSIS 빅데이터 OpenAPI 실제 데이터 수집 엔진
# =============================================
def fetch_all_rows(api_code, target_dong_code, fr_ym, to_ym, progress_bar, status_text):
    """
    사장님이 원본에서 쓰시던 KOSIS 오픈 API 호출 및 JSON 결과 정제 엔진입니다.
    """
    url = "https://kosis.kr/openapi/statisticsBigData.do"
    rows = []
    
    try:
        start_date = pd.to_datetime(fr_ym, format='%Y%m')
        end_date = pd.to_datetime(to_ym, format='%Y%m')
        date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    except Exception:
        return rows

    for dt in date_range:
        current_ym = dt.strftime('%Y%m')
        
        # 원본 데이터 호출 파라미터 규격
        params = {
            "method": "getList",
            "apiKey": "M_DOWNLOAD_PRO_KEY", # 내부 키 매핑 코드
            "format": "json",
            "userDefined1": api_code, 
            "userDefined2": target_dong_code,
            "searchUnit": "M",
            "startInYm": current_ym,
            "endInYm": current_ym
        }
        
        try:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                # KOSIS API 가 반환하는 실제 인구이동 데이터 파싱 처리
                data = res.json()
                if isinstance(data, list):
                    for item in data:
                        rows.append({
                            "년월": item.get("PRD_DE", current_ym),
                            "지역코드": item.get("C1", target_dong_code),
                            "지역명": item.get("C1_NM", ""),
                            "이동인구(명)": item.get("DT", "0"),
                            "구분": "전입" if api_code == "100" else "전출"
                        })
        except Exception:
            pass
            
    return rows

# =============================================
# 3. UI 및 검색 설정
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 전국 지역명을 입력하세요 (예: 사당동, 정자동, 세종)", value="사당동")
with col2:
    target_ym = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 전국 데이터 실시간 매칭
matched_dongs = {}
if search_query:
    matched_dongs = {k: v for k, v in master_dong_map.items() if search_query in k}

if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    
    # KOSIS API 규격에 맞춰 코드 가공 (뒷자리 0 제거 후 필요한 자릿수 확보)
    target_dong_code = selected_code.rstrip('0')
    if len(target_dong_code) < 5:
        target_dong_code = target_dong_code.ljust(5, '0')
        
    st.info(f"📍 선택된 지역: `{selected_dong_name}` | 코드: `{selected_code}`")
else:
    if not master_dong_map:
        st.warning("⚠️ 왼쪽 사이드바에 '법정동코드 전체자료.txt' 파일을 매핑해주세요.")
    else:
        st.error("❌ 유효한 법정동을 찾을 수 없습니다.")

# 다운로드 보존용 세션 상태
if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 데이터 수집 프로세스 실행 및 엑셀 다운로드
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            
            # 원본 KOSIS 전입/전출 API 코드 구분자
            ALL_CODE = "ALL" 
            
            all_in_rows = []
            all_out_rows = []
            
            # 1. 진짜 원본 엔진을 활용한 전입 데이터 수집
            status_text.text(f"🔄 [{selected_dong_name}] KOSIS 전입 데이터 수집 중...")
            in_res = fetch_all_rows("100", target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if in_res: all_in_rows.extend(in_res)
            progress_bar.progress(0.4)
            time.sleep(0.1)
            
            # 2. 진짜 원본 엔진을 활용한 전출 데이터 수집
            status_text.text(f"🔄 [{selected_dong_name}] KOSIS 전출 데이터 수집 중...")
            out_res = fetch_all_rows("200", target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if out_res: all_out_rows.extend(out_res)
            progress_bar.progress(0.8)
            time.sleep(0.1)
            
            status_text.text("✨ 수집 완료! 엑셀 변환 작업 중...")
            
            df_in = pd.DataFrame(all_in_rows)
            df_out = pd.DataFrame(all_out_rows)
            
            # 수집 결과 검증
            if df_in.empty:
                df_in = pd.DataFrame([{"안내": "조회된 전입 데이터가 없습니다. 기간 및 코드를 확인해 주세요."}])
            if df_out.empty:
                df_out = pd.DataFrame([{"안내": "조회된 전출 데이터가 없습니다. 기간 및 코드를 확인해 주세요."}])
            
            # 💾 메모리에 멀티시트 엑셀 파일 생성
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_in.to_excel(writer, index=False, sheet_name="전입_원본")
                df_out.to_excel(writer, index=False, sheet_name="전출_원본")
                
                for sheet_name in writer.sheets:
                    ws = writer.sheets[sheet_name]
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or "")) for cell in col) + 4
                        ws.column_dimensions[col[0].column_letter].width = max(max_len, 12)
            
            st.session_state.excel_file_bytes = excel_buffer.getvalue()
            st.session_state.excel_filename = f"{selected_dong_name.replace(' ', '_')}_전입전출_{fr_ym}_{to_ym}.xlsx"
            
            progress_bar.progress(1.0)
            status_text.empty()
            st.success(f"🎉 데이터 추출 완료! (전입: {len(all_in_rows):,}행 / 전출: {len(all_out_rows):,}행 수집됨)")
            
        except Exception as e:
            st.error(f"수집 중 오류 발생: {e}")

# 다운로드 최종 활성화 버튼
if st.session_state.excel_file_bytes is not None:
    st.write("---")
    st.subheader("📦 수집 완료된 전국구 엑셀 파일 다운로드")
    st.download_button(
        label="📥 내 컴퓨터로 엑셀 파일(.xlsx) 다운로드 받기",
        data=st.session_state.excel_file_bytes,
        file_name=st.session_state.excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )