# 08liter Global Operations Master v1

## Company
- 08liter Global: Influencer marketing (140M+ creators, 30K+ brand campaigns)
- Mili Mili: K-beauty brand
- Dashboard: https://dashboard-production-b2bd.up.railway.app/
- GitHub: jacobeveryfriday/jacob-ai-system

## KPI Targets (Monthly)
| Metric | Target |
|--------|--------|
| Revenue | 500M KRW |
| Contracts | 100 |
| Avg price | 5M KRW |
| Daily inbound | 100 |
| Daily valid DB | 30 |
| CPA | Under 10K KRW |
| Active influencers | 1,000+ per country |

## Email Templates
| Code | Target | Lang | Subject |
|------|--------|------|---------|
| Pitch-A | Brand | KR | Category success story hook |
| Pitch-B | Brand | KR | April promo urgent |
| Pitch-C | Brand | KR | Competitor hook |
| Luna-KR-A | KR influencer | KR | Brand + terms direct |
| Luna-KR-B | KR influencer | KR | Revenue case + limited hook |
| Luna-US-A | US influencer | EN | K-Beauty brand offer |
| Luna-US-B | US influencer | EN | Revenue case hook |

## Auto-Reply Scenarios
| Type | Keywords | Action |
|------|----------|--------|
| 1 Meeting | yes, when, available | Send meeting link |
| 2 Info | what, cost, price | Send service guide |
| 3 Later | later, busy, review | 3-week followup |
| 4 Reject | no need, pass | Polite close |

## Send Rules
- Send during recipient local business hours (09-18)
- KR -> Korean / US,CA -> English / JP -> Japanese
- No weekends, no local holidays
- KST conversion: KR 09-18 / US-ET 23-08 / US-PT 02-11 / MY 08-17

## Google Sheets
| Env Var | Tab | Purpose |
|---------|-----|---------|
| SHEET_TAB_CONTRACT | 계산서발행 | Revenue |
| SHEET_TAB_INBOUND | 파센문의 | Inbound DB |
| SHEET_TAB_PITCH | 피치_클로드 | Pitch send DB |
| SHEET_TAB_LUNA | 루나_클로드 | Luna send DB |
| SHEET_TAB_SOPHIE | 소피_클로드 | Sophie data |

## Known Issues & Fixes
| Problem | Cause | Fix |
|---------|-------|-----|
| Korean email garbled | ensure_ascii=True | ensure_ascii=False |
| Sheet data 0 | Tab name encoding | Env var tab names |
| Today data 0 | UTC/KST mismatch | KST timezone |
| Dashboard fetch error | res.json() | res.text()+JSON.parse() |
| Goals not saved | Hardcoded | goals.json |
| Kyle Korean garbled | Python->JS | Frontend hardcode |

## Design
- McKinsey style: #1a1a1a, Helvetica Neue, data-driven
- Buttons: Black bg + white text
- Consistent across dashboard, email, deck, quote

## Agents
| Agent | Email | KPI |
|-------|-------|-----|
| Kyle (lead) | kyle@08liter.com | All KPI + supervision |
| Luna (brand) | luna@08liter.com | Revenue, contracts |
| Pitch (influencer) | pitch@08liter.com | Influencer pool, outreach |
| Max (ads) | max@08liter.com | CPA, organic |
| Sophie (content) | sophie@08liter.com | SNS, followers |
| Ray (finance) | ray@08liter.com | Tax invoices |
| Hana (CS) | hana@08liter.com | CS, renewal |
