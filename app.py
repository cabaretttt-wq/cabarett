import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("행정안전부 법정동코드 자동 연동 (폐지 제외) & 엑셀 즉시 다운로드 버전")

# =============================================
# 1. 법정동코드 자동 로드 (매번 파일 업로드할 필요 없음)
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
            
            # '폐지'된 동은 제외하고 오직 '존재'하는 동만 필터링하여 저장
            if status == "존재":
                dong_map[dong_name] = code
                
    return dong_map

# 백그라운드에서 로컬 텍스트 마스터 파일 자동 검색 및 로드
master_dong_map = load_all_realdongs_from_local()

# 사이드바 데이터베이스 상태 관리 인터페이스
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map is not None:
    st.sidebar.success(f"✅ 법정동코드 자동 연동 완료!\n(전국 {len(master_dong_map):,}개 유효 지역 활성화)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일이 없습니다.")
    st.sidebar.info("💡 해결 방법: 이 app.py 파일이 저장되어 실행되는 폴더(디렉토리) 안에 '법정동코드 전체자료.txt' 파일을 같이 복사해 넣어두시면 매번 번거롭게 업로드하지 않아도 자동으로 인식합니다.")
    
    # 비상용 수동 업로더 유지
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
# 2. [복원 완료] 사장님의 진짜 데이터 수집 크롤링 엔진
# =============================================
def fetch_all_rows(api_code, target_dong_code, fr_ym, to_ym, progress_bar, status_text):
    """
    행정안전부 주민등록 인구통계 시스템에서 
    실제 선택한 기간(fr_ym ~ to_ym)의 전입/전출 데이터를 직접 긁어오는 핵심 엔진입니다.
    """
    url = "https://stat.moi.go.kr/WMO/stat/statMain.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://stat.moi.go.kr/"
    }
    rows = []
    
    try:
        # 화면에서 입력된 조회 기간(예: 202301-202312)을 월별 날짜 배열로 생성
        start_date = pd.to_datetime(fr_ym, format='%Y%m')
        end_date = pd.to_datetime(to_ym, format='%Y%m')
        date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    except Exception:
        return rows

    total_months = len(date_range)
    
    # 설정한 기간 동안 한 달씩 순회하면서 통계 데이터 수집
    for idx, dt in enumerate(date_range):
        current_ym = dt.strftime('%Y%m')
        
        # 행안부 서버가 요구하는 파라미터 세팅
        payload = {
            "searchType": "month",
            "searchGubun": api_code,       # 전입/전출 코드
            "dongCode": target_dong_code,  # 가공된 지역 코드
            "startInYm": current_ym,
            "endInYm": current_ym
        }
        
        try:
            res = requests.post(url, data=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                # 웹사이트 화면 안의 실제 테이블 행(tr) 파싱
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
        except Exception:
            pass
            
    return rows

# =============================================
# 3. 사용자 검색 및 조회 기간 UI 구성
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 전국 지역명을 입력하세요 (예: 사당동, 정자동, 세종)", value="사당동")
with col2:
    # 사장님이 화면에서 수정한 기간이 정상적으로 서버에 반영되도록 동적 입력창 연동
    target_ym = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 전국 '존재' 테이블에서 실시간 검색어 필터링
matched_dongs = {}
if search_query:
    matched_dongs = {k: v for k, v in master_dong_map.items() if search_query in k}

if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    
    # 10자리 법정동코드를 사장님 크롤러 통신 규격(뒷자리 0 제거 후 5자리화)에 맞춤 가공
    target_dong_code = selected_code.rstrip('0')
    if len(target_dong_code) < 5:
        target_dong_code = target_dong_code.ljust(5, '0')
        
    st.info(f"📍 선택된 지역: `{selected_dong_name}` | 법정동코드: `{selected_code}`")
else:
    if not master_dong_map:
        st.warning("⚠️ 왼쪽 사이드바 설명을 참고하여 '법정동코드 전체자료.txt' 파일 위치를 확인해주세요.")
    else:
        st.error("❌ 해당 이름을 가진 '존재' 상태의 법정동을 찾을 수 없습니다. 지역명을 다시 확인해주세요.")

# Streamlit 세션 상태 초기화 (다운로드용 엑셀 데이터 증발 방지 보호벽)
if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 일괄 크롤링 가동 및 멀티 시트 엑셀 다운로드
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            # 사용자가 화면에 입력한 기간 파싱 (하이픈 분리)
            fr_ym, to_ym = target_ym.split('-')
            
            # 행안부 시스템 전입(100) 및 전출(200) 고유 신호 정의
            IN_CODE = "100"
            OUT_CODE = "200"
            
            all_in_rows = []
            all_out_rows = []
            
            # 1. 전입 데이터 크롤링 엔진 구동
            status_text.text(f"🔄 [{selected_dong_name}] 해당 기간 실제 전입 데이터 수집 중...")
            in_res = fetch_all_rows(IN_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if in_res: all_in_rows.extend(in_res)
            progress_bar.progress(0.4)
            time.sleep(0.1)
            
            # 2. 전출 데이터 크롤링 엔진 구동
            status_text.text(f"🔄 [{selected_dong_name}] 해당 기간 실제 전출 데이터 수집 중...")
            out_res = fetch_all_rows(OUT_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if out_res: all_out_rows.extend(out_res)
            progress_bar.progress(0.8)
            time.sleep(0.1)
            
            status_text.text("✨ 수집 완료! 다운로드용 엑셀 파일 변환 중...")
            
            df_in = pd.DataFrame(all_in_rows)
            df_out = pd.DataFrame(all_out_rows)
            
            # 데이터 수집 결과 안전 예외 처리
            if df_in.empty:
                df_in = pd.DataFrame([{"안내": "해당 기간에 조회된 전입 데이터가 없거나 서버가 응답하지 않았습니다."}])
            if df_out.empty:
                df_out = pd.DataFrame([{"안내": "해당 기간에 조회된 전출 데이터가 없거나 서버가 응답하지 않았습니다."}])
            
            # 💾 중요: 가상 메모리에 엑셀 통합 마스터 멀티시트 생성
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_in.to_excel(writer, index=False, sheet_name="전입_원본")
                df_out.to_excel(writer, index=False, sheet_name="전출_원본")
                
                # 엑셀 열 너비 자동 최적화 배치 정제
                for sheet_name in writer.sheets:
                    ws = writer.sheets[sheet_name]
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or "")) for cell in col) + 4
                        ws.column_dimensions[col[0].column_letter].width = max(max_len, 12)
            
            # 다운로드 데이터와 고유 파일명을 브라우저 세션에 저장
            st.session_state.excel_file_bytes = excel_buffer.getvalue()
            st.session_state.excel_filename = f"{selected_dong_name.replace(' ', '_')}_전입전출_{fr_ym}_{to_ym}.xlsx"
            
            progress_bar.progress(1.0)
            status_text.empty()
            st.success(f"🎉 추출 완료! (실제 전입: {len(all_in_rows):,}행 / 전출: {len(all_out_rows):,}행 수집되었습니다.)")
            
        except Exception as e:
            st.error(f"데이터 수집 및 크롤링 처리 중 예외 오류 발생: {e}")

# 세션에 다운로드할 파일이 준비되어 있으면 마우스 클릭용 다운로드 버튼 활성화
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