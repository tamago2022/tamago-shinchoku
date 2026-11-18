#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人物ページの「スマホ用の写し」（2026-11-19 店主：iPhoneのObsidianで人物ページのDataviewがコードのまま出る）。

決まり「Dataviewは結果を書き足した写しを置く」の機械の裏付け。AIは呼ばない。1日1回だけ（20時間ゲート）。

やること：
  1) Vault（tamago_brain）の .md を読むだけで索引を作る（タグ・リンク・aliases・people・題名・更新日）。
  2) 人物ページ（本文に  await dv.view("人物/_jinbutsu_view")  がある76枚）ごとに、
     人物/_jinbutsu_view.js と同じ決まりで「この人が出てくるノート」を拾う（Python に写したもの。
     --dry で索引を書き出し、node で本物の _jinbutsu_view.js を動かして突き合わせられる）。
  3) Dataview の塊はそのまま残し、そのすぐ下に
        <!-- jinbutsu-utsushi:start --> … <!-- jinbutsu-utsushi:end -->
     の1ブロックだけを置く／書き換える。本文のほかの所には触らない。中身が前回と同じなら書かない。
     写しの中のリンクは索引のときに数えない（写しが写しを呼ぶ循環を作らない）。
  4) Dataview が有効か（community-plugins.json・isDesktopOnly・enableDataviewJs）を見て記録。
     無効なら Dispatch へ1行（直すのはしない：10/6の軽量化のように店主の判断で止めることがあるため）。

使い方：python3 tools/jinbutsu/utsushi.py            … 1日1回（20時間ゲート）
        python3 tools/jinbutsu/utsushi.py --force    … ゲート無視で今すぐ
        python3 tools/jinbutsu/utsushi.py --dry DIR  … Vaultに書かず、DIR に索引と予定を出す
        python3 tools/jinbutsu/utsushi.py --self-test
