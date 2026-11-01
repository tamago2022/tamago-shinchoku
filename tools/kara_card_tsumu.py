#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""空カード埋め（2026-11-02 たまごさん指示）の数えと積み。手順の正本は status/kara_card/README.md。

  python3 tools/kara_card_tsumu.py --kazoe [JRS]     # 空の曲を数え直す → status/kara_card/ichiran_最新.json
  python3 tools/kara_card_tsumu.py --tsumu 40 [JRS]  # まだ積んでいない分を queue に積む（最後に「次を積む」便）
  python3 tools/kara_card_tsumu.py --self-test

空＝coverGuide.ts の曲で、src(URL) が無く・relatedBlurbs に動画が無く・tabiCopy に無いもの
（truthGate で note が消え、カードが「ここから旅をする」だけになる）。
"""
import collections
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(REPO, "status", "kara_card")
TSUNDA = os.path.join(DIR, "tsunda.json")
JRS_DEFAULT = "/Users/mac/Desktop/joy-relief-station"
SHIMEKIRI = "2026-11-03T18:00"  # 火曜の週枠リセット。これを過ぎたら積まない
CHUNK = 20

ART_RE = re.compile(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"((?:[^"\\]|\\.)*)"')
SONG_RE = re.compile(r'\{\s*id:\s*"([^"]+)",\s*title:\s*"((?:[^"\\]|\\.)*)"')


def kazoe_text(cg, blurbs_txt, tabi_txt):
    blurbs = set(re.findall(r'^ "([^"]+)": \{', blurbs_txt, re.M))
    tabi = set(re.findall(r'^\s*"([^"]+/[^"]+)":', tabi_txt, re.M))
    ev = [(m.start(), "a", m) for m in ART_RE.finditer(cg)] + [(m.start(), "s", m) for m in SONG_RE.finditer(cg)]
    ev.sort(key=lambda x: x[0])
    res = collections.OrderedDict()
    cur = None
    tot = 0
    for i, (p, k, m) in enumerate(ev):
        if k == "a":
            cur = (m.group(1), m.group(2))
            res.setdefault(cur, [])
            continue
        if cur is None:
            continue
        end = ev[i + 1][0] if i + 1 < len(ev) else len(cg)
        body = cg[p:end]
        tot += 1
        has = bool(re.search(r'\bsrc:\s*(\[\s*)?"https?://', body))
        yt = re.search(r'youtubeId:\s*"([^"]+)"', body)
        yt = yt.group(1) if yt else None
        if has or yt in blurbs or ("%s/%s" % (cur[0], m.group(1))) in tabi:
            continue
        res[cur].append(m.group(1))
    arts = [{"id": a[0], "name": a[1], "kara": len(v), "songs": v} for a, v in res.items() if v]
    arts.sort(key=lambda x: -x["kara"])
    return {"zen_kyoku": tot, "kara": sum(a["kara"] for a in arts), "artist_su": len(arts), "artists": arts}


def kazoe(jrs):
    import subprocess

    def r(p):
        # 作業場の枝・手元の変更に引っぱられないよう、まず origin/main の中身を読む
        try:
            subprocess.run(["git", "-C", jrs, "fetch", "-q", "origin", "main"], timeout=120, capture_output=True)
            out = subprocess.run(["git", "-C", jrs, "show", "origin/main:" + p], timeout=60, capture_output=True)
            if out.returncode == 0 and out.stdout:
                return out.stdout.decode("utf-8")
        except Exception:
            pass
        return open(os.path.join(jrs, p), encoding="utf-8").read()
    return kazoe_text(r("src/lib/coverGuide.ts"), r("src/lib/relatedBlurbs.generated.ts"), r("src/lib/tabiCopy.ts"))


def sns_artists():
    try:
        d = json.load(open(os.path.join(REPO, "status", "public", "toukou_daicho.json"), encoding="utf-8"))
    except Exception:
        return []
    out = []
    for p in d.get("posts", []):
        k = p.get("songKey")
        if k and k.split("/")[0] not in out:
            out.append(k.split("/")[0])
    return out


def bin_list(data, sns):
    """件数の多い順（ただし20曲で割る）→ SNSで出したアーティスト。"""
    by = {a["id"]: a for a in data["artists"]}
    order = [a["id"] for a in data["artists"] if a["kara"] >= 10]
    order += [x for x in sns if x in by and x not in order]
    order += [a["id"] for a in data["artists"] if a["id"] not in order]
    bins = []
    for aid in order:
        songs = by[aid]["songs"]
        for i in range(0, len(songs), CHUNK):
            part = songs[i:i + CHUNK]
            bins.append({"key": "%s#%d" % (aid, i // CHUNK + 1), "artist": aid, "name": by[aid]["name"], "songs": part,
                         "bu": i // CHUNK + 1, "busu": (len(songs) + CHUNK - 1) // CHUNK})
    return bins


def what_of(b):
    bu = "（%d/%d）" % (b["bu"], b["busu"]) if b["busu"] > 1 else ""
    return ("【空カード埋め】%s%s の曲カードが「ここから旅をする」だけになっている%d曲を埋めて本番に出す。\n"
            "対象の曲ID：%s\n"
            "やり方・出典の決まり・書く形・関所・公開・記録は status/kara_card/README.md のとおり（見本は HYUKOH）。\n"
            "スキル sekisho-jijitsu-shutten と bonjovi-ojisan-kobun を必ず通す。取り違え禁止・ポエム禁止・出典は畳んで1行。\n"
            "棚の曲の入れ替え・追加はしない（文章を書くだけ）。ブラウザ・web_fetch・Lovableのエージェントは使わない。たまごさんに質問しない。\n"
            "【完了条件】本番 https://joy-relief-station.lovable.app/cover-guide?artist=%s で、その曲のカードに文が出ている。"
            "status/kara_card/hanei.jsonl に【反映】の1行。\n"
            "【報告】埋めた曲数／書けずに残した曲と理由／本番URL の3行。"
            % (b["name"], bu, len(b["songs"]), ", ".join(b["songs"]), b["artist"]))


def load_tsunda():
    try:
        return json.load(open(TSUNDA, encoding="utf-8"))
    except Exception:
        return {"keys": [], "log": []}


def tsumu(n, jrs):
    if time.strftime("%Y-%m-%dT%H:%M") >= SHIMEKIRI:
        print("締め切り（%s）を過ぎたので積みません" % SHIMEKIRI)
        return 0
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import command_ingest
    data = kazoe(jrs)
    t = load_tsunda()
    done = set(t["keys"])
    bins = [b for b in bin_list(data, sns_artists()) if b["key"] not in done and b["artist"] != "hyukoh"]
    added = 0
    for b in bins[:n]:
        bu = "（%d/%d）" % (b["bu"], b["busu"]) if b["busu"] > 1 else ""
        st, msg = command_ingest.queue_add(what_of(b), priority=1, label="空カード埋め｜%s%s" % (b["name"], bu),
                                           origin="user", urgent=True)
        t["keys"].append(b["key"])
        t["log"].append({"at": time.strftime("%F %T"), "key": b["key"], "st": st, "msg": msg})
        added += 1
    rest = len(bins) - added
    if rest > 0:
        st, msg = command_ingest.queue_add(
            "【空カード埋め・次を積む】python3 tools/kara_card_tsumu.py --tsumu %d を1回走らせ、出力をそのまま報告する。"
            "（残り%d便。%s を過ぎたら積まない。手順は status/kara_card/README.md）" % (n, rest, SHIMEKIRI),
            priority=1, label="空カード埋め｜次の%d便を積む（残り%d）重複OK" % (n, rest), origin="user", urgent=True)
        t["log"].append({"at": time.strftime("%F %T"), "key": "tsugi", "st": st, "msg": msg})
    os.makedirs(DIR, exist_ok=True)
    json.dump(t, open(TSUNDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("空 %d曲／%dアーティスト。今回 %d便を積んだ・残り %d便" % (data["kara"], data["artist_su"], added, rest))
    return added


def self_test():
    cg = ('{ id: "a1", name: "A", songs: [\n { id: "s1", title: "T1", note: "", youtubeId: "y1" },\n'
          ' { id: "s2", title: "T2", note: "x", youtubeId: "y2", src: ["https://e"] },\n'
          ' { id: "s3", title: "T3", note: "", youtubeId: "yb" },\n { id: "s4", title: "T4", note: "", youtubeId: "y4" },\n]},\n')
    d = kazoe_text(cg, ' "yb": {\n', '  "a1/s4": "x",\n')
    assert d["zen_kyoku"] == 4 and d["kara"] == 1 and d["artists"][0]["songs"] == ["s1"], d
    big = {"artists": [{"id": "b", "name": "B", "kara": 45, "songs": ["x%d" % i for i in range(45)]}]}
    bins = bin_list(big, [])
    assert [len(b["songs"]) for b in bins] == [20, 20, 5] and bins[2]["busu"] == 3
    print("self-test OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    jrs = next((x for x in a if not x.startswith("--") and not x.isdigit()), JRS_DEFAULT)
    if "--self-test" in a:
        self_test()
    elif "--kazoe" in a:
        d = kazoe(jrs)
        os.makedirs(DIR, exist_ok=True)
        json.dump({"at": time.strftime("%F %T"), **{k: v for k, v in d.items() if k != "artists"},
                   "artists": [{k: v for k, v in x.items() if k != "songs"} for x in d["artists"]]},
                  open(os.path.join(DIR, "ichiran_saishin.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(d["zen_kyoku"], d["kara"], d["artist_su"])
    elif "--tsumu" in a:
        n = int(a[a.index("--tsumu") + 1])
        tsumu(n, jrs)
    else:
        print(__doc__)
