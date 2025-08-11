#!/bin/bash

# 스크립트 실행 위치를 SimpleRS 디렉토리로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Candidate Generation..."
echo "Project directory: $PROJECT_DIR"

# 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR"

# Python path 설정
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 가상환경이 있다면 활성화 (선택사항)
# source venv/bin/activate

# 의존성 설치 (필요한 경우)
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running candidate generation batch..."
python -m batch.candidate_generation

echo "Candidate Generation Completed."
