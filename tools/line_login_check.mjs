#!/usr/bin/env node
/**
 * 769番→790番で修正：LINE Creators Market専用プロファイル(~/.tamago/chrome-line・CDP 9224)の
 * ログイン状態だけを確認する。フォーム入力や審査リクエストなど、ページの内容を
 * 書き換える操作は一切しない（読み取りのみ）。画面を前面に出す操作(activate)もしない。
 *
 * 判定：
 *   NO_CHROME  … 9224番でChromeが起動していない（start_chrome_line_login.shをまだ実行していない）
 *   NOT_LOGIN  … Chromeは起動しているが、LINEにログインしていない（「登録はこちら」画面）
 *   LOGGED_IN  … ログイン済み（マイページ相当の表示が出ている）
 *   ERROR      … 通信そのものが失敗
 *
 * 使い方: node tools/line_login_check.mjs
 *
 * 【790番で修正】旧版はplaywright-coreのconnectOverCDP()+ctx.newPage()を使っていたが、
 * headful Chrome・タブ0件の状態でnewPage()すると
 * 「Protocol error (Browser.setDownloadBehavior): Browser context management is not supported」
 * で毎回ERRORになるバグがあった（実測・案件#883/#790で確認）。
 * line_stamp_shot.mjs と同じ「生CDP WebSocketで既存タブを使い回す／無ければ/json/newで作る」
 * 方式に統一し、playwright-core依存を外して安定させた。
 */
const CDP_URL = "http://127.0.0.1:9224";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findOrMakePage() {
  const list = await (await fetch(`${CDP_URL}/json/list`, { signal: AbortSignal.timeout(8000) })).json();
  let page = list.find((t) => t.type === "page" && !String(t.url || "").startsWith("chrome://"));
  if (page) return page;
  page = await (await fetch(`${CDP_URL}/json/new?about:blank`, { method: "PUT", signal: AbortSignal.timeout(8000) })).json();
  return page;
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const cb = pending.get(msg.id);
      pending.delete(msg.id);
      cb(msg);
    }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const myId = ++id;
      pending.set(myId, (msg) => {
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      });
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}

async function waitComplete(send) {
  const start = Date.now();
  while (Date.now() - start < 20000) {
    await sleep(400);
    try {
      const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (r.result?.value === "complete") return true;
    } catch {
      /* ナビゲーション中 */
    }
  }
  return false;
}

async function main() {
  let version;
  try {
    // 790番実測：このMacは常時高負荷で、3秒だと重い瞬間にタイムアウトしNO_CHROMEに
    // 誤判定することがあった（実際はChromeは起動していた）。8秒に伸ばして安定させる。
    version = await (await fetch(`${CDP_URL}/json/version`, { signal: AbortSignal.timeout(8000) })).json();
  } catch {
    console.log(JSON.stringify({ state: "NO_CHROME", detail: "9224番でChromeが起動していません" }));
    return;
  }

  const page = await findOrMakePage();
  const { ready, send, close } = connect(page.webSocketDebuggerUrl);
  try {
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    // Target.activateTargetは呼ばない（たまごさんの画面を前面に奪わない）。
    await send("Page.navigate", { url: "https://creator.line.me/ja/" });
    await waitComplete(send);
    await sleep(1500);

    // 2026-09-16是正（案件#883）：/ja/dashboard は実在しないURL（404「指定された
    // ページは存在しません」）だったため、旧ロジック（本文にlogin/登録はこちらを
    // 含まない=ログイン済み、という判定）は404ページを常にLOGGED_INと誤判定する
    // バグがあった。正しいトップページ(/ja/)から「マイページ」リンクの実際の遷移先
    // (href)で判定する方式に修正。未ログイン時はhrefが/signup/line_authになる。
    const r = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        url: location.href,
        mypageHref: (() => {
          const a = Array.from(document.querySelectorAll('a')).find(el => el.textContent.includes('マイページ'));
          return a ? a.getAttribute('href') : null;
        })()
      })`,
      returnByValue: true,
    });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    const { url, mypageHref } = JSON.parse(r.result.value);
    const loggedIn = !!mypageHref && !mypageHref.includes("/signup/line_auth");
    console.log(JSON.stringify({
      state: loggedIn ? "LOGGED_IN" : "NOT_LOGIN",
      url,
      mypageHref,
      browser: version.Browser || null,
    }));
  } finally {
    close();
  }
}
main().catch((e) => {
  console.log(JSON.stringify({ state: "ERROR", detail: e.message }));
  process.exit(1);
});
