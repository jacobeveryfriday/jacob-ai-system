# Jacob AI System

## 대시보드 개발 체크리스트 (반복 실수 방지)

### Google Sheets API 연동 규칙
- GOOGLE_SHEETS_API_KEY가 .env에 있는지 먼저 확인
- API 키 없으면 더미 데이터 자동 폴백 (오류 없이 작동)
- fetch_sheet() 함수는 캐시 TTL 1800초 (30분) 적용
- 연동 시트 4개:
  - SHEET_INBOUND = 1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8 (인바운드)
  - SHEET_CONTRACT = 1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q (계산서)
  - SHEET_INFLUENCER = 1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs (인플루언서)
  - SHEET_ADS = 1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU (광고)

### HTML 함수 구현 규칙
- 새 페이지 추가 시 반드시 아래 함수 구현:
  - loadXxxData() -- API 호출 및 데이터 로드
  - renderXxxTable() -- 테이블 렌더링
  - applyXxxFilter() -- 필터 적용
- showPage() 함수에 페이지별 loadXxxData() 연동 필수
- HTML element ID와 JS getElementById() ID 반드시 일치 확인
- Chart.js canvas: 반드시 position:relative; height:200px 컨테이너 사용

### 파이프라인 보드 구현 규칙
- pipeline-board element 반드시 존재 확인 후 DOM 조작
- 오류 발생 시 재시도 버튼 포함한 에러 UI 표시
- API 데이터 source 필드로 live/dummy 표시

### 인플루언서 DB 규칙
- 국가 코드: KR/US/JP/CN/MY/SG/TH/ID/VT(베트남)/VN(베트남)
- 팔로워 수: K/M 단위 파싱 -> followers_num(숫자) 저장
- 필터: country/platform/category/followers/status/search 6개
- CSV 내보내기: BOM(\uFEFF) 포함으로 한글 깨짐 방지
- 타겟 리스트: 이메일+연락처 포함 50명 미리보기 + 전체 CSV

### 사이드바 메뉴 연결 확인 방법
```
curl http://localhost:8000/api/brand-pipeline | python3 -m json.tool | head -5
curl http://localhost:8000/api/influencer-db | python3 -m json.tool | head -5
curl http://localhost:8000/api/ads-performance | python3 -m json.tool | head -5
```
source=live -> 구글시트 연동 / source=dummy -> API 키 미입력

## 매출 데이터 컬럼 확인 (2026-04-06 직접 확인)

계산서발행 탭에서 B열부터 데이터 시작
- fetch_sheet 범위: "B:U"
- 공급가액 = T열 = 인덱스 18 (B=0, C=1, ... T=18)
- 음수값(환불/취소)은 매출에서 제외
- 신규/재계약 구분: G열(idx5)
  - "신규" 포함 -> 신규
  - "확인필요" -> 제외
  - 나머지 -> 재계약

인바운드 파센문의 탭
- fetch_sheet 범위: "A:R"
- 오늘 날짜 비교: B열="YYYY.MM", C열="M/D"
- 유효DB 기준: P열(idx15) 컨택현황에 "워킹" 포함
- 헤더 스킵: 국가/주의사항/본 리스트 키워드 체크

## 공유/배포 스크립트
- 즉시 공유: sh share-now.sh (ngrok)
- 클라우드: sh deploy.sh (Railway)
- 동료 설치: sh setup-for-colleague.sh
- WiFi 공유: http://192.168.0.6:8000

## 반복 실수 방지
- 공급가액 = T열(idx18), 세액 = U열(idx19)
- 인바운드 A:R 전체 범위 (A3:R 아님 - 헤더 스킵은 코드에서 처리)
- 계산서 B:U 전체 범위 (B2:N 아님 - T열 공급가액 포함 필요)
- 음수 매출 제외 필수 (환불/취소)
- 날짜 비교: 인바운드 C열 = "M/D" 형식, 계산서 B열 = "YYYYMMDD" 형식
- python-multipart는 FastAPI request.form() 사용 시 필수 (requirements.txt에 반드시 포함)
- Railway 배포: GitHub App 설치 후에도 "GitHub Repo not found" 시 Settings에서 Disconnect → Connect Repo 재연결 필요
- 인바운드 실제 컬럼 인덱스: J(9)=유입채널, O(14)=담당자, Q(16)=컨택현황 (N/P 아님!)

