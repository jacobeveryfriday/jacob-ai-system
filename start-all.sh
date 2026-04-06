#!/bin/bash
# Jacob AI System — 전체 시스템 일괄 실행
# Usage: sh start-all.sh

echo "⚡ Jacob AI Command Center 시작 중..."
echo "============================================"

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

# 각 시스템 실행 함수
start_system() {
    local name=$1
    local dir=$2
    local port=$3

    if [ -f "$BASE_DIR/$dir/main.py" ]; then
        echo "  ✅ $name (port $port) 시작..."
        cd "$BASE_DIR/$dir" && python3 main.py &
        PIDS+=($!)
        cd "$BASE_DIR"
    else
        echo "  ⚠️  $name — main.py 없음, 건너뜀"
    fi
}

# 시스템 1~7 실행
start_system "KPI 집계봇" "system1-kpi-bot" 8001
start_system "SNS 스케줄러" "system2-sns-scheduler" 8002
start_system "카카오 CRM" "system3-kakao-crm" 8003
start_system "리드 파이프라인" "system4-lead-pipeline" 8004
start_system "계약 자동화" "system5-contract-auto" 8005
start_system "광고 모니터링" "system6-ads-monitor" 8006
start_system "리뷰 모니터링" "system7-review-bot" 8007

# 잠시 대기 후 통합 대시보드 실행
sleep 2
start_system "통합 대시보드" "dashboard" 8000

echo "============================================"
echo "⚡ 전체 시스템 실행 완료!"
echo ""
echo "  🌐 통합 대시보드: http://localhost:8000"
echo "  📊 KPI 집계봇:    http://localhost:8001"
echo "  📱 SNS 스케줄러:  http://localhost:8002"
echo "  💌 카카오 CRM:    http://localhost:8003"
echo "  🆕 리드 파이프라인: http://localhost:8004"
echo "  📄 계약 자동화:   http://localhost:8005"
echo "  📣 광고 모니터링: http://localhost:8006"
echo "  ⭐ 리뷰 모니터링: http://localhost:8007"
echo ""
echo "종료: Ctrl+C"

# 브라우저 자동 열기
if command -v open &> /dev/null; then
    open "http://localhost:8000"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8000"
fi

# 종료 시 모든 프로세스 정리
cleanup() {
    echo ""
    echo "🛑 전체 시스템 종료 중..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    echo "✅ 종료 완료"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 대기
wait
