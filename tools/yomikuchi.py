#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各AIの読み口台帳（yomikuchi）— 2026-10-25 たまごさん指示。

たまごさん：「NotionもObsidianも、俺に関わる全AI（Claude・Grok・ChatGPT・Gensparkほか）は読めるようにしたい。
  各AIとの連携は常に調べておいて。一方通行は嫌。同じ部屋なのにパーティションがいっぱいある。それを取りたい」

■ 何をするか
  振り分け所の「できること台帳」（status/furiwake/dekiru_daicho.json）の各AIに "yomikuchi" を持たせ、
  Obsidian（Vault）／Googleドライブ（tamago_brain の写し）／GitHub／Notion の4つの部屋ごとに
  「読める・書ける」を ○（実測で通った）／△（機能はあるが未接続・未確認）／×（できない）で持つ。
  読めるのに書けない・書けるのに読めない＝片道、どちらも無い＝未接続 → 赤。赤の所には「つなぐ案」を1行。
  ・週1回（--tick の中で7日に1回）見直す：
      ① 工場の手元で測れるものは実測し直す（Notionの鍵・ドライブの写しが5分おきに動いているか・gh・Genspark の Notion の棚）
      ② 各社の公式ページ（新機能・コネクタ）を Mac の curl で読み、Drive／Notion／GitHub／コネクタ の新しい文があれば
         「新しい連携の候補」に積み、全AI共有メモ（#1040）へ1件・Dispatch へ1行
  ・出すもの：share/check/furiwake.html の中の「読み口」表（furiwake.kakidasu が html_table() を呼ぶ）、
      status/public/yomikuchi.json、ドライブ tamago_brain/00_AIの読み口台帳.md（どのAIからも読める所）

■ 使い方
  python3 tools/yomikuchi.py --tick       # 心臓（top_status の相乗り）。中で7日に1回
  python3 tools/yomikuchi.py --now        # 今すぐ見直し
  python3 tools/yomikuchi.py --kaku       # 測らずに台帳から表だけ書き出す
  python3 tools/yomikuchi.py --self-test

