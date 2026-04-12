# GAS Code.gs Backup & Reference

## Webhook URL
`EMAIL_WEBHOOK_URL` env var in Railway

## Current doPost Function

```javascript
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // Sheet append action (for DB collection writes)
    if (data.action === 'appendSheet') {
      var ss = SpreadsheetApp.openById(data.sheetId);
      var sheet = ss.getSheetByName(data.range.split('!')[0]) || ss.getSheets()[0];
      if (data.values && data.values.length > 0) {
        sheet.getRange(sheet.getLastRow()+1, 1, data.values.length, data.values[0].length)
          .setValues(data.values);
      }
      return ContentService.createTextOutput(
        JSON.stringify({status:'success', rows: data.values.length})
      ).setMimeType(ContentService.MimeType.JSON);
    }

    // Email send action (existing)
    var to = data.to || '';
    var subject = data.subject || '';
    var body = data.body || '';
    var htmlBody = data.htmlBody || '';
    var agent = data.agent || 'pitch';
    
    var names = {
      pitch: 'Pitch | 08liter(0.8L)',
      luna: 'Luna | Mili Mili x 08liter(0.8L)',
      sophie: 'Sophie | 08liter',
      kyle: 'Kyle | 08liter'
    };
    
    var fromName = names[agent] || 'Pitch | 08liter';
    
    if (!to || !subject) {
      return ContentService.createTextOutput(
        JSON.stringify({status: 'error', message: 'missing to or subject'})
      ).setMimeType(ContentService.MimeType.JSON);
    }
    
    GmailApp.sendEmail(to, subject, body, {
      htmlBody: htmlBody || body,
      name: fromName,
      noReply: false
    });
    
    return ContentService.createTextOutput(
      JSON.stringify({status: 'success', from: agent + '@08liter.com', to: to})
    ).setMimeType(ContentService.MimeType.JSON);
    
  } catch(err) {
    return ContentService.createTextOutput(
      JSON.stringify({status: 'error', message: err.toString()})
    ).setMimeType(ContentService.MimeType.JSON);
  }
}
```

## PITCH_TEMPLATES (to add in GAS)

```javascript
var PITCH_TEMPLATES = {
  A: {
    subject: '{brand}, 같은 카테고리 브랜드들이 어떻게 매출을 올렸는지 궁금하지 않으세요?',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상\n\n저희 파트너 브랜드들의 실제 성과입니다.\n🇲🇾 말레이시아 라이브 — 2분 30초 만에 1억 매출\n🇰🇷 국내 숏폼 1개 — 287만 조회 · 매출 +180%\n\n{brand}과 같은 카테고리, 경쟁사 기준의 성공사례는\n30분 미팅 시 맞춤으로 준비해서 설명드립니다.\n\n📎 상품소개서: https://buly.kr/AF24dn7\n📅 30분 구글 미팅: https://buly.kr/1c9NOdW\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  },
  B: {
    subject: '4/30 마감 — 숏폼 100건 200만원, {brand} 신청 가능합니다',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상\n\n4월 한 달만 진행하는 프로모션입니다.\n\n국내: 숏폼 100건 200만원 (정가 500만원 / 60% 할인)\n해외: 글로벌 숏폼 100건 500만원 (정가 1,000만원 / 50% 할인)\n생성 콘텐츠 3개월간 광고 소재 무료 활용 가능\n\n{brand} 카테고리 기준 성공사례와\n최적 패키지 추천은 30분 미팅에서 맞춤으로 준비해드립니다.\n\n📎 4월 프로모션 상세: https://buly.kr/AF24dn7\n📅 30분 구글 미팅: https://buly.kr/1c9NOdW\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  },
  C: {
    subject: '{brand}, 경쟁사는 지금 어떻게 인플루언서를 쓰고 있을까요?',
    body: '안녕하세요 {contact}님,\n\n공팔리터(0.8L) 피치입니다.\n140만 인플루언서 네트워크 · 3만여 브랜드 캠페인 경험 · 브랜드 만족도 91% 이상\n\n리뷰가 없어서, 숏폼이 안 터져서, 해외 진출이 막막해서.\n브랜드마다 고민이 다릅니다.\n\n{brand}의 카테고리·경쟁사 기준으로\n실제 성공한 캠페인 사례를 30분 미팅 시 직접 준비해드립니다.\n10년간 8개국 2만여 브랜드 경험이 기반입니다.\n\n📎 상품소개서: https://buly.kr/AF24dn7\n📅 30분 구글 미팅: https://buly.kr/1c9NOdW\n\n---\n공팔리터 주니어 컨설턴트 피치\npitch@08liter.com | 08liter.com'
  }
};
```

## Trigger Functions