作るもの：status/public/jinbutsu_utsushi.json（件数だけ・上書き）・status/jinbutsu_utsushi/runs.json（走った時刻・直近20回）。
          Vaultの人物ページの写しブロック（上書き・増えない）。消す役：不要。
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VAULT = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain")
OUT = os.path.join(REPO, "status", "public", "jinbutsu_utsushi.json")
RUNS = os.path.join(REPO, "status", "jinbutsu_utsushi", "runs.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
GATE_SEC = 20 * 3600
START, END = "<!-- jinbutsu-utsushi:start -->", "<!-- jinbutsu-utsushi:end -->"
VIEW_CALL = re.compile(r'dv\.view\(\s*["\']人物/_jinbutsu_view["\']\s*\)')

NFC = lambda s: unicodedata.normalize("NFC", str(s if s is not None else "")).strip()
LOW = lambda s: NFC(s).lower()

# ---- _jinbutsu_view.js の WADAI と同じ（向こうを直したらここも） ----
WADAI = [
    ("AI", re.compile(r"(^|[^a-z])ai|ＡＩ|人工知能|生成|chatgpt|gpt|claude|クロード|grok|gemini|llm|エージェント|ロボット|ヒューマノイド|シンギュラリティ|テクノロジー|自動化|デジタル|アルゴリズム|プロンプト|第二の脳|テック", re.I)),
    ("社会・経済", re.compile(r"経済|政治|社会|税|円安|インフレ|デフレ|物価|金融|お金|投資|株|不動産|格差|貧困|移民|選挙|政府|国家|官僚|戦争|軍事|地政学|中国|アメリカ|米国|イスラエル|イラン|ロシア|グローバル|資本|年金|監視|メディア|陰謀|利権|天下り|自民党|憲法|国際|外交|財務省")),
    ("暮らし・健康", re.compile(r"健康|食|医療|ワクチン|添加物|薬|病|癌|ゲノム|レシピ|グルメ|料理")),
    ("生き方・心", re.compile(r"幸福|悟り|生き方|人生|キャリア|働き方|メンタル|感謝|波動|心の時代|自己|安心|一人一宇宙")),
    ("ビジネス", re.compile(r"ビジネス|マーケ|起業|経営|副業|集客|ファネル|稼|ソロプレナー|コンテンツ|ceo|実業家|ブランディング", re.I)),
    ("笑い・エンタメ", re.compile(r"笑い|お笑い|芸人|コント|音楽|music|映画|アニメ|エンタメ|ユーモア|ダンス|モノマネ", re.I)),
]


def wadai_of(tags):
    s = " ".join(tags.keys())
    return [n for n, rx in WADAI if rx.search(s)]


def _han(ch):
    o = ord(ch)
    return ch in "々〇〻" or 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x3FFFF


def nagai(y):
    if len(y) >= 2 and all(_han(c) for c in y):
        return True
    if all(ord(c) < 0x80 for c in y):
        return len(y) >= 4
    return len(y) >= 3


# ---- 索引（Obsidian／Dataview の読み方に寄せる） ----
TAG_RE = re.compile(r"(?:^|(?<=\s))#([^ -⁯⸀-⹿'!\"#$%&()*+,.:;<=>?@^`{|}~\[\]\\\s]+)", re.M)
LINK_RE = re.compile(r"!?\[\[([^\]\|#\^\n]*)(?:[#\^][^\]\|\n]*)?(?:\|[^\]\n]*)?\]\]")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
REGION_RE = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def fm_split(t):
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(\n|$)", t, re.S)
    if not m:
        return None, t
    return m.group(1), t[m.end():]


def fm_list(fm, key):
    """frontmatter の key を文字列のリストで（YAMLの - 並び・[a, b]・a, b・1つだけ）。"""
    if not fm:
        return []
    m = re.search(r"^" + re.escape(key) + r":[ \t]*(.*?)(?=^\S|\Z)", fm, re.S | re.M)
    if not m:
        return []
    raw = m.group(1)
    out = []
    first = raw.split("\n", 1)[0].strip()
    if first:
        if first.startswith("["):
            parts = first.strip("[]").split(",")
        else:
            parts = first.split(",") if key in ("tags", "tag", "aliases", "alias", "people") else [first]
    else:
        parts = [l.strip()[1:] for l in raw.split("\n") if l.strip().startswith("-")]
    for x in parts:
        x = x.strip().strip("\"'").strip()
        if x:
            out.append(x)
    return out


def parse(t):
    fm, body = fm_split(t)
    tags = []
    for x in fm_list(fm, "tags") + fm_list(fm, "tag"):
        for y in re.split(r"[\s,]+", x):
            y = y.lstrip("#")
            if y:
                tags.append(y)
    b = REGION_RE.sub("", body)          # 写しの中のリンクは数えない
    b = FENCE_RE.sub("", b)
    b = re.sub(r"`[^`\n]*`", "", b)
    b = re.sub(r"<!--.*?-->", "", b, flags=re.S)
    b = re.sub(r"%%.*?%%", "", b, flags=re.S)
    for x in TAG_RE.findall(b):
        if re.fullmatch(r"[0-9/]+", x):
            continue
        tags.append(x.rstrip("/"))
    full = []
    seen = set()
    for x in tags:
        ps = x.split("/")
        for i in range(1, len(ps) + 1):
            k = "/".join(ps[:i])
            if k and k not in seen:
                seen.add(k)
                full.append("#" + k)
    links = [x.strip() for x in LINK_RE.findall(b) if x.strip()]
    for x in re.findall(r"\[\[([^\]\|#\^\n]+)", fm or ""):   # frontmatter のリンクも Dataview は数える
        links.append(x.strip())
    one = lambda k: (fm_list(fm, k) or [None])[0]
    return {"tags": full, "links": links, "aliases": fm_list(fm, "aliases") + fm_list(fm, "alias"),
            "people": fm_list(fm, "people"), "jinbutsu": one("jinbutsu"),
            "nozoku": fm_list(fm, "jinbutsu_nozoku")}


def index(V):
    files = []
    for root, ds, fs in os.walk(V):
        ds[:] = [d for d in ds if not d.startswith(".")]
        for f in fs:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, V)
            try:
                st = os.stat(p)
                if st.st_size > 5_000_000:
                    continue
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    t = fh.read()
            except Exception:
                continue
            d = parse(t)
            d.update(path=rel, size=st.st_size, mtime=st.st_mtime, text=t)
            files.append(d)
    # リンクの行き先（Obsidian：パスが合えばそれ、無ければ同じ名前のノートの中でパスが短いもの）
    bypath = {LOW(f["path"][:-3]): f["path"] for f in files}
    byname = {}
    for f in sorted(files, key=lambda f: (len(f["path"]), f["path"])):
        byname.setdefault(LOW(os.path.basename(f["path"])[:-3]), f["path"])
    for f in files:
        out = []
        for l in f["links"]:
            k = LOW(l[:-3] if l.lower().endswith(".md") else l)
            r = bypath.get(k) or (byname.get(k) if "/" not in k else byname.get(k.split("/")[-1]) if k not in bypath else None)
            out.append(r if r else l)
        f["outlinks"] = out
    return files