作るもの：status/yomikuchi/{state.json,log,news/*.txt} ／ status/public/yomikuchi.json ／ Drive tamago_brain/00_AIの読み口台帳.md
台帳：tools/jidou_daicho.json の "yomikuchi.py"（log 300行・news は上書きのみ）
"""
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DAICHO = os.path.join(REPO, "status", "furiwake", "dekiru_daicho.json")
D = os.path.join(REPO, "status", "yomikuchi")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
NEWS = os.path.join(D, "news")
PUB = os.path.join(REPO, "status", "public", "yomikuchi.json")
DRIVE_ROOT = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/tamago_brain")
DRIVE_MD = os.path.join(DRIVE_ROOT, "00_AIの読み口台帳.md")
MIRROR_LOG = os.path.expanduser("~/.tamago-sync/gdrive_md_mirror.log")
WEEK = 7 * 86400
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/furiwake.html#yomikuchi"
HEYA = [("obsidian", "Obsidian（Vault 原本）"), ("drive", "Googleドライブ（tamago_brain の写し＋notion/）"),
        ("github", "GitHub（共有メモ #1040・Issue・リポ）"), ("notion", "Notion")]
KIGOU = {"o": "○", "s": "△", "x": "×"}
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))

# 各社の公式の「新しく出たもの」ページ（Mac の curl で読む・無料）。増やすときはここに1行。
NEWS_SRC = [   # 2026-10-25 Mac の curl で実測して通ったもの（x.ai/news・help.openai.com は 403 なので使わない）
    ("grok", "https://docs.x.ai/docs/release-notes"),
    ("grok", "https://x.ai/news/grok-connectors"),
    ("chatgpt", "https://openai.com/news/rss.xml"),
    ("genspark", "https://www.genspark.ai/helpcenter/connectors-and-integrations"),
    ("claude", "https://support.claude.com/en/articles/12138966-release-notes"),
    ("notion", "https://www.notion.com/releases"),
]
NEWS_KW = re.compile(r"Google Drive|Notion|GitHub|connector|Connector|コネクタ|MCP|integration", re.I)

# 初期値（2026-10-25 時点の実測と公式・二次情報）。週1の見直しで工場の手元の分は実測で上書きする。
SHOKI = {
    "factory": {
        "obsidian": {"yomu": "o", "kaku": "o", "michi": "Mac の Vault を直接（実測）"},
        "drive": {"yomu": "o", "kaku": "o", "michi": "Drive for desktop。5分おきの写し gdrive_md_mirror（実測）"},
        "github": {"yomu": "o", "kaku": "o", "michi": "gh（実測）"},
        "notion": {"yomu": "x", "kaku": "x", "michi": "NOTION_TOKEN が無い（kagi_seimei）",
                   "tsunagu": "Notion の内部インテグレーションの鍵を1回作って api_keys.env に NOTION_TOKEN（振り分け所に依頼済み）→ notion_utsushi が notion/ へ定期で写す"},
    },
    "dispatch": {
        "obsidian": {"yomu": "o", "kaku": "o", "michi": "Cowork のフォルダ接続（/Users/mac）（実測）"},
        "drive": {"yomu": "o", "kaku": "o", "michi": "Google Drive コネクタ（検索・読む・作る・更新）（読むは実測）"},
        "github": {"yomu": "s", "kaku": "s", "michi": "サンドボックスから api.github.com に出られない。工場の窓口（oneshot・振り分け所・共有メモ係）経由で間接に読み書き",
                   "tsunagu": "今は工場経由で足りている。直通が要るときは Cowork に GitHub コネクタを足す"},
        "notion": {"yomu": "o", "kaku": "o", "michi": "Notion コネクタ（読むは実測 2026-10-25）"},
    },
    "grok": {
        "obsidian": {"yomu": "x", "kaku": "x", "michi": "直接は無い（ドライブの写し経由になる）",
                     "tsunagu": "Grok にドライブをつなげば、写し（Dataview の結果入り）で読める"},
        "drive": {"yomu": "s", "kaku": "s", "michi": "Grok Connectors（2026-05〜）に Google Drive がある。たまごさんの口座でつないだかは未確認",
                  "tsunagu": "grok.com の Connectors で Google Drive を1回つなぐ（ログイン1回）→ まず 00_索引_AIはここから読む.md を読ませる"},
        "github": {"yomu": "o", "kaku": "o", "michi": "共有メモを3時間ごとに読む・Issue を tamago2022 名義で書く（実測 #1028〜#1047）"},
        "notion": {"yomu": "s", "kaku": "s", "michi": "Grok Connectors に Notion がある。未接続（未確認）",
                   "tsunagu": "Connectors で Notion を1回つなぐ。つなぐまでは ドライブの notion/ の写しで読める（鍵が入れば）"},
    },
    "chatgpt": {
        "obsidian": {"yomu": "x", "kaku": "x", "michi": "直接は無い（ドライブの写し経由になる）",
                     "tsunagu": "ChatGPT にドライブをつなげば、写しで読める"},
        "drive": {"yomu": "s", "kaku": "x", "michi": "ChatGPT の Apps（旧コネクタ）に Google Drive（主に読む）。未接続（未確認）",
                  "tsunagu": "ChatGPT の設定 → Apps で Google Drive をつなぐ（ログイン1回）。書く側は GitHub（@codex）で返してもらう"},
        "github": {"yomu": "o", "kaku": "o", "michi": "Codex：Issue に @codex でコメント → PR／コメントで返る（#450 実測）。枠が今も残っているかは要確認"},
        "notion": {"yomu": "s", "kaku": "s", "michi": "ChatGPT の Apps に Notion がある。未接続（未確認）",
                   "tsunagu": "Apps で Notion をつなぐ（ログイン1回）"},
    },
    "genspark": {
        "obsidian": {"yomu": "x", "kaku": "x", "michi": "直接は無い（ドライブの写し経由になる）",
                     "tsunagu": "Genspark に Google Workspace をつなげば、写しで読める"},
        "drive": {"yomu": "s", "kaku": "s", "michi": "Genspark のコネクタに Google Workspace（Drive 含む）がある。未接続（未確認）。自分の AI Drive は読み書きできる（gsk・実測）",
                  "tsunagu": "Genspark の Skills → Connectors で Google Workspace を1回つなぐ（ログイン1回）"},
        "github": {"yomu": "s", "kaku": "x", "michi": "GitHub のコネクタは公式の一覧で見つからない。公開ページ（tamago-shinchoku の GitHub Pages）は Web で読める",
                   "tsunagu": "返事は AI Drive /tamago-inbox/ へ（claude_uketsuke が拾って GitHub へ運ぶ）で回っている"},
        "notion": {"yomu": "x", "kaku": "x", "michi": "Second Brain に Notion の棚が無い（gsk sb-brain ls -s notion・2026-09-24 実測）",
                   "tsunagu": "Genspark の Connectors で Notion を1回つなぐ（Notion API Call・読む／書く）"},
    },
}


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def log(msg):
    os.makedirs(D, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (now(), msg))
    try:
        ls = open(LOG, encoding="utf-8").read().splitlines()
        if len(ls) > 300:
            open(LOG, "w", encoding="utf-8").write("\n".join(ls[-300:]) + "\n")
    except Exception:
        pass


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def iro(c):
    """緑＝読み書き両方／赤（片道）＝片方だけ／赤（未接続）＝どちらも無い。△は「つながっていない」側に数える。"""
    y, k = c.get("yomu") == "o", c.get("kaku") == "o"
    if y and k:
        return "ok"
    if y or k:
        return "katamichi"
    return "misetsuzoku"


def merge_shoki(d):
    for a in d.get("ai", []):
        yk = a.setdefault("yomikuchi", {})
        for heya, _ in HEYA:
            if heya not in yk and heya in SHOKI.get(a["id"], {}):
                yk[heya] = dict(SHOKI[a["id"]][heya])
    return d


# ───────── 工場の手元で測れるもの ─────────
def jisoku(d):
    res = {}
    by = {a["id"]: a for a in d.get("ai", [])}
    f = by.get("factory", {}).get("yomikuchi", {})
    try:
        import kagi
        has = bool(kagi.get("NOTION_TOKEN") or kagi.get("NOTION_API_KEY"))
    except Exception:
        has = False
    if "notion" in f:
        if has:
            f["notion"].update({"yomu": "o", "kaku": "o", "michi": "NOTION_TOKEN あり（%s 実測）・notion_utsushi が notion/ へ写す" % now()[:10]})
            f["notion"].pop("tsunagu", None)
        res["notion_token"] = has
    try:
        last = open(MIRROR_LOG, encoding="utf-8").read().splitlines()[-1]
        ts = time.mktime(time.strptime(last[:19], "%Y-%m-%d %H:%M:%S"))
        fresh = time.time() - ts < 1800
    except Exception:
        fresh, last = False, ""
    res["mirror_fresh"] = fresh
    if "drive" in f:
        f["drive"]["yomu"] = f["drive"]["kaku"] = "o" if fresh else "s"
        f["drive"]["michi"] = "Drive for desktop。5分おきの写し gdrive_md_mirror（%s：%s）" % ("動いている" if fresh else "30分以上止まっている", now()[:10])
    try:
        p = subprocess.run([_exe("gh"), "auth", "status"], capture_output=True, text=True, timeout=30, env=ENV)
        res["gh"] = p.returncode == 0
        if "github" in f:
            f["github"]["yomu"] = f["github"]["kaku"] = "o" if p.returncode == 0 else "s"
    except Exception:
        pass
    g = by.get("genspark", {}).get("yomikuchi", {})
    try:
        p = subprocess.run([_exe("gsk"), "sb-brain", "ls", "-s", "notion"], capture_output=True, text=True, timeout=60, env=ENV)
        txt = (p.stdout + p.stderr)
        ok = p.returncode == 0 and "No mounted source" not in txt
        res["genspark_notion"] = ok
        if "notion" in g and ok:
            g["notion"].update({"yomu": "o", "kaku": "s", "michi": "Second Brain に Notion の棚がある（%s 実測）" % now()[:10]})
    except Exception:
        pass
    return res


def _exe(n):
    import shutil
    return shutil.which(n, path=ENV["PATH"]) or n


# ───────── 新しい連携の候補（各社の公式ページ） ─────────
def news_check(st):
    os.makedirs(NEWS, exist_ok=True)
    found = []
    for who, url in NEWS_SRC:
        try:
            p = subprocess.run(["curl", "-sL", "-m", "40", "-A", "Mozilla/5.0 (Macintosh) tamago-yomikuchi/1", url],
                               capture_output=True, timeout=60)
            t = p.stdout.decode("utf-8", "replace")
        except Exception as e:
            log("news %s 失敗 %s" % (who, e))
            continue
        t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)
        t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
        sents = set()
        for line in re.split(r"[\n。.!?]", t):
            line = re.sub(r"\s+", " ", line).strip()
            if 20 <= len(line) <= 300 and NEWS_KW.search(line):
                sents.add(line)
        key = "news_" + hashlib.md5(url.encode()).hexdigest()[:8]
        old = set(st.get(key, []))
        new = sorted(sents - old) if old else []
        st[key] = sorted(sents)[:400]
        open(os.path.join(NEWS, "%s_%s.txt" % (who, key[5:])), "w", encoding="utf-8").write("\n".join(sorted(sents)))
        for s in new[:10]:
            found.append({"who": who, "url": url, "bun": s, "at": now()})
    return found


# ───────── 書き出し ─────────
def html_table(d=None):
    """furiwake.kakidasu から呼ばれる（できること台帳のページに読み口の表を差し込む）。"""
    d = merge_shoki(d or load(DAICHO, {}))
    E = html.escape
    head = "".join("<th>%s</th>" % E(n) for _, n in HEYA)
    rows, an = [], []
    for a in d.get("ai", []):
        yk = a.get("yomikuchi", {})
        cells = []
        for heya, hn in HEYA:
            c = yk.get(heya)
            if not c:
                cells.append("<td>—</td>")
                continue
            col = {"ok": "#e7f6ea", "katamichi": "#ffd6d6", "misetsuzoku": "#ffb3b3"}[iro(c)]
            lab = {"ok": "", "katamichi": "<b style='color:#c00'>片道</b> ", "misetsuzoku": "<b style='color:#c00'>未接続</b> "}[iro(c)]
            cells.append("<td style='background:%s'>%s読む%s／書く%s<br><small>%s</small></td>" % (
                col, lab, KIGOU.get(c.get("yomu"), "?"), KIGOU.get(c.get("kaku"), "?"), E(c.get("michi", ""))))
            if iro(c) != "ok" and c.get("tsunagu"):
                an.append("<li><b>%s × %s</b>：%s</li>" % (E(a["namae"]), E(hn), E(c["tsunagu"])))
        rows.append("<tr><th>%s</th>%s</tr>" % (E(a["namae"]), "".join(cells)))
    st = load(STATE, {})
    cand = "".join("<li>%s（%s）<a href='%s'>元</a></li>" % (E(x["bun"]), E(x["who"]), E(x["url"])) for x in st.get("kouho", [])[-15:]) or "<li>今のところ無し</li>"
    return """<h2 id=yomikuchi>読み口（どのAIがどの部屋を読めて・書けるか）</h2>
<p>○＝実測で通った／△＝機能はあるが未接続・未確認／×＝できない。<b style='color:#c00'>赤</b>＝片道か未接続（部屋の仕切りが残っている所）。週1回 自動で見直し（最終 %s）。同じ表はドライブ tamago_brain/00_AIの読み口台帳.md にもある。</p>
<div style="overflow-x:auto"><table><tr><th>AI</th>%s</tr>%s</table></div>
<h3>つなぐ案（赤の所に1行ずつ）</h3><ul>%s</ul>
<h3>各社の公式ページで見つけた新しい連携の候補（週1）</h3><ul>%s</ul>
""" % (E(st.get("mita", "まだ")), head, "".join(rows), "".join(an) or "<li>赤なし</li>", cand)


def md_table(d):
    L = ["# 00_AIの読み口台帳", "",
         "> どのAIが、どの部屋（Obsidian／ドライブ／GitHub／Notion）を読めて・書けるか。自動生成・週1見直し（最終 %s）。" % load(STATE, {}).get("mita", now()),
         "> ○＝実測で通った／△＝機能はあるが未接続・未確認／×＝できない。🟥＝片道か未接続。",
         "> 同じ表（色つき）：%s" % PAGE_URL, "",
         "| AI | " + " | ".join(n for _, n in HEYA) + " |", "|---|" + "---|" * len(HEYA)]
    an = []
    for a in d.get("ai", []):
        yk = a.get("yomikuchi", {})
        cs = []
        for heya, hn in HEYA:
            c = yk.get(heya)
            if not c:
                cs.append("—")
                continue
            mark = "" if iro(c) == "ok" else ("🟥片道 " if iro(c) == "katamichi" else "🟥未接続 ")
            cs.append("%s読む%s／書く%s" % (mark, KIGOU.get(c.get("yomu"), "?"), KIGOU.get(c.get("kaku"), "?")))
            if iro(c) != "ok" and c.get("tsunagu"):
                an.append("- **%s × %s**：%s" % (a["namae"], hn, c["tsunagu"]))
        L.append("| %s | %s |" % (a["namae"], " | ".join(cs)))
    L += ["", "## つなぐ案（赤の所に1行ずつ）"] + (an or ["- 赤なし"])
    L += ["", "## 入口", "- まず [00_索引_AIはここから読む](00_%E7%B4%A2%E5%BC%95_AI%E3%81%AF%E3%81%93%E3%81%93%E3%81%8B%E3%82%89%E8%AA%AD%E3%82%80.md)",
          "- 仕事を頼み合う所：GitHub tamago2022/joy-relief-station のラベル「できる人いますか」／全AI共有メモ #1040"]
    return "\n".join(L) + "\n"


def kakidasu(d):
    save(PUB, {"kousin": now(), "page": PAGE_URL, "ai": [
        {"id": a["id"], "namae": a["namae"], "yomikuchi": {h: dict(c, iro=iro(c)) for h, c in a.get("yomikuchi", {}).items()}}
        for a in d.get("ai", [])]})
    if os.path.isdir(DRIVE_ROOT):
        try:
            tmp = os.path.join(DRIVE_ROOT, ".yk_tmp")
            open(tmp, "w", encoding="utf-8").write(md_table(d))
            os.replace(tmp, DRIVE_MD)
        except Exception as e:
            log("ドライブへ書けず %s" % e)
    try:
        import furiwake
        furiwake.kakidasu(furiwake.load(furiwake.IRAI, []))
    except Exception as e:
        log("台帳ページの作り直し失敗 %s" % e)


def run(force=False, sokutei=True):
    st = load(STATE, {})
    if not force and time.time() - st.get("at_ts", 0) < WEEK:
        return "skip: 週1"
    d = merge_shoki(load(DAICHO, {}))
    res, found = {}, []
    if sokutei:
        st["at_ts"] = time.time()
        st["mita"] = now()
        res = jisoku(d)
        found = news_check(st)
        if found:
            st.setdefault("kouho", []).extend(found)
            st["kouho"] = st["kouho"][-60:]
            body = "各社の公式ページに、Drive／Notion／GitHub／コネクタ まわりの新しい文が出ました（週1の見直し・yomikuchi.py）。\n" + \
                   "\n".join("- %s：%s（%s）" % (x["who"], x["bun"][:160], x["url"]) for x in found[:12]) + \
                   "\n読み口の表：" + PAGE_URL
            try:
                import zen_ai_kyouyu
                zen_ai_kyouyu.kaku("各AIの読み口：新しい連携の候補（%d件）" % len(found), body, who="yomikuchi（工場）")
            except Exception as e:
                log("共有メモへ書けず %s" % e)
            try:
                with open(os.path.join(REPO, "status", "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "n": "yomikuchi", "type": "yomikuchi",
                                        "title": "新しい連携の候補 %d件（読み口の見直し）" % len(found), "ok": True,
                                        "urls": [PAGE_URL], "result": found[0]["bun"][:200]}, ensure_ascii=False) + "\n")
            except Exception:
                pass
    d["_kousin"] = time.strftime("%Y-%m-%d")
    save(DAICHO, d)
    save(STATE, st)
    kakidasu(d)
    reds = sum(1 for a in d["ai"] for c in a.get("yomikuchi", {}).values() if iro(c) != "ok")
    msg = "jisoku=%s kouho=%d aka=%d" % (json.dumps(res, ensure_ascii=False), len(found), reds)
    log(msg)
    return msg


def self_test():
    assert iro({"yomu": "o", "kaku": "o"}) == "ok"
    assert iro({"yomu": "o", "kaku": "x"}) == "katamichi"
    assert iro({"yomu": "s", "kaku": "s"}) == "misetsuzoku"
    d = merge_shoki({"ai": [{"id": "grok", "namae": "Grokボット"}, {"id": "factory", "namae": "工場"}]})
    assert d["ai"][0]["yomikuchi"]["github"]["yomu"] == "o"
    h = html_table(d)
    assert "未接続" in h and "grok.com" in h and "id=yomikuchi" in h
    m = md_table(d)
    assert "🟥" in m and "| Grokボット |" in m
    # 既にある値は初期値で上書きしない
    d["ai"][0]["yomikuchi"]["drive"]["yomu"] = "o"
    d = merge_shoki(d)
    assert d["ai"][0]["yomikuchi"]["drive"]["yomu"] == "o"
    print("SELF-TEST OK")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--kaku" in a:
        print(run(force=True, sokutei=False))
    else:
        print(run(force=("--now" in a)))
