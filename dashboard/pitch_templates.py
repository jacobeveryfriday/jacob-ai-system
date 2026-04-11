# Pitch & Luna email templates - Korean via Unicode escapes for encoding safety
# Links
PROMO_LINK = "https://buly.kr/AF24dn7"
MEETING_LINK = "https://buly.kr/1c9NOdW"
KR_DECK = "https://docs.google.com/presentation/d/1D_vUqTx3yppl3iBE2ItT4d6fcBD4lEZG/preview"
US_DECK = "https://docs.google.com/presentation/d/1N69MLPASAOq5xVd1bSimK8fDWMg8QMmF/preview"

PITCH_TEMPLATES = {
    "A": {
        "label": "Meeting Hook",
        "subject": "{brand}, \uac19\uc740 \uce74\ud14c\uace0\ub9ac \ube0c\ub79c\ub4dc\ub4e4\uc774 \uc5b4\ub5bb\uac8c \ub9e4\ucd9c\uc744 \uc62c\ub838\ub294\uc9c0 \uad81\uae08\ud558\uc9c0 \uc54a\uc73c\uc138\uc694?",
        "body": "\uc548\ub155\ud558\uc138\uc694 {contact}\ub2d8,\n\n\uacf5\ud314\ub9ac\ud130(0.8L) \ud53c\uce58\uc785\ub2c8\ub2e4.\n140\ub9cc \uc778\ud50c\ub8e8\uc5b8\uc11c \ub124\ud2b8\uc6cc\ud06c \u00b7 3\ub9cc\uc5ec \ube0c\ub79c\ub4dc \uce90\ud398\uc778 \uacbd\ud5d8 \u00b7 \ube0c\ub79c\ub4dc \ub9cc\uc871\ub3c4 91% \uc774\uc0c1\n\n\uc800\ud76c \ud30c\ud2b8\ub108 \ube0c\ub79c\ub4dc\ub4e4\uc758 \uc2e4\uc81c \uc131\uacfc\uc785\ub2c8\ub2e4.\n\ud83c\uddf2\ud83c\uddfe \ub9d0\ub808\uc774\uc2dc\uc544 \ub77c\uc774\ube0c \u2014 2\ubd84 30\ucd08 \ub9cc\uc5d0 1\uc5b5 \ub9e4\ucd9c\n\ud83c\uddf0\ud83c\uddf7 \uad6d\ub0b4 \uc21f\ud3fc 1\uac1c \u2014 287\ub9cc \uc870\ud68c \u00b7 \ub9e4\ucd9c +180%\n\n{brand}\uacfc \uac19\uc740 \uce74\ud14c\uace0\ub9ac, \uacbd\uc7c1\uc0ac \uae30\uc900\uc758 \uc131\uacf5\uc0ac\ub840\ub294\n30\ubd84 \ubbf8\ud305 \uc2dc \ub9de\ucda4\uc73c\ub85c \uc900\ube44\ud574\uc11c \uc124\uba85\ub4dc\ub9bd\ub2c8\ub2e4.\n\n\ud83d\udcce \uc0c1\ud488\uc18c\uac1c\uc11c: " + PROMO_LINK + "\n\ud83d\udcc5 30\ubd84 \uad6c\uae00 \ubbf8\ud305: " + MEETING_LINK + "\n\n---\n\uacf5\ud314\ub9ac\ud130 \uc8fc\ub2c8\uc5b4 \ucee8\uc124\ud134\ud2b8 \ud53c\uce58\npitch@08liter.com | 08liter.com",
    },
    "B": {
        "label": "Promo",
        "subject": "4/30 \ub9c8\uac10 \u2014 \uc21f\ud3fc 100\uac74 200\ub9cc\uc6d0, {brand} \uc2e0\uccad \uac00\ub2a5\ud569\ub2c8\ub2e4",
        "body": "\uc548\ub155\ud558\uc138\uc694 {contact}\ub2d8,\n\n\uacf5\ud314\ub9ac\ud130(0.8L) \ud53c\uce58\uc785\ub2c8\ub2e4.\n140\ub9cc \uc778\ud50c\ub8e8\uc5b8\uc11c \ub124\ud2b8\uc6cc\ud06c \u00b7 3\ub9cc\uc5ec \ube0c\ub79c\ub4dc \uce90\ud398\uc778 \uacbd\ud5d8 \u00b7 \ube0c\ub79c\ub4dc \ub9cc\uc871\ub3c4 91% \uc774\uc0c1\n\n4\uc6d4 \ud55c \ub2ec\ub9cc \uc9c4\ud589\ud558\ub294 \ud504\ub85c\ubaa8\uc158\uc785\ub2c8\ub2e4.\n\n\uad6d\ub0b4: \uc21f\ud3fc 100\uac74 200\ub9cc\uc6d0 (\uc815\uac00 500\ub9cc\uc6d0 / 60% \ud560\uc778)\n\ud574\uc678: \uae00\ub85c\ubc8c \uc21f\ud3fc 100\uac74 500\ub9cc\uc6d0 (\uc815\uac00 1,000\ub9cc\uc6d0 / 50% \ud560\uc778)\n\uc0dd\uc131 \ucf58\ud150\uce20 3\uac1c\uc6d4\uac04 \uad11\uace0 \uc18c\uc7ac \ubb34\ub8cc \ud65c\uc6a9 \uac00\ub2a5\n\n{brand} \uce74\ud14c\uace0\ub9ac \uae30\uc900 \uc131\uacf5\uc0ac\ub840\uc640\n\ucd5c\uc801 \ud328\ud0a4\uc9c0 \ucd94\ucc9c\uc740 30\ubd84 \ubbf8\ud305\uc5d0\uc11c \ub9de\ucda4\uc73c\ub85c \uc900\ube44\ud574\ub4dc\ub9bd\ub2c8\ub2e4.\n\n\ud83d\udcce 4\uc6d4 \ud504\ub85c\ubaa8\uc158 \uc0c1\uc138: " + PROMO_LINK + "\n\ud83d\udcc5 30\ubd84 \uad6c\uae00 \ubbf8\ud305: " + MEETING_LINK + "\n\n---\n\uacf5\ud314\ub9ac\ud130 \uc8fc\ub2c8\uc5b4 \ucee8\uc124\ud134\ud2b8 \ud53c\uce58\npitch@08liter.com | 08liter.com",
    },
    "C": {
        "label": "Competitor Hook",
        "subject": "{brand}, \uacbd\uc7c1\uc0ac\ub294 \uc9c0\uae08 \uc5b4\ub5bb\uac8c \uc778\ud50c\ub8e8\uc5b8\uc11c\ub97c \uc4f0\uace0 \uc788\uc744\uae4c\uc694?",
        "body": "\uc548\ub155\ud558\uc138\uc694 {contact}\ub2d8,\n\n\uacf5\ud314\ub9ac\ud130(0.8L) \ud53c\uce58\uc785\ub2c8\ub2e4.\n140\ub9cc \uc778\ud50c\ub8e8\uc5b8\uc11c \ub124\ud2b8\uc6cc\ud06c \u00b7 3\ub9cc\uc5ec \ube0c\ub79c\ub4dc \uce90\ud398\uc778 \uacbd\ud5d8 \u00b7 \ube0c\ub79c\ub4dc \ub9cc\uc871\ub3c4 91% \uc774\uc0c1\n\n\ub9ac\ubdf0\uac00 \uc5c6\uc5b4\uc11c, \uc21f\ud3fc\uc774 \uc548 \ud130\uc838\uc11c, \ud574\uc678 \uc9c4\ucd9c\uc774 \ub9c9\ub9c9\ud574\uc11c.\n\ube0c\ub79c\ub4dc\ub9c8\ub2e4 \uace0\ubbfc\uc774 \ub2e4\ub985\ub2c8\ub2e4.\n\n{brand}\uc758 \uce74\ud14c\uace0\ub9ac\u00b7\uacbd\uc7c1\uc0ac \uae30\uc900\uc73c\ub85c\n\uc2e4\uc81c \uc131\uacf5\ud55c \uce90\ud398\uc778 \uc0ac\ub840\ub97c 30\ubd84 \ubbf8\ud305 \uc2dc \uc9c1\uc811 \uc900\ube44\ud574\ub4dc\ub9bd\ub2c8\ub2e4.\n10\ub144\uac04 8\uac1c\uad6d 2\ub9cc\uc5ec \ube0c\ub79c\ub4dc \uacbd\ud5d8\uc774 \uae30\ubc18\uc785\ub2c8\ub2e4.\n\n\ud83d\udcce \uc0c1\ud488\uc18c\uac1c\uc11c: " + PROMO_LINK + "\n\ud83d\udcc5 30\ubd84 \uad6c\uae00 \ubbf8\ud305: " + MEETING_LINK + "\n\n---\n\uacf5\ud314\ub9ac\ud130 \uc8fc\ub2c8\uc5b4 \ucee8\uc124\ud134\ud2b8 \ud53c\uce58\npitch@08liter.com | 08liter.com",
    },
    "A_EN": {
        "label": "Success Story (EN)",
        "subject": "287M views from 1 short video \u2014 {brand} could be next",
        "body": "Hi {contact},\n\nOne of our partners hit 1B KRW from a 2.5-min live stream in Malaysia.\nAnother drove 287M views and +180% revenue from a single short video.\n\nCurious what works for your category? We'll prepare a custom case study for a 30-min call.\n\n\ud83d\udcce Deck: " + PROMO_LINK + "\n\ud83d\udcc5 Book a call: " + MEETING_LINK + "\n\n---\nPitch, Junior Consultant\n08liter Global\npitch@08liter.com | 08liter.com",
    },
    "B_EN": {
        "label": "Promo (EN)",
        "subject": "April only \u2014 100 short videos for 2M KRW ({brand} eligible)",
        "body": "Hi {contact},\n\nThis month only: 100 short-form videos for 2M KRW (regular 5M).\nGlobal: 100 videos for 5M KRW (regular 10M).\nAll content reusable as ad creative for 3 months.\n\n\ud83d\udcce Details: " + PROMO_LINK + "\n\ud83d\udcc5 30-min call: " + MEETING_LINK + "\n\n---\nPitch, Junior Consultant\n08liter Global\npitch@08liter.com | 08liter.com",
    },
}

