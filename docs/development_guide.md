# Development Guide

## 🚀 개발 환경 설정

### 필수 요구사항

- Python 3.8+
- MongoDB 4.4+
- OpenSearch 1.0+
- 최소 4GB RAM

### 의존성 설치

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 환경 변수 설정
export MONGODB_URI="mongodb://localhost:27017"
export OPENSEARCH_HOST="localhost:9200"
export PORTFOLIO_API_URL="https://api.example.com"
export LOG_LEVEL="INFO"
```

## 🏗️ 프로젝트 구조

```
SimpleRS/
├── batch/                          # 배치 시스템 코어
│   ├── __init__.py
│   ├── candidate_generation.py     # 메인 배치 프로세스
│   ├── pipeline/                   # 파이프라인 모듈
│   │   ├── __init__.py
│   │   ├── global_candidate.py     # 글로벌 후보 생성
│   │   ├── local_candidate.py      # 로컬 후보 생성
│   │   └── final_candidate.py      # 최종 후보 생성
│   ├── rules/                      # 룰 엔진
│   │   ├── __init__.py
│   │   ├── base.py                 # 베이스 룰 클래스
│   │   ├── global_rules.py         # 글로벌 룰 구현
│   │   └── local_rules.py          # 로컬 룰 구현
│   └── utils/                      # 유틸리티
│       ├── __init__.py
│       ├── config_loader.py        # 설정 로더
│       ├── data_loader.py          # 데이터 로더
│       ├── db_manager.py           # DB 관리
│       └── logging_setup.py        # 로깅 설정
├── configs/                        # 설정 파일
│   └── config.yaml
├── scripts/                        # 실행 스크립트
│   ├── run_batch_production.sh
│   ├── run_candidate_generation.sh
│   ├── test_batch_logic.py
│   └── setup_test_data.py
├── tests/                          # 테스트 코드
│   ├── __init__.py
│   ├── test_rules.py
│   ├── test_pipeline.py
│   └── test_utils.py
├── docs/                           # 문서
├── requirements.txt                # Python 의존성
├── .env.example                    # 환경 변수 예시
└── README.md
```

## 🔧 핵심 컴포넌트

### 1. 데이터 로더 (data_loader.py)

외부 API와의 연동을 담당합니다.

```python
from batch.utils.data_loader import fetch_user_portfolio, fetch_latest_stock_data

# 사용자 포트폴리오 조회
portfolio = fetch_user_portfolio("USER123")

# 최신 주식 데이터 조회
stock_data = fetch_latest_stock_data(os_client, days_back=3)
```

**주요 기능:**
- 포트폴리오 API 연동
- OpenSearch 주식 데이터 조회
- 강화된 예외 처리 및 재시도 로직
- 응답 데이터 검증

### 2. 데이터베이스 관리자 (db_manager.py)

MongoDB, OpenSearch, Oracle 연결을 관리합니다.

```python
from batch.utils.db_manager import get_mongo_db, get_os_client

# MongoDB 연결
db = get_mongo_db()

# OpenSearch 연결
os_client = get_os_client()

# 데이터 로드
users_ddf = load_users(db)
contents_ddf = load_contents(db)
```

**주요 기능:**
- 연결 풀 관리
- 자동 재연결
- 배치 저장 최적화
- 폴백 메커니즘

### 3. 룰 엔진 (rules/)

추천 로직을 모듈화한 룰 시스템입니다.

```python
from batch.rules.global_rules import GLOBAL_RULE_REGISTRY
from batch.rules.local_rules import LOCAL_RULE_REGISTRY

# 글로벌 룰 실행
global_rule = GLOBAL_RULE_REGISTRY["global_stock_top_return"]
candidates = global_rule.apply(context)

# 로컬 룰 실행
local_rule = LOCAL_RULE_REGISTRY["local_market_content"]
user_candidates = local_rule.apply(user, context)
```

**주요 기능:**
- 룰 등록 시스템
- 예외 처리 표준화
- 성능 모니터링
- 확장 가능한 아키텍처

### 4. 파이프라인 (pipeline/)

후보 생성 파이프라인을 구현합니다.

```python
from batch.pipeline.global_candidate import compute_global_candidates
from batch.pipeline.final_candidate import generate_candidate_for_user

