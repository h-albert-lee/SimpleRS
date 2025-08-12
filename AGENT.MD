# LLM Project Context — 추천시스템 (배치 Candidate Generation + 실시간 Ranking)

## 1) MongoDB 스키마 (원문 요약)

### `curation`

| column\_name       | type          | constraints | description         |
| ------------------ | ------------- | ----------- | ------------------- |
| \_id               | 시스템키값         | PK          |                     |
| btopic             | string        |             | 대주제                 |
| stopic             | string        |             | 소주제                 |
| label              | string        |             | 라벨                  |
| gic\_code          | string        |             | 예: `UBSTLSA_005930` |
| krw\_currv\_sumamt | int / null    |             | krw 현재시가총액          |
| stk\_name          | string / null |             | 종목명                 |
| title              | string        |             | 제목                  |
| result             | string        |             | 결과값                 |
| thumbnail          | string        |             | 썸네일파일명(CMS? NGINX?) |
| total\_click\_cnt  | int           |             | 총 클릭수               |
| recent\_click\_cnt | int           |             | 최근 클릭수              |
| liked\_users       | cust\_no\[]   |             | 좋아요 표시한 고객 번호 목록    |
| disliked\_users    | cust\_no\[]   |             | 싫어요 표시한 고객 번호 목록    |
| live\_from         | timestamp     |             | 콘텐츠 시작일             |
| entry\_curation    | list\[int]    |             | 진입 큐레이션 ID들         |
| ext\_lm\_yn        | string        |             | 외부 LM 사용 여부         |
| create\_dt         | datetime(utc) |             | 생성 일시               |
| modi\_dt           | datetime(utc) |             | 수정 일시               |

---

### `curation_hist`

| column\_name      | type            | constraints         | description |
| ----------------- | --------------- | ------------------- | ----------- |
| \_id              | 시스템키값           | PK                  |             |
| curation\_id      | string          | FK → `curation._id` | 큐레이션 ID     |
| batch\_dt         | string          |                     | 배치 수행일자     |
| qst\_cnt          | int             |                     | 질문 수        |
| result            | string          |                     | 결과값         |
| component\_list   | array           |                     | 컴포넌트 목록     |
| rsp\_ok\_yn       | string("Y"/"N") |                     | 응답 성공 여부    |
| guardrail\_result | object          |                     | 가드레일 코드     |

---

### `user_candidate`

| column\_name   | type                              | constraints         | description     |
| -------------- | --------------------------------- | ------------------- | --------------- |
| \_id           | 시스템키값                             | PK                  |                 |
| cust\_no       | string                            | FK → `user.cust_no` | 고객번호            |
| curation\_list | list\[{curation\_id, score\:int}] |                     | 추천 큐레이션 ID 및 점수 |
| create\_dt     | datetime                          |                     | 생성 일시           |
| modi\_dt       | datetime                          |                     | 수정 일시           |

---

### `user`

| column\_name    | type     | constraints | description                     |
| --------------- | -------- | ----------- | ------------------------------- |
| \_id            | 시스템키값    | PK          |                                 |
| cust\_no        | string   |             | 고객번호                            |
| cust\_nm        | string   |             | 고객 이름                           |
| cyber\_id       | string   |             | 사이버 아이디                         |
| last\_login\_dt | datetime |             | 최종 로그인 일시                       |
| user\_vec       | array    |             | 유저 벡터 정보                        |
| concerns        | object   |             | 관심 종목 정보 `{gic_code, stk_name}` |
| create\_dt      | datetime |             | 생성 일시                           |
| modi\_dt        | datetime |             | 수정 일시                           |

---

### `msg`

| column\_name              | type           | constraints         | description           |
| ------------------------- | -------------- | ------------------- | --------------------- |
| \_id                      | ObjectId       | PK                  |                       |
| chat\_id                  | ObjectId       | FK → `chat._id`     | 대화 ID                 |
| question                  | string         |                     | 질문 텍스트                |
| cust\_no                  | string         | FK → `user.cust_no` | 고객번호                  |
| planning\_text            | string         |                     | 플래닝 텍스트               |
| chaining\_sentences       | array\[string] |                     | 체이닝 문장                |
| input\_guardrail\_results | list\[object]  |                     | 입력 가드레일 결과            |
| components                | list\[object]  |                     | 컴포넌트 정보               |
| react\_type               | string         |                     | 반응 유형(좋아요, 싫어요, 선택없음) |
| create\_dt                | datetime       |                     | 생성 일시                 |
| modi\_dt                  | datetime       |                     | 수정 일시                 |

---

### `chat`

| column\_name    | type            | constraints         | description |
| --------------- | --------------- | ------------------- | ----------- |
| \_id            | 시스템키값           | PK                  |             |
| cust\_no        | string          | FK → `user.cust_no` | 고객번호        |
| start\_chat\_dt | datetime        |                     | 대화 시작일      |
| last\_chat\_dt  | datetime        |                     | 대화 종료일      |
| delete\_dt      | datetime / null |                     | 삭제 일시       |
| title           | string          |                     | 대화 제목       |
| create\_dt      | datetime        |                     | 생성 일시       |
| modi\_dt        | datetime        |                     | 수정 일시       |

---

### `session`