LUNA_KR_TEMPLATES = {
    "A": {
        "label": "KR Formal",
        "subject": "{name}\ub2d8, \uce74\ud14c\uace0\ub9ac\ubcc4 \ud30c\ud2b8\ub108 \uc778\ud50c\ub8e8\uc5b8\uc11c \ud55c\uc815 \ubaa8\uc9d1 \uc548\ub0b4",
        "body": "\uc548\ub155\ud558\uc138\uc694 {name}\ub2d8,\n\n\uacf5\ud314\ub9ac\ud130(0.8L) \ub8e8\ub098\uc785\ub2c8\ub2e4.\n\n{name}\ub2d8\uc758 \ucf58\ud150\uce20\ub97c \uc778\uc0c1 \uae4a\uac8c \ubcf4\uc558\uc2b5\ub2c8\ub2e4.\n\ud604\uc7ac \uce74\ud14c\uace0\ub9ac\ubcc4 \ud30c\ud2b8\ub108 \uc778\ud50c\ub8e8\uc5b8\uc11c\ub97c \ud55c\uc815 \ubaa8\uc9d1\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4.\n\n\u2705 \uc81c\ud488 \ubb34\uc0c1 \uc81c\uacf5\n\u2705 \ucf58\ud150\uce20 \ubc29\ud5a5 100% \uc790\uc720\n\u2705 \uc6d0\uace0\ub8cc + \uc131\uacfc \uc218\uc775 \uc250\uc5b4\n\n\uad00\uc2ec \uc788\uc73c\uc2dc\uba74 \ud3b8\ud558\uac8c \ub2f5\uc7a5 \uc8fc\uc138\uc694!\n\n\ud83d\udcce \uc18c\uac1c\uc11c: " + KR_DECK + "\n\n---\n\uacf5\ud314\ub9ac\ud130 \uc778\ud50c\ub8e8\uc5b8\uc11c \ud30c\ud2b8\ub108\uc2ed\n\ub8e8\ub098\nluna@08liter.com",
    },
    "B": {
        "label": "KR Casual",
        "subject": "{name}\ub2d8, \ud314\ub85c\uc6cc 2\ub9cc\uc73c\ub85c \uc6d4 300\ub9cc\uc6d0 \u2014 \uc774\ubc88 \uc2dc\uc98c \ud55c\uc815 \ubaa8\uc9d1",
        "body": "\uc548\ub155\ud558\uc138\uc694 {name}\ub2d8,\n\n\uacf5\ud314\ub9ac\ud130(0.8L) \ub8e8\ub098\uc785\ub2c8\ub2e4.\n\n\uc800\ud76c \ud30c\ud2b8\ub108\ub4e4\uc758 \uc2e4\uc81c \uc218\uc775 \uc0ac\ub840\uc785\ub2c8\ub2e4:\n\ud83d\udcb0 \uc778\uc2a4\ud0c0 2.3\ub9cc \ud314\ub85c\uc6cc \u2192 \uc6d4 280\ub9cc\uc6d0\n\ud83d\udcb0 \ud2f1\ud1a1 1.8\ub9cc \ud314\ub85c\uc6cc \u2192 \uc6d4 210\ub9cc\uc6d0\n\n\uc774\ubc88 \uc2dc\uc98c \ud55c\uc815 \ubaa8\uc9d1\uc785\ub2c8\ub2e4.\n\uad00\uc2ec \uc788\uc73c\uc2dc\uba74 \ub2f5\uc7a5\ub9cc \uc8fc\uc138\uc694!\n\n\ud83d\udcce \uc18c\uac1c\uc11c: " + KR_DECK + "\n\n---\n\uacf5\ud314\ub9ac\ud130 \uc778\ud50c\ub8e8\uc5b8\uc11c \ud30c\ud2b8\ub108\uc2ed\n\ub8e8\ub098\nluna@08liter.com",
    },
}

