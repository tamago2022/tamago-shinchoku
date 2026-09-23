// 1131番 — 3本の結果を1つにまとめ、昨日の数と並べて status/1131_kowareteru.json に書く。
// たまごさん：「上に『今いくつ壊れているか』の数字だけ。昨日◯件 → 今日◯件。」
import fs from "fs";
import path from "path";

const WORK = process.cwd();
const REPO = path.resolve(WORK, "..", "..");
const OUT = path.join(REPO, "status", "1131_kowareteru.json");
const LOG = path.join(REPO, "status", "1131_suii.jsonl");

const J = (f) => JSON.parse(fs.readFileSync(path.join(WORK, f), "utf8"));
const f = J("flow.json");
const e0 = fs.existsSync(path.join(WORK, "era0.json")) ? J("era0.json") : null;
const e1 = fs.existsSync(path.join(WORK, "era1.json")) ? J("era1.json") : null;
const e = e0 && e1
  ? { nogate: [...e0.nogate, ...e1.nogate], gap: [...e0.gap, ...e1.gap], pages: e0.pages + e1.pages, shown: e0.shown + e1.shown }
  : J("era.json");
const r = J("rest.json");

const pages = (a) => new Set(a.map((x) => x.page)).size;

const shurui = [
  { k: "flow_nobasis", label: "「この流れで、もう一本」に根拠が無い（同じ棚に入っているだけ）", n: f.nobasis.length, pages: pages(f.nobasis), tani: "枚" },
  { k: "flow_missing", label: "「この流れで」の行き先が名簿に存在しない（押しても無い）", n: f.missing.length, tani: "枚" },
  { k: "era_nogate", label: "「同じ時代の曲」の年差チェックが素通り（その曲に年が無い）", n: e.nogate.length, pages: pages(e.nogate), tani: "枚" },
  { k: "era_gap", label: "「同じ時代」なのに年差15年超（年がある場合）", n: e.gap.length, tani: "枚" },
  { k: "linked_nosource", label: "既に繋いでいるのに出典URLが無い（★まず外す対象）", n: r.linked_nosource.length, tani: "件" },
  { k: "cover_candidate", label: "【裏取り待ち】曲名が同じ古い曲が棚に在る（※曲名一致は証拠ではない）", n: r.cover_candidate.length, tani: "件" },
  { k: "no_video", label: "動画IDが無い（開いても鳴らない）", n: r.no_video.length, tani: "曲" },
  { k: "no_year", label: "年が無い（「同じ時代」の門が効かなくなる元）", n: r.no_year.length, tani: "曲" },
  { k: "no_note", label: "紹介文が空", n: r.no_note.length, tani: "曲" },
  { k: "note_cut", label: "紹介文が途中で切れている", n: r.note_cut.length, tani: "曲" },
  { k: "note_spotify", label: "紹介文にSpotify表記が残っている", n: r.note_spotify.length, tani: "曲" },
  { k: "same_name", label: "同名アーティストが複数（別人混入のリスク）", n: r.same_name.length, tani: "組" },
];

const total = shurui.reduce((t, x) => t + x.n, 0);

// 昨日の数（前回の記録の最後の1行）
let kinou = null;
try {
  const lines = fs.readFileSync(LOG, "utf8").trim().split("\n").filter(Boolean);
  if (lines.length) kinou = JSON.parse(lines[lines.length - 1]);
} catch {}

const out = {
  asof: new Date().toISOString().slice(0, 16).replace("T", " "),
  total,
  shuruiCount: shurui.filter((x) => x.n > 0).length,
  kinou: kinou ? { asof: kinou.asof, total: kinou.total } : null,
  sa: kinou ? total - kinou.total : null,
  scope: { flowPages: f.pages, flowCards: f.picks, eraPages: e.pages, eraCards: e.shown },
  shurui,
  samples: {
    flow_nobasis: f.nobasis.slice(0, 40),
    flow_missing: f.missing.slice(0, 20),
    era_nogate: e.nogate.slice(0, 20),
    linked_nosource: r.linked_nosource.slice(0, 20),
    cover_candidate: r.cover_candidate.slice(0, 40),
    same_name: r.same_name,
    note_spotify: r.note_spotify,
    note_cut: r.note_cut.slice(0, 10),
  },
};

fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
fs.appendFileSync(LOG, JSON.stringify({ asof: out.asof, total, shurui: Object.fromEntries(shurui.map((x) => [x.k, x.n])) }) + "\n");
console.log(`合計 ${total} 件 ／ ${out.shuruiCount} 種類` + (out.sa !== null ? `（昨日 ${kinou.total} → 今日 ${total}／${out.sa >= 0 ? "+" : ""}${out.sa}）` : ""));