def shita(files):
    notes = []
    for f in files:
        if f["size"] == 0:
            continue
        path = NFC(f["path"])
        if path.startswith("人物/00_") or path.endswith(".js"):
            continue
        tags = {}
        for t in f["tags"]:
            tags[LOW(t).lstrip("#")] = NFC(t)
        links = {}
        for l in f["outlinks"]:
            full = re.sub(r"\.md$", "", NFC(l))
            links[LOW(full.split("/")[-1])] = full
            links[LOW(full)] = full
        notes.append({"f": f, "path": path, "title": NFC(os.path.basename(f["path"])[:-3]), "tags": tags,
                      "links": links, "people": [LOW(x) for x in f["people"]]})
    return notes


def yobikata(me):
    al = []
    for a in me["aliases"]:
        a = NFC(a)
        if a and a not in al:
            al.append(a)
    return al or [NFC(os.path.basename(me["path"])[:-3])]


def hirou(me, yobi, notes):
    Y = [(y, LOW(y), nagai(y)) for y in yobi]
    NG = [LOW(x) for x in me["nozoku"] if LOW(x)]
    ng = lambda s: any(w in s for w in NG)
    me_path = re.sub(r"\.md$", "", NFC(me["path"]))
    rows = []
    for n in notes:
        if n["path"] == NFC(me["path"]):
            continue
        why = []
        add = lambda w: why.append(w) if w not in why else None
        for t, moto in n["tags"].items():
            if ng(t):
                continue
            last = t.split("/")[-1]
            for y, ly, ok in Y:
                if t == ly or last == ly or (ok and ly in t):
                    add(moto)
        for k, full in n["links"].items():
            if full == me_path:
                add("[[" + full.split("/")[-1] + "]]")
            for y, ly, ok in Y:
                if k == ly:
                    add("[[" + full.split("/")[-1] + "]]")
        for y, ly, ok in Y:
            if ly in n["people"]:
                add("people欄")
        if not ng(LOW(n["title"])):
            for y, ly, ok in Y:
                if ok and ly in LOW(n["title"]):
                    add("題名")
                    break
        if why:
            rows.append((n, why))
    rows.sort(key=lambda r: -r[0]["f"]["mtime"])
    return rows


# ---- 写しのブロック ----
def link_md(path):
    p = path[:-3]
    name = os.path.basename(p)
    if re.search(r"[\[\]\|#\^]", p):
        return name.replace("|", "／")
    return "[[%s\\|%s]]" % (p, name)


def block(me, hi):
    yobi = yobikata(me)
    rows = hirou(me, yobi, NOTES)
    cnt = {}
    body = []
    for n, why in rows:
        w = wadai_of(n["tags"])
        for x in w:
            cnt[x] = cnt.get(x, 0) + 1
        body.append("| %s | %s | %s |" % (link_md(n["f"]["path"]), "・".join(w), time.strftime("%Y-%m-%d", time.localtime(n["f"]["mtime"]))))
    naiyou = "／".join("%s %d" % (n, cnt[n]) for n, _ in WADAI if cnt.get(n))
    core = ["呼び方 %d 通り（%s）で **%d 件**" % (len(yobi), "・".join(yobi), len(rows)) + ("　｜　話題：" + naiyou if naiyou else ""), ""]
    if body:
        core += ["| ノート | 話題 | 更新 |", "|---|---|---|"] + body
    return core, len(rows)


