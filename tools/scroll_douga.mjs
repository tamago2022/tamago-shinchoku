#!/usr/bin/env node
/**
 * 本番ページを「スマホで上から下までゆっくりスクロールする動画（MP4）」に撮る（2026-10-30 たまごさん
 * 「ページ全体を1枚にした細長いスクショは、スマホで見ると縮んで確認しづらい。埋め込み動画にしてタイムラインで
 * スクロールして見られるように」）。確認用の「見せ方の型」はこれ。細長い1枚スクショは確認用に使わない。
 *
 * 方式は tools/kyoku_shot.mjs と同じ（頭なし Chrome・一時プロフィール・使ったら SIGKILL と削除。
 * たまごさんの Brave・Chrome の画面やプロフィールには触らない。許可ダイアログは出ない）。
 *   1) 本物の画面（390×844・拡大率3）を1画面ずつ下ろして撮り、縦につなぐ
 *      （Mac が重いと1コマずつ撮る方式は1コマ3秒以上かかった／全体撮り captureBeyondViewport は YouTube の表紙が黒く抜けた＝実測 10-30）
 *   2) その絵の上を 390×844 の窓がゆっくり下りる動画を ffmpeg で作る（上に張り付く見出し・下に張り付く帯は、
 *      本物の画面から切り取って全コマに重ねる＝スマホで見たときと同じ）
 *   3) 途中で最初の動画を本当に押し、再生が始まるところを実時間（画面の録画）で数秒入れる
 *
 * 使い方: node tools/scroll_douga.mjs <URL> <出力.mp4> [--dark] [--sec 20] [--play 5]
 *   画面 390×844・拡大率3（iPhone相当）・音なし・H.264（yuv420p・faststart）・10MB以下に収める。
 *   同じ名前の .json に、長さ・大きさ・押した動画などを書く。一時ファイルは終わったら必ず消す。
 * 逆テスト: node tools/scroll_douga.mjs --self-test
 */
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { dirname, resolve, join } from "node:path";

const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };

// ffmpeg の crop の y 式：hold 秒止まってから、dur 秒で y0→y1 へゆっくり動き出してゆっくり止まる
export function easeExpr(y0, y1, hold, dur) {
  const T = `clip((t-${hold})/${dur.toFixed(3)},0,1)`;
  return `${y0}+(${y1 - y0})*if(lt(${T},0.5),2*pow(${T},2),1-pow(-2*${T}+2,2)/2)`;
}
// 1画面ずつ撮るときの位置と、各画面のうち使う部分（off＝上から何px目から、h＝何px）
export function stitchPlan(docH, H) {
  const maxY = Math.max(0, docH - H);
  const ys = []; for (let y = 0; y < maxY; y += H) ys.push(y); ys.push(maxY);
  const out = []; let covered = 0;
  for (const y of ys) {
    if (covered >= docH) break;
    const off = Math.max(0, covered - y);
    const h = Math.min(H - off, docH - covered);
    if (h <= 0) continue;
    out.push({ y, off, h }); covered += h;
  }
  return out;
}

if (args[0] === "--self-test") {
  const e = easeExpr(0, 300, 0.5, 2);
  const p = stitchPlan(3993, 844), p2 = stitchPlan(844 * 3, 844), p3 = stitchPlan(500, 844);
  const sum = (a) => a.reduce((s, x) => s + x.h, 0);
  const ok = e.includes("clip((t-0.5)/2.000,0,1)") && e.startsWith("0+(300)*")
    && sum(p) === 3993 && p[p.length - 1].y === 3149 && sum(p2) === 2532 && p2.length === 3 && sum(p3) === 500 && p3.length === 1;
  console.log(ok ? "SELF_TEST: PASS" : "SELF_TEST: FAIL");
  process.exit(ok ? 0 : 1);
}

