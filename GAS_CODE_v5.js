// ===================================================================
// GAS Code.gs v5 — 08liter Global
// 이 파일 전체를 script.google.com Code.gs에 붙여넣고 재배포
// Deploy > "Execute as: Me" / "Who has access: Anyone"
// 배포 후 setupTriggers() 1회 실행
// ===================================================================

// ===== MONTHLY CONFIG (매달 여기만 수정) =====
var MONTHLY_CONFIG = {
  promo_deadline: '4/30',
  domestic_price: '200만원',
  domestic_original: '500만원',
  domestic_discount: '60%',
  global_price: '500만원',
  global_original: '1,000만원',
  global_discount: '50%',
  brochure_link: 'https://buly.kr/AF24dn7',
  meeting_link: 'https://buly.kr/1c9NOdW',
  creator_guide_link: 'https://buly.kr/AF24dn7'
};

// ===== PITCH TEMPLATES =====
var PITCH_TEMPLATES = {
  A: {
    subject: '{brand}, 같은 카테고리 브랜드들이 어떻게 매출을 올렸는지 궁금하지 않으세요?',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n139만+ 인플루언서 네트워크 · 20,000+ 브랜드 캠페인 경험 · 브랜드 만족도 89%\n\n저희 파트너 브랜드들의 실제 성과입니다.\n🇲🇾 말레이시아 라이브 — 2분 30초 만에 1억 매출\n🇰🇷 국내 숏폼 1개 — 287만 조회 · 매출 +180%\n\n✅ 생성된 모든 콘텐츠는 3개월간 광고 소재로 무료 활용 가능\n\n{brand}과 같은 카테고리, 경쟁사 기준의 성공사례는\n30분 미팅 시 맞춤으로 준비해서 설명드립니다.\n\n📎 상품소개서: ' + MONTHLY_CONFIG.brochure_link + '\n📅 30분 구글 미팅: ' + MONTHLY_CONFIG.meeting_link + '\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  },
  B: {
    subject: MONTHLY_CONFIG.promo_deadline + ' 마감 — 숏폼 100건 ' + MONTHLY_CONFIG.domestic_price + ', {brand} 신청 가능합니다',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n139만+ 인플루언서 네트워크 · 20,000+ 브랜드 캠페인 경험 · 브랜드 만족도 89%\n\n4월 한 달만 진행하는 프로모션입니다.\n\n국내: 숏폼 100건 ' + MONTHLY_CONFIG.domestic_price + ' (정가 ' + MONTHLY_CONFIG.domestic_original + ' / ' + MONTHLY_CONFIG.domestic_discount + ' 할인)\n해외: 글로벌 숏폼 100건 ' + MONTHLY_CONFIG.global_price + ' (정가 ' + MONTHLY_CONFIG.global_original + ' / ' + MONTHLY_CONFIG.global_discount + ' 할인)\n생성 콘텐츠 3개월간 광고 소재 무료 활용 가능\n\n🎁 4월 앵콜 특전: 구매평 체험단 + 인스타 피드 + 네이버 블로그 3개월 무제한 이용\n   (대행비 전액무료, 유저 페이백 실비만 발생)\n\n{brand} 카테고리 기준 성공사례와\n최적 패키지 추천은 30분 미팅에서 맞춤으로 준비해드립니다.\n\n📎 4월 프로모션 상세: ' + MONTHLY_CONFIG.brochure_link + '\n📅 30분 구글 미팅: ' + MONTHLY_CONFIG.meeting_link + '\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  },
  C: {
    subject: '{brand}, 경쟁사는 지금 어떻게 인플루언서를 쓰고 있을까요?',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n139만+ 인플루언서 네트워크 · 20,000+ 브랜드 캠페인 경험 · 브랜드 만족도 89%\n\n리뷰가 없어서, 숏폼이 안 터져서, 해외 진출이 막막해서, 구매평이 부족해서.\n브랜드마다 고민이 다릅니다.\n\n{brand}의 카테고리·경쟁사 기준으로\n실제 성공한 캠페인 사례를 30분 미팅 시 직접 준비해드립니다.\n10년간 8개국 2만여 브랜드 경험이 기반입니다.\n\n💡 구매평 부족? 건당 5,000원부터 실구매 리뷰를 쌓을 수 있습니다.\n\n📎 상품소개서: ' + MONTHLY_CONFIG.brochure_link + '\n📅 30분 구글 미팅: ' + MONTHLY_CONFIG.meeting_link + '\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  }
};

