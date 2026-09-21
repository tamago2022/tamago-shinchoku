#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""977番【他のAIと連携する仕組み ①行き】どの会社にでも、同じ1本で仕事を投げる口。

たまごさん（2026-09-22・原文）:
  「とにかく全部とつながれるようにしておいて、全部に仕事を割り当てられるようにしておいて。」
  「伝書鳩、卒業させてください。」

■ 変わること
  変更前：Codexに頼むときはIssueの書き方、Julesは別の書き方、Devinは「返事を書くな」を
          毎回入れる…と、**宛先ごとの作法をたまごさん／担当AIが覚えている**状態。
  変更後：`python3 tools/nageru.py codex "お題"` の1行。作法は全部この中に隠す。

■ 使い方
  python3 tools/nageru.py codex    "お題1行" --body "詳しい依頼文"
  python3 tools/nageru.py jules    "お題1行" --body-file path.md
  python3 tools/nageru.py grok     "お題1行"            # 公開掲示板 ai-kaigi へ
  python3 tools/nageru.py genspark "お題1行"
  python3 tools/nageru.py devin    "お題1行" --body "…"  # 1本ずつしか投げない
  python3 tools/nageru.py --status                        # 死活（投げ／返り）
  python3 tools/nageru.py --dry-run codex "お題"          # 出す文面だけ見る（投げない）

■ 回線（2026-09-18 実測・944番で確定した前提をそのまま踏襲）
  サンドボックス（Cowork/Dispatch）からは api.github.com に出られない。Macからは出られる。
  → このファイルは**自分で判定して**、出られなければ工場（Mac）に代行させ、結果を待つ。
     呼ぶ側は意識しなくてよい。工場の便は15秒おきに拾いに来る。

■ ★公開掲示板に出すときの検査（ai-kaigi は全世界から読める）
  秘密らしき文字（sk- / ghp_ / AKIA / 各種KEY= / .env の中身 / 絶対パス）が本文に混ざっていたら
  **投げずに止める。**止めたことも台帳に ok=false で残す（黙って飲み込まない）。

■ 台帳
  投げた1件ごとに tools/ai_daicho.py へ out の行を書く。**失敗しても必ず書く。**
  帰りは tools/github_watch.py が in の行を書く。両方が揃って初めて「双方向◯」になる。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ai_daicho  # noqa: E402
import gaibu_kuchi as gkuchi  # noqa: E402

PRIVATE_REPO = "tamago2022/joy-relief-station"   # .env が入っている。絶対に公開にしない
PUBLIC_BOARD = "tamago2022/ai-kaigi"             # Grok / Genspark はこちらしか読めない

# 「終わったらここに書いて返してね」を必ず書く。これが無いと帰りが来ない＝片道になる。
RETURN_RULE = (
    "【返し方（これだけ守ってください）】\n"
    "・終わったら **このIssueにコメント** で結果を返してください。\n"
    "・1行目に結論、2行目以降に根拠。長い成果物はPRかリンクで。\n"
    "・分からない点があっても人間に確認を求めず、前提を書いて進めてください。\n"
)

