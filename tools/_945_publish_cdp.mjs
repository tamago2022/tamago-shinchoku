/**
 * 【945番・2026-09-19】Lovable の「公開」を **Playwright を通さず生のCDPで**押す。
 *
 * なぜ要るか：
 *   既存の scripts/patrol/lovable-publish.mjs は Playwright の connectOverCDP を使うが、
 *   Chrome 153 では接続直後の `Browser.setDownloadBehavior` が
 *   「Browser context management is not supported」で弾かれ、1行も進めない
 *   （＝ブラウザ階層のCDPドメインが制限されている）。
 *   ページ階層のドメイン（Runtime/Page）は使えるので、そちらだけで押す。
 *
 * 前提：Chrome が --user-data-dir=<既定以外> --remote-debugging-port=9223 で起動していること。
 *   （Chrome 136以降、既定プロファイルのままだと --remote-debugging-port は無視される）
 *
 * 使い方： node tools/_945_publish_cdp.mjs
 */
const CDP = process.env.LOVABLE_CDP_URL || "http://127.0.0.1:9223";
const PROJECT_URL =
  process.env.LOVABLE_PROJECT_URL ||
  "https://lovable.dev/projects/8ebdb648-3686-4457-b42c-d01c493793b1";
const PROD_URL = "https://joy-relief-station.lovable.app/";
const WAIT_DEPLOY_MS = 15 * 60 * 1000;

const log = (...a) => console.log(`[${new Date().toLocaleString("ja-JP")}]`, ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function deploymentId() {
  try {
    const r = await fetch(PROD_URL, { method: "HEAD", cache: "no-store" });
    return r.headers.get("x-deployment-id") || "";
  } catch {
    return "";
  }
}

/** ページのターゲットを1つ用意する（既にプロジェクトを開いていればそれを使う）。 */
async function pickTarget() {
  const list = await (await fetch(`${CDP}/json/list`)).json();
  let t = list.find((x) => x.type === "page" && (x.url || "").startsWith(PROJECT_URL));
  if (t) return { target: t, opened: false };
  // Chrome 111以降、/json/new は PUT でないと 405 になる
  const r = await fetch(`${CDP}/json/new?${encodeURIComponent(PROJECT_URL)}`, { method: "PUT" });
  if (!r.ok) throw new Error(`タブを開けません: ${r.status} ${await r.text()}`);
  return { target: await r.json(), opened: true };
}

/** 生CDPの最小クライアント（Node 22 の組み込み WebSocket を使う）。 */
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map();
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", () => res());
    ws.addEventListener("error", (e) => rej(new Error(`ws error: ${e?.message || e}`)));
  });
  ws.addEventListener("message", (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.id && waiting.has(msg.id)) {
      const { res, rej } = waiting.get(msg.id);
      waiting.delete(msg.id);
      msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
    }
  });
  const send = (method, params = {}) =>
    ready.then(
      () =>
        new Promise((res, rej) => {
          const mid = ++id;
          waiting.set(mid, { res, rej });
          ws.send(JSON.stringify({ id: mid, method, params }));
          setTimeout(() => {
            if (waiting.has(mid)) {
              waiting.delete(mid);
              rej(new Error(`${method} タイムアウト`));
            }
          }, 90000);
        }),
    );
  return { send, close: () => ws.close() };
}

/** ページ内で式を評価して値を返す。 */
async function evalIn(cli, expression) {
  const r = await cli.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (r.exceptionDetails) {
    throw new Error(r.exceptionDetails.exception?.description || "ページ内でエラー");
  }
  return r.result?.value;
}

/**
 * 画面の中で「公開」→「変更を公開」を押す一連の操作。
 * ポップオーバーは6〜7秒で勝手に閉じるので、開く→即押す を1セットで4回まで繰り返す
 * （既存 lovable-publish.mjs が実測から辿り着いた手順をそのまま移植）。
 */
const CLICK_SCRIPT = `(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const label = (el) => (el.getAttribute('aria-label') || el.innerText || el.textContent || '').trim();
  const findPublish = () =>
    [...document.querySelectorAll('button')].find(b => /^(公開|Publish)/.test(label(b)));
  const findUpdate = () =>
    [...document.querySelectorAll('button')].find(b => /(変更を公開|Publish update|^Update$)/.test(label(b)));

  if (/login|auth|signin/i.test(location.href)) return { ok:false, reason:'未ログイン', url:location.href };

  for (let i = 0; i < 12; i++) {
    const updating = [...document.querySelectorAll('button')].some(b => /(更新中|Updating)/.test(label(b)));
    if (!updating) break;
    await sleep(5000);
  }

  const pub = findPublish();
  if (!pub) return { ok:false, reason:'「公開」ボタンが見つからない', url:location.href,
                     buttons:[...document.querySelectorAll('button')].slice(0,40).map(label).filter(Boolean) };

  let hasUpdate = false, clicked = false;
  for (let attempt = 0; attempt < 4 && !clicked; attempt++) {
    pub.click();
    let upd = null;
    for (let w = 0; w < 15; w++) { await sleep(100); upd = findUpdate(); if (upd) break; }
    if (!upd) { document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); await sleep(500); continue; }
    hasUpdate = true;
    upd.click();
    upd.dispatchEvent(new MouseEvent('click', { bubbles:true, cancelable:true }));
    clicked = true;
  }
  if (!hasUpdate) return { ok:false, reason:'未公開の変更なし（ポップオーバーに「変更を公開」が無い）' };
  return { ok:true, reason:'「変更を公開」を押した' };
})()`;

async function main() {
  const before = await deploymentId();
  log("本番 x-deployment-id(前):", before.slice(0, 12) || "(取得失敗)");

  const ver = await (await fetch(`${CDP}/json/version`)).json();
  log("CDP 接続先:", ver.Browser);

  const { target, opened } = await pickTarget();
  log(opened ? "タブを開きました" : "既存タブを使います", target.url);
  const cli = connect(target.webSocketDebuggerUrl);
  await cli.send("Runtime.enable");
  await cli.send("Page.enable");

  if (opened) await sleep(12000);
  else await sleep(3000);

  const here = await evalIn(cli, "location.href");
  log("画面:", here);

  const res = await evalIn(cli, CLICK_SCRIPT);
  log("結果:", JSON.stringify(res));
  if (!res?.ok) {
    cli.close();
    process.exitCode = 4;
    return;
  }

  log("反映を待ちます（最大15分）…");
  const started = Date.now();
  while (Date.now() - started < WAIT_DEPLOY_MS) {
    await sleep(20000);
    const now = await deploymentId();
    if (now && now !== before) {
      log("本番反映を確認。x-deployment-id(後):", now.slice(0, 12));
      cli.close();
      return;
    }
  }
  log("15分待ったが x-deployment-id が変わりませんでした。Lovable 側のビルドを確認してください。");
  cli.close();
  process.exitCode = 5;
}

main().catch((e) => {
  log("ERR", e?.stack || e?.message || String(e));
  process.exitCode = 1;
});
