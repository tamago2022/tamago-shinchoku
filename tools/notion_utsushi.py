#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Notion の写し係（notion_utsushi）— 2026-10-25 たまごさん指示。

たまごさん：「NotionもObsidianも、俺に関わる全AIは読めるようにしたい。一方通行は嫌。
  同じ部屋なのにパーティションがいっぱいある。それを取りたい」

■ 何をするか
  Notion のページを .md に書き出して、Google ドライブ「マイドライブ/tamago_brain/notion/」へ置く。
  Obsidian の写し（gdrive_md_mirror）と同じ部屋に入るので、ドライブを読めるAIは Notion も読める。
  ・Notion 公式API（無料・内部インテグレーションの鍵 NOTION_TOKEN）だけを使う。有料APIは使わない。
  ・差分だけ：last_edited_time が前回より新しいページだけ書き直す。1回の持ち時間は約3分、残りは次の回へ。
  ・鍵・お金・ログイン系の題のページ（ログイン／パスワード／鍵／口座／家計簿／暗証 等）は本文を写さない（題とURLだけ）。
  ・入口 notion/00_Notion索引.md（題・ドライブ上の写し・NotionのURL・更新日）。
  ・鍵（NOTION_TOKEN）が無い間は何もしない。代わりに振り分け所へ「鍵を作って置く」を1回だけ出す。

■ 使い方
  python3 tools/notion_utsushi.py --tick      # 心臓（top_status の相乗り）。中で 6時間に1回（書き出し途中なら10分に1回）
  python3 tools/notion_utsushi.py --now       # 間引きなしで1回
  python3 tools/notion_utsushi.py --self-test # 逆テスト（ネットに出ない）

