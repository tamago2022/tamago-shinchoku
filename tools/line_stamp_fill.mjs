#!/usr/bin/env node
/**
 * 883番：LINE Creators Marketへの申請文言・自動入力機（769番の続き）。
 *
 * 目的：たまごさんに15項目×3キャラを手で貼らせない。
 * ~/.tamago/chrome-line（CDP 9224）は、たまごさん本人が
 * tools/start_chrome_line_login.sh を1回実行してLINEにログインした
 * "本人専用" プロファイル。ログインという認証行為だけは代行不能
 * （本人にしかできない）なので、この道具はそこから先を全部自動化する。
 *
 * 安全設計：
 *   - ログインが確認できない場合は、フォームに一切触れず即座に停止する
 *     （NO_CHROME / NOT_LOGIN を正直にJSONで返すだけ）。
 *   - Request（審査リクエスト）ボタンは絶対に押さない。このスクリプトの
 *     責任範囲は「入力して保存」まで。押すのは別スクリプト／たまごさんの意思。
 *   - 入力欄は正確なCSSセレクタが未確定（未ログインのため実地調査できて
 *     いない）ため、ラベルテキストに基づく複数戦略のフォールバックで探す。
 *     見つからなかった項目は失敗として記録し、黙って諦めない。
 *
 * 2026-09-16 是正（案件#883・1回目FAIL対応）で追加調査したこと：
 *   ログイン不要な https://creator.line.me/ja/ トップページをheadless Chromeで
 *   一度だけ開きDOM構造を覗いた（742/769番と同じ安全方式：一時プロファイル→
 *   CDP接続→終了後SIGKILL＆プロファイル削除）。結果、トップページは
 *   #root/#next等の一般的なSPAルートIDを持たず、チェックボックス1個以外に
 *   input/textareaが存在しなかった（＝申請フォームはログイン後にしか描画され
 *   ない）。つまりトップページの下調べでは fillByLabel の3戦略が的外れで
 *   ないかを確認できなかった。これは「調べたが分からなかった」という正直な
 *   結果であり、フォーム自体の検証にはたまごさん本人のログインが必須という
 *   結論を裏付けるものだった。下の pageStats（総input/textarea数）は、
 *   ログイン後に初めて実行された時、原因の切り分けをしやすくするために追加。
 *
 * 使い方：
 *   node tools/line_stamp_fill.mjs <slug> [--shot <出力png絶対パス>] [--plan A|B]
 *   例）node tools/line_stamp_fill.mjs rashikoru --shot /tmp/rashikoru-filled.png
 *
 * 出力：標準出力へ1行JSON
 *   {state, filled:[{field,value}], failed:[{field,reason}], screenshot, url}
 */
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const CDP_URL = "http://127.0.0.1:9224";
const CONFIG_DIR = path.join(path.dirname(new URL(import.meta.url).pathname), "line_stamp_configs");

function parseArgs(argv) {
  const [slug, ...rest] = argv;
  const out = { slug, shot: null, plan: "A" };
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === "--shot") out.shot = rest[++i];
    if (rest[i] === "--plan") out.plan = rest[++i];
  }
  return out;
}

