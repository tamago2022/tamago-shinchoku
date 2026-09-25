#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【隠す表を関所に繋ぐ】本番のサイトマップ・検索から、隠すはずの2378件を実際に消す。

■ 何が起きていたか（2026-09-25 実測・ここが本当の原因）

  1140番の全曲検査は「再生できる動画が1本も無い曲」2,378件を
  src/lib/kanseiHidden.generated.ts という表に書き出していた。
  1132番の関所（src/lib/kansei.ts の isKansei）は**この表を読んでいなかった。**
  読んでいたのは棚の src/lib/worlds.ts だけ。
  だから：
    棚・おすすめ   → 消えていた
    サイトマップ・検索・アーティストの曲一覧 → **2,287件がそのまま出ていた**
  実測（本番のsitemap.xmlを叩いた）: 隠すはず2,383件のうち2,287件が居た。

  なぜ関所が読めなかったか：
    関所は「データの中身」だけで判定している（youtubeIdがある／死亡表に載っている）。
    ところが今回の2,378件は、**IDは入っているのにYouTube側で実際には再生できない**もの。
    これは oEmbed で叩かないと分からない（回線が要る＝ビルド時には分からない）。
    だから検査が先に叩いて表にした。その表を関所が読まなければ意味が無い。

■ 直し方（判定は1か所のまま）

  ① src/lib/kansei.ts … 隠す表を読む。key（"artist/song"）を渡されたら、表に載っていれば不合格。
  ② src/lib/coverGuide.ts … isSongPublishable が key を渡す。
  これだけで、同じ1本（isKansei）を通っている出口全部（検索・棚・おすすめ・
  この流れで・サイトマップ・アーティストの曲一覧）が一斉に隠れる。

  ★消していない。隠すだけ。
  ★戻し方（1行）: src/lib/kansei.ts の KANSEI_GATE を false にする。
