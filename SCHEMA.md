추천 시스템 데이터 스키마 (2025-04-16 기준)이 문서는 추천 시스템에서 사용하는 주요 데이터베이스(MongoDB, OpenSearch)의 스키마 정보를 설명합니다.1. MongoDB 스키마MongoDB는 주로 사용자 정보, 콘텐츠 메타데이터, 사용자별 추천 후보 목록 등을 저장합니다.1.1. user 컬렉션목적: 개별 사용자의 기본 정보, 동의 여부, 관심사 등을 저장합니다.주요 필드:CUST_NO타입: Number설명: 고객 번호. 시스템 전체에서 사용자를 식별하는 고유 키입니다. user_candidate 컬렉션의 cust_no와 연결됩니다.예시: 1061202622wlcm_msg타입: String설명: 사용자에게 보여줄 개인화된 환영 메시지.예시: "정만선임님 하이"last_login_dt타입: ISODate 또는 Null설명: 사용자의 마지막 로그인 일시. 초기값은 null일 수 있습니다.예시: ISODate("2025-04-15T10:00:00Z")last_upd_dt타입: ISODate 또는 Null설명: 사용자 정보가 마지막으로 수정된 일시. 초기값은 null일 수 있습니다.예시: ISODate("2025-04-16T09:30:00Z")agreement타입: Boolean설명: 서비스 이용 동의 여부.예시: trueuser_vec타입: Array<Number>설명: 사용자의 특성이나 유형을 나타내는 벡터 정보 (예: 클러스터링 ID, 사용자 세그먼트 등).예시: [1]conc타입: Array<Object>설명: 사용자의 관심사 목록. 각 객체는 관심사 이름과 우선순위를 포함합니다.객체 구조:cat_nm: (String) 관심사 이름 (예: "여행", "금융", "IT")prto: (Number) 관심사 우선순위 (숫자가 낮을수록 높음)예시:[
  { "cat_nm": "여행", "prto": 1 },
  { "cat_nm": "금융", "prto": 2 }
]
(추가 가능 필드 - 규칙용)recent_stocks: (Array<String>) 최근 본 주식 코드 목록group1_stocks: (Array<String>) 관심 그룹 1 주식 코드 목록onboarding_stocks: (Array<String>) 온보딩 선택 주식 코드 목록참고: 이 필드들은 user 컬렉션 또는 별도 테이블/캐시에서 관리될 수 있습니다.예시 Document:{
  "_id": ObjectId("661e0f3aabcd1234ef567890"),
  "CUST_NO": 1061202622,
  "wlcm_msg": "정만선임님 하이",
  "last_login_dt": ISODate("2025-04-15T10:00:00Z"),
  "last_upd_dt": ISODate("2025-04-16T09:30:00Z"),
  "agreement": true,
  "user_vec": [1],
  "conc": [
    { "cat_nm": "여행", "prto": 1 },
    { "cat_nm": "금융", "prto": 2 }
  ],
  "recent_stocks": ["000660"],
  "group1_stocks": ["005380"],
  "onboarding_stocks": ["005930"]
}
1.2. user_candidate 컬렉션목적: 각 사용자별 추천 초기 후보 콘텐츠 목록과 초기 점수를 저장합니다. (배치 생성/갱신)주요 필드:cust_no타입: Number설명: 고객 번호. user.CUST_NO와 매칭됩니다. (인덱싱 필요)예시: 1061202622curation_list타입: Object (Dictionary)설명: 추천 후보 콘텐츠 ID(Key)와 점수(Value) 딕셔너리. Key는 curation._id(문자열)와 연결됩니다.구조:Key: (String) 콘텐츠 ID (curation._id)Value: (Number, Float) 콘텐츠 점수예시:{
  "661e1a0b1122334455667788": 0.85,
  "661e1a0b1122334455667799": 0.72,
  "661e1a0b11223344556677aa": 0.65
}
예시 Document:{
  "_id": ObjectId("661e1a0b11223344556677bb"),
  "cust_no": 1061202622,
  "curation_list": {
    "661e1a0b1122334455667788": 0.85,
    "661e1a0b1122334455667799": 0.72,
    "661e1a0b11223344556677aa": 0.65,
    "661e1a0b11223344556677cc": 0.55,
    "661e1a0b11223344556677dd": 0.5
  }
}
1.3. curation 컬렉션목적: 추천 대상 콘텐츠(큐레이션)의 메타데이터를 저장합니다.주요 필드:_id타입: ObjectId (또는 고유 String)설명: 콘텐츠 고유 식별자. user_candidate.curation_list Key와 연결됩니다.예시: ObjectId("661e1a0b1122334455667788")label타입: String 또는 Null설명: 콘텐츠 관련 대표 식별자 (예: 주식 코드(shrt_code)). 규칙에서 사용됩니다.예시: "005930", "Tech", nulltitle타입: String설명: 콘텐츠 제목.예시: "삼성전자 주가 전망과 투자 전략"category (또는 btopic, stopic)타입: String설명: 콘텐츠 카테고리 정보. 규칙에서 사용될 수 있습니다.예시: "Finance", "IT", "시장"thumbnail타입: String (URL)설명: 콘텐츠 썸네일 이미지 URL.예시: "https://example.com/thumb/123.jpg"(기타 배치/분석용 필드)functions: (String or Array) 콘텐츠 관련 기능 태그total_click_cnt: (Number) 전체 클릭 수recent_click_cnt: (Number) 최근 클릭 수like_cnt: (Number) 좋아요 수dislike_cnt: (Number) 싫어요 수예시 Document:{
  "_id": ObjectId("661e1a0b1122334455667788"),
  "label": "005930",
  "title": "삼성전자 실적 발표, 주가 영향은?",
  "category": "Finance",
  "btopic": "기업분석",
  "stopic": "실적시즌",
  "thumbnail": "https://example.com/thumb/samsung.jpg",
  "total_click_cnt": 1502,
  "recent_click_cnt": 350,
  "like_cnt": 120,
  "dislike_cnt": 5
}
1.4. user_port 컬렉션목적: 사용자의 실제 보유 종목(포트폴리오) 정보를 저장합니다. (배치 코드에서 언급됨)주요 필드:cust_no타입: Number설명: 고객 번호. user.CUST_NO와 매칭됩니다.예시: 1061202622owned_stocks타입: Array<String>설명: 보유 주식 코드 목록. 실시간 규칙(BoostUserStocksRule)에서 사용됩니다.예시: ["005930", "035720", "000660"]예시 Document:{
  "_id": ObjectId("661e2b0cabcdef9876543210"),
  "cust_no": 1061202622,
  "owned_stocks": ["005930", "035720", "000660"]
}
참고: 이 정보는 user 컬렉션에 포함될 수도 있습니다.1.5. global_data 컬렉션목적: 시스템 전역 데이터 또는 비로그인 사용자용 데이터를 저장합니다. (API 구현 시 가정)주요 필드 (비로그인 추천용):_id타입: String설명: 데이터 종류 식별 키.예시: "anonymous_recs"curation_ids타입: Array<String>설명: 비로그인 사용자 추천 콘텐츠 ID 목록. curation._id(문자열)와 매칭됩니다.예시: ["item_popular_1", "item_general_5", ...]예시 Document:{
  "_id": "anonymous_recs",
  "description": "Recommendations for anonymous users based on general popularity.",
  "curation_ids": [
    "661e1a0b1122334455667788",
    "661e1a0b11223344556677aa",
    "661e1a0b11223344556677dd",
    "item_manual_curation_1",
    "item_popular_general_2"
  ],
  "last_updated": ISODate("2025-04-16T00:00:00Z")
}
2. OpenSearch 스키마OpenSearch는 주로 대용량 로그 데이터나 검색이 필요한 데이터를 저장합니다.2.1. curation-logs-YYYYMMDD 인덱스목적: 사용자의 콘텐츠 소비 로그(클릭, 조회 등)를 저장합니다. 실시간 규칙에서 사용됩니다.인덱스 이름 패턴: curation-logs-YYYYMMDD (예: curation-logs-20250416)주요 필드:@timestamp (또는 timestamp)타입: date설명: 로그 발생 시간 (UTC 권장).예시: "2025-04-16T15:30:00Z"cust_no타입: long (또는 keyword)설명: 고객 번호. user.CUST_NO와 매칭됩니다.예시: 1061202611curation_id타입: keyword설명: 상호작용한 콘텐츠 ID. curation._id와 매칭됩니다.예시: "661e1a0b1122334455667799"curation_title (선택 사항)타입: text (또는 keyword)설명: 콘텐츠 제목 (분석용).예시: "카카오 주가, 반등의 시작?"user_action타입: object (JSON Object)설명: 사용자 행동 정보 객체.구조 예시:action: (Number) 행동 유형 (1=클릭, 2=상세조회 등)duration: (Number) 체류 시간 (초)scroll_depth: (Float) 스크롤 깊이 (0.0 ~ 1.0)예시: {"action": 1, "duration": 120, "scroll_depth": 0.75}예시 Record:{
  "@timestamp": "2025-04-16T15:30:00Z",
  "cust_no": 1061202611,
  "curation_id": "661e1a0b1122334455667799",
  "curation_title": "카카오 주가, 반등의 시작?",
  "user_action": {
    "action": 1,
    "source": "home_feed"
  }
}
2.2. screen-YYYYMMDD 인덱스목적: 주식 종목의 일별 시세 및 수익률 정보를 저장합니다. 실시간 규칙에서 사용됩니다.인덱스 이름 패턴: screen-YYYYMMDD (예: screen-20250416)주요 필드:shrt_code타입: keyword설명: 주식 종목 단축 코드. curation.label과 매칭됩니다.예시: "005930"1d_returns타입: float 또는 double (Null 허용)설명: 일일 수익률 (%).예시: 1.5, -0.2, null1m_returns타입: float 또는 double (Null 허용)설명: 최근 1개월 수익률 (%).예시: 5.8, -2.1, nullcountry (선택 사항)타입: keyword설명: 주식 시장 국가.예시: "Korea", "USA"(기타 시세 필드)close_price: (Number) 종가volume: (Number) 거래량 등예시 Record:{
  "@timestamp": "2025-04-16T08:00:00Z",
  "shrt_code": "005930",
  "country": "Korea",
  "1d_returns": 1.25,
  "1m_returns": 3.5,
  "close_price": 85000,
  "volume": 15000000
}
```json
{
  "@timestamp": "2025-04-16T08:00:00Z",
  "shrt_code": "AAPL",
  "country": "USA",
  "1d_returns": -0.5,
  "1m_returns": null,
  "close_price": 175.50,
  "volume": 80000000
}
이 문서는 현재까지 논의된 내용을 기반으로 작성되었으며, 실제 운영 환경 및 데이터 요구사항에 따라 지속적으로 업데이트될 수 있습니다.