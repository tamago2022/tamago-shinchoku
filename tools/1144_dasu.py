#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【隠す表を出口に繋ぐ】本番の検索・棚・曲一覧・サイトマップから、実測で死んでいる2,378件を消す。

■ 何が起きていたか（2026-09-25 実測・これが「1件も本番に反映されていない」本当の理由）

  1140番の全曲検査は、oEmbedで全26,400曲の動画IDを1件ずつ叩いて、
  「再生できる動画が1本も無い」2,378件を src/lib/kanseiHidden.generated.ts に書き出した。
  その表は 9/25 にちゃんと main に入った。関所 src/lib/kansei.ts も入った。
  **しかし、その表を読む側のコードが1行も入っていなかった。**
    main の coverGuide.ts / searchCards.ts / worlds.ts / sitemap / cover-guide.tsx を
    実際に取ってきて数えた → isSongPublishable = 0個、KANSEI_HIDDEN = 0個。
  だから表は「置いてあるだけ」で、出口は全部素通り。
  実測（本番の sitemap.xml を叩いた）: 隠すはず2,383件のうち **2,287件がそのまま出ていた**。

  なぜ 1132_dasu.py では入らなかったか:
    あの1本は status/1132_kansei/1132.patch を当てる形だった。差分は「9/25 03:21 時点の
    手元のファイル」を元に作られていて、main は15分ごとに動いている。
    当たったように見えて、出口の呼び出しは1つも入らなかった（＝差分は当てても中身が変わらない）。
    → だからこの1本は**差分を使わない**。いまの main の中身を取ってきて、
      文字列が1個だけ在ることを確かめてから、その1個を置き換える。0個や2個なら触らない。

■ 直す4か所（判定の表は1つ = KANSEI_HIDDEN_SONG_KEYS）

  ① src/routes/sitemap[.]xml.ts  … 地図に載せない（検索エンジンからの入口を塞ぐ）
  ② src/lib/searchCards.ts       … 検索に出さない
  ③ src/lib/worlds.ts            … 棚・おすすめ・「この流れで、もう一本」に出さない
  ④ src/routes/cover-guide.tsx   … アーティストページの曲一覧に出さない

■ 絶対

  ★1件も消さない。隠すだけ。動画が入れば次の検査で表から外れ、自動的に戻る。
  ★戻し方（1行）: src/lib/kansei.ts の KANSEI_GATE を false にする。
    （この1本が入れた4か所は全部 KANSEI_GATE を見ているので、falseで全部素通りに戻る）
