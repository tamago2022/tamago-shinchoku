#!/usr/bin/env node
/**
 * iphone_kakunin.mjs — 本番ページを「iPhone 14 の WebKit」で開いて、中身と再生を確かめる（必ず無音）。
 *
 * 2026-11-14 店主「再生テストの音がMacのスピーカーから鳴った。音が出るテストは二度とやらない」。
 * だからこの道具は、音を出せない作りにしてある：
 *   ①headless の WebKit だけ（普段のブラウザには触らない）
 *   ②全フレーム（YouTube などの埋め込みの中も含む）に、ページより先に「消音の初期スクリプト」を入れる：
 *     video/audio は作られた瞬間に muted=true・volume=0。play() の直前にも必ず消音。muted/volume の書き換えは無視。
 *     WebAudio（AudioContext）は使えなくする。
 *   ③YouTube の埋め込みURLには mute=1 を足してから読む（route で書き換え）。
 *   ④再生の判定は音ではなく currentTime が進んだか。判定の前に、全部の media が消音か確かめ、
 *     1つでも消音でなければその場で止めて exit 3（＝音が出る恐れ。結果は出さない）。
 *
 * 使い方:
 *   node tools/iphone_kakunin.mjs <URL> <出力の頭> [--tap "<CSSセレクタ>"] [--link "<hrefに含む文字>"]
 *     → <出力の頭>.json（題名・画像が出たか・リンク・再生の結果）と <出力の頭>-*.png（スクショ）
 *   node tools/iphone_kakunin.mjs --self-test   … 消音の初期スクリプトが効くかを空ページで確かめる
 * playwright は ~/.tamago/pw/node_modules（リポジトリの外）から読む。WebKit は playwright 1.49 系（macOS 14 で動く版）。
 * 使い終わったら、スクショ等は自分で消すこと（作ったら消す）。
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const require = createRequire(path.join(os.homedir(), ".tamago/pw/package.json"));
const { webkit, devices } = require("playwright");

const MUTE_SCRIPT = `(() => {
  try {
    const P = HTMLMediaElement.prototype;
    const md = Object.getOwnPropertyDescriptor(P, "muted");
    const vd = Object.getOwnPropertyDescriptor(P, "volume");
    const hush = (m) => { try { md.set.call(m, true); vd.set.call(m, 0); } catch (e) {} };
    Object.defineProperty(P, "muted", { configurable: true, get() { return md.get.call(this); }, set() { hush(this); } });
    Object.defineProperty(P, "volume", { configurable: true, get() { return vd.get.call(this); }, set() { hush(this); } });
    const play = P.play;
    P.play = function () { hush(this); return play.apply(this, arguments); };
    const sweep = () => document.querySelectorAll("video,audio").forEach(hush);
    new MutationObserver(sweep).observe(document, { childList: true, subtree: true });
    setInterval(sweep, 50);
    document.addEventListener("play", (e) => hush(e.target), true);
    window.AudioContext = undefined; window.webkitAudioContext = undefined;
  } catch (e) {}
})();`;

async function open() {
  const b = await webkit.launch({ headless: true });
  const ctx = await b.newContext({ ...devices["iPhone 14"] });
  await ctx.addInitScript(MUTE_SCRIPT);
  await ctx.route(/youtube(-nocookie)?\.com\/embed\//, (route) => {
    const u = new URL(route.request().url());
    u.searchParams.set("mute", "1");
    route.continue({ url: u.toString() });
  });
  return { b, ctx, p: await ctx.newPage() };
}

async function allMuted(p) {
  let ok = true;
  for (const f of p.frames()) {
    const r = await f.evaluate(() => [...document.querySelectorAll("video,audio")].every((m) => m.muted && m.volume === 0)).catch(() => true);
    if (!r) ok = false;
  }
  return ok;
}

async function stopAll(p) {
  for (const f of p.frames()) await f.evaluate(() => document.querySelectorAll("video,audio").forEach((m) => { try { m.pause(); } catch (e) {} })).catch(() => {});
}

async function selfTest() {
  const { b, p } = await open();
  await p.setContent('<video id=v src="data:video/mp4;base64,"></video><audio id=a></audio>');
  const r = await p.evaluate(() => { const v = document.getElementById("v"); v.muted = false; v.volume = 1; return { m: v.muted, vol: v.volume, ac: typeof window.AudioContext }; });
  await b.close();
  const pass = r.m === true && r.vol === 0 && r.ac === "undefined";
  console.log("SELF_TEST:", pass ? "PASS" : "FAIL", JSON.stringify(r));
  process.exit(pass ? 0 : 1);
}

const args = process.argv.slice(2);
if (args[0] === "--self-test") await selfTest();
const flag = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : null; };
const [url, head] = args;
if (!url || !head) { console.error("使い方: node tools/iphone_kakunin.mjs <URL> <出力の頭> [--tap SEL] [--link 文字]"); process.exit(2); }

const { b, p } = await open();
const out = { url };
try {
  await p.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await p.waitForTimeout(9000);
  out.title = await p.title();
  await p.screenshot({ path: head + "-top.png" });
  const text = flag("--text");
  if (text) {
    for (let y = 1; y <= 12; y++) { await p.evaluate((yy) => window.scrollTo(0, yy), y * 700); await p.waitForTimeout(350); }
    await p.waitForTimeout(2000);
    out.text = { want: text, found: (await p.evaluate(() => document.body.innerText)).includes(text) };
    const el = p.getByText(text, { exact: false }).first();
    if (out.text.found) { await el.scrollIntoViewIfNeeded().catch(() => {}); await p.waitForTimeout(1500); await p.screenshot({ path: head + "-text.png" }); }
  }
  const link = flag("--link");
  if (link) {
    const a = await p.$(`a[href*="${link}"]`);
    out.link = { found: !!a };
    if (a) {
      await a.scrollIntoViewIfNeeded(); await p.waitForTimeout(3000);
      out.link.img = await a.evaluate((e) => { const im = e.querySelector("img"); return im ? { src: im.currentSrc.slice(0, 90), ok: im.naturalWidth > 0 } : null; });
      out.link.text = (await a.innerText()).replace(/\s+/g, " ").slice(0, 120);
      await p.screenshot({ path: head + "-link.png" });
    }
  }
  const tap = flag("--tap");
  if (tap) {
    const el = await p.$(tap);
    out.play = { found: !!el };
    if (el) {
      await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(1500);
      out.play.thumb = await el.evaluate((e) => { const root = e.closest("div")?.parentElement || e; const im = root.querySelector("img"); return im ? { src: im.currentSrc.slice(0, 90), ok: im.naturalWidth > 0 } : null; });
      await p.screenshot({ path: head + "-before.png" });
      const bb = await el.boundingBox();
      await p.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2);
      const samples = [];
      for (let i = 0; i < 6; i++) {
        await p.waitForTimeout(1000);
        if (!(await allMuted(p))) { await stopAll(p); await b.close(); console.error("消音でない media を見つけたので止めました（音が出る恐れ）"); process.exit(3); }
        let t = null;
        for (const f of p.frames()) { const v = await f.evaluate(() => { const m = document.querySelector("video"); return m ? m.currentTime : null; }).catch(() => null); if (v !== null) t = v; }
        samples.push(t);
      }
      out.play.currentTime = samples;
      out.play.playing = samples.filter((x) => x !== null).length >= 2 && samples[samples.length - 1] > (samples.find((x) => x !== null) ?? 0);
      out.play.muted = await allMuted(p);
      await p.screenshot({ path: head + "-after.png" });
      await stopAll(p);
    }
  }
} finally {
  fs.writeFileSync(head + ".json", JSON.stringify(out, null, 1));
  await b.close();
}
console.log(JSON.stringify(out));