def kakikomi(t, core, hi):
    """Dataviewの塊の下に写しを置く／前の写しを置き換える。中身（日付以外）が同じなら None。"""
    m = REGION_RE.search(t)
    if m:
        old = m.group(0)
        old_core = old.split("\n")[3:-1] if old.count("\n") >= 3 else []
        if old_core == core:
            return None
    head = "### （スマホ用の写し・%s更新）" % hi
    note = "Dataviewが動かない時（スマホなど）に見る用。上の自動の表と同じ決まりで、1日1回書き直す。"
    new = "\n".join([START, head, note] + core + [END])
    if m:
        return t[:m.start()] + new + t[m.end():]
    # Dataview の塊（_jinbutsu_view を呼ぶもの）の閉じ ``` の直後に入れる
    mv = VIEW_CALL.search(t)
    if not mv:
        return None
    close = re.compile(r"^```[ \t]*$", re.M).search(t, mv.end())
    if not close:
        return None
    pos = close.end()
    return t[:pos] + "\n\n" + new + "\n" + t[pos:]


NOTES = []


def run(V, dry=None):
    global NOTES
    t0 = time.time()
    files = index(V)
    NOTES = shita(files)
    hi = "%d月%d日" % (time.localtime().tm_mon, time.localtime().tm_mday)
    people = [f for f in files if VIEW_CALL.search(f["text"])]
    res = {"jinbutsu": len(people), "kaita": 0, "onaji": 0, "dekinai": 0, "kensuu": 0, "err": 0}
    plan = {}
    for me in people:
        core, n = block(me, hi)
        res["kensuu"] += n
        new = kakikomi(me["text"], core, hi)
        if new is None:
            if REGION_RE.search(me["text"]):
                res["onaji"] += 1
            else:
                res["dekinai"] += 1
            continue
        if dry:
            plan[me["path"]] = new
            res["kaita"] += 1
            continue
        p = os.path.join(V, me["path"])
        try:
            with open(p, encoding="utf-8") as fh:
                cur = fh.read()
            if cur != me["text"]:          # 読んだ後に誰かが書いた → 今日は触らない
                res["err"] += 1
                continue
            tmp = p + ".utsushi.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(new)
            os.replace(tmp, p)
            res["kaita"] += 1
        except Exception:
            res["err"] += 1
    res["sec"] = round(time.time() - t0, 1)
    if dry:
        os.makedirs(dry, exist_ok=True)
        pages = [{"path": f["path"], "name": os.path.basename(f["path"])[:-3], "folder": os.path.dirname(f["path"]),
                  "size": f["size"], "mtime": f["mtime"], "tags": f["tags"], "outlinks": f["outlinks"],
                  "aliases": f["aliases"], "people": f["people"], "jinbutsu": f["jinbutsu"], "nozoku": f["nozoku"],
                  "view": bool(VIEW_CALL.search(f["text"]))} for f in files]
        json.dump(pages, open(os.path.join(dry, "pages.json"), "w"), ensure_ascii=False)
        py = {}
        for me in people:
            py[me["path"]] = [n["path"] for n, _ in hirou(me, yobikata(me), NOTES)]
        json.dump(py, open(os.path.join(dry, "py_rows.json"), "w"), ensure_ascii=False)
        json.dump(plan, open(os.path.join(dry, "plan.json"), "w"), ensure_ascii=False)
    return res


