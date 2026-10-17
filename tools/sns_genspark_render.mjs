#!/usr/bin/env node
/**
 * Gensparkの型（status/sns_shuukan/gs/promo.html）を1コマずつ撮ってMP4にする（README「Direct MP4 export」の手順どおり）。
 * 方式は tools/1168_shot.mjs と同じ：headless Chrome・一時プロファイル・使用後SIGKILL。
 * ★たまごさんの通常のChromeには一切触れない。タブも開かない。許可ポップアップの出る操作はしない。
 *
 * 使い方: node tools/sns_genspark_render.mjs <週番号> <出力MP4> [<1コマ目PNG>]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const W = process.argv[2] || "1";
const OUT = resolve(process.argv[3] || `/tmp/promo_${W}.mp4`);
const PNG = process.argv[4] ? resolve(process.argv[4]) : null;
const FPS = 30, N = 450;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const FF = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"].find((p) => existsSync(p));

const port = 9500 + Math.floor(Math.random() * 400);
const prof = mkdtempSync(`${tmpdir()}/sgr-`);
const chrome = spawn(CHROME, [
  "--headless=new", "--mute-audio", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
  "--hide-scrollbars", "--force-device-scale-factor=1", "about:blank",
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

let ff;
try {
  const page = await findPage();
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  });
  await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", () => rej(new Error("CDP失敗"))); });
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pend.set(i, (m) => res(m)); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1080, height: 1964, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: `file://${REPO}/status/sns_shuukan/gs/promo.html?w=${W}` });
  // React・Babel・書体・画像を待つ
  for (let i = 0; i < 120; i++) { if (await ev("!!(window.__timelines&&window.__timelines.promo15)")) break; await sleep(500); }
  await ev(`Promise.all(["500 40px 'Shippori Mincho B1'","800 40px 'Shippori Mincho B1'","40px Anton","500 40px 'IBM Plex Mono'"].map(f=>document.fonts.load(f))).then(()=>document.fonts.ready).then(()=>1)`);
  const fontsOk = await ev(`document.fonts.check("800 40px 'Shippori Mincho B1'")&&document.fonts.check("40px Anton")`);
  if (!fontsOk) throw new Error("書体が読めていない（Google Fonts）");
  await ev("window.__timelines.promo15.pause(),1");
  // 画像を先読み（全部の場面を一度通す）
  for (const t of [3.5, 10.5, 13.5]) { await ev(`window.__timelines.promo15.seek(${t}),1`); await sleep(400); }
  await ev(`Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>{i.onload=i.onerror=r})))`);

  ff = spawn(FF || "ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-movflags", "+faststart", OUT], { stdio: ["pipe", "inherit", "inherit"] });
  for (let i = 0; i < N; i++) {
    await ev(`(window.__timelines.promo15.seek(${i / FPS}),new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1)))))`);
    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1080, height: 1920, scale: 1 } });
    const buf = Buffer.from(shot.result.data, "base64");
    if (i === 0 && PNG) writeFileSync(PNG, buf);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  console.log(`できた 週${W} → ${OUT}`);
  ws.close();
} finally {
  try { chrome.kill("SIGKILL"); } catch { /* */ }
  try { rmSync(prof, { recursive: true, force: true }); } catch { /* */ }
}
