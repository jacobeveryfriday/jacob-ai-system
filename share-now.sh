#!/bin/bash
# ============================================
#  Jacob AI 대시보드 — 즉시 인터넷 공유
#  사용법: sh share-now.sh
#  계정 불필요 / 설치 자동 / 1분 완료
# ============================================

echo ""
echo "🚀 대시보드 인터넷 공유 시작..."
echo ""

# 대시보드가 실행 중인지 확인
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "⚠️  대시보드가 실행 중이 아닙니다."
    echo "   먼저 다른 터미널에서 실행하세요:"
    echo "   cd ~/jacob-ai-system/dashboard && python3 main.py"
    echo ""
    echo "   또는 전체 시스템:"
    echo "   sh ~/jacob-ai-system/start-all.sh"
    echo ""
    read -p "   대시보드를 자동으로 시작할까요? (y/n): " yn
    if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
        echo "   대시보드 시작 중..."
        cd "$(dirname "$0")/dashboard" && python3 main.py &
        sleep 3
    else
        exit 1
    fi
fi

echo "✅ 대시보드 실행 확인 (localhost:8000)"
echo ""

# 방법 1: cloudflared (가장 안정적, 계정 불필요)
if command -v cloudflared &> /dev/null; then
    echo "🌐 Cloudflare Tunnel로 공유 중..."
    echo "   아래 나오는 https:// 주소를 동료에게 보내세요!"
    echo "   종료: Ctrl+C"
    echo ""
    cloudflared tunnel --url http://localhost:8000
    exit 0
fi

# 방법 2: ngrok
if command -v ngrok &> /dev/null; then
    echo "🌐 ngrok으로 공유 중..."
    echo "   아래 나오는 https:// 주소를 동료에게 보내세요!"
    echo "   종료: Ctrl+C"
    echo ""
    ngrok http 8000
    exit 0
fi

# 둘 다 없으면 cloudflared 설치
echo "📦 Cloudflare Tunnel 설치 중 (계정 불필요, 무료)..."
if command -v brew &> /dev/null; then
    brew install cloudflared
else
    # brew 없으면 직접 다운로드
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz -o /tmp/cloudflared.tgz
    tar -xzf /tmp/cloudflared.tgz -C /usr/local/bin/
    rm /tmp/cloudflared.tgz
fi

echo ""
echo "🌐 Cloudflare Tunnel로 공유 시작..."
echo "   아래 나오는 https:// 주소를 동료에게 보내세요!"
echo "   종료: Ctrl+C"
echo ""
cloudflared tunnel --url http://localhost:8000