// ===== LUNA TEMPLATES =====
var LUNA_TEMPLATES = {
  KR_A: {
    subject: '{name}님, K-뷰티 브랜드와 함께할 크리에이터를 찾고 있습니다',
    body: '안녕하세요 {name}님,\n\n공팔리터글로벌(0.8L) 루나입니다.\n\n저희는 한국 K-뷰티 브랜드와 인플루언서를 연결하는 플랫폼입니다.\n139만+ 인플루언서 네트워크를 통해 {name}님의 채널에 맞는\n최적의 브랜드 협찬 기회를 제안드립니다.\n\n1만 팔로워부터 월 고정 수익이 가능합니다.\n팔로워 규모와 카테고리에 따른 맞춤 수익 구조를 안내드립니다.\n\n✅ 무료 제품 시딩\n✅ 유료 콘텐츠 제작 (건당 협의)\n✅ 장기 파트너십 — 월 고정 수익 보장\n\n맞춤 수익 구조를 받아보시려면 이 메일에 회신해주세요.\n\n---\n공팔리터글로벌 루나\nluna@08liter.com | 08liter.com'
  },
  KR_B: {
    subject: '{name}님, 요즘 뷰티 크리에이터들 사이에서 핫한 협찬 기회 🔥',
    body: '안녕하세요 {name}님!\n\n루나입니다 😊\n\n요즘 K-뷰티 브랜드들이 인스타/틱톡 크리에이터와의 협업에\n정말 적극적이에요!\n\n{name}님 채널 보고 연락드렸는데요,\n지금 진행 중인 캠페인 중에 딱 맞는 게 있어서요.\n\n🎁 무료 제품 + 콘텐츠 제작비 지원\n📦 한국에서 직접 발송\n💰 1만 팔로워부터 월 고정 수익 가능\n\n상세 수익 구조는 회신 시 {name}님 채널에 맞춰 안내드릴게요.\n\n관심 있으시면 편하게 답장 주세요!\n\n---\n루나 | 공팔리터글로벌\nluna@08liter.com'
  },
  US_A: {
    subject: 'K-Beauty collab opportunity for {name}',
    body: 'Hi {name},\n\nI\'m Luna from 08liter Global — a K-beauty influencer platform based in Seoul.\n\nWe work with 20,000+ beauty brands in Korea and match them with creators like you.\n\nWhat we offer our partners:\n· Free K-Beauty product seeding\n· Paid content opportunities\n· Monthly guaranteed brand collabs\n· Dedicated partnership manager\n\nFrom 10K followers, you can earn stable monthly income.\nReply for your personalized earning projection.\n\n🌸 Exclusive: K-Beauty brand Mili Mili product seeding opportunity\n   - Free product gifting for selected creators\n   - First access to new K-Beauty launches\n\nInterested? Just reply to this email.\n\n---\n08liter Global — Influencer Partnership\nLuna\nluna@08liter.com | www.08liter.com'
  },
  US_B: {
    subject: 'Steady monthly income from K-beauty collabs — interested, {name}?',
    body: 'Hi {name},\n\nI\'m Luna from 08liter Global in Seoul.\n\nInstead of one-off sponsorships, we offer long-term partnerships:\n\n· Guaranteed brand collabs per month\n· Stable monthly payment from 10K followers\n· You choose the brands you like\n· Dedicated manager (me, Luna)\n\nReply and I\'ll send your personalized earning projection\nbased on your follower count and niche.\n\n🌸 Exclusive: K-Beauty brand Mili Mili product seeding opportunity\n   - Free product gifting for selected creators\n   - First access to new K-Beauty launches\n\nContracts start from 3 months.\nWant to know more? Just reply.\n\n---\n08liter Global — Influencer Partnership\nLuna\nluna@08liter.com | www.08liter.com'
  },
  JP_A: {
    subject: '{name}さん、インフルエンサー案件のご案内です — 08liter',
    body: '{name}さん、こんにちは。\n\n08liter Global（コンパルリトグローバル）のLunaと申します。\n韓国No.1 インフルエンサーマーケティングプラットフォームです。\n\n139万+ クリエイターネットワーク · 20,000+ ブランド実績\n\nK-Beautyおよびグローバルブランドとの有料コラボレーション機会をご案内しています。\n\n✅ 1万フォロワーから安定した月収が可能\n✅ 無料製品シーディング + コンテンツ制作費支援\n✅ 長期パートナーシップ — 月額固定報酬保証\n\n📌 カテゴリー別に限定募集中です。\n\nフォロワー数とカテゴリーに合わせた収益プランをご案内いたします。\nご興味がございましたら、このメールにご返信ください。\n\n📎 クリエイターガイドブック: ' + MONTHLY_CONFIG.creator_guide_link + '\n\n---\n08liter Global — Influencer Partnership\nLuna\nluna@08liter.com | www.08liter.com'
  },
  JP_B: {
    subject: '{name}さん — K-Beautyブランドがあなたのようなクリエイターを探しています',
    body: '{name}さん、こんにちは。\n\n08liter GlobalのLunaです。\n\n現在、K-Beautyブランドが{name}さんのようなクリエイターとの\nコラボレーションパートナーを探しています。\n\n私たちが重視するのは：\n· フォロワー数よりコンテンツの質とニッチな専門性\n· ビューティー・スキンケア分野への情熱\n· オーセンティックなストーリーテリング\n\n🌸 今シーズン限定の募集枠があります\n\n月額固定報酬 + 無料製品 + コンテンツ制作費\nフォロワー規模に合わせた収益プランをご提案します。\n\nご興味がございましたら、メールにてご返信ください。\n\n📎 クリエイターデッキ: ' + MONTHLY_CONFIG.creator_guide_link + '\n\n---\n08liter Global — Influencer Partnership\nLuna\nluna@08liter.com | www.08liter.com'
  }
};