ROUTE = {
    "codex": {
        "how": "gh-issue", "repo": PRIVATE_REPO,
        "title": "【ChatGPT(Codex)に頼む】%s",
        "labels": [],
        "head": "この号はChatGPT(Codex)への依頼です。\n",
        "foot": RETURN_RULE,
        # ★2026-09-22 実測でわかった一番大事なこと：
        #   Codexは**Issueの本文に @codex と書いても動かない。コメントで呼ばれて初めて動く。**
        #   証拠＝#450：本文に依頼を書いても無反応、たまごさんが「@codex 上のお題をお願いします。」と
        #   コメントした**7秒後**に chatgpt-codex-connector[bot] が返事をした。
        #   つまり「起こす」のは本文ではなく別コメント。ここを機械でやる＝たまごさんが押さなくてよくなる。
        "wake": "@codex 上のお題をお願いします。",
        "note": "Codexは@codexコメントで起きる（本文だけでは起きない・実測）。mainに直接pushできる。",
    },
    "jules": {
        "how": "gh-issue", "repo": PRIVATE_REPO,
        "title": "【Gemini(Jules)に頼む】%s",
        # ★Julesの起こし方は「@メンション」ではなく **`jules` ラベルを貼ること**。
        #   公式ドキュメント（実際に読んだ）: https://jules.google/docs/running-tasks/
        #     > Select an issue, then click the gear icon next to "Labels",
        #     > and add the label "jules" (case insensitive) to the issue
        #   実測の裏：#449 は「Jules is on it」→12分後「Ready for a review! PR created」まで
        #   自動で進んだ。こちらは一度も呼びかけていない＝ラベルが引き金だった。
        "labels": ["jules"],
        "head": "この号はGemini(Jules)への依頼です。\n",
        "foot": RETURN_RULE,
        "wake": None,
        "note": "Julesは `jules` ラベルで起きる（公式ドキュメント＋実測）。終わるとPRを立てて知らせてくる。",
    },
    "copilot": {
        "how": "gh-issue", "repo": PRIVATE_REPO,
        "title": "【GitHub Copilotに頼む】%s",
        "labels": [],
        "head": "この号はGitHub Copilotへの依頼です。\n",
        "foot": RETURN_RULE,
        "wake": "@copilot 上のお題をお願いします。",
        "note": "★未実測。@copilotで起きるかは確かめていない。",
    },
    "grok": {
        "how": "gh-issue", "repo": PUBLIC_BOARD,
        "title": "【Grokに聞く】%s",
        "labels": [],
        "head": ("Grokへ。これは公開の掲示板です。ここに書いたものは全世界から読めます。\n"
                 "この号は Grok への相談です。\n"),
        "foot": RETURN_RULE +
                "・Grokはこちらから自動で起こせません。たまごさんがGrokの画面でこのURLを渡します。\n",
        "note": "★Grokは非公開repoが読めない（たまごさん実測）ので公開掲示板を使う。",
    },
    "genspark": {
        "how": "gh-issue", "repo": PUBLIC_BOARD,
        "title": "【Gensparkに頼む】%s",
        "labels": [],
        "head": ("@genspark-ai-developer この号はあなたへの依頼です。\n"
                 "これは公開の掲示板です。ここに書いたものは全世界から読めます。\n"),
        "foot": RETURN_RULE,
        "note": ("★こちらからGensparkを起こす手段が無い（2026-09-22実測：api.genspark.ai と "
                 "docs.genspark.ai は名前解決せず、www.genspark.ai/api/mcp は403。"
                 "Issueに @genspark-ai-developer と書いても16分無反応）。"
                 "公式が書いているのは Genspark→GitHub の片方向だけ。"
                 "GensparkのWorkflowはトリガーがScheduleとEmailの2つで、連携先にGitHubがある。"
                 "向こうの画面でスケジュールを1つ仕込めば、以後はIssueを立てるだけで回る見込み（未検証）。"),
    },
    "devin": {
        "how": "devin",
        "title": "%s",
        "note": ("★Devinは『指示があるまで待ちます』と言って止まり finished で死ぬ（実測）。"
                 "依頼文に『返事を書くな・終わりの合図はPRのURLだけ』を必ず埋める。1本ずつ投げる。"),
        "foot": ("\n\n【Devinへの絶対の決まり】\n"
                 "・確認の返事を書かないでください。質問もしないでください。\n"
                 "・前提が足りなければ、自分で仮定を置いて進め、その仮定をPR本文に書いてください。\n"
                 "・**終わりの合図はPRのURLだけです。**それ以外のメッセージは要りません。\n"),
    },
}

