# Operations Guide

## 🚀 운영 환경 설정

### 시스템 요구사항

#### 하드웨어
- **CPU**: 최소 4 코어, 권장 8 코어
- **메모리**: 최소 8GB, 권장 16GB
- **디스크**: 최소 100GB SSD
- **네트워크**: 1Gbps 이상

#### 소프트웨어
- **OS**: Ubuntu 20.04 LTS 또는 CentOS 8
- **Python**: 3.8 이상
- **MongoDB**: 4.4 이상
- **OpenSearch**: 1.0 이상

### 환경 변수 설정

```bash
# /etc/environment 또는 ~/.bashrc
export MONGODB_URI="mongodb://mongo-cluster:27017/recommendation"
export OPENSEARCH_HOST="opensearch-cluster:9200"
export OPENSEARCH_USERNAME="admin"
export OPENSEARCH_PASSWORD="secure_password"
export PORTFOLIO_API_URL="https://api.internal.com/portfolio"
export PORTFOLIO_API_KEY="your_api_key"
export LOG_LEVEL="INFO"
export BATCH_SIZE="1000"
export MAX_WORKERS="4"
```

## 📅 배치 스케줄링

### Cron 설정

```bash
# /etc/crontab 또는 crontab -e

# 매일 오전 2시에 후보 생성 배치 실행
0 2 * * * /opt/SimpleRS/scripts/run_batch_production.sh >> /var/log/batch/candidate_generation.log 2>&1

# 매주 일요일 오전 3시에 전체 재생성
0 3 * * 0 /opt/SimpleRS/scripts/run_full_regeneration.sh >> /var/log/batch/full_regen.log 2>&1

# 매시간 헬스 체크
0 * * * * /opt/SimpleRS/scripts/health_check.sh >> /var/log/batch/health.log 2>&1
```

### Systemd 서비스 설정

```ini
# /etc/systemd/system/batch-candidate-generation.service
[Unit]
Description=SimpleRS Candidate Generation Batch
After=network.target mongodb.service opensearch.service

[Service]
Type=oneshot
User=batch
Group=batch
WorkingDirectory=/opt/SimpleRS
Environment=PYTHONPATH=/opt/SimpleRS
ExecStart=/opt/SimpleRS/venv/bin/python batch/candidate_generation.py
StandardOutput=journal
StandardError=journal
TimeoutStartSec=3600

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 등록 및 활성화
sudo systemctl daemon-reload
sudo systemctl enable batch-candidate-generation.service

# 수동 실행
sudo systemctl start batch-candidate-generation.service

# 상태 확인
sudo systemctl status batch-candidate-generation.service
```

## 📊 모니터링

### 1. 시스템 메트릭

#### CPU 및 메모리 모니터링

```bash
# 실시간 모니터링
htop

# 배치 프로세스 모니터링
ps aux | grep candidate_generation

# 메모리 사용량 확인
free -h
```

#### 디스크 사용량

```bash
# 디스크 사용량 확인
df -h

# 로그 파일 크기 확인
du -sh /var/log/batch/

# 임시 파일 정리
find /tmp -name "candidate_results_*" -mtime +7 -delete
```

### 2. 애플리케이션 메트릭

#### 배치 실행 상태

```bash
# 최근 배치 실행 로그 확인
tail -f /var/log/batch/candidate_generation.log

# 에러 로그 검색
grep -i error /var/log/batch/candidate_generation.log | tail -20

# 성공/실패 통계
grep "BATCH PROCESS COMPLETED" /var/log/batch/candidate_generation.log | wc -l
grep "BATCH PROCESS FAILED" /var/log/batch/candidate_generation.log | wc -l
```

#### 성능 메트릭

```bash
# 실행 시간 분석
grep "Total duration" /var/log/batch/candidate_generation.log | tail -10

# 처리된 사용자 수 확인
grep "Processed.*users with candidates" /var/log/batch/candidate_generation.log | tail -5

# API 응답 시간 확인
grep "response time" /var/log/batch/candidate_generation.log | tail -10
```

### 3. 데이터베이스 모니터링

#### MongoDB

```javascript
// MongoDB 연결 및 상태 확인
use recommendation
db.runCommand({ping: 1})

// 컬렉션 크기 확인
db.user_candidate.stats()

// 최근 업데이트된 문서 확인
db.user_candidate.find().sort({modi_dt: -1}).limit(5)

// 인덱스 사용률 확인
db.user_candidate.getIndexes()
```

#### OpenSearch

```bash
# 클러스터 상태 확인
curl -X GET "opensearch-cluster:9200/_cluster/health?pretty"

# 인덱스 상태 확인
curl -X GET "opensearch-cluster:9200/_cat/indices/screen*?v"

# 검색 성능 확인
curl -X GET "opensearch-cluster:9200/_cat/nodes?v&h=name,heap.percent,ram.percent,cpu,load_1m"
```

### 4. 외부 API 모니터링

```bash
# 포트폴리오 API 상태 확인
curl -I https://api.internal.com/portfolio/health

# API 응답 시간 측정
time curl -s https://api.internal.com/portfolio/USER123 > /dev/null
```

