#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1038番【公開監視】「mainに入った → 本番に出た」を毎回自動で確かめ、出ていなければ赤にする係。

━━ なぜ作ったか（2026-09-23・たまごさん）━━

  「この『公開が出ない』は今日だけで3回目です。
    決まり：2回目以降の不具合は直さずパイプごと替える。」

  これまでの数え方が間違っていた：**「pushした＝出た」と数えていた。**
  ごきげん補給所（joy-relief-station）は GitHub Pages ではなく **Lovable配信**。
  mainに入れても、Lovable側の公開（Publish）が走らなければ本番は古いまま。
  ところが検品係（tools/kakunin.py）は「200が返るか」しか見ていないので、
  **1週間前の中身が200で返ってきても合格になる。**だから詰まりが見えなかった。

  実測（1032番の引き継ぎ・2026-09-23）：
    12:46 main に commit 5c929630 が入った（GitHub Contents API 200）
    12:51:11〜13:00:22 に7回 `curl -sI` → 200だが x-deployment-id は psr2.80cf3e85… のまま
    13:02 omosa 総バイト 3,026,697（10:46の 3,067,067 とほぼ同じ）＝ 何も出ていない

━━ この係が見るもの（2つだけ。増やさない）━━

  ① 本番の `x-deployment-id` が変わったか
     Lovableは公開ごとにこのヘッダを差し替える。**変わっていなければ出ていない。**
  ② mainの最新コミットのSHAと、それを見た時刻
     mainが動いたのに①が動かないまま MATIGIRE_SEC 秒すぎたら **赤**。

  ★「pushした＝出た」とは数えない。①が動くまでは「出ていない」。

━━ 使い方 ━━

  工場（Mac）側：heartbeat から tools/top_status.py 経由で毎回呼ばれる（自分で間引く）。
  サンドボックス側：
    gaibu_kuchi.enqueue_job("kakunin", {"mode": "kohyou_kanshi"})
    → 結果は status/kohyou_kanshi.json（機械用）と status/kohyou_kanshi.log（人用）。

  GETのみ・鍵はGitHubの読み取りだけ・課金0円。公開ボタンは押さない（押す係は別）。