## 미처리 인바운드 비즈니스 로직 (2026-04-06 확정)

정의: 금일 인바운드 중 담당자(O열) 없거나 컨택현황(Q열) 없으면 "미처리"
- 미처리: 담당자 없음 OR 컨택현황 없음 -> 즉시 대응 필요
- 처리중: 담당자 있고 컨택현황 있음 (워킹중/부적합 등)
- 유효DB: 컨택현황 = "워킹중" 포함

API 반환 필드:
- today.unhandled: 오늘 미처리 건수
- today.handled: 오늘 처리중 건수
- month.unhandled: 이번 달 미처리 누적
- unhandled_brands: 미처리 브랜드 목록 (이름/채널/사유)

UI 표시:
- 총괄KPI: 미처리 카드 (빨강, 점멸)
- 브랜드: 미처리 알림 박스 (오늘 미처리 목록)

## 날짜 파싱 반복 실수 방지 (2026-04-06 확인)

인바운드 C열 날짜 형식 2가지 혼재:
- 형식A: "4/6" or "04/06" (일반)
- 형식B: "2026-04-06 11:50..." (타임스탬프)
- 둘 다 처리 필수, 하나만 처리하면 카운트 오류

오늘 비교: date_val==today_day or date_val==today_day2 or date_val.startswith(today_iso)
이번 달: this_month in month_val, 또는 날짜에서 월 추출

파이프라인 UI 원칙:
- 카드 목록 나열 금지 -> 숫자 요약 바만 표시
- 오늘/이번달 탭 구분
- 미처리 알림은 오늘 탭에서만 표시

## 캐시 TTL 항목별 분리 (2026-04-07 적용)

CACHE_TTLS = {
    "inbound": 300,      # 5분 - 인바운드 빠른 갱신
    "contract": 3600,    # 1시간 - 계산서
    "influencer": 21600, # 6시간 - 인플루언서
    "ads": 3600,         # 1시간 - 광고
    "default": 1800,     # 30분 폴백
}

fetch_sheet() 호출 시 ttl_key 파라미터 반드시 지정

## API 엔드포인트 목록 (2026-04-07 최종)

- GET  /health              — 헬스체크 (sheets/openai/slack 상태)
- GET  /api/kpi-summary     — 총괄 KPI
- GET  /api/brand-pipeline  — 브랜드 파이프라인 (인바운드+계약서)
- GET  /api/brand-comparison — 기간별 비교표
- GET  /api/influencer-db   — 인플루언서 DB (필터 지원)
- GET  /api/ads-performance — 광고 성과
- GET  /api/sns-performance — SNS 운영 현황 (더미, API 연동 예정)
- POST /api/chat            — AI 채팅 (OpenAI GPT-4o-mini / 룰베이스 폴백)
- POST /api/slack/test      — Slack 웹훅 테스트
- GET  /api/slack/kpi-report — Slack KPI 리포트 발송
- GET  /api/sheets-status   — Google Sheets 연동 상태
- GET  /api/cache-clear     — 캐시 초기화
- GET  /api/checklist       — 체크리스트 조회
- POST /api/checklist       — 체크리스트 저장
- POST /api/checklist/add   — 체크리스트 추가

## Jacob 대표님 확인 필요 항목 (2026-04-07)

1. OPENAI_API_KEY: Railway 환경변수에 추가하면 AI 채팅 GPT-4o-mini 활성화
   - Railway Dashboard > Variables > OPENAI_API_KEY=sk-xxx 추가
2. SLACK_WEBHOOK_URL: Slack 앱에서 Incoming Webhook 생성 후 URL 추가
   - Railway Dashboard > Variables > SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx 추가
3. 날짜 파싱 4가지 포맷 대응 완료 — 오늘 인바운드 카운트 확인 부탁드립니다
4. SNS API는 Instagram/TikTok Business API 연동 시 실데이터 전환 예정

## 날짜 파싱 포맷 (2026-04-07 최종)

인바운드 C열 is_today 판단 5가지:
- "4/7" (month/day)
- "4/07" (month/day zero-padded)
- "04/7" (month zero-padded/day)
- "04/07" (both zero-padded)
- "2026-04-07..." (ISO 타임스탬프 startswith)
