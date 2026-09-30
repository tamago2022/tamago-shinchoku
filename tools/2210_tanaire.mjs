#!/usr/bin/env node
/**
 * 2210番【投げ込み箱 → 本番の棚】鍵をMacに置かずに入れる係（Mac側の半分）。
 *
 * ■ なぜこの道か（2026-10-01・実測で決めた）
 *   前の道（tools/nagekomi_shelf.py）は Supabase REST を直接叩くので service_role 鍵が要る。
 *   Macには無い（joy-relief-station/.env.local の SUPABASE_SERVICE_ROLE_KEY は空＝実測）。
 *   鍵を貼らせる＝たまごさんを動かすので禁止。
 *
 *   並べた道：
 *     ① Supabase Edge Function 新設（SUPABASE_SERVICE_ROLE_KEY は実行環境に既定で入る）
 *        → GitHubにpushしても Edge Function は本番に出ない（#1386：4日届かなかった実測）。
 *          CLIデプロイの鍵も無い。Lovableエージェントは禁止。→ 不採用
 *     ② Lovable Cloud の管理画面で鍵を見る／表を直接いじる → 人の手が要る。不採用
 *     ③ 既存の管理用サーバー関数（adminAddStockFromUrl 等）を合言葉で叩く
 *        → 実測で Unauthorized（合言葉が変わっている）。合言葉を探して使うのはやらない。不採用
 *     ④ 本番に「投げ込み箱の公開台帳を自分で読みに行って棚へ入れる」サーバー関数を1本足す
 *        （joy-relief-station: src/lib/nagekomiSync.functions.ts）。
 *        サーバー関数は main→公開ボタンで本番に出る（kohyou_osu で実測済みの道）。
 *        鍵はサーバー側。入力を受け取らないので、誰が叩いても入るのは箱に投げた分だけ。★採用
 *
 * ■ この係がやること
 *   okuru … status/nagekomi.jsonl から「たまごさんが投げた分」だけを
 *           status/public/nagekomi_okuru.json に書き出す（機械の試し投げは入れない。ひとことは出さない）
 *   yobu  … 本番の nagekomiSync を呼び、入った分を status/nagekomi_ireta.jsonl に控える
 *
 * 使い方:
 *   node tools/2210_tanaire.mjs okuru
 *   node tools/2210_tanaire.mjs yobu
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const LEDGER = path.join(REPO, "status", "nagekomi.jsonl");
const IRETA = path.join(REPO, "status", "nagekomi_ireta.jsonl");
const OKURU = path.join(REPO, "status", "public", "nagekomi_okuru.json");
const OUT = path.join(REPO, "status", "public", "nagekomi_shelf.json");
const BASE = process.env.JRS_BASE || "https://joy-relief-station.lovable.app";
const FN_ID = crypto
  .createHash("sha256")
  .update("src/lib/nagekomiSync.functions.ts--nagekomiSync_createServerFn_handler")
  .digest("hex");

const now = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 16).replace("T", " ");
const readJsonl = (p) =>
  fs.existsSync(p)
    ? fs.readFileSync(p, "utf8").split("\n").filter((l) => l.trim()).map((l) => {
        try { return JSON.parse(l); } catch { return null; }
      }).filter(Boolean)
    : [];

function okuru() {
  const rows = readJsonl(LEDGER);
  const items = [];
  const seen = new Set();
  for (const r of rows) {
    if (String(r.nageta || "") === "test" || r.test === true) continue;
    const url = String(r.url || "").trim();
    if (!/^https:\/\//.test(url)) continue;
    const shelves = Array.isArray(r.shelves) && r.shelves.length
      ? r.shelves.map((s) => ({ id: s?.id || null, title: s?.title || null }))
      : (r.shelfId || r.shelf) ? [{ id: r.shelfId || null, title: r.shelf || null }] : [];
    if (!shelves.length) continue;          // 行き先未定は棚へ入れない（受付一覧に「行き先未定」で残る）
    const key = url + "|" + JSON.stringify(shelves);
    if (seen.has(key)) continue;
    seen.add(key);
    const title = String(r.title || "").trim();
    const okTitle = title && !/^https?:\/\//.test(title) && !/pic\.twitter\.com|&mdash;/.test(title);
    items.push({ id: r.id, url, title: okTitle ? title : null, shelves });
  }
  const out = { at: now(), note: "2210番：投げ込み箱のうち、たまごさんが投げて行き先が決まっている分だけ（試し投げは入れない）", items };
  fs.writeFileSync(OKURU, JSON.stringify(out, null, 1));
  console.log(JSON.stringify({ okuru: items.length, ids: items.map((x) => x.id) }));
}

async function yobu() {
  const res = await fetch(`${BASE}/_serverFn/${FN_ID}`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-tsr-serverFn": "true", accept: "application/json" },
    body: await body0(),
  });
  const text = await res.text();
  console.log("HTTP", res.status, "fn", FN_ID.slice(0, 12));
  console.log(text.slice(0, 6000));
  const sum = { ranAt: now(), bin: "2210", via: "本番サーバー関数 nagekomiSync（鍵はサーバー側）", http: res.status, raw: text.slice(0, 4000), red: [], ireta: [] };
  // 返り値（seroval）から、入った棚を拾って控える（受付一覧が読む形）
  try {
    const done = [];
    const re = /"id".*?/g; // 形が崩れても落ちないよう、下で素直にほどく
    void re;
    const val = unser(JSON.parse(text.split("\n").find((l) => l.trim())));
    const r = val?.result ?? val;
    for (const d of r?.done || []) {
      const ok = (d.shelves || []).filter((s) => s.ok);
      if (!ok.length) { sum.red.push(`${d.id}: ${d.why || JSON.stringify(d.shelves).slice(0, 200)}`); continue; }
      const rec = { bin: "2210", at: now(), id: d.id, nagekomiId: d.id, stockId: d.stockId, madeStock: !!d.madeStock,
        ref: d.url, shelfId: ok[0].page, shelf: ok[0].title, world: ok[0].world, pickId: ok[0].pickId || null,
        hokaShelves: ok.slice(1).map((s) => ({ shelfId: s.page, shelf: s.title, world: s.world })),
        pickStatus: "candidate", via: "nagekomiSync", already: !!ok[0].already };
      done.push(rec);
    }
    const had = new Set(readJsonl(IRETA).filter((x) => x.via === "nagekomiSync").map((x) => x.id));
    for (const rec of done) if (!had.has(rec.id)) fs.appendFileSync(IRETA, JSON.stringify(rec) + "\n");
    sum.ireta = done;
  } catch (e) {
    sum.red.push("返事が読めない: " + String(e).slice(0, 200));
  }
  sum.iretaCount = sum.ireta.length;
  sum.ok = res.status === 200 && !sum.red.length;
  sum.totalYen = 0;
  fs.writeFileSync(OUT, JSON.stringify(sum, null, 1));
  process.exit(res.status === 200 ? 0 : 1);
}

// 画面から呼んだときと同じ形（seroval）で送る。無ければ素のJSONで送る
async function body0() {
  for (const p of ["/Users/mac/Desktop/joy-relief-station/node_modules/seroval/dist/index.js",
                   path.join(REPO, "status/1147/src_main/node_modules/seroval/dist/index.js")]) {
    if (fs.existsSync(p)) {
      try { const s = await import(p); return JSON.stringify(await s.toJSONAsync({ data: undefined })); } catch { /* 次 */ }
    }
  }
  return JSON.stringify({});
}

const CONST = { 1: undefined, 2: true, 3: false, 4: null };
function unser(n, refs = new Map()) {
  if (n === null || typeof n !== "object") return n;
  if (n.t === 0 || n.t === 1) return n.s;
  if (n.t === 2) return CONST[n.s];
  if (n.t === 9) { const a = []; if (n.i !== undefined) refs.set(n.i, a); for (const x of n.a || []) a.push(unser(x, refs)); return a; }
  if (n.t === 10 || n.t === 11) { const o = {}; if (n.i !== undefined) refs.set(n.i, o); (n.p?.k || []).forEach((k, i) => (o[k] = unser(n.p.v[i], refs))); return o; }
  if (n.i !== undefined && refs.has(n.i)) return refs.get(n.i);
  return n.s ?? null;
}

const mode = process.argv[2];
if (mode === "okuru") okuru();
else if (mode === "yobu") await yobu();
else { console.log("okuru | yobu"); process.exit(2); }