## 🚨 알람 설정

### 1. 로그 기반 알람

```bash
#!/bin/bash
# scripts/check_batch_errors.sh

LOG_FILE="/var/log/batch/candidate_generation.log"
ERROR_COUNT=$(grep -c "ERROR\|CRITICAL" $LOG_FILE | tail -1)

if [ $ERROR_COUNT -gt 10 ]; then
    echo "High error count detected: $ERROR_COUNT errors in batch log"
    # Slack 알람 발송
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🚨 Batch Error Alert: '$ERROR_COUNT' errors detected"}' \
        $SLACK_WEBHOOK_URL
fi
```

### 2. 시스템 리소스 알람

```bash
#!/bin/bash
# scripts/check_system_resources.sh

# 메모리 사용률 확인
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
if [ $MEMORY_USAGE -gt 90 ]; then
    echo "High memory usage: ${MEMORY_USAGE}%"
    # 알람 발송
fi

# 디스크 사용률 확인
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
    echo "High disk usage: ${DISK_USAGE}%"
    # 알람 발송
fi
```

### 3. 배치 실행 실패 알람

```bash
#!/bin/bash
# scripts/check_batch_completion.sh

LAST_SUCCESS=$(grep "BATCH PROCESS COMPLETED SUCCESSFULLY" /var/log/batch/candidate_generation.log | tail -1 | awk '{print $1" "$2}')
LAST_SUCCESS_TIMESTAMP=$(date -d "$LAST_SUCCESS" +%s)
CURRENT_TIMESTAMP=$(date +%s)
HOURS_SINCE_SUCCESS=$(( ($CURRENT_TIMESTAMP - $LAST_SUCCESS_TIMESTAMP) / 3600 ))

if [ $HOURS_SINCE_SUCCESS -gt 25 ]; then
    echo "Batch has not completed successfully for $HOURS_SINCE_SUCCESS hours"
    # 긴급 알람 발송
fi
```

## 🔧 유지보수

### 1. 로그 로테이션

```bash
# /etc/logrotate.d/batch-logs
/var/log/batch/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 batch batch
    postrotate
        systemctl reload rsyslog > /dev/null 2>&1 || true
    endrotate
}
```

### 2. 데이터베이스 유지보수

#### MongoDB

```javascript
// 인덱스 재구성 (월 1회)
db.user_candidate.reIndex()

// 오래된 데이터 정리 (필요시)
db.user_candidate.deleteMany({
    "modi_dt": {
        $lt: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000)  // 90일 이전
    }
})

// 컬렉션 통계 업데이트
db.runCommand({collStats: "user_candidate"})
```

#### OpenSearch

```bash
# 인덱스 최적화 (주 1회)
curl -X POST "opensearch-cluster:9200/screen/_forcemerge?max_num_segments=1"

# 오래된 인덱스 삭제
curl -X DELETE "opensearch-cluster:9200/screen-2024-01-*"
```

### 3. 시스템 정리

```bash
#!/bin/bash
# scripts/system_cleanup.sh

# 임시 파일 정리
find /tmp -name "candidate_results_*" -mtime +7 -delete
find /var/log/batch -name "*.log.*" -mtime +30 -delete

# 캐시 정리
echo 3 > /proc/sys/vm/drop_caches

# 디스크 사용량 보고
df -h > /var/log/batch/disk_usage_$(date +%Y%m%d).log
```

## 🚨 장애 대응

### 1. 일반적인 장애 시나리오

#### 배치 실행 실패

```bash
# 1. 로그 확인
tail -100 /var/log/batch/candidate_generation.log

# 2. 프로세스 상태 확인
ps aux | grep candidate_generation

# 3. 시스템 리소스 확인
free -h
df -h

# 4. 데이터베이스 연결 확인
python -c "from batch.utils.db_manager import get_mongo_db; print(get_mongo_db().admin.command('ping'))"

# 5. 수동 재실행
cd /opt/SimpleRS
./scripts/run_batch_production.sh
```

#### MongoDB 연결 실패

```bash
# 1. MongoDB 서비스 상태 확인
systemctl status mongodb

# 2. 연결 테스트
mongo --eval "db.runCommand({ping: 1})"

# 3. 로그 확인
tail -50 /var/log/mongodb/mongod.log

# 4. 서비스 재시작 (필요시)
sudo systemctl restart mongodb
```

#### OpenSearch 연결 실패

```bash
# 1. OpenSearch 서비스 상태 확인
systemctl status opensearch

# 2. 클러스터 상태 확인
curl -X GET "localhost:9200/_cluster/health?pretty"

# 3. 로그 확인
tail -50 /var/log/opensearch/opensearch.log

# 4. 서비스 재시작 (필요시)
sudo systemctl restart opensearch
```

#### 외부 API 연결 실패

