# Pitch & Luna email templates — McKinsey-style HTML + plain text fallback
# Links
PROMO_LINK = "https://buly.kr/AF24dn7"
MEETING_LINK = "https://buly.kr/1c9NOdW"
KR_DECK = "https://docs.google.com/presentation/d/1D_vUqTx3yppl3iBE2ItT4d6fcBD4lEZG/preview"
US_DECK = "https://docs.google.com/presentation/d/1N69MLPASAOq5xVd1bSimK8fDWMg8QMmF/preview"

# Monthly config (update at start of each month)
MONTHLY_CONFIG = {
    "promo_deadline": "4/30",
    "promo_month": "4월",
    "domestic_price": "200만원",
    "domestic_original": "500만원",
    "domestic_discount": "60%",
    "global_price": "500만원",
    "global_original": "1,000만원",
    "global_discount": "50%",
}

# Sender display names
SENDER_NAMES = {
    "pitch": "Pitch | 08liter(0.8L)",
    "luna": "08liter Global",
    "sophie": "Sophie | 08liter",
    "kyle": "Kyle | 08liter",
}

# ===== McKinsey-Style HTML Email Builder =====
def _wrap_html(content: str) -> str:
    return (
        '<\!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0"></head>'
        '<body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f5f5f5;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;">'
        '<tr><td align="center" style="padding:20px 0;">'
        '<table width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%;background-color:#ffffff;border-top:4px solid #1a2b4a;">'
        + content +
        '</table></td></tr></table></body></html>'
    )

def _header(title: str, sub: str = "08liter Influencer Marketing") -> str:
    return (
        '<tr><td style="padding:35px 40px 10px;">'
        f'<h1 style="font-family:Georgia,serif;color:#1a2b4a;font-size:22px;margin:0 0 5px;font-weight:normal;">{title}</h1>'
        f'<p style="font-family:Georgia,serif;color:#1a2b4a;font-size:14px;margin:0;opacity:0.7;">{sub}</p>'
        '</td></tr>'
    )

def _text(content: str) -> str:
    return (
        '<tr><td style="padding:15px 40px;">'
        f'<p style="font-family:Arial,sans-serif;color:#333333;font-size:15px;line-height:1.7;margin:0;">{content}</p>'
        '</td></tr>'
    )

def _box(content: str) -> str:
    return (
        '<tr><td style="padding:10px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f8fa;border-left:3px solid #1a2b4a;">'
        f'<tr><td style="padding:18px 22px;"><p style="font-family:Arial,sans-serif;color:#333;font-size:14px;line-height:1.8;margin:0;">{content}</p></td></tr>'
        '</table></td></tr>'
    )

def _buttons(btns: list) -> str:
    cells = ""
    for label, url in btns:
        cells += (
            f'<td style="padding:0 8px;"><a href="{url}" '
            'style="display:inline-block;background-color:#1a2b4a;color:#ffffff;'
            'font-family:Arial,sans-serif;font-size:14px;font-weight:bold;'
            f'text-decoration:none;padding:12px 28px;border-radius:4px;">{label}</a></td>'
        )
    return (
        '<tr><td style="padding:10px 40px 5px;" align="center">'
        f'<table cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>'
        '</td></tr>'
    )

def _footer(lines: list) -> str:
    text = "<br>".join(lines)
    return (
        '<tr><td style="padding:25px 0 0;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f8fa;">'
        f'<tr><td style="padding:18px 40px;"><p style="font-family:Arial,sans-serif;color:#888888;font-size:12px;line-height:1.6;margin:0;">{text}</p></td></tr>'
        '</table></td></tr>'
    )