"""
from __future__ import annotations
import base64, io, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import github_watch  # noqa: E402

GH_REPO = "tamago2022/joy-relief-station"
BRANCH = "main"
API = "https://api.github.com"
SHIRUSHI = "1144番【隠す表を関所に繋ぐ】"

MESSAGE = (
    "1144番【隠す表を関所に繋ぐ】サイトマップ・検索からも未完成の曲を出さない\n\n"
    "1140番の全曲検査が作った隠す表（kanseiHidden.generated.ts）を、\n"
    "関所（src/lib/kansei.ts の isKansei）が読むようにした。\n"
    "これまで表を読んでいたのは棚(worlds.ts)だけで、サイトマップと検索には\n"
    "2,287件がそのまま出ていた（本番のsitemap.xmlを叩いて実測）。\n\n"
    "データは1件も消していない（隠しているだけ）。動画が入れば次の生成で自動的に戻る。\n"
    "戻し方: src/lib/kansei.ts の KANSEI_GATE を false。"
)


def _req(method, url, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer %s" % token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "tamago-1144")
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── ①関所が隠す表を読む ─────────────────────────────────────────────
K_IMPORT_MOTO = 'import { videoReplacements } from "./videoReplacements.generated";'
K_IMPORT_ATO = K_IMPORT_MOTO + '''
// ★1144番【隠す表を関所に繋ぐ】1140番の全曲検査（oEmbedで実測）が作った表。
//   「IDは入っているのにYouTube側で再生できない」曲は、中身だけ見ても分からない。
//   回線が要るので、検査が先に叩いて表にしてある。関所はその表を読む。
import { KANSEI_HIDDEN_SONG_KEYS } from "./kanseiHidden.generated";'''

K_IFACE_MOTO = '''export interface KanseiInput {
  /** アーティスト名。空なら不合格（noName）。 */
  artistName?: string;'''
K_IFACE_ATO = '''export interface KanseiInput {
  /** アーティスト名。空なら不合格（noName）。 */
  artistName?: string;
  /**
   * ★1144番 "artistId/songId"。隠す表（kanseiHidden.generated）と突き合わせる鍵。
   * 渡さなければ表は見ない（既にある呼び出しを壊さないため）。
   */
  key?: string;'''

K_GATE_MOTO = '''export function isKansei(input: KanseiInput): boolean {
  if (!KANSEI_GATE) return true;
  const fault = kanseiFault(input);'''
K_GATE_ATO = '''export function isKansei(input: KanseiInput): boolean {
  if (!KANSEI_GATE) return true;
  // ★1144番 実測で「再生できる動画が1本も無い」と分かっている曲は、ここで落とす。
  //   これを入れるまで、サイトマップと検索には2,287件が出たままだった。
  if (input.key && KANSEI_HIDDEN_SONG_KEYS.has(input.key)) return false;
  const fault = kanseiFault(input);'''

# ── ②coverGuide が鍵を渡す ──────────────────────────────────────────
C_MOTO = '''export function isSongPublishable(artistId: string, song: CoverGuideSong): boolean {
  return isKansei({
    artistName: getArtist(artistId)?.name,
    song,
    curatedVideoIds: curatedVideoIdsForSong(artistId, song),
  });
}'''
C_ATO = '''export function isSongPublishable(artistId: string, song: CoverGuideSong): boolean {
  return isKansei({
    artistName: getArtist(artistId)?.name,
    song,
    curatedVideoIds: curatedVideoIdsForSong(artistId, song),
    // ★1144番 隠す表と突き合わせる鍵。これを渡すまでサイトマップ・検索が素通りだった。
    key: `${artistId}/${song.id}`,
  });
}'''

C_FAULT_MOTO = '''export function songKanseiFault(artistId: string, song: CoverGuideSong): KanseiFault | null {
  return kanseiFault({
    artistName: getArtist(artistId)?.name,
    song,
    curatedVideoIds: curatedVideoIdsForSong(artistId, song),
  });
}'''
C_FAULT_ATO = '''export function songKanseiFault(artistId: string, song: CoverGuideSong): KanseiFault | null {
  return kanseiFault({
    artistName: getArtist(artistId)?.name,
    song,
    curatedVideoIds: curatedVideoIdsForSong(artistId, song),
    key: `${artistId}/${song.id}`,
  });
}'''

NAOSU = {
    "src/lib/kansei.ts": [(K_IMPORT_MOTO, K_IMPORT_ATO), (K_IFACE_MOTO, K_IFACE_ATO),
                          (K_GATE_MOTO, K_GATE_ATO)],
    "src/lib/coverGuide.ts": [(C_MOTO, C_ATO), (C_FAULT_MOTO, C_FAULT_ATO)],
}


def run(dry=False):
    token = github_watch.gh_token()
    if not token:
        return {"ok": False, "log": ["GitHubの鍵が取れませんでした"]}
    log = []
    head = _req("GET", "%s/repos/%s/git/ref/heads/%s" % (API, GH_REPO, BRANCH), token)
    base_sha = head["object"]["sha"]
    log.append("いまの main = %s" % base_sha[:8])
    tree_all = _req("GET", "%s/repos/%s/git/trees/%s?recursive=1" % (API, GH_REPO, base_sha), token)
    sha_of = {e["path"]: e["sha"] for e in tree_all.get("tree", []) if e.get("type") == "blob"}

    okuru = {}
    for path, naoshi in NAOSU.items():
        if path not in sha_of:
            return {"ok": False, "log": log + ["mainに無いファイル: %s" % path]}
        got = _req("GET", "%s/repos/%s/git/blobs/%s" % (API, GH_REPO, sha_of[path]), token)
        body = base64.b64decode(got["content"]).decode("utf-8")
        if SHIRUSHI in body or "input.key && KANSEI_HIDDEN_SONG_KEYS" in body \
                or "key: `${artistId}/${song.id}`" in body:
            log.append("%s ← もう入っています" % path)
            continue
        for moto, ato in naoshi:
            n = body.count(moto)
            if n != 1:
                return {"ok": False, "log": log + [
                    "%s の当てる場所が %d個 見つかりました（1個でないので触りません）\n%s"
                    % (path, n, moto[:120])]}
            body = body.replace(moto, ato)
        okuru[path] = body
        log.append("%s ← 当てました" % path)

    if not okuru:
        log.append("★もう入っていました。何もしません。")
        return {"ok": True, "alreadyIn": True, "log": log}
    if dry:
        log.append("--dry-run なのでGitHubには書きません（送る予定: %s）" % ", ".join(okuru))
        return {"ok": True, "dryRun": True, "log": log}

    tree = []
    for p, b in sorted(okuru.items()):
        blob = _req("POST", "%s/repos/%s/git/blobs" % (API, GH_REPO), token,
                    {"content": b, "encoding": "utf-8"})
        tree.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    base_commit = _req("GET", "%s/repos/%s/git/commits/%s" % (API, GH_REPO, base_sha), token)
    new_tree = _req("POST", "%s/repos/%s/git/trees" % (API, GH_REPO), token,
                    {"base_tree": base_commit["tree"]["sha"], "tree": tree})
    commit = _req("POST", "%s/repos/%s/git/commits" % (API, GH_REPO), token,
                  {"message": MESSAGE, "tree": new_tree["sha"], "parents": [base_sha]})
    _req("PATCH", "%s/repos/%s/git/refs/heads/%s" % (API, GH_REPO, BRANCH), token,
         {"sha": commit["sha"], "force": False})
    log.append("★mainに入りました: %s" % commit["sha"][:8])
    return {"ok": True, "commit": commit["sha"], "log": log}


if __name__ == "__main__":
    print(json.dumps(run("--dry-run" in sys.argv), ensure_ascii=False, indent=1))
