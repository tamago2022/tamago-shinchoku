#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1192番【曲名にローマ字（海外向け表記）を付ける】ごきげん補給所・日本語以外の表示（2026-10-10 たまごさん指示）

たまごさんの言葉：「カタカナ・漢字の曲名にもローマ字を付けて。外国の人が見ると象形文字で、
どこが曲名でどこがアーティスト名か分からない。大事なのは、本人が海外に向けて出している表記、
海外の人が探すときの表記に合わせること」

表記の優先順位（出どころは scripts/i18n/title_romaji.json の src に残す）：
  ① 公式（official）… Apple Music / iTunes の米国ストアの曲名（レーベルが海外向けに登録した表記）。
       日本ストアで同じ trackId の曲名が、こちらの曲名と一致したものだけ使う（名前の一致だけで別の曲を拾わない）。
  ② 検索（search）  … MusicBrainz の作品(work)の別名（英語名・検索ヒント）。
  ③ 自動（auto）    … Claude Haiku でヘボン式ローマ字（長音記号なし・英語由来のカタカナは英単語）。

画面の表示：「元の表記 海外向け表記」。公式が英訳でローマ字と違うときは「元の表記 公式 (ローマ字)」。
  例：異邦人 Ihojin ／ 神っぽいな God-ish (Kamippoina)
置き場：joy-relief-station の src/i18n/overlay/tr.<言語>.json（曲名の原文ハッシュ → 表示）。4言語とも同じ表記。

  python3 tools/1192_title_romaji.py official   # ①②を集める（工場=Mac・回線が要る・課金0・再開可）
  python3 tools/1192_title_romaji.py romaji     # ③ Haiku（工場=Mac・再開可）
  python3 tools/1192_title_romaji.py build [--push]  # 合わせて辞書へ。--push で GitHub API に1コミット
  python3 tools/1192_title_romaji.py --self-test
