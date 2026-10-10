#!/usr/bin/env node
/**
 * LINE Creators Marketへの問い合わせフォームを、文面を入れた状態まで開く（送信はしない）。
 *
 * たまごさん「文面だけ渡して『あとは自分で送って』は禁止。送信ボタンの手前まで持っていく」への対応。
 * ここで確立した手順（宛先を調べる→専用プロファインのChromeで画面を開く→文面を入れる→
 * 送信直前で止める→スクショを確認ページに置く）は、他のサービスへの問い合わせでも同じ形で使う。
 * サービスごとに変わるのは「フォームの構造（カスタムselect/条件分岐の質問）」だけなので、
 * 新しいサービス用に作るときは、このファイルの main() の中身（フォーム操作の部分）だけを
 * そのサービス用に差し替える。
 *
 * 使い方:
 *   node tools/line_inquiry_prepare.mjs
 *   （事前に ~/.tamago/chrome-line プロファイルでLINEにログイン済みであること。
 *    未ログインなら tools/start_chrome_line_login.sh を実行して手動ログインしてもらう）
 *
 * 実測した窓口URL: https://contact-cc.line.me/serviceId/10569
 *   → 「ログインせずにつづける」を押すと ?continue_without_login=true で本フォームに到達。
 *   フォーム構造（2026-09-16実測）：
 *     国 → PC/スマホ等 → サービス（LINE Creators Market・LINEスタンプメーカー）→ カテゴリ → 詳細
 *     という5段のカスタムselectがあり、カテゴリ・詳細を選ぶと条件分岐の質問（ラジオボタン）と
 *     自由記述欄が動的に現れる。これらは素のCSS<select>ではなくJS製のカスタムUIなので、
 *     hidden selectのvalueを直接書き換えても画面にもReact側の状態にも反映されない。
 *     必ず「見えているdiv.MdSelectBox01をクリック→開いたa要素をクリック」で選ぶこと。
 */
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
const require = createRequire(import.meta.url);

const CDP_URL = "http://127.0.0.1:9224";
const FORM_URL = "https://contact-cc.line.me/serviceId/10569";

// ここを差し替えれば別カテゴリ/別文面で使える
const CATEGORY_LABEL = "制作・修正";
const DETAIL_LABEL = "制作に関する問題";
const PLACE_RADIO_VALUE = "LINE Creators Market（PC/Webサイト）";

function loadPlaywright() {
  return require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));
}

async function selectCustomDropdown(page, boxIndex, optionText) {
  const boxes = await page.locator("div.MdSelectBox01").all();
  await boxes[boxIndex].click({ timeout: 8000 });
  await page.waitForTimeout(500);
  const opt = page.locator(`a:has-text('${optionText}')`).last();
  await opt.waitFor({ state: "visible", timeout: 5000 });
  await opt.click({ timeout: 5000 });
  await page.waitForTimeout(800);
}

async function main() {
  let version;
  try {
    version = await (await fetch(`${CDP_URL}/json/version`, { signal: AbortSignal.timeout(3000) })).json();
  } catch {
    console.log("NO_CHROME: 9224番でChromeが起動していません。手動で以下を実行してください：");
    console.log("  bash tools/start_chrome_line_login.sh");
    process.exit(1);
  }
  console.log("CDP接続先:", version.Browser);

  const { chromium } = loadPlaywright();
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 30000 });
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  await page.goto(FORM_URL, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForTimeout(2000);

  const skipLink = page.locator("text=ログインせずにつづける").first();
  if ((await skipLink.count()) > 0) {
    await skipLink.click({ timeout: 10000 });
    await page.waitForTimeout(2000);
  }

  // 5段のカスタムselect：0=国 1=機種 2=サービス 3=カテゴリ 4=詳細
  await selectCustomDropdown(page, 1, "PC");
  await selectCustomDropdown(page, 2, "LINE Creators Market・LINEスタンプメーカー");
  await selectCustomDropdown(page, 3, CATEGORY_LABEL);
  await selectCustomDropdown(page, 4, DETAIL_LABEL);

  const radio = page.locator(`input[value="${PLACE_RADIO_VALUE}"]`);
  if ((await radio.count()) > 0) {
    await radio.click({ timeout: 8000, force: true });
    await page.waitForTimeout(1000);
  }

  console.log("フォームを開き、カテゴリ・詳細まで選択しました。");
  console.log("自由記述欄の中身は screenshots で目視確認し、必要なら手で調整してください。");
  console.log("送信ボタンは押していません。URL:", page.url());

  await page.screenshot({ path: "/tmp/line_inquiry_prepared.png", fullPage: true });
  console.log("スクショ: /tmp/line_inquiry_prepared.png");
}

main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
