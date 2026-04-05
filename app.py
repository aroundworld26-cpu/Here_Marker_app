import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation
import ssl

# --- 0. 환경 설정 ---
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
        # SSL 검증 무시 설정
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
        
    st.divider()
    st.caption("카카오 API 및 구글 시트 실시간 연동 중")

SELECTED_SHEET_URL = sheet_dict[st.session_state.current_team]

# --- 4. 메인 화면 구성 ---

st.title(f"📍 Here Marker - {st.session_state.current_team}")

# GPS 위치 확인
location = streamlit_geolocation()
if location['latitude'] and location['longitude']:
    my_lat, my_lng = location['latitude'], location['longitude']
else:
    my_lat, my_lng = 36.3504, 127.3845 # 기본 대전 좌표

# 데이터 로드 및 좌표 변환
df = load_data_from_gsheet(SELECTED_SHEET_URL)

if df is not None and '주소' in df.columns:
    with st.spinner(f"'{st.session_state.current_team}' 좌표 변환 중..."):
        # 좌표 변환 수행
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        
        # 통계 계산
        total_count = len(df)
        marked_df = df.dropna(subset=['위도', '경도'])
        marked_count = len(marked_df)
        unmarked_count = total_count - marked_count

    # --- 현황 요약 표시 (Metrics) ---
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 업체 수", f"{total_count}개")
    col2.metric("마커 표시됨", f"{marked_count}개", delta_color="normal")
    col3.metric("표시 안 됨(주소 오류)", f"{unmarked_count}개", delta=f"-{unmarked_count}" if unmarked_count > 0 else None, delta_color="inverse")

    if unmarked_count > 0:
        st.warning(f"⚠️ 주소가 불분명하여 표시되지 않은 업체가 {unmarked_count}개 있습니다. 시트의 주소를 확인해 주세요.")

    # 지도 생성
    m = folium.Map(location=[my_lat, my_lng], zoom_start=14)

    # 내 위치 마커
    folium.Marker(
        [my_lat, my_lng],
        popup="내 위치",
        icon=folium.Icon(color='blue', icon='star')
    ).add_to(m)

    # 업체 마커 표시
    for _, row in marked_df.iterrows():
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}<br>{row.get('전화번호', '')}", max_width=300),
            tooltip=folium.Tooltip(row['업체명'], permanent=True),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=600)

    # --- 팀 데이터 원본 (선택 시 보여주기) ---
    st.divider()
    with st.expander(f"🔍 {st.session_state.current_team} 상세 데이터 원본 보기"):
        st.write("표시 안 된 업체는 아래 표에서 위도/경도가 NaN으로 나타납니다.")
        st.dataframe(df, use_container_width=True)

else:
    st.error("데이터를 불러오지 못했거나 '주소' 컬럼이 없습니다.")