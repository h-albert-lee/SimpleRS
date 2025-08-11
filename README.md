# SimpleRS - Simple Recommendation System

이 프로젝트는 간단한 추천 시스템을 구현합니다.

## 구조

- `api/`: API 서버 관련 코드 (ranking)
- `batch/`: 배치 처리 관련 코드 (candidate generation)
- `configs/`: 설정 파일들
- `scripts/`: 실행 스크립트들

## 배치 시스템 (Candidate Generation)

### 개요
배치 시스템은 3개의 candidate pool을 통해 사용자별 추천 후보를 생성합니다:

1. **Global Pool**: 실시간 시세 상승률 top 10 종목의 한국/미국 컨텐츠
2. **Local Pool**: 
   - 시장 관련 컨텐츠 (btopic="시장")
   - 사용자 보유 종목 관련 컨텐츠
   - 사용자 보유 종목의 섹터 관련 컨텐츠
3. **Other Pool**: liked_users가 높은 컨텐츠

### 설정

`configs/config.yaml` 파일에서 다음을 설정합니다:
- MongoDB 연결 정보
- OpenSearch 연결 정보  
- Oracle DB 연결 정보 (포트폴리오 API용)

### 실행

#### 개발/테스트 환경
```bash
# 의존성 설치
pip install -r requirements.txt

# 테스트 실행 (더미 데이터)
python scripts/test_batch_logic.py

# 배치 실행
./scripts/run_candidate_generation.sh
```

#### 프로덕션 환경
```bash
# 프로덕션 배치 실행 (로그 포함)
./scripts/run_batch_production.sh
```

### 결과
- MongoDB `user_candidate` 컬렉션에 사용자별 추천 후보와 점수가 저장됩니다
- 스키마: `{cust_no, curation_list: [{curation_id, score}], create_dt, modi_dt}`

### API 서버
```bash
python api/app.py
```

## 의존성
- Python 3.8+
- MongoDB
- OpenSearch
- Oracle DB (포트폴리오 API)

자세한 패키지 목록은 `requirements.txt` 참조
