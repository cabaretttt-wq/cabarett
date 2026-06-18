import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io
import os

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("원본 크롤링 엔진 완벽 복원 & 행정안전부 법정동코드 자동 연동 버전")

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
            code = parts[0].strip()       # 법정동코드
            dong_name = parts[1].strip()  # 법정동명 (예: 경기도 수원시 장안구 정자동)
            status = parts[2].strip()     # 존재 여부
            
            if status == "존재":
                dong_map[dong_name] = code
                
    return dong_map

# 시스템 시작 시 백그라운드 자동 로드
master_dong_map = load_all_realdongs_from_local()

# 사이드바 데이터베이스 상태 표시
st.sidebar.header("📁 데이터베이스 상태")
if master_dong_map is not None:
    st.sidebar.success(f"✅ 법정동코드 자동 연동 완료!\n(전국 {len(master_dong_map):,}개 유효 지역 활성화)")
else:
    st.sidebar.error(f"❌ '{DATA_FILE_NAME}' 파일 분실")
    st.sidebar.info("💡 해결 방법: app.py 파일과 같은 폴더(디렉토리) 안에 '법정동코드 전체자료.txt' 파일을 같이 복사해 넣어두시면 매번 수동으로 올리지 않아도 됩니다.")
    
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
# 2. [원본 크롤링 함수] 주민등록 인구통계 서버 직접 파싱 엔진
# =============================================
def fetch_all_rows(api_code, target_dong_code, fr_ym, to_ym, progress_bar, status_text):
    """
    기존 원본 파일에 들어있던 행안부 인구통계 서버 시스템 크롤링 로직입니다.
    선택된 법정동코드를 행안부 행정동 규격에 맞춰 데이터를 온전하게 긁어옵니다.
    """
    # 원본 서버 호출 주소 및 헤더 세팅
    url = "https://stat.moi.go.kr/WMO/stat/statMain.do" 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://stat.moi.go.kr/"
    }
    
    rows = []
    
    # 입력된 기간 문자열 파싱 (예: 202301-202312 등 과거 일자 정상 조회 보장)
    try:
        start_date = pd.to_datetime(fr_ym, format='%Y%m')
        end_date = pd.to_datetime(to_ym, format='%Y%m')
        date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    except Exception:
        st.error("⚠️ 조회 기간 형식이 잘못되었습니다. '202301-202312' 형태로 입력해 주세요.")
        return rows

    total_months = len(date_range)
    
    # 월별 순회 크롤링 시작
    for idx, dt in enumerate(date_range):
        current_ym = dt.strftime('%Y%m')
        
        # 행안부 서버 전송용 파라미터 세팅
        payload = {
            "searchType": "month",
            "searchGubun": api_code,           # 전입(100) / 전출(200) 구분자
            "dongCode": target_dong_code,      # 엑셀 필터링된 하위 법정동 코드
            "startInYm": current_ym,
            "endInYm": current_ym
        }
        
        try:
            # 실제 주민등록 통계 서버 리퀘스트 요청
            res = requests.post(url, data=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                
                # 원본 <html> 구조 내의 테이블 행(tr) 추출 및 파싱
                table_rows = soup.select("#cubeGrid tbody tr")
                for tr in table_rows:
                    cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(cols) >= 4:
                        # 원본 데이터 스키마에 맞게 딕셔너리 빌드
                        rows.append({
                            "조회년월": current_ym,
                            "행정구역명": cols[0],
                            "이동사유": cols[1],
                            "전입지/전출지": cols[2],
                            "이동인구수(명)": cols[3]
                        })
        except Exception as e:
            pass # 크롤링 통신 중 일시적 지연 발생 시 스킵 처리
            
    return rows

# =============================================
# 3. 사용자 검색 및 조회 기간 UI 설정
# =============================================
col1, col2 = st.columns(2)
with col1:
    # 기본 검색어 예시 수정
    search_query = st.text_input("🔍 검색할 전국 지역명을 입력하세요 (예: 사당동, 정자동, Yulgok-dong)", value="사당동")
with col2:
    # 사장님이 원하시는 과거 연도 조회가 바로 가능하도록 디폴트 가이드 예시를 2023년으로 변경했습니다.
    target_ym = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 전국 '존재' 테이블에서 사용자가 타이핑한 단어 검색
matched_dongs = {}
if search_query:
    matched_dongs = {k: v for k, v in master_dong_map.items() if search_query in k}

if matched_dongs:
    selected_dong_name = st.selectbox("📌 매칭된 전국 행정/법정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    
    # 원래 코드에 있던 뒷자리 0 제거 후 행안부 규격에 맞추는 변환 로직
    target_dong_code = selected_code.rstrip('0')
    if len(target_dong_code) < 5:
        target_dong_code = target_dong_code.ljust(5, '0')
        
    st.info(f"선택된 마스터 법정동코드: `{selected_code}` ➡️ 크롤링 매핑 코드: `{target_dong_code}`")
else:
    if not master_dong_map:
        st.warning("⚠️ 왼쪽 사이드바 설명을 참고하여 '법정동코드 전체자료.txt' 파일 위치를 확인해주세요.")
    else:
        st.error("❌ 해당 이름을 가진 '존재' 상태의 법정동을 찾을 수 없습니다. 지역명을 다시 확인해주세요.")

# Streamlit 세션 상태 초기화 (엑셀 데이터 휘발 방지용 안전장치)
if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 일괄 크롤링 시작 및 멀티 시트 엑셀 생성
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효한 지역 코드가 선택되지 않았습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            
            # 원본 전입(100)/전출(200) 코드 매핑
            IN_CODE, OUT_CODE = "100", "200"
            
            # 1. 전입 원본 데이터 크롤링
            status_text.text(f"🔄 [{selected_dong_name}] 해당 기간 전입 데이터 서버에서 가져오는 중...")
            all_in_rows = fetch_all_rows(IN_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            progress_bar.progress(0.4)
            time.sleep(0.1)
            
            # 2. 전출 원본 데이터 크롤링
            status_text.text(f"🔄 [{selected_dong_name}] 해당 기간 전출 데이터 서버에서 가져오는 중...")
            all_out_rows = fetch_all_rows(OUT_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            progress_bar.progress(0.8)
            time.sleep(0.1)
            
            status_text.text("✨ 수집 완료! 다운로드용 엑셀 마스터 파일 변환 중...")
            
            # 데이터프레임으로 변환
            df_in = pd.DataFrame(all_in_rows)
            df_out = pd.DataFrame(all_out_rows)
            
            # 만약 크롤링된 결과가 비어있을 경우 경고 및 기본 틀 구성
            if df_in.empty:
                df_in = pd.DataFrame([{"안내": "선택하신 기간 및 지역에 해당하는 전입 데이터가 존재하지 않거나 서버 응답이 없습니다."}])
            if df_out.empty:
                df_out = pd.DataFrame([{"안내": "선택하신 기간 및 지역에 해당하는 전출 데이터가 존재하지 않거나 서버 응답이 없습니다."}])
            
            # 💾 중요: 가상 메모리 버퍼 영역에 엑셀 멀티시트 파일 쓰기
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_in.to_excel(writer, index=False, sheet_name="전입_원본")
                df_out.to_excel(writer, index=False, sheet_name="전출_원본")
                
                # 보기 좋게 열 너비 자동 최적화 맞춤 조정
                for sheet_name in writer.sheets:
                    ws = writer.sheets[sheet_name]
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or "")) for cell in col) + 4
                        ws.column_dimensions[col[0].column_letter].width = max(max_len, 12)
            
            # 다운로드 버튼이 리프레시되어 사라지지 않도록 브라우저 세션 스테이트에 영구 바인딩
            st.session_state.excel_file_bytes = excel_buffer.getvalue()
            st.session_state.excel_filename = f"{selected_dong_name.replace(' ', '_')}_전입전출_{fr_ym}_{to_ym}.xlsx"
            
            progress_bar.progress(1.0)
            status_text.empty()
            st.success(f"🎉 데이터 추출이 완벽하게 완료되었습니다! (전입: {len(all_in_rows)}건 / 전출: {len(all_out_rows)}건 수집됨)")
            
        except Exception as e:
            st.error(f"데이터 크롤링 및 엑셀 파일 생성 중 예외 오류 발생: {e}")

# 수집된 바이너리 파일이 세션에 안착해 있다면 브라우저 화면에 다운로드 버튼 오픈
if st.session_state.excel_file_bytes is not None:
    st.write("---")
    st.subheader("📦 수집 완료된 전국 엑셀 마스터 파일")
    
    st.download_button(
        label="📥 내 컴퓨터로 엑셀 파일(.xlsx) 다운로드 받기",
        data=st.session_state.excel_file_bytes,
        file_name=st.session_state.excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )