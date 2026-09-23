#!/usr/bin/env node
/**
 * ★1043番【スマホの門】たまごさんのiPhoneのSafariと同じ条件で、箱のページを開いて
 * 実際にボタンを押し、届いたかどうかを画面から読み取る門。
 *
 * なぜ要るか（たまごさん原文 2026-09-24）:
 *   「こういうのを俺で試さないでよ。俺が依頼したものが確実になってるものだけ見せてよ」
 *   「俺が入れたもの全然入ってないよ」
 *   → 1038〜1042番の実測は全部 curl / python で叩いていた。**経路が違う。**
 *     ブラウザは独自ヘッダが付くと本番の前に preflight(OPTIONS) を投げる。curlは投げない。
 *     だから「機械からは通る／たまごさんからは1件も届かない」が起きた。
 *     この門は**ブラウザから押す。**preflightも走る。CORSで止まればここで止まる。
 *
 * 安全側（tools/_825_screenshot_375.mjs と同じ型をそのまま継承する）:
 *   ・headless Chrome ／ 使い捨てプロファイル ／ 終わったら必ず殺す
 *   ・★たまごさんの普段のブラウザには一切触らない。タブを1枚も増やさない
 *   ・投げるURLには ?kikai=1 を付ける＝台帳に「機械の試し投げ」の印が入る
 *     （たまごさんの一覧には1件も混ざらない）
 *
 * 使い方:
 *   node tools/sumaho_gate.mjs <箱のURL> <出力JSONパス> [PNGパス]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const BOX = process.argv[2];
const OUT = resolve(process.argv[3] || "/tmp/sumaho_gate.json");
const PNG = process.argv[4] ? resolve(process.argv[4]) : null;
if (!BOX) { console.error("使い方: node tools/sumaho_gate.mjs <箱のURL> <出力JSON> [PNG]"); process.exit(1); }

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
// ★iPhoneのSafariのUA（iOS 17）。375x812＝iPhone SE/13 miniの実寸
const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
         + "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const W = 375, H = 812;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch { /* 起動待ち */ }
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
    if (msg.id && pending.has(msg.id)) { const cb = pending.get(msg.id); pending.delete(msg.id); cb(msg); }
    else if (msg.method && onEvent) onEvent(msg);
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) => new Promise((res, rej) => {
    const myId = ++id;
    pending.set(myId, (m) => (m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}

async function evalIn(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r?.result?.value;
}

async function main() {
  const res = { at: new Date().toISOString(), box: BOX, ua: "iPhone Safari 17.5", size: `${W}x${H}`,
                console: [], netFail: [], steps: [], ok: false };
  const port = 9600 + Math.floor(Math.random() * 300);
  const profile = mkdtempSync(resolve(tmpdir(), "sumaho-gate-"));
  const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio", `--window-size=${W},${H}`,
    "--disable-features=Translate,MediaRouter", "about:blank",
  ], { stdio: "ignore" });

  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl, (msg) => {
      // ★スマホではconsoleが見えない。ここで全部拾って証拠に残す
      if (msg.method === "Runtime.consoleAPICalled") {
        res.console.push((msg.params.type || "log") + ": " +
          (msg.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 300));
      }
      if (msg.method === "Log.entryAdded") {
        const e = msg.params.entry || {};
        res.console.push(`${e.level}(${e.source}): ${String(e.text || "").slice(0, 300)}`);
        // ★CORSで止められた場合はここに出る（これが1043番で探していたもの）
        if (/cors|Access-Control|preflight/i.test(e.text || "")) res.corsBlocked = String(e.text).slice(0, 400);
      }
      if (msg.method === "Network.loadingFailed") {
        res.netFail.push(`${msg.params.type} ${msg.params.errorText}${msg.params.corsErrorStatus
          ? " / CORS:" + JSON.stringify(msg.params.corsErrorStatus) : ""}`);
        if (msg.params.corsErrorStatus) res.corsBlocked = JSON.stringify(msg.params.corsErrorStatus);
      }
    });
    await ready;
    await send("Page.enable"); await send("Runtime.enable");
    await send("Log.enable"); await send("Network.enable");
    await send("Emulation.setDeviceMetricsOverride",
      { width: W, height: H, deviceScaleFactor: 3, mobile: true });
    await send("Emulation.setUserAgentOverride", { userAgent: UA, platform: "iPhone" });
    await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });

    const url = BOX + (BOX.includes("?") ? "&" : "?") + "kikai=1&t=" + Date.now();
    await send("Page.navigate", { url });
    for (let i = 0; i < 60 && (await evalIn(send, "document.readyState")) !== "complete"; i++) await sleep(300);
    await sleep(2500); // 棚一覧(tana_ichiran.json)のfetch待ち
    res.steps.push("箱を開いた（readyState complete）");

    const has = await evalIn(send, `JSON.stringify({
      send: !!document.getElementById("send"), u: !!document.getElementById("u"),
      m: !!document.getElementById("m"), nomu: !!document.getElementById("nomu"),
      tana: (document.getElementById("tanaNote")||{}).textContent || "" })`);
    res.parts = JSON.parse(has || "{}");
    if (!res.parts.send) throw new Error("［投 げ る］ボタンが画面に無い");
    res.steps.push("ボタンと欄がある: " + has);

    // ★4パターンを、たまごさんと同じ道（ブラウザ→中継所）で順に押す
    const stamp = Date.now().toString(36);
    const patterns = [
      { name: "①URLだけ（棚なし・ひとことなし）", u: "https://www.youtube.com/watch?v=J---aiyznGQ", m: "", tana: false },
      { name: "②URL＋棚", u: "https://www.youtube.com/watch?v=lDK9QqIzhwk", m: "", tana: true },
      { name: "③ひとことだけ", u: "", m: "1043番 スマホの門 ひとことだけ " + stamp, tana: false },
      { name: "④日本語の題名のYouTube", u: "https://www.youtube.com/watch?v=WSeNSzJ2-Jw", m: "1043番 日本語題名の実測 " + stamp, tana: false },
    ];
    res.oshita = [];
    for (const pt of patterns) {
      await evalIn(send, `(function(){
        document.getElementById("u").value = ${JSON.stringify(pt.u)};
        document.getElementById("m").value = ${JSON.stringify(pt.m)};
        document.getElementById("msg").textContent = "";
        ${pt.tana ? `var b=document.querySelector("#tana button"); if(b) b.click();` : ``}
        return 1; })()`);
      await sleep(250);
      // ★実際にボタンを押す（クリックのイベントをそのまま起こす）
      await evalIn(send, `document.getElementById("send").click(), 1`);
      let msg = "", cls = "";
      for (let i = 0; i < 50; i++) {
        await sleep(400);
        msg = await evalIn(send, `(document.getElementById("msg")||{}).textContent || ""`);
        cls = await evalIn(send, `(document.getElementById("msg")||{}).className || ""`);
        if (msg && !/送っています/.test(msg)) break;
      }
      const nokori = await evalIn(send, `(function(){try{return JSON.parse(localStorage.getItem("nagekomi.pending")||"[]").length}catch(e){return -1}})()`);
      res.oshita.push({ pattern: pt.name, gamen: String(msg).slice(0, 300), ok: /ok/.test(cls),
                        tanmatsuNokori: nokori });
      res.steps.push(`${pt.name} → 画面:「${String(msg).slice(0, 120)}」`);
      await sleep(600);
    }
    res.diag = await evalIn(send, `(document.getElementById("diag")||{}).textContent || ""`);
    res.tsuutta = res.oshita.filter((x) => x.ok).length;
    res.ok = res.tsuutta === patterns.length;

    if (PNG) {
      mkdirSync(dirname(PNG), { recursive: true });
      const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
      writeFileSync(PNG, Buffer.from(shot.data, "base64"));
      res.png = PNG;
    }
    close();
  } catch (e) {
    res.error = String(e && e.message ? e.message : e);
  } finally {
    try { chrome.kill("SIGKILL"); } catch {}
  }
  if (!existsSync(dirname(OUT))) mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res, null, 1));
  process.exit(res.ok ? 0 : 1);
}
main();
