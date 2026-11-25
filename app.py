import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup


# 웹페이지 HTML을 가져오는 함수
def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Educational Python Scraping Practice; Student Assignment)"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


# HTML에서 '관객수'와 '감독'이 포함된 wikitable 표를 찾는 함수
def find_ranking_table(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="wikitable")
    for table in tables:
        first_row = table.find("tr")
        if first_row:
            header_text = first_row.get_text(" ", strip=True)
            if "관객수" in header_text and "감독" in header_text:
                return table
    return None


# 찾은 표의 각주(sup)를 제거하고 DataFrame으로 변환하는 함수
def table_to_dataframe(table):
    for sup in table.find_all("sup"):
        sup.decompose()

    rows = table.find_all("tr")
    headers = [cell.get_text(strip=True) for cell in rows[0].find_all(["th", "td"])]

    data = []
    for tr in rows[1:]:
        cells = [cell.get_text(strip=True) for cell in tr.find_all(["th", "td"])]
        if len(cells) == len(headers):
            data.append(cells)

    return pd.DataFrame(data, columns=headers)


# 문자열에서 숫자만 추출해 정수로 바꾸는 함수
def to_number(text):
    digits = re.sub(r"[^0-9]", "", str(text))
    return int(digits) if digits else 0


# 수집한 표의 제목, 관객수, 개봉일을 분석 가능하게 정제하는 함수
def clean_movie_data(df):
    cleaned = df.copy()

    # 제목 열 찾아서 겹화살괄호(《》) 제거
    title_cols = [c for c in cleaned.columns if "제목" in c or "작품" in c]
    if title_cols:
        title_col = title_cols[0]
        cleaned[title_col] = cleaned[title_col].str.replace("《", "", regex=False).str.replace("》", "", regex=False).str.strip()
        cleaned = cleaned.rename(columns={title_col: "제목"})

    # 관객수 열 찾아서 정수형으로 변환
    audience_cols = [c for c in cleaned.columns if "관객" in c]
    if audience_cols:
        aud_col = audience_cols[0]
        cleaned["관객수"] = cleaned[aud_col].apply(to_number)
        if aud_col != "관객수":
            cleaned = cleaned.drop(columns=[aud_col])

    # 개봉일 열 찾아서 개봉연도, 개봉월 추출
    date_cols = [c for c in cleaned.columns if "개봉" in c]
    if date_cols:
        date_col = date_cols[0]
        cleaned["개봉연도"] = cleaned[date_col].str.extract(r"(\d{4})")
        cleaned["개봉월"] = cleaned[date_col].str.extract(r"\d{4}[-./년\s]+(\d{1,2})")
        cleaned["개봉월"] = pd.to_numeric(cleaned["개봉월"], errors="coerce").fillna(0).astype(int)

    # 관객수 1,000만 명 이상 데이터만 필터링 및 내림차순 정렬
    if "관객수" in cleaned.columns:
        cleaned = cleaned[cleaned["관객수"] >= 10000000].sort_values(by="관객수", ascending=False).reset_index(drop=True)
        cleaned["순위"] = cleaned.index + 1

    return cleaned


# 화면 구성을 실행하는 메인 함수
def main():
    st.set_page_config(page_title="천만관객 영화 분석", layout="wide")
    st.title("위키백과 천만관객 한국 영화 분석")

    default_url = "https://ko.wikipedia.org/wiki/%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD%EC%9D%98_%EC%98%81%ED%99%94_%ED%9D%A5%ED%96%89_%EA%B8%B0%EB%A1%9D"
    url = st.text_input("위키백과 주소를 입력하세요", value=default_url)

    if st.button("데이터 수집 및 분석 시작"):
        try:
            with st.spinner("위키백과에서 데이터를 가져오는 중입니다..."):
                html = fetch_html(url)
                table = find_ranking_table(html)

                if table is None:
                    st.error("페이지에서 '관객수'와 '감독' 항목이 포함된 흥행 순위 표를 찾지 못했습니다.")
                    return

                raw_df = table_to_dataframe(table)
                df = clean_movie_data(raw_df)

                if df.empty:
                    st.warning("수집된 천만 관객 영화 데이터가 없습니다.")
                    return

            # 핵심 지표 3가지 표시
            col1, col2, col3 = st.columns(3)
            col1.metric("천만 영화 수", f"{len(df)}편")
            col2.metric("역대 1위 영화", df.loc[0, "제목"])
            col3.metric("1위 관객수", f"{df.loc[0, '관객수']:,}명")

            st.subheader("천만 관객 영화 목록")
            st.dataframe(df, use_container_width=True)

            # 차트 1: 관객수 상위 10편 가로 막대 차트
            st.subheader("관객수 상위 10편")
            top10 = df.head(10).set_index("제목")["관객수"]
            st.bar_chart(top10, horizontal=True)

            # 차트 2: 개봉 연도별 편수 막대 차트
            if "개봉연도" in df.columns:
                st.subheader("개봉 연도별 천만 영화 편수")
                year_counts = df["개봉연도"].dropna().value_counts().sort_index()
                st.bar_chart(year_counts)

        except requests.exceptions.Timeout:
            st.error("요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")
        except requests.exceptions.ConnectionError:
            st.error("네트워크 연결에 실패했습니다. 인터넷 연결과 주소를 확인해 주세요.")
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP 오류가 발생했습니다: {e}")
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()