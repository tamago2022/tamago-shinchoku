#!/usr/bin/env node
/**
 * 896番：外部連絡いっぱつ(renraku.py)のブラウザ操作部分。
 *
 * 既存のtools/line_inquiry_prepare.mjsはplaywright-core経由のconnectOverCDPを使っていたが、
 * 2026-09-17実測で「Browser.setDownloadBehavior: Browser context management is not supported」
 * エラーで接続確立自体に失敗した（playwright-core 1.62.1 と通常配布版Chrome 152系の非互換）。
 * Playwrightに頼らず、CDPの生HTTPエンドポイント(/json/new, /json/close)とWebSocket
 * (Node.js v24組み込みのグローバルWebSocket)だけで完結させる方式に切り替えた。
 * これなら追加の依存なしでどのMacでも動く。今後、他のフォーム操作を足すときもこのファイルの
 * 薄い関数(send/click/setValue/waitText)を土台にする。
 *
 * サブコマンド:
 *   open  <cdpPort> <url> <shotPath>
 *     → 新規タブでurlを開き、読み込みを待ってスクショをshotPathへ保存。タブは閉じずに残す。
 *       出力: {"ok":true,"tabId":"...","url":"..."}
 *   click <cdpPort> <tabId> <text>
 *     → 既存タブ内で、表示テキストがtextに一致する要素を探してクリックする。
 *       出力: {"ok":true,"clicked":true/false}
 *   fill  <cdpPort> <tabId> <selector> <text(base64)>
 *     → 既存タブ内で、selectorに一致するtextarea/inputへtext(base64デコード後)を入れる。
 *   shot  <cdpPort> <tabId> <shotPath>
 *     → 既存タブのスクショだけ撮る。
 */

async function connect(port, tabId) {
  const base = `http://127.0.0.1:${port}`;
  const wsUrl = `ws://127.0.0.1:${port}/devtools/page/${tabId}`;
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", () => reject(new Error("ws open failed")), { once: true });
    setTimeout(() => reject(new Error("ws open timeout")), 8000);
  });
  let msgId = 1;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.id && pending.has(data.id)) {
        pending.get(data.id)(data);
        pending.delete(data.id);
      }
    } catch {}
  });
  function send(method, params = {}) {
    const id = msgId++;
    return new Promise((resolve, reject) => {
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(new Error(`timeout: ${method}`));
        }
      }, 15000);
    });
  }
  return { ws, send, base };
}

async function evalJs(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result && r.result.exceptionDetails) {
    throw new Error("eval exception: " + JSON.stringify(r.result.exceptionDetails.text || r.result.exceptionDetails));
  }
  return r.result && r.result.result ? r.result.result.value : undefined;
}

async function main() {
  const [, , cmd, portStr, ...rest] = process.argv;
  const port = Number(portStr);
  if (!cmd || !port) {
    console.log(JSON.stringify({ ok: false, error: "usage: <open|click|fill|shot> <cdpPort> ..." }));
    process.exit(1);
  }
  const base = `http://127.0.0.1:${port}`;

  try {
    await (await fetch(`${base}/json/version`, { signal: AbortSignal.timeout(3000) })).json();
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: `CDP接続不可(port ${port}): ${e.message}` }));
    process.exit(1);
  }

  if (cmd === "open") {
    const [url, shotPath] = rest;
    let tab;
    try {
      const r = await fetch(`${base}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
      tab = await r.json();
    } catch (e) {
      console.log(JSON.stringify({ ok: false, error: `タブ作成失敗: ${e.message}` }));
      process.exit(1);
    }
    let conn;
    try {
      conn = await connect(port, tab.id);
      await conn.send("Page.enable");
      await new Promise((r) => setTimeout(r, 3500));
      const shot = await conn.send("Page.captureScreenshot", { format: "png" });
      if (shot.result && shot.result.data) {
        const fs = await import("node:fs");
        fs.writeFileSync(shotPath, Buffer.from(shot.result.data, "base64"));
      }
      conn.ws.close();
      console.log(JSON.stringify({ ok: true, tabId: tab.id, url: tab.url || url, screenshot: shotPath }));
    } catch (e) {
      try {
        if (conn) conn.ws.close();
      } catch {}
      console.log(JSON.stringify({ ok: false, error: e.message, tabId: tab.id }));
      process.exit(1);
    }
    return;
  }

  if (cmd === "click") {
    const [tabId, text] = rest;
    let conn;
    try {
      conn = await connect(port, tabId);
      await conn.send("Runtime.enable");
      const escaped = JSON.stringify(text);
      const expr = `
        (function(){
          const wanted = ${escaped};
          // 親要素より先に、クリック可能な葉要素(button/a/input)を優先する。
          // 広いdiv/spanを先にクリックすると実際のハンドラが発火しないSPAが多い（896番実測）。
          const priority = Array.from(document.querySelectorAll('button,a,input[type=radio],label'));
          const fallback = Array.from(document.querySelectorAll('div,span'));
          for (const el of [...priority, ...fallback]) {
            const t = (el.innerText || el.textContent || '').trim();
            if (t === wanted || t.includes(wanted)) {
              el.scrollIntoView({block:'center'});
              el.click();
              return true;
            }
          }
          return false;
        })()
      `;
      const clicked = await evalJs(conn.send, expr);
      conn.ws.close();
      console.log(JSON.stringify({ ok: true, clicked: !!clicked }));
    } catch (e) {
      try {
        if (conn) conn.ws.close();
      } catch {}
      console.log(JSON.stringify({ ok: false, error: e.message }));
      process.exit(1);
    }
    return;
  }

  if (cmd === "fill") {
    const [tabId, selector, textB64] = rest;
    const text = Buffer.from(textB64, "base64").toString("utf-8");
    let conn;
    try {
      conn = await connect(port, tabId);
      await conn.send("Runtime.enable");
      const expr = `
        (function(){
          try {
            const el = document.querySelector(${JSON.stringify(selector)});
            if (!el) return 'NO_ELEMENT';
            el.scrollIntoView({block:'center'});
            el.focus();
            const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value');
            if (setter && setter.set) { setter.set.call(el, ${JSON.stringify(text)}); }
            else { el.value = ${JSON.stringify(text)}; }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return 'OK';
          } catch (e) { return 'ERR:' + e.message; }
        })()
      `;
      const result = await evalJs(conn.send, expr);
      conn.ws.close();
      console.log(JSON.stringify({ ok: true, filled: result === "OK", detail: result }));
    } catch (e) {
      try {
        if (conn) conn.ws.close();
      } catch {}
      console.log(JSON.stringify({ ok: false, error: e.message }));
      process.exit(1);
    }
    return;
  }

  if (cmd === "shot") {
    const [tabId, shotPath] = rest;
    let conn;
    try {
      conn = await connect(port, tabId);
      await conn.send("Page.enable");
      const shot = await conn.send("Page.captureScreenshot", { format: "png" });
      const fs = await import("node:fs");
      fs.writeFileSync(shotPath, Buffer.from(shot.result.data, "base64"));
      conn.ws.close();
      console.log(JSON.stringify({ ok: true, screenshot: shotPath }));
    } catch (e) {
      try {
        if (conn) conn.ws.close();
      } catch {}
      console.log(JSON.stringify({ ok: false, error: e.message }));
      process.exit(1);
    }
    return;
  }

  console.log(JSON.stringify({ ok: false, error: `unknown cmd: ${cmd}` }));
  process.exit(1);
}

main();