// ===== SENDER NAMES =====
var SENDER_NAMES = {
  pitch: 'Pitch | 08liter(0.8L)',
  luna: 'Luna | Mili Mili x 08liter(0.8L)',
  sophie: 'Sophie | 08liter',
  kyle: 'Kyle | 08liter'
};

// ===== McKinsey HTML Builder =====
function buildMcKinseyHtml(subject, bodyText, agent) {
  var agentColor = {pitch:'#1B2A4A', luna:'#2D4A7A', sophie:'#1A7A4C', kyle:'#333'}[agent] || '#1B2A4A';
  var bodyHtml = bodyText.replace(/\n/g, '<br>');
  return '<div style="font-family:Helvetica Neue,Arial,sans-serif;max-width:600px;margin:0 auto">'
    + '<div style="background:' + agentColor + ';padding:16px 24px;border-radius:8px 8px 0 0">'
    + '<span style="color:#fff;font-size:14px;font-weight:700">' + (SENDER_NAMES[agent] || agent) + '</span></div>'
    + '<div style="background:#f8f7f5;padding:24px;border:1px solid #e8e6e1;border-top:none;border-radius:0 0 8px 8px">'
    + '<p style="font-size:14px;color:#1a1a1a;line-height:1.8;margin:0">' + bodyHtml + '</p>'
    + '</div></div>';
}

// ===== MAIN doPost =====
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // Action: appendSheet
    if (data.action === 'appendSheet') {
      var ss = SpreadsheetApp.openById(data.sheet_id);
      var tabName = data.tab_name || (data.range ? data.range.split('!')[0] : null);
      var sheet = tabName ? ss.getSheetByName(tabName) : ss.getSheets()[0];
      if (!sheet) return _jsonResponse({status:'error', message:'Tab not found: ' + tabName});
      if (data.rows && data.rows.length > 0) {
        sheet.getRange(sheet.getLastRow()+1, 1, data.rows.length, data.rows[0].length).setValues(data.rows);
      }
      return _jsonResponse({status:'success', action:'appendSheet', rows_written: data.rows ? data.rows.length : 0, tab: tabName});
    }

    // Action: test
    if (data.action === 'test') return _jsonResponse({status:'success', action:'test'});

    var to = data.to || '';
    var agent = data.agent || 'pitch';
    var fromName = SENDER_NAMES[agent] || 'Pitch | 08liter';

    // Template mode
    if (data.template) {
      var tmpl = PITCH_TEMPLATES[data.template] || LUNA_TEMPLATES[data.template];
      if (!tmpl) return _jsonResponse({status:'error', message:'Unknown template: ' + data.template});

      var brand = data.brand || (data.vars && data.vars.brand) || '';
      var contact = data.contact || (data.vars && data.vars.contact) || brand;
      var name = data.name || (data.vars && data.vars.name) || '';

      var subject = tmpl.subject.replace(/\{brand\}/g, brand).replace(/\{contact\}/g, contact).replace(/\{name\}/g, name);
      var bodyText = tmpl.body.replace(/\{brand\}/g, brand).replace(/\{contact\}/g, contact).replace(/\{name\}/g, name);
      var htmlBody = buildMcKinseyHtml(subject, bodyText, agent);

      if (!to) return _jsonResponse({status:'error', message:'missing to'});
      GmailApp.sendEmail(to, subject, bodyText, {htmlBody: htmlBody, name: fromName, noReply: false});
      return _jsonResponse({status:'success', from: agent + '@08liter.com', to: to, template: data.template});
    }

    // Legacy mode
    var subject = data.subject || '';
    var body = data.body || '';
    var htmlBody = data.htmlBody || '';
    if (!to || !subject) return _jsonResponse({status:'error', message:'missing to or subject'});
    GmailApp.sendEmail(to, subject, body, {htmlBody: htmlBody || body, name: fromName, noReply: false});
    return _jsonResponse({status:'success', from: agent + '@08liter.com', to: to});

  } catch(err) {
    return _jsonResponse({status:'error', message: err.toString()});
  }
}

