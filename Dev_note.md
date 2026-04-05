** 작성일: 2026-04-05
---
아주 좋은 접근입니다! 구글 대신 국내 포털의 API를 활용하면 **신용카드 등록 없이, 사실상 완전 무료**로 원하시는 프로그램을 만드실 수 있습니다.

특히 **카카오(다음) API**를 강력히 추천합니다. 카카오의 '로컬 API(주소 검색)'는 하루 10만 건까지 무료로 제공되며, 지도 화면 자체는 오픈소스인 OpenStreetMap(Folium 기본 제공)을 결합하면 비용이 전혀 발생하지 않습니다.

카카오 API를 활용하여 완전 무료로 동작하도록 코드를 변경해 드립니다.

### 1. 카카오 API 키 발급 방법 (무료, 카드 등록 X)
1.  **카카오 디벨로퍼스(Kakao Developers)** 웹사이트에 카카오 계정으로 로그인합니다.
2.  [내 애플리케이션] > [애플리케이션 추가하기]를 눌러 앱을 하나 생성합니다.
3.  앱이 생성되면 요약 정보에 여러 개의 키가 나오는데, 그중 **'REST API 키'**를 복사해 둡니다.

### 2. 완전 무료 전환 코드 (app.py)
구글 라이브러리를 제거하고, 파이썬 내장 라이브러리인 `requests`를 사용해 카카오 서버에 주소 변환을 요청하도록 수정한 버전입니다.

```python
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io

st.set_page_config(page_title="인근 업체 지도 검색 (무료버전)", layout="wide")

# --- 카카오 REST API 키 (발급받은 키를 여기에 입력하세요) ---
KAKAO_REST_API_KEY = '여기에_카카오_REST_API_키를_입력하세요'

# 카카오 API를 이용한 주소 -> 좌표 변환 함수
@st.cache_data
def get_coordinates_kakao(address):
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        result = response.json()
        
        if result.get('documents'):
            # 카카오 API는 x가 경도(lng), y가 위도(lat)입니다.
            lng = float(result['documents'][0]['x'])
            lat = float(result['documents'][0]['y'])
            return lat, lng
    except Exception as e:
        return None, None
    return None, None

def create_sample_excel():
    data = {
        "업체명": ["대전시청", "정부대전청사", "대전동물보호센터", "유성구청"],
        "주소": [
            "대전광역시 서구 둔산로 100",
            "대전광역시 서구 청사로 189",
            "대전광역시 유성구 금남구즉로 1234",
            "대전광역시 유성구 대학로 211"
        ]
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

with st.sidebar:
    st.header("📂 데이터 관리")
    sample_file = create_sample_excel()
    st.download_button(
        label="📥 예시 엑셀 파일 다운로드",
        data=sample_file,
        file_name="업체리스트_예시.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["xlsx"])

st.title("📍 무료 API 활용 업체 지도")
default_lat, default_lng = 36.3504, 127.3845 

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    if '주소' in df.columns:
        with st.spinner('카카오 API로 주소를 좌표로 변환 중입니다...'):
            df[['위도', '경도']] = df['주소'].apply(lambda x: pd.Series(get_coordinates_kakao(str(x))))
            df = df.dropna(subset=['위도', '경도'])
        
        st.success(f"총 {len(df)}건의 위치를 성공적으로 불러왔습니다. (요금 발생 없음)")

        # Folium 기본 지도는 OpenStreetMap을 사용하여 완전 무료입니다.
        m = folium.Map(location=[default_lat, default_lng], zoom_start=12)

        folium.Marker(
            [default_lat, default_lng],
            popup="내 위치",
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

        for _, row in df.iterrows():
            folium.Marker(
                [row['위도'], row['경도']],
                popup=f"<b>{row.get('업체명', '업체')}</b><br>{row['주소']}",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)

        st_folium(m, width="100%", height=500)
    else:
        st.error("엑셀 파일에 '주소' 컬럼이 존재하지 않습니다.")
else:
    st.info("왼쪽 사이드바에서 엑셀 파일을 업로드해 주세요.")
    m_empty = folium.Map(location=[default_lat, default_lng], zoom_start=12)
    st_folium(m_empty, width="100%", height=500)
```

### 이 방식의 장점
* **비용 스트레스 제로:** 구글처럼 카드를 등록할 필요가 없고, 하루 10만 건이면 개인이 엑셀 데이터를 처리하기에 차고 넘치는 양입니다. 초과 요금 차단 코드를 굳이 넣지 않아도 안전합니다.
* **한국 주소 인식률 우수:** 구글 지도는 간혹 한국의 지번 주소나 도로명 주소를 정확히 변환하지 못하는 경우가 있는데, 카카오 API는 한국 주소 체계에 가장 최적화되어 있어 인식률이 훨씬 뛰어납니다.
* **가벼운 라이브러리:** `googlemaps` 라이브러리를 설치할 필요 없이, 파이썬 기본 통신 라이브러리인 `requests`만으로 빠르고 가볍게 동작합니다.

터미널에서 `pip install requests` 만 추가로 확인해 주신 뒤 코드를 실행하시면 완벽하게 무료로 구동됩니다.

