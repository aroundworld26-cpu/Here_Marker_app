import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster  # 클러스터 라이브러리 추가
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

# --- 3. 사이드바 ---
with st.sidebar:
    st.title("📂 제어판")
    selected_team = st.selectbox("팀 리스트 선택", options=list(sheet_dict.keys()))
    st.session_state.current_team = selected_team
    
    if st.button("🔄 데이터 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. 메인 화면 ---
# st.title(f"📍 Here Marker - {st.session_state.current_team}")
st.markdown(f"### 📍 Here Marker - {st.session_state.current_team}")
location = streamlit_geolocation()
my_lat, my_lng = (location['latitude'], location['longitude']) if location['latitude'] else (36.3504, 127.3845)

df = load_data_from_gsheet(sheet_dict[st.session_state.current_team])

if df is not None and '주소' in df.columns:
    with st.spinner("마커 준비 중..."):
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        marked_df = df.dropna(subset=['위도', '경도'])
        
        total_count, marked_count = len(df), len(marked_df)
        unmarked_count = total_count - marked_count

    # 요약 표
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
    m = folium.Map(location=[my_lat, my_lng], zoom_start=14)

    # 내 위치 마커 (클러스터에 포함하지 않음)
    folium.Marker([my_lat, my_lng], popup="내 위치", icon=folium.Icon(color='blue', icon='star')).add_to(m)

    # ★ 마커 클러스터 생성 ★
    marker_cluster = MarkerCluster().add_to(m)

    # 업체 마커를 클러스터에 추가
    for _, row in marked_df.iterrows():
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}", max_width=300),
            tooltip=folium.Tooltip(row['업체명'], permanent=True),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(marker_cluster) # m이 아닌 marker_cluster에 추가

    st_folium(m, width="100%", height=600)

    with st.expander("🔍 상세 데이터 원본 보기"):
        st.dataframe(df, use_container_width=True)
else:
    st.error("데이터를 불러올 수 없습니다.")