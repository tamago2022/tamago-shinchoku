#!/usr/bin/env node
/**
 * 案件#800：「押せるボタンが、押しても何も起きない」を機械が見つける検品。
 *
 * 背景（たまごさんの言葉 2026-09-13）：
 *   「間違えたものがガンガン上がってきてる。結局、俺が見つけて『違うよ』って言ってる。
 *    直っているものだけ見せてほしいのよ。」
 *
 * 原因：AI検品(Verifier)は build_verify_prompt() で「curlで読め・ブラウザは使うな」と
 *   命じられていたため、「押しても何も起きない」を一度も確認せずPASSを出していた
 *   （実例：コンシェルジュの『話す』ボタンが押しても無反応でもHTMLにコードはあるのでPASS）。
 *
 * これは既存の tools/_759_screenshot.mjs と同じ安全な方式（headless Chrome・
 * 一時プロファイル・使用後SIGKILL・たまごさんの通常ブラウザ／Braveには一切触れない）。
 * claude-in-chrome・screencaptureとは別物＝許可ダイアログを一切出さない。
 *
 * 使い方: node tools/verify_click.mjs <URL> [結果JSON出力パス]
 * 標準出力の最後に必ず1行、次のどちらかを出す（Verifierプロンプトがパースする）:
 *   CLICK_VERDICT: PASS - 押せる要素は全て反応しました（n件中n件）
 *   CLICK_VERDICT: FAIL - 押しても反応しない要素がn件あります（一覧は上記）
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const URL_ARG = process.argv[2];
const OUT_JSON = process.argv[3] ? resolve(process.argv[3]) : null;
if (!URL_ARG) {
  console.error("使い方: node tools/verify_click.mjs <URL> [結果JSON出力パス]");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 1500;
const CLICK_SETTLE_MS = 600;
const MAX_ELEMENTS = 30;      // これ以上は時間がかかりすぎるので打ち切る（心臓を止めない）
const TIME_BUDGET_MS = 90000; // 全体の時間予算。超えたら残りは未検査として打ち切る

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  // 案件#800実測：この工場のMacは常時たくさんのChrome/自動化が同時稼働しており、
  // 高負荷時はデバッグ口が開くまで30秒では足りないことがあった（実測60〜90秒）。
  // ここを短く保つと「検品が失敗しました」の大半が中身ではなくインフラのFAILになる。
  for (let i = 0; i < 300; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      /* 起動待ち */
    }
    await sleep(300);
  }
  throw new Error("Chromeのデバッグ口が開きませんでした");
}