LUNA_US_TEMPLATES = {
    "A": {
        "label": "US Formal",
        "subject": "Limited Creator Partnership \u2014 K-Beauty Brands on Amazon & TikTok Shop",
        "body": "Hi {name},\n\nI'm Luna from 08liter Global, Asia's largest K-beauty influencer platform.\n\nWe're selectively onboarding creators for paid K-beauty partnerships:\n\n\u2705 Free K-beauty products shipped to you\n\u2705 Content fee paid monthly\n\u2705 Full creative freedom\n\nBased on your content, you'd be a great fit.\nInterested? Just reply to this email.\n\n\ud83d\udcce Creator Deck: " + US_DECK + "\n\n---\n08liter Global \u2014 Influencer Partnership\nLuna\nluna@08liter.com",
    },
    "B": {
        "label": "US Casual",
        "subject": "How creators with 20K followers make $2,000/month \u2014 Limited spots open",
        "body": "Hi {name},\n\nI'm Luna from 08liter Global.\n\nReal earnings from our creator partners:\n\ud83d\udcb0 Instagram 23K followers \u2192 $1,800/month\n\ud83d\udcb0 TikTok 18K followers \u2192 $1,400/month\n\nWe handle everything \u2014 brand matching, negotiation, monthly payments.\nYou just create content you love.\n\nLimited spots this season. Interested?\n\n\ud83d\udcce Creator Deck: " + US_DECK + "\n\n---\n08liter Global \u2014 Influencer Partnership\nLuna\nluna@08liter.com",
    },
}