作るもの：Drive tamago_brain/notion/*.md ／ status/notion_utsushi/{state.json,log} ／ status/public/notion_utsushi.json
台帳：tools/jidou_daicho.json の "notion_utsushi.py"（log 300行で刈る・ドライブの写しは上書きのみ）
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "notion_utsushi")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
PUB = os.path.join(REPO, "status", "public", "notion_utsushi.json")
OUT = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/tamago_brain/notion")
API = "https://api.notion.com/v1"
VER = "2022-06-28"
GATE_SEC = 6 * 3600
GATE_BACKLOG_SEC = 600
BUDGET_SEC = 180
INDEX = "00_Notion索引.md"
HIMITSU_RX = re.compile(r"ログイン|パスワード|password|Password|鍵|暗証|口座|家計簿|カード番号|マイナンバー|認証|秘密|機密|住所", re.I)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


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


def token():
    try:
        import kagi
        return kagi.get("NOTION_TOKEN") or kagi.get("NOTION_API_KEY")
    except Exception:
        return None


# ───────── API（urllib・Macの上だけで走る） ─────────
def call(tok, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + tok, "Notion-Version": VER, "Content-Type": "application/json"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                time.sleep(0.34)   # 1秒3回まで
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 + i * 3)
                continue
            raise
    raise RuntimeError("Notion API が混んでいて返らない")


def rich(rt):
    out = []
    for t in rt or []:
        s = t.get("plain_text", "")
        href = t.get("href")
        a = t.get("annotations") or {}
        if a.get("code"):
            s = "`%s`" % s
        if a.get("bold") and s.strip():
            s = "**%s**" % s
        if href:
            s = "[%s](%s)" % (s, href)
        out.append(s)
    return "".join(out)


def title_of(page):
    for v in (page.get("properties") or {}).values():
        if v.get("type") == "title":
            return rich(v.get("title")).strip() or "（無題）"
    return "（無題）"


def props_md(page):
    L = []
    for k, v in (page.get("properties") or {}).items():
        ty = v.get("type")
        val = v.get(ty)
        s = ""
        if ty in ("rich_text",):
            s = rich(val)
        elif ty in ("select", "status"):
            s = (val or {}).get("name", "")
        elif ty == "multi_select":
            s = ", ".join(x.get("name", "") for x in val or [])
        elif ty in ("number", "checkbox", "url", "email", "phone_number"):
            s = "" if val is None else str(val)
        elif ty == "date":
            s = (val or {}).get("start", "") or ""
        if s:
            L.append("- %s：%s" % (k, s))
    return L


def block_md(b, depth):
    ty = b.get("type")
    v = b.get(ty) or {}
    ind = "  " * depth
    t = rich(v.get("rich_text"))
    if ty == "paragraph":
        return ind + t
    if ty in ("heading_1", "heading_2", "heading_3"):
        return "#" * int(ty[-1]) + "# " + t if depth == 0 else ind + "**" + t + "**"
    if ty == "bulleted_list_item":
        return ind + "- " + t
    if ty == "numbered_list_item":
        return ind + "1. " + t
    if ty == "to_do":
        return ind + "- [%s] %s" % ("x" if v.get("checked") else " ", t)
    if ty == "toggle":
        return ind + "- ▸ " + t
    if ty == "quote":
        return ind + "> " + t
    if ty == "callout":
        return ind + "> " + ((v.get("icon") or {}).get("emoji") or "💡") + " " + t
    if ty == "code":
        return ind + "```%s\n%s\n%s```" % (v.get("language", ""), t, ind)
    if ty == "divider":
        return ind + "---"
    if ty in ("bookmark", "embed", "link_preview"):
        return ind + "- 🔗 " + (v.get("url") or "")
    if ty in ("image", "video", "file", "pdf", "audio"):
        u = (v.get("external") or {}).get("url") or "（Notion内のファイル）"
        cap = rich(v.get("caption"))
        return ind + "- [%s] %s %s" % (ty, cap, u if v.get("type") == "external" else "（Notion内のファイル・URLは期限付きなので写さない）")
    if ty == "child_page":
        return ind + "- 📄 子ページ：" + v.get("title", "")
    if ty == "child_database":
        return ind + "- 🗂 データベース：" + v.get("title", "")
    if ty == "link_to_page":
        return ind + "- → ページへのリンク " + (v.get("page_id") or v.get("database_id") or "")
    if ty == "table_row":
        return ind + "| " + " | ".join(rich(c) for c in v.get("cells", [])) + " |"
    if ty == "table":
        return ""
    if ty == "equation":
        return ind + "$" + v.get("expression", "") + "$"
    return ind + "（未対応のブロック：%s）" % ty


def page_md(tok, pid, t_end, max_blocks=3000):
    lines, n = [], [0]

    def walk(bid, depth):
        cur = None
        while True:
            if time.time() > t_end or n[0] > max_blocks:
                lines.append("（長いのでここまで。続きは Notion で）")
                return
            q = "/blocks/%s/children?page_size=100" % bid + ("&start_cursor=" + cur if cur else "")
            r = call(tok, "GET", q)
            for b in r.get("results", []):
                n[0] += 1
                lines.append(block_md(b, depth))
                if b.get("type") == "table":
                    walk(b["id"], depth)
                    continue
                if b.get("has_children") and b.get("type") not in ("child_page", "child_database") and depth < 4:
                    walk(b["id"], depth + 1)
            if not r.get("has_more"):
                return
            cur = r.get("next_cursor")
    walk(pid, 0)
    return "\n".join(x for x in lines if x is not None)


def fname(title, pid):
    t = re.sub(r"[\\/:*?\"<>|\n\r\t#^\[\]]", " ", title).strip()
    t = re.sub(r"\s+", " ", t)
    b = t.encode("utf-8")[:150].decode("utf-8", "ignore").strip() or "無題"
    return "%s__%s.md" % (b, pid.replace("-", "")[:8])


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)   # その場で上書き（差し替えるとドライブのURLが変わる）


def doc(page, title, body, himitsu):
    url = page.get("url", "")
    L = ["# " + title, "",
         "> Notion の写し（自動・%s）。正本は Notion：%s" % (now()[:16], url),
         "> 最終更新（Notion）：%s" % page.get("last_edited_time", "")[:16].replace("T", " "), ""]
    L += props_md(page)
    if L[-1] != "":
        L.append("")
    if himitsu:
        L.append("（題が鍵・お金・ログイン系なので、本文は写していません。Notion で開いてください）")
    else:
        L.append(body)
    return "\n".join(L) + "\n"


def index_md(pages):
    L = ["# 00_Notion索引", "",
         "> Notion のページの一覧（新しい順）。各ページは同じフォルダに .md で写してある。正本は Notion。自動生成：%s。%d ページ。" % (now()[:16], len(pages)),
         "> 鍵・お金・ログイン系の題のページは、本文を写さず題とURLだけ。", ""]
    for p in sorted(pages.values(), key=lambda x: x.get("le", ""), reverse=True):
        from urllib.parse import quote
        loc = "[写し](%s)" % quote(p["f"]) if p.get("f") else "（まだ写していない）"
        L.append("- %s ｜%s ｜[Notionで開く](%s) ｜更新 %s" % (p.get("t", "").replace("]", "］"), loc, p.get("url", ""), p.get("le", "")[:10]))
    return "\n".join(L) + "\n"


def furiwake_once(st):
    if st.get("furiwake_dashita"):
        return
    try:
        import furiwake
        furiwake.dasu(
            "Notion の公式API用の鍵（無料の内部インテグレーション）を作って、工場の鍵置き場に NOTION_TOKEN として置く",
            "Notion の中身を Google ドライブ tamago_brain/notion/ に定期で写す仕組み（tools/notion_utsushi.py）は出来ているが、鍵が無いので動けない。"
            "鍵を作るには notion.so/my-integrations にたまごさんのアカウントでログインする必要があり、工場（Mac上のClaude）はログイン画面を通れない。"
            "鍵ができたら、写したいページ（またはワークスペースの一番上のページ）の「接続」にそのインテグレーションを足す。",
            "~/.tamago/keys/api_keys.env に NOTION_TOKEN=... が入り、python3 tools/notion_utsushi.py --now で notion/00_Notion索引.md の件数が増えること",
            tags=["notion", "鍵", "ログイン"], who="notion_utsushi（工場）")
        st["furiwake_dashita"] = now()
        log("振り分け所へ：Notionの鍵づくりを出した")
    except Exception as e:
        log("振り分け所へ出せず：%s" % e)


def run(force=False):
    st = load(STATE, {})
    pages = st.setdefault("pages", {})
    gate = GATE_BACKLOG_SEC if st.get("backlog") else GATE_SEC
    if not force and time.time() - st.get("at_ts", 0) < gate:
        return "skip: 間引き"
    st["at_ts"] = time.time()
    tok = token()
    if not tok:
        furiwake_once(st)
        save(STATE, st)
        save(PUB, {"kousin": now(), "jotai": "鍵なし（NOTION_TOKEN）＝振り分け所に依頼済み", "pages": len(pages),
                   "okiba": "マイドライブ/tamago_brain/notion/"})
        return "鍵なし"
    if not os.path.isdir(os.path.dirname(OUT)):
        return "skip: ドライブが見えない"
    t0 = time.time()
    t_end = t0 + BUDGET_SEC
    # ① 一覧（新しい順）。前回の最新より古いところまで来たら止める（初回は全部）
    mark = st.get("mark", "")
    cur, seen, stop = None, 0, False
    while not stop and time.time() < t_end:
        body = {"page_size": 100, "filter": {"property": "object", "value": "page"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
        if cur:
            body["start_cursor"] = cur
        r = call(tok, "POST", "/search", body)
        for pg in r.get("results", []):
            if pg.get("archived") or pg.get("in_trash"):
                continue
            seen += 1
            le = pg.get("last_edited_time", "")
            if mark and le < mark and st.get("listed_all"):
                stop = True
                break
            pid = pg["id"]
            o = pages.get(pid, {})
            if o.get("le") != le:
                o.update({"t": title_of(pg), "url": pg.get("url", ""), "le": le, "todo": True})
                pages[pid] = o
        if not r.get("has_more"):
            st["listed_all"] = True
            break
        cur = r.get("next_cursor")
    # ② 本文を書き出す（新しい順・持ち時間まで）
    done = 0
    todo = sorted([k for k, v in pages.items() if v.get("todo")], key=lambda k: pages[k].get("le", ""), reverse=True)
    for pid in todo:
        if time.time() > t_end:
            break
        o = pages[pid]
        try:
            pg = call(tok, "GET", "/pages/" + pid)
            title = title_of(pg)
            him = bool(HIMITSU_RX.search(title))
            body = "" if him else page_md(tok, pid, t_end + 30)
            fn = o.get("f") or fname(title, pid)
            write(os.path.join(OUT, fn), doc(pg, title, body, him))
            o.update({"f": fn, "t": title, "todo": False})
            done += 1
        except Exception as e:
            o["err"] = str(e)[:200]
            log("error %s: %s" % (pid, e))
    if pages:
        st["mark"] = max(v.get("le", "") for v in pages.values())
    left = sum(1 for v in pages.values() if v.get("todo"))
    st["backlog"] = left > 0
    write(os.path.join(OUT, INDEX), index_md(pages))
    save(STATE, st)
    msg = "seen=%d wrote=%d left=%d total=%d sec=%d" % (seen, done, left, len(pages), time.time() - t0)
    save(PUB, {"kousin": now(), "jotai": "動いている" if not left else "書き出し途中（10分おきに続き）", "pages": len(pages),
               "nokori": left, "okiba": "マイドライブ/tamago_brain/notion/", "saigo": msg})
    log(msg)
    return msg


def self_test():
    b = [{"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "見出し"}]}},
         {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "本文", "href": "https://x"}]}},
         {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "やる"}], "checked": True}},
         {"type": "weird", "weird": {}}]
    out = [block_md(x, 0) for x in b]
    assert out[0] == "### 見出し" and out[1] == "[本文](https://x)" and out[2] == "- [x] やる" and "未対応" in out[3], out
    assert fname("a/b:c", "1234abcd-ef") == "a b c__1234abcd.md"
    assert HIMITSU_RX.search("ログイン方法一覧（2026-10）") and not HIMITSU_RX.search("グルメ　春")
    pg = {"url": "https://www.notion.so/x", "last_edited_time": "2026-10-25T01:02:00.000Z",
          "properties": {"名前": {"type": "title", "title": [{"plain_text": "鍵の一覧"}]}}}
    d = doc(pg, title_of(pg), "秘密の本文", True)
    assert "秘密の本文" not in d and "本文は写していません" in d
    ix = index_md({"a": {"t": "T", "url": "u", "le": "2026", "f": "T__a.md"}})
    assert "[写し](T__a.md)" in ix
    print("SELF-TEST OK")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    print(run(force=("--now" in a)))
