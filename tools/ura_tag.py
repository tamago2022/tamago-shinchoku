#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""曲の裏タグ（画面には出さない・おすすめ／パーソナライズ用）を全曲に付ける。2026-10-11 たまごさん指示。

たまごさんの言葉：
  「裏タグ（画面には出さない、おすすめ・パーソナライズ用）：ジャンル、国・地域、年代に加えて、
    気分（切ない、明るい、ノスタルジック、高揚、癒し、など）、季節、シチュエーション（ドライブ、夜、
    失恋、ダンス、雨、朝、作業用、など）を付ける。既存の全曲にも同じ形の裏タグを付ける
    （量が多いので Haiku で一括、根拠の弱いものは付けない）。タグの語彙は決まった一覧に揃え、表記ゆれを出さない。」

決まり（機械の裏付け）：
  - 語彙は status/ura_tag/vocab.json だけ。一覧に無い語は捨てる（check で数える・build で落とす）。
  - 根拠の弱いものは付けない：Haiku には「確信が持てないカテゴリは空にする」と指示し、
    さらに数の上限（ジャンル2・地域1・年代1・気分2・季節1・シーン2）を超えた分は捨てる。
  - 課金：Mac の claude CLI（サブスク枠）で Haiku を呼ぶ。API 従量は使わない。
    # kakeibo: 課金なし（claude CLI のサブスク枠・API従量なし）

  python3 tools/ura_tag.py run [--workers 6] [--batch 50]   # Mac で。途中で止まっても続きから
  python3 tools/ura_tag.py check                            # 語彙外・件数を数える
  python3 tools/ura_tag.py build                            # status/ura_tag/song_ura_tags.json を作る
  python3 tools/ura_tag.py --self-test
