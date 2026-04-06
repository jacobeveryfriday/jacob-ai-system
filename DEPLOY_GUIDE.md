# Jacob AI System — Railway 배포 가이드

## 사전 준비 (1회만)

### 1. Railway CLI 설치
```bash
brew install railway
```

### 2. Railway 로그인
```bash
railway login
```
브라우저가 열리면 GitHub 계정으로 로그인

---

## 배포하기

### Step 1 — 프로젝트 폴더로 이동
```bash
cd ~/jacob-ai-system
```

### Step 2 — Railway 프로젝트 초기화 (최초 1회)
```bash
railway init --name jacob-ai-system
```

### Step 3 — 환경변수 설정
.env에 있는 API 키들을 Railway에 등록:
```bash
railway variables set GOOGLE_SHEETS_API_KEY=실제값
railway variables set OPENAI_API_KEY=실제값
railway variables set SLACK_WEBHOOK_URL=실제값
```
> 참고: 값이 비어있는 키는 설정하지 않아도 됨 (더미 데이터로 자동 폴백)

### Step 4 — 배포
```bash
railway up
```

### Step 5 — 공개 URL 생성
```bash
railway domain
```
생성된 URL (예: `jacob-ai-system.up.railway.app`)을 동료에게 공유!

---

## 코드 수정 후 재배포
```bash
cd ~/jacob-ai-system
railway up
```

## GitHub 연동 자동배포 (선택)
Railway 웹 대시보드(railway.app)에서:
1. 프로젝트 선택
2. Settings → Source → Connect GitHub repo
3. 이후 `git push`만 하면 자동 배포

---

## 동료가 코드를 수정하려면

### 동료에게 보내줄 메시지:
```
1. git clone https://github.com/[계정]/jacob-ai-system.git
2. cd jacob-ai-system
3. cp .env.example .env    (API 키 입력)
4. pip install -r dashboard/requirements.txt
5. cd dashboard && uvicorn main:app --reload --port 8000
6. 브라우저에서 http://localhost:8000
```

### 수정 후 합치기:
```bash
# 동료:
git add . && git commit -m "수정내용" && git push

# Jacob:
git pull
railway up
```

---

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| 배포 성공인데 접속 안 됨 | Procfile의 `--host 0.0.0.0 --port $PORT` 확인 |
| 템플릿 못 찾음 | `cd dashboard &&` 부분이 Procfile에 있는지 확인 |
| static 파일 안 나옴 | `dashboard/static/` 폴더가 git에 포함됐는지 확인 |
| Google Sheets 데이터 안 나옴 | `railway variables set GOOGLE_SHEETS_API_KEY=값` 설정 |
| 502 Bad Gateway | `railway logs`로 에러 확인 → 주로 import 에러 |

---

## 파일 구조 (배포 관련)
```
jacob-ai-system/
├── Procfile              ← Railway 실행 명령
├── requirements.txt      ← Python 패키지 (루트)
├── railway.toml          ← Railway 배포 설정
├── .gitignore            ← git 제외 파일
├── .env                  ← 환경변수 (배포 안 됨, railway variables로 설정)
└── dashboard/
    ├── main.py           ← FastAPI 앱 (진입점)
    ├── requirements.txt  ← 대시보드 전용 패키지
    ├── templates/
    ├── static/
    └── data/
```
