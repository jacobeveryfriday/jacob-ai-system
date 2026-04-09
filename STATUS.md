# STATUS.md -- API 연동 및 외부 서비스 상태

> 마지막 업데이트: 2026-04-09

## API 연동 상태

| 서비스 | 상태 | 비고 |
|--------|------|------|
| **Google Sheets API** | ✅ 정상 | API키 설정됨, 시트 4개 연동 (인바운드/계산서/인플루언서/광고) |
| **카카오 API (B2B)** | ✅ 정상 (Redirect URI 설정 완료, 2026-04-09) | 채널: 08liter_b2b, API키 설정됨 |
| **카카오 API (B2C)** | ✅ 정상 (Redirect URI 설정 완료, 2026-04-09) | 채널: 08liter_korea, API키 설정됨 |
| **카카오 CRM (system3)** | ⚠️ 개발중 | 시뮬레이션 모드, 실제 API 연동 예정 |
| **Anthropic API** | ✅ 정상 | AI 채팅 기능용 |
| **OpenAI API** | ❌ 미설정 | Railway Variables에 OPENAI_API_KEY 추가 필요 |
| **Slack Webhook** | ❌ 미설정 | SLACK_WEBHOOK_URL 추가 필요 |
| **Slack Bot** | ❌ 미설정 | SLACK_BOT_TOKEN 추가 필요 |
| **Naver Works SMTP** | ⚠️ 부분설정 | 호스트/포트/유저 설정됨, 비밀번호는 Railway Variables에 별도 관리 |
| **Meta Ads API** | ✅ 토큰 갱신 완료 (2026-04-09) | APP_ID/계정ID/토큰 설정됨 |
| **Instagram API** | ❌ 미연동 | 계정명만 설정, Business API 연동 예정 |
| **YouTube API** | ❌ 미연동 | 채널명만 설정 |
| **TikTok API** | ❌ 미연동 | 계정명만 설정 |

## 대시보드 배포

| 항목 | 상태 | 비고 |
|------|------|------|
| Railway 배포 | ✅ 설정됨 | railway.toml 구성 완료 |
| 헬스체크 | ✅ /health | sheets/openai/slack/kakao 상태 확인 |
| 로컬 공유 | ✅ share-now.sh | ngrok 기반 |

## 변경 이력

- **2026-04-09 오후**: 매출/계약 데이터 정확성 수정 (G열 기반 신규/재계약 분류 통일), 차트 12개월 확장, 기존 대시보드 McKinsey 스타일 적용 (7개 페이지 통일)
- **2026-04-09**: STATUS.md 생성, 카카오 Redirect URI 설정 완료 반영
- **2026-04-08**: 대시보드 매출/계약 데이터 정확성 수정
- **2026-04-07**: 캐시 TTL 항목별 분리, API 엔드포인트 정리
- **2026-04-06**: 매출 데이터 컬럼 확인, 날짜 파싱 수정
