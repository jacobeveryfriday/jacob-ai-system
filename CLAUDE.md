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

## Reference Docs (docs/ 폴더)
프로젝트 핵심 문서. 피치/루나 업무 시 참조:
- docs/sales-script.md — 영업 스크립트 (미팅/콜드콜)
- docs/growth-package-proposal.md — 성장 패키지 제안서
- docs/may-promotion.md — 월별 프로모션 기획
- docs/case-study-01~04.md — 성공사례 4건 (피치 이메일 개인화용)
- docs/fanclub-plan.md — 팬클럽 플랜

## Data Harvest APIs
| API | 용도 | 키 |
|-----|------|-----|
| 식약처 CsmtcsMfcrtrInfoService01 | 화장품 제조업체 BIZRNO | env: HARVEST_API_KEY |
| 공정위 MllBs_2Service | 통신판매사업자 이메일/대표자 | env: HARVEST_API_KEY |
| 국세청 odcloud nts-businessman | 사업자번호 진위검증 | env: HARVEST_API_KEY |

## Scheduled Tasks (Remote Triggers)
| ID | 주기 | 설명 |
|----|------|------|
| bizrno-join-harvest | 3시간마다 | 식약처→공정위 BIZRNO 조인 |
| daily-new-signups-harvest | 매일 07시 KST | 공정위 신규 통신판매사업자 |
| masked-email-enrichment | 4시간마다 | 마스킹 이메일 웹크롤링 보강 |
| weekly-category-rescan | 매주 일 21시 KST | 공정위+식약처 전수 재스캔 |