# ★公開掲示板に出してはいけない文字。1つでも当たったら投げずに止める。
SECRET_PATTERNS = [
    (r"\bsk-[A-Za-z0-9_\-]{16,}", "OpenAI系の鍵らしき文字"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}", "GitHubトークンらしき文字"),
    (r"\bxai-[A-Za-z0-9_\-]{16,}", "xAIの鍵らしき文字"),
    (r"\bAIza[0-9A-Za-z_\-]{30,}", "Google APIキーらしき文字"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWSのアクセスキーらしき文字"),
    (r"\bapk_[A-Za-z0-9]{16,}", "Devinの鍵らしき文字"),
    (r"(?i)\b(api[_-]?key|secret|password|token|access[_-]?token)\s*[:=]\s*\S{8,}", "鍵らしき代入行"),
    (r"/Users/[A-Za-z0-9._\-]+/", "たまごさんのMacの中の絶対パス"),
    (r"(?i)\bjoy-relief-station\b.*\.env", ".env への言及"),
]


def scan_secrets(text):
    """見つかった指摘を並べて返す。空リストなら通してよい。"""
    hits = []
    for pat, why in SECRET_PATTERNS:
        m = re.search(pat, text or "")
        if m:
            # ★見つけた値そのものは返さない（ログに秘密を書かないため）
            hits.append("%s（%d文字目あたり）" % (why, m.start()))
    return hits


def _run_factory(kind, payload, wait_sec=240):
    """回線の出る側で走らせる。出られる環境ならその場で、出られなければ工場に代行させる。"""
    if gkuchi.net_ok():
        import importlib
        import _965_keijiban
        importlib.reload(_965_keijiban)
        return _965_keijiban.run_job(payload) if kind == "keijiban" else {
            "ok": False, "error": "この経路では kind=%s を直接は走らせません" % kind}
    jid = gkuchi.enqueue_job(kind, payload)
    res = gkuchi.wait_job(jid, wait_sec=wait_sec)
    if res is None:
        return {"ok": False, "error": "工場からの返事が%d秒来ませんでした（jobId=%s）" % (wait_sec, jid)}
    return res


def _thread_key(repo, number):
    return "gh:%s#%s" % (repo, number)


def nageru(ai, topic, body="", n=None, dry_run=False, wait_sec=240):
    ai = ai_daicho.ai_key(ai)
    r = ROUTE[ai]
    label = ai_daicho.AI[ai]["label"]

    title = r["title"] % topic
    if n:
        title = "%s（%s号）" % (title, n)

    # ★工場が自分で立てた号を、見張り番（github_watch.py）が拾い直して
    #   「この依頼をやれ」と自分自身に積む無限ループを止める印。GitHubの画面には出ない。
    #   相手（Codex/Jules等）からは普通に読める本文なので、頼みごとの伝わり方は変わらない。
    full = "".join([
        "<!-- tamago-factory -->\n",
        r.get("head", ""),
        "\n",
        (body or topic).strip(), "\n\n",
        r.get("foot", ""),
    ])

    # ---- 公開掲示板の秘密検査（ここで止めるのが仕事）----
    repo = r.get("repo", "")
    if repo == PUBLIC_BOARD:
        hits = scan_secrets(title + "\n" + full)
        if hits:
            err = "公開掲示板への投稿を止めました: " + " / ".join(hits)
            ai_daicho.append("out", ai, topic=topic, ok=False, err=err)
            ai_daicho.summarize()
            return {"ok": False, "error": err, "ai": ai}

    if dry_run:
        return {"ok": True, "dryRun": True, "ai": ai, "label": label,
                "how": r["how"], "repo": repo, "title": title, "body": full,
                "note": r.get("note", "")}

    # ---- Devin だけは経路が違う ----
    if r["how"] == "devin":
        return _nageru_devin(ai, topic, (body or topic).strip() + r["foot"], n)

    # ---- GitHub Issue ----
    res = _run_factory("keijiban", {"repo": repo, "action": "issue",
                                    "title": title, "body": full,
                                    "labels": r.get("labels") or []}, wait_sec=wait_sec)
    if not res.get("ok"):
        err = res.get("error") or "理由不明"
        ai_daicho.append("out", ai, topic=topic, ok=False, err=err)
        ai_daicho.summarize()
        return {"ok": False, "error": err, "ai": ai}

    thread = _thread_key(repo, res.get("number"))
    ai_daicho.append("out", ai, thread=thread, topic=topic, ref=res.get("url"), ok=True)

    # ---- 起こす（相手によっては、号を立てるだけでは動かない）----
    wake = r.get("wake")
    woke = None
    if wake:
        # ★見張り番に自分の書き込みを拾わせない印は**入れない。**
        #   ここは相手を起こすための呼びかけであって、工場への指示ではない。
        #   印を入れると相手の連携アプリが読み飛ばす可能性があるため、
        #   代わりに「自分が書いたコメント」は投稿者が tamago2022 なので、
        #   github_watch 側の名札照合（外部AIだけ拾う）で自然に無視される。
        wres = _run_factory("keijiban", {"repo": repo, "action": "comment",
                                         "number": res.get("number"), "body": wake},
                            wait_sec=wait_sec)
        woke = bool(wres.get("ok"))
        if not woke:
            # ★起こせなかったことを飲み込まない。号は立っているので out は成功のまま、
            #   「起こせていない」を別の失敗行として残す（返りが来ない理由がこれになるため）。
            ai_daicho.append("out", ai, thread=thread, topic="起こす（%s）" % topic,
                             ref=res.get("url"), ok=False,
                             err="号は立ったが起こせませんでした: %s" % (wres.get("error") or "理由不明"))
    ai_daicho.summarize()
    return {"ok": True, "ai": ai, "label": label, "thread": thread, "woke": woke,
            "number": res.get("number"), "url": res.get("url"), "note": r.get("note", "")}


def _nageru_devin(ai, topic, body, n=None):
    """Devinは残高が減る。★1本ずつしか投げない（走っているものがあれば投げない）。"""
    script = os.path.join(HERE, "devin_start.py")
    if not os.path.exists(script):
        err = "tools/devin_start.py が見つかりません"
        ai_daicho.append("out", ai, topic=topic, ok=False, err=err)
        return {"ok": False, "error": err}
    # 走っているものがあるか確認する（devin_sessions.py があればそれで見る）
    sess = os.path.join(HERE, "devin_sessions.py")
    if os.path.exists(sess):
        try:
            p = subprocess.run([sys.executable, sess], capture_output=True, text=True, timeout=60)
            if re.search(r'"status_enum"\s*:\s*"(working|running)"', p.stdout or ""):
                err = "skip: Devinが既に1本走っています（1本ずつの決まり）"
                ai_daicho.append("out", ai, topic=topic, ok=False, err=err)
                ai_daicho.summarize()
                return {"ok": False, "error": err}
        except Exception as e:
            # ★見に行けなかったことも飲み込まない
            ai_daicho.append("out", ai, topic=topic, ok=False,
                             err="skip: 走行中か確認できず投げませんでした（%s）" % type(e).__name__)
            ai_daicho.summarize()
            return {"ok": False, "error": "走行中か確認できないので投げません"}
    try:
        p = subprocess.run([sys.executable, script, body], capture_output=True, text=True, timeout=180)
        out = (p.stdout or "") + (p.stderr or "")
        m = re.search(r"(https://app\.devin\.ai/sessions/\S+)", out)
        url = m.group(1) if m else ""
        ok = p.returncode == 0 and bool(url)
        ai_daicho.append("out", ai, thread=("devin:%s" % url.rsplit("/", 1)[-1]) if url else "",
                         topic=topic, ref=url, ok=ok,
                         err=None if ok else ("devin_start.py rc=%s %s" % (p.returncode, out[-300:])))
        ai_daicho.summarize()
        return {"ok": ok, "ai": ai, "url": url, "raw": out[-500:]}
    except Exception as e:
        ai_daicho.append("out", ai, topic=topic, ok=False, err="%s: %s" % (type(e).__name__, e))
        ai_daicho.summarize()
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser(description="他のAIに仕事を投げる1本の口")
    ap.add_argument("ai", nargs="?", help="codex / jules / grok / genspark / devin / copilot")
    ap.add_argument("topic", nargs="?", help="お題（1行）")
    ap.add_argument("--body", default="", help="詳しい依頼文")
    ap.add_argument("--body-file", default="", help="依頼文をファイルから読む")
    ap.add_argument("--n", default=None, help="号番号（前の話の続きとして扱われる）")
    ap.add_argument("--dry-run", action="store_true", help="出す文面だけ見る（投げない）")
    ap.add_argument("--wait", type=int, default=240)
    ap.add_argument("--status", action="store_true", help="死活（投げ／返り）")
    ap.add_argument("--routes", action="store_true", help="宛先ごとの作法を一覧する")
    a = ap.parse_args()

    if a.status:
        print(ai_daicho.report())
        return 0
    if a.routes:
        for k, r in ROUTE.items():
            print("■ %s（%s）" % (k, ai_daicho.AI[k]["label"]))
            print("   経路: %s %s" % (r["how"], r.get("repo", "")))
            if r.get("note"):
                print("   注意: %s" % r["note"])
        return 0
    if not a.ai or not a.topic:
        ap.print_help()
        return 2

    body = a.body
    if a.body_file:
        body = io.open(a.body_file, encoding="utf-8").read()

    res = nageru(a.ai, a.topic, body=body, n=a.n, dry_run=a.dry_run, wait_sec=a.wait)
    if res.get("dryRun"):
        print("宛先: %s ／ 経路: %s %s" % (res["label"], res["how"], res.get("repo", "")))
        print("題名: %s" % res["title"])
        print("-" * 50)
        print(res["body"])
        if res.get("note"):
            print("-" * 50)
            print("注意: %s" % res["note"])
        return 0
    if res.get("ok"):
        print("投げました: %s → %s" % (res.get("label") or res.get("ai"), res.get("url") or ""))
        if res.get("note"):
            print("注意: %s" % res["note"])
        return 0
    print("投げられませんでした: %s" % res.get("error"))
    print("（台帳には失敗として1行残しました。`python3 tools/ai_daicho.py --report` で見えます）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
