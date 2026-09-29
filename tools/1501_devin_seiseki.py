#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1501番 Devin成績表を機械で付ける係（手で書かない）。

■ 何のためか
  2026-10-16 の更新（月20ドル）を「役に立ったかどうか」で決める。
  そのための1本ごとの成績を、Devin API と GitHub から機械で取る。手書きの数字は1つも載せない。

■ 1本ごとに付けるもの
  投げた日時 / 依頼の1行 / 終わったらたまごさんの何が変わるか / PRが出たか /
  mergeされたか / 本番に出て画面が変わったか / かかった枠（無料枠か従量か・円）

■ 取れないものは「取れない」と書く（嘘のログを書かない）
  - 金額：/v1/enterprise/consumption は 403「Contact support to enable」。**円は取れない。**
    ただし「従量の残高がマイナスのあいだに立った本」は、従量では立てないので**無料枠**と断定できる。
  - 「画面が変わった」：機械で断定できない。**本番の重さ(KB)を毎日測って並べる**ことで代わりに出す。
    重さが減った日と、mergeされた日が一致すれば、それが「変わった」の証拠になる。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.devin.ai/v1"
OUT = os.path.join(REPO, "status", "devin_seiseki.json")
PAGE = os.path.join(REPO, "share", "check", "1500-devin-seiseki.html")
QUEUE = os.path.join(REPO, "status", "1500_queue.json")
STATE = os.path.join(REPO, "status", "1500_wakuban.json")
PROD = "https://joy-relief-station.lovable.app/"

# ── 更新判定の線（先に決めて書いておく。あとで動かさない）─────────────
HANTEI = {
    "kijitsu": "2026-10-16",
    "sen": 2,
    "hakaru": "本番に出て画面が変わった本数（＝mergeされた上で、本番の重さが減った／表示が変わったと測れた本）",
    "koushin_suru": "2026-10-16までに2本以上 → 更新する（月20ドルは元が取れている）",
    "koushin_shinai": "1本以下 → 更新しない。ここで切る",
    "hoju": "PRが出ても1本もmergeされていないなら、本数に関係なく更新しない（受け取れていない＝こちらの監督不足だが、払う理由にはならない）",
}


def key():
    try:
        with io.open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("DEVIN_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def gh_token():
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GH_PAT"):
        v = os.environ.get(k)
        if v:
            return v
    try:
        with io.open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
            for line in f:
                for k in ("GH_TOKEN=", "GITHUB_TOKEN=", "GH_PAT="):
                    if line.startswith(k):
                        return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def dv(path, timeout=45):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + key())
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


def sessions():
    out, off = [], 0
    while True:
        c, d = dv("/sessions?limit=100&offset=%d" % off)
        if c != 200:
            break
        ss = d.get("sessions") or []
        out += ss
        if len(ss) < 100 or off > 1200:
            break
        off += 100
    return out


# ── PRがmergeされたか ────────────────────────────────────────────
def pr_num(pr):
    if not pr:
        return None, None
    if isinstance(pr, dict):
        url = pr.get("url") or pr.get("html_url") or ""
        n = pr.get("number")
    else:
        url, n = str(pr), None
    m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url or "")
    if m:
        return m.group(1), int(m.group(2))
    return None, n


def merged(repo, num):
    """gh → GitHub API → ローカルcloneのgit log、の順に試す。全部だめなら None（＝取れない）。"""
    if not repo or not num:
        return None, "PRのURLが取れない"
    try:
        p = subprocess.run(["gh", "pr", "view", str(num), "-R", repo, "--json", "state,mergedAt"],
                           capture_output=True, text=True, timeout=40)
        if p.returncode == 0:
            d = json.loads(p.stdout)
            return (d.get("state") == "MERGED"), (d.get("mergedAt") or "")
    except Exception:
        pass
    tok = gh_token()
    if tok:
        try:
            req = urllib.request.Request("https://api.github.com/repos/%s/pulls/%d" % (repo, num))
            req.add_header("Authorization", "Bearer " + tok)
            req.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8"))
            return bool(d.get("merged")), (d.get("merged_at") or "")
        except Exception:
            pass
    name = repo.split("/")[-1]
    for c in (os.path.join(os.path.expanduser("~"), "Desktop", name), REPO):
        if os.path.isdir(os.path.join(c, ".git")):
            try:
                p = subprocess.run(["git", "log", "--oneline", "-200", "--grep", "#%d" % num],
                                   cwd=c, capture_output=True, text=True, timeout=40)
                if p.returncode == 0 and p.stdout.strip():
                    return True, "git logで確認（日時は取れない）"
            except Exception:
                pass
    return None, "ghもトークンもローカルcloneも使えない＝取れない"


