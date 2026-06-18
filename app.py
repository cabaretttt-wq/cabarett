import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os
import re

st.set_page_config(page_title="전국 전입전출 데이터 추출기", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("모든 오류 및 예외 상황(오타, 파일없음, 매칭실패) 통합 방어 버전")

# =============================================
# 1. 로컬 텍스트 파일 로드 (모든 예외상황 완벽 방어)
# =============================================
DATA_FILE_NAME = "법정동코드 전체자료.txt"

@st.cache_data(show_spinner=False)
def load_dong_map_final():
    dong_map = {}
    if not os.path.exists(DATA_FILE_NAME):
        return None
        
    try:
        with open(DATA_FILE_NAME, 'r', encoding='utf-8') as f:
            text_data = f.read()
    except UnicodeDecodeError:
        try:
            with open(DATA_FILE_NAME, 'r', encoding='cp949') as f:
                text_data = f.read()
        except Exception:
            return None
    except Exception:
        return None
        
    lines = text_data.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
            
        parts = line.split('\t')
        if len(parts) < 3:
            continue
            
        code = parts[0].strip()       
        dong_name = parts[1].strip()  
        status = parts[2].strip()     
        
        # 첫 줄 헤더이거나 '존재' 상태가 아니면 제외
        if code == "법정동코드" or status != "존재":
            continue
            
        # 전체 주소명(Key), 10자리 코드(Value)
        dong_map[dong_name] = str(code)
                
    return dong_map

# [오류 해결] 함수 이름 오타를 완벽히 제거하고 안전하게 로드
master_dong_map = load_dong_map_final()

# 사이드바 데이터베이스 상태 표시
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map:
    st.sidebar.success(f"✅ 법정동코드 연동 완료\n(전국 {len(master_dong_map):,}개 구역)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일이 없습니다.")
    st.sidebar.info("💡 app.py와 같은 폴더에 '법정동코드 전체자료.txt'를 넣어주세요.")
    
    uploaded_file = st.sidebar.file_uploader("또는 텍스트 파일을 직접 업로드하세요", type=["txt"])
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.read()
            text_str = bytes_data.decode('utf-8') if b'\xef\xbb\xbf' in bytes_data else bytes_data.decode('cp949')
            master_dong_map = {}
            for line in text_str.strip().split('\n'):
                if not line.strip(): continue
                parts = line.split('\t')
                if len(parts) >= 3 and parts[2].strip() == "존재" and parts[0].strip() != "법정동코드":
                    master_dong_map[parts[1].strip()] = parts[0].strip()
            st.sidebar.success(f"✅ 업로드 연동 완료! ({len(master_dong_map):,}개)")
        except Exception as e:
            st.sidebar.error(f"파일 읽기 실패: {e}")

if master_dong_map is None:
    master_dong_map = {}

# =============================================
# 2. 크롤링 엔진
# =============================================
def fetch_all_rows(search_gubun, target_dong_code, fr_ym, to_ym):
    url = "https://stat.moi.go.kr/WMO/stat/statMain.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://stat.moi.go.kr/"
    }
    rows = []
    
    try:
        start_date = pd.to_datetime(fr_ym, format='%Y%m')
        end_date = pd.to_datetime(to_ym, format='%Y%m')
        date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    except Exception:
        return rows

    session = requests.Session()
    
    for dt in date_range:
        current_ym = dt.strftime('%Y%m')
        
        payload = {
            "searchType": "month",
            "searchGubun": str(search_gubun),   
            "dongCode": str(target_dong_code).strip(),  
            "startInYm": str(current_ym),
            "endInYm": str(current_ym)
        }
        
        try:
            res = session.post(url, data=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                table_rows = soup.select("#cubeGrid tbody tr")
                
                for tr in table_rows:
                    cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(cols) >= 4:
                        rows.append({
                            "조회년월": current_ym,
                            "행정구역명": cols[0],
                            "이동사유": cols[1],
                            "전입지/전출지": cols[2],
                            "이동인구수(명)": cols[3]
                        })
            time.sleep(0.1) 
        except Exception:
            pass
            
    return rows

# =============================================
# 3. 메인 UI 및 오류 방지 로직
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 지역명 (예: 사당, 정자)", value="사당")
with col2:
    target_ym_input = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 검색어 매칭 (안전장치 추가)
matched_dongs = {}
if search_query and master_dong_map:
    query_str = search_query.strip()
    matched_dongs = {k: v for k, v in master_dong_map.items() if query_str in k}

target_dong_code = None
selected_dong_name = ""

if matched_dongs:
    selected_dong_name = st.selectbox("📌 정확한 법정동을 선택해주세요", list(matched_dongs.keys()))
    target_dong_code = matched_dongs.get(selected_dong_name)
    
    if target_dong_code:
        st.info(f"📍 선택 완료: `{selected_dong_name}` (코드: `{target_dong_code}`)")
elif search_query and not matched_dongs:
    st.error("❌ 일치하는 지역이 없습니다. 검색어를 줄여보세요. (예: '사당동' 대신 '사당')")

if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 데이터 수집 및 엑셀 다운로드
# =============================================
if st.button("🚀 데이터 일괄 수집 시작", type="primary"):
    # 1차 검증: 코드 유무
    if not target_dong_code:
        st.warning("유효한 지역이 선택되지 않았습니다.")
        st.stop()
        
    # 2차 검증: 날짜 포맷팅 안전 처리 (- 이외의 기호를 넣어도 자동 교정)
    clean_ym = re.sub(r'[^0-9\-~]', '', target_ym_input).replace('~', '-')
    if '-' in clean_ym:
        parts = clean_ym.split('-')
        fr_ym, to_ym = parts[0], parts[1]
    else:
        fr_ym = to_ym = clean_ym

    if len(fr_ym) != 6 or len(to_ym) != 6:
        st.error("❌ 날짜 형식이 잘못되었습니다. (YYYYMM-YYYYMM 형식으로 입력해주세요)")
        st.stop()

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    
    try:
        IN_CODE = "100"
        OUT_CODE = "200"
        
        all_in_rows = []
        all_out_rows = []
        
        # 전입 데이터 수집
        status_text.text(f"🔄 [{selected_dong_name}] 전입 데이터 수집 중...")
        in_res = fetch_all_rows(IN_CODE, target_dong_code, fr_ym, to_ym)
        if in_res: all_in_rows.extend(in_res)
        progress_bar.progress(0.4)
        
        # 전출 데이터 수집
        status_text.text(f"🔄 [{selected_dong_name}] 전출 데이터 수집 중...")
        out_res = fetch_all_rows(OUT_CODE, target_dong_code, fr_ym, to_ym)
        if out_res: all_out_rows.extend(out_res)
        progress_bar.progress(0.8)
        
        status_text.text("✨ 수집 완료! 엑셀 서식 변환 중...")
        
        df_in = pd.DataFrame(all_in_rows)
        df_out = pd.DataFrame(all_out_rows)
        
        if df_in.empty:
            df_in = pd.DataFrame([{"결과": "해당 기간 내 전입 데이터가 없습니다."}])
        if df_out.empty:
            df_out = pd.DataFrame([{"결과": "해당 기간 내 전출 데이터가 없습니다."}])
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_in.to_excel(writer, index=False, sheet_name="전입_원본")
            df_out.to_excel(writer, index=False, sheet_name="전출_원본")
            
            # 셀 너비 자동 조정
            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col) + 4
                    ws.column_dimensions[col[0].column_letter].width = max(max_len, 12)
                    
        st.session_state.excel_file_bytes = excel_buffer.getvalue()
        
        # 파일명 저장 시 윈도우에서 에러를 뱉는 특수문자 자동 제거
        safe_name = re.sub(r'[\\/*?:"<>|]', "", selected_dong_name).replace(' ', '_')
        st.session_state.excel_filename = f"{safe_name}_전입전출_{fr_ym}_{to_ym}.xlsx"
        
        progress_bar.progress(1.0)
        status_text.empty()
        st.success(f"🎉 성공적으로 추출되었습니다! (전입: {len(all_in_rows):,}행 / 전출: {len(all_out_rows):,}행)")
        
    except Exception as e:
        st.error(f"수집 중 오류가 발생했습니다: {e}")

if st.session_state.excel_file_bytes is not None:
    st.write("---")
    st.subheader("📦 수집 완료된 엑셀 파일 다운로드")
    st.download_button(
        label="📥 내 컴퓨터로 엑셀 파일 다운로드 받기",
        data=st.session_state.excel_file_bytes,
        file_name=st.session_state.excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )