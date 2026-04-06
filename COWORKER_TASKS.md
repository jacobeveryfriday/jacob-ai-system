# Coworker Tasks — KPI 집계봇 설정 가이드

## 1. Slack Bot Token 설정

KPI 리포트를 Slack 채널에 자동 발송하기 위해 Bot Token이 필요합니다.

### 설정 순서

1. [Slack API](https://api.slack.com/apps) 에서 새 앱 생성
2. **OAuth & Permissions** → Bot Token Scopes 추가:
   - `chat:write` — 메시지 발송
   - `chat:write.public` — 공개 채널 발송 (초대 없이)
3. 앱을 워크스페이스에 설치
4. **Bot User OAuth Token** (`xoxb-...`) 복사
5. `.env` 파일에 추가:

```env
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=#kpi-daily
```

### 기존 Webhook 방식 (폴백)

Bot Token이 없으면 Incoming Webhook으로 폴백합니다:

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx
```

> Bot Token 방식을 권장합니다. 채널 변경, Block Kit 등 고급 기능 사용 가능.

---

## 2. Google Sheets API Key 설정

Google Sheets에서 KPI 원본 데이터를 자동 수집하기 위한 설정입니다.

### 설정 순서

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 선택 (또는 새 프로젝트 생성)
3. **APIs & Services → Library** → "Google Sheets API" 검색 → 활성화
4. **APIs & Services → Credentials** → **Create Credentials → API Key**
5. 생성된 API Key 복사
6. (권장) API Key 제한 설정:
   - **Application restrictions**: IP 주소 제한
   - **API restrictions**: Google Sheets API만 허용
7. `.env` 파일에 추가:

```env
GOOGLE_SHEETS_API_KEY=AIza...your-key-here
GOOGLE_SHEETS_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
GOOGLE_SHEETS_RANGE=KPI!A1:Z100
```

### 스프레드시트 공유 설정

- API Key 방식은 **공개 읽기 권한**이 필요합니다
- 스프레드시트 → 공유 → "링크가 있는 모든 사용자" → **뷰어** 권한 설정

---

## 3. 환경변수 전체 목록 (.env)

```env
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#kpi-daily
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...   # 폴백용

# Google Sheets
GOOGLE_SHEETS_API_KEY=AIza...
GOOGLE_SHEETS_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
GOOGLE_SHEETS_RANGE=KPI!A1:Z100

# 스케줄러
KPI_CRON_HOUR=9
KPI_CRON_MINUTE=0
TIMEZONE=Asia/Seoul
```

---

## 4. 검증 체크리스트

- [ ] `SLACK_BOT_TOKEN` 설정 후 `POST /api/slack/send` 로 테스트 메시지 발송
- [ ] `GOOGLE_SHEETS_API_KEY` 설정 후 스프레드시트 데이터 읽기 확인
- [ ] `POST /api/kpi/run` 으로 전체 파이프라인 수동 실행 확인
- [ ] Slack 채널에 비교표 리포트 정상 수신 확인
