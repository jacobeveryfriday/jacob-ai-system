#!/bin/bash
# ============================================
#  Jacob AI System — Railway 원클릭 배포
#  사용법: sh deploy.sh
# ============================================

set -e
echo ""
echo "=============================="
echo " Jacob AI 클라우드 배포 시작"
echo "=============================="
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 1. Railway CLI 확인 & 설치 ──
if ! command -v railway &> /dev/null; then
    echo "📦 Railway CLI 설치 중..."
    if command -v brew &> /dev/null; then
        brew install railway
    else
        npm install -g @railway/cli
    fi
    echo "✅ Railway CLI 설치 완료"
fi

# ── 2. Railway 로그인 확인 ──
echo ""
echo "🔐 Railway 로그인 확인 중..."
if ! railway whoami 2>/dev/null; then
    echo "   브라우저가 열리면 GitHub 계정으로 로그인하세요."
    railway login
fi
echo "✅ 로그인 완료"

# ── 3. 프로젝트 초기화 (최초 1회) ──
echo ""
if [ ! -f ".railway/config.json" ] && [ ! -d ".railway" ]; then
    echo "🚀 Railway 프로젝트 초기화..."
    railway init --name jacob-ai-system
    echo "✅ 프로젝트 생성 완료"
else
    echo "✅ Railway 프로젝트 이미 연결됨"
fi

# ── 4. 환경변수 자동 설정 ──
echo ""
echo "🔑 환경변수 설정 중..."

# .env 파일에서 값이 있는 키만 Railway에 설정
if [ -f ".env" ]; then
    while IFS='=' read -r key value; do
        # 주석, 빈 줄, 값 없는 줄 건너뛰기
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        [[ -z "$value" ]] && continue
        # 앞뒤 공백 제거
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        if [ -n "$value" ]; then
            railway variables set "$key=$value" 2>/dev/null && \
                echo "   ✅ $key 설정됨" || \
                echo "   ⚠️  $key 설정 실패"
        fi
    done < .env
else
    echo "   ⚠️  .env 파일 없음 — 더미 데이터로 작동합니다"
fi

# 대시보드 접근 비밀번호 설정 (없으면 기본값)
echo ""
echo "🔒 대시보드 접근 비밀번호 설정..."
railway variables set "DASH_USER=jacob" 2>/dev/null
railway variables set "DASH_PASS=08liter2026" 2>/dev/null
echo "   아이디: jacob"
echo "   비밀번호: 08liter2026"
echo "   (변경하려면: railway variables set DASH_USER=새아이디)"
echo "   (비밀번호 없이 열려면: railway variables set DASH_USER= DASH_PASS=)"

# ── 5. 배포 ──
echo ""
echo "🚀 배포 시작... (1~2분 소요)"
railway up

# ── 6. 도메인 생성 ──
echo ""
echo "🌐 공개 URL 생성 중..."
DOMAIN=$(railway domain 2>/dev/null)

echo ""
echo "=============================="
echo " ✅ 배포 완료!"
echo "=============================="
echo ""
echo " 🌐 대시보드 URL: $DOMAIN"
echo " 👤 아이디:       jacob"
echo " 🔑 비밀번호:     08liter2026"
echo ""
echo " 이 URL을 동료에게 카카오톡으로 보내세요!"
echo ""
echo " 📝 코드 수정 후 재배포: railway up"
echo " 📊 로그 확인:           railway logs"
echo " ⚙️  환경변수 변경:      railway variables set KEY=VALUE"
echo "=============================="
