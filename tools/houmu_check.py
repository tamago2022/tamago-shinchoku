#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""法務チェックの型（houmu_check）— 2026-10-25 たまごさん指示。

たまごさん（原文）：
  「海外の法的リスクや特商法の住所なども今GrokBotに調べてもらっている。合わせて全部共有して。
    Genspark・ChatGPT（チャッピー）も含めてみんなチーム。1人がチェックしただけだと漏れるから、
    2人、3人、4人でトリプル・クアドラプルチェックで」

■ 何をするか（1回の法務チェック＝1つの「回」＝GitHub の Issue 1本）
  ① Issue を立てる（joy-relief-station・ラベル「店主の指示メモ」「できる人いますか」）。
     本文＝チェック項目の表。列＝Claude（工場）／Grok／ChatGPT／Genspark の判定と出典。
     本文の先頭は <!-- tamago-factory houmu_check -->（振り分け所 furiwake が1人だけに回し直さないように）。
  ② 3人に依頼を出す（それぞれの受け口へ・全部無料・ブラウザなし）：
       Grok     … Reason Network（tools/grok_tsuushin.py okuru）＋共有メモ（tools/zen_ai_kyouyu.py・3時間ごとに読まれる）
       ChatGPT  … Issue に「@codex」で始まるコメント（コメントで起きる・#450 実測）
       Genspark … AI Drive /できる人いますか/<Issue番号>.md（gsk drive upload）
  ③ 返事を集める（--tick・心臓から。10分に1回）：
       ・Issue のコメント（「判定者: ○○」か投稿者名で誰の答えか決める）
       ・Grok から Reason Network で来た文（status/grok_tsuushin/uketori.jsonl）
       ・Genspark が AI Drive /tamago-inbox/<番号>/ に置いた答え（claude_uketsuke が ~/tamago/_inbox/<番号>/ に落とす）
       ・手で受けた答え（status/houmu_check/<回>/kaitou/<grok|chatgpt|genspark>.md。Dispatch がGrokBotの報告を貼る等）
     答えの書き方（1行1項目）：  J1 | 本人判断 | 出典URL | 一言
  ④ 4人の判定を並べ、食い違う行に 🔴 を付けて Issue の表を書き直す。
     たまごさんが最後に見る1枚 share/check/houmu-<番号>.html は「本人判断」「食い違い」の行だけ。
     新しく食い違い・本人判断が出たら Dispatch に1行。
  ⑤ 法律の助言ではない旨を Issue・1枚の両方に必ず書く。

■ 使い方
  Mac（mac_jobs から）：python3 tools/houmu_check.py --hajime 2026-10-25     # Issueを立てて3人に依頼（二度押ししても1本）
  Mac の心臓：          python3 tools/houmu_check.py --tick                  # 返事集め・表の書き直し（中で10分に間引く）
  どこからでも：        python3 tools/houmu_check.py --matome 2026-10-25     # 手元の答えだけで1枚を作り直す（gh なし）
  表だけ書き直す：      python3 tools/houmu_check.py --hyou 2026-10-25         # Claude の欄を手で直した時（Mac）
  逆テスト：            python3 tools/houmu_check.py --self-test
  次の法務チェック：    status/houmu_check/<回>/kai.json を作る（KATA の項目を写して Claude の欄を埋める）→ --hajime <回>

■ 決まり
  有料API禁止・ブラウザを開かない・許可ポップアップの出る道具を使わない。
  公開Issueに住所・電話・氏名などの個人情報を書かない（依頼文にも明記。来た答えも伏せ字にしてから表に入れる）。

