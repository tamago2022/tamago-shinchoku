#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工場の自動処理の棚卸し（2026-10-16・たまごさん「3万4千個を今気づくのは、自分たちのやってることを把握してない証拠。全部に責任を持て」）。

工場が自動で動かしているものを全部数え、1つずつ「何を・どこに作るか／片付け役は誰か」を台帳と突き合わせる。
  拾う場所：心臓（tools/heartbeat.sh の tick_every／.go の行）・心臓の相乗り（tools/top_status.py の _okosu）・
           launchd（~/Library/LaunchAgents の com.tamago.*）・cron（crontab -l）・GitHub Actions（.github/workflows）
  台帳（正本）：tools/jidou_daicho.json   キー＝名前（tools/xxx.py・launchd のラベル・workflow のファイル名）
           値＝{"tsukuru": 作るもの, "okiba": 置き場, "kesu": 消す役}
  中身の下見：各スクリプト（と、そこから呼んでいるスクリプト1段）を読み、一時フォルダ・ブラウザ・複製・動画/音・
           キャッシュ等を作っていそうかを機械で拾う（hint）。台帳に無いもの＝「片付け役なし」。
結果：status/jidou_tanaoroshi.json（全部）／status/public/jidou_tanaoroshi.json（進捗表 health.json の jidou が読む）
使い方：
  python3 tools/jidou_tanaoroshi.py            棚卸しして書く（心臓から1時間に1回。未登録があれば Dispatch に1行）
  python3 tools/jidou_tanaoroshi.py --check    未登録が1つでもあれば exit 2（関所：.githooks/pre-push・top_status の _okosu）
  python3 tools/jidou_tanaoroshi.py --tooroku  未登録を、下見の結果から台帳へ仮登録する（人が見直す前提）
  python3 tools/jidou_tanaoroshi.py --self-test
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
DAICHO = os.path.join(HERE, "jidou_daicho.json")
OUT = os.path.join(REPO, "status", "jidou_tanaoroshi.json")
PUB = os.path.join(REPO, "status", "public", "jidou_tanaoroshi.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
STAMP = os.path.join(REPO, "status", ".jidou_tanaoroshi_at")
TICK_SEC = 15  # 心臓の1周（tools/heartbeat.sh）

# 下見：作っていそうなもの → 片付け役
HINTS = [
    ("$TMPDIR の一時フォルダ", r"mkdtemp|NamedTemporaryFile|TemporaryDirectory|gettempdir|tmpdir\(\)|\$TMPDIR",
     "youryou_jougen（使い捨て1時間・$TMPDIR上限5GB）"),
    ("/private/tmp", r"[\"'](/private)?/tmp/", "worktree_taihi＋youryou_jougen（/private/tmp 上限3GB）"),
    ("自動操作ブラウザ", r"chromium\.launch|puppeteer|launchPersistentContext|user-data-dir|userDataDir|from playwright|require\(.playwright|from .playwright",
     "youryou_jougen --tsukaisute（playwright*・puppeteer* を1時間）"),
    ("作業場・複製", r"[\"']worktree[\"'],\s*[\"']add|worktree add|git clone|[\"']clone[\"']", "worktree_taihi（回収のたび＋10分おき）"),
    ("動画・音の中間物", r"ffmpeg|yt-dlp|yt_dlp|whisper", "chukan_shimau（中間物2時間）"),
    ("AI作業・制作フォルダ", r"Documents/AI作業|[\"']AI作業[\"']|howitholds", "claude_nouhin（完成品→HDD/ドライブ）＋chukan_shimau"),
    ("キャッシュ", r"Library/Caches|\.cache/", "youryou_jougen（キャッシュ上限6GB）"),
    ("iMac HDD", r"import hdd_okiba|/Volumes/", "shimau（HDDの置き場を日数で）"),
]
SELF_CLEAN = r"rmtree|rmSync|rm -rf|os\.remove|unlink|cleanup|TemporaryDirectory|finally"


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def read(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def refs(text, base):
    """スクリプトから呼んでいる別のスクリプト（1段）。"""
    out = []
    for m in re.findall(r"([\w./$\"{}~\-]+\.(?:py|mjs|js|sh|ts))", text):
        m = m.strip("\"'").replace("$REPO", REPO).replace("${REPO}", REPO).replace("~", HOME)
        for c in (m, os.path.join(base, m), os.path.join(base, os.path.basename(m))):
            if os.path.isfile(c):
                out.append(os.path.abspath(c))
                break
    return sorted(set(out))[:30]


def code_only(t):
    """コメント・説明文を外す（説明に出てくる言葉で誤判定しない）。"""
    t = re.sub(r'"""[\s\S]*?"""', "", t)
    t = re.sub(r"/\*[\s\S]*?\*/", "", t)
    return "\n".join(l for l in t.splitlines() if not l.strip().startswith(("#", "//")))


def shitami(path, base=None):
    base = base or os.path.dirname(path)
    files = [path]
    if not path.endswith(".py"):   # シェル・node の入口は、呼んでいる先も2段まで見る（Python は import 先まで追わない）
        lv1 = [r for r in refs(read(path), base) if r != path]
        files += lv1
        for f in lv1:
            if f.endswith((".mjs", ".js", ".ts", ".sh")):
                files += [r for r in refs(read(f), os.path.dirname(f)) if r not in files]
        files = files[:60]
    text = "\n".join(code_only(read(f)) for f in files)
    hits = [{"what": w, "kesu": k} for w, pat, k in HINTS if re.search(pat, text)]
    return {"files": [f.replace(HOME, "~") for f in files[:8]], "hints": hits,
            "self_clean": bool(re.search(SELF_CLEAN, read(path)))}


def from_heartbeat():
    items = []
    t = read(os.path.join(HERE, "heartbeat.sh"))
    for ln in t.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        m = re.search(r"tools/([\w\-]+\.(?:py|sh|mjs))", s)
        if not m:
            continue
        te = re.search(r"tick_every\s+(\d+)", s)
        go = re.search(r"status/([\w\-]+\.go)", s)
        freq = ("%d分おき" % max(1, int(te.group(1)) * TICK_SEC // 60)) if te else \
               ("%s があるとき" % go.group(1) if go else "毎周（15秒）")
        if te and go:
            freq += "＋%s" % go.group(1)
        items.append({"name": m.group(1), "kind": "心臓", "freq": freq, "path": os.path.join(HERE, m.group(1))})
    return items


def from_top_status():
    items = []
    for m in re.finditer(r"_okosu\(\"([\w\-]+\.py)\"", read(os.path.join(HERE, "top_status.py"))):
        items.append({"name": m.group(1), "kind": "心臓の相乗り", "freq": "毎周（15秒・中で間引くものあり）",
                      "path": os.path.join(HERE, m.group(1))})
    return items


def from_launchd():
    import plistlib
    items = []
    for p in sorted(glob.glob(HOME + "/Library/LaunchAgents/*.plist")):
        try:
            d = plistlib.load(open(p, "rb"))
        except Exception:
            continue
        lab = d.get("Label") or os.path.basename(p)
        if not re.search(r"tamago|joy|howit", lab):
            continue
        args = d.get("ProgramArguments") or [d.get("Program") or ""]
        if d.get("StartInterval"):
            freq = "%d分おき" % max(1, d["StartInterval"] // 60) if d["StartInterval"] >= 60 else "%d秒おき" % d["StartInterval"]
        elif d.get("StartCalendarInterval"):
            c = d["StartCalendarInterval"]
            c = c if isinstance(c, list) else [c]
            freq = "毎日 " + "・".join("%02d:%02d" % (x.get("Hour", 0), x.get("Minute", 0)) for x in c)
        elif d.get("KeepAlive"):
            freq = "常駐"
        else:
            freq = "起動時"
        script = next((a for a in args if re.search(r"\.(py|sh|mjs|js)$", str(a))), None)
        items.append({"name": lab, "kind": "launchd", "freq": freq, "path": script,
                      "base": d.get("WorkingDirectory")})
    return items


def from_claude_teiki():
    """Claude アプリの定期タスク（scheduled-tasks.json）。有効なものだけ拾う。
    2026-10-17 実測：rusuban-mimawari-30min が中身は停止済みなのに有効のまま30分おきにセッションを作り、
    たまごさんの画面に「見回り30分が開始されました」を出し続けていた（この棚卸しに入っていなかった）。"""
    items = []
    for f in glob.glob(HOME + "/Library/Application Support/Claude/*/*/*/scheduled-tasks.json"):
        try:
            ts = json.load(open(f, encoding="utf-8")).get("scheduledTasks", [])
        except Exception:
            continue
        for t in ts:
            if not t.get("enabled"):
                continue
            items.append({"name": "claude-teiki:" + t.get("id", "?"), "kind": "Claudeの定期タスク（画面に通知が出る）",
                          "freq": t.get("cronExpression") or ("1回 %s" % t.get("fireAt")), "path": t.get("filePath")})
    return items


def from_cron():
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith("#")]
    except Exception:
        lines = []
    return [{"name": "cron:" + l[:60], "kind": "cron", "freq": " ".join(l.split()[:5]), "path": None} for l in lines]


def from_actions():
    items = []
    for wf in sorted(glob.glob(os.path.join(REPO, ".github", "workflows", "*.yml"))):
        t = read(wf)
        cron = re.findall(r"cron:\s*['\"]([^'\"]+)", t)
        on = "定期 " + "・".join(cron) if cron else ("push のたび" if re.search(r"\bpush\b", t) else "手動・その他")
        items.append({"name": "actions:" + os.path.basename(wf), "kind": "GitHub Actions", "freq": on, "path": None,
                      "fixed": {"tsukuru": "GitHub のサーバー上だけ（Mac には作らない）", "okiba": "GitHub",
                                "kesu": "GitHub（実行ごとに捨てられる）"}})
    return items


def tanaoroshi():
    daicho = load(DAICHO, {})
    seen, rows = set(), []
    for it in from_heartbeat() + from_top_status() + from_launchd() + from_claude_teiki() + from_cron() + from_actions():
        if it["name"] in seen:
            continue
        seen.add(it["name"])
        sh = shitami(it["path"], it.get("base")) if it.get("path") and os.path.isfile(it["path"]) else None
        d = daicho.get(it["name"]) or it.get("fixed")
        row = {"name": it["name"], "kind": it["kind"], "freq": it["freq"],
               "tsukuru": (d or {}).get("tsukuru"), "okiba": (d or {}).get("okiba"), "kesu": (d or {}).get("kesu"),
               "touroku": bool(d), "shitami": sh}
        if not d:
            row["mondai"] = "台帳に無い（片付け役なし）"
        elif sh and not d.get("kesu", "").startswith(("自分が", "各係", "GitHub")):
            # 下見で拾った物の片付け役が、台帳の「消す役」に書かれていなければ「ずれ」
            need = sorted(set(h["kesu"].split("（")[0].split(" ")[0].split("＋")[0] for h in sh["hints"]))
            miss = [n for n in need if n not in d.get("kesu", "")]
            if miss:
                row["zure"] = "下見では %s が要りそう" % "・".join(miss)
        rows.append(row)
    return rows


def write(rows):
    mitouroku = [r["name"] for r in rows if not r["touroku"]]
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    res = {"at": time.strftime("%F %T"), "total": len(rows), "kinds": kinds, "mitouroku": mitouroku,
           "kari": sum(1 for r in rows if (load(DAICHO, {}).get(r["name"]) or {}).get("kari")),
           "zure": [{"name": r["name"], "zure": r["zure"]} for r in rows if r.get("zure")], "rows": rows}
    for p, o in ((OUT, res), (PUB, {k: v for k, v in res.items() if k != "rows"} |
                              {"rows": [{k: r[k] for k in ("name", "kind", "freq", "tsukuru", "okiba", "kesu")}
                                        for r in rows]})):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(o, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(p + ".tmp", p)
    return res


def tooroku(rows):
    """未登録を下見から仮登録（作るもの＝下見で拾ったもの／無ければ status の記録だけ）。"""
    daicho = load(DAICHO, {})
    n = 0
    for r in rows:
        if r["touroku"] or r["kind"] == "GitHub Actions":
            continue
        hints = (r.get("shitami") or {}).get("hints") or []
        if hints:
            daicho[r["name"]] = {"tsukuru": "・".join(h["what"] for h in hints),
                                 "okiba": "・".join(h["what"] for h in hints),
                                 "kesu": "・".join(sorted(set(h["kesu"] for h in hints))), "kari": True}
        else:
            daicho[r["name"]] = {"tsukuru": "記録だけ（status/ のファイル）", "okiba": "tamago-shinchoku/status",
                                 "kesu": "youryou_jougen（status/*.log 上限50MB）＋gomi_assyuku（控え箱）", "kari": True}
        n += 1
    json.dump(dict(sorted(daicho.items())), open(DAICHO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return n


def self_test():
    import tempfile
    d = tempfile.mkdtemp()
    a = os.path.join(d, "a.sh"); b = os.path.join(d, "b.mjs")
    open(a, "w").write("node %s\n" % b)
    open(b, "w").write("const o = mkdtempSync(join(tmpdir(), 'x-')); await chromium.launch()\n")
    s = shitami(a)
    w = {h["what"] for h in s["hints"]}
    assert "$TMPDIR の一時フォルダ" in w and "自動操作ブラウザ" in w, w
    assert not s["self_clean"]
    open(b, "w").write("console.log(1)\n")
    assert shitami(a)["hints"] == []
    rows = tanaoroshi()
    assert any(r["kind"] == "心臓" for r in rows), "心臓の行が拾えていない"
    print("self-test OK（%d件）" % len(rows))


def main():
    if "--self-test" in sys.argv:
        return self_test()
    rows = tanaoroshi()
    if "--tooroku" in sys.argv:
        print("仮登録 %d件" % tooroku(rows))
        rows = tanaoroshi()
    if "--check" in sys.argv:
        mi = [r["name"] for r in rows if not r["touroku"]]
        if mi:
            print("JIDOU_TANAOROSHI: FAIL 台帳に無い自動処理 %d件：%s\n"
                  "→ tools/jidou_daicho.json に「作るもの・置き場・消す役」を書いてから出す。" % (len(mi), "、".join(mi[:10])))
            sys.exit(2)
        print("JIDOU_TANAOROSHI: PASS（%d件すべて台帳あり）" % len(rows))
        return
    if "--hourly" in sys.argv:
        try:
            if time.time() - os.path.getmtime(STAMP) < 3600:
                return
        except Exception:
            pass
        open(STAMP, "w").close()
    res = write(rows)
    if res["mitouroku"] and "--hourly" in sys.argv:
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "n": "jidou-tanaoroshi",
                                "type": "jidou_mitouroku", "title": "片付け役のいない自動処理が%d件" % len(res["mitouroku"]),
                                "message": "、".join(res["mitouroku"][:10]) + "（tools/jidou_daicho.json に登録する）"},
                               ensure_ascii=False) + "\n")
    print("棚卸し %d件・未登録 %d件" % (res["total"], len(res["mitouroku"])))


if __name__ == "__main__":
    main()
