import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation
import ssl

# --- 0. 환경 설정 ---
ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="Here Marker", layout="wide")

# --- 1. 보안 설정 ---
try:
    KAKAO_REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]
    sheet_dict = st.secrets["sheets"]
except KeyError:
    st.error("⚠️ Streamlit Secrets 설정을 확인해 주세요.")
    st.stop()

# --- 2. 핵심 함수 정의 ---
@st.cache_data
def get_coordinates_kakao(address):
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    try:
        response = requests.get(url, headers=headers, verify=False)
        result = response.json()
        if result.get('documents'):
            return float(result['documents'][0]['y']), float(result['documents'][0]['x'])
    except:
        return None, None
    return None, None

@st.cache_data(ttl=600)
def load_data_from_gsheet(url):
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8' 
        return pd.read_csv(io.StringIO(response.text))
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# --- 3. 사이드바 (제어판 및 필터) ---
with st.sidebar:
    st.title("📂 제어판")
    selected_team = st.selectbox("팀 리스트 선택", options=list(sheet_dict.keys()))
    st.session_state.current_team = selected_team
    
    if st.button("🔄 데이터 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    
    # 지역구 필터
    st.subheader("🏙️ 지역구 필터")
    gu_list = ["동구", "중구", "서구", "유성구", "대덕구"]
    selected_gus = st.multiselect("보고 싶은 구를 선택하세요", options=gu_list, default=gu_list)

    st.divider()
    
    # 업체 검색 및 초기화
    st.subheader("🔍 업체 검색")
    if "search_word" not in st.session_state:
        st.session_state["search_word"] = ""

    def clear_search():
        st.session_state["search_word"] = ""

    # text_input에 key를 부여하여 세션 상태와 연결
    search_query = st.text_input("업체명을 입력하세요", placeholder="예: 대전시청", key="search_word")
    
    # 검색창 바로 밑에 초기화 버튼 배치 (클릭 시 clear_search 함수 실행)
    st.button(" ⏪ 검색어 지우기 (초기 화면)", on_click=clear_search, use_container_width=True)

# --- 4. 메인 화면 ---
st.markdown(f"## 🏘️📍 Here Marker - {st.session_state.current_team}")
location = streamlit_geolocation()
my_lat, my_lng = (location['latitude'], location['longitude']) if location['latitude'] else (36.3504, 127.3845)

df = load_data_from_gsheet(sheet_dict[st.session_state.current_team])

if df is not None and '주소' in df.columns:
    with st.spinner("데이터 분석 및 마커 준비 중..."):
        
        # [핵심 로직] 시트에 위도/경도 열이 아예 없으면 일단 빈 칸으로 생성
        if '위도' not in df.columns:
            df['위도'] = None
        if '경도' not in df.columns:
            df['경도'] = None

        # 하이브리드 함수: 값이 있으면 쓰고, 없으면 카카오 API 호출
        def fetch_coords_if_missing(row):
            # 1. 시트에 값이 존재하는지 확인 (빈 칸이 아님을 검사)
            if pd.notna(row['위도']) and pd.notna(row['경도']) and str(row['위도']).strip() != "":
                try:
                    # 값이 있으면 문자열일 수 있으므로 소수점 숫자(float)로 변환하여 그대로 사용
                    return pd.Series([float(row['위도']), float(row['경도'])])
                except ValueError:
                    # 실수로 숫자가 아닌 글자가 입력되어 있으면 무시하고 API 호출로 넘어감
                    pass 
            
            # 2. 값이 비어있으면 카카오 API 호출
            return pd.Series(get_coordinates_kakao(str(row['주소'])))

        # 데이터프레임 전체에 하이브리드 방식 적용
        df[['위도', '경도']] = df.apply(fetch_coords_if_missing, axis=1)
        
        # 좌표가 정상적으로 채워진(변환된) 데이터만 추출
        valid_coords_df = df.dropna(subset=['위도', '경도'])
        marked_df = valid_coords_df.copy()
        
        # 지역구 필터링 적용
        if selected_gus:
            marked_df = marked_df[marked_df['주소'].str.contains('|'.join(selected_gus), na=False)]
        else:
            marked_df = marked_df.iloc[0:0] 

        # 검색어 필터링 적용 및 지도 중심 이동 처리
        search_result = None
        if search_query:
            search_result = marked_df[marked_df['업체명'].str.contains(search_query, case=False, na=False)]
            if not search_result.empty:
                st.success(f"선택한 지역 내 '{search_query}' 검색 결과: {len(search_result)}건")
                my_lat = search_result.iloc[0]['위도']
                my_lng = search_result.iloc[0]['경도']
            else:
                st.warning("현재 선택된 지역구 내에는 해당 업체를 찾을 수 없습니다.")
        
        # 현황 계산
        total_count = len(df)
        valid_count = len(valid_coords_df)
        filtered_count = len(marked_df)
        error_count = total_count - valid_count

    # --- 5. 화면 출력 (요약 표) ---
    st.markdown(f"#### 🗂 업체 표시 현황")
    summary_data = {
        "전체 등록 업체": [f"{total_count}개"],
        "현재 지도 표시": [f"{filtered_count}개"],
        "주소 변환 실패": [f"{error_count}개"]
    }
    st.table(pd.DataFrame(summary_data))

    st.divider()
    
    # --- 6. 지도 렌더링 ---
    zoom_level = 16 if search_query and search_result is not None and not search_result.empty else 13
    m = folium.Map(location=[my_lat, my_lng], zoom_start=zoom_level)

    folium.Marker([location['latitude'] if location['latitude'] else 36.3504, 
                   location['longitude'] if location['longitude'] else 127.3845], 
                  popup="내 위치", icon=folium.Icon(color='blue', icon='star')).add_to(m)

    marker_cluster = MarkerCluster().add_to(m)

    for _, row in marked_df.iterrows():
        is_search_target = search_query and search_query.lower() in str(row['업체명']).lower()
        icon_color = 'orange' if is_search_target else 'red'
        
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}", max_width=300),
            tooltip=folium.Tooltip(row['업체명'], permanent=bool(is_search_target)),
            icon=folium.Icon(color=icon_color, icon='info-sign')
        ).add_to(marker_cluster)

    st_folium(m, width="100%", height=600, returned_objects=[])
    
    with st.expander("🔍 상세 데이터 원본 보기"):
        st.dataframe(df, use_container_width=True)
else:
    st.error("데이터를 불러올 수 없거나 시트에 '주소' 컬럼이 존재하지 않습니다.")