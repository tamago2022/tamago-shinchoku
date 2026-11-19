#!/usr/bin/env node
/**
 * 2026-11-12：猫の棚の看板と美の部屋の看板を、本番のスマホ画面（390×844）で同じ物差しで測る＋画面を撮る。
 * ティロリミックスの曲ページでは「関連」の列の札の題名を順に出す。
 * headless Chrome・一時プロファイル・使用後SIGKILL（1168_shot.mjs と同じ方式。普段のブラウザには触らない）。
 * 使い方: node tools/neko1112_mikurabe.mjs <出力フォルダ>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const OUT = resolve(process.argv[2] || "status/neko1112");
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BUST = `t=${Date.now()}`;
const PAGES = [
  ["bi", `https://joy-relief-station.lovable.app/hidden/beauty?${BUST}`],
  ["neko", `https://joy-relief-station.lovable.app/shelf/cute/neko?${BUST}`],
  ["tirori", `https://joy-relief-station.lovable.app/cover-guide?artist=mcdonalds-jp&song=mcd-ado-yoasobi-suisei-mashup-a&${BUST}`],
];

const MEASURE = `(() => {
  const sec = document.querySelector("section.relative.overflow-hidden.text-white");
  if (!sec) return { found: false, h1: [...document.querySelectorAll("h1")].map(e=>e.innerText).slice(0,3) };
  const cs = (el) => el ? getComputedStyle(el) : null;
  const img = sec.querySelector(":scope > img");
  const ov = img ? img.nextElementSibling : null;
  const eb = sec.querySelector(".tracking-\\\\[0\\\\.4em\\\\]");
  const h1 = sec.querySelector("h1");
  const kj = h1 && h1.querySelector("span");
  const p = h1 && h1.nextElementSibling;
  const pick = (el, ks) => { const c = cs(el); return c ? Object.fromEntries(ks.map(k => [k, c[k]])) : null; };
  return {
    found: true,
    secBg: cs(sec).backgroundImage,
    imgOpacity: img ? cs(img).opacity : null,
    imgLoaded: img ? (img.complete && img.naturalWidth > 0) : null,
    imgSrc: img ? img.currentSrc.split("/").pop() : null,
    overlay: ov ? cs(ov).backgroundImage : null,
    eyebrow: pick(eb, ["fontSize", "letterSpacing", "opacity"]),
    h1: pick(h1, ["fontSize", "lineHeight", "fontFamily"]),
    kanji: pick(kj, ["fontSize", "opacity", "marginRight"]),
    line: pick(p, ["fontSize", "opacity"]),
    texts: [eb && eb.innerText, h1 && h1.innerText, p && p.innerText],
    height: Math.round(sec.getBoundingClientRect().height),
  };
})()`;

const RELATED = `(() => {
  const heads = [...document.querySelectorAll("section.mt-10")];
  const out = [];
  for (const s of heads) {
    const row = s.querySelector(".shelf-scroll");
    if (!row) continue;
    out.push({ head: s.firstElementChild?.innerText, cards: [...row.children].map(c => (c.innerText || "").split("\\n").filter(Boolean)[0]) });
  }
  return out;
})()`;

const port = 9500 + Math.floor(Math.random() * 400);
const prof = mkdtempSync(`${tmpdir()}/neko1112-`);
const chrome = spawn(CHROME, [
  "--headless=new", "--mute-audio", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "about:blank",
], { stdio: "ignore" });

async function findPage() {
  for (let i = 0; i < 200; i++) {
    try {
      const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = l.find((t) => t.type === "page");
      if (p?.webSocketDebuggerUrl) return p;
    } catch { /* 起動待ち */ }
    await sleep(300);
  }
  throw new Error("Chromeのデバッグ口が開かない");
}

const result = {};
try {
  const page = await findPage();
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  });
  await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", () => rej(new Error("CDP失敗"))); });
  const send = (method, params = {}) => new Promise((res) => {
    const i = ++id; pend.set(i, (m) => res(m.result));
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true }))?.result?.value;
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  for (const [name, url] of PAGES) {
    await send("Page.navigate", { url });
    await sleep(7000);
    if (name === "tirori") {
      // 関連の列まで下ろして描かせる
      for (let y = 0; y < 8; y++) { await ev("window.scrollBy(0, 900)"); await sleep(700); }
      await sleep(2500);
      result[name] = { related: await ev(RELATED) };
    } else {
      result[name] = await ev(MEASURE);
    }
    await ev("window.scrollTo(0,0)");
    await sleep(600);
    const shot = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(shot.data, "base64"));
  }
  ws.close();
} finally {
  try { chrome.kill("SIGKILL"); } catch { /* もう死んでいる */ }
}
writeFileSync(`${OUT}/mikurabe.json`, JSON.stringify(result, null, 1));
console.log(JSON.stringify(result, null, 1));
