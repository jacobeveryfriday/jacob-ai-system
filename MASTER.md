# 08liter Global Operations Master Document v1

## Company
- 08liter Global: Influencer marketing platform
- Mili Mili: K-beauty brand
- Dashboard: https://dashboard-production-b2bd.up.railway.app/
- GitHub: jacobeveryfriday/jacob-ai-system

## KPI Targets (Monthly)
| Metric | Target |
|--------|--------|
| Revenue | 500M KRW |
| Contracts | 100 |
| Avg price | 5M KRW |
| Daily inbound DB | 100 |
| Daily valid DB | 30 |
| CPA | Under 10K KRW |
| Active influencers | 1,000+ per country |

## Email Automation Flow
```
Railway API -> GAS Webhook -> Naver Works SMTP -> Recipient
                |
                v
         GAS internal templates (Korean hardcoded)
         Variable substitution: {brand}, {contact}
```

## Agents
| Agent | Email | Role |
|-------|-------|------|
| Kyle | kyle@08liter.com | Lead - all KPI |
| Luna | luna@08liter.com | Brand sales |
| Pitch | pitch@08liter.com | Influencer outreach |
| Max | max@08liter.com | Ads - CPA |
| Sophie | sophie@08liter.com | Content - SNS |
| Ray | ray@08liter.com | Finance |
| Hana | hana@08liter.com | CS |

## Google Sheets
| Sheet | ID | Key Tabs |
|-------|----|----------|
| Tax Invoice | 1j_3IYME... | 계산서발행 |
| Inbound/Pitch | 1ISL7s9... | 파센문의, 피치_클로드 |
| Influencer | 1xLkrml... | 현황시트(수동매칭), 루나_클로드 |
| Ads/Sophie | 1FOnGv2... | 소피_클로드 |

## Encoding Rules
1. Never write Korean in Python source code
2. Use Unicode escapes or env vars for Korean strings
3. json.dumps -> ensure_ascii=False always
4. Tab names managed via env vars (TAB_CONTRACT, TAB_INBOUND, etc.)

## Deploy Checklist
1. python3 -c "import main; print('OK')"
2. git push origin main
3. Wait 90s for Railway build
4. curl /health -> google_sheets: connected
5. curl /api/kpi-summary -> revenue > 0
