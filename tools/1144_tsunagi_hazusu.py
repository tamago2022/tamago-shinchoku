#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【根拠のない繋ぎを外す】「年が近いだけ」で機械が並べた9,736件の繋ぎを、本番から外す。

■ 何を外すのか（2026-09-25 実測・ここを取り違えないこと）

  1140番の検査は「繋ぎ間違い 9,788件」と数えた。内訳は
    年が近いだけ 9,736 / 出典なし 32 / 行き先なし 20。
  ★この 9,736 は「その曲に悪い繋ぎが1本ある」という数ではない。
    検査の中身を読むと `if s["year"]: faults.append("eraOnlyTsunagi")` ＝
    **年号が入っている曲を全部数えただけ**。つまり「年号入りの曲 9,736件」の数。

  では本当の繋ぎはどこで作られているか。1か所だけだった:
    src/lib/coverGuide.ts の getContemporaryArtists()
      … アーティストの eras（時代）が重なる数だけで並べる。出典は無い。
    src/routes/cover-guide.tsx
      … curated（人が書いた繋ぎ）が5件未満のとき、上を呼んで
        現曲の年±10年で絞って「同じ時代の曲」として出す。

  ＝ 年号が入っている曲のページには、**根拠が1つも無い繋ぎ**が機械で生えていた。
    これが「一番AI臭いやつ」の正体。

■ どう外すか（たまごさんの規則に従う）

  [[feedback_same_title_is_not_evidence_of_a_cover]]
  「根拠のない繋ぎは、繋ぎ直さずまず外す。」
  → 繋ぎ直さない。生やすのをやめる。人が書いた繋ぎ（curated eraHits）はそのまま残す。

  栓: src/lib/kansei.ts の TSUNAGI_KONKYO_GATE
  ★戻し方（1行）: TSUNAGI_KONKYO_GATE を false にすると、元どおり機械が生やす。
  ★データは1件も消していない。eras も year も coverGuide.ts にそのまま残っている。
"""
from __future__ import annotations
import base64, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import github_watch  # noqa: E402

GH_REPO = "tamago2022/joy-relief-station"
BRANCH = "main"
API = "https://api.github.com"
SHIRUSHI = "1144番【根拠のない繋ぎを外す】"

MESSAGE = (
    "1144番【根拠のない繋ぎを外す】「年が近いだけ」で機械が生やす繋ぎをやめる\n\n"
    "曲ページの「同じ時代の曲」は、人が書いた繋ぎが5件未満のとき、\n"
    "アーティストの eras が重なる数と 年±10年 だけで機械が並べていた（出典ゼロ）。\n"
    "年号が入っている曲 9,736件のページにこれが生えていた。\n\n"
    "根拠のない繋ぎは繋ぎ直さず、まず外す。人が書いた繋ぎ（curated eraHits）は残す。\n"
    "データは1件も消していない（eras も year もそのまま）。\n"
    "戻し方: src/lib/kansei.ts の TSUNAGI_KONKYO_GATE を false。"
)

K_MOTO = '''/**
 * コピー（copy / note）が空のものも隠すか。'''
K_ATO = '''/**
 * ★1144番【根拠のない繋ぎを外す】根拠のない繋ぎを生やさないための栓。
 *
 * 曲ページの「同じ時代の曲」は、人が書いた繋ぎ（curated eraHits）が5件未満のとき、
 * アーティストの eras が重なる数と 年±10年 だけで機械が並べていた。出典は1つも無い。
 * たまごさんの規則「根拠のない繋ぎは、繋ぎ直さずまず外す」に従って、生やすのをやめる。
 *
 * ★false にすると元どおり機械が生やす（データは消していないので完全に戻る）。
 */
export const TSUNAGI_KONKYO_GATE = true;

/**
 * コピー（copy / note）が空のものも隠すか。'''

C_MOTO = '''  const fallbackPicks: EraHitPick[] =
    curatedPicks.length < 5 ? getEraHitsFallback(artistId, 30) : [];'''
C_ATO = '''  // ★1144番【根拠のない繋ぎを外す】ここが「年が近いだけ」の繋ぎを生やしていた場所。
  //   出典が1つも無い繋ぎなので、繋ぎ直さずに生やすのをやめる。
  //   人が書いた繋ぎ（curatedPicks）はそのまま出る。
  //   ★戻し方: src/lib/kansei.ts の TSUNAGI_KONKYO_GATE を false。
  const fallbackPicks: EraHitPick[] =
    !TSUNAGI_KONKYO_GATE && curatedPicks.length < 5 ? getEraHitsFallback(artistId, 30) : [];'''

C_IMPORT_MOTO = 'import { KANSEI_GATE } from "@/lib/kansei";'
C_IMPORT_ATO = 'import { KANSEI_GATE, TSUNAGI_KONKYO_GATE } from "@/lib/kansei";'

NAOSU = {
    "src/lib/kansei.ts": [(K_MOTO, K_ATO)],
    "src/routes/cover-guide.tsx": [(C_IMPORT_MOTO, C_IMPORT_ATO), (C_MOTO, C_ATO)],
}


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


def run(dry=False):
    token = github_watch.gh_token()
    if not token:
        return {"ok": False, "log": ["GitHubの鍵が取れませんでした"]}
    log = []
    head = _req("GET", "%s/repos/%s/git/ref/heads/%s" % (API, GH_REPO, BRANCH), token)
    base_sha = head["object"]["sha"]
    log.append("いまの main = %s" % base_sha[:8])
    t = _req("GET", "%s/repos/%s/git/trees/%s?recursive=1" % (API, GH_REPO, base_sha), token)
    sha_of = {e["path"]: e["sha"] for e in t.get("tree", []) if e.get("type") == "blob"}

    okuru = {}
    for path, naoshi in NAOSU.items():
        got = _req("GET", "%s/repos/%s/git/blobs/%s" % (API, GH_REPO, sha_of[path]), token)
        body = base64.b64decode(got["content"]).decode("utf-8")
        if SHIRUSHI in body:
            log.append("%s ← もう入っています" % path)
            continue
        bad = False
        for moto, ato in naoshi:
            n = body.count(moto)
            if n != 1:
                log.append("★%s：当てる場所が%d個（触りません）: %s"
                           % (path, n, moto.strip().splitlines()[0][:80]))
                bad = True
                break
            body = body.replace(moto, ato)
        if bad:
            return {"ok": False, "log": log + ["★1か所でも当たらないので1本も押しません"]}
        okuru[path] = body
        log.append("%s ← 当てました" % path)

    if not okuru:
        return {"ok": True, "alreadyIn": True, "log": log + ["★もう入っていました"]}
    if dry:
        return {"ok": True, "dryRun": True, "log": log + ["--dry-run。送る予定: %s" % ", ".join(okuru)]}

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
