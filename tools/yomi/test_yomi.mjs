// 読み辞書の自動テスト。0円・ネットに出ない。
// 「案内人に実際に渡る文字列」まで組み立てて、King Gnu がカタカナで渡ることを確かめる。
// 実行: node tools/yomi/test_yomi.mjs
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "share/yomi/yomi.js"), "utf8"), sandbox);
const Y = sandbox.window.TAMAGO_YOMI;

let ng = 0;
const ok = (cond, label, got) => {
  console.log(`${cond ? "OK  " : "NG  "} ${label}${got === undefined ? "" : `  → ${got}`}`);
  if (!cond) ng++;
};

// ── 1. 店主が実際に聞いて間違っていた名前 ─────────────────
ok(Y.of("King Gnu") === "キングヌー", 'King Gnu の読み', Y.of("King Gnu"));
ok(Y.of("YOASOBI") === "ヨアソビ", 'YOASOBI の読み', Y.of("YOASOBI"));
ok(Y.of("Official髭男dism") === "オフィシャルヒゲダンディズム", 'Official髭男dism の読み', Y.of("Official髭男dism"));
ok(Y.of("RADWIMPS") === "ラッドウィンプス", 'RADWIMPS の読み', Y.of("RADWIMPS"));
ok(Y.of("BUMP OF CHICKEN") === "バンプ・オブ・チキン", 'BUMP OF CHICKEN の読み', Y.of("BUMP OF CHICKEN"));
ok(Y.of("ONE OK ROCK") === "ワンオクロック", 'ONE OK ROCK の読み', Y.of("ONE OK ROCK"));
ok(Y.of("米津玄師") === "ヨネヅケンシ", '米津玄師 の読み（当て字。形態素解析だけだとヨネツゲンシで外す）', Y.of("米津玄師"));
ok(Y.of("ヨルシカ") === "ヨルシカ", 'ヨルシカ の読み', Y.of("ヨルシカ"));

// ── 2. 指示文に読みが載っているか ────────────────────────
const ins = Y.instruction();
ok(ins.includes("King Gnu=キングヌー"), "指示文に King Gnu=キングヌー が入っている");
ok(ins.includes("英語読みに直さない"), "指示文に「英語読みに直さない」が入っている");

// ── 3. 検索結果に読みが付くか（案内人へ返る JSON そのもの）────
const result = Y.decorate({
  id: "king-gnu", name: "King Gnu",
  songs: [{ id: "hakujitsu", title: "白日" }, { id: "teenager-forever", title: "Teenager Forever" }],
});
ok(result.yomi === "キングヌー", "検索結果に yomi が付く", result.yomi);
ok(result.name === "King Gnu", "元の name は壊していない", result.name);
ok(result.songs[0].titleYomi === "ハクジツ", "曲名にも読みが付く", result.songs[0].titleYomi);

// ── 4. 案内人へ実際に送る payload を組み立てて確認 ───────────
const BASE = ["あなたは「ごきげん補給所」の案内人です。名前はアイリス。"].join("\n");
const payload = JSON.stringify({
  session: { type: "realtime", model: "gpt-realtime",
             instructions: BASE + "\n" + Y.instruction() },
});
ok(payload.includes("キングヌー"), "音声APIへ送る本文にカタカナの「キングヌー」が入っている");
const fnOut = JSON.stringify(Y.decorate(result));
ok(fnOut.includes('"yomi":"キングヌー"'), "function_call_output にも yomi が入って返る");

// ── 5. 辞書の健全性 ───────────────────────────────────────
const KATA = /^[゠-ヿーー・\s]+$/;
const bad = Object.entries(Y.artists).filter(([, v]) => !KATA.test(v));
ok(bad.length === 0, `辞書 ${Object.keys(Y.artists).length} 件がすべてカタカナ`, bad.slice(0, 3).join(","));
ok(Object.keys(Y.hot).length > 100, `指示文に固定する名前の数 ${Object.keys(Y.hot).length}`);

console.log(ng === 0 ? "\n全部通りました。" : `\n${ng} 件おちました。`);
process.exit(ng === 0 ? 0 : 1);