入力：status/1192_romaji/songs.json（[{a,an,id,raw,tidy}]・曲データ coverGuide.ts から抜いたもの）
"""
from __future__ import annotations
import io, json, os, re, subprocess, sys, tarfile, tempfile, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.dirname(HERE)
D = os.path.join(SH, "status", "1192_romaji")
SONGS = os.path.join(D, "songs.json")
OFF = os.path.join(D, "official.jsonl")
MBF = os.path.join(D, "mb.jsonl")
ROM = os.path.join(D, "romaji.jsonl")
JOY = os.path.expanduser("~/Desktop/joy-relief-station")
LANGS = ("en", "es", "zh-Hans", "ko")
JA = re.compile(r"[぀-ヿ㐀-鿿豈-﫿々〆]")
LATIN = re.compile(r"[A-Za-z]")
UA = "tamago-romaji/1.0 ( https://github.com/tamago2022/tamago-shinchoku )"


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s・\-_.'’&,()（）「」『』\[\]【】!?！？~〜～:：/／\"“”]", "", s)


def jsonl(p):
    out = []
    if os.path.exists(p):
        for l in io.open(p, encoding="utf-8"):
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def songs():
    return json.load(io.open(SONGS, encoding="utf-8"))


def ja_titles():
    ts = set()
    for s in songs():
        for k in ("raw", "tidy"):
            t = (s.get(k) or "").strip()
            if JA.search(t):
                ts.add(t)
    return ts


def get(url, tries=4):
    for k in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(r, timeout=40).read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                time.sleep(60 * (k + 1))
                continue
            return None
        except Exception:
            time.sleep(5)
    return None


# ---------------- ① 公式：Apple Music（JPとUSで同じ trackId） ----------------
def official():
    done = {x.get("k") or x["a"] for x in jsonl(OFF)}
    by = {}
    for s in songs():
        if JA.search(s.get("raw") or "") or JA.search(s.get("tidy") or ""):
            by.setdefault((s["a"], s["an"]), []).append(s)
    todo = [k for k in by if k[0] not in done and "%s|%s" % k not in done]
    print("公式：残り %d 人" % len(todo), flush=True)
    for (aid, an) in todo:
        term = re.sub(r"\s*[（(].*?[)）]\s*", " ", an).strip() or an
        q = urllib.parse.urlencode({"term": term, "country": "JP", "entity": "song", "attribute": "artistTerm", "limit": 200})
        jp = get("https://itunes.apple.com/search?" + q) or {}
        time.sleep(2)
        want = {}
        for s in by[(aid, an)]:
            for k in ("raw", "tidy"):
                if JA.search(s.get(k) or ""):
                    want.setdefault(norm(s[k]), set()).add(s[k])
        hit = {}
        nt = norm(term)
        for r in jp.get("results", []):
            if not nt or (nt not in norm(r.get("artistName")) and norm(r.get("artistName")) not in nt):
                continue
            n = norm(r.get("trackName"))
            if n in want:
                hit.setdefault(n, []).append(r["trackId"])
        found = {}
        ids = sorted({i for v in hit.values() for i in v})
        us = {}
        for c in range(0, len(ids), 150):
            u = get("https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
                {"id": ",".join(map(str, ids[c:c + 150])), "country": "US"})) or {}
            time.sleep(2)
            for r in u.get("results", []):
                if r.get("trackId"):
                    us[r["trackId"]] = r.get("trackName") or ""
        for n, tids in hit.items():
            names = [(us[t], t) for t in tids if us.get(t) and not JA.search(us[t]) and LATIN.search(us[t])]
            if not names:
                continue
            cnt = {}
            for nm, t in names:
                cnt.setdefault(nm, []).append(t)
            best = sorted(cnt.items(), key=lambda x: (-len(x[1]), len(x[0])))[0]
            for t in want[n]:
                found[t] = {"o": best[0], "ref": "https://music.apple.com/us/song/%d" % best[1][0]}
        io.open(OFF, "a", encoding="utf-8").write(json.dumps({"a": aid, "k": "%s|%s" % (aid, an), "n": len(jp.get("results", [])), "found": found}, ensure_ascii=False) + "\n")
        if found:
            print(an, len(found), flush=True)
    mb()


# ---------------- ② 検索：MusicBrainz の作品の別名 ----------------
def mb():
    offd = {t for x in jsonl(OFF) for t in x.get("found", {})}
    done = {x["t"] for x in jsonl(MBF)}
    by = {}
    for s in songs():
        t = (s.get("tidy") or "").strip()
        if JA.search(t) and t not in offd and t not in done and len(t) <= 40:
            by.setdefault(t, s)
    print("MusicBrainz：残り %d 曲" % len(by), flush=True)
    for t, s in by.items():
        q = 'work:"%s"' % t.replace('"', "")
        res = get("https://musicbrainz.org/ws/2/work?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": 5})) or {}
        time.sleep(1.1)
        pick = None
        for w in res.get("works", []):
            if norm(w.get("title")) != norm(t) or w.get("score", 0) < 95:
                continue
            al = w.get("aliases") or []
            en = [a["name"] for a in al if a.get("locale") == "en" and a.get("primary") and LATIN.search(a["name"]) and not JA.search(a["name"])]
            if not en:
                en = [a["name"] for a in al if a.get("locale") == "en" and LATIN.search(a["name"]) and not JA.search(a["name"])]
            if en:
                pick = {"o": en[0], "ref": "https://musicbrainz.org/work/%s" % w["id"]}
                break
        io.open(MBF, "a", encoding="utf-8").write(json.dumps({"t": t, "found": pick}, ensure_ascii=False) + "\n")


# ---------------- ③ 自動：Haiku でローマ字 ----------------
PROMPT = """You romanize Japanese (and Chinese) SONG TITLES for overseas listeners, so they can search them on YouTube / Spotify.
For each input line give the title as people outside Japan would write it in Latin letters.
Rules:
- Japanese: Hepburn romaji WITHOUT macrons (異邦人 -> Ihojin, 東京 -> Tokyo, 神っぽいな -> Kamippoina, 夜に駆ける -> Yoru ni Kakeru).
  Particles: は->wa, へ->e, を->o. Capitalize each word except particles (no, ni, wa, ga, o, e, to, de, mo, ka, yo, ne, na) — but the FIRST word always starts with a capital letter.