入力：status/ura_tag/songs_in.jsonl（{k:"artistId/songId", a, t, y, n, e}）
"""
import io
import json
import os
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
D = os.path.join(REPO, "status", "ura_tag")
VOCAB = os.path.join(D, "vocab.json")
IN = os.environ.get("URA_IN") or os.path.join(D, "songs_in.jsonl")
OUT = os.environ.get("URA_OUT") or os.path.join(D, "tags.jsonl")
FINAL = os.path.join(D, "song_ura_tags.json")
LIMITS = {"g": ("genre", 2), "r": ("region", 1), "e": ("era", 1), "m": ("mood", 2), "s": ("season", 1), "c": ("scene", 2)}


def vocab():
    return json.load(io.open(VOCAB, encoding="utf-8"))


def jsonl(p):
    out = []
    if os.path.exists(p):
        for l in io.open(p, encoding="utf-8"):
            l = l.strip()
            if l:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def prompt(v):
    keys = "\n".join("%s(%s): %s" % (c, name, ", ".join(v[name].keys())) for c, (name, _n) in LIMITS.items())
    return (
        "You tag songs for a music recommendation site. For each input line (i=index, a=artist, t=title as stored "
        "(may be a messy YouTube title), y=release year if known, n=short note, e=artist active decades), output ONE JSON "
        "line: {\"i\":<i>,\"g\":[],\"r\":[],\"e\":[],\"m\":[],\"s\":[],\"c\":[]}.\n"
        "Use ONLY these keys (copy exactly):\n" + keys + "\n"
        "Rules:\n"
        "- g genre (max 2), r artist's country/region (max 1), e decade the SONG was originally released (max 1).\n"
        "- m mood (max 2), s season (max 1), c scene/situation (max 2).\n"
        "- Only tag what you are confident about from real knowledge of this artist and song. If unsure, leave that list empty. "
        "Season and scene: tag only when the song is clearly associated (title/lyrics/well-known use), otherwise empty.\n"
        "- If the line is not a song (interview, trailer, compilation/mix, reaction, unboxing), output {\"i\":<i>,\"x\":1} plus r only if sure.\n"
        "- Output JSON lines only, no prose, no code fences.\n"
    )


def claude_bin():
    for c in (os.path.expanduser("~/.local/bin/claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def clean(o, v):
    rec = {}
    for c, (name, n) in LIMITS.items():
        xs = o.get(c) or []
        if isinstance(xs, str):
            xs = [xs]
        ok = []
        for x in xs:
            if isinstance(x, str) and x in v[name] and x not in ok:
                ok.append(x)
        if ok:
            rec[c] = ok[:n]
    if o.get("x"):
        rec["x"] = 1
    return rec


def ask(batch, v, model="claude-haiku-4-5"):
    lines = [json.dumps({"i": i, "a": s.get("a"), "t": s.get("t"), "y": s.get("y"), "n": (s.get("n") or "")[:120],
                         "e": s.get("e") or []}, ensure_ascii=False) for i, s in enumerate(batch)]
    p = prompt(v) + "\nINPUT:\n" + "\n".join(lines)
    try:
        r = subprocess.run([claude_bin(), "-p", "--model", model, "--output-format", "text"], input=p,
                           capture_output=True, text=True, timeout=900)
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
        i = o.get("i")
        if isinstance(i, int) and 0 <= i < len(batch):
            out[batch[i]["k"]] = clean(o, v)
    return out


def run(workers=6, bsize=50):
    v = vocab()
    done = {x["k"] for x in jsonl(OUT)}
    todo = [s for s in jsonl(IN) if s["k"] not in done]
    sh = os.environ.get("URA_SHARD")
    if sh:
        k, n = map(int, sh.split("/"))
        todo = [s for s in todo if zlib.crc32(s["k"].encode("utf-8")) % n == k]
    print("残り %d" % len(todo), flush=True)
    batches = [todo[i:i + bsize] for i in range(0, len(todo), bsize)]

    def one(b):
        got = ask(b, v)
        miss = [s for s in b if s["k"] not in got]
        if miss and len(miss) < len(b):
            got.update(ask(miss, v))
        with io.open(OUT, "a", encoding="utf-8") as f:
            for k, rec in got.items():
                f.write(json.dumps(dict(k=k, **rec), ensure_ascii=False) + "\n")
        return len(got)

    n = 0
    with ThreadPoolExecutor(workers) as ex:
        for k in ex.map(one, batches):
            n += k
            print("…%d" % n, flush=True)


def merged():
    v = vocab()
    keys = {s["k"] for s in jsonl(IN)}
    out = {}
    for x in jsonl(OUT):
        k = x.get("k")
        if k in keys:
            out[k] = clean(x, v)  # 後の行が勝つ（やり直し分）
    return out


def check():
    v = vocab()
    raw = jsonl(OUT)
    bad = 0
    for x in raw:
        for c, (name, n) in LIMITS.items():
            xs = x.get(c) or []
            bad += sum(1 for t in xs if t not in v[name]) + max(0, len(xs) - n)
    m = merged()
    total = len(jsonl(IN))
    tagged = sum(1 for r in m.values() if any(c in r for c in LIMITS))
    st = {"in": total, "answered": len(m), "tagged": tagged, "notSong": sum(1 for r in m.values() if r.get("x")),
          "outOfVocab_or_overLimit_rows": bad,
          "byCat": {c: sum(1 for r in m.values() if c in r) for c in LIMITS}}
    print(json.dumps(st, ensure_ascii=False))
    return st


def build():
    m = merged()
    io.open(FINAL, "w", encoding="utf-8").write(json.dumps(
        {"_about": "曲の裏タグ（画面に出さない）。キー=artistId/songId。g=ジャンル r=国・地域 e=年代 m=気分 s=季節 c=シーン x=曲ではない。"
                   "語彙は vocab.json のみ（tools/ura_tag.py）。",
         "vocab": vocab(), "tags": dict(sorted(m.items()))}, ensure_ascii=False, separators=(",", ":")))
    print("build", len(m))


def self_test():
    v = {"genre": {"j-pop": 1}, "region": {"japan": 1}, "era": {"90s": 1}, "mood": {"setsunai": 1, "akarui": 1, "iyashi": 1},
         "season": {"winter": 1}, "scene": {"night": 1}}
    r = clean({"g": ["j-pop", "JPOP"], "r": "japan", "e": ["90s", "80s"], "m": ["setsunai", "akarui", "iyashi"], "c": ["夜"]}, v)
    ok = r == {"g": ["j-pop"], "r": ["japan"], "e": ["90s"], "m": ["setsunai", "akarui"]}
    print("self-test", "OK" if ok else "NG", r)
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--self-test":
        sys.exit(self_test())
    if a[0] == "run":
        w = int(a[a.index("--workers") + 1]) if "--workers" in a else 6
        b = int(a[a.index("--batch") + 1]) if "--batch" in a else 50
        run(w, b)
    elif a[0] == "check":
        check()
    elif a[0] == "build":
        build()
