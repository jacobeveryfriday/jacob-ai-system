"""리뷰 모니터링봇 — Mili Mili"""
import json
import os
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from collections import Counter

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="리뷰 모니터링")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "reviews.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

NEGATIVE_KEYWORDS = ["환불", "효과없음", "트러블", "자극", "가려움", "발진", "알레르기", "배송", "파손", "가품", "짝퉁", "냄새"]
PRODUCTS = ["500달톤 히알루론산 세럼", "500달톤 콜라겐 크림", "500달톤 비타민C 앰플", "500달톤 레티놀 에센스", "500달톤 나이아신아마이드 토너"]
PLATFORMS = ["쿠팡", "올리브영", "라자다"]

def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def detect_keywords(content: str) -> List[str]:
    return [kw for kw in NEGATIVE_KEYWORDS if kw in content]

def generate_response(review: dict) -> str:
    rating = review.get("rating", 5)
    keywords = review.get("keywords_detected", [])
    product = review.get("product_name", "제품")
    reviewer = review.get("reviewer", "고객")

    if rating <= 2:
        base = f"{reviewer}님, 불편을 드려 진심으로 죄송합니다.\n\n"
        if "트러블" in keywords or "자극" in keywords or "가려움" in keywords or "발진" in keywords or "알레르기" in keywords:
            base += "피부 민감 반응에 대해 매우 걱정됩니다. 개인 피부 타입에 따라 반응이 다를 수 있으며, 즉시 사용을 중단하시고 피부과 상담을 권장드립니다.\n\n밀리밀리 고객센터(1544-XXXX)로 연락 주시면 교환/환불 및 피부 상담을 도와드리겠습니다."
        elif "환불" in keywords:
            base += "구매에 만족하지 못하셨다니 안타깝습니다. 고객센터(1544-XXXX)로 연락 주시면 신속하게 환불 처리 도와드리겠습니다."
        elif "배송" in keywords or "파손" in keywords:
            base += "배송/포장 관련 불편을 드려 죄송합니다. 고객센터(1544-XXXX)로 사진과 함께 접수해주시면 즉시 재발송 처리해드리겠습니다."
        else:
            base += f"{product}의 사용 경험이 기대에 미치지 못해 죄송합니다. 구체적인 개선을 위해 고객센터로 상세 내용을 공유해주시면 감사하겠습니다."
        return base
    elif rating == 3:
        return f"{reviewer}님, 솔직한 리뷰 감사합니다.\n\n말씀해주신 부분은 R&D팀에 전달하여 제품 개선에 적극 반영하겠습니다. 500달톤 기술의 효과를 최대화하는 사용법(세안 후 토너 → 소량 도포 → 가볍게 두드리기)도 참고해주세요.\n\n더 나은 제품으로 보답하겠습니다. 감사합니다."
    elif rating >= 4 and keywords:
        concern = ", ".join(keywords)
        return f"{reviewer}님, 좋은 평가 감사합니다!\n\n말씀하신 {concern} 관련 부분은 확인 후 개선하겠습니다. 밀리밀리의 500달톤 저분자 기술이 더 좋은 결과를 드릴 수 있도록 노력하겠습니다."
    else:
        return f"{reviewer}님, 밀리밀리를 사랑해주셔서 감사합니다! 💕\n\n{product}의 500달톤 저분자 성분이 {reviewer}님 피부에 좋은 변화를 드리고 있다니 기쁩니다. 꾸준한 사용으로 더 큰 효과를 경험하실 수 있어요!\n\n다음 구매 시 사용 가능한 10% 할인 쿠폰을 드립니다: THANKYOU10"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/reviews")
async def list_reviews(platform: str = "", min_rating: int = 0, max_rating: int = 5, keyword: str = ""):
    data = load_data()
    if platform:
        data = [d for d in data if d.get("platform") == platform]
    data = [d for d in data if min_rating <= d.get("rating", 5) <= max_rating]
    if keyword:
        data = [d for d in data if keyword.lower() in d.get("content", "").lower()]
    return data

@app.post("/api/reviews")
async def add_review(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    body["keywords_detected"] = detect_keywords(body.get("content", ""))
    body["response_draft"] = generate_response(body)
    body.setdefault("response_status", "pending")
    body["created_at"] = datetime.now().isoformat()
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.post("/api/reviews/csv")
async def upload_csv(request: Request):
    body = await request.json()
    rows = body.get("rows", [])
    data = load_data()
    for row in rows:
        row["id"] = str(uuid.uuid4())[:8]
        row["keywords_detected"] = detect_keywords(row.get("content", ""))
        row["response_draft"] = generate_response(row)
        row.setdefault("response_status", "pending")
        row["created_at"] = datetime.now().isoformat()
        data.append(row)
    save_data(data)
    return {"status": "ok", "count": len(rows)}

@app.get("/api/reviews/{review_id}")
async def get_review(review_id: str):
    for r in load_data():
        if r["id"] == review_id:
            return r
    return {"error": "not found"}

@app.post("/api/reviews/{review_id}/response")
async def gen_response(review_id: str):
    data = load_data()
    for r in data:
        if r["id"] == review_id:
            r["response_draft"] = generate_response(r)
            save_data(data)
            return {"response": r["response_draft"]}
    return {"error": "not found"}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    by_platform = {}
    all_keywords = []
    for r in data:
        p = r.get("platform", "기타")
        if p not in by_platform:
            by_platform[p] = {"count": 0, "total_rating": 0, "urgent": 0}
        by_platform[p]["count"] += 1
        by_platform[p]["total_rating"] += r.get("rating", 0)
        if r.get("rating", 5) <= 3:
            by_platform[p]["urgent"] += 1
        all_keywords.extend(r.get("keywords_detected", []))
    for p in by_platform:
        cnt = by_platform[p]["count"]
        by_platform[p]["avg_rating"] = round(by_platform[p]["total_rating"] / cnt, 1) if cnt else 0
    keyword_freq = dict(Counter(all_keywords).most_common(10))
    urgent_count = sum(1 for r in data if r.get("rating", 5) <= 3)
    return {"by_platform": by_platform, "keyword_freq": keyword_freq, "total": len(data), "urgent": urgent_count}

@app.get("/api/alerts")
async def get_alerts():
    data = load_data()
    return [r for r in data if r.get("rating", 5) <= 3 or r.get("keywords_detected")]

@app.get("/api/insights")
async def get_insights():
    data = load_data()
    negatives = [r for r in data if r.get("rating", 5) <= 3]
    all_kw = []
    for r in negatives:
        all_kw.extend(r.get("keywords_detected", []))
    freq = Counter(all_kw).most_common(5)
    insights = []
    if freq:
        insights.append(f"부정 리뷰에서 가장 많이 언급된 키워드: {', '.join(k for k,v in freq)}")
    skin_issues = sum(1 for k,v in freq if k in ["트러블","자극","가려움","발진","알레르기"])
    if skin_issues:
        insights.append("피부 반응 관련 이슈가 다수 감지됨 → R&D팀 성분 안전성 재검토 권장")
    shipping = sum(1 for k,v in freq if k in ["배송","파손"])
    if shipping:
        insights.append("배송/포장 관련 불만 감지 → 물류 파트너 품질 점검 권장")
    return {"insights": insights, "negative_count": len(negatives), "keyword_frequency": dict(freq)}

if __name__ == "__main__":
    import uvicorn
    print("⭐ 리뷰 모니터링 시작 → http://localhost:8007")
    uvicorn.run(app, host="0.0.0.0", port=8007)