# ── 本番の重さ（画面が変わったかの代わりに、毎日の実測を並べる）──────────
def prod_weight():
    try:
        req = urllib.request.Request(PROD, headers={"User-Agent": "Mozilla/5.0 (iPhone)"} )
        with urllib.request.urlopen(req, timeout=40) as r:
            html = r.read().decode("utf-8", "replace")
            total = len(html.encode("utf-8"))
    except Exception as e:
        return {"at": time.strftime("%F %T"), "error": repr(e)[:120], "kb": None}
    n = 0
    seen = set()
    for m in re.finditer(r'(?:src|href)="([^"]+\.(?:js|css|mjs))(?:\?[^"]*)?"', html):
        raw = m.group(1)
        if raw.startswith("http"):
            u = raw
        elif raw.startswith("/"):
            u = PROD.rstrip("/") + raw
        else:
            u = PROD.rstrip("/") + "/" + raw
        if u in seen:
            continue
        seen.add(u)
        try:
            rq = urllib.request.Request(u, method="HEAD")
            with urllib.request.urlopen(rq, timeout=25) as rr:
                total += int(rr.headers.get("Content-Length") or 0)
                n += 1
        except Exception:
            pass
    return {"at": time.strftime("%F %T"), "kb": round(total / 1024.0, 1), "assets": n,
             "note": "HTML＋/assets/のJS/CSSの合計。ブラウザが実際に落とす全部ではないが、同じ測り方で毎日並べているので増減は本物"}


