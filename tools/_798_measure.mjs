#!/usr/bin/env node
/**
 * 798番：進捗表の実測（通信回数・通信量・再描画回数・スクロール移動量・ズレ幅）。
 * ヘッドレスChrome+CDPで本番ページを開き、Performance/Network/Mutation を実測する。
 * 参考にした既存パターン：tools/perf_watch.mjs（ヘッドレスChrome起動→CDP接続→計測→必ずkill）。
 * 画面には何も表示しない（--headless=new）。たまごさんの画面は一切奪わない。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = "https://tamago2022.github.io/tamago-shinchoku/";
const WATCH_MS = 60000; // 60秒観測
const SCROLL_SAMPLE_MS = 30000; // 30秒スクロール観測

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findWs(port) {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {}
    await sleep(250);
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
      pending.get(msg.id)(msg.result ?? msg.error);
      pending.delete(msg.id);
    } else if (msg.method) onEvent(msg);
  });
  const ready = new Promise((res) => ws.addEventListener("open", res));
  const send = (method, params = {}) =>
    new Promise((res) => {
      const myId = ++id;
      pending.set(myId, res);
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}

async function main() {
  const port = 9800 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "measure798-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=375,812",
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  const netReqs = []; // {url, ts}
  const netSizes = new Map(); // requestId -> {url, size}
  let mutCountRes = null;
  let scrollStatsRes = null;
  const shots = {};

  try {
    const target = await findWs(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl, (msg) => {
      if (msg.method === "Network.requestWillBeSent") {
        const u = msg.params.request.url;
        netSizes.set(msg.params.requestId, { url: u, size: 0 });
        netReqs.push({ url: u, ts: Date.now() });
      } else if (msg.method === "Network.loadingFinished") {
        const rec = netSizes.get(msg.params.requestId);
        if (rec) rec.size = msg.params.encodedDataLength || 0;
      }
    });
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Network.enable");
    await send("Network.setCacheDisabled", { cacheDisabled: true }); // CDN/ブラウザキャッシュで古いindex.htmlを掴まない
    await send("Target.activateTarget", { targetId: target.id });

    // 798番⑦の?v=一本化仕様に合わせ、実際のホーム画面アプリと同じ「?v=版ハッシュ」を付けて開く。
    //   ?v=無しで開くとPAGE_BUILDが空のままcheckVersion()がlocation.replaceを起こし、
    //   ページが2回読み込まれて計測が水増しされてしまう（実際のユーザーは?v=を保持し続ける）。
    //   末尾に計測用タイムスタンプも足し、CDNの古いindex.htmlキャッシュも避ける。
    const verJson = await (await fetch(URL + "status/version.json", { cache: "no-store" })).json();
    const pageUrl = URL + "index.html?v=" + encodeURIComponent(verJson.v || "") + "&m798=" + Date.now();
    await send("Page.navigate", { url: pageUrl });
    await sleep(4000); // 初回ロード安定待ち

    // 初期スクリーンショット
    const shot0 = await send("Page.captureScreenshot", { format: "png" });
    shots.before = shot0.data;

    // MutationObserverを#paceBar/#genzaichiBarに仕込む＋スクロール監視をセット
    await send("Runtime.evaluate", {
      expression: `
        (function(){
          window.__mut798 = 0;
          const targets = ["paceBar","genzaichiBar"].map(id=>document.getElementById(id)).filter(Boolean);
          const obs = new MutationObserver((muts)=>{ window.__mut798 += muts.length; });
          targets.forEach(t=> obs.observe(t, {childList:true, subtree:true, characterData:true, attributes:true}));
          window.__mut798Targets = targets.length;
          window.scrollTo(0, 600);
          window.__scrollStart = window.scrollY;
          window.__scrollMin = window.scrollY;
          window.__scrollMax = window.scrollY;
          window.addEventListener("scroll", ()=>{
            const y = window.scrollY;
            if(y < window.__scrollMin) window.__scrollMin = y;
            if(y > window.__scrollMax) window.__scrollMax = y;
          }, {passive:true});
          return {targets: window.__mut798Targets, scrollStart: window.__scrollStart};
        })()
      `,
      returnByValue: true,
    });

    // now.json / rev.txt の値を観測開始時点で記録（ズレ幅測定の材料）
    const t0 = Date.now();
    const revBefore = await (await fetch(URL + "status/rev.txt", { cache: "no-store" })).text();
    const nowJsonBefore = await (await fetch(URL + "status/now.json", { cache: "no-store" })).text();

    // 60秒観測（この間のNetworkイベントを集める）。前半30秒はスクロール移動量も見る。
    await sleep(SCROLL_SAMPLE_MS);
    const scrollEval = await send("Runtime.evaluate", {
      expression: `({start: window.__scrollStart, min: window.__scrollMin, max: window.__scrollMax, now: window.scrollY})`,
      returnByValue: true,
    });
    scrollStatsRes = scrollEval.result?.value || scrollEval.value?.result?.value || null;

    const shot30 = await send("Page.captureScreenshot", { format: "png" });
    shots.after30s = shot30.data;

    await sleep(WATCH_MS - SCROLL_SAMPLE_MS);

    const t1 = Date.now();
    const revAfter = await (await fetch(URL + "status/rev.txt", { cache: "no-store" })).text();

    const mutEval = await send("Runtime.evaluate", {
      expression: `window.__mut798`,
      returnByValue: true,
    });
    mutCountRes = mutEval.result?.value ?? mutEval.value?.result?.value ?? null;

    // status/配下への通信だけ集計
    const statusReqs = netReqs.filter((r) => r.url.includes("/status/"));
    const sizes = [...netSizes.values()].filter((r) => r.url.includes("/status/"));
    const totalBytes = sizes.reduce((a, b) => a + (b.size || 0), 0);
    const byFile = {};
    for (const s of sizes) {
      const name = s.url.split("/status/")[1] || s.url;
      byFile[name] = (byFile[name] || 0) + (s.size || 0);
    }

    close();

    const result = {
      observedMs: t1 - t0,
      statusRequestCount: statusReqs.length,
      statusTotalBytes: totalBytes,
      byFile,
      revBefore,
      revAfter,
      revChanged: revBefore.trim() !== revAfter.trim(),
      nowJsonBytes: Buffer.byteLength(nowJsonBefore, "utf8"),
      mutationCount: mutCountRes,
      scroll: scrollStatsRes,
    };
    writeFileSync(join(process.cwd(), "status/_798_measure_result.json"), JSON.stringify(result, null, 1));
    writeFileSync(join(tmpdir(), "798-before.png"), Buffer.from(shots.before, "base64"));
    writeFileSync(join(tmpdir(), "798-after30s.png"), Buffer.from(shots.after30s, "base64"));
    console.log(JSON.stringify(result, null, 1));
    console.log("screenshots:", join(tmpdir(), "798-before.png"), join(tmpdir(), "798-after30s.png"));
  } finally {
    await new Promise((resolve) => {
      let done = false;
      const finish = () => { if (done) return; done = true; resolve(); };
      chrome.once("exit", finish);
      chrome.kill("SIGKILL");
      setTimeout(finish, 3000);
    });
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

main().catch((e) => { console.error("ERROR", e); process.exit(1); });