function loadConfig(slug) {
  const file = path.join(CONFIG_DIR, `${slug}.json`);
  if (!fs.existsSync(file)) throw new Error(`config無し: ${file}`);
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

// LINE Creators Marketの入力欄フォームに合わせた「日本語ラベルの候補」。
// 実際のDOM構造は未ログインのため未確認 → 1つのフィールドに複数の言い回しを
// 用意し、上から順に一致するlabelを探す（見出しがEnglish UIの可能性も含める）。
function fieldPlan(cfg, plan) {
  const suffix = plan === "B" ? "_planB" : "";
  return [
    { key: "title_en", labels: ["Title (English)", "タイトル（英語）", "Title(English)"], value: cfg[`title_en${suffix}`] ?? cfg.title_en },
    { key: "title_ja", labels: ["Title (Japanese)", "タイトル（日本語）"], value: cfg[`title_ja${suffix}`] ?? cfg.title_ja },
    { key: "desc_en", labels: ["Description (English)", "説明文（英語）"], value: cfg[`desc_en${suffix}`] ?? cfg.desc_en },
    { key: "desc_ja", labels: ["Description (Japanese)", "説明文（日本語）"], value: cfg[`desc_ja${suffix}`] ?? cfg.desc_ja },
    { key: "creator_en", labels: ["Creator name (English)", "クリエイター名（英語）"], value: cfg.creator_en },
    { key: "creator_ja", labels: ["Creator name (Japanese)", "クリエイター名（日本語）"], value: cfg.creator_ja },
    { key: "copyright", labels: ["Copyright", "コピーライト", "コピーライト表記"], value: cfg.copyright },
  ];
}

async function findLoginState(ctx) {
  const page = await ctx.newPage();
  try {
    // 2026-09-16是正（案件#883）：/ja/dashboard は実在しないURL（404）だったため、
    // 旧ロジックは404ページを常にLOGGED_INと誤判定するバグがあった。line_login_check.mjs
    // と同じ「マイページ」リンクのhref判定へ修正（/signup/line_authなら未ログイン）。
    await page.goto("https://creator.line.me/ja/", { waitUntil: "domcontentloaded", timeout: 20000 });
    await page.waitForTimeout(1200);
    const url = page.url();
    const mypageHref = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll("a")).find((el) => el.textContent.includes("マイページ"));
      return a ? a.getAttribute("href") : null;
    });
    const loggedIn = !!mypageHref && !mypageHref.includes("/signup/line_auth");
    return { loggedIn, url, mypageHref, page };
  } catch (e) {
    await page.close().catch(() => {});
    throw e;
  }
}

// ラベルテキスト→隣接input/textareaを複数戦略で探す。
// 戦略1: Playwrightの getByLabel（<label for>/aria-labelledby対応）
// 戦略2: テキストを含む要素の直後の input/textarea 兄弟
// 戦略3: placeholder一致
async function fillByLabel(page, labels, value) {
  // 失敗時の切り分け用に、どのラベル候補が何個見つかったか（strategy別）を残す。
  const diagnostics = [];
  for (const label of labels) {
    const perLabel = { label, getByLabelCount: 0, textMatchFound: false, placeholderCount: 0 };
    // 戦略1
    try {
      const loc = page.getByLabel(label, { exact: false });
      const count = await loc.count();
      perLabel.getByLabelCount = count;
      if (count > 0) {
        await loc.first().fill(value);
        return { ok: true, strategy: "getByLabel", label, diagnostics: [...diagnostics, perLabel] };
      }
    } catch {
      /* 次の戦略へ */
    }
    // 戦略2: ラベルらしきテキストを含む要素の近傍input
    try {
      const handle = await page.evaluateHandle((labelText) => {
        const all = Array.from(document.querySelectorAll("label, span, div, p"));
        const hit = all.find((el) => el.textContent && el.textContent.trim().startsWith(labelText));
        if (!hit) return null;
        // 同じ行・親要素内のinput/textareaを探す
        const scope = hit.closest("div") || hit.parentElement;
        return scope ? scope.querySelector("input, textarea") : null;
      }, label);
      const el = handle.asElement();
      perLabel.textMatchFound = !!el;
      if (el) {
        await el.fill(value);
        return { ok: true, strategy: "sibling", label, diagnostics: [...diagnostics, perLabel] };
      }
    } catch {
      /* 次の戦略へ */
    }
    // 戦略3: placeholder
    try {
      const loc = page.locator(`input[placeholder*="${label}"], textarea[placeholder*="${label}"]`);
      const count = await loc.count();
      perLabel.placeholderCount = count;
      if (count > 0) {
        await loc.first().fill(value);
        return { ok: true, strategy: "placeholder", label, diagnostics: [...diagnostics, perLabel] };
      }
    } catch {
      /* 諦める */
    }
    diagnostics.push(perLabel);
  }
  return { ok: false, diagnostics };
}

