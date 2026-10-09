#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1191番【入荷したら自動で訳す】ごきげん補給所の「訳が無い日本語の文」を見つけて、安いモデルでまとめて訳し、辞書に入れる。

たまごさんのルール（2026-10-10）：
  1. 文章（カードのひとこと・曲の説明・アーティスト紹介・棚名・特集本文）は、その言語に全部訳す。日本語が残るのは不合格。
  2. 人名・アーティスト名・日本語の曲名は、元の表記を残して、その言語の読みを並べる（布袋寅泰 Tomoyasu Hotei）。
  3. 表示のたびに訳さない（重くなる）。入荷のときに訳して辞書（src/i18n/overlay/tr.<言語>.json）に置く。

流れ（工場=Macで、心臓から1時間に1回）：
  ① joy-relief-station の origin/main を読む（作業ツリーには触らない：git archive だけ）
  ② コード（src/）と DB（棚に出ている在庫・棚名）から、画面に出る日本語の文を集める
  ③ tr.<言語>.json に訳が無いものだけを、Claude Haiku（claude -p --model claude-haiku-4-5）で4言語へ訳す
  ④ かなが「人名・曲名の元の表記」以外に残った訳は捨てる（もう1回だけ Sonnet でやり直す）
  ⑤ 辞書を GitHub API で main に1コミット（巻き戻し防止つき）。公開ボタンは kohyou_osu.py が押す
  結果: status/1191_nihongo_nokori/jidou.json（未訳の件数・今回訳した件数・捨てた件数）

  python3 tools/1191_honyaku_jidou.py            # 本番
  python3 tools/1191_honyaku_jidou.py --dry-run  # 数えるだけ（訳さない・pushしない）
  python3 tools/1191_honyaku_jidou.py --self-test
