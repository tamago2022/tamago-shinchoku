// 本番の頭なしブラウザ確認（2026-10-22・思い込み）：差し込み位置・動画再生・曲ページへのリンク
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const pw = require(process.env.HOME + "/.tamago/node_modules/playwright-core");
const OUT = process.argv[2];
const b = await pw.chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", args: ["--autoplay-policy=no-user-gesture-required"] });
const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const r = {};
await p.goto("https://joy-relief-station.lovable.app/magazine/kimi-wa-hoshi-katsu.html?v=" + Date.now(), { waitUntil: "networkidle" });
r.pos = await p.evaluate(() => {
  const l = document.querySelector('[data-omk="1"].cw-more__label'); if (!l) return null;
  const sec = l.closest("section"); const prev = l.previousElementSibling; let n = l.nextElementSibling; while (n && !n.matches(".cw-more__label")) n = n.nextElementSibling;
  return { chapter: sec.id, chTitle: sec.querySelector("h2").textContent, prevEndsWith: prev.textContent.trim().slice(-30), nextLabel: n && n.textContent, songHref: sec.querySelector('a[href*="song=omoikomi"]')?.href, srcLi: !!document.querySelector('.cw-sources li[data-omk="1"]') };
});
const lab = p.locator('[data-omk="1"].cw-more__label');
await lab.scrollIntoViewIfNeeded(); await p.waitForTimeout(800);
await p.screenshot({ path: OUT + "/omk_mag.png" });
await p.click('button[data-yt-cover="28x7Wirobjw"]');
await p.waitForTimeout(6000);
const fr = p.frames().find((f) => f.url().includes("28x7Wirobjw"));
r.iframe = fr ? fr.url().slice(0, 120) : null;
if (fr) r.player = await fr.evaluate(() => { const v = document.querySelector("video"); const e = document.querySelector(".ytp-error"); return { hasVideo: !!v, t: v ? v.currentTime : null, paused: v ? v.paused : null, error: e ? e.textContent.trim().slice(0, 100) : null }; }).catch((e) => String(e));
await p.screenshot({ path: OUT + "/omk_play.png" });
await p.goto(r.pos.songHref, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
r.song = await p.evaluate(() => ({ url: location.href, title: document.title, h1: document.querySelector("h1")?.textContent?.slice(0, 80), related: [...new Set([...document.querySelectorAll('a[href*="/cover-guide?artist="]')].map((a) => a.getAttribute("href")).filter((h) => !h.includes("song=omoikomi")))].length, hasCopy: document.body.innerText.includes("作曲欄の一行がほどく") }));
await p.screenshot({ path: OUT + "/omk_song.png" });
console.log(JSON.stringify(r, null, 1));
await b.close();