const URL_ARG = args[0];
const OUT_FILE = args[1] ? resolve(args[1]) : "";
const DARK = args.includes("--dark");
const SEC = Math.min(25, Math.max(15, Number(flag("--sec", "20"))));
const PLAY = Math.min(8, Math.max(0, Number(flag("--play", "5"))));
const FPS = 24;
const MAX_BYTES = 10 * 1024 * 1024;
if (!URL_ARG || !OUT_FILE) {
  console.error("使い方: node tools/scroll_douga.mjs <URL> <出力.mp4> [--dark] [--sec 20] [--play 5]");
  process.exit(1);
}
const W = 390, H = 844, DPR = 3, PW = W * DPR, PH = H * DPR;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const FFMPEG = [join(homedir(), ".local/bin/ffmpeg"), join(homedir(), "bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"].find((p) => existsSync(p)) || "ffmpeg";
// スマホの UA は Android の Chrome にする（iPhone の UA だと YouTube が iPhone 用の再生方式を返し、頭なし Chrome では
// 読み込み中のまま再生が始まらなかった＝実測 10-30）。--user-agent で動画の iframe の中にも効かせる
const MOBILE_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (s) => console.error(`[${new Date().toTimeString().slice(0, 8)}] ${s}`);

async function findPage(port) {
  for (let i = 0; i < 240; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {}
    await sleep(250);
  }
  throw new Error("Chromeのデバッグ口が開きませんでした");
}
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const handlers = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { const cb = pending.get(msg.id); pending.delete(msg.id); cb(msg); }
    else if (msg.method && handlers.has(msg.method)) handlers.get(msg.method)(msg.params);
  });
  const ready = new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", () => rej(new Error("CDP接続失敗"))); });
  const send = (method, params = {}, sessionId) => new Promise((ok, ng) => {
    const myId = ++id;
    pending.set(myId, (m) => (m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result)));
    ws.send(JSON.stringify(sessionId ? { id: myId, method, params, sessionId } : { id: myId, method, params }));
  });
  return { ready, send, on: (m, f) => handlers.set(m, f), close: () => ws.close() };
}
const ev = async (send, expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.value;
const ff = (a) => {
  const r = spawnSync(FFMPEG, ["-y", "-loglevel", "error", ...a], { stdio: ["ignore", "inherit", "inherit"] });
  if (r.status !== 0) throw new Error(`ffmpeg 失敗(${FFMPEG} ${r.error?.code || r.status}): ` + a.slice(-1));
};

// 最初の動画（押すと再生になる表紙か YouTube の iframe）
const FIND_VIDEO = `(()=>{
  const cands=[...document.querySelectorAll('button[aria-label*="再生"],button[aria-label*="Play"],button[aria-label*="play"],[data-video-id],[data-youtube-id],iframe[src*="youtube"],iframe[src*="youtu"],video,img[src*="ytimg"]')];
  for(const el0 of cands){
    let el=el0; if(el.tagName==='IMG'){ el=el.closest('button,a,[role=button],div')||el; }
    const r=el.getBoundingClientRect(); if(r.width<150||r.height<80) continue;
    return {cx:Math.round(r.left+r.width/2), cy:Math.round(r.top+scrollY+r.height/2), h:Math.round(r.height), tag:el.tagName, desc:(el.getAttribute('aria-label')||el.getAttribute('src')||'').slice(0,80)};
  }
  return null;})()`;
// 画面に張り付く帯（上の見出し・下の帯）の高さ。つなぎ撮りの間だけ隠す（あとで本物の画面から重ねる）
const BANDS = `(()=>{let top=0,bot=0;const hid=[];
  for(const el of document.querySelectorAll('body *')){const cs=getComputedStyle(el);if(cs.position!=='fixed'&&cs.position!=='sticky')continue;
    const r=el.getBoundingClientRect();if(r.width<innerWidth*0.6||r.height<1||r.height>innerHeight*0.3||cs.visibility==='hidden'||cs.display==='none')continue;
    if(r.top<=2){top=Math.max(top,Math.ceil(r.bottom));el.setAttribute('data-sd-hide','1');hid.push(el.tagName);}
    else if(r.bottom>=innerHeight-2&&cs.position==='fixed'){bot=Math.max(bot,Math.ceil(innerHeight-r.top));el.setAttribute('data-sd-hide','1');hid.push(el.tagName);}}
  return {top,bot,hid};})()`;

async function main() {
  if (!existsSync(dirname(OUT_FILE))) mkdirSync(dirname(OUT_FILE), { recursive: true });
  const port = 9300 + Math.floor(Math.random() * 500);
  const profile = mkdtempSync(resolve(tmpdir(), "scroll-douga-prof-"));
  const work = mkdtempSync(resolve(tmpdir(), "scroll-douga-frames-"));
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--mute-audio", `--user-agent=${MOBILE_UA}`,
    "--autoplay-policy=no-user-gesture-required", `--window-size=${W},${H}`, "--disable-features=Translate,MediaRouter", "about:blank"], { stdio: "ignore" });
  const cleanup = () => { try { chrome.kill("SIGKILL"); } catch {} for (const d of [profile, work]) { try { rmSync(d, { recursive: true, force: true }); } catch {} } };
  for (const sig of ["SIGALRM", "SIGTERM", "SIGINT"]) process.on(sig, () => { cleanup(); process.exit(1); });
  let close = () => {};
  try {
    const target = await findPage(port);
    const c = connect(target.webSocketDebuggerUrl); close = c.close;
    const send = c.send;
    await c.ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: DPR, mobile: true });
    await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 }).catch(() => {});
    await send("Emulation.setUserAgentOverride", { userAgent: MOBILE_UA });
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: DARK ? "dark" : "light" }] });
    await send("Page.addScriptToEvaluateOnNewDocument", { source: `try{localStorage.setItem('gokigen-theme','${DARK ? "dark" : "light"}')}catch(e){}` });
    await send("Page.navigate", { url: URL_ARG });
    for (let i = 0; i < 60; i++) { await sleep(500); if ((await ev(send, "document.readyState").catch(() => "")) === "complete") break; }
    await sleep(2500);
    // 下まで下ろして、後から描かれる欄を出し切る
    for (let i = 0; i < 50; i++) {
      const done = await ev(send, `(()=>{window.scrollBy(0, ${H * 0.8}); return (window.scrollY + innerHeight + 4) >= document.documentElement.scrollHeight;})()`);
      await sleep(400);
      if (done) { await sleep(1500); if (await ev(send, `(window.scrollY + innerHeight + 4) >= document.documentElement.scrollHeight`)) break; }
    }
    await ev(send, "document.documentElement.style.scrollBehavior='auto'; window.scrollTo(0,0)");
    await sleep(1500);
    log("読み込み済み");

    // 本物の最初の画面（張り付く帯をここから切り取る）
    const top = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(join(work, "top.png"), Buffer.from(top.data, "base64"));
    const bands = await ev(send, BANDS);
    await ev(send, `(()=>{const s=document.createElement('style');s.id='sd-hide';s.textContent='[data-sd-hide]{visibility:hidden!important}';document.head.appendChild(s)})()`);
    await sleep(300);
    const docH = await ev(send, "document.documentElement.scrollHeight");
    const maxY = Math.max(0, docH - H);
    const isDark = await ev(send, "document.documentElement.classList.contains('dark')");
    const vid = PLAY > 0 ? await ev(send, FIND_VIDEO) : null;
    log(`高さ${docH} 帯${JSON.stringify(bands)} 動画${JSON.stringify(vid)}`);

    // ページ全体＝本物の画面を1画面ずつ下ろして撮り、縦につなぐ
    const plan = stitchPlan(docH, H);
    const parts = [];
    for (const p of plan) {
      await ev(send, `window.scrollTo(0, ${p.y})`);
      await sleep(700);
      const s = await send("Page.captureScreenshot", { format: "png" });
      const f = join(work, `part${parts.length}.png`); writeFileSync(f, Buffer.from(s.data, "base64"));
      parts.push({ ...p, f });
    }
    const full = join(work, "full.png");
    ff([...parts.flatMap((p) => ["-i", p.f]), "-filter_complex",
      parts.map((p, i) => `[${i}:v]crop=${PW}:${p.h * DPR}:0:${p.off * DPR}[c${i}]`).join(";") + ";" +
      (parts.length > 1 ? parts.map((_, i) => `[c${i}]`).join("") + `vstack=inputs=${parts.length}[o]` : "[c0]null[o]"),
      "-map", "[o]", "-frames:v", "1", full]);
    await ev(send, "document.getElementById('sd-hide')?.remove()");
    log(`全体を撮影 ${parts.length}枚`);

    // 区間の長さ
    const stopY = vid ? Math.min(maxY, Math.max(0, vid.cy - Math.round(H * 0.45))) : maxY;
    const scrollSec = Math.max(8, SEC - (vid ? PLAY + 2 : 0) - 1.6);
    const s1 = vid ? Math.max(1.2, maxY ? scrollSec * (stopY / maxY) : scrollSec / 2) : scrollSec;
    const s2 = vid ? Math.max(1.2, scrollSec - s1) : 0;

    // 窓が下りる区間を作る（絵は1回だけ読んで使い回す＝Mac が重くても軽い。帯は本物の画面から重ねる）
    const tb = Math.max(2, bands.top * DPR), bb = Math.max(2, bands.bot * DPR);
    const hdPng = join(work, "hd.png"), ftPng = join(work, "ft.png");
    if (bands.top > 0) ff(["-i", join(work, "top.png"), "-vf", `crop=${PW}:${tb}:0:0`, "-frames:v", "1", hdPng]);
    if (bands.bot > 0) ff(["-i", join(work, "top.png"), "-vf", `crop=${PW}:${bb}:0:${PH - bb}`, "-frames:v", "1", ftPng]);
    let fullNow = full;
    const segScroll = (name, y0, y1, holdA, dur, holdB) => {
      const len = (holdA + dur + holdB).toFixed(3);
      const ins = ["-i", fullNow];
      let fc = `[0:v]loop=loop=-1:size=1:start=0,setpts=N/${FPS}/TB,trim=duration=${len},crop=${PW}:${PH}:0:'${easeExpr(y0 * DPR, y1 * DPR, holdA, dur)}'[bg]`;
      let last = "bg", k = 1;
      if (bands.top > 0) { ins.push("-loop", "1", "-framerate", String(FPS), "-t", len, "-i", hdPng); fc += `;[${last}][${k++}:v]overlay=0:0:shortest=1[v1]`; last = "v1"; }
      if (bands.bot > 0) { ins.push("-loop", "1", "-framerate", String(FPS), "-t", len, "-i", ftPng); fc += `;[${last}][${k++}:v]overlay=0:${PH - bb}:shortest=1[v2]`; last = "v2"; }
      fc += `;[${last}]format=yuv420p[out]`;
      const out = join(work, name);
      ff(["-threads", "2", ...ins, "-filter_complex", fc, "-map", "[out]", "-r", String(FPS), "-t", len,
        "-an", "-color_range", "tv", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out]);
      return out;
    };
    const segs = [];
    segs.push(segScroll("a.mp4", 0, stopY, 0.8, s1, vid ? 0.3 : 0.8));
    let played = null;
    if (vid) {
      // 本当に押して、再生の様子を画面の録画で撮る。動画の中（iframe）にもつないで、本当に再生が進んだかを測る
      await ev(send, `window.scrollTo(0, ${stopY})`);
      await sleep(800);
      const cyView = Math.round(await ev(send, `(()=>{const v=${FIND_VIDEO};return v?v.cy-scrollY:${vid.cy - stopY}})()`));
      const frameSids = [];
      c.on("Target.attachedToTarget", (p) => { if (p.targetInfo?.type === "iframe") { frameSids.push(p.sessionId); send("Runtime.runIfWaitingForDebugger", {}, p.sessionId).catch(() => {}); } });
      await send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }).catch(() => {});
      const videoTime = async () => {
        let best = -1;
        for (const sid of frameSids) {
          const r = await send("Runtime.evaluate", { expression: "(()=>{const v=document.querySelector('video');return v?v.currentTime:-1})()", returnByValue: true }, sid).catch(() => null);
          const v = r?.result?.value; if (typeof v === "number" && v > best) best = v;
        }
        return best;
      };
      const frames = [];
      c.on("Page.screencastFrame", (p) => { frames.push({ t: Date.now() / 1000, data: p.data }); send("Page.screencastFrameAck", { sessionId: p.sessionId }).catch(() => {}); });
      await send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: PW, maxHeight: PH, everyNthFrame: 1 });
      await sleep(400);
      const tClick = Date.now() / 1000;
      for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x: vid.cx, y: cyView, button: "left", clickCount: 1 });
      // 再生が始まるまで待つ（最大20秒。待った時間は動画の中では2秒に縮める）
      let tPlay = null;
      for (let i = 0; i < 40; i++) { await sleep(500); if ((await videoTime()) > 0.2) { tPlay = Date.now() / 1000; break; } }
      await sleep(PLAY * 1000);
      const endT = await videoTime();
      const endY = Math.round(await ev(send, "scrollY"));
      const endShot = await send("Page.captureScreenshot", { format: "png" }).catch(() => null);
      await send("Page.stopScreencast").catch(() => {});
      const tEnd = Date.now() / 1000;
      if (endShot) {
        writeFileSync(join(work, "end.png"), Buffer.from(endShot.data, "base64"));
        ff(["-i", join(work, "end.png"), "-q:v", "2", "-frames:v", "1", join(work, "end.jpg")]); // 録画のコマ（jpg）と形をそろえる
        frames.push({ t: tEnd, png: join(work, "end.jpg") });
      }
      played = { started: tPlay !== null, waitSec: tPlay ? Number((tPlay - tClick).toFixed(1)) : null, videoCurrentTime: Number(endT.toFixed(1)), iframes: frameSids.length };
      log(`再生区間 ${frames.length}コマ ${JSON.stringify(played)}`);
      const tP = tPlay ?? tClick + 2;
      const waitF = Math.min(1, 2 / Math.max(0.01, tP - tClick)); // 待ち時間を2秒に縮める
      const shown = frames.filter((fr) => fr.t >= tClick - 0.4);
      if (shown.length) {
        const lines = [];
        shown.forEach((fr, i) => {
          let f = fr.png;
          if (!f) { f = join(work, `p${String(i).padStart(4, "0")}.jpg`); writeFileSync(f, Buffer.from(fr.data, "base64")); }
          const next = i < shown.length - 1 ? shown[i + 1].t : fr.t + 0.5;
          let d = Math.max(0.03, next - fr.t);
          if (fr.t >= tClick && fr.t < tP) d *= waitF;
          lines.push(`file '${f}'\nduration ${d.toFixed(4)}`);
        });
        const listF = join(work, "p.txt"); writeFileSync(listF, lines.join("\n") + `\nfile '${shown[shown.length - 1].png || join(work, `p${String(shown.length - 1).padStart(4, "0")}.jpg`)}'\n`);
        const out = join(work, "p.mp4");
        ff(["-f", "concat", "-safe", "0", "-i", listF, "-vf", `scale=${PW}:${PH}:force_original_aspect_ratio=decrease:out_range=tv,pad=${PW}:${PH}:(ow-iw)/2:0,fps=${FPS},format=yuv420p`,
          "-t", String(PLAY + 3), "-an", "-color_range", "tv", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", out]);
        segs.push(out);
      }
      // 再生後の画面を全体の絵に貼る（下りる続きの区間が、再生前の表紙に戻らないように）
      if (endShot) {
        const t0 = bands.top > 0 ? tb : 0;
        const keepH = PH - (bands.bot > 0 ? bb : 0) - t0;
        const full2 = join(work, "full2.png");
        ff(["-i", full, "-i", join(work, "end.png"), "-filter_complex", `[1:v]crop=${PW}:${keepH}:0:${t0}[e];[0:v][e]overlay=0:${endY * DPR + t0}`, "-frames:v", "1", full2]);
        fullNow = full2;
      }
      segs.push(segScroll("b.mp4", stopY, maxY, 0.3, s2, 0.8));
    }
    close();

    // つないで仕上げ（10MB を超えたら軽くし直す）
    const cl = join(work, "segs.txt"); writeFileSync(cl, segs.map((s) => `file '${s}'`).join("\n") + "\n");
    const tries = [[PW, 26], [PW, 30], [780, 28], [780, 32]];
    let size = 0, used = null;
    for (const [w, crf] of tries) {
      ff(["-f", "concat", "-safe", "0", "-i", cl, "-an", "-vf", `scale=${w}:-2:flags=lanczos:in_range=tv:out_range=tv,format=yuv420p`, "-c:v", "libx264", "-preset", "fast", "-crf", String(crf),
        "-color_range", "tv", "-profile:v", "high", "-movflags", "+faststart", OUT_FILE]);
      size = statSync(OUT_FILE).size; used = `幅${w} crf${crf}`;
      if (size <= MAX_BYTES) break;
    }
    const FFPROBE = FFMPEG.replace(/ffmpeg$/, "ffprobe");
    const pr = spawnSync(existsSync(FFPROBE) ? FFPROBE : "ffprobe", ["-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name", "-of", "json", OUT_FILE], { encoding: "utf8" });
    let probe = null; try { probe = JSON.parse(pr.stdout); } catch {}
    const planned = 0.8 + s1 + (vid ? 0.3 + 2.4 + PLAY + 0.3 + s2 : 0) + 0.8;
    const info = { url: URL_ARG, out: OUT_FILE, dark: DARK, darkClass: isDark, sec: Number((probe ? Number(probe.format?.duration) : planned).toFixed(1)),
      mb: Number((size / 1048576).toFixed(2)), enc: used, size: probe?.streams?.[0] ? `${probe.streams[0].width}x${probe.streams[0].height} ${probe.streams[0].codec_name}` : null,
      pageH: docH, bands, video: vid, played };
    writeFileSync(OUT_FILE.replace(/\.mp4$/, ".json"), JSON.stringify(info, null, 1));
    console.log("保存:", JSON.stringify(info));
    if (size > MAX_BYTES) { console.error("10MBを超えました"); process.exitCode = 2; }
  } finally {
    try { close(); } catch {}
    try { chrome.kill("SIGKILL"); } catch {}
    for (let i = 0; i < 6 && (existsSync(profile) || existsSync(work)); i++) {
      await sleep(600);
      for (const d of [profile, work]) { try { rmSync(d, { recursive: true, force: true }); } catch {} }
    }
  }
}
main().catch((e) => { console.error("失敗:", e.message); process.exitCode = 1; });