"""
from __future__ import annotations
import io, json, os, re, subprocess, sys, tarfile, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.dirname(HERE)
OUTD = os.path.join(SH, "status", "1191_nihongo_nokori")
STATE = os.path.join(OUTD, "jidou.json")
LOCK = os.path.join(OUTD, "jidou.lock")
JOY = os.path.expanduser("~/Desktop/joy-relief-station")
LANGS = {"en": "en", "es": "es", "zh-Hans": "zh", "ko": "ko"}
MAX_UNITS = int(os.environ.get("HONYAKU_MAX", "400"))
BATCH = 25
JA = re.compile(r"[ぁ-ゟァ-ヺヽ-ヿ㐀-鿿]")
KANA = re.compile(r"[ぁ-ゟァ-ヺヽ-ヿ]")
RUN = re.compile(r"[ぁ-ゟァ-ヿ㐀-鿿々〆]+")
READ = re.compile(r"[A-Za-zÀ-ɏ가-힣一-鿿]")
READ_START = re.compile(r"[A-ZÀ-Þ가-힣一-鿿¡¿0-9]")
CLOSE = set("」』”》’\"）)]】")


# ---------- 共通（サイト側 src/i18n/hashDict.ts・scripts/patrol/check-i18n-kana.mjs と同じ計算） ----------
def jahash(s):
    u = s.encode("utf-16-le")
    h1, h2 = 0x811C9DC5, 5381
    for k in range(0, len(u), 2):
        c = u[k] | (u[k + 1] << 8)
        h1 ^= c
        h1 = (h1 * 0x01000193) & 0xFFFFFFFF
        h2 = ((h2 * 33) ^ c) & 0xFFFFFFFF

    def b36(n):
        s = ""
        while True:
            n, r = divmod(n, 36)
            s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
            if n == 0:
                return s
    return b36(h1) + "." + b36(h2)


def pair_ok(t, r):
    if len(r) > 30:
        return False
    i = 0
    while True:
        j = t.find(r, i)
        if j < 0:
            return False
        k = j + len(r)
        while k < len(t) and t[k] in CLOSE:
            k += 1
        if k < len(t) and t[k] in " （(":
            saw = t[k] != " "
            k2 = k + 1
            while k2 < len(t) and t[k2] in " （(“\"":
                saw = saw or t[k2] in "（("
                k2 += 1
            if k2 < len(t) and ((READ if saw else READ_START).match(t[k2])):
                return True
        b = j - 1
        if b >= 1 and t[b] == " " and READ.match(t[b - 1]):
            w = b - 1
            while w > 0 and READ.match(t[w - 1]):
                w -= 1
            if READ_START.match(t[w]):
                return True
        i = j + 1


def kana_left(t, idx):
    for r in RUN.findall(t):
        if not KANA.search(r):
            continue
        if any(a in t for a in idx.get(r, ())):
            continue
        if pair_ok(t, r):
            continue
        return r
    return None


def allow_index(allow):
    idx = {}
    for a in allow:
        for r in RUN.findall(a):
            idx.setdefault(r, []).append(a)
    return idx


# ---------- ② 画面に出る日本語を集める ----------
LIT = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')
EXCL_FILES = ("yomiDictionary", "searchNormalize", "videoHealthReport", "/admin", "Admin", "admin_",
              "prefectureTags", ".server.ts", ".functions.ts", "artistAliases", ".test.", ".spec.",
              "/i18n/", "Debug", "debug", "coverGuideLite")
SKIP_KEYS = {"aliases", "id", "slug", "yomi", "src", "kana", "search", "reading", "href", "url", "keywords",
             "alias", "searchTerms", "sources", "source", "key", "queryKey", "className", "path", "route", "to",
             "tags", "tag", "ref", "refs", "yomigana", "furigana", "match", "pattern", "regex", "sortKey",
             "searchQuery", "moreOnYoutubeQuery", "songId", "artistId", "originalSongId", "tieInSearchQuery"}
NAME_KEYS = {"name", "artist", "artistName", "byline", "singer", "performer", "composer", "lyricist",
             "originalArtist", "by", "who", "person", "author", "coverArtist"}
TITLE_KEYS = {"title", "songTitle", "originalTitle", "song", "track", "album"}
CODEY = re.compile(r"function |=>|\bconst |;\n|return |\bexport |\bimport |\}\)|className=|/g,")


def collect_units(root, db):
    units = {}

    def add(t, cat):
        t = t.strip()
        if not t or not JA.search(t) or t.startswith(("http", "/", "@/", "./", "#")) or "${" in t or CODEY.search(t):
            return
        pri = {"name": 0, "title": 1, "text": 2}
        if t not in units or pri[cat] < pri[units[t]]:
            units[t] = cat

    for base, _d, fs in os.walk(os.path.join(root, "src")):
        for f in fs:
            if not f.endswith((".ts", ".tsx")):
                continue
            p = os.path.join(base, f)
            rel = os.path.relpath(p, root)
            if any(e in rel for e in EXCL_FILES):
                continue
            s = io.open(p, encoding="utf-8").read()
            s2 = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), s, flags=re.S)
            s2 = re.sub(r'(^|[^:\\"\'])//[^\n]*', lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), s2, flags=re.M)
            for m in LIT.finditer(s2):
                raw = m.group(1) if m.group(1) is not None else (m.group(2) if m.group(2) is not None else m.group(3))
                if not raw or not JA.search(raw):
                    continue
                t = raw
                if m.group(3) is None:
                    try:
                        t = json.loads('"' + raw.replace("\\'", "'") + '"')
                    except Exception:
                        pass
                ls = s2.rfind("\n", 0, m.start()) + 1
                before = s2[max(ls, m.start() - 400):m.start()]
                km = list(re.finditer(r"([A-Za-z_]\w*)\s*:\s*", before))
                key = None
                if km:
                    k = km[-1]
                    tail = before[k.end():]
                    if tail.strip() == "" or (tail.lstrip().startswith("[") and "]" not in tail):
                        key = k.group(1)
                if key in SKIP_KEYS:
                    continue
                add(t, "name" if key in NAME_KEYS else "title" if key in TITLE_KEYS else "text")
            if f.endswith(".tsx"):
                for m in re.finditer(r">([^<>{}]*[぀-ヿ㐀-鿿][^<>{}]*)<", s2):
                    add(re.sub(r"\s+", " ", m.group(1)), "text")
    for r in (db or {}).get("stock", []):
        add(r.get("title") or "", "title")
        add(r.get("whisper") or "", "text")
        add(r.get("note") or "", "text")
    for r in (db or {}).get("shelves", []):
        add(r.get("title") or "", "text")
        add(r.get("subtitle") or "", "text")
    return units


# ---------- ③ 訳す ----------
def claude_bin():
    for c in (os.path.expanduser("~/.local/bin/claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def ask(model, rules, items, glossary, strict=False):
    prompt = (rules + "\n\n## This batch\nName glossary (JSON): " + json.dumps(glossary, ensure_ascii=False) +
              ("\nIMPORTANT: a previous attempt left Japanese words. Translate common words fully; only names/titles may keep "
               "the original, immediately followed by a space and the reading." if strict else "") +
              "\n\nInput lines (JSON Lines):\n" + "\n".join(json.dumps(x, ensure_ascii=False) for x in items) +
              "\n\nReply with ONLY the output JSON Lines (one per input line), nothing else.")
    r = subprocess.run([claude_bin(), "-p", "--model", model, "--output-format", "text"], input=prompt,
                       capture_output=True, text=True, timeout=600)
    out = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip().strip(",")
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if isinstance(o.get("i"), int) and all(isinstance(o.get(k), str) and o.get(k) for k in ("en", "es", "zh", "ko")):
            out[o["i"]] = o
    return out, r.returncode, (r.stderr or "")[-300:]


# ---------- 本体 ----------
def git(args, t=300):
    r = subprocess.run(["git"] + args, cwd=JOY, capture_output=True, text=True, timeout=t)
    return r.returncode, r.stdout, r.stderr


def main(dry=False):
    os.makedirs(OUTD, exist_ok=True)
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 3 * 3600:
        print("走行中（lock）"); return 0
    io.open(LOCK, "w").write(str(os.getpid()))
    st = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "dryRun": dry}
    try:
        git(["fetch", "origin", "main"])
        rc, sha, _ = git(["rev-parse", "origin/main"])
        sha = sha.strip()
        st["base"] = sha[:12]
        tmp = tempfile.mkdtemp(prefix="1191_")
        tg = os.path.join(tmp, "a.tar")
        subprocess.run(["git", "archive", "-o", tg, "origin/main", "src", "scripts/i18n"], cwd=JOY, check=True, timeout=300)
        tarfile.open(tg).extractall(tmp)
        ov = os.path.join(tmp, "src", "i18n", "overlay")
        sys.path.insert(0, HERE)
        db = {}
        try:
            import importlib
            m = importlib.import_module("1191_db_nihongo")
            m.main()
            db = json.load(io.open(m.OUT, encoding="utf-8"))
        except Exception as e:
            st["dbErr"] = str(e)[:200]
        units = collect_units(tmp, db)
        names = {}
        for lg in LANGS:
            p = os.path.join(ov, "names.%s.json" % lg)
            if os.path.exists(p):
                names.update(json.load(io.open(p, encoding="utf-8")))
        tr = {lg: json.load(io.open(os.path.join(ov, "tr.%s.json" % lg), encoding="utf-8")) for lg in LANGS}
        hand = {}
        for lg in LANGS:
            for f in ("%s.json" % lg, "extra.%s.json" % lg):
                p = os.path.join(ov, f)
                if os.path.exists(p):
                    hand.setdefault(lg, {}).update(json.load(io.open(p, encoding="utf-8")))
        miss = [t for t, c in units.items()
                if not (c == "name" and t in names)
                and any(jahash(t) not in tr[lg] and t not in hand.get(lg, {}) for lg in LANGS)]
        st["units"] = len(units)
        st["mitaku"] = len(miss)
        print("画面に出る日本語 %d 件／訳が無い %d 件" % (len(units), len(miss)))
        if dry or not miss:
            st["ok"] = True
            return 0
        allow_p = os.path.join(tmp, "scripts", "i18n", "allow_originals.json")
        allow = set(json.load(io.open(allow_p, encoding="utf-8"))) if os.path.exists(allow_p) else set()
        allow |= set(names)
        rules = io.open(os.path.join(tmp, "scripts", "i18n", "TRANSLATE_PROMPT.md"), encoding="utf-8").read()
        todo = miss[:MAX_UNITS]
        got, dropped, calls = {}, [], 0
        name_keys = sorted([k for k in names if len(k) >= 2], key=len, reverse=True)
        for b in range(0, len(todo), BATCH):
            batch = todo[b:b + BATCH]
            items = [{"i": n, "kind": units[t] if units[t] != "name" else "name", "ja": t} for n, t in enumerate(batch)]
            gl = {k: names[k] for k in name_keys if any(k in t for t in batch)}
            res, rc, err = ask("claude-haiku-4-5", rules, items, gl)
            calls += 1
            if rc != 0 and not res:
                st["cliErr"] = err
                break
            redo = []
            for it in items:
                o = res.get(it["i"])
                kept = {k for k in (o or {}).get("keep") or [] if isinstance(k, str) and k in it["ja"]}
                idx = allow_index(allow | kept)
                if o and not any(kana_left(o[k], idx) for k in ("en", "es", "zh", "ko")):
                    got[it["ja"]] = (o, kept)
                else:
                    redo.append(it)
            if redo:
                res2, _, _ = ask("claude-sonnet-5", rules, redo, gl, strict=True)
                calls += 1
                for it in redo:
                    o = res2.get(it["i"])
                    kept = {k for k in (o or {}).get("keep") or [] if isinstance(k, str) and k in it["ja"]}
                    idx = allow_index(allow | kept)
                    if o and not any(kana_left(o[k], idx) for k in ("en", "es", "zh", "ko")):
                        got[it["ja"]] = (o, kept)
                    else:
                        dropped.append(it["ja"][:80])
        st["yakushita"] = len(got)
        st["suteta"] = len(dropped)
        st["suteta_rei"] = dropped[:10]
        st["calls"] = calls
        if not got:
            st["ok"] = not st.get("cliErr")
            return 0
        full = os.path.join(OUTD, "full")
        subprocess.run(["rm", "-rf", full])
        for lg, k in LANGS.items():
            d = tr[lg]
            for ja, (o, _k) in got.items():
                d[jahash(ja)] = o[k]
            p = os.path.join(full, "src", "i18n", "overlay", "tr.%s.json" % lg)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8").write(json.dumps(dict(sorted(d.items())), ensure_ascii=False, separators=(",", ":")))
        for ja, (o, kept) in got.items():
            allow |= kept
        p = os.path.join(full, "scripts", "i18n", "allow_originals.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(json.dumps(sorted(a for a in allow if a not in names), ensure_ascii=False, indent=0))
        import importlib
        df = importlib.import_module("_952_data_fetch")
        r = df._op_apipush({"dir": "status/1191_nihongo_nokori/full", "base_sha": sha,
                            "message": "1191番: 入荷した日本語の文を4言語へ自動で訳した（%d件）" % len(got)})
        st["push"] = {k: r.get(k) for k in ("ok", "commit", "error", "moved")}
        st["ok"] = bool(r.get("ok"))
        return 0 if r.get("ok") else 1
    except Exception as e:
        st["ok"] = False
        st["error"] = "%s: %s" % (type(e).__name__, str(e)[:300])
        return 1
    finally:
        try:
            os.remove(LOCK)
        except Exception:
            pass
        io.open(STATE, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))


def self_test():
    assert jahash("布袋寅泰") == "8iy8wu.17d56t4", jahash("布袋寅泰")
    idx = allow_index({"布袋寅泰", "竹内まりや"})
    assert kana_left("布袋寅泰 Tomoyasu Hotei's riff", idx) is None
    assert kana_left("“エイリアンズ (Aliens)” by KIRINJI", idx) is None
    assert kana_left("1987年、BOØWY。布袋寅泰がソロになる前の", idx)
    assert kana_left("The band's よく知られた song", idx)
    print("✓ self-test 合格")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        sys.exit(main(dry="--dry-run" in sys.argv))