# ===== PITCH TEMPLATES (Korean B2B) =====
def _pitch_a_html(brand: str, contact: str) -> str:
    return _wrap_html(
        _header("같은 카테고리, 다른 성과")
        + _text(
            f"안녕하세요 {contact}님,<br>"
            "공팔리터(0.8L) 피치입니다.<br>"
            "140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상"
        )
        + _box(
            "🇲🇾 말레이시아 라이브 — 2분 30초 만에 1억 매출<br>"
            "🇰🇷 국내 숏폼 1개 — 287만 조회 · 매출 +180%"
        )
        + _text(
            f"{brand}과 같은 카테고리, 경쟁사 기준의 성공사례는<br>"
            "30분 미팅 시 맞춤으로 준비해서 설명드립니다."
        )
        + _buttons([("상품소개서 보기", PROMO_LINK), ("30분 구글 미팅 예약", MEETING_LINK)])
        + _footer(["공팔리터 주니어 컨설턴트 피치", "pitch@08liter.com | 08liter.com"])
    )

def _pitch_b_html(brand: str, contact: str) -> str:
    mc = MONTHLY_CONFIG
    return _wrap_html(
        _header(f"{mc['promo_deadline']} 마감 프로모션")
        + _text(
            f"안녕하세요 {contact}님,<br>"
            "공팔리터(0.8L) 피치입니다.<br>"
            "140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상"
        )
        + _box(
            f"<strong>{mc['promo_month']} 한 달만 진행하는 프로모션</strong><br>"
            f"국내: 숏폼 100건 {mc['domestic_price']} (정가 {mc['domestic_original']} / {mc['domestic_discount']} 할인)<br>"
            f"해외: 글로벌 숏폼 100건 {mc['global_price']} (정가 {mc['global_original']} / {mc['global_discount']} 할인)<br>"
            "생성 콘텐츠 3개월간 광고 소재 무료 활용 가능"
        )
        + _text(
            f"{brand} 카테고리 기준 성공사례와<br>"
            "최적 패키지 추천은 30분 미팅에서 맞춤으로 준비해드립니다."
        )
        + _buttons([("상품소개서 보기", PROMO_LINK), ("30분 구글 미팅 예약", MEETING_LINK)])
        + _footer(["공팔리터 주니어 컨설턴트 피치", "pitch@08liter.com | 08liter.com"])
    )

def _pitch_c_html(brand: str, contact: str) -> str:
    return _wrap_html(
        _header("경쟁사는 지금 어떻게?")
        + _text(
            f"안녕하세요 {contact}님,<br>"
            "공팔리터(0.8L) 피치입니다.<br>"
            "140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상"
        )
        + _box(
            "리뷰가 없어서, 숏폼이 안 터져서, 해외 진출이 막막해서.<br>"
            "브랜드마다 고민이 다릅니다."
        )
        + _text(
            f"{brand}의 카테고리·경쟁사 기준으로 실제 성공한 캠페인 사례를<br>"
            "30분 미팅 시 직접 준비해드립니다.<br>"
            "10년간 8개국 2만여 브랜드 경험이 기반입니다."
        )
        + _buttons([("상품소개서 보기", PROMO_LINK), ("30분 구글 미팅 예약", MEETING_LINK)])
        + _footer(["공팔리터 주니어 컨설턴트 피치", "pitch@08liter.com | 08liter.com"])
    )


PITCH_TEMPLATES = {
    "A": {
        "label": "Meeting Hook",
        "subject": "{brand}, 같은 카테고리 브랜드들이 어떻게 매출을 올렸는지 궁금하지 않으세요?",
        "build_html": _pitch_a_html,
    },
    "B": {
        "label": "Promo",
        "subject": f"{MONTHLY_CONFIG['promo_deadline']} 마감 — 숏폼 100건 {MONTHLY_CONFIG['domestic_price']}, " + "{brand} 신청 가능합니다",
        "build_html": _pitch_b_html,
    },
    "C": {
        "label": "Competitor Hook",
        "subject": "{brand}, 경쟁사는 지금 어떻게 인플루언서를 쓰고 있을까요?",
        "build_html": _pitch_c_html,
    },
}


