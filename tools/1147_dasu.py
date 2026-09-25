#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1147番【出す口】下を薄くした分と、読み込みを軽くした分を main に1コミットで入れる。0円。

なぜ patch ではなく「ファイルまるごと差し替え」なのか（1132番の反省）:
  1132.patch は「当たること」が前提で、main が動くと当たらなくなる（実測で失敗した）。
  この便は6本のファイルを差し替えるだけなので patch は要らない。
  作業ツリー（/Users/mac/Desktop/joy-relief-station）には一切触らない。
  GitHub の API だけで main の上に1コミット作る。

出すもとは status/1147/src_main（この便で main の tarball から作った作業場）。
出す前に、そこで `bun run build` が通ることを確かめてある。
"""
from __future__ import annotations
import importlib.util, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "status", "1147", "src_main")

FILES = [
    "src/routes/__root.tsx",
    "src/routes/cover-guide.tsx",
    "src/components/CoverGuidePageBody.tsx",
    "src/components/MiniPlayer.tsx",
    "src/components/BottomTabNav.tsx",
    "vite.config.ts",
]

MESSAGE = (
    "1147番【下を薄く・曲ページを軽く】Spotifyに倣って1段64px、名簿7.6MBを初回から外した\n\n"
    "■ 実測（本番のURLを叩いた数字・2026-09-26）\n"
    "  曲ページが最初に落とす量 3,550KB（圧縮後）。うち coverguide-data.js が 2,688KB＝76%。\n"
    "  これが <link rel=modulepreload> で CSS と帯域を奪い合い、スマホで真っ白になっていた。\n"
    "\n"
    "■ 直したもの\n"
    "  1) routes/cover-guide.tsx を入口だけにして、本体4,142行を\n"
    "     components/CoverGuidePageBody.tsx へ移し、動的importで呼ぶ（中身は1行も変えていない）。\n"
    "     → 名簿が modulepreload から外れる。SSRは今まで通り全部描くので見える中身は減らない。\n"
    "     ローカルビルド実測：ルートのチャンク 243,803B → 2,186B。\n"
    "  2) vite.config.ts：worlds.ts(516KB)・extraCards(188KB)・ogCards(148KB)・\n"
    "     cardTags(104KB)・yomiDictionary(312KB) を純粋データと明示し、専用チャンクへ隔離。\n"
    "     ローカルビルド実測：全ページ共通のエントリ 2,072,292B → 1,279,162B（gzip 633KB → 401KB）。\n"
    "  3) __root.tsx：SwipeNavigator を lazy に。これが worlds.ts を全ページへ引き込む唯一の経路だった。\n"
    "  4) MiniPlayer.tsx：2段 → 1段64px。シークバーは数字を消して下辺の細線1本。\n"
    "     ボタンは 再生/停止・次の曲・⌃ の3つ。外したボタンは全部 ⌃ の中に残してある（消していない）。\n"
    "  5) BottomTabNav.tsx：高さを48pxに固定。ミニプレイヤーが真上に隙間ゼロで貼り付く。\n"
    "     下に使う高さ 約134px（隙間あり）→ 112px（隙間ゼロ）。\n"
    "\n"
    "戻し方：このコミットを revert する。本体は components/CoverGuidePageBody.tsx に\n"
    "丸ごと入っているだけなので、戻しても中身は1行も失われない。"
)


def load_dasu():
    spec = importlib.util.spec_from_file_location("dasu", os.path.join(HERE, "1132_dasu.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_job(payload=None):
    payload = payload or {}
    m = load_dasu()
    log = []
    token = m._token()
    if not token:
        return {"ok": False, "log": ["GitHubの鍵が取れませんでした"], "totalYen": 0.0}
    api, repo, br = m.API, m.GH_REPO, m.BRANCH

    head = m._req("GET", "%s/repos/%s/git/ref/heads/%s" % (api, repo, br), token)
    base = head["object"]["sha"]
    base_commit = m._req("GET", "%s/repos/%s/git/commits/%s" % (api, repo, base), token)
    log.append("いまの main = %s" % base[:8])

    tree_items = []
    for rel in FILES:
        p = os.path.join(SRC, rel)
        if not os.path.isfile(p):
            return {"ok": False, "log": log + ["ありません: %s" % rel], "totalYen": 0.0}
        body = io.open(p, encoding="utf-8").read()
        log.append("%-45s %6d行" % (rel, body.count("\n")))
        blob = m._req("POST", "%s/repos/%s/git/blobs" % (api, repo), token,
                      {"content": body, "encoding": "utf-8"})
        tree_items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    if payload.get("dryRun"):
        log.append("--dry-run なのでGitHubには書きません")
        return {"ok": True, "log": log, "dryRun": True, "totalYen": 0.0}

    new_tree = m._req("POST", "%s/repos/%s/git/trees" % (api, repo), token,
                      {"base_tree": base_commit["tree"]["sha"], "tree": tree_items})
    commit = m._req("POST", "%s/repos/%s/git/commits" % (api, repo), token,
                    {"message": MESSAGE, "tree": new_tree["sha"], "parents": [base]})
    m._req("PATCH", "%s/repos/%s/git/refs/heads/%s" % (api, repo, br), token,
           {"sha": commit["sha"], "force": False})
    log.append("★mainに入りました: %s" % commit["sha"][:8])
    return {"ok": True, "log": log, "commit": commit["sha"], "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"dryRun": "--dry-run" in sys.argv}),
                     ensure_ascii=False, indent=1))