"""
from __future__ import annotations
import base64, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import github_watch  # noqa: E402

GH_REPO = "tamago2022/joy-relief-station"
BRANCH = "main"
API = "https://api.github.com"
SHIRUSHI = "1144番【隠す表を出口に繋ぐ】"

MESSAGE = (
    "1144番【隠す表を出口に繋ぐ】検索・棚・曲一覧・サイトマップから、実測で死んでいる2378件を外す\n\n"
    "1140番の全曲検査（oEmbedで全26400曲を実測）が作った隠す表は main に入っていたが、\n"
    "その表を読む側のコードが1行も入っていなかった（実測: 出口4本すべてで0箇所）。\n"
    "そのため本番のサイトマップに2287件がそのまま出ていた（sitemap.xmlを叩いて確認）。\n\n"
    "データは1件も消していない（隠しているだけ）。動画が入れば次の検査で自動的に戻る。\n"
    "戻し方: src/lib/kansei.ts の KANSEI_GATE を false。"
)

IMPORT_KANSEI_LIB = '''import { KANSEI_GATE } from "./kansei";
import { KANSEI_HIDDEN_SONG_KEYS } from "./kanseiHidden.generated";
'''

NAOSU = {
    # ── ① サイトマップ ─────────────────────────────────────────────
    "src/routes/sitemap[.]xml.ts": [(
        '''          for (const s of a.songs) {
            entries.push({
              path: `/cover-guide?artist=${encodeURIComponent(a.id)}&song=${encodeURIComponent(s.id)}`,''',
        '''          for (const s of a.songs) {
            // ★1144番【隠す表を出口に繋ぐ】再生できる動画が1本も無い曲は地図に載せない。
            //   検索エンジンから「穴の空いたページ」へお客さんが降りてくる口を塞ぐ。
            //   ★消していない。動画が入れば次の検査で表から外れ、自動的に戻る。
            if (KANSEI_GATE && KANSEI_HIDDEN_SONG_KEYS.has(`${a.id}/${s.id}`)) continue;
            entries.push({
              path: `/cover-guide?artist=${encodeURIComponent(a.id)}&song=${encodeURIComponent(s.id)}`,'''),
        (
        '''        // 名簿はここで初めて開く（サーバ側だけ・ブラウザへは送らない）。
        const { artists } = await import("../lib/coverGuide");''',
        '''        // 名簿はここで初めて開く（サーバ側だけ・ブラウザへは送らない）。
        const { artists } = await import("../lib/coverGuide");
        // ★1144番 隠す表（軽い・106KB）。名簿と違って常に読んでよい重さ。
        const { KANSEI_GATE } = await import("../lib/kansei");
        const { KANSEI_HIDDEN_SONG_KEYS } = await import("../lib/kanseiHidden.generated");'''),
    ],
    # ── ② 検索 ─────────────────────────────────────────────────────
    "src/lib/searchCards.ts": [(
        '''    for (const s of a.songs) {
      const songCardId = `cg-song:${a.id}:${s.id}`;''',
        '''    for (const s of a.songs) {
      // ★1144番【隠す表を出口に繋ぐ】再生できる動画が1本も無い曲は検索に出さない。
      //   押して「あれ、無い」を作らない。★消していない。直れば自動的に戻る。
      if (KANSEI_GATE && KANSEI_HIDDEN_SONG_KEYS.has(`${a.id}/${s.id}`)) continue;
      const songCardId = `cg-song:${a.id}:${s.id}`;'''),
    ],
    # ── ③ 棚・おすすめ・この流れで ──────────────────────────────────
    "src/lib/worlds.ts": [(
        '''        if (WAREHOUSED_SONG_KEYS.has(`${cg.artistId}/${cg.songId}`)) return false;''',
        '''        if (WAREHOUSED_SONG_KEYS.has(`${cg.artistId}/${cg.songId}`)) return false;
        // ★1144番【隠す表を出口に繋ぐ】行き先の曲が実測で再生できないなら、
        //   棚にもおすすめにも「この流れで、もう一本」にも出さない。
        //   ★消していない。動画が入れば次の検査で表から外れ、自動的に戻る。
        if (KANSEI_GATE && KANSEI_HIDDEN_SONG_KEYS.has(`${cg.artistId}/${cg.songId}`)) return false;'''),
    ],
    # ── ④ アーティストページの曲一覧 ────────────────────────────────
    "src/routes/cover-guide.tsx": [(
        '''    const filtered = dedupedBase.filter((s) => songHasPlayableOriginal(artist.id, s));''',
        '''    // ★1144番【隠す表を出口に繋ぐ】実測で再生できない曲は、棚の曲一覧から出さない。
    //   ★消していない。動画が入れば次の検査で表から外れ、自動的に戻る。
    const notHidden = dedupedBase.filter(
      (s) => !(KANSEI_GATE && KANSEI_HIDDEN_SONG_KEYS.has(`${artist.id}/${s.id}`)),
    );
    const filtered = notHidden.filter((s) => songHasPlayableOriginal(artist.id, s));'''),
    ],
}

# 読み込み（import）を足す場所。ファイルごとに「1個だけ在る行」の直後に入れる。
IMPORTS = {
    "src/lib/searchCards.ts": (
        'import { WAREHOUSED_SONG_KEYS } from "./warehousedSongs";',
        'import { WAREHOUSED_SONG_KEYS } from "./warehousedSongs";\n'
        '// ★1144番 実測で死んでいる曲の表（1140番の全曲検査が作る）。判定の栓は KANSEI_GATE。\n'
        + IMPORT_KANSEI_LIB.rstrip("\n")),
    "src/lib/worlds.ts": (
        'import { WAREHOUSED_SONG_KEYS } from "./warehousedSongs";',
        'import { WAREHOUSED_SONG_KEYS } from "./warehousedSongs";\n'
        '// ★1144番 実測で死んでいる曲の表（1140番の全曲検査が作る）。判定の栓は KANSEI_GATE。\n'
        + IMPORT_KANSEI_LIB.rstrip("\n")),
    "src/routes/cover-guide.tsx": (
        '  songHasPlayableOriginal,',
        '  songHasPlayableOriginal,'),   # 印だけ。実体は下の ADD_IMPORT で足す
}
COVER_GUIDE_IMPORT = (
    'import { KANSEI_GATE } from "@/lib/kansei";\n'
    'import { KANSEI_HIDDEN_SONG_KEYS } from "@/lib/kanseiHidden.generated";\n')


def _req(method, url, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer %s" % token)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "tamago-1144")
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ateru(body, moto, ato, path, log):
    n = body.count(moto)
    if n != 1:
        log.append("★%s：当てる場所が%d個（1個でないので触りません）: %s"
                   % (path, n, moto.strip().splitlines()[0][:90]))
        return None
    return body.replace(moto, ato)


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
    for p in ("src/lib/kansei.ts", "src/lib/kanseiHidden.generated.ts"):
        if p not in sha_of:
            return {"ok": False, "log": log + ["土台が無い: %s（先に1132番を入れる）" % p]}

    okuru, dame = {}, False
    for path, naoshi in NAOSU.items():
        got = _req("GET", "%s/repos/%s/git/blobs/%s" % (API, GH_REPO, sha_of[path]), token)
        body = base64.b64decode(got["content"]).decode("utf-8")
        if SHIRUSHI in body:
            log.append("%s ← もう入っています" % path)
            continue
        # 読み込みを足す
        if path in IMPORTS:
            moto, ato = IMPORTS[path]
            if path == "src/routes/cover-guide.tsx":
                anchor = 'import { Helmet } from "react-helmet-async";'
                if body.count(anchor) == 1:
                    body = body.replace(anchor, anchor + "\n" + COVER_GUIDE_IMPORT.rstrip("\n"))
                else:
                    # 先頭の import 群の直後に入れる（1行目が import なら その行の後ろ）
                    i = body.index("\n", body.index("import "))
                    body = body[:i + 1] + COVER_GUIDE_IMPORT + body[i + 1:]
                log.append("%s ← 読み込みを足しました" % path)
            else:
                nb = _ateru(body, moto, ato, path, log)
                if nb is None:
                    dame = True; continue
                body = nb
        elif path == "src/routes/sitemap[.]xml.ts":
            pass  # サイトマップは中で await import する（下の差し替えに含めてある）
        for moto, ato in naoshi:
            nb = _ateru(body, moto, ato, path, log)
            if nb is None:
                dame = True; body = None; break
            body = nb
        if body is None:
            continue
        okuru[path] = body
        log.append("%s ← 当てました" % path)

    if dame:
        return {"ok": False, "log": log + ["★1か所でも当たらなかったので、1本も押しません"]}
    if not okuru:
        return {"ok": True, "alreadyIn": True, "log": log + ["★もう入っていました"]}
    if dry:
        return {"ok": True, "dryRun": True,
                "log": log + ["--dry-run。送る予定: %s" % ", ".join(sorted(okuru))]}

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
