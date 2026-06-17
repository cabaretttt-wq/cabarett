import streamlit as st
import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import io

# =============================================
# 기본 설정 및 함수 (기존 스크립트 기능 유지)
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
        time.sleep(0.1) # 웹 앱 환경이므로 조금 더 빠르게 조절
        html = fetch_page(mvin_dong, mvt_dong, fr_ym, to_ym, page=page)
        if not html:
            break
        _, rows = parse_rows(html)
        all_rows.extend(rows)
        
        # 웹 UI에 실시간 진행 상황 업데이트
        status_text.text(f"진행 중... ({page}/{total_pages} 페이지 수집 완료)")
        progress_bar.progress(page / total_pages)

    return all_rows

# =============================================
# Streamlit 웹 UI 구성
# =============================================
st.set_page_config(page_title="인구이동 데이터 수집기", layout="centered")

st.title("📊 지역별 인구이동 원본 데이터 수집기")
st.caption("출처: 행정안전부 지역별 인구이동 현황 (rdoa.jumin.go.kr)")

st.markdown("---")

# 사용자 입력 칸 생성
col1, col2, col3 = st.columns(3)
with col1:
    target_year = st.selectbox("조회 년도", ["2026", "2025", "2024", "2023"], index=1)
with col2:
    area_name = st.text_input("지역 이름 (파일명용)", value="조치원읍")
with col3:
    target_dong_code = st.text_input("행정동 코드 (10자리)", value="3611025000")

st.info("💡 **Tip:** 행정동 코드는 해당 사이트에서 조회하려는 동의 10자리 고유 코드를 입력해야 정확히 작동합니다.")

# 수집 시작 버튼
if st.button("🚀 데이터 수집 시작", use_container_width=True):
    
    # 4분기 설정
    periods = [
        (f"{target_year}01", f"{target_year}03", "1분기"),
        (f"{target_year}04", f"{target_year}06", "2분기"),
        (f"{target_year}07", f"{target_year}09", "3분기"),
        (f"{target_year}10", f"{target_year}12", "4분기"),
    ]
    
    all_in_rows = []
    all_out_rows = []
    
    # 웹 화면에 진행바 표시용 플레이스홀더
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
        
        # 데이터프레임 변환
        df_in = pd.DataFrame(all_in_rows)
        df_out = pd.DataFrame(all_out_rows)
        
        # 결과를 화면에 맛보기로 보여주기
        st.success(f"🎉 수집 성공! (전입: {len(df_in):,}행 / 전출: {len(df_out):,}행)")
        
        # 엑셀 파일을 파일 형태로 서버 메모리에 저장 (BytesIO 활용)
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_in.to_excel(writer, index=False, sheet_name="전입_원본")
            df_out.to_excel(writer, index=False, sheet_name="전출_원본")
            
            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col) + 4
                    ws.column_dimensions[col[0].column_letter].width = max_len
        
        # 다운로드 버튼 활성화
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=excel_buffer.getvalue(),
            file_name=f"{area_name}_{target_year}년_전입전출_원본데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"❌ 에러가 발생했습니다: {e}")