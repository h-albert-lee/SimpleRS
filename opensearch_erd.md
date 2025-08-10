## 📄 OpenSearch 스키마 정리 (추천 시스템)

### 1. `curation-logs-YYYYMMDD` 인덱스

* **목적**: 사용자의 콘텐츠 소비 로그(클릭, 조회 등)를 저장 (실시간 규칙에서 활용)
* **인덱스 패턴**: `curation-logs-YYYYMMDD` (예: `curation-logs-20250416`)

| field            | type           | constraints | description                       |
| ---------------- | -------------- | ----------- | --------------------------------- |
| @timestamp       | date           | required    | 로그 발생 시간 (UTC 권장)                 |
| cust\_no         | long / keyword | required    | 고객 번호 (`user.CUST_NO`와 매칭)        |
| curation\_id     | keyword        | required    | 상호작용한 콘텐츠 ID (`curation._id`와 매칭) |
| curation\_title  | text / keyword | optional    | 콘텐츠 제목 (분석용)                      |
| user\_action     | object         | optional    | 사용자 행동 정보 객체                      |
| ├─ action        | number         | optional    | 행동 유형 (1=클릭, 2=상세조회 등)            |
| ├─ duration      | number         | optional    | 체류 시간 (초)                         |
| └─ scroll\_depth | float          | optional    | 스크롤 깊이 (0.0 \~ 1.0)               |

**예시 Document**

```json
{
  "@timestamp": "2025-04-16T15:30:00Z",
  "cust_no": 1061202611,
  "curation_id": "661e1a0b1122334455667799",
  "curation_title": "카카오 주가, 반등의 시작?",
  "user_action": {
    "action": 1,
    "source": "home_feed"
  }
}
```

---

### 2. `screen-YYYYMMDD` 인덱스

* **목적**: 주식 종목의 일별 시세 및 수익률 정보를 저장 (실시간 규칙에서 활용)
* **인덱스 패턴**: `screen-YYYYMMDD` (예: `screen-20250416`)

| field        | type           | constraints | description                        |
| ------------ | -------------- | ----------- | ---------------------------------- |
| @timestamp   | date           | required    | 데이터 기록 시각 (UTC 권장)                 |
| shrt\_code   | keyword        | required    | 주식 종목 단축 코드 (`curation.label`과 매칭) |
| country      | keyword        | optional    | 주식 시장 국가                           |
| 1d\_returns  | float / double | optional    | 일일 수익률 (%)                         |
| 1m\_returns  | float / double | optional    | 최근 1개월 수익률 (%)                     |
| close\_price | number         | optional    | 종가                                 |
| volume       | number         | optional    | 거래량                                |

**예시 Document (KR)**

```json
{
  "@timestamp": "2025-04-16T08:00:00Z",
  "shrt_code": "005930",
  "country": "Korea",
  "1d_returns": 1.25,
  "1m_returns": 3.5,
  "close_price": 85000,
  "volume": 15000000
}
```

**예시 Document (US)**

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
```
