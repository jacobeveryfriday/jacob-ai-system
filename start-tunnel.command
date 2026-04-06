#!/bin/bash
# Jacob AI Dashboard - 외부 공유 터널
# 이 파일을 더블클릭하면 자동으로 외부 접속 URL이 생성됩니다

echo "============================================"
echo "  Jacob AI Dashboard - 외부 공유 시작"
echo "============================================"
echo ""

# cloudflared 설치 확인
if ! command -v cloudflared &> /dev/null; then
    echo ">> cloudflared 설치 중..."
    if command -v brew &> /dev/null; then
        brew install cloudflared
    else
        echo ">> Homebrew 없이 직접 다운로드 중..."
        curl -L -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz 2>/dev/null
        if [ $? -ne 0 ]; then
            # ARM Mac
            curl -L -o /tmp/cloudflared.tgz https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz 2>/dev/null
            cd /tmp && tar xzf cloudflared.tgz 2>/dev/null
        fi
        chmod +x /tmp/cloudflared
        export PATH="/tmp:$PATH"
    fi
fi

# 대시보드 실행 확인
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo ">> 대시보드가 실행되지 않고 있습니다."
    echo ">> 먼저 대시보드를 실행해주세요: cd dashboard && python3 -m uvicorn main:app --port 8000"
    echo ""
    read -p "대시보드 실행 후 Enter를 누르세요..."
fi

echo ""
echo ">> Cloudflare Tunnel 시작 중..."
echo ">> 아래에 나오는 URL을 동료에게 공유하세요!"
echo ">> (Ctrl+C로 종료)"
echo ""
echo "============================================"

cloudflared tunnel --url http://localhost:8000 2>&1 | while read line; do
    echo "$line"
    # URL이 나오면 강조 표시
    if echo "$line" | grep -q "https://.*trycloudflare.com"; then
        echo ""
        echo "============================================"
        echo "  공유 URL: $(echo $line | grep -oE 'https://[^ ]*trycloudflare.com[^ ]*')"
        echo "============================================"
        echo ""
    fi
done