```javascript
function checkCEOApproval() {
  var RAILWAY = 'https://dashboard-production-b2bd.up.railway.app';
  try {
    var threads = GmailApp.search('subject:(피치 검수) from:jacob is:unread', 0, 5);
    threads.forEach(function(thread) {
      var msgs = thread.getMessages();
      var latest = msgs[msgs.length - 1];
      var body = latest.getPlainBody().trim().substring(0, 20).toUpperCase();
      var variant = null;
      if (body.match(/^A\b/)) variant = 'A';
      else if (body.match(/^B\b/)) variant = 'B';
      else if (body.match(/^C\b/)) variant = 'C';
      if (variant) {
        UrlFetchApp.fetch(RAILWAY + '/api/pitch/send', {
          method: 'POST', contentType: 'application/json',
          payload: JSON.stringify({template: variant, source: 'ceo_approval'})
        });
        latest.markRead();
      }
    });
  } catch(e) { Logger.log('checkCEOApproval: ' + e); }
}

function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('checkCEOApproval').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('checkBounces').timeBased().everyHours(1).create();
  Logger.log('Triggers set: checkCEOApproval(5min), checkBounces(1h)');
}
```

## checkBounces (bounce detection - NEW)

```javascript
function checkBounces() {
  var RAILWAY = 'https://dashboard-production-b2bd.up.railway.app';
  try {
    var threads = GmailApp.search(
      'subject:(Delivery Status Notification) OR subject:(Mail Delivery Failed) OR subject:(Undeliverable) newer_than:1d',
      0, 50
    );
    var bounced = [];
    threads.forEach(function(thread) {
      var msg = thread.getMessages()[0];
      var body = msg.getPlainBody();
      var emailMatch = body.match(/[\w.-]+@[\w.-]+\.\w+/g);
      if (emailMatch) {
        bounced.push({
          email: emailMatch[0],
          date: msg.getDate().toISOString(),
          subject: msg.getSubject()
        });
      }
    });
    if (bounced.length > 0) {
      UrlFetchApp.fetch(RAILWAY + '/api/email-bounce', {
        method: 'POST',
        contentType: 'application/json',
        payload: JSON.stringify({bounced: bounced}),
        muteHttpExceptions: true
      });
      Logger.log('Bounce detected: ' + bounced.length);
    }
  } catch(e) { Logger.log('checkBounces error: ' + e); }
}
```

## checkCEOApproval (updated - Luna support added)

```javascript
function checkCEOApproval() {
  var RAILWAY = 'https://dashboard-production-b2bd.up.railway.app';
  try {
    // Pitch approval
    var pitchThreads = GmailApp.search('subject:(피치 검수) from:jacob is:unread', 0, 5);
    pitchThreads.forEach(function(thread) {
      var msgs = thread.getMessages();
      var latest = msgs[msgs.length - 1];
      var body = latest.getPlainBody().trim().substring(0, 20).toUpperCase();
      var variant = null;
      if (body.match(/^A\b/)) variant = 'A';
      else if (body.match(/^B\b/)) variant = 'B';
      else if (body.match(/^C\b/)) variant = 'C';
      if (variant) {
        UrlFetchApp.fetch(RAILWAY + '/api/pitch/send', {
          method: 'POST', contentType: 'application/json',
          payload: JSON.stringify({template: variant, source: 'ceo_approval'})
        });
        latest.markRead();
      }
    });
    // Luna approval (NEW)
    var lunaThreads = GmailApp.search('subject:(루나 검수) from:jacob is:unread', 0, 5);
    lunaThreads.forEach(function(thread) {
      var msgs = thread.getMessages();
      var latest = msgs[msgs.length - 1];
      var body = latest.getPlainBody().trim().substring(0, 20).toUpperCase();
      if (body.indexOf('APPLY') !== -1 || body.match(/KR_A|KR_B|US_A|US_B/)) {
        var variant = body.match(/KR_A|KR_B|US_A|US_B/) ?
          body.match(/KR_A|KR_B|US_A|US_B/)[0] : 'KR_A';
        UrlFetchApp.fetch(RAILWAY + '/api/luna/send-na', {
          method: 'POST', contentType: 'application/json',
          payload: JSON.stringify({template: variant, source: 'ceo_approval'})
        });
        latest.markRead();
      }
    });
    // Improvement approval
    var applyThreads = GmailApp.search('subject:(개선안) from:jacob is:unread', 0, 5);
    applyThreads.forEach(function(thread) {
      var msgs = thread.getMessages();
      var latest = msgs[msgs.length - 1];
      var body = latest.getPlainBody().trim().toUpperCase();
      if (body.indexOf('APPLY') !== -1) {
        UrlFetchApp.fetch(RAILWAY + '/api/apply-improvements', {
          method: 'POST', contentType: 'application/json',
          payload: JSON.stringify({source: 'ceo_approval'})
        });
        latest.markRead();
      }
    });
  } catch(e) { Logger.log('checkCEOApproval: ' + e); }
}
```

## Deploy Steps
1. Open script.google.com
2. Edit Code.gs
3. Deploy > Manage deployments > Edit > New version > Deploy
4. Run setupTriggers() once to register new triggers
5. Test: curl EMAIL_WEBHOOK_URL -d '{"to":"jacob@08liter.com","subject":"test","body":"test"}'
