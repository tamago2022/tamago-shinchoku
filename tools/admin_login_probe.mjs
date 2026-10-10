#!/usr/bin/env node
/**
 * 本番の編集ログインを、画面を出さないブラウザ（Playwrightのheadless）で実際に試す。
 * tools/admin_login_mimawari.py から呼ばれる。単体でも動く：
 *   node tools/admin_login_probe.mjs [--base https://joy-relief-station.lovable.app]
 *
 * 試すこと（合言葉ごとに、まっさらなブラウザで）：
 *   1) /admin のパスワード欄に入れて「ログイン」→ サーバーの返事が ok:true / via:"password" か
 *   2) そのまま再読込 → ログイン欄が出ない（＝端末が覚えている。Cookieが焼けている）か
 * 合言葉の値は結果ファイルに書かない（"half"/"full" の名前だけ書く）。
 * Chrome本体は起動しない。~/.tamago/node_modules/playwright-core のheadlessだけ。
 */
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : "https://joy-relief-station.lovable.app";
// 半角と全角（iPhoneの日本語キーボード）。値はここにだけある＝店主が決めた合言葉そのもの。
const CASES = [
  { name: "half", value: "@" },
  { name: "full", value: "＠" },
];

const browser = await chromium.launch({ headless: true });
const results = [];
for (const c of CASES) {
  const r = { name: c.name, login: false, via: null, remembered: false, error: null };
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  try {
    await page.goto(base + "/admin", { waitUntil: "domcontentloaded", timeout: 60000 });
    const pw = page.locator("#admin-pw");
    await pw.waitFor({ state: "visible", timeout: 45000 });
    await pw.fill(c.value);
    await page.locator('button[type="submit"]').click();
    // 画面で判定：ログイン欄が消えれば通った／「合言葉が違う」が出れば落ちた
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      if (await page.getByText("合言葉が違うようです").first().isVisible().catch(() => false)) { r.via = "rejected"; break; }
      if (!(await pw.isVisible().catch(() => false))) { r.login = true; r.via = "password"; break; }
      await page.waitForTimeout(500);
    }
    // 端末が覚えているか：画面側の控え（localStorage）を消してから再読込しても、
    // ログイン欄が出ないこと＝サーバーが焼いたCookie（400日）だけで通っている
    await page.waitForTimeout(1500);
    await page.evaluate(() => { try { localStorage.clear(); } catch {} });
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(8000);
    r.remembered = !(await page.locator("#admin-pw").isVisible().catch(() => false));
    const cookies = await ctx.cookies();
    r.cookieDays = Math.round(
      Math.max(0, ...cookies.filter((k) => k.name.startsWith("gokigen-admin")).map((k) => k.expires || 0)) / 86400 -
        Date.now() / 86400000,
    );
  } catch (e) {
    r.error = String(e && e.message ? e.message : e).slice(0, 200);
  }
  results.push(r);
  await ctx.close();
}
await browser.close();
const ok = results.every((r) => r.login && r.remembered);
console.log(JSON.stringify({ base, ok, results }));
