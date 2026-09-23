#!/usr/bin/env node
// 1154号：受付。完了条件が1行で書けていない依頼は、ここで弾いて発車させない。
//
//   受ける： node tools/stop_kanmon/ukeire.mjs uke <id> "<題名>" <本番URL> <最低バイト> <最低差分>
//   発車　： node tools/stop_kanmon/ukeire.mjs hassha <id>
//   見る　： node tools/stop_kanmon/ukeire.mjs miru
//   下ろす： node tools/stop_kanmon/ukeire.mjs orosu <id> "<理由>"   ← 引き継ぎに回す
//
// 機械が弾くので、口約束（「あとで決めます」）では発車できない。

import { execFileSync } from "node:child_process";
import { write, jotai, joukenOK, REPO, kensa } from "./kanmon.mjs";

const [, , cmd, ...rest] = process.argv;
const sha = () =>
  execFileSync("git", ["rev-parse", "HEAD"], { cwd: REPO, encoding: "utf8" }).trim();

if (cmd === "uke") {
  const [id, title, url, minBytes, minDiff] = rest;
  const done = { url, min_bytes: Number(minBytes), min_diff: Number(minDiff) };
  const bad = joukenOK(done);
  if (!id || !title || bad) {
    console.error(
      `発車させない。完了条件が1行で書けていない：${bad ?? "id／題名が無い"}\n` +
        `書き方： uke <id> "<題名>" <https://…の本番URL> <最低バイト> <最低差分>`,
    );
    process.exit(1);
  }
  write({ id, event: "ukeire", title, done, base_sha: sha() });
  console.log(`受けた：${id}「${title}」／完了＝${url} が200・${done.min_bytes}バイト以上・差分${done.min_diff}件以上`);
} else if (cmd === "hassha") {
  const [id, h] = rest;
  const c = jotai().find((x) => x.id === id);
  if (!c || joukenOK(c.done)) {
    console.error(`発車させない：${id} は受付が通っていない（完了条件が無い）`);
    process.exit(1);
  }
  write({ id, event: "hassha", base_sha: sha(), deadline_h: Number(h) || 6 });
  console.log(`発車：${id}。終わろうとしても、完了条件を満たすまでStopフックが止める。`);
} else if (cmd === "orosu") {
  const [id, why] = rest;
  write({ id, event: "hikitsugi", why: why || "手で下ろした" });
  console.log(`下ろした：${id}`);
} else if (cmd === "miru") {
  for (const c of jotai()) {
    const st = c.kanryou ? "完了" : c.hikitsugi ? "引き継ぎ" : c.hassha ? "走行中" : "受付のみ";
    console.log(`${c.id}\t${st}\tブロック${c.blocks}回\t${c.title ?? ""}\t${c.done?.url ?? ""}`);
  }
} else if (cmd === "kanryou") {
  // 外で測った実測値だけを受け取って完了にする。条件を満たさない数字は受け付けない。
  // （このサンドボックスは外に出られないので、ブラウザで測った status/bytes をここに入れる）
  const [id, status, bytes, diff, via] = rest;
  const c = jotai().find((x) => x.id === id);
  if (!c) {
    console.error(`そんな案件は無い：${id}`);
    process.exit(1);
  }
  const proof = { url: c.done.url, status: Number(status), bytes: Number(bytes), diff: Number(diff), via: via || "実測" };
  if (proof.status !== 200 || proof.bytes < c.done.min_bytes || proof.diff < c.done.min_diff) {
    console.error(`完了にさせない：実測が条件に届いていない ${JSON.stringify(proof)}`);
    process.exit(1);
  }
  write({ id, event: "kanryou", hook: "手", proof });
  console.log(`完了：${id} ${JSON.stringify(proof)}`);
} else if (cmd === "kensa") {
  const [id] = rest;
  const c = jotai().find((x) => x.id === id);
  console.log(JSON.stringify(await kensa(c), null, 2));
} else {
  console.log("uke / hassha / orosu / miru / kensa");
}