- Katakana words that come from English: write the English word (スリル -> Thrill, ラストシーン -> Last Scene, ラブ・ストーリー -> Love Story). Other katakana: romaji.
- Chinese-language titles (Chinese singers): Hanyu Pinyin without tone marks, words capitalized (月亮代表我的心 -> Yue Liang Dai Biao Wo De Xin).
- Keep Latin letters, numbers and symbols that are already in the title as they are, in the same place. Keep the structure (brackets, " - ", "/", feat.).
  Japanese brackets 「」『』 become ' ' (single quotes); 【】 become [ ]; （） become ( ); ～ becomes ~.
- Do NOT translate meaning (no English translation of Japanese words), only romanize. Output must contain no Japanese/Chinese characters.
Input: JSON Lines {"i": n, "t": "<title>"}. Output: ONLY JSON Lines {"i": n, "r": "<romanized>"} one per input line."""


def claude_bin():
    for c in (os.path.expanduser("~/.local/bin/claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def ask(batch, model="claude-haiku-4-5"):
    items = [{"i": n, "t": t} for n, t in enumerate(batch)]
    p = PROMPT + "\n\n" + "\n".join(json.dumps(x, ensure_ascii=False) for x in items)
    try:
        r = subprocess.run([claude_bin(), "-p", "--model", model, "--output-format", "text"], input=p,
                           capture_output=True, text=True, timeout=600)
    except Exception:
        return {}
    out = {}
    for l in (r.stdout or "").splitlines():
        l = l.strip().strip(",")
        if not l.startswith("{"):
            continue
        try:
            o = json.loads(l)
        except Exception:
            continue
        i, rr = o.get("i"), o.get("r")
        if isinstance(rr, str):
            # 中黒・長音・半角かぎ括弧はアルファベットの記号へ（「M・A・D」→「M·A·D」）
            rr = rr.replace("・", "·").replace("･", "·").replace("ー", "-").replace("｢", "'").replace("｣", "'").replace("〜", "~")
        if isinstance(i, int) and 0 <= i < len(batch) and isinstance(rr, str) and good_romaji(rr):
            out[batch[i]] = rr.strip()
    return out


def good_romaji(r):
    r = (r or "").strip()
    return bool(r) and not JA.search(r) and bool(LATIN.search(r))


def romaji():
    done = {x["t"] for x in jsonl(ROM)}
    todo = sorted(t for t in ja_titles() if t not in done)
    sh = os.environ.get("ROMAJI_SHARD")  # 例 "0/3"：3本に分けて並べて走らせる
    if sh:
        k, n = map(int, sh.split("/"))
        import zlib
        todo = [t for t in todo if zlib.crc32(t.encode("utf-8")) % n == k]
    print("ローマ字：残り %d" % len(todo), flush=True)
    B = int(os.environ.get("ROMAJI_BATCH", "40"))
    batches = [todo[i:i + B] for i in range(0, len(todo), B)]

    def run(b):
        got = ask(b)
        miss = [t for t in b if t not in got]
        if miss:
            got.update(ask(miss))
        with io.open(ROM, "a", encoding="utf-8") as f:
            for t, r in got.items():
                f.write(json.dumps({"t": t, "r": cap(r)}, ensure_ascii=False) + "\n")
        return len(got)

    n = 0
    with ThreadPoolExecutor(int(os.environ.get("ROMAJI_WORKERS", "8"))) as ex:
        for k in ex.map(run, batches):
            n += k
            print("…%d" % n, flush=True)


def cap(r):
    r = r.strip()
    for i, ch in enumerate(r):
        if ch.isalpha():
            return r[:i] + ch.upper() + r[i + 1:]
    return r


# ---------------- 合わせる ----------------
def similar(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    a2, b2 = a.replace("ou", "o").replace("uu", "u"), b.replace("ou", "o").replace("uu", "u")
    return a2 == b2


# 手書きの表で上書きしてよい「曲名」（画面の言葉と同じ字のもの＝駅・再生・猫・もう一度などは入れない）
WHOLE_OVERRIDE = set("""襟裳岬 蛍の光 月光の夜 秋の気配 雨の街を 誰のため 故乡的云 少年時代 遠い恋人 ふるさと 花咲く旅路 真夏の果実
リオの少女 夏の終わり 茜色の夕日 家族の風景 青い珊瑚礁 影になって 旅人のうた 若者のすべて ルイジアンナ 大きな古時計 時間よ止まれ
カチューシャ ルージュの伝言 いとしのエリー 赤黄色の金木犀 セカンド・ラブ さよなら夏の日 恋人も濡れる街角 上を向いて歩こう
クシコス・ポスト シングル・アゲイン テレフォン・ナンバー プラスティック・ラブ 祭りの花を買いに行く ベルベット・イースター
やさしさに包まれたなら フライディ・チャイナタウン""".split())


def has_reading(t, v):
    """関所 scripts/patrol/check-i18n-title-romaji.mjs の hasReading と同じ。"""
    if not isinstance(v, str) or not v.startswith(t + " "):
        return False
    rest = v[len(t) + 1:]
    return bool(LATIN.search(rest)) and not JA.search(rest)


def display(t, rec):
    o, r = rec.get("o"), rec.get("r")
    if o and r and not similar(o, r):
        return "%s %s (%s)" % (t, o, r)
    return "%s %s" % (t, o or r)


def table():
    """{原題: {o, r, src, ref}}"""
    rom = {}
    for x in jsonl(ROM):
        rom[x["t"]] = x["r"]
    # 同じ題名を複数の人が持つとき（カバー）は、原曲の人（曲データで originalRef の無い方）の公式表記を採る。
    #   例：異邦人 … 久保田早紀の米国ストア表記「Ihojin」を、Ms.OOJA のカバー盤の「Ihoujin」より優先。
    orig = {}
    for s_ in songs():
        if not s_.get("cv"):
            for k in ("raw", "tidy"):
                orig.setdefault((s_.get(k) or "").strip(), set()).add(s_["a"])
    cand = {}
    for x in jsonl(OFF):
        for t, v in (x.get("found") or {}).items():
            cand.setdefault(t, []).append((x["a"], v))
    off = {}
    for t, cs in cand.items():
        own = [v for a, v in cs if a in orig.get(t, ())]
        pool = own or [v for _a, v in cs]
        cnt = {}
        for v in pool:
            cnt[v["o"]] = cnt.get(v["o"], 0) + 1
        best = sorted(pool, key=lambda v: -cnt[v["o"]])[0]
        off[t] = best
    mbd = {x["t"]: x["found"] for x in jsonl(MBF) if x.get("found")}
    out = {}
    for t in sorted(ja_titles()):
        rec = {}
        if t in off:
            rec = {"o": off[t]["o"], "src": "official", "ref": off[t]["ref"]}
        elif t in mbd:
            rec = {"o": mbd[t]["o"], "src": "search", "ref": mbd[t]["ref"]}
        if t in rom:
            rec["r"] = rom[t]
            rec.setdefault("src", "auto")
        if rec.get("o") or rec.get("r"):
            # 公式の表記が元の題をそのままアルファベットにしただけでも、ローマ字と同じなら1つにまとめる
            out[t] = rec
    return out


def build(push=False):
    import importlib
    sys.path.insert(0, HERE)
    hj = importlib.import_module("1191_honyaku_jidou")
    subprocess.run(["git", "fetch", "origin", "main", "-q"], cwd=JOY, timeout=300)
    sha = subprocess.run(["git", "rev-parse", "origin/main"], cwd=JOY, capture_output=True, text=True).stdout.strip()
    tmp = tempfile.mkdtemp(prefix="1192_")
    tg = os.path.join(tmp, "a.tar")
    subprocess.run(["git", "archive", "-o", tg, "origin/main", "src/i18n/overlay", "scripts/i18n"], cwd=JOY, check=True, timeout=300)
    tarfile.open(tg).extractall(tmp)
    tab = table()
    full = os.path.join(D, "full")
    subprocess.run(["rm", "-rf", full])
    st = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "base": sha[:12], "titles": len(ja_titles()), "covered": len(tab),
          "src": {}}
    for rec in tab.values():
        st["src"][rec["src"]] = st["src"].get(rec["src"], 0) + 1
    for lg in LANGS:
        p = os.path.join(tmp, "src", "i18n", "overlay", "tr.%s.json" % lg)
        d = json.load(io.open(p, encoding="utf-8"))
        for t, rec in tab.items():
            d[hj.jahash(t)] = display(t, rec)
        # まだ表記が無い曲名に、意味だけの訳（「Godlike, Huh」「异邦人」など）が残っていたら消す（関所が止めるため）
        for t in ja_titles():
            h = hj.jahash(t)
            if t not in tab and h in d and not has_reading(t, d[h]):
                del d[h]
                st["keshita"] = st.get("keshita", 0) + 1
        q = os.path.join(full, "src", "i18n", "overlay", "tr.%s.json" % lg)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        io.open(q, "w", encoding="utf-8").write(json.dumps(dict(sorted(d.items())), ensure_ascii=False, separators=(",", ":")))
    # 手書きの表（<言語>.json＝lc()の表／extra.<言語>.json）は辞書(tr)より先に効く。そこに曲名が入っていると
    # 「いとしのエリー → Itoshi no Ellie」のように元の表記が消える（2026-10-10 弾き語り特集で実測）。
    # 表には「再生→Play」「猫→Cat」のような画面の言葉も同じ字で入っているので、曲名だと確かめたものだけ上書きする。
    st["te_uwagaki"] = 0
    for lg in LANGS:
        for f in ("%s.json" % lg, "extra.%s.json" % lg):
            p = os.path.join(tmp, "src", "i18n", "overlay", f)
            if not os.path.exists(p):
                continue
            d = json.load(io.open(p, encoding="utf-8"))
            ch = [0]

            def walk(o):
                for k, v in list(o.items()):
                    if isinstance(v, dict):
                        walk(v)
                    elif isinstance(v, str) and k in WHOLE_OVERRIDE and k in tab and not has_reading(k, v):
                        o[k] = display(k, tab[k])
                        ch[0] += 1
            walk(d)
            if ch[0]:
                q = os.path.join(full, "src", "i18n", "overlay", f)
                raw = io.open(p, encoding="utf-8").read()
                ind = 1 if raw[2:3] == " " and raw[3:4] != " " else (2 if raw[2:4] == "  " else 0)
                os.makedirs(os.path.dirname(q), exist_ok=True)
                io.open(q, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=ind) + ("\n" if raw.endswith("\n") else ""))
                st["te_uwagaki"] += ch[0]
    q = os.path.join(full, "scripts", "i18n", "title_romaji.json")
    os.makedirs(os.path.dirname(q), exist_ok=True)
    io.open(q, "w", encoding="utf-8").write(json.dumps(
        {"_about": "曲名の海外向け表記（1192番）。src: official=Apple Music米国ストアの公式表記 / search=MusicBrainzの作品別名 / auto=Haikuのヘボン式ローマ字。"
                   "画面には tr.<言語>.json の「元の表記 海外向け表記」で出る。",
         "titles": tab}, ensure_ascii=False, indent=0, sort_keys=True))
    # 曲名の元の表記（かなを含むもの）は「残ってよい日本語」（かなの関所 check-i18n-kana.mjs と画面の検品 1190 が読む）
    ap = os.path.join(tmp, "scripts", "i18n", "allow_originals.json")
    allow = set(json.load(io.open(ap, encoding="utf-8"))) if os.path.exists(ap) else set()
    allow |= {t for t in tab if re.search(r"[ぁ-ゟァ-ヺヽ-ヿ]", t)}
    q = os.path.join(full, "scripts", "i18n", "allow_originals.json")
    io.open(q, "w", encoding="utf-8").write(json.dumps(sorted(allow), ensure_ascii=False, indent=0))
    io.open(os.path.join(SH, "status", "1191_nihongo_nokori", "allow_originals.json"), "w", encoding="utf-8").write(
        json.dumps(sorted(allow), ensure_ascii=False, indent=0))
    import hashlib
    st["tabHash"] = hashlib.sha1(json.dumps([tab, sorted(WHOLE_OVERRIDE), st.get("te_uwagaki")], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    prev = {}
    try:
        prev = json.load(io.open(os.path.join(D, "build.json"), encoding="utf-8"))
    except Exception:
        pass
    if push and prev.get("tabHash") == st["tabHash"] and (prev.get("push") or {}).get("ok"):
        push = False
        st["push"] = prev.get("push")
        st["skip"] = "前回から変わっていない"
    # 足りない分の報告
    st["missing"] = sorted(t for t in ja_titles() if t not in tab)[:50]
    st["missingN"] = len(ja_titles()) - len(tab)
    if push:
        df = importlib.import_module("_952_data_fetch")
        r = df._op_apipush({"dir": "status/1192_romaji/full", "base_sha": sha,
                            "message": "1192番: 日本語の曲名に海外向け表記（公式→検索→ローマ字）を付けた（%d曲）" % len(tab)})
        st["push"] = {k: r.get(k) for k in ("ok", "commit", "error", "moved", "alreadyIn")}
    io.open(os.path.join(D, "build.json"), "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False)[:3000])


def hourly():
    """心臓から1時間に1回：新しい曲を拾う→ローマ字→（公式集めが止まっていれば再開）→辞書へ1コミット。"""
    lock = os.path.join(D, "hourly.lock")
    last = os.path.join(D, "hourly.last")
    # 心臓の tick は数分おきに来るので、ここで1時間に1回へ間引く（--force で今すぐ）
    if "--force" not in sys.argv and os.path.exists(last) and time.time() - os.path.getmtime(last) < 3300:
        return
    io.open(last, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
        print("走行中（lock）"); return
    io.open(lock, "w").write(str(os.getpid()))
    try:
        subprocess.run(["git", "fetch", "origin", "main", "-q"], cwd=JOY, timeout=300)
        tmp = tempfile.mkdtemp(prefix="1192h_")
        tg = os.path.join(tmp, "a.tar")
        subprocess.run(["git", "archive", "-o", tg, "origin/main", "src/lib/coverGuide.ts", "src/lib/songTitleTidy.ts",
                        "src/lib/hikigatariSongs.ts"], cwd=JOY, check=True, timeout=300)
        tarfile.open(tg).extractall(tmp)
        node = "/usr/local/bin/node" if os.path.exists("/usr/local/bin/node") else "node"
        r = subprocess.run([node, "--experimental-strip-types", os.path.join(HERE, "1192_extract.mjs"), tmp, SONGS + ".new"],
                           capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.exists(SONGS + ".new"):
            os.replace(SONGS + ".new", SONGS)
        else:
            print("抜き出し失敗", (r.stderr or "")[-300:])
        ps = subprocess.run(["/bin/ps", "-axo", "command"], capture_output=True, text=True).stdout
        if "1192_title_romaji.py official" not in ps:
            subprocess.Popen([sys.executable, os.path.join(HERE, "1192_title_romaji.py"), "official"],
                             stdout=open(os.path.join(D, "official.log"), "a"), stderr=subprocess.STDOUT,
                             cwd=SH, start_new_session=True)
        if "1192_title_romaji.py romaji" not in ps:
            romaji()
        build(push=True)
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass


def self_test():
    assert display("異邦人", {"o": "Ihojin", "r": "Ihojin"}) == "異邦人 Ihojin"
    assert display("異邦人", {"o": "Ihoujin", "r": "Ihojin"}) == "異邦人 Ihoujin"
    assert display("神っぽいな", {"o": "God-ish", "r": "Kamippoina"}) == "神っぽいな God-ish (Kamippoina)"
    assert display("雨音", {"r": "Amaoto"}) == "雨音 Amaoto"
    assert good_romaji("Kamippoina") and not good_romaji("神っぽいな") and not good_romaji("")
    assert cap("'suriru'") == "'Suriru'"
    assert has_reading("異邦人", "異邦人 Ihojin") and not has_reading("異邦人", "異邦人 이방인") and not has_reading("神っぽいな", "Godlike, Huh")
    print("✓ self-test 合格")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        self_test()
    elif a and a[0] == "official":
        official()
    elif a and a[0] == "mb":
        mb()
    elif a and a[0] == "romaji":
        romaji()
    elif a and a[0] == "hourly":
        hourly()
    elif a and a[0] == "build":
        build(push="--push" in a)
    else:
        print(__doc__)
