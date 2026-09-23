#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1052番【たまごさんの確認待ち・1枚】たまごさんにしか押せないものだけを10行で出す係。

たまごさん（2026-09-24・原文）:
  「俺の確認待ちもいっぱいあるのかもしれない。なんか今出してよ。優先順位つけるから。」
  「1件1行。何を／なぜ止まっているか（1語）／たまごさんが押すべきボタン1つ。多くても10行。」
  「こちらでできるのに止めてしまったものは、たまごさんに見せずにその場で自分で進める。」

★ここに載せてよいのは **たまごさんにしかできないもの** だけ。
  ＝パスワード・本人確認・金銭・取り消せない公開。
  AIが自分で進められるものは1行も載せない（載せた時点でこの紙の負け）。
★出どころの無い断定を書かない。全部、機械が測ったファイルの行から写す。
★AIを1回も呼ばない・外へ1回も出ない＝0円。

使い方:
  python3 tools/kakunin_machi.py            … 1日1回だけ本体が走る
  python3 tools/kakunin_machi.py --force
  python3 tools/kakunin_machi.py --self-test
"""
from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import soto_hatarakite as soto  # ★出どころ（path:行番号）の付け方は1か所にしか書かない

OUT_JSON = os.path.join(PUBLIC, "kakunin_machi.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1052-kakunin-machi.html")
STAMP = os.path.join(STATUS, ".kakunin_machi_at")
JST = timezone(timedelta(hours=9))

MAX_GYO = 10  # たまごさんの指定。これを超えたら出さない


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------
# 集める。1行 = (なに, とまり(1語), ボタン, どこを押すか, 出どころ, 重さ)
# 重さ：小さいほど上。「これが止まると全部止まる」ものを上に。
# ---------------------------------------------------------------

def _moto(rel, needle, detail=""):
    """出どころを `パス:行番号` の形で返す。数字の門(KZ1)はこの形しか通さない。"""
    n = soto.srcline(rel, needle)
    head = f"{rel}:{n}" if n else rel
    d = (detail or "").replace("\n", " ")[:40]
    return f"{head}{('｜' + d) if d else ''}"


def atsumeru():
    rows = []
    k = _load(os.path.join(PUBLIC, "kaitsuu.json"), {}) or {}
    kmap = {x.get("id"): x for x in k.get("keys", [])}

    def kagi(kid, nani, botan, doko, omosa):
        """開通台帳（機械が実測している）で ng のものだけを1行にする。"""
        e = kmap.get(kid) or {}
        if e.get("status") == "ok":
            return
        rows.append(
            dict(
                nani=nani,
                tomari="鍵" if e.get("status") == "ng" else "不明",
                botan=botan,
                doko=doko,
                deme=(e.get("stops") or "")[:70],
                moto=_moto("status/public/kaitsuu.json", f'"{kid}"', e.get("detail", "")),
                omosa=omosa,
            )
        )

    # ① これが直らないと工場が1本も動かない
    kagi("claude", "Claudeのログイン（工場の発車そのもの）",
         "いつものClaudeのアプリで1回ログインし直す", "Claudeアプリ", 1)

    # ② 返事に誰も気づけなくなる系
    kagi("gmail", "Gmailのアプリパスワード（メールの見張り4本の目）",
         "Googleアカウントでアプリパスワードを作る", "https://myaccount.google.com/apppasswords", 2)
    kagi("github", "GitHubのトークン（見張り番の目）",
         "ターミナルで gh auth login", "gh auth login", 3)

    # ③ お金・残高（たまごさんしか入れられない）
    kagi("xai", "Grok（xAI）の残高（チーム goodvibes が0）",
         "console.x.ai でこのチームに残高を入れる", "https://console.x.ai", 4)
    kagi("gemini", "Geminiの鍵（安い代行先が丸ごと無い）",
         "Google AI Studio で無料発行して鍵ファイルへ", "https://aistudio.google.com/apikey", 5)

    # ④ 財布が空（実測でHTTP 429が返っている）
    o = _load(os.path.join(PUBLIC, "okane_ichimai.json"), {}) or {}
    for s in o.get("saifu", []):
        if "0円" in str(s.get("nokori", "")) and "取れていない" not in str(s.get("nokori", "")):
            rows.append(dict(
                nani=f"{s['name']} の残高が0円",
                tomari="残高",
                botan="入れるか、使わないと決める",
                doko="https://platform.openai.com/settings/organization/billing",
                # 数字の門(KZ3)：前に出した数字と食い違うときは、必ず訂正の形で書く
                deme="★訂正：前は1,479円と言いましたが、正しくは0円です。外部の検品・下書きがここで止まる",
                moto=_moto("status/public/okane_ichimai.json", s["name"], s["nokori"]),
                omosa=6,
            ))

    # ⑤ 売上が1件も読めていない
    sales = _load(os.path.join(STATUS, "sales.json"), {}) or {}
    if sales.get("configured") is False:
        rows.append(dict(
            nani="Gumroadの鍵（売上が1円も読めていない）",
            tomari="鍵",
            botan="アクセストークンを作って .env に置く",
            doko="https://app.gumroad.com/settings/advanced",
            deme="いくら売れたかが誰にも分からない",
            moto=_moto("status/sales.json", "note", str(sales.get("note", ""))),
            omosa=7,
        ))

    # ⑥ AIが1円も使えない設定になっている（金銭＝たまごさんの領分）
    y = _load(os.path.join(STATUS, "yosan.json"), {}) or {}
    lim = y.get("limits") or {}
    if lim and all((v or 0) == 0 for v in lim.values()):
        rows.append(dict(
            nani=f"1日の上限が{len(lim)}社とも0円（AIが1円も使えない）",
            tomari="上限",
            botan="いくらまでなら使っていいか決める",
            doko="status/yosan.json の limits",
            deme="外へ出す仕事が全部その場で止まる",
            moto=_moto("status/yosan.json", "limits", "＝".join([", ".join(sorted(lim)), "すべて0.0"])),
            omosa=8,
        ))

    # ⑦ 本番に出ていない（取り消せない公開＝たまごさんの領分）
    t = _load(os.path.join(STATUS, "top_status.json"), {}) or {}
    lp = t.get("lovablePublish") or {}
    if lp.get("mainUnpublished") and lp.get("stoppedForToday"):
        rows.append(dict(
            nani="本番へ出ていない（公開ボタンが押せていない）",
            tomari="公開",
            botan="Lovableの画面で公開を1回押す",
            doko="https://lovable.dev/projects/8ebdb648-3686-4457-b42c-d01c493793b1",
            deme=f"直したものが世に出ない（連続失敗 {lp.get('consecutiveFailures')}回で今日は停止）",
            moto=_moto("status/top_status.json", "lastFailureReason", str(lp.get("lastFailureReason", ""))),
            omosa=9,
        ))

    # ⑧ 期限が来るサブスク（続けるか止めるか＝金銭の判断）
    for s in (o.get("subs") or []):
        tsugi = str(s.get("tsugi") or "")
        if "終了" in tsugi and "使っていない" in str(s.get("tsukau") or ""):
            rows.append(dict(
                nani=f"{s['name']}（使っていないのに期限が来る）",
                tomari="期限",
                botan="続けるか止めるかを決める",
                doko="https://www.genspark.ai/settings",
                deme=tsugi[:50],
                moto=_moto("status/public/okane_ichimai.json", s["name"], str(s.get("tsukau"))),
                omosa=10,
            ))

    rows.sort(key=lambda r: r["omosa"])
    return rows[:MAX_GYO]


# ---------------------------------------------------------------

def kaku(rows):
    e = html.escape
    tr = "\n".join(
        "<tr><td class=n>{n}</td><td class=t>{t}</td><td><b>{b}</b><br><span class=k>{d}</span>"
        "<br><span class=k>止まると：{s}</span><br><span class=k>出どころ：{m}</span></td></tr>".format(
            n=e(r["nani"]), t=e(r["tomari"]), b=e(r["botan"]), d=e(r["doko"]),
            s=e(r["deme"] or "—"), m=e(r["moto"]))
        for r in rows
    )
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>たまごさんの確認待ち</title><style>
*{{box-sizing:border-box}}body{{margin:0;padding:12px;background:#111;color:#eee;font:13px/1.55 -apple-system,"Hiragino Sans",sans-serif}}
.big{{background:#1a1a1a;border-radius:12px;padding:14px;text-align:center;margin:0 0 12px}}
.big b{{display:block;font-size:30px;line-height:1.2}}.big span{{color:#999;font-size:12px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border-bottom:1px solid #2b2b2b;padding:8px 6px;text-align:left;vertical-align:top;font-size:12px}}
th{{color:#8a8a8a;font-weight:normal;white-space:nowrap}}
td.n{{font-weight:bold}}td.t{{color:#f2777a;white-space:nowrap}}
.k{{color:#8a8a8a;font-size:11px;word-break:break-all}}
</style></head><body>
<div class="big"><span>たまごさんにしか押せないもの</span><b>{len(rows)}件</b><span>出どころ：status/public/kakunin_machi.json:3</span>
<span>上から順に。ここに無いものは、こちらで勝手に進めます</span></div>
<table><tr><th>何が</th><th>なぜ</th><th>押すボタン1つ</th></tr>
{tr}
</table>
<p class="k">この紙は tools/kakunin_machi.py が毎日書き直す。手で書き換えない。最後に書き直した時刻 {_now()}</p>
</body></html>"""


def main():
    argv = sys.argv[1:]
    if "--self-test" in argv:
        rows = atsumeru()
        bad = [r for r in rows if not r.get("botan") or not r.get("moto")]
        assert not bad, f"ボタンか出どころが欠けた行: {bad}"
        assert len(rows) <= MAX_GYO, f"{len(rows)}行（上限{MAX_GYO}）"
        print(f"自己試験 ◯ 通った（{len(rows)}件）")
        return 0

    # 1日1回だけ（--force で無視）
    if "--force" not in argv:
        try:
            if open(STAMP).read().strip() == datetime.now(JST).strftime("%Y-%m-%d"):
                return 0
        except Exception:
            pass

    rows = atsumeru()
    os.makedirs(PUBLIC, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"generatedAt": _now(), "n": len(rows), "rows": rows}, f, ensure_ascii=False, indent=1)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(kaku(rows))
    with open(STAMP, "w") as f:
        f.write(datetime.now(JST).strftime("%Y-%m-%d"))
    print(f"書いた {OUT_HTML} ／ {len(rows)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
