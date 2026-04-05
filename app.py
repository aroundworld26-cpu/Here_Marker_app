import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation

# 페이지 설정
st.set_page_config(page_title="Here Marker", layout="wide")

# --- 1. 보안 설정 (API 키 및 시트 URL) ---
try:
    KAKAO_REST_API_KEY = st.secrets["KAKAO_REST_API_KEY"]
    # 구글 시트 주소도 secrets에 저장해두면 관리가 편합니다.
    SHEET_URL = st.secrets["GOOGLE_SHEET_URL"] 
except KeyError:
    st.error("⚠️ Streamlit Secrets 설정에서 API 키와 시트 URL을 확인해 주세요.")
    st.stop()

# --- 2. 핵심 함수 정의 ---

# 카카오 API 주소 -> 좌표 변환 (캐싱 적용)
@st.cache_data
def get_coordinates_kakao(address):
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        result = response.json()
        if result.get('documents'):
            lng = float(result['documents'][0]['x'])
            lat = float(result['documents'][0]['y'])
            return lat, lng
    except:
        return None, None
    return None, None

# 구글 시트 데이터 로드 함수
@st.cache_data(ttl=600) # 10분마다 새 데이터를 가져오도록 설정
def load_data_from_gsheet(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다: {e}")
        return None

# --- 3. 메인 UI 구성 ---

st.title("📍 Here Marker")
st.subheader("실시간 구글 시트 연동 지도")

# GPS 위치 가져오기
location = streamlit_geolocation()
if location['latitude'] and location['longitude']:
    my_lat, my_lng = location['latitude'], location['longitude']
    st.success("🛰️ 현재 위치(GPS)를 성공적으로 잡았습니다.")
else:
    # GPS를 잡기 전 기본 좌표 (대전시청 기준)
    my_lat, my_lng = 36.3504, 127.3845
    st.info("⌛ GPS 신호를 기다리는 중입니다. 기본 위치가 표시됩니다.")

# 데이터 불러오기
df = load_data_from_gsheet(SHEET_URL)

if df is not None and '주소' in df.columns:
    # 주소를 좌표로 변환
    with st.spinner('업체 위치 정보를 갱신 중입니다...'):
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        df = df.dropna(subset=['위도', '경도'])

    # 지도 생성
    m = folium.Map(location=[my_lat, my_lng], zoom_start=14)

    # 내 위치 표시 (파란색 마커)
    folium.Marker(
        [my_lat, my_lng],
        popup="내 위치",
        icon=folium.Icon(color='blue', icon='star')
    ).add_to(m)

# 업체 위치 표시 (빨간색 마커)
    for _, row in df.iterrows():
        folium.Marker(
            [row['위도'], row['경도']],
            # 1. 마커를 클릭했을 때 나타나는 상세 정보 (팝업)
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}<br>{row.get('전화번호', '')}", max_width=250),
            
            # 2. 마커 옆에 항상 표시되는 이름 (툴팁)
            # permanent=True: 마우스를 올리지 않아도 항상 이름이 보입니다.
            # permanent=False: 마우스를 올리거나 모바일에서 터치했을 때만 이름이 보입니다.
            tooltip=folium.Tooltip(row['업체명'], permanent=True),
            
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=500)

    # 하단 데이터 리스트
    with st.expander("📋 전체 업체 명단 확인"):
        st.dataframe(df[['업체명', '주소']], use_container_width=True)

else:
    st.warning("구글 시트에 '주소' 컬럼이 있는지 확인해 주세요.")

# 새로고침 버튼
if st.button("🔄 데이터 강제 새로고침"):
    st.cache_data.clear()
    st.rerun()