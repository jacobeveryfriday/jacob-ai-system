# CLAUDE.md — jacob-ai-system

## Project
- Company: 08liter Global (influencer marketing) + Mili Mili (K-beauty)
- Dashboard: https://dashboard-production-b2bd.up.railway.app/
- Stack: Python(Railway) + Google Sheets + GAS webhook + Slack

## Principles
- Data: API or sheet. Minimize manual input.
- Processing: Claude API or rule-based. Clear logic.
- Action: Auto email/slack/sheet recording.
- Report: jacob@08liter.com + Slack simultaneously.
- Exception: 3 retries on failure -> alert -> stop.

## Agents
| Agent | Email | KPI |
|-------|-------|-----|
| Kyle (lead) | kyle@08liter.com | All KPI + agent supervision |
| Luna (brand) | luna@08liter.com | Revenue, contracts, pipeline |
| Pitch (influencer) | pitch@08liter.com | Influencer pool, outreach |
| Max (ads) | max@08liter.com | CPA, organic leads |
| Sophie (content) | sophie@08liter.com | SNS, followers |
| Ray (finance) | ray@08liter.com | Tax invoices, payments |
| Hana (CS) | hana@08liter.com | CS, renewal rate |

All agents have full data access. Difference is KPI ownership only.

## KPI Targets (2026 monthly)
| Metric | Target | Note |
|--------|--------|------|
| Monthly revenue | 500M KRW | |
| Monthly contracts | 100 | |
| Avg contract value | 5M KRW | |
| Active influencers | 1,000+ per country | 1+ transaction/month |
| Ad CPA | Under 10K KRW | Current: 30K |
| Daily inbound DB | 100 | |
| Daily valid DB | 30 | |

## Google Sheets
Tab names managed via env vars only. Never hardcode Korean in Python.

| Env Var | Tab Name |
|---------|----------|
| SHEET_TAB_CONTRACT | 계산서발행 |
| SHEET_TAB_INBOUND | 파센문의 |
| SHEET_TAB_PITCH | 피치_클로드 |
| SHEET_TAB_LUNA | 루나_클로드 |
| SHEET_TAB_SOPHIE | 소피_클로드 |

Sheet IDs:
- GOOGLE_SHEETS_ID: Tax invoices (1j_3IYME...)
- INBOUND_SHEET_ID: Inbound/Pitch (1ISL7s9...)
- LUNA_SHEET_ID: Luna (1xLkrml...)
- SOPHIE_SHEET_ID: Sophie (1FOnGv2...)

## Email
Railway -> GAS webhook (EMAIL_WEBHOOK_URL) -> Naver Works SMTP
- GAS account: rollpie@gmail.com
- From: pitch@08liter.com / luna@08liter.com
- Korean email content hardcoded in GAS (encoding safety)

## Encoding Rules (violation = data corruption)
1. json.dumps -> ensure_ascii=False always
2. Never write Korean strings directly in Python code
3. Korean -> env vars or GAS internal only
4. requests.post -> charset=utf-8 header
5. Email HTML -> GAS internal hardcoding

## Deploy Checklist (all 4 required)
1. /api/health -> google_sheets: connected
2. /api/kpi-summary -> source: "live" + numbers correct
3. /api/pitch/performance -> total_db correct
4. testEmail() -> Korean renders correctly

## Known Issues & Fixes
| Problem | Cause | Fix |
|---------|-------|-----|
| Korean garbled | ensure_ascii=True | ensure_ascii=False |
| Sheet data 0 | Tab name encoding mismatch | Env var tab names |
| Today data 0 | UTC/KST mismatch | KST timezone |
| Dashboard fetch error | res.json() failure | res.text()+JSON.parse() |

## Pitch Outreach Rules
- DB source: Only from pitch_claude tab (no external)
- CEO approval required before any send (jacob@ reply detection)
