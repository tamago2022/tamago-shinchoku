#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1502番 Devinに「毎回ゼロから」をやめさせる仕込み。Knowledge と Playbook を入れる。

■ なぜ（2026-09-30 実測・公式ドキュメント）
  27本ずっと Knowledge も Playbook も空のまま投げていた。
  Devin公式は「Knowledge＝全セッションで参照される決まり事」「Playbook＝繰り返す仕事の型」
  と書いていて、使っていないなら **27本が毎回ゼロから始まっていた**ことになる。
  → docs.devin.ai/product-guides/knowledge ／ /product-guides/creating-playbooks

■ 公式が言う「向いている仕事」（docs.devin.ai/essential-guidelines/when-to-use-devin）
  ・3時間以内で終わる大きさ ・成功条件が機械で判定できる（テスト・lint・CIが緑）
  ・お手本になる既存コードがある ・独立していて後方互換 ・同じ形が何度も出てくる
  逆に向いていないと明記されているもの：
  ・「コードベースの問題を見つけて直して」のような終わりの無い調べもの
  ・「見た目を良くして」のような主観の判断
  ・大きくて曖昧な設計ごと

■ 入れるもの
  Knowledge … このリポの決まり事（触るな／重くするな／返事を書くな／関所）
  Playbook  … よく出す依頼の型（機械判定の一括直し）

■ 冪等：同じ name / title が既にあれば作らない。何回走らせても増えない。
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.devin.ai/v1"
OUT = os.path.join(REPO, "status", "1502_shikomi.json")