# ===== LUNA TEMPLATES (Korean Creator) =====
def _luna_kr_a_html(name: str) -> str:
    return _wrap_html(
        _header("파트너 인플루언서 한정 모집", "08liter Creator Partnership")
        + _text(
            f"안녕하세요 {name}님,<br>"
            "공팔리터(0.8L) 루나입니다.<br><br>"
            f"{name}님의 콘텐츠를 인상 깊게 보았습니다.<br>"
            "현재 카테고리별 파트너 인플루언서를 한정 모집하고 있습니다."
        )
        + _box(
            "✅ 제품 무상 제공<br>"
            "✅ 콘텐츠 방향 100% 자유<br>"
            "✅ 원고료 + 성과 수익 셰어"
        )
        + _text("관심 있으시면 편하게 답장 주세요\!")
        + _buttons([("소개서 보기", KR_DECK)])
        + _footer(["공팔리터 인플루언서 파트너십 루나", "luna@08liter.com"])
    )

def _luna_kr_b_html(name: str) -> str:
    return _wrap_html(
        _header("이번 시즌 한정 모집", "08liter Creator Partnership")
        + _text(
            f"안녕하세요 {name}님,<br>"
            "공팔리터(0.8L) 루나입니다."
        )
        + _box(
            "<strong>실제 수익 사례:</strong><br>"
            "💰 인스타 2.3만 팔로워 → 월 280만원<br>"
            "💰 틱톡 1.8만 팔로워 → 월 210만원"
        )
        + _text("이번 시즌 한정 모집입니다. 관심 있으시면 답장만 주세요\!")
        + _footer(["공팔리터 인플루언서 파트너십 루나", "luna@08liter.com"])
    )


LUNA_KR_TEMPLATES = {
    "A": {
        "label": "KR Formal",
        "subject": "{name}님, 카테고리별 파트너 인플루언서 한정 모집 안내",
        "build_html": _luna_kr_a_html,
    },
    "B": {
        "label": "KR Casual",
        "subject": "{name}님, 팔로워 2만으로 월 300만원 — 이번 시즌 한정 모집",
        "build_html": _luna_kr_b_html,
    },
}


# ===== LUNA TEMPLATES (US Creator) =====
def _luna_us_a_html(name: str) -> str:
    return _wrap_html(
        _header("K-Beauty Creator Partnership", "08liter Global")
        + _text(
            f"Hi {name},<br><br>"
            "I'm Luna from 08liter Global, Asia's largest K-beauty influencer platform."
        )
        + _box(
            "✅ Free K-beauty products shipped to you<br>"
            "✅ Content fee paid monthly<br>"
            "✅ Full creative freedom"
        )
        + _text(
            "Based on your content, you'd be a great fit.<br>"
            "Interested? Just reply to this email."
        )
        + _buttons([("View Partnership Details", US_DECK)])
        + _footer(["08liter Global — Influencer Partnership", "Luna | luna@08liter.com"])
    )

def _luna_us_b_html(name: str) -> str:
    return _wrap_html(
        _header("Limited Creator Spots", "08liter Global")
        + _text(
            f"Hi {name},<br><br>"
            "Luna from 08liter Global."
        )
        + _box(
            "<strong>Real earnings:</strong><br>"
            "💰 Instagram 23K followers → $1,800/month<br>"
            "💰 TikTok 18K followers → $1,400/month"
        )
        + _text(
            "We handle everything — brand matching, negotiation, monthly payments.<br>"
            "You just create content you love.<br><br>"
            "Limited spots this season. Interested?"
        )
        + _footer(["08liter Global — Influencer Partnership", "Luna | luna@08liter.com"])
    )


LUNA_US_TEMPLATES = {
    "A": {
        "label": "US Formal",
        "subject": "Limited Creator Partnership — K-Beauty on Amazon & TikTok Shop",
        "build_html": _luna_us_a_html,
    },
    "B": {
        "label": "US Casual",
        "subject": "How creators with 20K followers make $2,000/month — Limited spots",
        "build_html": _luna_us_b_html,
    },
}
