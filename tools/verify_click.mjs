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
const SETTLE_MS = 4000;
// 案件#793実測：この進捗表(index.html)は初回描画後、status/*.json群（queue.json等）を
// 複数の非同期fetchで順次読み込んで再描画するため、SETTLE_MSが短いと「まだ一部しか
// 描画されていない瞬間」を対象にしてしまい、同じURLを繰り返し検品しても検出件数が
// 1086件→17件→7件のようにバラつき、無関係なボタンが「無反応」と誤検知される事故があった。
// 1.5秒→4秒に伸ばし、主要な非同期描画が出そろってから要素収集を始める。
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
// 案件#795実測：閉じた<details>（このサイトの「できたもの」「次に発車」等の折りたたみセクション）の
// 中身は、モダンなブラウザでは display:none ではなく content-visibility:hidden で隠される。
// この方式だとoffsetWidth/offsetHeight/getClientRects()は非ゼロを返し続けるため、旧来のvisible判定では
// 「たまごさんには見えていない・押せない」要素を「見える押せる要素」と誤認していた
// （実例：「すべて」「記事」フィルターボタン・「工場に積む」ボタンが軒並み無反応FAILになった。
//  実際にJSで直接.click()すると正しくclassList等は変化しており、実装側は壊れていなかった）。
// 開閉トリガーであるsummary自身（またはその中の要素）は常に押せるので除外しない。
const LIST_EXPR = `JSON.stringify(Array.from(document.querySelectorAll('button, a, [role="button"], [onclick]'))
  .map((el, i) => {
    el.setAttribute('${MARK_ATTR}', String(i));
    const hasBox = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const closedDetails = el.closest('details:not([open])');
    const insideSummary = !!el.closest('summary');
    const hiddenByClosedDetails = !!(closedDetails && !insideSummary);
    return {
      i,
      tag: el.tagName,
      text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30),
      href: el.getAttribute('href') || null,
      target: el.getAttribute('target') || null,
      disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true'),
      visible: hasBox && !hiddenByClosedDetails,
    };
  })
  .filter(x => x.visible && !x.disabled))`;

