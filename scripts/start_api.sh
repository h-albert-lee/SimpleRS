#!/bin/bash
echo "Starting API Server..."
uvicorn api.main:app --host 0.0.0.0 --port 8000
