#!/bin/bash
echo "=============================="
echo " Jacob AI 동료용 설치 가이드"
echo "=============================="

echo "1. Python 패키지 설치..."
pip3 install fastapi uvicorn requests python-dotenv jinja2 aiofiles httpx \
    --break-system-packages 2>/dev/null || \
pip install fastapi uvicorn requests python-dotenv jinja2 aiofiles httpx

echo "2. .env 파일 확인..."
if [ ! -f .env ]; then
    echo "GOOGLE_SHEETS_API_KEY=" > .env
    echo ".env 파일 생성됨 — GOOGLE_SHEETS_API_KEY 값을 Jacob에게 받아서 입력하세요"
fi

echo "3. 시스템 시작..."
sh start-all.sh

echo ""
echo "=============================="
echo " 완료! 브라우저: http://localhost:8000"
echo "=============================="
