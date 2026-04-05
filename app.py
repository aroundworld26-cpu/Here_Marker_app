import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation
import ssl

# --- 0. 환경 설정 (맥 SSL 에러 방지 및 페이지 설정) ---
ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="Here Marker", layout="wide")

# --- 1. 보안 설정 (Secrets 활용) ---
try:
    KAKAO_REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]
    sheet_dict = st.secrets["sheets"]
except KeyError:
    st.error("⚠️ Streamlit Secrets 설정(API 키, 시트 목록)을 확인해 주세요.")
    st.stop()

# --- 2. 핵심 함수 정의 ---

# 카카오 API 주소 -> 좌표 변환 (캐싱 적용)
@st.cache_data
def get_coordinates_kakao(address):
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    try:
        response = requests.get(url, headers=headers, verify=False)
        result = response.json()
        if result.get('documents'):
            lng = float(result['documents'][0]['x'])
            lat = float(result['documents'][0]['y'])
            return lat, lng
    except:
        return None, None
    return None, None

# 구글 시트 데이터 로드 함수 (한글 깨짐 방지 및 SSL 우회)
@st.cache_data(ttl=600)
def load_data_from_gsheet(url):
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8' 
        df = pd.read_csv(io.StringIO(response.text))
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다: {e}")
        return None

# --- 3. 사이드바 UI 구성 ---

with st.sidebar:
    st.title("📂 제어판")
    team_options = list(sheet_dict.keys())
    selected_team = st.selectbox("팀 리스트 선택", options=team_options)
    st.session_state.current_team = selected_team
    
    st.divider()
    
    if st.button("🔄 데이터 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. 메인 화면 구성 ---

st.title(f"📍 Here Marker - {st.session_state.current_team}")

# GPS 위치 확인
location = streamlit_geolocation()
my_lat, my_lng = (location['latitude'], location['longitude']) if location['latitude'] else (36.3504, 127.3845)

# 데이터 로드 및 처리
df = load_data_from_gsheet(sheet_dict[st.session_state.current_team])

if df is not None and '주소' in df.columns:
    with st.spinner("데이터 분석 중..."):
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        marked_df = df.dropna(subset=['위도', '경도'])
        
        total_count = len(df)
        marked_count = len(marked_df)
        unmarked_count = total_count - marked_count

    # --- 요청하신 요약 표 표시 ---
    st.markdown("#### 📊 업체 표시 현황")
    
    summary_data = {
        "전체 업체": [f"{total_count}개"],
        "표시 업체": [f"{marked_count}개"],
        "미표시 업체": [f"{unmarked_count}개"]
    }
    st.table(pd.DataFrame(summary_data))

    if unmarked_count > 0:
        st.warning(f"⚠️ 주소 오류 등으로 표시되지 않은 업체가 {unmarked_count}개 있습니다.")

    st.divider()

    # --- 5. 지도 생성 및 출력 ---
    m = folium.Map(location=[my_lat, my_lng], zoom_start=14)

    # 내 위치 마커
    folium.Marker([my_lat, my_lng], popup="내 위치", icon=folium.Icon(color='blue', icon='star')).add_to(m)

    # 업체 마커
    for _, row in marked_df.iterrows():
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}", max_width=300),
            tooltip=folium.Tooltip(row['업체명'], permanent=True),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    st_folium(m, width="100%", height=600)

    # --- 6. 상세 데이터 원본 (Expander) ---
    with st.expander("🔍 상세 데이터 원본 보기"):
        st.dataframe(df, use_container_width=True)

else:
    st.error("데이터를 불러오지 못했거나 '주소' 컬럼이 없습니다.")
