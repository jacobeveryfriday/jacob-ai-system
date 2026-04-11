# CLAUDE.md — jacob-ai-system

## 프로젝트 개요
- 회사: 공팔리터글로벌 (인플루언서 마케팅) + 밀리밀리 (K-뷰티)
- 대시보드: https://dashboard-production-b2bd.up.railway.app/
- GitHub: jacobeveryfriday/jacob-ai-system
- 스택: Python(Railway) + Google Sheets + GAS 웹훅 + Slack

## 에이전트 구조
| 에이전트 | 이메일 | 담당 KPI |
|---------|--------|---------|
| 카일(총괄) | kyle@08liter.com | 전체 KPI + 에이전트 감독 |
| 루나(브랜드) | luna@08liter.com | 매출·계약·파이프라인 |
| 피치(인플루언서) | pitch@08liter.com | 인플루언서 풀·발송 |
| 맥스(광고) | max@08liter.com | CPA·오가닉 리드 |
| 소피(콘텐츠) | sophie@08liter.com | SNS·팔로워 |
| 레이(경영) | ray@08liter.com | 세금계산서·입금 |
| 하나(CS) | hana@08liter.com | CS·재계약률 |

## 구글시트 연동
환경변수로만 관리 — 코드에 한국어 하드코딩 절대 금지

| 환경변수 | 값 |
|---------|-----|
| SHEET_TAB_CONTRACT | 계산서발행 |
| SHEET_TAB_INBOUND | 현황시트(수동매칭) |
| SHEET_TAB_PITCH | 피치_클로드 |
| SHEET_TAB_LUNA | 루나_클로드 |
| SHEET_TAB_SOPHIE | 소피_클로드 |

시트 ID:
- GOOGLE_SHEETS_ID: 세금계산서 (1j_3IYME...)
- INBOUND_SHEET_ID: 인바운드/피치 (1ISL7s9...)
- LUNA_SHEET_ID: 루나 (1xLkrml...)
- SOPHIE_SHEET_ID: 소피 (1FOnGv2...)

## 이메일 발송 구조
Railway → GAS 웹훅(EMAIL_WEBHOOK_URL) → Naver Works SMTP
- GAS 계정: rollpie@gmail.com
- 발신: pitch@08liter.com / luna@08liter.com
- GAS에 시안 하드코딩 방식 사용 (인코딩 문제 방지)

## 인코딩 원칙 (위반 시 데이터 깨짐)
1. 모든 json.dumps → ensure_ascii=False 필수
2. 한국어 문자열을 Python 코드에 직접 작성 금지
3. 한국어는 반드시 환경변수 또는 GAS 내부에서 관리
4. requests.post 시 Content-Type: application/json; charset=utf-8 명시

## 배포 전 필수 체크리스트
배포할 때마다 아래 4개 확인 후 railway up 실행:
1. /api/health → google_sheets: connected 확인
2. /api/kpi-summary → source: "live" + 수치 정상 확인
3. /api/pitch/performance → total_db 정상 확인
4. testEmail() 실행 → 한국어 정상 수신 확인

## KPI 목표 (2026년 4월 기준)
- 월 매출 목표: 1.6억
- 월 계약 목표: 38건
- 인플루언서 풀 목표: 155만명
- 광고 CPA 목표: 5만원 이하
- 오가닉 리드: 15건/일

## 피치 발송 원칙
- 발송 대상: 피치_클로드 탭 등록 DB만 (외부 수집 DB 제외)
- CEO 승인 후 발송 (jacob@08liter.com 회신 감지)