"""
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
STATE = os.path.join(ST, "kohyou_kanshi.json")
LOG = os.path.join(ST, "kohyou_kanshi.log")
GATE = os.path.join(ST, ".kohyou_kanshi_gate")

# 見張る先。増やすときはここに1行足す（本番URL と mainのある倉庫が対）。
WATCH = [
    {"name": "ごきげん補給所",
     "url": "https://joy-relief-station.lovable.app/",
     "repo": "tamago2022/joy-relief-station",
     "branch": "main",
     "haishin": "Lovable"},
]

INTERVAL_SEC = 300      # 心臓は15秒おきに呼ぶので、実際に叩くのは5分に1回だけ
MATIGIRE_SEC = 1800     # mainが動いてから30分、本番が動かなければ赤
UA = "tamago-kohyou-kanshi/1.0 (+1038)"


def _now():
    return time.strftime("%F %T")


def _deploy_key(dep):
    """x-deployment-id から**公開ごとに変わる部分だけ**を取り出す。

    ★2026-09-23 実測（ここを間違えると係が毎回「公開された」と嘘をつく）：
      12:51 `psr2.80cf3e85-c16f-435a-b19b-51e75d92af04.1790740151.jpPZ…`
      13:20 `psr2.80cf3e85-c16f-435a-b19b-51e75d92af04.1790742014.jpPZ…`
      ＝ 真ん中のUUIDは同じで、**3つ目の数字（署名の有効期限）だけが毎回変わる。**
      公開されたかを表すのは **UUID（2つ目）** だけ。全文を比べてはいけない。
    """
    parts = (dep or "").split(".")
    return parts[1] if len(parts) >= 2 else (dep or "")


def _headers(url, timeout=15):
    """本番のヘッダだけ取る。中身は読まない（重いので）。"""
    out = {"status": 0, "deploymentId": "", "error": ""}
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": UA, "Cache-Control": "no-cache", "Pragma": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as res:
            out["status"] = res.status
            for k, v in res.getheaders():
                if k.lower() == "x-deployment-id":
                    out["deploymentId"] = v.strip()
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["error"] = "HTTP %d" % e.code
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    return out


def _gh_token():
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import github_watch
        return github_watch.gh_token()
    except Exception:
        return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _main_head(repo, branch):
    """mainの先頭コミット（SHA・時刻・件名）。読むだけ。"""
    out = {"sha": "", "at": "", "subject": "", "error": ""}
    url = "https://api.github.com/repos/%s/commits/%s" % (repo, branch)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/vnd.github+json"})
        tok = _gh_token()
        if tok:
            req.add_header("Authorization", "Bearer %s" % tok)
        with urllib.request.urlopen(req, timeout=20,
                                    context=ssl.create_default_context()) as res:
            d = json.loads(res.read().decode("utf-8", "ignore"))
        out["sha"] = (d.get("sha") or "")[:8]
        out["at"] = ((d.get("commit") or {}).get("committer") or {}).get("date") or ""
        out["subject"] = ((d.get("commit") or {}).get("message") or "").splitlines()[0][:80]
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    return out


def _load():
    try:
        return json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def _save(d):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def check_one(w, prev):
    """1か所を見て、前回と比べて判定する。返すのは辞書1つ。"""
    h = _headers(w["url"])
    g = _main_head(w["repo"], w["branch"])
    now = time.time()
    p = prev.get(w["name"]) or {}

    dep = h.get("deploymentId") or ""
    key = _deploy_key(dep)
    sha = g.get("sha") or ""
    r = {
        "name": w["name"], "url": w["url"], "repo": w["repo"],
        "haishin": w["haishin"], "checkedAt": _now(),
        "status": h.get("status"), "deploymentId": dep, "deployKey": key,
        "mainSha": sha, "mainAt": g.get("at"), "mainSubject": g.get("subject"),
        "error": h.get("error") or g.get("error") or "",
    }

    # 本番が動いたか（比べるのはUUIDだけ。全文は毎回変わるので使えない）
    prev_dep = p.get("deployKey") or _deploy_key(p.get("deploymentId") or "")
    dep_moved = bool(key and prev_dep and key != prev_dep)
    if dep_moved:
        r["deployChangedAt"] = _now()
        r["deployChangedFrom"] = prev_dep
    else:
        r["deployChangedAt"] = p.get("deployChangedAt", "")
        r["deployChangedFrom"] = p.get("deployChangedFrom", "")

    # mainが動いたか＝「まだ出ていない借り」を持つ
    prev_sha = p.get("mainSha") or ""
    machi_sha = p.get("machiSha") or ""
    machi_since = p.get("machiSince") or 0
    if sha and prev_sha and sha != prev_sha:
        # ★時計は「いちばん古い借り」で回す。新しいコミットで押し直さない。
        #   ごきげん補給所のmainには15分見回りの便が入り続けるので、毎回押し直すと
        #   「30分出ていない」に永久に届かず、赤が一生点かない（1038番で踏んだ）。
        machi_sha = sha
        if not machi_since:
            machi_since = now
    if dep_moved:
        machi_sha, machi_since = "", 0             # 公開が走ったので借りは返った

    r["machiSha"] = machi_sha
    r["machiSince"] = machi_since
    r["machiSec"] = int(now - machi_since) if machi_since else 0

    # 判定（増やさない）
    if r["error"] or (r["status"] and r["status"] >= 400):
        r["hantei"] = "赤"
        r["riyuu"] = "本番が叩けません：%s（%s）" % (r["error"] or r["status"], w["url"])
    elif not dep:
        r["hantei"] = "黄"
        r["riyuu"] = "x-deployment-id が返ってきません。物差しが無いので出たか判定できません"
    elif machi_since and (now - machi_since) > MATIGIRE_SEC:
        r["hantei"] = "赤"
        r["riyuu"] = ("mainに %s が入って %d分たつのに、本番の deploymentId が "
                      "%s のまま変わっていません＝**出ていません**"
                      % (machi_sha, r["machiSec"] // 60, key))
    elif machi_since:
        r["hantei"] = "黄"
        r["riyuu"] = ("mainに %s が入りました。公開待ち %d分（%d分で赤）"
                      % (machi_sha, r["machiSec"] // 60, MATIGIRE_SEC // 60))
    elif not prev_dep:
        r["hantei"] = "黄"
        r["riyuu"] = ("初回。前回の deploymentId が無いので「出たか」はまだ判定できません"
                      "（今のは %s。次の push から判定します）" % key)
    else:
        r["hantei"] = "青"
        r["riyuu"] = "mainと本番が揃っています（deploymentId %s）" % key
    return r


def run_now():
    """間引きなしで1回見る。サンドボックスからも工場からも同じ入口。"""
    prev = _load()
    prev_items = {x.get("name"): x for x in (prev.get("items") or [])}
    items = [check_one(w, prev_items) for w in WATCH]
    doc = {"checkedAt": _now(), "items": items,
           "aka": [x["name"] for x in items if x["hantei"] == "赤"],
           "ki": [x["name"] for x in items if x["hantei"] == "黄"]}
    try:
        _save(doc)
    except Exception:
        pass
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            for x in items:
                f.write("%s %s %s dep=%s main=%s %s\n" % (
                    x["checkedAt"], x["hantei"], x["name"],
                    x.get("deployKey") or "-", x["mainSha"] or "-", x["riyuu"]))
    except Exception:
        pass
    return doc


def run():
    """心臓から毎回呼ばれる入口。INTERVAL_SEC に1回しか実際には叩かない。"""
    try:
        if os.path.exists(GATE) and time.time() - os.path.getmtime(GATE) < INTERVAL_SEC:
            return
        io.open(GATE, "w").write(str(time.time()))
    except Exception:
        return
    try:
        run_now()
    except Exception:
        pass


def run_job(payload=None):
    """gaibu_runner から kind=kakunin / mode=kohyou_kanshi で呼ばれる。"""
    doc = run_now()
    return {"ok": not doc["aka"], "kohyou": doc, "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_now(), ensure_ascii=False, indent=1))