// 失敗時、ページ全体のinput/textarea総数を取得（「ラベルが見つからない」のか
// 「フォームがまだ描画されていない」のかの切り分け用）。
async function pageFieldStats(page) {
  try {
    return await page.evaluate(() => ({
      inputCount: document.querySelectorAll("input").length,
      textareaCount: document.querySelectorAll("textarea").length,
    }));
  } catch {
    return { inputCount: null, textareaCount: null };
  }
}

async function main() {
  const { slug, shot, plan } = parseArgs(process.argv.slice(2));
  if (!slug) {
    console.log(JSON.stringify({ state: "ERROR", detail: "使い方: node tools/line_stamp_fill.mjs <slug> [--shot path]" }));
    process.exitCode = 1;
    return;
  }

  let version;
  try {
    version = await (await fetch(`${CDP_URL}/json/version`, { signal: AbortSignal.timeout(3000) })).json();
  } catch {
    console.log(JSON.stringify({
      state: "NO_CHROME",
      detail: "9224番でChromeが起動していません。たまごさんが tools/start_chrome_line_login.sh を実行しログインするまで、この先には進めません（ログインは本人にしかできない認証行為のため）。",
    }));
    return;
  }

  const cfg = loadConfig(slug);
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];
  let page;
  try {
    const login = await findLoginState(ctx);
    page = login.page;
    if (!login.loggedIn) {
      console.log(JSON.stringify({
        state: "NOT_LOGIN",
        url: login.url,
        mypageHref: login.mypageHref,
        browser: version.Browser || null,
        detail: "Chromeは起動していますがLINEに未ログインです。フォームには一切触れず停止しました。",
      }));
      return;
    }

    // ここから先はログイン済みの場合のみ実行される（今回は未検証区間）。
    // stamp_idが分かっていれば編集画面、無ければマイページのまま
    // 新規作成導線を人力で辿る前提とし、まずは今いる画面のフィールドを埋める。
    if (cfg.stamp_id) {
      const editUrl = `https://creator.line.me/ja/stamp/${cfg.stamp_id}/edit`;
      await page.goto(editUrl, { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(1500);
    }

    const plan_ = fieldPlan(cfg, plan);
    const filled = [];
    const failed = [];
    for (const f of plan_) {
      if (!f.value) {
        failed.push({ field: f.key, reason: "config側に値が無い" });
        continue;
      }
      const result = await fillByLabel(page, f.labels, f.value);
      if (result.ok) filled.push({ field: f.key, strategy: result.strategy, label: result.label });
      else
        failed.push({
          field: f.key,
          reason: "ラベルに一致する入力欄が見つからなかった",
          triedLabels: f.labels,
          diagnostics: result.diagnostics,
        });
    }

    // 失敗が1件でもあれば、ページ全体のinput/textarea総数も添える
    // （「ラベルが違う」のか「フォームがまだ描画されていない」のかの切り分け用）。
    const pageStats = failed.length > 0 ? await pageFieldStats(page) : null;

    let screenshot = null;
    if (shot) {
      const dir = path.dirname(shot);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      await page.screenshot({ path: shot, fullPage: true });
      screenshot = shot;
    }

    console.log(JSON.stringify({
      state: filled.length > 0 && failed.length === 0 ? "FILLED" : "PARTIAL",
      url: page.url(),
      filled,
      failed,
      pageStats,
      screenshot,
      note: "Requestボタンは押していません（このスクリプトの責任範囲外）。",
    }, null, 0));
  } finally {
    if (page) await page.close().catch(() => {});
  }
}

main().catch((e) => {
  console.log(JSON.stringify({ state: "ERROR", detail: e.message }));
  process.exitCode = 1;
});
