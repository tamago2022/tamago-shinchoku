#!/usr/bin/env node
/**
 * 1165番【本番サーバー関数の口】joy-relief-station 本番の server function を叩く。
 *
 * なぜ必要か：曲ページの「この曲の関連動画」は本番DB(admin_song_overrides.related_videos)に
 * 入っているもので、リポジトリを直してもページは変わらない。本番には既に
 * adminAddRelatedVideo / searchYouTubeCandidates が生きているので、それを直接呼ぶ。
 * （デプロイ不要・service_roleはサーバー側が持っている）
 *
 * 落ちても続きから：1本ごとに台帳(--ledger)へ追記し、次に走ったとき済みは飛ばす。
 * 通信が切れた1本は3回まで待って再送する（前のセッションは1本のECONNRESETで全部止まった）。
 *
 * 使い方:
 *   node tools/1165_serverfn.mjs <functionId> '<payloadJSON>'
 *   node tools/1165_serverfn.mjs --file <注文票.json> [--ledger <台帳.jsonl>]
 *
 * 注文票の形: [{ "name":"見出し", "id":"<64桁>", "data":{...} }, ...]
 * 合言葉は data.password に入れる（呼ぶ側が入れる。ここには書かない）。
 */
import fs from "node:fs";

const SEROVAL_CANDIDATES = [
  "/Users/mac/Desktop/joy-relief-station/node_modules/seroval/dist/index.js",
  "/Users/mac/Desktop/tamago-shinchoku/status/1147/src_main/node_modules/seroval/dist/index.js",
];
let toJSONAsync = null;
for (const p of SEROVAL_CANDIDATES) {
  if (!fs.existsSync(p)) continue;
  try {
    ({ toJSONAsync } = await import(p));
    if (toJSONAsync) break;
  } catch {
    /* 次を試す */
  }
}
if (!toJSONAsync) {
  console.error("seroval が見つからない:\n" + SEROVAL_CANDIDATES.join("\n"));
  process.exit(2);
}

const BASE = process.env.JRS_BASE || "https://joy-relief-station.lovable.app";

async function callOnce(id, data) {
  const body = JSON.stringify(await toJSONAsync({ data }));
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 30000);
  try {
    const res = await fetch(`${BASE}/_serverFn/${id}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-tsr-serverFn": "true",
        accept: "application/json",
      },
      body,
      signal: ac.signal,
    });
    const text = await res.text();
    return { http: res.status, text };
  } finally {
    clearTimeout(t);
  }
}

async function call(id, data) {
  let last = null;
  for (let i = 0; i < 3; i++) {
    try {
      return await callOnce(id, data);
    } catch (e) {
      last = String(e?.cause?.code || e?.name || e).slice(0, 80);
      await new Promise((s) => setTimeout(s, 1500 * (i + 1)));
    }
  }
  return { http: 0, text: "通信できなかった: " + last };
}

const args = process.argv.slice(2);
let jobs = [];
let ledgerPath = null;
if (args[0] === "--file") {
  const j = JSON.parse(fs.readFileSync(args[1], "utf8"));
  jobs = Array.isArray(j) ? j : [j];
  const li = args.indexOf("--ledger");
  if (li > 0) ledgerPath = args[li + 1];
} else {
  jobs = [{ id: args[0], data: JSON.parse(args[1]) }];
}

// 済みを読む（同じ名前で ok が付いているものは飛ばす）
const sumi = new Set();
if (ledgerPath && fs.existsSync(ledgerPath)) {
  for (const ln of fs.readFileSync(ledgerPath, "utf8").split("\n")) {
    if (!ln.trim()) continue;
    try {
      const d = JSON.parse(ln);
      if (d.ok) sumi.add(d.name);
    } catch {
      /* 壊れた行は無視 */
    }
  }
}

let ok = 0;
let ng = 0;
let tobashita = 0;
for (const job of jobs) {
  const name = job.name || JSON.stringify(job.data).slice(0, 60);
  if (sumi.has(name)) {
    tobashita++;
    continue;
  }
  const r = await call(job.id, job.data);
  const good = r.http === 200 && /"ok"/.test(r.text);
  const safe = { ...job.data };
  if (safe.password) safe.password = "***";
  const rec = {
    at: new Date().toISOString(),
    name,
    ok: good,
    http: r.http,
    data: safe,
    body: r.text.slice(0, 400),
  };
  if (ledgerPath) fs.appendFileSync(ledgerPath, JSON.stringify(rec) + "\n");
  console.log(`${good ? "○" : "×"} ${name} http=${r.http} ${good ? "" : r.text.slice(0, 200)}`);
  if (good) ok++;
  else ng++;
  await new Promise((s) => setTimeout(s, 600));
}
console.log(`入った=${ok} 失敗=${ng} 済みで飛ばした=${tobashita}`);
process.exit(ng ? 1 : 0);
