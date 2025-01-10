#!/bin/bash
echo "Starting API Server..."
# 워커 1: GPU 0 사용
CUDA_VISIBLE_DEVICES=0 gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000 &

# 워커 2: GPU 1 사용
CUDA_VISIBLE_DEVICES=1 gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8001 &
