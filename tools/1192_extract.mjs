// 1192番：曲データ（coverGuide.ts）から「アーティスト・曲名（生の題名と、画面に出る整えた題名）」を抜き出す。
// 使い方: node --experimental-strip-types tools/1192_extract.mjs <joy-relief-stationを展開した場所> <出力json>
// 整え方は joy-relief-station の src/lib/songTitleTidy.ts をそのまま使う（画面と同じ文字列にするため）。
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const [root, outP] = process.argv.slice(2);
const { tidySongTitle } = await import(pathToFileURL(path.join(root, "src/lib/songTitleTidy.ts")).href);
const src = fs.readFileSync(path.join(root, "src/lib/coverGuide.ts"), "utf8").split("\n");
const str = (l, k) => { const m = new RegExp(`\\b${k}: ("(?:[^"\\\\]|\\\\.)*")`).exec(l); return m ? JSON.parse(m[1]) : undefined; };
let artist = null; const out = [];
for (const l of src) {
  if (/^  \{ id: "/.test(l) && / name: "/.test(l)) {
    const al = /aliases: (\[[^\]]*\])/.exec(l);
    let aliases = []; try { aliases = al ? JSON.parse(al[1]) : []; } catch {}
    artist = { id: str(l, "id"), name: str(l, "name"), aliases };
    continue;
  }
  if (artist && /^    \{ id: "/.test(l) && / title: "/.test(l)) {
    const raw = str(l, "title"); if (raw === undefined) continue;
    out.push({ a: artist.id, an: artist.name, id: str(l, "id"), raw, tidy: tidySongTitle(raw, { name: artist.name, aliases: artist.aliases }), cv: /\boriginalRef:/.test(l) });
  }
}
// 特集「心を震わせる弾き語り」の曲名（曲データの外にある分）
const hk = path.join(root, "src/lib/hikigatariSongs.ts");
if (fs.existsSync(hk)) {
  const t = fs.readFileSync(hk, "utf8");
  for (const m of t.matchAll(/artist: ("(?:[^"\\]|\\.)*"),\s*\n\s*title: ("(?:[^"\\]|\\.)*")/g)) {
    const raw = JSON.parse(m[2]);
    out.push({ a: "hikigatari", an: JSON.parse(m[1]), id: "hk", raw, tidy: raw });
  }
}
fs.writeFileSync(outP, JSON.stringify(out));
console.log("songs", out.length);