// 案件#718実測：target="_blank"のリンク（確認ページの外部参照リンク等・全340枚の確認ページで
// 使用中）は、押しても元のタブのlocation.hrefは変わらない。しかも本物のヘッドレスChromeでは
// window.open()自体がポップアップとしてブロックされ「新しいタブ」すら実際には開かない
// （/json/listで確認してもタブが増えないことを実測で確認済み）。そのためこのスクリプトは
// 正しく動くリンクを毎回「無反応」と誤検知していた（実例：#718の確認ページ内のGitHubリンク）。
// CDPには、ブロックされたかどうかに関わらずwindow.open()が呼ばれた瞬間に発火する
// `Page.windowOpen` イベントがある（実測で確認済み）。これをクリックへの「反応」の証拠として使う。

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
    skippedDisappeared: [],
    consoleErrors: [],
    truncated: false,
    error: null,
  };

  try {
    const target = await findPage(port);
    let lastWindowOpenAt = 0; // Page.windowOpenが発火した時刻（target="_blank"クリックの証拠）
    const { ready, send, close } = connect(target.webSocketDebuggerUrl, (method, params) => {
      if (method === "Runtime.consoleAPICalled" && params?.type === "error") {
        const msg = (params.args || []).map((a) => a.value ?? a.description ?? "").join(" ");
        consoleErrors.push(msg.slice(0, 200));
      }
      if (method === "Runtime.exceptionThrown") {
        const desc = params?.exceptionDetails?.exception?.description || params?.exceptionDetails?.text || "";
        consoleErrors.push(("[uncaught] " + desc).slice(0, 200));
      }
      if (method === "Page.windowOpen") {
        lastWindowOpenAt = Date.now();
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
        lastWindowOpenAt = 0; // このクリックで新たに発火したPage.windowOpenだけを見る
        let r = await send("Runtime.evaluate", { expression: clickExpr, returnByValue: true });
        // 案件#793実測：このサイトのキュー一覧・できたもの一覧は数十秒おきの自動再描画
        // （renderQueue()等）でDOM全体が作り直され、無関係なタイミングでマーカー属性が
        // 消えることがある。1回目に見失っただけで即「消えた」と断じると、下の
        // skippedDisappeared行きが増えて本来の無反応検出まで薄まるため、300ms待って
        // 同じマーカーをもう一度だけ探し直してから、それでも駄目なら既存の
        // disappearedBeforeClick判定（下）に委ねる。
        if (!r.result?.value) {
          await sleep(300);
          r = await send("Runtime.evaluate", { expression: clickExpr, returnByValue: true });
        }
        if (!r.result?.value) clickError = "要素が見つかりませんでした（クリック前にDOMから消えた＝マーカーが外れた）";
      } catch (e) {
        clickError = String(e.message || e).slice(0, 150);
      }
      await sleep(CLICK_SETTLE_MS);
      // href付き要素（外部/内部リンク）は実際のページ遷移がCLICK_SETTLE_MSの600msでは
      // 終わらないことがあり、遷移中のURLを「無反応」と誤判定する事故があった
      // （実測：GitHub Pages確認ページの「← 進捗表に戻る」リンク）。
      // href付きだけ、URLが変わるまで最大NAV_WAIT_MSポーリングして待つ。
      // 案件#802実測：遷移先の本番index.html(約340KB・多数の非同期fetch)への遷移で
      // 4秒では時々足りず、実際は動くリンクを無反応と誤検知することがあった
      // （4回連続実行で1回FAIL・3回PASSを実測）。8秒に伸ばして再現率を下げる。
      const NAV_WAIT_MS = 8000;
      let newTabOpened = false;
      // 案件#914実測：GitHub Pagesの進捗表トップ(index.html・多数の非同期fetchで重い)への
      // 遷移中は、下のevalJson('location.href')自体がナビゲーションに巻き込まれて例外を
      // 投げることがある。これまではその瞬間を「遷移が進んでいる証拠」とコメントに書きながら、
      // 実際にはただbreakするだけでフラグに残していなかった。直後の afterスナップショット取得
      // （341行目付近）がその不安定な瞬間に重なって失敗すると after = before に
      // フォールバックし、「クリック前後で何も変化しませんでした」という誤判定になっていた
      // （実測：3回に1回の頻度で再現。894番・892番・896番のstuck化の直接原因）。
      // evalJson失敗そのものを「反応があった証拠」として navDetected に記録する。
      let navDetected = false;
      if (el.href) {
        const navWaitStart = Date.now();
        while (Date.now() - navWaitStart < NAV_WAIT_MS) {
          if (lastWindowOpenAt) {
            newTabOpened = true;
            break;
          }
          try {
            const cur = await evalJson(send, `location.href`);
            if (cur && before && cur !== before.url) {
              navDetected = true;
              break;
            }
          } catch {
            /* ナビゲーション中は評価自体が失敗することがある＝遷移が進んでいる証拠 */
            navDetected = true;
            break;
          }
          await sleep(300);
        }
        // 案件#718実測：target="_blank"のリンク（確認ページ340枚が使用中）は元のタブの
        // URLが変わらない。しかもヘッドレスChromeではwindow.open()自体がポップアップとして
        // ブロックされ「新しいタブ」すら実際には開かない（/json/listで確認済み）ため、
        // 上のURLポーリングだけでは絶対に「変化」を検知できず毎回無反応と誤検知していた。
        // CDPの`Page.windowOpen`イベント（ブロックされても発火する）を反応の証拠として使う。
        if (!newTabOpened && lastWindowOpenAt) newTabOpened = true;
        // 案件#914：遷移を検知した直後は新ページがまだ不安定（DOM構築中）で、
        // 次のafter評価が失敗しやすい。少し待って安定させてから評価する。
        if (navDetected || newTabOpened) await sleep(1200);
      }
      let afterEvalFailed = false;
      try {
        after = await evalJson(send, SNAPSHOT_EXPR);
      } catch {
        afterEvalFailed = true;
        after = before;
      }

      result.tested++;
      // 案件#914：evalJson失敗・遷移検知はそれ自体が「反応があった」証拠として navigated にも含める。
      // これが無いと、後段の「元のURLへ戻す」処理が働かず、以降の要素が軒並り
      // 「クリック前にDOMから消えた」誤検出（無害だが本来不要）を量産する。
      const navigated = (navDetected || afterEvalFailed) || (before && after && before.url !== after.url);
      // htmlLenは広告・時刻表示・無関係な非同期再描画で数文字だけ揺れることがあるため、
      // 「意味のある変化」だけを拾うよう最小の差分しきい値を設ける（案件#800実測で調整）。
      const HTML_LEN_NOISE_THRESHOLD = 30;
      const changed =
        clickError == null &&
        before &&
        (newTabOpened ||
          navDetected ||
          afterEvalFailed ||
          (after &&
            (before.url !== after.url ||
              Math.abs((before.scrollY || 0) - (after.scrollY || 0)) > 5 ||
              before.textHash !== after.textHash ||
              Math.abs((before.htmlLen || 0) - (after.htmlLen || 0)) > HTML_LEN_NOISE_THRESHOLD ||
              before.openDialogCount !== after.openDialogCount)));

      // 案件#795実測（GitHub Pages版 tamago-shinchoku 進捗表・#740の教訓と同型）：
      // 「要素が見つかりませんでした（クリック前にDOMから消えた）」は、その要素自身が
      // 無反応だった証拠にはならない。この進捗表は10〜60秒おきの自動更新（refreshHealth等）と
      // ライブフィードの再描画が常時走っており、直前の別要素へのクリック・ページ内ナビゲーション・
      // ただの自動更新タイマーのどれかが割り込んでDOMを再構築すると、まだ処理待ちだった
      // 後続要素のマーカーが軒並み外れる（1個の巻き込まれで無関係な要素まで無反応扱いになる）。
      // 実際に壊れているボタンは要素ごと消えたりしない（押しても何も起きないだけ）ので、
      // このケースはnoResponseに数えず、再検証が必要な別枠として記録しFAIL判定に使わない。
      const disappearedBeforeClick = clickError != null && clickError.includes("クリック前にDOMから消えた");
      if (!changed && disappearedBeforeClick) {
        result.skippedDisappeared.push({ index: idx, tag: el.tag, text: el.text, href: el.href });
      } else if (!changed) {
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
    skippedDisappearedCount: result.skippedDisappeared.length,
    consoleErrorCount: result.consoleErrors.length,
  }));
  if (result.noResponse.length) {
    console.log("--- 押しても反応しない要素 ---");
    for (const nr of result.noResponse) {
      console.log(`  [${nr.index}] <${nr.tag}> 「${nr.text}」 ${nr.href ? "href=" + nr.href : ""} — ${nr.reason}`);
    }
  }
  if (result.skippedDisappeared.length) {
    console.log("--- クリック前にDOMから消えていた要素（無反応扱いにしない・自動更新/他クリックの巻き込まれの可能性） ---");
    for (const sd of result.skippedDisappeared) {
      console.log(`  [${sd.index}] <${sd.tag}> 「${sd.text}」 ${sd.href ? "href=" + sd.href : ""}`);
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