---
카카오 디벨로퍼스(Kakao Developers) 사이트에서 몇 가지 간단한 절차를 거치면 바로 REST API 키를 발급받고 확인할 수 있습니다. 

다음 순서대로 진행해 주시면 됩니다.

### 🔑 카카오 REST API 키 확인 및 발급 방법

1. **카카오 디벨로퍼스 접속 및 로그인**
   * 카카오 디벨로퍼스 공식 웹사이트([https://developers.kakao.com](https://developers.kakao.com))에 접속합니다.
   * 우측 상단의 **[로그인]** 버튼을 눌러 평소 사용하시는 카카오톡 계정으로 로그인합니다.

2. **애플리케이션 추가**
   * 상단 메뉴에서 **[내 애플리케이션]**을 클릭합니다.
   * 화면 중앙이나 우측에 있는 **[애플리케이션 추가하기]** 버튼을 누릅니다.
   * '앱 이름'과 '사업자명'을 입력하는 창이 나옵니다. (개인 프로젝트이므로 앱 이름은 아까 고르신 이름이나 임의의 이름, 사업자명은 본인 이름이나 닉네임을 적어주셔도 무방합니다.)
   * 이용약관에 동의한 후 **[저장]**을 누릅니다.

3. **REST API 키 확인**
   * 방금 생성한 애플리케이션을 클릭하여 상세 페이지로 들어갑니다.
   * 왼쪽 메뉴 중 **[앱 설정] > [요약 정보]** 페이지(보통 클릭 시 가장 먼저 보이는 화면)를 확인합니다.
   * 화면 중앙에 **'앱 키'**라는 항목이 있으며, 그 아래에 4가지 종류의 키가 보입니다.
     * 네이티브 앱 키
     * **REST API 키** 👈 **(여기에 있는 영문+숫자 조합의 긴 문자열이 필요합니다.)**
     * JavaScript 키
     * Admin 키

4. **키 복사 및 코드에 적용**
   * **'REST API 키'** 옆에 있는 복사 버튼을 눌러 키를 복사합니다.
   * 파이썬 코드의 `KAKAO_REST_API_KEY = '여기에_카카오_REST_API_키를_입력하세요'` 부분의 따옴표 안에 복사한 키를 붙여넣으시면 됩니다.

**※ 주의사항:** 구글 API 키와 마찬가지로 카카오 REST API 키 역시 본인의 고유한 비밀번호와 같으므로, 외부에 공개된 게시판이나 깃허브 등에 코드를 올릴 때는 키 값이 노출되지 않도록 주의해 주세요.

---
구글 스프레드시트를 데이터베이스처럼 활용하여 실시간으로 업체 정보를 불러오는 **'방법 2'**가 적용된 최종 코드를 구성해 드립니다. 

이 방식을 사용하면 핸드폰으로 현장에서 업체 정보를 수정하거나 추가해도, 앱을 새로고침만 하면 즉시 지도에 반영되어 매우 효율적입니다.

### 1. 구글 스프레드시트 준비 (사전 작업)
1. 구글 스프레드시트를 하나 만들고, 첫 줄(헤더)에 **업체명, 주소, 전화번호** 컬럼을 만듭니다.
2. 내용을 입력한 후, 우측 상단 **[공유]** 버튼 -> 일반 액세스를 **[링크가 있는 모든 사용자]**로 변경합니다.
3. 웹 브라우저 주소창의 링크에서 `/edit...` 부분을 지우고 `/export?format=csv`를 붙여 복사해 둡니다.
   * 예시: `https://docs.google.com/spreadsheets/d/시트ID/export?format=csv`

### 2. Here Marker 최종 코드 (app.py)

```python
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
            popup=f"<b>{row.get('업체명', '업체')}</b><br>{row['주소']}<br>{row.get('전화번호', '')}",
            tooltip=row.get('업체명', '상세보기'),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=500)

    # 하단 데이터 리스트
    with st.expander("📋 전체 업체 명단 확인"):
        st.dataframe(df[['업체명', '주소', '전화번호']], use_container_width=True)

else:
    st.warning("구글 시트에 '주소' 컬럼이 있는지 확인해 주세요.")

# 새로고침 버튼
if st.button("🔄 데이터 강제 새로고침"):
    st.cache_data.clear()
    st.rerun()
```

### 3. 필수 설정 사항

**1. 라이브러리 추가 설치:**
터미널에서 GPS 라이브러리를 꼭 설치해 주세요.
```bash
pip install streamlit-geolocation
```

**2. `.streamlit/secrets.toml` 파일 구성:**
내 컴퓨터에서 테스트할 때 API 키와 시트 주소를 아래 형식으로 넣어줍니다.
```toml
KAKAO_REST_API_KEY = "발급받은_REST_API_키"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/시트ID/export?format=csv"
```

### 💡 이 프로그램의 장점
* **편의성:** 현장에서 핸드폰으로 구글 스프레드시트 앱을 열어 주소만 수정하면, 이 프로그램에 즉시 반영됩니다.
* **현장 중심:** `streamlit-geolocation`을 통해 내 실제 발걸음을 따라 지도가 움직입니다.
* **무료 운영:** 카카오 API(하루 10만 건 무료)와 구글 시트(무료)를 사용하므로 운영 비용이 들지 않습니다.

