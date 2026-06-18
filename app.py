import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="전국 전입전출 데이터 추출기 PRO", layout="wide")

st.title("📊 전국 전입·전출 데이터 수집 자동화 시스템")
st.caption("텍스트 파일 제로! 행정안전부 서버 실시간 지역 매칭 및 크롤링 버전")

# =============================================
# 1. [혁신] 인터넷 실시간 행정동 코드 조회 기능 (API/txt 파일 불필요)
# =============================================
@st.cache_data(ttl=3600)  # 1시간 동안 메모리 유지로 속도 최적화
def fetch_realtime_administrative_dongs(keyword):
    """
    사용자가 입력한 검색어를 가지고 행정안전부 주민등록 인구통계 서버에서
    실제 사용 중인 정식 행정동 이름과 10자리 행정동 코드를 실시간으로 긁어옵니다.
    """
    if not keyword or len(keyword.strip()) < 2:
        return {}
        
    url = "https://stat.moi.go.kr/WMO/stat/statMain.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 행안부 내부 지역 검색용 파라미터 규격
    payload = {
        "searchType": "month",
        "searchGubun": "100",
        "dongCode": "",
        "searchDongNm": keyword.strip()
    }
    
    dong_map = {}
    try:
        res = requests.post(url, data=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            # 행안부 행정구역 선택 select 박스 내의 옵션값 파싱
            options = soup.select("#admDongList option")
            for opt in options:
                code = opt.get("value", "").strip()
                name = opt.get_text(strip=True)
                if code and name and "선택" not in name:
                    dong_map[name] = code
    except Exception:
        pass
    return dong_map

# =============================================
# 2. 행정안전부 실제 데이터 수집 크롤링 엔진
# =============================================
def fetch_all_rows(api_code, target_dong_code, fr_ym, to_ym, progress_bar, status_text):
    """
    행정안전부 주민등록 인구통계 시스템 서버에서
    선택한 기간의 전입/전출 테이블 데이터를 파싱하는 핵심 기동 함수입니다.
    """
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

    # 한 달씩 돌면서 실제 행안부 시스템 데이터 수집
    for dt in date_range:
        current_ym = dt.strftime('%Y%m')
        
        payload = {
            "searchType": "month",
            "searchGubun": api_code,       # 전입(100) / 전출(200) 코드
            "dongCode": target_dong_code,  # 인터넷망에서 직송받은 10자리 행정동 코드
            "startInYm": current_ym,
            "endInYm": current_ym
        }
        
        try:
            res = requests.post(url, data=payload, headers=headers, timeout=15)
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
        except Exception:
            pass
            
    return rows

# =============================================
# 3. 메인 인터페이스 및 검색 UI (실시간 매칭)
# =============================================
col1, col2 = st.columns(2)
with col1:
    search_query = st.text_input("🔍 검색할 전국 행정구역/읍면동 입력 (예: 사당동, 정자1동, 세종)", value="사당동")
with col2:
    target_ym = st.text_input("📅 조회 기간 (예: 202301-202312)", value="202301-202312")

# 사용자가 타이핑하면 즉시 인터넷망에서 유효한 행정동 코드를 실시간 조회
matched_dongs = {}
if search_query and len(search_query.strip()) >= 2:
    with st.spinner("🌐 행정안전부 서버에서 실시간 지역 코드를 동기화하는 중..."):
        matched_dongs = fetch_realtime_administrative_dongs(search_query)

if matched_dongs:
    selected_dong_name = st.selectbox("📌 행안부 서버에 등록된 공식 행정동 선택", list(matched_dongs.keys()))
    selected_code = matched_dongs[selected_dong_name]
    
    # 인터넷망에서 가져온 검증된 원본 행정동 코드 그대로 바인딩
    target_dong_code = selected_code
    st.success(f"🔗 행안부 서버 실시간 동기화 성공! 코드: `{target_dong_code}`")
else:
    if search_query:
        st.error("❌ 현재 행정안전부 인구통계 시스템상에 존재하지 않거나 검색어가 너무 짧습니다. 정확한 명칭을 입력해 주세요.")

# 브라우저 다운로드 세션 상태 유지 안전장치
if "excel_file_bytes" not in st.session_state:
    st.session_state.excel_file_bytes = None
if "excel_filename" not in st.session_state:
    st.session_state.excel_filename = ""

# =============================================
# 4. 데이터 수집 프로세스 구동 및 엑셀 마스터 시트 생성
# =============================================
if st.button("🚀 전국 데이터 일괄 수집 시작", type="primary"):
    if not matched_dongs:
        st.warning("유효하게 조회된 행정동 코드가 없습니다.")
    else:
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        try:
            fr_ym, to_ym = target_ym.split('-')
            
            # 행안부 고유 통신 신호
            IN_CODE = "100"
            OUT_CODE = "200"
            
            all_in_rows = []
            all_out_rows = []
            
            # 1. 실시간 매칭된 코드로 전입 데이터 크롤링
            status_text.text(f"🔄 [{selected_dong_name}] 행안부 전입 데이터 수집 중...")
            in_res = fetch_all_rows(IN_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if in_res: all_in_rows.extend(in_res)
            progress_bar.progress(0.4)
            time.sleep(0.1)
            
            # 2. 실시간 매칭된 코드로 전출 데이터 크롤링
            status_text.text(f"🔄 [{selected_dong_name}] 행안부 전출 데이터 수집 중...")
            out_res = fetch_all_rows(OUT_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            if out_res: all_out_rows.extend(out_res)
            progress_bar.progress(0.8)
            time.sleep(0.1)
            
            status_text.text("✨ 수집 완료! 다운로드용 통합 엑셀 문서 빌드 중...")
            
            df_in = pd.DataFrame(all_in_rows)
            df_out = pd.DataFrame(all_out_rows)
            
            if df_in.empty:
                df_in = pd.DataFrame([{"결과": "조회 기간 내 행안부 전입 통계 데이터가 존재하지 않습니다."}])
            if df_out.empty:
                df_out = pd.DataFrame([{"결과": "조회 기간 내 행안부 전출 통계 데이터가 존재하지 않습니다."}])
            
            # 💾 가상 버퍼 상에 엑셀 멀티 시트 마스터 저장
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
            st.success(f"🎉 데이터 추출이 완벽히 완료되었습니다! (전입: {len(all_in_rows):,}행 / 전출: {len(all_out_rows):,}행)")
            
        except Exception as e:
            st.error(f"실시간 크롤링 기동 중 시스템 예외 발생: {e}")

# 다운로드 최종 활성화 버튼 영역
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