function connect(wsUrl, onEvent) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const cb = pending.get(msg.id);
      pending.delete(msg.id);
      cb(msg);
    } else if (msg.method && onEvent) {
      onEvent(msg.method, msg.params);
    }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) =>
    new Promise((resolve2, reject) => {
      const myId = ++id;
      pending.set(myId, (msg) => {
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve2(msg.result);
      });
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}

async function waitComplete(send) {
  const start = Date.now();
  while (Date.now() - start < LOAD_TIMEOUT_MS) {
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

async function evalJson(send, expression) {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: false });
  if (r.exceptionDetails) {
    throw new Error("JS評価エラー: " + JSON.stringify(r.exceptionDetails.text || r.exceptionDetails));
  }
  const v = r.result?.value;
  if (v === undefined) return null;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

// 押せる要素の「状態」を取る式（クリック前後で同じものを2回評価して比較する）
const SNAPSHOT_EXPR = `JSON.stringify({
  url: location.href,
  scrollY: Math.round(window.scrollY),
  textLen: (document.body.innerText || '').length,
  textHash: (document.body.innerText || '').length + ':' + (document.body.innerText || '').slice(0, 40),
  htmlLen: document.documentElement.outerHTML.length,
  openDialogCount: document.querySelectorAll('[role="dialog"], dialog[open], [aria-modal="true"]').length
})`;

// 案件#800実測：querySelectorAllの通し番号(i)でクリック対象を再取得すると、直前のクリックで
// DOM順序が変わった（ドロップダウンが開く等）場合に別の要素を押してしまい、本来無反応だった
// 要素（実例：「話す」ボタン）を見逃す事故があった。要素へ一時マーカー属性を直接付けて、
// DOM順序が変わってもクリック時に正しく同じ要素を再取得できるようにする。
const MARK_ATTR = "data-vc-mark";
const LIST_EXPR = `JSON.stringify(Array.from(document.querySelectorAll('button, a, [role="button"], [onclick]'))
  .map((el, i) => {
    el.setAttribute('${MARK_ATTR}', String(i));
    return {
      i,
      tag: el.tagName,
      text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30),
      href: el.getAttribute('href') || null,
      disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true'),
      visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
    };
  })
  .filter(x => x.visible && !x.disabled))`;

async function main() {
  const t0 = Date.now();
  const outDir = OUT_JSON ? dirname(OUT_JSON) : null;
  if (outDir && !existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const port = 9700 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(resolve(tmpdir(), "verify-click-"));
  const consoleErrors = [];
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=375,900",
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore", detached: true },
  );
  chrome.unref();

  const result = {
    url: URL_ARG,
    checkedAt: new Date().toISOString(),
    totalClickable: 0,
    tested: 0,
    autoOkLinkCount: 0,
    noResponse: [],
    consoleErrors: [],
    truncated: false,
    error: null,
  };

  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl, (method, params) => {
      if (method === "Runtime.consoleAPICalled" && params?.type === "error") {
        const msg = (params.args || []).map((a) => a.value ?? a.description ?? "").join(" ");
        consoleErrors.push(msg.slice(0, 200));
      }
      if (method === "Runtime.exceptionThrown") {
        const desc = params?.exceptionDetails?.exception?.description || params?.exceptionDetails?.text || "";
        consoleErrors.push(("[uncaught] " + desc).slice(0, 200));
      }
    });
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: 375,
      height: 900,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    const beforeShot = await send("Page.captureScreenshot", { format: "png" });
    if (OUT_JSON) {
      writeFileSync(OUT_JSON.replace(/\.json$/, "") + ".before.png", Buffer.from(beforeShot.data, "base64"));
    }

    const elements = await evalJson(send, LIST_EXPR);
    result.totalClickable = elements.length;

    // 案件#800実測：cover-guideのようなカード一覧ページはhref付き<a>だけで数千件になり、
    // 全部を素直に先頭から拾うと予算をリンクの繰り返し(▶ボタンの隣のカード等)で使い切り、
    // 本当に検証したい「JSで動くはずのボタン」（話す・気分・棚・扉等）まで到達できなかった。
    // href付き<a>はブラウザの標準動作として押せば必ず遷移する＝無反応になりようがないので、
    // 代表数件だけ実クリックし、残りは「自明に反応する」ものとして検証対象から外す。
    const buttonLike = elements.filter((e) => !(e.tag === "A" && e.href));
    const linksWithHref = elements.filter((e) => e.tag === "A" && e.href);
    const LINK_SAMPLE = 5;
    const linkSample = linksWithHref.slice(0, LINK_SAMPLE);
    result.autoOkLinkCount = Math.max(0, linksWithHref.length - linkSample.length);
    const testList = [...buttonLike, ...linkSample].slice(0, MAX_ELEMENTS);
    if (buttonLike.length + linkSample.length > MAX_ELEMENTS || result.autoOkLinkCount > 0) {
      result.truncated = true;
    }

    // 案件#800実測：Chrome起動〜ページロード〜要素収集だけでマシン高負荷時は90秒近く
    // 使うことがあり、時間予算の起点をmain()先頭のままにすると「クリックループに
    // 1件も入れないままtested=0で終わり、無反応0件だからPASS」という見せかけの合格が
    // 生まれた（実測：cover-guideで発生）。クリックループ自体の予算はここから測り直す。
    const clickLoopT0 = Date.now();
    for (let listIdx = 0; listIdx < testList.length; listIdx++) {
      if (Date.now() - clickLoopT0 > TIME_BUDGET_MS) {
        result.truncated = true;
        break;
      }
      const el = testList[listIdx];
      const idx = el.i; // querySelectorAllでの元の位置（クリック時はこれで再取得する）
      let before, after, clickError = null;
      try {
        before = await evalJson(send, SNAPSHOT_EXPR);
      } catch {
        continue;
      }
      try {
        // querySelectorAllの通し番号ではなく、要素本体に付けたマーカー属性で再取得する
        // （直前のクリックでDOM順序が変わっても、同じ物理要素を確実に狙い撃つ）。
        const clickExpr = `(() => {
          const target = document.querySelector('[${MARK_ATTR}="${idx}"]');
          if (!target) return false;
          target.scrollIntoView({ block: 'center' });
          target.click();
          return true;
        })()`;
        const r = await send("Runtime.evaluate", { expression: clickExpr, returnByValue: true });
        if (!r.result?.value) clickError = "要素が見つかりませんでした（クリック前にDOMから消えた＝マーカーが外れた）";
      } catch (e) {
        clickError = String(e.message || e).slice(0, 150);
      }
      await sleep(CLICK_SETTLE_MS);
      try {
        after = await evalJson(send, SNAPSHOT_EXPR);
      } catch {
        after = before;
      }

      result.tested++;
      const navigated = before && after && before.url !== after.url;
      // htmlLenは広告・時刻表示・無関係な非同期再描画で数文字だけ揺れることがあるため、
      // 「意味のある変化」だけを拾うよう最小の差分しきい値を設ける（案件#800実測で調整）。
      const HTML_LEN_NOISE_THRESHOLD = 30;
      const changed =
        clickError == null &&
        before &&
        after &&
        (before.url !== after.url ||
          Math.abs((before.scrollY || 0) - (after.scrollY || 0)) > 5 ||
          before.textHash !== after.textHash ||
          Math.abs((before.htmlLen || 0) - (after.htmlLen || 0)) > HTML_LEN_NOISE_THRESHOLD ||
          before.openDialogCount !== after.openDialogCount);

      if (!changed) {
        result.noResponse.push({
          index: idx,
          tag: el.tag,
          text: el.text,
          href: el.href,
          reason: clickError || "クリック前後でURL・DOM・スクロール・表示テキストのいずれも変化しませんでした",
        });
        // 無反応だった証拠として、その場でスクショを残す（何件あっても最初の5件だけ）
        if (OUT_JSON && result.noResponse.length <= 5) {
          try {
            const shot = await send("Page.captureScreenshot", { format: "png" });
            writeFileSync(
              OUT_JSON.replace(/\.json$/, "") + `.noresponse-${idx}.png`,
              Buffer.from(shot.data, "base64"),
            );
          } catch {
            /* スクショ失敗は致命的ではない */
          }
        }
      }

      // ナビゲーションで別ページへ飛んだ場合は、元のURLへ戻して次の要素の検証を続ける。
      // 戻ると新しいDOMになりマーカー属性が消えるため、同じ通し順で付け直す
      // （URLが同じなら描画順序も基本的に同じという前提。ズレても以降の要素は
      //  「マーカーが見つからない＝クリックできない」としてclickErrorに残るので安全）。
      if (navigated) {
        await send("Page.navigate", { url: URL_ARG });
        await waitComplete(send);
        await sleep(SETTLE_MS);
        try {
          await send("Runtime.evaluate", { expression: LIST_EXPR });
        } catch {
          /* マーカー再付与に失敗しても、以降はclickErrorとして安全に扱われる */
        }
      }
    }

    const afterShot = await send("Page.captureScreenshot", { format: "png" });
    if (OUT_JSON) {
      writeFileSync(OUT_JSON.replace(/\.json$/, "") + ".after.png", Buffer.from(afterShot.data, "base64"));
    }

    result.consoleErrors = [...new Set(consoleErrors)].slice(0, 20);
    // 押せる要素はあったのに1件もクリックできなかったら「無反応0件」を「全部OK」と
    // 取り違えてPASSにしてしまう（実測で発生した見せかけのPASS）。検品未了として明示する。
    if (result.totalClickable > 0 && result.tested === 0 && !result.error) {
      result.error = "押せる要素が" + result.totalClickable + "件あるのに、時間内に1件もクリックできませんでした（検品未実施）";
    }
    close();
  } catch (e) {
    result.error = String(e.message || e);
  } finally {
    // detached起動＝新しいプロセスグループのリーダーなので、グループごと殺してレンダラー等の
    // 子プロセスを残さない（-pid はプロセスグループ全体へのシグナル送信）。
    try {
      process.kill(-chrome.pid, "SIGKILL");
    } catch {
      try {
        chrome.kill("SIGKILL");
      } catch {
        /* 既に終了している */
      }
    }
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* 無視 */
    }
  }

  if (OUT_JSON) {
    writeFileSync(OUT_JSON, JSON.stringify(result, null, 1));
  }

  console.log("実測:", JSON.stringify({
    url: result.url,
    totalClickable: result.totalClickable,
    tested: result.tested,
    autoOkLinkCount: result.autoOkLinkCount || 0,
    truncated: result.truncated,
    noResponseCount: result.noResponse.length,
    consoleErrorCount: result.consoleErrors.length,
  }));
  if (result.noResponse.length) {
    console.log("--- 押しても反応しない要素 ---");
    for (const nr of result.noResponse) {
      console.log(`  [${nr.index}] <${nr.tag}> 「${nr.text}」 ${nr.href ? "href=" + nr.href : ""} — ${nr.reason}`);
    }
  }
  if (result.consoleErrors.length) {
    console.log("--- コンソールエラー ---");
    for (const ce of result.consoleErrors) console.log("  " + ce);
  }

  if (result.error) {
    console.log(`CLICK_VERDICT: FAIL - 検品自体が失敗しました（${result.error}）`);
    process.exitCode = 1;
  } else if (result.noResponse.length > 0) {
    console.log(
      `CLICK_VERDICT: FAIL - 押しても反応しない要素が${result.noResponse.length}件あります（${result.tested}件中）`,
    );
    process.exitCode = 1;
  } else if (result.consoleErrors.length > 0) {
    console.log(`CLICK_VERDICT: FAIL - コンソールエラーが${result.consoleErrors.length}件出ています`);
    process.exitCode = 1;
  } else {
    console.log(`CLICK_VERDICT: PASS - 押せる要素は全て反応しました（${result.tested}件中${result.tested}件・全${result.totalClickable}件）`);
  }
}

main().catch((e) => {
  console.error("失敗:", e.message);
  console.log("CLICK_VERDICT: FAIL - 検品スクリプトが異常終了しました（" + e.message + "）");
  process.exitCode = 1;
});