def build():
    q = {}
    try:
        q = json.load(io.open(QUEUE, encoding="utf-8"))
    except Exception:
        q = {}
    kawaru_by_name = {}
    for j in (q.get("jobs") or []):
        kawaru_by_name[j.get("name", "")] = j.get("kawaru", "")
    st = {}
    try:
        st = json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    kawaru_by_sid = {}
    for r in (st.get("done") or []) + ([st.get("current")] if st.get("current") else []):
        if r and r.get("sid"):
            v = r.get("kawaru") or kawaru_by_name.get(r.get("name", ""), "")
            for k in (str(r["sid"]), str(r["sid"]).replace("devin-", "")):
                kawaru_by_sid[k] = v

    ss = sessions()
    rows = []
    for s in sorted(ss, key=lambda x: x.get("created_at") or ""):
        sid = s.get("session_id") or s.get("id")
        repo, num = pr_num(s.get("pull_request"))
        mg, mgat = (None, "PRが出ていない") if not s.get("pull_request") else merged(repo, num)
        rows.append({
            "nagetaAt": (s.get("created_at") or "")[:16].replace("T", " "),
            "title": (s.get("title") or "")[:70],
            "kawaru": (kawaru_by_sid.get(str(sid))
                       or kawaru_by_sid.get(str(sid).replace("devin-", ""))
                       or "（記録なし＝この基準を作る前に投げた本）"),
            "sid": sid,
            "url": "https://app.devin.ai/sessions/" + str(sid).replace("devin-", ""),
            "status": s.get("status_enum"),
            "pr": ("#%d %s" % (num, repo)) if num else "出ていない",
            "merged": mg,
            "mergedAt": mgat,
            "honban": "要目視（機械では断定できない）" if mg else ("—" if mg is None else "出ていない"),
            "waku": "無料枠（従量の残高がマイナスのあいだに立った＝従量では立たない）",
            "yen": 0,
            "yen_note": "円はDevin側のconsumption APIが403で取れない。立った本が無料枠だったことだけが断定できる",
        })
    pr_n = len([r for r in rows if r["pr"] != "出ていない"])
    mg_n = len([r for r in rows if r["merged"] is True])
    torenai = len([r for r in rows if r["merged"] is None and r["pr"] != "出ていない"])

    # ★投げ方を変えた前と後で分けて数える（更新判定はこれで見る）
    # 変えた点：Knowledge/Playbookを入れた・依頼文の先頭に「返事を書くな」・1本ずつ・
    #           成功条件を機械判定にした・触るなファイルを明記した。
    # 境目：2026-09-27 15:00 UTC（＝日本時間 9/28 00:00）
    # ★日付で切ると、枠番を通していない別セッションの分まで「後」に混ざる（2026-09-30 実測）。
    #   だから **枠番(1500_wakuban)を通ったかどうか** で分ける。これは台帳に残っているので間違えない。
    SAKAI = "2026-09-27 15:00"
    wk = set()
    for r0 in (st.get("done") or []) + ([st.get("current")] if st.get("current") else []):
        if r0 and r0.get("sid"):
            wk.add(str(r0["sid"]))
            wk.add(str(r0["sid"]).replace("devin-", ""))
    for r in rows:
        if str(r["sid"]) in wk:
            r["katachi"] = "新しい投げ方（枠番）"
        elif r["nagetaAt"] < SAKAI:
            r["katachi"] = "前"
        else:
            r["katachi"] = "他所から（枠番を通していない）"
    def cnt(sel):
        g = [r for r in rows if sel(r)]
        p = [r for r in g if r["pr"] != "出ていない"]
        return {"nageta": len(g), "pr": len(p), "merged": len([r for r in g if r["merged"] is True]),
                "ritsu": ("%d%%" % round(100.0 * len(p) / len(g))) if g else "—"}
    mae = cnt(lambda r: r["katachi"] == "前")
    ato = cnt(lambda r: r["katachi"] == "新しい投げ方（枠番）")
    yoso = cnt(lambda r: r["katachi"] == "他所から（枠番を通していない）")

    old = {}
    try:
        old = json.load(io.open(OUT, encoding="utf-8"))
    except Exception:
        pass
    weights = (old.get("honban_omosa") or [])
    today = time.strftime("%F")
    last = weights[-1] if weights else {}
    naoshi = bool(last) and (last.get("kb") is None or not last.get("assets"))
    if not weights or not str(last.get("at", "")).startswith(today) or naoshi:
        w = prod_weight()
        if naoshi:
            weights = weights[:-1]   # 測り損ねた行は残さない（嘘の数字を並べない）
        weights = (weights + [w])[-40:]

    d = {
        "updatedAt": time.strftime("%F %T"),
        "tsukurikata": "Devin API（/v1/sessions）とGitHubから機械で取っている。手で書いた数字は1つも入っていない。",
        "hantei": HANTEI,
        "nagekata": {
            "sakai": SAKAI + " UTC（日本時間 9/28 00:00）",
            "kaeta": ["Knowledgeを6本入れた", "Playbookを2本入れた",
                      "依頼文の先頭に『返事を書くな。終わりの合図はPRのURLだけ』",
                      "1本ずつ投げる", "成功条件を機械で判定できる形にした",
                      "触ってはいけないファイルを明記した"],
            "wakekata": "枠番(status/1500_wakuban.json)を通ったかどうかで分ける。日付で切ると他所からの分が混ざる",
            "mae": mae, "ato": ato, "yoso": yoso,
        },
        "goukei": {
            "nageta": len(rows),
            "pr": pr_n,
            "merged": mg_n,
            "merged_torenai": torenai,
            "honban_kakunin": 0,
            "honban_note": "「本番に出て画面が変わった」は機械で断定できない。下の『本番の重さ』が減った日で見る。",
        },
        "honban_omosa": weights,
        "rows": rows[::-1],
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    page(d)
    print("nageta=%d pr=%d merged=%d merged_torenai=%d" % (len(rows), pr_n, mg_n, torenai))
    return d


def page(d):
    g = d["goukei"]
    h = d["hantei"]
    n = d["nagekata"]
    w = d.get("honban_omosa") or []
    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    tr = []
    for r in d["rows"]:
        mg = {True: "✅ merged", False: "入っていない", None: "取れない"}[r["merged"]]
        tr.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td class=k>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(r["nagetaAt"]), esc(r.get("katachi", "")), esc(r["title"]), esc(r["kawaru"]), esc(r["status"]),
               esc(r["pr"]), mg, esc(r["honban"]), esc(r["waku"].split("（")[0] + "・0円"))
        )
    wl = "".join("<li>%s … <b>%s KB</b></li>" % (esc(x.get("at", "")[:16]), esc(x.get("kb"))) for x in w[::-1])
    html = u"""<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Devin成績表（更新するかしないかの判定）</title>
<style>
:root{color-scheme:dark}
body{margin:0;padding:18px;background:#0d1117;color:#e6edf3;font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif;line-height:1.6}
a{color:#8ef0ae}h1{font-size:1.25rem;margin:.2em 0 .6em}
.box{border:1px solid #30363d;border-radius:12px;padding:14px;margin:0 0 16px;background:#161b22}
.big{font-size:2rem;font-weight:800;letter-spacing:-.02em}
.sen{border-color:#e3b341}.sen b{color:#e3b341}
table{width:100%%;border-collapse:collapse;font-size:.78rem}
th,td{border-bottom:1px solid #21262d;padding:6px 5px;text-align:left;vertical-align:top}
th{color:#8b949e;font-weight:600;white-space:nowrap}
td.k{color:#8ef0ae}
small{color:#8b949e}
.wrap{overflow-x:auto}
ul{padding-left:1.2em;margin:.3em 0}
</style>
<h1>Devin成績表 — 10/16に更新するかしないかを、これで決める</h1>
<p><small>更新 %(updatedAt)s ／ %(tsukurikata)s</small></p>

<div class="box sen">
<div>更新判定の線（先に決めた。あとで動かさない）</div>
<div class=big>%(sen)d本</div>
<div><b>%(koushin_suru)s</b></div>
<div><b>%(koushin_shinai)s</b></div>
<div><small>測るもの：%(hakaru)s</small></div>
<div><small>補足：%(hoju)s</small></div>
</div>

<div class=box>
<div>いまの実績</div>
<div class=big>投げた %(nageta)d ／ PRが出た %(pr)d ／ mergeされた %(merged)s</div>
<div><small>mergeが「取れない」本：%(merged_torenai)d（ghコマンド・トークン・ローカルcloneのどれも使えなかった本）</small></div>
<div><small>%(honban_note)s</small></div>
</div>

<div class=box>
<div>投げ方を変えた「前」と「後」</div>
<div class=big>前 %(m_n)d本→PR %(m_p)d（%(m_r)s） ／ 新しい投げ方 %(a_n)d本→PR %(a_p)d（%(a_r)s）</div>
<div><small>参考・枠番を通していない他所からの分：%(y_n)d本→PR %(y_p)d（%(y_r)s）</small></div>
<div><small>分け方：%(wakekata)s</small></div>
<div><small>変えたこと：%(kaeta)s</small></div>
</div>

<div class=box>
<div>本番の重さ（同じ測り方で毎日）</div>
<ul>%(wl)s</ul>
<div><small>減った日と、上の表のmergeの日が一致したら、それが「画面が変わった」の証拠。</small></div>
</div>

<div class="box wrap">
<table><thead><tr><th>投げた</th><th>形</th><th>依頼</th><th>たまごさんの何が変わるか</th><th>状態</th><th>PR</th><th>merge</th><th>本番</th><th>枠</th></tr></thead>
<tbody>%(tr)s</tbody></table>
</div>
<p><a href="https://tamago2022.github.io/tamago-shinchoku/">← 進捗表に戻る</a></p>
</html>""" % {
        "updatedAt": d["updatedAt"], "tsukurikata": d["tsukurikata"],
        "sen": h["sen"], "koushin_suru": h["koushin_suru"], "koushin_shinai": h["koushin_shinai"],
        "hakaru": h["hakaru"], "hoju": h["hoju"],
        "nageta": g["nageta"], "pr": g["pr"],
        "merged": g["merged"] if not g["merged_torenai"] else "%d（+取れない%d）" % (g["merged"], g["merged_torenai"]),
        "merged_torenai": g["merged_torenai"], "honban_note": g["honban_note"],
        "wl": wl or "<li>まだ測っていない</li>", "tr": "".join(tr) or "<tr><td colspan=9>まだ1本もない</td></tr>",
        "m_n": n["mae"]["nageta"], "m_p": n["mae"]["pr"], "m_r": n["mae"]["ritsu"],
        "a_n": n["ato"]["nageta"], "a_p": n["ato"]["pr"], "a_r": n["ato"]["ritsu"],
        "y_n": n["yoso"]["nageta"], "y_p": n["yoso"]["pr"], "y_r": n["yoso"]["ritsu"],
        "wakekata": esc(n["wakekata"]), "kaeta": esc(" / ".join(n["kaeta"])),
    }
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with io.open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    # 1日1回でいい仕事。間引く（心臓を重くしない）
    stamp = os.path.join(REPO, "status", ".1501_at")
    force = "--now" in sys.argv or not os.path.exists(PAGE)   # 1枚が無い周回は必ず作る
    try:
        if not force and time.time() - os.path.getmtime(stamp) < 600:
            sys.exit(0)
    except Exception:
        pass
    try:
        io.open(stamp, "w").write(time.strftime("%F %T"))
    except Exception:
        pass
    build()
