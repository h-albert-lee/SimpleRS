#!/bin/bash

# 프로덕션 환경에서 배치 실행을 위한 스크립트

# 스크립트 실행 위치를 SimpleRS 디렉토리로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Candidate Generation Batch Job ==="
echo "Start time: $(date)"
echo "Project directory: $PROJECT_DIR"

# 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR"

# Python path 설정
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 로그 디렉토리 생성
mkdir -p logs

# 로그 파일명 (날짜 포함)
LOG_FILE="logs/candidate_generation_$(date +%Y%m%d_%H%M%S).log"

echo "Log file: $LOG_FILE"

# 배치 실행 (로그 파일에 출력 저장)
python -m batch.candidate_generation 2>&1 | tee "$LOG_FILE"

# 실행 결과 확인
EXIT_CODE=${PIPESTATUS[0]}

echo "=== Batch Job Completed ==="
echo "End time: $(date)"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Candidate generation completed successfully"
else
    echo "❌ Candidate generation failed with exit code $EXIT_CODE"
    echo "Check log file: $LOG_FILE"
fi

exit $EXIT_CODE