```bash
# 1. 네트워크 연결 확인
ping api.internal.com
telnet api.internal.com 443

# 2. API 응답 확인
curl -I https://api.internal.com/portfolio/health

# 3. DNS 확인
nslookup api.internal.com

# 4. 방화벽 확인
iptables -L | grep 443
```

### 2. 긴급 대응 절차

#### 1단계: 즉시 대응

```bash
# 배치 프로세스 중단 (필요시)
pkill -f candidate_generation

# 시스템 리소스 확인
htop
iotop

# 긴급 알람 발송
echo "🚨 URGENT: Batch system failure detected" | \
    curl -X POST -H 'Content-type: application/json' \
    --data-binary @- $SLACK_WEBHOOK_URL
```

#### 2단계: 원인 분석

```bash
# 상세 로그 수집
mkdir -p /tmp/incident_$(date +%Y%m%d_%H%M%S)
cp /var/log/batch/*.log /tmp/incident_*/
dmesg > /tmp/incident_*/dmesg.log
free -h > /tmp/incident_*/memory.log
df -h > /tmp/incident_*/disk.log
```

#### 3단계: 복구 작업

```bash
# 서비스 재시작
sudo systemctl restart mongodb
sudo systemctl restart opensearch

# 배치 재실행
cd /opt/SimpleRS
./scripts/run_batch_production.sh --force-restart

# 결과 확인
tail -f /var/log/batch/candidate_generation.log
```

### 3. 데이터 복구

#### MongoDB 데이터 복구

```bash
# 백업에서 복구
mongorestore --host localhost:27017 --db recommendation /backup/mongodb/latest/

# 특정 컬렉션만 복구
mongorestore --host localhost:27017 --db recommendation --collection user_candidate /backup/mongodb/latest/recommendation/user_candidate.bson
```

#### 폴백 파일에서 복구

```python
# scripts/restore_from_fallback.py
import json
from batch.utils.db_manager import get_mongo_db, save_results

# 폴백 파일 로드
with open('candidate_results_20240115_020000.json', 'r') as f:
    fallback_data = json.load(f)

# MongoDB에 저장
db = get_mongo_db()
save_results(fallback_data, db)
```

## 📈 성능 튜닝

### 1. 데이터베이스 최적화

#### MongoDB 인덱스 최적화

```javascript
// 복합 인덱스 생성
db.user_candidate.createIndex({"cust_no": 1, "modi_dt": -1})

// 인덱스 사용률 확인
db.user_candidate.find({"cust_no": "USER123"}).explain("executionStats")

// 느린 쿼리 프로파일링
db.setProfilingLevel(2, {slowms: 100})
db.system.profile.find().sort({ts: -1}).limit(5)
```

#### OpenSearch 최적화

```bash
# 샤드 설정 최적화
curl -X PUT "localhost:9200/screen/_settings" -H 'Content-Type: application/json' -d'
{
  "index": {
    "number_of_replicas": 1,
    "refresh_interval": "30s"
  }
}'

# 매핑 최적화
curl -X PUT "localhost:9200/screen/_mapping" -H 'Content-Type: application/json' -d'
{
  "properties": {
    "1d_returns": {"type": "float", "index": true},
    "country": {"type": "keyword"},
    "shrt_code": {"type": "keyword"}
  }
}'
```

### 2. 애플리케이션 최적화

#### 메모리 사용량 최적화

```python
# 배치 크기 조정
OPTIMAL_BATCH_SIZE = 500  # 메모리 사용량에 따라 조정

# 가비지 컬렉션 강제 실행
import gc
gc.collect()

# 메모리 프로파일링
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 메모리 사용량 모니터링
    pass
```

#### 병렬 처리 최적화

```python
# 워커 수 조정
import multiprocessing
optimal_workers = min(multiprocessing.cpu_count(), 8)

# Dask 설정 최적화
from dask import config
config.set({'distributed.worker.memory.target': 0.8})
config.set({'distributed.worker.memory.spill': 0.9})
```

### 3. 네트워크 최적화

```bash
# TCP 설정 최적화
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 87380 16777216' >> /etc/sysctl.conf
sysctl -p

# 연결 풀 크기 최적화
export MONGODB_MAX_POOL_SIZE=50
export OPENSEARCH_MAX_CONNECTIONS=20
```

## 📋 체크리스트

### 일일 점검

- [ ] 배치 실행 성공 여부 확인
- [ ] 시스템 리소스 사용률 확인
- [ ] 에러 로그 검토
- [ ] 데이터베이스 연결 상태 확인
- [ ] 외부 API 응답 시간 확인

### 주간 점검

- [ ] 성능 메트릭 분석
- [ ] 로그 파일 크기 확인
- [ ] 데이터베이스 인덱스 성능 확인
- [ ] 백업 상태 확인
- [ ] 보안 업데이트 확인

### 월간 점검

- [ ] 전체 시스템 성능 리뷰
- [ ] 용량 계획 검토
- [ ] 장애 대응 절차 테스트
- [ ] 문서 업데이트
- [ ] 팀 교육 및 지식 공유

이 운영 가이드를 따라 시스템을 안정적으로 운영할 수 있습니다.