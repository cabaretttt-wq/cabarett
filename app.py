import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os

st.set_page_config(page_title="전국 전입전출 데이터 추출기", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("텍스트 파일 풀네임 부분 매칭 및 선언부 오류 완벽 수정 버전")

# =============================================
# 1. 로컬 텍스트 파일 로드 (오류 원천 차단)
# =============================================
DATA_FILE_NAME = "법정동코드 전체자료.txt"

@st.cache_data
def load_dong_map_final():
    """
    텍스트 파일에서 데이터를 읽어와 안전하게 맵을 구성합니다.
    제목 줄(헤더)이나 빈 줄로 인한 오류를 원천 차단합니다.
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
        if not line.strip():
            continue
            
        parts = line.split('\t')
        if len(parts) < 3:
            continue
            
        code = parts[0].strip()       # 10자리 코드
        dong_name = parts[1].strip()  # 전체 지역명 (예: 서울특별시 동작구 사당동)
        status = parts[2].strip()     # 존재 여부
        
        # 첫 줄 헤더이거나 '존재' 상태가 아니면 제외
        if code == "법정동코드" or status != "존재":
            continue
            
        # 전체 주소명을 키(Key)로, 10자리 코드를 값(Value)으로 저장
        dong_map[dong_name] = str(code)
                
    return dong_map

# [교정 완료] 오타를 지우고 안전하게 데이터베이스 로드
master_dong_map = load_dong_map_final()

# 사이드바 데이터베이스 상태 표시
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map is not None:
    st.sidebar.success(f"✅ 법정동코드 파일 연동 완료\n(전국 {len(master_dong_map):,}개 구역 활성화)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일이 없습니다.")
    st.sidebar.info("💡 app.py 파일과 같은 위치(폴더)에 '법정동코드 전체자료.txt' 파일을 넣어주세요.")
    
    uploaded_file = st.sidebar.file_uploader("또는 여기에 직접 텍스트 파일을 업로드하세요.", type=["txt"])
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
            st.sidebar.success(f"✅ 업로드 완료! ({len(master_dong_map):,}개)")
        except Exception as e:
            st.sidebar.error(f"파일 읽기 실패: {e}")

if master_dong_map is None:
    master_dong_map = {}

# =============================================
# 2. 행정안전부 주민등록 인구통계 테이블 크롤링 엔진
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
        
        # 10자리 코드를 온전하게 변수 매핑하여 요청 보냄
        payload = {
            "searchType": "month",
            "searchGubun": str(search_gubun),   # 전입(100), 전출(200)
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
            time.sleep(0.15) # 과부하 방지 지연
        except Exception:
            pass
            
    return rows

# =============================================
# 3. 사용자 인터페이스 (KeyError 원천 차단 매칭)
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 전국 지역명을 입력하세요 (예: 사당, 정자, 세종)", value="사당동")
with col2:
    target_ym = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 사용자가 입력한 키워드가 풀네임 주소에 '포함'되어 있는지 체크하여 매칭
matched_dongs = {}
if search_query:
    query_str = search_query.strip()
    matched_dongs = {k: v for k, v in master_dong_map.items() if query_str in k}

target_dong_code = None
selected_dong_name = ""

if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    target_dong_code = matched_dongs.get(selected_dong_name)
    
    if target_dong_code:
        st.info(f"📍 선택된 지역: `{selected_dong_name}` | 전송용 10자리 고유코드: `{target_dong_code}`")
else:
    if not master_dong_map:
        st.warning("⚠️ 왼쪽 사이드바 상태를 확인하시거나 '법정동코드 전체자료.txt' 파일을 연결해 주세요.")
    else:
        st.error("❌ 일치하는 지역을 찾을 수 없습니다. 검색어를 짧게 입력해 보세요. (예: 사당동 -> 사당)")

if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 수집 가동 및 멀티 시트 엑셀 생성
# =============================================
if st.button("🚀 데이터 일괄 수집 시작", type="primary"):
    if not target_dong_code:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            
            IN_CODE = "100"
            OUT_CODE = "200"
            
            all_in_rows = []
            all_out_rows = []
            
            # 1. 전입 수집
            status_text.text(f"🔄 [{selected_dong_name}] 전입 데이터 수집 중...")
            in_res = fetch_all_rows(IN_CODE, target_dong_code, fr_ym, to_ym)
            if in_res: all_in_rows.extend(in_res)
            progress_bar.progress(0.4)
            
            # 2. 전출 수집
            status_text.text(f"🔄 [{selected_dong_name}] 전출 데이터 수집 중...")
            out_res = fetch_all_rows(OUT_CODE, target_dong_code, fr_ym, to_ym)
            if out_res: all_out_rows.extend(out_res)
            progress_bar.progress(0.8)
            
            status_text.text("✨ 수집 완료! 엑셀 서식 변환 중...")
            
            df_in = pd.DataFrame(all_in_rows)
            df_out = pd.DataFrame(all_out_rows)
            
            if df_in.empty:
                df_in = pd.DataFrame([{"결과": "해당 기간 내 전입 데이터가 존재하지 않습니다."}])
            if df_out.empty:
                df_out = pd.DataFrame([{"결과": "해당 기간 내 전출 데이터가 존재하지 않습니다."}])
            
            # 메모리 내에 데이터 엑셀화
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
            st.success(f"🎉 성공적으로 추출되었습니다! (전입: {len(all_in_rows):,}행 / 전출: {len(all_out_rows):,}행)")
            
        except Exception as e:
            st.error(f"수집 프로세스 중 오류가 발생했습니다: {e}")

# 다운로드 컴포넌트 활성화
if st.session_state.excel_file_bytes is not None:
    st.write("---")
    st.subheader("📦 수집 완료된 엑셀 파일 다운로드")
    st.download_button(
        label="📥 내 컴퓨터로 엑셀 파일(.xlsx) 다운로드 받기",
        data=st.session_state.excel_file_bytes,
        file_name=st.session_state.excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )