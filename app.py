import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io

# =============================================
# [NEW] 전국의 행정동 명칭과 코드를 검색하는 함수
# 행정안전부 주민등록 인구통계 페이지의 코드 검색 로직 활용
# =============================================
def search_dong_code(keyword):
    """사용자가 입력한 동 이름으로 10자리 행정동 코드를 찾아오는 함수"""
    if not keyword.strip():
        return []
        
    url = "https://rdoa.jumin.go.kr/openStats/selectConeTermList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://rdoa.jumin.go.kr/openStats/selectConPpltnData"
    }
    
    # 행정안전부 서버에 해당 동 이름 검색 요청
    params = {"searchWord": keyword}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json() # JSON 형태로 결과 반환받음
            # 데이터 구조 예시: [{'admmCd': '3611025000', 'admmNm': '세종특별자치시  조치원읍'}, ...]
            return data
    except Exception as e:
        st.error(f"⚠️ 행정동 코드 검색 중 오류 발생: {e}")
    return []

# =============================================
# 크롤링 기본 설정 및 함수 (기존 기능 유지)
# =============================================
BASE_URL = "https://rdoa.jumin.go.kr/openStats/selectConPpltnData"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer":    "https://rdoa.jumin.go.kr/openStats/selectConPpltnData",
}
ALL_CODE = "1000000000"

def fetch_page(mvin_dong, mvt_dong, fr_ym, to_ym, page=1):
    param_url = f"mvinAdmmCd={mvin_dong}&mvtAdmmCd={mvt_dong}&lv=3&srchFrYm={fr_ym}&srchToYm={to_ym}"
    params = {"curPage": str(page), "paramUrl": param_url}
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return None

def parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    total_count = 0
    total_tag = soup.select_one("p.total b")
    if total_tag:
        try:
            total_count = int(total_tag.text.replace(",", "").strip())
        except ValueError:
            pass

    rows_data = []
    rows = soup.select("div.bbs_list table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if len(tds) >= 12:
            try:
                rows_data.append({
                    "통계년월":       tds[0].text.strip(),
                    "전입행정기관코드": tds[1].text.strip(),
                    "전출행정기관코드": tds[2].text.strip(),
                    "전입시도":       tds[3].text.strip(),
                    "전입시군구":     tds[4].text.strip(),
                    "전입행정동":     tds[5].text.strip(),
                    "전출시도":       tds[6].text.strip(),
                    "전출시군구":     tds[7].text.strip(),
                    "전출행정동":     tds[8].text.strip(),
                    "총인구수":       int(tds[9].text.strip().replace(",", "")),
                    "남자인구수":     int(tds[10].text.strip().replace(",", "")),
                    "여자인구수":     int(tds[11].text.strip().replace(",", "")),
                })
            except (ValueError, IndexError):
                pass
    return total_count, rows_data

def fetch_all_rows(mvin_dong, mvt_dong, fr_ym, to_ym, progress_bar, status_text):
    all_rows = []
    html = fetch_page(mvin_dong, mvt_dong, fr_ym, to_ym, page=1)
    if not html:
        return []

    total_count, rows = parse_rows(html)
    all_rows.extend(rows)
    total_pages = (total_count + 9) // 10 if total_count > 0 else 1

    for page in range(2, total_pages + 1):
        time.sleep(0.1)
        html = fetch_page(mvin_dong, mvt_dong, fr_ym, to_ym, page=page)
        if not html:
            break
        _, rows = parse_rows(html)
        all_rows.extend(rows)
        
        status_text.text(f"진행 중... ({page}/{total_pages} 페이지 수집 완료)")
        progress_bar.progress(page / total_pages)

    return all_rows

# =============================================
# Streamlit 웹 UI 구성
# =============================================
st.set_page_config(page_title="인구이동 데이터 수집기 v10", layout="centered")

st.title("📊 지역별 인구이동 원본 데이터 수집기")
st.caption("출처: 행정안전부 지역별 인구이동 현황 (rdoa.jumin.go.kr)")

st.markdown("---")

# 1. 연도 선택 및 행정동 이름 검색 창
col1, col2 = st.columns([1, 2])
with col1:
    target_year = st.selectbox("조회 년도", ["2026", "2025", "2024", "2023"], index=1)
with col2:
    search_keyword = st.text_input("행정동 이름 검색 (예: 조치원읍, 정자1동, 사당동)", value="조치원읍")

# 2. 이름 기반으로 코드 자동 검색 및 선택창 제공
target_dong_code = None
target_dong_name = ""

if search_keyword:
    results = search_dong_code(search_keyword)
    
    if results:
        # 사용자가 알아보기 쉽게 "시도 시군구 동이름 (코드)" 형태로 목록 제작
        options = [f"{r['admmNm']} ({r['admmCd']})" for r in results]
        selected_option = st.selectbox("🎯 검색된 지역 선택", options)
        
        # 선택된 항목에서 코드와 실제 지역명 추출
        selected_index = options.index(selected_option)
        target_dong_code = results[selected_index]['admmCd']
        # 전체 주소에서 마지막 단어(읍/면/동 이름)만 추출해서 파일명에 활용
        target_dong_name = results[selected_index]['admmNm'].split()[-1]
        
        st.success(f"✅ 선택된 지역 코드: `{target_dong_code}` ({target_dong_name})")
    else:
        st.warning("🔍 검색 결과가 없습니다. 행정동 이름을 정확하게 입력해 주세요. (예: 조치원 (X) -> 조치원읍 (O))")

st.markdown("---")

# 수집 시작 버튼 (코드가 정상적으로 찾아졌을 때만 활성화)
if target_dong_code and st.button("🚀 데이터 수집 시작", use_container_width=True):
    
    periods = [
        (f"{target_year}01", f"{target_year}03", "1분기"),
        (f"{target_year}04", f"{target_year}06", "2분기"),
        (f"{target_year}07", f"{target_year}09", "3분기"),
        (f"{target_year}10", f"{target_year}12", "4분기"),
    ]
    
    all_in_rows = []
    all_out_rows = []
    
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    
    try:
        for fr_ym, to_ym, q_label in periods:
            # 1. 전입 데이터 수집
            status_text.text(f"🔄 [{q_label}] 전입 데이터 수집 중...")
            in_rows = fetch_all_rows(target_dong_code, ALL_CODE, fr_ym, to_ym, progress_bar, status_text)
            all_in_rows.extend(in_rows)
            time.sleep(0.3)
            
            # 2. 전출 데이터 수집
            status_text.text(f"🔄 [{q_label}] 전출 데이터 수집 중...")
            out_rows = fetch_all_rows(ALL_CODE, target_dong_code, fr_ym, to_ym, progress_bar, status_text)
            all_out_rows.extend(out_rows)
            time.sleep(0.3)
            
        status_text.text("✨ 수집 완료! 데이터 변환 중...")
        progress_bar.progress(1.0)
        
        df_in = pd.DataFrame(all_in_rows)
        df_out = pd.DataFrame(all_out_rows)
        
        st.success(f"🎉 수집 성공! (전입: {len(df_in):,}행 / 전출: {len(df_out):,}행)")
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_in.to_excel(writer, index=False, sheet_name="전입_원본")
            df_out.to_excel(writer, index=False, sheet_name="전출_원본")
            
            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col) + 4
                    ws.column_dimensions[col[0].column_letter].width = max_len
        
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=excel_buffer.getvalue(),
            file_name=f"{target_dong_name}_{target_year}년_전입전출_원본데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ 에러가 발생했습니다: {e}")