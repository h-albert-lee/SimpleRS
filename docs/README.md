# SimpleRS Batch System Documentation

## 📚 목차

1. [시스템 개요](#시스템-개요)
2. [아키텍처](#아키텍처)
3. [개발자 가이드](#개발자-가이드)
4. [운영 가이드](#운영-가이드)
5. [트러블슈팅](#트러블슈팅)

## 시스템 개요

SimpleRS는 3-pool 아키텍처를 기반으로 한 추천시스템의 배치 후보 생성 시스템입니다.

### 주요 특징

- **3-Pool 아키텍처**: Global, Local, Other 세 개의 후보 풀
- **동일 가중치**: 각 풀에 1.0의 동일한 가중치 적용
- **강화된 예외처리**: 외부 API 장애에 대한 graceful 처리
- **배치 처리**: MongoDB 대량 저장을 위한 배치 처리
- **모니터링**: 상세한 로깅 및 성능 메트릭

### 후보 풀 구성

1. **Global Pool**: 실시간 시세 상승률 top 10 종목의 한국/미국 컨텐츠
2. **Local Pool**: 
   - 시장 관련 컨텐츠 (btopic="시장")
   - 사용자 보유 종목 관련 컨텐츠
   - 사용자 보유 종목의 섹터 관련 컨텐츠
3. **Other Pool**: liked_users가 높은 컨텐츠

## 아키텍처

```
SimpleRS/
├── batch/                          # 배치 시스템 코어
│   ├── __init__.py
│   ├── candidate_generation.py     # 메인 배치 프로세스
│   ├── pipeline/                   # 파이프라인 모듈
│   │   ├── global_candidate.py     # 글로벌 후보 생성
│   │   ├── local_candidate.py      # 로컬 후보 생성
│   │   └── final_candidate.py      # 최종 후보 생성 및 스코어링
│   ├── rules/                      # 룰 엔진
│   │   ├── base.py                 # 베이스 룰 클래스
│   │   ├── global_rules.py         # 글로벌 룰 구현
│   │   └── local_rules.py          # 로컬 룰 구현
│   └── utils/                      # 유틸리티
│       ├── __init__.py
│       ├── config_loader.py        # 설정 로더
│       ├── data_loader.py          # 데이터 로더 (API 연동)
│       ├── db_manager.py           # 데이터베이스 관리
│       └── logging_setup.py        # 로깅 설정
├── configs/                        # 설정 파일
│   └── config.yaml
├── scripts/                        # 실행 스크립트
│   ├── run_batch_production.sh     # 프로덕션 실행
│   ├── run_candidate_generation.sh # 개발 실행
│   ├── test_batch_logic.py         # 로직 테스트
│   └── setup_test_data.py          # 테스트 데이터 설정
└── docs/                           # 문서
    ├── README.md                   # 이 파일
    ├── development_guide.md        # 개발자 가이드
    ├── rule_development.md         # 룰 개발 가이드
    ├── operations_guide.md         # 운영 가이드
    └── ranking_guide.md            # 랭킹 시스템 가이드
```

### 데이터 플로우

```
1. MongoDB에서 사용자/컨텐츠 데이터 로드
2. OpenSearch에서 주식 시세 데이터 조회
3. 포트폴리오 API에서 사용자 보유 종목 조회
4. 3개 풀별로 후보 생성
5. 사용자별 최종 후보 생성 및 스코어링
6. MongoDB user_candidate 컬렉션에 저장
```

## 개발자 가이드

자세한 개발자 가이드는 [development_guide.md](development_guide.md)를 참조하세요.

### 빠른 시작

```bash
# 의존성 설치
pip install -r requirements.txt

# 설정 파일 수정
vi configs/config.yaml

# 테스트 실행
python scripts/test_batch_logic.py

# 배치 실행
./scripts/run_batch_production.sh
```

## 운영 가이드

자세한 운영 가이드는 [operations_guide.md](operations_guide.md)를 참조하세요.

### 모니터링 포인트

- **배치 실행 시간**: 정상적으로 완료되는지 확인
- **후보 생성 수**: 각 풀별 후보 생성 수 모니터링
- **외부 API 응답**: OpenSearch, 포트폴리오 API 응답 시간
- **MongoDB 저장**: 저장 성공률 및 성능

### 알람 설정

- 배치 실행 실패
- 외부 API 연결 실패
- MongoDB 저장 실패
- 메모리 사용량 임계치 초과

## 트러블슈팅

### 자주 발생하는 문제

1. **OpenSearch 연결 실패**
   - 네트워크 연결 확인
   - 인증 정보 확인
   - 인덱스 존재 여부 확인

2. **포트폴리오 API 타임아웃**
   - API 서버 상태 확인
   - 타임아웃 설정 조정
   - 재시도 로직 확인

3. **MongoDB 저장 실패**
   - 연결 풀 설정 확인
   - 디스크 용량 확인
   - 인덱스 성능 확인

### 로그 분석

```bash
# 에러 로그 확인
grep "ERROR" /path/to/batch.log

# 성능 로그 확인
grep "duration\|elapsed" /path/to/batch.log

# API 응답 시간 확인
grep "response time" /path/to/batch.log
```

## 참고 자료

- [Rule Development Guide](rule_development.md): 새로운 룰 개발 방법
- [Development Guide](development_guide.md): 코드 개발 및 테스트
- [Operations Guide](operations_guide.md): 운영 및 모니터링
- [Ranking System Guide](ranking_guide.md): API 랭킹 구조 및 룰 설명