# 글로벌 후보 생성
global_candidates = compute_global_candidates(context)

# 사용자별 최종 후보 생성
final_result = generate_candidate_for_user(user, global_candidates, other_candidates, context)
```

## 🧪 테스트

### 단위 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/

# 특정 모듈 테스트
python -m pytest tests/test_rules.py

# 커버리지 포함 테스트
python -m pytest tests/ --cov=batch --cov-report=html
```

### 통합 테스트

```bash
# 배치 로직 테스트
python scripts/test_batch_logic.py

# 개별 컴포넌트 테스트
python scripts/test_data_loader.py
python scripts/test_db_connections.py
```

### 성능 테스트

```bash
# 성능 벤치마크
python scripts/benchmark_batch.py

# 메모리 프로파일링
python -m memory_profiler scripts/profile_memory.py
```

## 🐛 디버깅

### 로깅 설정

```python
# 개발 환경에서 상세 로깅
import logging
logging.basicConfig(level=logging.DEBUG)

# 특정 모듈만 디버그
logging.getLogger('batch.rules').setLevel(logging.DEBUG)
```

### 디버그 모드 실행

```bash
# 디버그 모드로 배치 실행
PYTHONPATH=. python -m pdb batch/candidate_generation.py

# 특정 사용자만 처리
python scripts/debug_single_user.py --user_id USER123
```

### 일반적인 디버깅 시나리오

1. **외부 API 연결 실패**
```python
# API 응답 확인
import requests
response = requests.get("https://api.example.com/portfolio/USER123")
print(response.status_code, response.text)
```

2. **MongoDB 연결 문제**
```python
# 연결 테스트
from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017")
print(client.admin.command('ping'))
```

3. **메모리 사용량 확인**
```python
import psutil
import os
process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

## 🔄 개발 워크플로우

### 1. 기능 개발

```bash
# 새 브랜치 생성
git checkout -b feature/new-rule

# 개발 진행
# ... 코드 작성 ...

# 테스트 실행
python -m pytest tests/

# 코드 품질 검사
flake8 batch/
black batch/

# 커밋
git add .
git commit -m "Add new recommendation rule"
```

### 2. 코드 리뷰

- 모든 변경사항은 Pull Request를 통해 리뷰
- 최소 1명의 승인 필요
- 자동화된 테스트 통과 필수

### 3. 배포

```bash
# 스테이징 환경 배포
./scripts/deploy_staging.sh

# 프로덕션 배포
./scripts/deploy_production.sh
```

## 📊 성능 최적화

### 1. 데이터베이스 최적화

```python
# 인덱스 생성
db.users.create_index([("cust_no", 1)])
db.contents.create_index([("label", 1), ("btopic", 1)])

# 배치 크기 조정
BATCH_SIZE = 1000  # 메모리와 성능의 균형점
```

### 2. 메모리 최적화

```python
# 대용량 데이터 처리시 청크 단위 처리
def process_large_dataset(data, chunk_size=1000):
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        yield process_chunk(chunk)

# 불필요한 데이터 정리
del large_dataframe
gc.collect()
```

### 3. 병렬 처리

```python
from dask import delayed, compute

# 사용자별 병렬 처리
delayed_results = []
for user in users:
    delayed_result = delayed(process_user)(user)
    delayed_results.append(delayed_result)

results = compute(*delayed_results)
```

## 🔒 보안 고려사항

### 1. 인증 정보 관리

```python
# 환경 변수 사용
import os
api_key = os.getenv('API_KEY')

# 설정 파일에서 민감 정보 제외
# config.yaml에는 구조만, 실제 값은 환경 변수
```

### 2. 입력 검증

```python
def validate_user_id(user_id: str) -> bool:
    """사용자 ID 검증"""
    if not user_id or not isinstance(user_id, str):
        return False
    if len(user_id) > 50:  # 길이 제한
        return False
    if not user_id.isalnum():  # 영숫자만 허용
        return False
    return True
