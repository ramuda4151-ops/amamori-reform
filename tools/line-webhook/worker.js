// LINE Webhook受信Worker
// POST /line : LINEからのWebhookイベントを受信してKVに保存。
//              LINE_CHANNEL_ACCESS_TOKEN が設定済みなら「ID」発言にグループIDを自動返信
// GET  /last?k=amarefo : 直近の受信イベント（groupId等）をJSONで表示
export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    if (req.method === 'POST' && url.pathname === '/line') {
      let body = null;
      try { body = await req.json(); } catch (_) {}
      const events = [];
      for (const ev of body?.events ?? []) {
        const rec = {
          time: new Date(ev.timestamp || Date.now()).toISOString(),
          sourceType: ev.source?.type ?? null,
          groupId: ev.source?.groupId ?? null,
          userId: ev.source?.userId ?? null,
          text: ev.message?.text ?? null,
        };
        events.push(rec);

        // 「ID」と発言されたら送信元IDを返信（トークン設定済みの場合のみ）
        if (env.LINE_CHANNEL_ACCESS_TOKEN && ev.replyToken &&
            typeof rec.text === 'string' && rec.text.trim().toUpperCase() === 'ID') {
          const id = rec.groupId || rec.userId || '不明';
          const label = rec.groupId ? 'このグループのID' : 'あなたのユーザーID';
          await fetch('https://api.line.me/v2/bot/message/reply', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${env.LINE_CHANNEL_ACCESS_TOKEN}`,
            },
            body: JSON.stringify({
              replyToken: ev.replyToken,
              messages: [{ type: 'text', text: `${label}:\n${id}` }],
            }),
          });
        }
      }
      if (events.length) {
        const prev = JSON.parse((await env.EVENTS.get('recent')) || '[]');
        await env.EVENTS.put('recent', JSON.stringify([...events, ...prev].slice(0, 20)));
      }
      return new Response('ok');
    }

    if (req.method === 'GET' && url.pathname === '/last') {
      if (url.searchParams.get('k') !== 'amarefo') return new Response('ng', { status: 403 });
      const recent = (await env.EVENTS.get('recent')) || '[]';
      return new Response(recent, { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
    }

    return new Response('amamori line webhook', { status: 200 });
  },
};