function _jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ===== CEO Approval (5분마다) =====
function checkCEOApproval() {
  var RAILWAY = 'https://dashboard-production-b2bd.up.railway.app';
  try {
    var pitchThreads = GmailApp.search('subject:(피치 검수) from:jacob is:unread', 0, 5);
    pitchThreads.forEach(function(thread) {
      var latest = thread.getMessages()[thread.getMessages().length - 1];
      var body = latest.getPlainBody().trim().substring(0, 20).toUpperCase();
      var variant = null;
      if (body.match(/^A\b/)) variant = 'A';
      else if (body.match(/^B\b/)) variant = 'B';
      else if (body.match(/^C\b/)) variant = 'C';
      if (variant) {
        UrlFetchApp.fetch(RAILWAY + '/api/pitch/send', {method:'POST', contentType:'application/json', payload:JSON.stringify({template:variant, source:'ceo_approval'})});
        latest.markRead();
      }
    });
    var lunaThreads = GmailApp.search('subject:(루나 검수) from:jacob is:unread', 0, 5);
    lunaThreads.forEach(function(thread) {
      var latest = thread.getMessages()[thread.getMessages().length - 1];
      var body = latest.getPlainBody().trim().substring(0, 20).toUpperCase();
      if (body.indexOf('APPLY') !== -1 || body.match(/KR_A|KR_B|US_A|US_B|JP_A|JP_B/)) {
        var variant = body.match(/KR_A|KR_B|US_A|US_B|JP_A|JP_B/) ? body.match(/KR_A|KR_B|US_A|US_B|JP_A|JP_B/)[0] : 'KR_A';
        UrlFetchApp.fetch(RAILWAY + '/api/luna/send-na', {method:'POST', contentType:'application/json', payload:JSON.stringify({template:variant, source:'ceo_approval'})});
        latest.markRead();
      }
    });
  } catch(e) { Logger.log('checkCEOApproval: ' + e); }
}

// ===== Bounce Detection (1시간마다) =====
function checkBounces() {
  var RAILWAY = 'https://dashboard-production-b2bd.up.railway.app';
  try {
    var threads = GmailApp.search('subject:(Delivery Status Notification) OR subject:(Mail Delivery Failed) OR subject:(Undeliverable) newer_than:1d', 0, 50);
    var bounced = [];
    threads.forEach(function(thread) {
      var msg = thread.getMessages()[0];
      var body = msg.getPlainBody();
      var emailMatch = body.match(/[\w.-]+@[\w.-]+\.\w+/g);
      if (emailMatch) bounced.push({email: emailMatch[0], date: msg.getDate().toISOString(), subject: msg.getSubject()});
    });
    if (bounced.length > 0) {
      UrlFetchApp.fetch(RAILWAY + '/api/email-bounce', {method:'POST', contentType:'application/json', payload:JSON.stringify({bounced:bounced}), muteHttpExceptions:true});
    }
  } catch(e) { Logger.log('checkBounces: ' + e); }
}

// ===== Trigger Setup (최초 1회) =====
function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('checkCEOApproval').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('checkBounces').timeBased().everyHours(1).create();
  Logger.log('Triggers set: checkCEOApproval(5min), checkBounces(1h)');
}