| column\_name | type                | constraints         | description |
| ------------ | ------------------- | ------------------- | ----------- |
| \_id         | 시스템키값               | PK                  |             |
| service      | string              |                     | 서비스 구분      |
| cust\_no     | string              | FK → `user.cust_no` | 고객번호        |
| cust\_nm     | string              |                     | 고객 이름       |
| cyber\_id    | string              |                     | 사이버 아이디     |
| create\_dt   | datetime(ttl index) |                     | 생성 일시       |

---

### `user_feedback`

| column\_name | type     | constraints         | description |
| ------------ | -------- | ------------------- | ----------- |
| \_id         | 시스템키값    | PK                  |             |
| cust\_no     | string   | FK → `user.cust_no` | 고객번호        |
| feedback     | string   |                     | 피드백 내용      |
| create\_dt   | datetime |                     | 생성 일시       |

---

### `user_stat`

| column\_name  | type             | constraints         | description |
| ------------- | ---------------- | ------------------- | ----------- |
| \_id          | 시스템키값            | PK                  |             |
| base\_ymd     | string(YYYYMMDD) |                     | 카운트 시점      |
| cust\_no      | string           | FK → `user.cust_no` | 고객번호        |
| question\_cnt | int              |                     | 질문 건수       |
| create\_dt    | datetime         |                     | 생성 일시       |
| modi\_dt      | datetime         |                     | 수정 일시       |

---

### `kill_switch`

| column\_name | type            | constraints | description |
| ------------ | --------------- | ----------- | ----------- |
| \_id         | 시스템키값           | PK          |             |
| kill\_yn     | string("Y"/"N") |             | 차단 여부       |
| regmn\_id    | string          |             | 생성자 사번      |
| adjmn\_id    | string          |             | 수정자 사번      |
| create\_dt   | datetime        |             | 생성 일시       |
| modi\_dt     | datetime        |             | 수정 일시       |

---

### `kill_switch_hist`

| column\_name | type            | constraints | description |
| ------------ | --------------- | ----------- | ----------- |
| \_id         | 시스템키값           | PK          |             |
| kill\_yn     | string("Y"/"N") |             | 차단 여부       |
| regmn\_id    | string          |             | 생성자 사번      |
| adjmn\_id    | string          |             | 수정자 사번      |
| create\_dt   | datetime        |             | 생성 일시       |
| modi\_dt     | datetime        |             | 수정 일시       |

---

#### FK 관계 요약 (원문)

* `user_candidate.cust_no` → `user.cust_no`
* `user_feedback.cust_no` → `user.cust_no`
* `user_stat.cust_no` → `user.cust_no`
* `session.cust_no` → `user.cust_no`
* `msg.chat_id` → `chat._id`
* `msg.cust_no` → `user.cust_no`
* `chat.cust_no` → `user.cust_no`
* `curation_hist.curation_id` → `curation._id`

---

## 2) OpenSearch 스키마 (원문 요약)

### `curation-logs-YYYYMMDD`

* 목적: 사용자의 콘텐츠 소비 로그(클릭/만족/새로고침 등) 저장
* 필드

  * `timestamp: date` (로그 발생 시간, UTC 권장)
  * `cust_no: long/keyword` (고객 번호 — `user.CUST_NO` 매칭)
  * `curation_id: keyword` (상호작용 콘텐츠 ID — `curation._id` 매칭)
  * `curation_title: text/keyword` (선택)
  * `user_action: object` (선택)

    * `sati_yn: keyword("Y"/"N")`
    * `sati_dt: date`
    * `click_btn_nm: keyword`
    * `click_dt: date`
    * `refresh_yn: keyword("Y"/"N")`
    * `refresh_dt: date`
  * (문서 하단 병기된 대안 필드)

    * `@timestamp: date`, `user_action.action: number`, `duration: number`, `scroll_depth: float`, `user_action.source: keyword`

### `screen-YYYYMMDD`

* 목적: 주식 종목 일별 시세/수익률 정보 저장
* 필드

  * `@timestamp: date` (UTC 권장)
  * `shrt_code: keyword` (주식 종목 단축 코드 — `curation.label` 매칭)
  * `country: keyword` (선택)
  * `1d_returns: float/double` (선택)
  * `1m_returns: float/double` (선택)
  * `close_price: number` (선택)
  * `volume: number` (선택)

---

## 3) 내부/외부 API (원문 요약)

### 고객 포트폴리오 조회 (MU800)

* **호출 위치**: module server (`172.17.4.53:8150`)
* **Endpoint**: `/api/mu800`
* **Request (Pydantic)**

  ```python
  class MU800Request(BaseModel):
      customer_no: str = Field(..., description="고객번호", examples=["105466942"])
      target_type: list[str] = Field(default_factory=list, description="조회유형", examples=["stock", "country", "sector"])
      top_n: int | None = Field(default=None, description="조회 개수", examples=[10])
  ```
* **Response (Pydantic)**

  ```python
  class MU800Response(BaseModel):
      portfolio_info: list[dict[str, Any]] = Field(default_factory=list)
      country_weight: dict[str, float] = Field(default_factory=list)
      sector_weight: dict[str, float] = Field(default_factory=list)
  ```
* **비고**: `customer_no`는 `mongodb.user`의 값과 동일하게 사용됨. 원문에 요청/응답 JSON 예시 포함.

---