def key():
    try:
        with io.open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("DEVIN_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def call(path, data=None, method=None, timeout=45):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + key())
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if method:
        req.get_method = lambda: method
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": repr(e)}


# ── Knowledge（全セッションで効く決まり事）────────────────────────────
KNOWLEDGE = [
    {
        "name": "返事を書かない。終わりの合図はPRのURLだけ",
        "trigger_description": "tamago2022 の joy-relief-station / tamago-shinchoku で作業するとき、常に",
        "body": (
            "依頼主は会話を見ていません。誰も返事を書けません。\n"
            "・「指示を待ちます」「確認をお願いします」「どちらにしますか」と書いて止まってはいけません。\n"
            "・迷ったら、自分が妥当だと思う方を選んで進めてください。\n"
            "・環境が壊れたら、聞かずに自分で直してください。手を5つ試すまで止まらないでください。\n"
            "・終わりの合図は Pull Request の URL だけです。調べただけ・書いただけは未完了です。\n"
            "（過去27セッションのうち21本が、質問を書いて finished のまま死にました。これが最大の失敗です。）"
        ),
    },
    {
        "name": "触ってはいけないファイル（衝突事故の元）",
        "trigger_description": "joy-relief-station のコードを変更するとき、常に",
        "body": (
            "次のものには、明示的に指示された場合を除いて1バイトも触らないでください。\n"
            "・src/lib/coverGuide.ts および src/lib/coverGuide*.ts（全曲名簿。人間が別途作り直し中）\n"
            "・public/youtube-id-map*（YouTube索引。同上）\n"
            "・supabase/ 以下すべて（RLSの設計は意図的なものです。事故ではありません）\n"
            "・曲名・アーティスト名・動画URL・紹介文などの中身のデータ（1文字も変えない）\n"
            "触らずには目的を達成できないと判断したら、変更せずに、その根拠を数字で書いてPRを出してください。"
        ),
    },
    {
        "name": "ページを重くしない（スマホが最優先）",
        "trigger_description": "joy-relief-station のフロントエンドを変更するとき",
        "body": (
            "このサイトの利用者はほぼスマホです。表示までの待ち時間が最重要の指標です。\n"
            "・新しい依存パッケージを足さないでください。既存のもので済ませてください。\n"
            "・画面に出ないものを初回ロードで読ませないでください（動的importを優先）。\n"
            "・img には必ず width/height（または aspect-ratio）を付けてください。無いとスクロール中に画面が飛びます。\n"
            "・変更の前後で、ページが落とす転送量(KB)を実測して PR 本文に必ず数字で書いてください。"
        ),
    },
    {
        "name": "見た目は変えない。変えるなら数字で示す",
        "trigger_description": "CSS・レイアウト・コンポーネントを変更するとき",
        "body": (
            "「良くしておきました」は受け取れません。\n"
            "・標準的な画面幅（375px と 1440px）での見た目を変えないでください。\n"
            "・意図して変えた場合は、変更前後のスクリーンショットを PR に貼ってください。\n"
            "・該当しない箇所まで巻き込んで一括置換しないでください。対象の数と、対象外にした数と理由を書いてください。"
        ),
    },
    {
        "name": "報告は日本語で、必ず数字を入れる",
        "trigger_description": "PR本文やセッションの報告を書くとき、常に",
        "body": (
            "日本語で書いてください。\n"
            "必ず入れる数字：走査したファイル数／該当した箇所の数／実際に直した数／直さなかった数と理由。\n"
            "推測で書かないでください。実際にコマンドを走らせて出た値だけを書いてください。\n"
            "測れなかったものは「測れなかった」と書いてください。埋めないでください。"
        ),
    },
    {
        "name": "CIが赤でも、それがこちらの課金停止のせいなら気にしない",
        "trigger_description": "GitHub Actions が失敗するとき",
        "body": (
            "2026-09-28 時点で、このorgの GitHub Actions は課金の問題で全ランが起動前に落ちます"
            "（\"recent account payments have failed or your spending limit needs to be increased\"）。\n"
            "これは PR 側で直せる失敗ではありません。CIの赤を直そうとして時間を使わないでください。\n"
            "代わりに、ローカルで `npm run build` と型チェックが通ることを自分で確かめて、その結果をPRに書いてください。"
        ),
    },
]

# ── Playbook（繰り返す仕事の型）──────────────────────────────────
PLAYBOOKS = [
    {
        "title": "機械判定の一括直し（joy-relief-station）",
        "body": (
            "このPlaybookは「機械で該当箇所が特定でき、直したかどうかが機械で判定できる」仕事の型です。\n\n"
            "1. リポジトリ https://github.com/tamago2022/joy-relief-station を clone し、`npm ci` を通す。\n"
            "2. 指定された条件に該当する箇所を、src/ 以下から**全部**洗い出す。数を数える。\n"
            "3. 該当箇所だけを直す。該当しないものを巻き込まない。\n"
            "4. `npm run build` が通ることを確かめる。型チェックがあれば通す。\n"
            "   ※ GitHub Actions は課金停止で全ランが落ちる。CIの赤は無視してよい。\n"
            "5. Pull Request を1本出す。PR本文に必ず日本語でこの4つの数字を書く：\n"
            "   走査したファイル数 / 該当した箇所の数 / 直した数 / 直さなかった数と理由\n\n"
            "触らないもの：src/lib/coverGuide*.ts、public/youtube-id-map*、supabase/、曲やアーティストの中身のデータ。\n"
            "見た目（375px と 1440px）を変えない。\n"
            "返事を書かない。終わりの合図は Pull Request の URL だけ。"
        ),
    },
    {
        "title": "前提を実測で確かめる（結論を見せずに投げる）",
        "body": (
            "このPlaybookは「こちらの思い込みが正しいかを、実測で確かめさせる」型です。\n"
            "★結論を書かないこと。Devinに先に答えを見せると、それを裏付ける形に寄ってしまう。\n\n"
            "1. 確かめたい前提を1文だけ渡す。\n"
            "2. その前提が正しいか、実際にビルド・実行・計測して確かめる。\n"
            "3. 測った生の数字を表にする。上位15件など、件数を必ず指定する。\n"
            "4. 前提が正しければ「正しい」、違っていれば「違う」と、数字を根拠に1行で書く。\n"
            "5. 測定結果の Markdown を docs/ に置いて Pull Request を1本出す。\n\n"
            "推測で埋めない。測れなかったものは「測れなかった」と書く。\n"
            "返事を書かない。終わりの合図は Pull Request の URL だけ。"
        ),
    },
]


def items(d, *keys):
    """一覧の返り方が list のときと {"knowledge":[...]} のときの両方に耐える。"""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if isinstance(v, list):
                return v
    return []


def main():
    res = {"at": time.strftime("%F %T"), "knowledge": [], "playbooks": []}

    code, d = call("/knowledge")
    have = set()
    if code == 200:
        for k in items(d, "knowledge", "items", "data"):
            if isinstance(k, dict) and k.get("name"):
                have.add(k["name"])
    else:
        res["knowledge_list_error"] = "HTTP=%s %s" % (code, str(d)[:120])
    for k in KNOWLEDGE:
        if k["name"] in have:
            res["knowledge"].append({"name": k["name"], "result": "すでに入っている"})
            continue
        c, r = call("/knowledge", k)
        res["knowledge"].append({"name": k["name"], "http": c,
                                 "id": (r or {}).get("id"), "err": None if c == 200 else str(r)[:160]})

    code, d = call("/playbooks")
    havep = set()
    if code == 200:
        for p in items(d, "playbooks", "items", "data"):
            if isinstance(p, dict) and p.get("title"):
                havep.add(p["title"])
    else:
        res["playbook_list_error"] = "HTTP=%s %s" % (code, str(d)[:120])
    for p in PLAYBOOKS:
        if p["title"] in havep:
            res["playbooks"].append({"title": p["title"], "result": "すでに入っている"})
            continue
        c, r = call("/playbooks", p)
        res["playbooks"].append({"title": p["title"], "http": c,
                                 "playbook_id": (r or {}).get("playbook_id"),
                                 "err": None if c == 200 else str(r)[:160]})

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
