import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation
import ssl
from folium import LayerControl, Map
from branca.element import MacroElement
from jinja2 import Template

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

# --- 커스텀 컨트롤 위치 클래스 ---
class CustomZoomPosition(MacroElement):
    """
    Move the zoom-control to the top-right (default is top-left).
    """
    def __init__(self, position='topright'):
        super().__init__()
        self._template = Template(u"""
            {% macro script(this, kwargs) %}
                {{this._parent.get_name()}}.zoomControl.setPosition('{{ this.position }}');
            {% endmacro %}
        """)
        self.position = position

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
    
    # --- [추가된 기능] 업체 검색 및 초기화 ---
    st.subheader("🔍 업체 검색")
    
    # 세션 상태(Session State) 초기화
    if "search_word" not in st.session_state:
        st.session_state["search_word"] = ""

    # 검색어 지우기 버튼을 눌렀을 때 실행될 함수
    def clear_search():
        st.session_state["search_word"] = ""

    # text_input에 key를 부여하여 세션 상태와 연결
    search_query = st.text_input("업체명을 입력하세요", placeholder="예: 대전시청", key="search_word")
    
    # 검색창 바로 밑에 초기화 버튼 배치 (클릭 시 clear_search 함수 실행)
    st.button(" ⏪ 검색어 지우기 (초기 화면)", on_click=clear_search, use_container_width=True)

# --- 4. 메인 화면 ---
st.markdown(f"## 📍 Here Marker - {st.session_state.current_team}")
location = streamlit_geolocation()
# 위치 정보가 없을 경우 대전시청 좌표를 기본값으로 사용
my_lat, my_lng = (location['latitude'], location['longitude']) if location['latitude'] else (36.3504, 127.3845)

df = load_data_from_gsheet(sheet_dict[st.session_state.current_team])

if df is not None and '주소' in df.columns:
    with st.spinner("데이터 분석 및 마커 준비 중..."):
        # 1. 위도/경도 변환 (캐싱 적용)
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        
        # 좌표가 정상적으로 변환된 데이터만 추출
        valid_coords_df = df.dropna(subset=['위도', '경도'])
        marked_df = valid_coords_df.copy()
        
        # 2. 지역구 필터링 적용
        if selected_gus:
            # 선택된 구가 주소에 포함된 행만 필터링
            marked_df = marked_df[marked_df['주소'].str.contains('|'.join(selected_gus), na=False)]
        else:
            # 아무 구도 선택하지 않으면 빈 데이터 반환
            marked_df = marked_df.iloc[0:0] 

        # 3. 검색어 필터링 적용 및 지도 중심 이동 처리
        search_result = None
        if search_query:
            search_result = marked_df[marked_df['업체명'].str.contains(search_query, case=False, na=False)]
            if not search_result.empty:
                st.success(f"선택한 지역 내 '{search_query}' 검색 결과: {len(search_result)}건")
                # 검색 결과의 첫 번째 업체 위치로 지도 중심 이동
                my_lat = search_result.iloc[0]['위도']
                my_lng = search_result.iloc[0]['경도']
            else:
                st.warning("현재 선택된 지역구 내에는 해당 업체를 찾을 수 없습니다.")
        
        # 현황 계산
        total_count = len(df) # 전체 원본 데이터 수
        valid_count = len(valid_coords_df) # 주소 변환 성공 수
        filtered_count = len(marked_df) # 필터링되어 지도에 표시될 수
        error_count = total_count - valid_count # 주소 오류 등으로 좌표 변환 실패 수

    # --- 5. 화면 출력 (요약 표) ---
    st.markdown(f"#### 📊 업체 표시 현황")
    summary_data = {
        "전체 등록 업체": [f"{total_count}개"],
        "현재 지도 표시": [f"{filtered_count}개"],
        "주소 변환 실패": [f"{error_count}개"]
    }
    st.table(pd.DataFrame(summary_data))

    st.divider()
    
    # --- 6. 지도 렌더링 ---
    # 검색 결과가 있으면 지도를 확대(zoom 16), 없으면 기본 배율(zoom 13)
    zoom_level = 16 if search_query and search_result is not None and not search_result.empty else 13
    m = folium.Map(location=[my_lat, my_lng], zoom_start=zoom_level)

    # [추가] 확대/축소 컨트롤을 우측 상단으로 옮기는 커스텀 요소를 지도에 추가
    m.add_child(CustomZoomPosition(position='topright'))

    # 내 위치 마커 (파란색 별)
    folium.Marker([location['latitude'] if location['latitude'] else 36.3504, 
                   location['longitude'] if location['longitude'] else 127.3845], 
                  popup="내 위치", icon=folium.Icon(color='blue', icon='star')).add_to(m)

    # 마커 클러스터 생성
    marker_cluster = MarkerCluster().add_to(m)

    # 필터링 및 검색이 완료된 마커 추가
    for _, row in marked_df.iterrows():
        # 검색된 대상인지 확인하여 아이콘 색상 및 툴팁 가시성 변경
        is_search_target = search_query and search_query.lower() in str(row['업체명']).lower()
        icon_color = 'orange' if is_search_target else 'red'
        
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}", max_width=300),
            tooltip=folium.Tooltip(row['업체명'], permanent=bool(is_search_target)),
            icon=folium.Icon(color=icon_color, icon='info-sign')
        ).add_to(marker_cluster)

    # Streamlit 화면에 지도 출력
    st_folium(m, width="100%", height=600)

    # 원본 데이터 확인용 아코디언 메뉴
    with st.expander("🔍 상세 데이터 원본 보기"):
        st.dataframe(df, use_container_width=True)
else:
    st.error("데이터를 불러올 수 없거나 시트에 '주소' 컬럼이 존재하지 않습니다.")