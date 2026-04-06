#!/bin/bash
# 외부 공유 URL 생성 — 설치 불필요 (SSH 내장 사용)
# Claude Code 터미널에서 실행 가능

echo ""
echo "🌐 외부 공유 URL 생성 중..."
echo ""

# 대시보드 확인
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "대시보드 시작 중..."
    cd ~/jacob-ai-system/dashboard && python3 main.py &
    sleep 3
fi

# 방법 1: localhost.run (SSH 기반, 설치 불필요)
echo "SSH 터널 연결 중... (localhost.run)"
echo "아래 https:// 주소가 동료에게 보낼 URL입니다"
echo ""
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run 2>&1
