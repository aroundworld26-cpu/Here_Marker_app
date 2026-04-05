import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io
from streamlit_geolocation import streamlit_geolocation
import ssl

# --- 모바일 최적화: 버튼 글자 크기 및 간격 조절 ---
# --- 모바일 최적화: 버튼 최소 크기 및 가로 한 줄 밀착 배치 ---
st.markdown("""
    <style>
    /* 1. 기본 GPS 아이콘 숨기기 */
    iframe[title="streamlit_geolocation.streamlit_geolocation"] {
        display: none;
    }

    /* 2. 버튼 컨테이너를 가로로 촘촘하게 배치 (핵심) */
    [data-testid="stHorizontalBlock"] {
        display: flex;
        flex-direction: row;
        flex-wrap: nowrap;      /* 줄바꿈 금지 */
        overflow-x: auto;       /* 버튼이 너무 많으면 가로 스크롤 허용 */
        gap: 5px !important;    /* 버튼 사이 간격 5px */
        align-items: center;
    }

    /* 3. 각 버튼 컬럼의 너비를 '균등'이 아닌 '최소 내용치'로 설정 */
    [data-testid="column"] {
        width: auto !important;
        flex: 0 1 auto !important;
        min-width: min-content !important;
    }

    /* 4. 버튼 내부 스타일 세밀 조절 */
    div[data-testid="stButton"] button {
        font-size: 11px !important;    /* 글자 크기 살짝 축소 */
        padding: 4px 10px !important;  /* 좌우 여백 최적화 */
        white-space: nowrap !important; /* 글자 잘림 방지 */
        border-radius: 20px !important; /* 둥근 버튼으로 세련되게 */
    }

    /* 5. 현재 선택된 팀 버튼 강조 색상 */
    div[data-testid="stButton"] button:contains("✅") {
        background-color: #007BFF !important;
        color: white !important;
        border-color: #0056b3 !important;
    }
    </style>
""", unsafe_allow_html=True)
# --- 0. 환경 설정 (맥 SSL 에러 및 페이지 설정) ---
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
        # SSL 검증 무시(verify=False) 추가
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
        response.encoding = 'utf-8' # 한글 깨짐 방지
        df = pd.read_csv(io.StringIO(response.text))
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다: {e}")
        return None

# --- 3. 메인 UI 구성 ---

st.title("📍 Here Marker")
# st.subheader("실시간 구글 시트 연동 지도")

# 우측 상단 새로고침 버튼
col_title, col_refresh = st.columns([8, 2])
with col_refresh:
    if st.button("🔄 전체 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. GPS 아이콘 + 팀 선택 버튼 (모바일 최적화 한 줄 배치) ---
if 'current_team' not in st.session_state:
    st.session_state.current_team = list(sheet_dict.keys())[0]

# 컬럼 비중 조절 (아이콘용 작은 칸 1개 + 팀 개수만큼의 칸)
# 아이콘 1.5, 각 팀 버튼 3의 비율로 배분 (팀이 많으면 숫자를 조절하세요)
column_weights = [1.5] + [3] * len(sheet_dict)
menu_cols = st.columns(column_weights)

# 1. 가장 왼쪽: GPS 아이콘 버튼 (누르면 현재 위치로 지도 갱신 효과)
with menu_cols[0]:
    if st.button("🎯", help="내 위치 찾기", use_container_width=True):
        st.rerun() # 앱을 다시 읽어 GPS를 최신화함

# 2. 옆으로 팀 리스트 버튼 배치
for i, team_name in enumerate(sheet_dict.keys()):
    with menu_cols[i+1]:
        # 현재 선택된 팀은 버튼 앞에 체크 표시(✅)를 붙여 시각적으로 구분
        display_name = f"✅ {team_name}" if st.session_state.current_team == team_name else team_name
        
        if st.button(display_name, use_container_width=True, key=f"btn_{i}"):
            st.session_state.current_team = team_name
            st.rerun() # 팀 변경 시 즉시 반영

# 현재 상태 안내 문구 (공간 절약을 위해 작게 표시)
# st.caption(f"📍 현재 **{st.session_state.current_team}** 데이터가 지도에 표시 중입니다.")

SELECTED_SHEET_URL = sheet_dict[st.session_state.current_team]
st.info(f"현재 **[{st.session_state.current_team}]** 데이터를 지도에 표시하고 있습니다.")

# --- 5. GPS 및 지도 로직 ---

# GPS 위치 가져오기 (컴포넌트)
location = streamlit_geolocation()

if location['latitude'] and location['longitude']:
    my_lat, my_lng = location['latitude'], location['longitude']
    st.success("🛰️ 현재 위치(GPS)를 성공적으로 잡았습니다.")
else:
    # 기본 위치 (대전시청 기준)
    my_lat, my_lng = 36.3504, 127.3845
    st.warning("⌛ GPS 신호를 기다리는 중입니다. 기본 위치(대전)가 표시됩니다.")

# 데이터 불러오기 및 좌표 변환
df = load_data_from_gsheet(SELECTED_SHEET_URL)

if df is not None and '주소' in df.columns:
    with st.spinner(f"'{st.session_state.current_team}' 위치 정보를 갱신 중입니다..."):
        # 좌표 변환 적용
        df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
        df = df.dropna(subset=['위도', '경도'])

    # 지도 생성
    m = folium.Map(location=[my_lat, my_lng], zoom_start=14)

    # 내 위치 마커 (파란색 별)
    folium.Marker(
        [my_lat, my_lng],
        popup="내 실제 위치",
        icon=folium.Icon(color='blue', icon='star')
    ).add_to(m)

    # 업체 마커 표시 (빨간색 핀 + 이름 상시 표시)
    for _, row in df.iterrows():
        folium.Marker(
            [row['위도'], row['경도']],
            popup=folium.Popup(f"<b>{row['업체명']}</b><br>{row['주소']}<br>{row.get('전화번호', '')}", max_width=250),
            tooltip=folium.Tooltip(row['업체명'], permanent=True), # 이름 상시 노출
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=600)

    # 하단 데이터 리스트 확인
    with st.expander(f"📋 {st.session_state.current_team} 상세 명단"):
        st.dataframe(df[['업체명', '주소']], use_container_width=True)

else:
    st.error("구글 시트의 내용을 읽어오지 못했거나 '주소' 컬럼이 없습니다. 시트 설정을 확인해 주세요.")