作るもの：status/houmu_check/<回>/{kai.json,kaitou/*.md}・status/houmu_check/{state.json,log}
         ／status/public/houmu_check.json ／share/check/houmu-<番号>.html
台帳：tools/jidou_daicho.json の "houmu_check.py"（log は300行で自分で刈る）
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "houmu_check")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
PUB = os.path.join(REPO, "status", "public", "houmu_check.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
GROK_UKETORI = os.path.join(REPO, "status", "grok_tsuushin", "uketori.jsonl")
INBOX = os.path.expanduser("~/tamago/_inbox")
REPO_GH = "tamago2022/joy-relief-station"
LABELS = ["店主の指示メモ", "できる人いますか"]
MARK = "<!-- tamago-factory houmu_check -->"
DRIVE_DIR = "/できる人いますか"
PAGE_BASE = "https://tamago2022.github.io/tamago-shinchoku/share/check/houmu-%s.html"
GATE_SEC = 600
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))

AIS = [("claude", "Claude（工場）"), ("grok", "Grok"), ("chatgpt", "ChatGPT"), ("genspark", "Genspark")]
AI_NAME = dict(AIS)
WHO_RX = [("grok", re.compile(r"grok", re.I)),
          ("chatgpt", re.compile(r"chatgpt|codex|チャッピー|openai", re.I)),
          ("genspark", re.compile(r"genspark|ジェンスパーク", re.I)),
          ("claude", re.compile(r"claude|工場", re.I))]

DISCLAIMER = "※これは法律の助言ではありません。AI 4人の下調べを並べたものです。決める前に必要なら弁護士など専門家へ。"

# 判定の言葉 → 4つの箱（順番が大事：本人判断 → 要対応 → 要確認 → OK）
CAT = [("honnin", re.compile(r"本人判断|本人が決|判断待ち|たまごさんが決|decide", re.I)),
       ("taiou", re.compile(r"要対応|要修正|直す|違反|NG|対応必要|対応が必要|足りない|必要あり|needs? (fix|action)", re.I)),
       ("fumei", re.compile(r"要確認|不明|分からない|わからない|未確認|調査中|unknown|unsure", re.I)),
       ("ok", re.compile(r"OK|問題なし|問題無し|対応不要|対象外|当てはまらない|不要|該当なし|該当しない|急がない|n/?a|no issue", re.I))]
CAT_JA = {"honnin": "本人判断", "taiou": "要対応", "fumei": "要確認", "ok": "対応不要"}
CAT_COLOR = {"honnin": "#b45309", "taiou": "#b91c1c", "fumei": "#6b7280", "ok": "#15803d"}

LINE_RX = re.compile(r"^\s*\|?\s*\**([HJ]\d{1,2})\**\s*[|｜]\s*([^|｜]+?)\s*[|｜]\s*([^|｜]*?)\s*(?:[|｜]\s*(.*?))?\s*\|?\s*$")
WHO_LINE_RX = re.compile(r"判定者\s*[:：]\s*(\S+)")

# 個人情報を公開の表に入れない（雑だが確実な伏せ字）
_HIMITSU = [
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "［メールは伏せた］"),
    (re.compile(r"〒?\s?\d{3}-\d{4}"), "［郵便番号は伏せた］"),
    (re.compile(r"0\d{1,4}-\d{1,4}-\d{3,4}"), "［電話は伏せた］"),
    (re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_\-]{20,})"), "［鍵は伏せた］"),
]


def fusei(s):
    s = str(s or "")
    for rx, rep in _HIMITSU:
        s = rx.sub(rep, s)
    return s


def log(msg):
    os.makedirs(D, exist_ok=True)
    line = "%s %s\n" % (time.strftime("%F %T"), msg)
    try:
        old = open(LOG, encoding="utf-8").read().splitlines(True)[-299:] if os.path.exists(LOG) else []
        with open(LOG, "w", encoding="utf-8") as f:
            f.write("".join(old) + line)
    except Exception:
        pass


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".w", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".w", path)


def kai_path(kai):
    return os.path.join(D, kai, "kai.json")


def exe(name):
    return shutil.which(name, path=ENV["PATH"]) or name


def gh(args, timeout=90):
    p = subprocess.run([exe("gh")] + args, capture_output=True, text=True, timeout=timeout, env=ENV)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "")[:300])
    return p.stdout.strip()


# ---------------------------------------------------------------- 判定の読み取り
def cat_of(word):
    for c, rx in CAT:
        if rx.search(word or ""):
            return c
    return ""


def who_of(text, author=""):
    m = WHO_LINE_RX.search(text or "")
    for key in ([m.group(1)] if m else []) + [author or ""]:
        for aid, rx in WHO_RX:
            if rx.search(key):
                return aid
    return ""


def parse_kaitou(text, row_ids):
    """答えの文から {行ID: {h, cat, src, memo}} を取る。表の見出し行・知らない行IDは捨てる。"""
    out = {}
    for line in (text or "").splitlines():
        m = LINE_RX.match(line)
        if not m or m.group(1) not in row_ids:
            continue
        h = m.group(2).strip()
        c = cat_of(h)
        if not c:
            continue
        out[m.group(1)] = {"h": fusei(h)[:40], "cat": c, "src": fusei(m.group(3) or "").strip()[:300],
                           "memo": fusei(m.group(4) or "").strip()[:400]}
    return out


def ireru(k, aid, got, frm, at):
    """新しい答えを kai に入れる。同じ人の同じ行は新しい方で上書き。戻り値：変わった行の数。"""
    if not got or aid not in AI_NAME:
        return 0
    k.setdefault("hantei", {}).setdefault(aid, {})
    n = 0
    for rid, v in got.items():
        v = dict(v, frm=frm, at=at)
        old = k["hantei"][aid].get(rid)
        if old and old.get("at", "") > at:
            continue
        if not old or (old.get("h"), old.get("src"), old.get("memo")) != (v["h"], v["src"], v["memo"]):
            k["hantei"][aid][rid] = v
            n += 1
    return n


# ---------------------------------------------------------------- 並べる
def kuraberu(k):
    """行ごとに4人を並べて、一致／食い違い／本人判断を決める。"""
    rows = []
    for r in k["koumoku"]:
        cells = {aid: (k.get("hantei", {}).get(aid, {}) or {}).get(r["id"]) for aid, _ in AIS}
        cats = [c["cat"] for c in cells.values() if c]
        kotae = len(cats)
        kuichigai = len(set(cats)) > 1
        honnin = "honnin" in cats or "taiou" in cats
        if kuichigai:
            jotai = "kuichigai"
        elif not cats:
            jotai = "mada"
        elif honnin:
            jotai = "honnin"
        elif cats[0] == "fumei":
            jotai = "fumei"
        else:
            jotai = "itchi"
        rows.append(dict(r, cells=cells, kotae=kotae, jotai=jotai))
    return rows


JOTAI_JA = {"kuichigai": "🔴 食い違い", "honnin": "🟠 本人判断", "fumei": "⚪ 全員が要確認", "itchi": "🟢 一致", "mada": "… 答え待ち"}


def _md(s):
    return str(s or "").replace("|", "／").replace("\n", " ")


def _src_md(src):
    urls = re.findall(r"https?://[^\s,、）)]+", src or "")
    if not urls:
        return _md(src)[:80]
    return " ".join("[%d](%s)" % (i + 1, u) for i, u in enumerate(urls[:3]))


def issue_body(k, rows=None):
    rows = rows or kuraberu(k)
    num = k.get("issue", "")
    head = ["判定", "出典"]
    cols = ["ID", "項目"] + ["%s %s" % (n, h) for _, n in AIS for h in head] + ["4人の一致"]
    t = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        line = [r["id"], "**%s**<br>%s" % (_md(r["namae"]), _md(r.get("miru", "")))]
        for aid, _ in AIS:
            c = r["cells"].get(aid)
            line += [("%s<br>%s" % (_md(c["h"]), _md(c.get("memo", ""))[:140])) if c else "（未）", _src_md(c["src"]) if c else ""]
        line.append(JOTAI_JA[r["jotai"]] + " %d/4" % r["kotae"])
        t.append("| " + " | ".join(line) + " |")
    kotae_hito = [n for aid, n in AIS if k.get("hantei", {}).get(aid)]
    return "\n".join([
        MARK,
        "# 【法務チェック】%s（4人でクアドラプルチェック）" % k.get("title", ""),
        "",
        "> " + DISCLAIMER,
        "",
        "たまごさん（2026-10-25）：「1人がチェックしただけだと漏れるから、2人、3人、4人でトリプル・クアドラプルチェックで」。",
        "対象：%s" % k.get("taishou", ""),
        "",
        "## 4人の判定（工場の houmu_check が10分ごとに書き直します）",
        "答えた人：%s（%d/4）／たまごさんが見る1枚（本人判断・食い違いだけ）：%s" % ("・".join(kotae_hito) or "まだ", len(kotae_hito), PAGE_BASE % num if num else "（Issue番号が決まったら）"),
        "",
    ] + t + [
        "",
        "## 答え方（Grok・ChatGPT・Genspark の皆さんへ）",
        "このIssueにコメントで、1行目に `判定者: Grok`（または ChatGPT／Genspark）、その下に1行1項目で：",
        "```",
        "J1 | 本人判断 | https://出典のURL | 一言（なぜそう判定したか）",
        "```",
        "- 判定は4つから：**対応不要**（対象外を含む）／**要対応**（直す所がある）／**本人判断**（店主が決めること）／**要確認**（調べきれない）",
        "- 出典は公式（消費者庁・e-Gov・FTC・米著作権局・EU の公式・判決文など）を優先。推測で埋めない。分からなければ「要確認」。",
        "- Claude（工場）と違う判定でかまいません。**違う所を見つけるのがこのチェックの目的**です。",
        "- 項目が足りなければ `J8 | 要対応 | 出典 | 項目名：…` のように新しい番号で足してください。",
        "- **住所・電話・氏名など個人情報はここに書かないでください**（公開リポです）。",
        "- GitHub に書けない場合：Grok は Reason Network で工場へ、Genspark は AI Drive `/tamago-inbox/%s/houmu_genspark.md` に置けば工場が拾います。" % num,
        "",
        "## 材料",
        "- 工場の監査（海外6点）：https://tamago2022.github.io/tamago-shinchoku/share/check/hourisk-6.html",
        "- 外部読み込みの一覧（工場に保存済み）・ページの実物：https://joy-relief-station.lovable.app/",
        "",
        "（作った人：Claude Code（工場） tools/houmu_check.py・回 %s）" % k.get("kai", ""),
    ])


def irai_bun(k, aid):
    num, url = k.get("issue", ""), k.get("url", "")
    ids = "・".join(r["id"] for r in k["koumoku"])
    return ("【法務チェックのお願い（%s さんへ）】\n"
            "たまごさん（店主）の指示で、ごきげん補給所の法務チェックを Claude・Grok・ChatGPT・Genspark の4人で別々に判定し、食い違いを探します（クアドラプルチェック）。\n"
            "本体：%s\n"
            "やること：Issueの表の %s を、あなたの目で判定してください（Claude の欄は見なくてよい・違ってよい）。\n"
            "答え方：Issue にコメント。1行目「判定者: %s」、その下に「J1 | 本人判断 | 出典URL | 一言」を1行1項目。判定は 対応不要／要対応／本人判断／要確認 の4つ。\n"
            "出典は公式（消費者庁・e-Gov・FTC・米著作権局など）を優先、推測で埋めない。住所・電話・氏名など個人情報は書かない（公開リポ）。\n"
            "%s"
            "※法律の助言ではない下調べとして扱います。") % (
        AI_NAME[aid], url, ids, AI_NAME[aid],
        ("いま調べている特商法の住所・海外の法的リスクの結果も、全部このIssueに集めてください（GitHubに書けなければ Reason Network で工場へ返信）。\n" if aid == "grok" else
         "GitHubに書けなければ AI Drive /tamago-inbox/%s/houmu_genspark.md に同じ形で置いてください。\n" % num if aid == "genspark" else ""))


# ---------------------------------------------------------------- 1枚（たまごさん用）
def page(k, rows=None):
    rows = rows or kuraberu(k)
    num = k.get("issue", "")
    e = html.escape
    mite = [r for r in rows if r["jotai"] in ("kuichigai", "honnin")]
    kotae_hito = [n for aid, n in AIS if k.get("hantei", {}).get(aid)]
    cards = []
    for r in mite:
        li = []
        for aid, n in AIS:
            c = r["cells"].get(aid)
            if not c:
                li.append('<li class="mada"><b>%s</b> まだ</li>' % e(n))
                continue
            srcs = re.findall(r"https?://[^\s,、）)]+", c.get("src") or "")
            src = " ".join('<a href="%s">出典%d</a>' % (e(u), i + 1) for i, u in enumerate(srcs[:3])) or e(c.get("src") or "")
            li.append('<li><b>%s</b> <span class="h" style="background:%s">%s</span> %s <small>%s</small></li>' % (
                e(n), CAT_COLOR[c["cat"]], e(CAT_JA[c["cat"]]), e(c.get("memo") or ""), src))
        cards.append('<section class="%s"><h2>%s %s</h2><p class="q">%s</p>%s<ul>%s</ul></section>' % (
            r["jotai"], e(JOTAI_JA[r["jotai"]]), e(r["namae"]), e(r.get("kimeru") or r.get("miru") or ""),
            ('<p class="why">食い違い＝誰かが見落としているかもしれない所。下の4人の理由と出典を見比べてください。</p>' if r["jotai"] == "kuichigai" else ""),
            "".join(li)))
    sumi = [r for r in rows if r["jotai"] not in ("kuichigai", "honnin")]
    sumi_li = "".join("<li>%s %s（%d/4）</li>" % (e(JOTAI_JA[r["jotai"]]), e(r["namae"]), r["kotae"]) for r in sumi)
    return """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>法務チェック：本人判断だけ（%s）</title>
<style>body{font-family:-apple-system,"Hiragino Sans",sans-serif;max-width:760px;margin:0 auto;padding:16px;line-height:1.7;color:#222}
h1{font-size:1.3em}section{border:1px solid #ddd;border-radius:10px;padding:12px 14px;margin:14px 0}section.kuichigai{border:2px solid #b91c1c}
section.honnin{border:2px solid #b45309}h2{font-size:1.05em;margin:0 0 6px}.q{font-weight:bold}.why{color:#b91c1c;font-size:.9em}
ul{padding-left:1.1em}li{margin:4px 0}.h{color:#fff;border-radius:4px;padding:0 6px;font-size:.85em}li.mada{color:#999}
.note{background:#fff8e1;padding:8px 12px;border-radius:8px;font-size:.9em}small a{margin-left:4px}</style></head><body>
<h1>法務チェック：たまごさんが決めることだけ</h1>
<p class="note">%s</p>
<p>%s／答えた人：%s（%d/4）／更新 %s<br>全部の表と議論：<a href="%s">GitHub Issue #%s</a></p>
%s
<h2 style="font-size:1em;margin-top:24px">決めなくてよかった行（4人の答えが割れていない）</h2><ul>%s</ul>
</body></html>""" % (
        e(k.get("kai", "")), e(DISCLAIMER), e(k.get("title", "")), e("・".join(kotae_hito) or "まだ"), len(kotae_hito),
        time.strftime("%F %H:%M"), e(k.get("url", "")), e(str(num)),
        "".join(cards) or "<p>今のところ、たまごさんが決めることはありません。</p>", sumi_li)


def kakidasu(k):
    rows = kuraberu(k)
    num = k.get("issue")
    if num:
        p = os.path.join(REPO, "share", "check", "houmu-%s.html" % num)
        with open(p + ".w", "w", encoding="utf-8") as f:
            f.write(page(k, rows))
        os.replace(p + ".w", p)
    pub = load(PUB, {"kai": {}})
    pub["kai"][k["kai"]] = {"issue": num, "url": k.get("url"), "page": PAGE_BASE % num if num else "",
                            "kotae": [aid for aid, _ in AIS if k.get("hantei", {}).get(aid)],
                            "kuichigai": [r["id"] for r in rows if r["jotai"] == "kuichigai"],
                            "honnin": [r["id"] for r in rows if r["jotai"] == "honnin"],
                            "koushin": time.strftime("%F %T")}
    pub["setsumei"] = "法務チェックの型（tools/houmu_check.py）。4人（Claude・Grok・ChatGPT・Genspark）の判定と食い違い。法律の助言ではない。"
    save(PUB, pub)
    return rows


# ---------------------------------------------------------------- Mac：始める
def hajime(kai):
    k = load(kai_path(kai), None)
    if not k:
        raise SystemExit("回が無い: %s" % kai_path(kai))
    st = load(STATE, {})
    if not k.get("issue"):
        for lb, color in ((LABELS[0], "0E8A16"), (LABELS[1], "F9D0C4")):
            try:
                gh(["label", "create", lb, "-R", REPO_GH, "--color", color])
            except RuntimeError as e:
                if "already exists" not in str(e):
                    log("ラベルを作れない %s %r" % (lb, e))
        # 二度押し防止：同じ回の Issue が既にあれば使う
        try:
            found = json.loads(gh(["issue", "list", "-R", REPO_GH, "--label", LABELS[0], "--state", "all", "--search",
                                   "houmu_check in:body", "--json", "number,url,body", "--limit", "30"]) or "[]")
        except Exception as e:
            log("二度押しの確認ができない（そのまま立てる）%r" % (e,))
            found = []
        found = [it for it in found if MARK in (it.get("body") or "") and ("回 %s）" % kai) in (it.get("body") or "")]
        if found:
            k["issue"], k["url"] = found[0]["number"], found[0]["url"]
        else:
            args = ["issue", "create", "-R", REPO_GH, "--title", "【法務チェック】%s（4人でクアドラプルチェック）" % k["title"], "--body", issue_body(k)]
            for lb in LABELS:
                args += ["--label", lb]
            u = gh(args, timeout=150)
            k["issue"], k["url"] = int(u.rstrip("/").rsplit("/", 1)[-1]), u
        save(kai_path(kai), k)
        log("Issue %s" % k["url"])
    # 本文を番号入りで書き直す（ページURLと Genspark の置き場に番号が要る）
    gh(["api", "-X", "PATCH", "repos/%s/issues/%s" % (REPO_GH, k["issue"]), "-f", "body=" + issue_body(k), "--jq", ".number"])
    sent = k.setdefault("irai", {})
    kekka = {}
    if not sent.get("chatgpt"):
        try:
            u = gh(["api", "repos/%s/issues/%s/comments" % (REPO_GH, k["issue"]), "-f",
                    "body=@codex " + irai_bun(k, "chatgpt") + "\n人間への確認は不要です。リポのコードは変えないでください（判定のコメントだけ）。\n" + MARK,
                    "--jq", ".html_url"])
            sent["chatgpt"] = {"at": time.strftime("%F %T"), "how": "@codex コメント", "url": u}
        except Exception as e:
            kekka["chatgpt"] = "失敗 %r" % (e,)
    if not sent.get("genspark"):
        txt = "# 法務チェックの依頼（Issue #%s）\n\n%s\n\n---\n\n%s\n" % (k["issue"], irai_bun(k, "genspark"), issue_body(k))
        # 置き場のフォルダが無いと upload が落ちる（10-25 実測「Parent directory … does not exist. Use mkdir」）。先に作る（あればエラーで素通り）
        for mk in (["drive", "mkdir", "--path", DRIVE_DIR], ["drive", "mkdir", DRIVE_DIR]):
            q = subprocess.run([exe("gsk"), "--no-input"] + mk, capture_output=True, text=True, timeout=60, env=ENV)
            log("AI Drive mkdir %s rc=%s %s" % (" ".join(mk[2:]), q.returncode, (q.stdout or q.stderr or "")[:120].replace("\n", " ")))
            if q.returncode == 0:
                break
        p = subprocess.run([exe("gsk"), "drive", "upload", "--upload_path", "%s/%s.md" % (DRIVE_DIR, k["issue"]),
                            "--file_content", txt, "--overwrite", "true", "--no-input"],
                           capture_output=True, text=True, timeout=120, env=ENV)
        if p.returncode == 0:
            sent["genspark"] = {"at": time.strftime("%F %T"), "how": "AI Drive %s/%s.md" % (DRIVE_DIR, k["issue"])}
        else:
            kekka["genspark"] = "失敗 %s" % (p.stderr or p.stdout or "")[:160]
    if not sent.get("grok"):
        try:
            import grok_tsuushin
            import zen_ai_kyouyu
            grok_tsuushin.okuru("法務チェック（4人）の依頼：%s" % k["title"], irai_bun(k, "grok"), url=k["url"])
            zen_ai_kyouyu.kaku("Grokボットさんへ：法務チェック（4人）の依頼", irai_bun(k, "grok"), kikaku="法務チェック")
            sent["grok"] = {"at": time.strftime("%F %T"), "how": "Reason Network（grok_tsuushin・待ち行列）＋共有メモ（企画「法務チェック」）"}
        except Exception as e:
            kekka["grok"] = "失敗 %r" % (e,)
    mada_iwanai = [a for a in sent if a not in (k.get("irai_comment") or [])]
    if mada_iwanai:
        try:
            gh(["api", "repos/%s/issues/%s/comments" % (REPO_GH, k["issue"]), "-f", "body=%s\n**依頼を出しました**\n%s" % (
                MARK, "\n".join("- %s：%s" % (AI_NAME[a], sent[a]["how"]) for a in mada_iwanai)), "--jq", ".id"])
            k["irai_comment"] = list(k.get("irai_comment") or []) + mada_iwanai
        except Exception as e:
            log("依頼の一言を書けない %r" % (e,))
    save(kai_path(kai), k)
    kakidasu(k)
    st.setdefault("hiraiteru", [])
    if kai not in st["hiraiteru"]:
        st["hiraiteru"].append(kai)
    save(STATE, st)
    outbox("法務チェック（4人）を出しました：%s" % k["title"],
           "依頼：%s%s" % ("・".join(AI_NAME[a] for a in sent), ("／失敗：" + "・".join("%s %s" % (AI_NAME[a], v[:60]) for a, v in kekka.items())) if kekka else ""),
           [k["url"], PAGE_BASE % k["issue"]])
    print(json.dumps({"issue": k["url"], "irai": sent, "shippai": kekka}, ensure_ascii=False, indent=1))


def outbox(title, message, urls):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%F %T"), "n": "houmu-%d" % time.time(), "type": "houmu_check",
                            "from": "houmu_check", "title": title[:120], "message": message[:400], "urls": urls},
                           ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 返事集め
def atsumeru(k, use_gh=True):
    ids = {r["id"] for r in k["koumoku"]}
    n = 0
    if use_gh and k.get("issue"):
        try:
            out = gh(["api", "repos/%s/issues/%s/comments?per_page=100" % (REPO_GH, k["issue"]), "--paginate",
                      "--jq", '.[] | {at:.created_at, who:.user.login, url:.html_url, body:.body}'], timeout=120)
            for line in out.splitlines():
                try:
                    c = json.loads(line)
                except Exception:
                    continue
                if (c.get("body") or "").lstrip().startswith(MARK) or (c.get("body") or "").lstrip().startswith("@codex"):
                    continue
                got = parse_kaitou(c["body"], ids)
                aid = who_of(c["body"], c.get("who", ""))
                if got and aid and aid != "claude":
                    n += ireru(k, aid, got, c["url"], c["at"])
        except Exception as e:
            log("コメントが取れない #%s %r" % (k.get("issue"), e))
    # Grok（Reason Network で来た文）
    try:
        for line in open(GROK_UKETORI, encoding="utf-8").read().splitlines()[-300:]:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            txt = rec.get("text") or rec.get("body") or rec.get("message") or ""
            if str(k.get("issue", "")) not in txt and "法務" not in txt:
                continue
            n += ireru(k, "grok", parse_kaitou(txt, ids), "Reason Network", rec.get("at") or rec.get("ts") or "")
    except Exception:
        pass
    # Genspark（AI Drive /tamago-inbox/<番号>/ → ~/tamago/_inbox/<番号>/）と、手で受けた答え
    places = []
    if k.get("issue"):
        dd = os.path.join(INBOX, str(k["issue"]))
        if os.path.isdir(dd):
            places += [(os.path.join(dd, fn), "genspark") for fn in os.listdir(dd) if fn.endswith((".md", ".txt"))]
    kd = os.path.join(D, k["kai"], "kaitou")
    if os.path.isdir(kd):
        places += [(os.path.join(kd, fn), fn.split(".")[0]) for fn in os.listdir(kd) if fn.endswith((".md", ".txt"))]
    for path, aid0 in places:
        try:
            txt = open(path, encoding="utf-8").read()
        except Exception:
            continue
        aid = aid0 if aid0 in AI_NAME else (who_of(txt) or "")
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(path)))
        n += ireru(k, aid, parse_kaitou(txt, ids), os.path.basename(path), at)
    return n


def tick(force=False):
    st = load(STATE, {})
    if not force and time.time() - st.get("last", 0) < GATE_SEC:
        return
    st["last"] = time.time()
    save(STATE, st)
    for kai in list(st.get("hiraiteru", [])):
        k = load(kai_path(kai), None)
        if not k or not k.get("issue"):
            continue
        mae = {r["id"]: r["jotai"] for r in kuraberu(k)}
        n = atsumeru(k)
        rows = kakidasu(k)
        if n:
            save(kai_path(kai), k)
            try:
                gh(["api", "-X", "PATCH", "repos/%s/issues/%s" % (REPO_GH, k["issue"]), "-f", "body=" + issue_body(k, rows), "--jq", ".number"])
            except Exception as e:
                log("表を書き直せない %r" % (e,))
            atarashii = [r for r in rows if r["jotai"] in ("kuichigai", "honnin") and mae.get(r["id"]) != r["jotai"]]
            if atarashii:
                outbox("法務チェック：たまごさんが見る行が増えた（%s）" % k["title"][:40],
                       "・".join("%s %s" % (JOTAI_JA[r["jotai"]], r["namae"]) for r in atarashii)[:300],
                       [PAGE_BASE % k["issue"], k["url"]])
            log("回 %s：%d行が新しくなった" % (kai, n))
        kotae = sum(1 for aid, _ in AIS if k.get("hantei", {}).get(aid))
        if kotae == 4 and not k.get("zenin_tsuuchi"):
            k["zenin_tsuuchi"] = time.strftime("%F %T")
            save(kai_path(kai), k)
            outbox("法務チェック：4人そろいました（%s）" % k["title"][:40], "本人判断と食い違いだけの1枚を見てください",
                   [PAGE_BASE % k["issue"], k["url"]])


def matome(kai):
    k = load(kai_path(kai), None)
    if not k:
        raise SystemExit("回が無い")
    if atsumeru(k, use_gh=False):
        save(kai_path(kai), k)
    rows = kakidasu(k)
    for r in rows:
        print(r["id"], JOTAI_JA[r["jotai"]], r["kotae"], r["namae"])


# ---------------------------------------------------------------- 逆テスト
def self_test():
    ids = {"J1", "J2", "H1"}
    t = "判定者: Grok\n| ID | 判定 | 出典 | 一言 |\n|---|---|---|---|\nJ1 | 本人判断 | https://a.example/x | 住所\n| J2 | 対応不要 | https://b | ok |\nJ9 | 要対応 | x | 知らない行\nH1｜要確認｜｜わからない"
    got = parse_kaitou(t, ids)
    assert set(got) == {"J1", "J2", "H1"}, got
    assert got["J1"]["cat"] == "honnin" and got["J2"]["cat"] == "ok" and got["H1"]["cat"] == "fumei", got
    assert who_of(t) == "grok" and who_of("x", "chatgpt-codex-connector[bot]") == "chatgpt" and who_of("判定者: Genspark") == "genspark"
    assert cat_of("対応不要") == "ok" and cat_of("要対応") == "taiou" and cat_of("対象外") == "ok"
    assert "伏せた" in fusei("〒123-4567 東京都") and "伏せた" in fusei("03-1234-5678") and "伏せた" in fusei("a@b.co")
    k = {"kai": "t", "title": "t", "koumoku": [{"id": "J1", "namae": "特商法"}, {"id": "J2", "namae": "PP"}, {"id": "H1", "namae": "COPPA"}],
         "hantei": {"claude": {"J1": {"h": "本人判断", "cat": "honnin", "src": "", "memo": ""},
                               "J2": {"h": "対応不要", "cat": "ok", "src": "", "memo": ""}}}}
    ireru(k, "grok", got, "t", "2026-10-25T00:00:00Z")
    rows = {r["id"]: r["jotai"] for r in kuraberu(k)}
    assert rows == {"J1": "honnin", "J2": "itchi", "H1": "fumei"}, rows
    ireru(k, "chatgpt", {"J2": {"h": "要対応", "cat": "taiou", "src": "", "memo": ""}}, "t", "2026-10-25T01:00:00Z")
    assert {r["id"]: r["jotai"] for r in kuraberu(k)}["J2"] == "kuichigai"
    b = issue_body(k)
    assert b.startswith(MARK) and "法律の助言ではありません" in b and "🔴 食い違い" in b
    pg = page(k)
    assert "法律の助言ではありません" in pg and "PP" in pg and "COPPA" not in pg.split("決めなくてよかった")[0]
    assert ireru(k, "nanika", got, "t", "z") == 0
    print("SELF-TEST OK")


def main(a):
    if "--self-test" in a:
        return self_test()
    if "--hajime" in a:
        return hajime(a[a.index("--hajime") + 1])
    if "--matome" in a:
        return matome(a[a.index("--matome") + 1])
    if "--hyou" in a:   # 手で直した回（Claude の欄の訂正など）の表を Issue に書き直す
        kai = a[a.index("--hyou") + 1]
        k = load(kai_path(kai), None)
        rows = kakidasu(k)
        return print(gh(["api", "-X", "PATCH", "repos/%s/issues/%s" % (REPO_GH, k["issue"]), "-f", "body=" + issue_body(k, rows), "--jq", ".html_url"]))
    if "--tick" in a:
        return tick(force="--force" in a)
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