def dv_joutai(V):
    o = os.path.join(V, ".obsidian")
    r = {}
    try:
        r["community_plugins_ni_aru"] = "dataview" in json.load(open(os.path.join(o, "community-plugins.json")))
    except Exception as e:
        r["community_plugins_ni_aru"] = None
    try:
        r["isDesktopOnly"] = json.load(open(os.path.join(o, "plugins", "dataview", "manifest.json"))).get("isDesktopOnly")
    except Exception:
        r["isDesktopOnly"] = None
    try:
        d = json.load(open(os.path.join(o, "plugins", "dataview", "data.json")))
        r["enableDataviewJs"] = d.get("enableDataviewJs", False)
    except Exception:
        r["enableDataviewJs"] = None
    r["main_js"] = os.path.exists(os.path.join(o, "plugins", "dataview", "main.js"))
    return r


def _runs():
    try:
        return json.load(open(RUNS))
    except Exception:
        return []


def main():
    args = sys.argv[1:]
    if "--dry" in args:
        d = args[args.index("--dry") + 1]
        print(json.dumps(run(VAULT, dry=d), ensure_ascii=False))
        return
    runs = _runs()
    if "--force" not in args and runs and time.time() - runs[-1] < GATE_SEC:
        return
    runs = (runs + [time.time()])[-20:]
    os.makedirs(os.path.dirname(RUNS), exist_ok=True)
    json.dump(runs, open(RUNS, "w"))
    res = run(VAULT)
    dv = dv_joutai(VAULT)
    res.update(at=time.strftime("%Y-%m-%d %H:%M"), dataview=dv,
               note="人物ページのDataviewの下に、普通のリンクの表で写しを置く（スマホ用）。AIなし・1日1回。")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    json.dump(res, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    if dv.get("community_plugins_ni_aru") is False or dv.get("isDesktopOnly") or dv.get("enableDataviewJs") is False:
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "jinbutsu_utsushi",
               "title": "ObsidianのDataviewが無効になっている（人物ページは写しで見える）",
               "message": "community-plugins.json に dataview=%s／isDesktopOnly=%s／enableDataviewJs=%s" % (
                   dv.get("community_plugins_ni_aru"), dv.get("isDesktopOnly"), dv.get("enableDataviewJs"))}
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(res, ensure_ascii=False))


def selftest():
    global NOTES
    t = tempfile.mkdtemp(prefix="jinbutsu_utsushi_")
    try:
        os.makedirs(os.path.join(t, "人物"))
        os.makedirs(os.path.join(t, "メモ"))
        page = ("---\naliases:\n  - 長嶋修\n  - 長嶋さん\njinbutsu: 発信者\n---\n# 長嶋修\n\n本文は残す。\n\n"
                "```dataviewjs\nawait dv.view(\"人物/_jinbutsu_view\")\n```\n\n## 下の段落も残す\n")
        open(os.path.join(t, "人物", "長嶋修（人物）.md"), "w").write(page)
        open(os.path.join(t, "メモ", "a.md"), "w").write("今日の話 #長嶋さん\n")
        open(os.path.join(t, "メモ", "長嶋修　金融の話.md"), "w").write("題名だけ\n")
        open(os.path.join(t, "メモ", "c.md"), "w").write("[[長嶋修]] を見た\n")
        open(os.path.join(t, "メモ", "d.md"), "w").write("関係ない `#長嶋さん`\n```\n#長嶋さん\n```\n")
        open(os.path.join(t, "メモ", "e.md"), "w").write("")
        r = run(t)
        assert r["jinbutsu"] == 1 and r["kaita"] == 1, r
        txt = open(os.path.join(t, "人物", "長嶋修（人物）.md")).read()
        assert "本文は残す。" in txt and "## 下の段落も残す" in txt and 'await dv.view("人物/_jinbutsu_view")' in txt, txt
        assert txt.index("```\n\n" + START) < txt.index("## 下の段落も残す"), txt
        assert "**3 件**" in txt, txt                    # a(タグ)・長嶋修 金融の話(題名)・c(リンク)。d（コードの中だけ）と e（空）は拾わない
        r2 = run(t)
        assert r2["kaita"] == 0 and r2["onaji"] == 1, r2   # 2回目は書かない
        assert open(os.path.join(t, "人物", "長嶋修（人物）.md")).read().count(START) == 1
        print("jinbutsu utsushi self-test OK")
    finally:
        shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    selftest() if "--self-test" in sys.argv else main()