```

### 3. SQL 인젝션 방지

```python
# 파라미터화된 쿼리 사용
cursor.execute(
    "SELECT * FROM users WHERE cust_no = %s",
    (user_id,)
)
```

## 📈 모니터링 및 알람

### 1. 메트릭 수집

```python
import time
from datetime import datetime

class MetricsCollector:
    def __init__(self):
        self.metrics = {}
    
    def record_execution_time(self, operation: str, duration: float):
        self.metrics[f"{operation}_duration"] = duration
    
    def record_count(self, metric: str, count: int):
        self.metrics[metric] = count
```

### 2. 헬스 체크

```python
def health_check():
    """시스템 상태 확인"""
    checks = {
        'mongodb': check_mongodb_connection(),
        'opensearch': check_opensearch_connection(),
        'portfolio_api': check_portfolio_api(),
        'memory_usage': check_memory_usage()
    }
    return all(checks.values()), checks
```

### 3. 알람 설정

```python
def send_alert(message: str, severity: str = "warning"):
    """알람 발송"""
    if severity == "critical":
        # 즉시 알람
        send_slack_message(message)
        send_email_alert(message)
    elif severity == "warning":
        # 배치 알람
        log_warning(message)
```

## 🚀 배포 가이드

### 1. 환경별 설정

```yaml
# configs/config.yaml
development:
  mongodb:
    uri: "mongodb://localhost:27017"
  log_level: "DEBUG"

production:
  mongodb:
    uri: "${MONGODB_URI}"
  log_level: "INFO"
```

### 2. 배포 스크립트

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

ENV=${1:-staging}

echo "Deploying to $ENV environment..."

# 의존성 설치
pip install -r requirements.txt

# 설정 검증
python scripts/validate_config.py --env $ENV

# 데이터베이스 마이그레이션
python scripts/migrate_db.py --env $ENV

# 배치 작업 등록
crontab scripts/crontab.$ENV

echo "Deployment completed successfully!"
```

### 3. 롤백 절차

```bash
#!/bin/bash
# scripts/rollback.sh

PREVIOUS_VERSION=${1}

echo "Rolling back to version $PREVIOUS_VERSION..."

# 이전 버전으로 코드 복원
git checkout $PREVIOUS_VERSION

# 의존성 재설치
pip install -r requirements.txt

# 서비스 재시작
systemctl restart batch-service

echo "Rollback completed!"
```

## 📝 코딩 스타일

### 1. Python 스타일 가이드

- PEP 8 준수
- Type hints 사용
- Docstring 작성 (Google 스타일)

```python
def process_user_data(user_id: str, options: Dict[str, Any]) -> List[str]:
    """
    사용자 데이터를 처리하여 추천 후보를 생성합니다.
    
    Args:
        user_id: 사용자 식별자
        options: 처리 옵션
        
    Returns:
        추천 후보 ID 리스트
        
    Raises:
        ValueError: 잘못된 사용자 ID
        APIConnectionError: 외부 API 연결 실패
    """
    pass
```

### 2. 네이밍 컨벤션

- 클래스: PascalCase (`UserDataProcessor`)
- 함수/변수: snake_case (`process_user_data`)
- 상수: UPPER_SNAKE_CASE (`MAX_CANDIDATES`)
- 파일: snake_case (`data_loader.py`)

### 3. 에러 처리

```python
# 구체적인 예외 타입 사용
try:
    result = api_call()
except requests.ConnectionError as e:
    logger.error(f"API connection failed: {e}")
    raise APIConnectionError(f"Failed to connect to API: {e}")
except requests.Timeout as e:
    logger.warning(f"API timeout: {e}")
    return default_value
```

이 가이드를 따라 개발하면 일관성 있고 유지보수 가능한 코드를 작성할 수 있습니다.