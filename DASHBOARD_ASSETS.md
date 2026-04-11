# Dashboard Assets

## Deploy
- URL: https://dashboard-production-b2bd.up.railway.app/
- Platform: Railway (auto-deploy on git push)
- Stack: Python (FastAPI) + Vanilla JS + Google Sheets API
- Entry: dashboard/main.py

## API Endpoints (50+)

### Core
- GET /health
- GET /api/sheets/health
- GET /api/kpi-summary
- GET /api/kpi-trend
- GET /api/brand-pipeline
- GET /api/brand-comparison
- GET /api/influencer-db
- GET /api/ads-performance

### Agents
- GET /api/agent-performance
- GET /api/agent-kpi-dashboard
- GET /api/agent-scoreboard
- GET /api/agent-cycle
- POST /api/agents/pitch/daily
- POST /api/agents/luna/collect-northamerica
- GET /api/agents/luna/review-northamerica

### Pitch
- POST /api/pitch/send
- POST /api/pitch/reply
- POST /api/pitch/revise
- GET /api/pitch/performance
- GET /api/send-review-email

### Luna
- POST /api/luna/send-na
- GET /api/send-luna-db-request

### Email
- POST /api/send-email
- GET /api/test-email
- GET /api/email-queue
- POST /api/email-queue/approve
- POST /api/email-queue/approve-all
- POST /api/email-queue/update
- POST /api/email-queue/delete
- POST /api/email-queue/regenerate
- GET /api/agent-auto-send
- POST /api/agent-auto-send
- GET /api/email-log
- GET /api/email-templates

### Pipeline
- POST /api/crawl/brands
- POST /api/crawl/influencers
- POST /api/generate-emails
- POST /api/generate-with-promo
- GET /api/pipeline-stats
- GET /api/outbound-dashboard
- GET /api/sheet-pipeline

### Content
- POST /api/sns-content/generate
- POST /api/sns-manual
- GET /api/sns-performance
- GET /api/sns-accounts

### Slack
- GET /api/slack/toggle
- POST /api/slack/toggle
- POST /api/slack/test
- GET /api/slack/kpi-report
- GET /api/slack/daily-brief

### External APIs
- GET /api/meta-ads
- GET /api/kakao-channel
- GET /api/kakao-b2b/messages
- GET /api/kakao-b2c/inquiries

### Settings
- GET /api/goals
- POST /api/goals
- GET /api/sheets-status
- GET /api/debug-env
- GET /api/checklist
- POST /api/checklist
- POST /api/checklist/add

### Proposals
- GET /api/proposals
- POST /api/proposals
- POST /api/proposals/approve
- POST /api/proposals/reject
- POST /api/proposals/edit
- POST /api/proposals/execute
- POST /api/pipeline/start

### Alerts
- GET /api/alerts-board
- POST /api/alerts-board
- POST /api/alerts-board/resolve
- GET /api/kyle-suggestions
- GET /api/performance-summary

### Auth
- GET /login
- POST /login
- GET /logout

## Environment Variables (52)
ANTHROPIC_API_KEY, DASH_USER, DASH_PASS, EMAIL_WEBHOOK_URL,
FROM_NAME_PITCH, FROM_NAME_LUNA, GOOGLE_SHEETS_API_KEY, GOOGLE_SHEETS_ID,
INBOUND_SHEET_ID, PITCH_SHEET_ID, LUNA_SHEET_ID, SOPHIE_SHEET_ID,
SHEET_TAB_CONTRACT, SHEET_TAB_INBOUND, SHEET_TAB_PITCH, SHEET_TAB_LUNA, SHEET_TAB_SOPHIE, SHEET_TAB_INFLUENCER,
SLACK_WEBHOOK_URL, SESSION_SECRET,
META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, META_INSTAGRAM_TOKEN,
KAKAO_B2B_API_KEY, KAKAO_B2C_API_KEY, KAKAO_REST_API_KEY, KAKAO_B2B_CHANNEL, KAKAO_B2C_CHANNEL,
NAVER_WORKS_SMTP_USER, NAVER_WORKS_SMTP_PASSWORD,
PITCH_FROM_EMAIL, LUNA_FROM_EMAIL, PITCH_EMAIL, LUNA_EMAIL,
KYLE_EMAIL, MAX_EMAIL, SOPHIE_EMAIL, RAY_EMAIL, HANA_EMAIL,
INSTAGRAM_B2B_ACCOUNT, INSTAGRAM_B2C_ACCOUNT, YOUTUBE_B2B_CHANNEL,
TIKTOK_B2B_ACCOUNT, TIKTOK_B2C_ACCOUNT,
NAVER_API_KEY, NAVER_SECRET_KEY, NAVER_CUSTOMER_ID,
GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_REFRESH_TOKEN

## Completed Features
1. Google Sheets real-time integration (4 sheets, 5+ tabs)
2. Revenue/contract KPI dashboard with McKinsey design
3. 7 AI agent system (Kyle/Luna/Pitch/Max/Sophie/Ray/Hana)
4. Email outreach pipeline (GAS webhook -> Naver Works SMTP)
5. CEO approval queue (email reply detection via GAS)
6. Pitch templates A/B/C (Korean) + A_EN/B_EN (English)
7. Luna North America influencer collection
8. Agent performance tracking (agent_performance.json)
9. Benchmarks comparison (benchmarks.json)
10. Token usage tracking per agent
11. Email quality check before send
12. Business hours enforcement per country
13. Slack integration (toggle on/off)
14. Chat widget (floating button)
15. Monthly goals management (goals.json)
16. Cache warming + background refresh (10min)
17. GZip compression middleware
18. Sheet tab names via environment variables
19. Encoding-safe templates (pitch_templates.py)
20. Daily auto-proposals for all agents
