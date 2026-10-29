#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""止まらない改善ループ（2026-10-29 たまごさん指示）。

たまごさん（10/29）：「ループエンジニアリング、ハーネスエンジニアリング、自動化でどんどんサイトが強く良くなる
ようにしてほしい。止まってるのは俺の中でありえない」「もっと気を利かせて。『これをやったら俺が喜ぶ』『お客さん
が喜ぶ』『もっと便利になる』『もっと軽くなる』と考えてほしい。望んでいるのは、自動で改善されてどんどん良くなって
いくやり方」。

新しい仕組みは作らず、既にある道具をつなぐ（材料はすべて既存の見張りの結果）：
  曲ページの5点      status/public/toukou_tenken.json（toukou_mimawari.py・Xなどに出した曲）
  マガジンの曲       status/public/magazine_gate.json（magazine/magazine_gate.py）
  消えた動画         status/public/hikkomi.json（hikkomi.py）
  白コマ             status/public/shirotobi.json（shirotobi_mimawari.py）
  反応               status/public/sns_hannou.json・toukou_daicho.json
  赤入れ             status/tenaoshi/kimari.json（tenaoshi_chou.py）
  週枠・同時本数     tools/shuwaku_sen.py（auto_launcher が守る。ここは積むだけ）
  公開               kohyou_osu.py（main と本番がズレたら deploy_project を押す係）＋ koutai_kanmon.py（後退の関所）
  戻す               hikkomi.py の push_generated と同じ形（worktree を作らず origin/main の上にコミットを1つ積む）

段（--tick が心臓から呼ばれ、中で間引く）：
  1 測る   毎時   本番を採点 → status/kaizen/score.json（写し status/public/kaizen.json）・status/public/kaizen.html
  2 選ぶ   10分   点の低い順×（X・LINEに出した／マガジンの曲）を優先して、1便15〜30分の直しを queue に積む（待ち3本を保つ）
  3 確かめ 10分   直しが終わったページを採点し直す。2回続けて下がったら自動で戻す
  4 学ぶ   10分   同じ種類の失敗が2回 → 関所を1つ足す便を1回だけ積む
  5 止まり 5分    30分どの子も動いていない／待ちが空 → 理由を見分けて再点火 or 理由を1行、Dispatch へ
  6 案出し 1日1回 4つの見方（①店主 ②お客さん ③便利 ④軽い）で案を出し、良い順に並べる。
                  見た目が変わらない案は直す便に、見た目が変わる案は非公開のA/B案を作る便にする
  7 効き目 毎時   型ごとに「効いた／変わらず／下がった」を数え、効いた型は増やし、効かない型はやめる
  8 週報   日曜朝 「今週、勝手に良くなったこと」3行（実物のURLつき）を Dispatch へ

守ること：棚（worlds.ts の shelves・admin_shelf_picks）は積む仕事の対象にしない／見た目は勝手に変えない（A/B止まり）／
有料APIなし（GET と Lovable の読む道具だけ）／Lovable のチャットに書かない／ブラウザ・web_fetch・git worktree なし／
並行の子（マガジンの曲ページ点検・Xで出した曲ページを強くする）と同じ仕事は積まない（status/kaizen/heikou.json）。

使い方:
  python3 tools/kaizen_loop.py --tick            # 心臓から
  python3 tools/kaizen_loop.py --saiten [--max 40]
  python3 tools/kaizen_loop.py --tsumu | --kakunin | --tomari | --an | --shuukan [--force]
  python3 tools/kaizen_loop.py --self-test
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

ST = os.path.join(REPO, "status")
KZ = os.path.join(ST, "kaizen")
PUB = os.path.join(ST, "public")
SCORE = os.path.join(KZ, "score.json")
STATE = os.path.join(KZ, "state.json")
BIN = os.path.join(KZ, "bin.json")            # 積んだ直し便の台帳（n → 対象・前の点・後の点・結果）
MANABU = os.path.join(KZ, "manabu.json")      # 失敗の種類ごとの回数・足した関所
KATA = os.path.join(KZ, "kata.json")          # 型ごとの効き目
AN = os.path.join(KZ, "an.json")              # 今日の案
MACHI = os.path.join(KZ, "machi.json")        # 積めなかった（シャッター中など）直し便の控え
HEIKOU = os.path.join(KZ, "heikou.json")      # 並行の子が受け持っている範囲
ANALYTICS = os.path.join(KZ, "analytics.json")
RIREKI = os.path.join(KZ, "rireki.jsonl")     # 採点の平均の推移
LOG = os.path.join(KZ, "kaizen.log")
PUB_JSON = os.path.join(PUB, "kaizen.json")
PUB_SHUUKAN = os.path.join(PUB, "kaizen_shuukan.json")
# 確認ページは status/public に置く（main の commit を待たずに gh-pages へそのまま出る＝pages_publish.sh の(2)）
PAGE = os.path.join(PUB, "kaizen.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/status/public/kaizen.html"
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
QUEUE = os.path.join(ST, "queue.json")

SITE = "https://joy-relief-station.lovable.app"
JRS = os.path.expanduser(os.environ.get("KAIZEN_JRS", "~/Desktop/joy-relief-station"))
PROJECT_ID = "8ebdb648-3686-4457-b42c-d01c493793b1"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 tamago-kaizen"

GAP_SAITEN = 55 * 60
GAP_TSUMU = 10 * 60
GAP_TOMARI = 5 * 60
GAP_AN = 20 * 3600
TOMARI_MIN = 30          # 30分どの子も動いていなければ止まり
KEEP_WAITING = 3         # 改善の待ちを常に3本
COOLDOWN_H = 24          # 同じページを直すのは1日1回まで
MAX_PROBE = 40           # 1時間に本番を読む曲ページの数（Mac と回線を重くしない）
LIMIT_MIN = 30

# 採点の項目（点の重み）。100点満点に直して出す。
W = {"kanren": 20, "copy": 15, "memo": 10, "douga": 20, "ikidomari": 10, "kensaku": 5,
     "shiro": 5, "hayasa": 10, "misettei": 5, "ogp": 5}
NAME = {"kanren": "関連4つ以上", "copy": "コピー", "memo": "メモと出典", "douga": "動画が生きている",
        "ikidomari": "行き止まりなし", "kensaku": "検索に出る", "shiro": "白コマなし", "hayasa": "速さ",
        "misettei": "未設定の表示なし", "ogp": "シェア表示（OGP）"}
# 直し方（子への指示の芯）。見た目を変えずに直せるものだけ。
NAOSHI = {
    "kanren": "関連（bridgeRelated）を理由の言える曲で4本以上にする。同じアーティストの別曲・カバー元・同じ時代の音の温度で選ぶ。棚には置かない",
    "copy": "曲ページのコピー（2行の型）を書く。ボンジョビおじさん構文。テンプレ文・ポエム禁止。事実は出典つき",
    "memo": "メモ（note）と出典（src）を足す。裏の取れた事実だけ（sekisho-jijitsu-shutten の関所を通す）",
    "douga": "再生できない動画を、同じ曲の生きている公式動画に差し替える（oEmbed 200 を確かめる）。見つからなければ hikkomi の表に入れて隠す",
    "ikidomari": "曲ページが開かない・リンク先が違う／無いものを直す（曲ページを作る・リンクを正しい曲へ）",
    "kensaku": "検索（aliases）に曲名・アーティスト名＋曲名・カタカナ⇔英語を足す",
    "shiro": "一瞬の白（白コマ）を出している箇所を直す（背景色の先出し・読み込み中の色）。見た目の配置は変えない",
    "hayasa": "HTMLを軽く・速くする（不要な読み込みの削除・画像の遅延読み込み・preload）。見た目は変えない",
    "misettei": "「未設定」「undefined」「NaN」「null」や壊れた画像の表示を消す（データを埋めるか、その枠を出さない）",
    "ogp": "og:title／og:description／og:image を入れる（曲ページは曲名・アーティスト・コピー・動画のサムネイル）",
}
MITAME = {"shiro"}  # 直すと見た目が少し動く可能性がある → 子に「配置は変えない」を強く言う
MISETTEI_RX = re.compile(r">\s*(未設定|undefined|NaN|null|\[object Object\])\s*<")


# ────────────────────────── 道具 ──────────────────────────
def now():
    return datetime.now()


def ts():
    return now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def load(p, d):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp%d" % os.getpid()
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def log(msg):
    line = "%s %s" % (now().strftime("%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        os.makedirs(KZ, exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1500000:
            with io.open(LOG, encoding="utf-8") as f:
                tail = f.read()[-500000:]
            with io.open(LOG, "w", encoding="utf-8") as f:
                f.write(tail)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def dispatch(kind, title, message, once_key=None, every_h=6):
    """Dispatch へ1行（同じ key は every_h 時間に1回まで）。"""
    st = load(STATE, {})
    key = once_key or ("%s|%s" % (kind, title))
    told = st.setdefault("told", {})
    last = told.get(key)
    if last:
        try:
            if (now() - datetime.strptime(last[:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() < every_h * 3600:
                return False
        except Exception:
            pass
    row = {"ts": ts(), "n": "kaizen-%s" % now().strftime("%Y%m%d%H%M"), "type": kind, "title": title, "message": message,
           "urls": [PAGE_URL]}
    with io.open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    told[key] = ts()
    save(STATE, st)
    return True


def gate(name, gap):
    """name の段を gap 秒に1回だけ通す。"""
    st = load(STATE, {})
    stamps = st.setdefault("stamps", {})
    t = stamps.get(name) or 0
    if time.time() - t < gap:
        return False
    stamps[name] = time.time()
    save(STATE, st)
    return True


_LAST_URL = {"u": None}


def fetch(url, timeout=20, want_body=True):
    """GET 1本。(status, 秒, バイト, 本文)。失敗は status=0。転送された先は _LAST_URL["u"] に残す。"""
    t0 = time.time()
    _LAST_URL["u"] = url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            _LAST_URL["u"] = r.geturl()
            body = r.read(2500000) if want_body else b""
            return r.status, round(time.time() - t0, 2), len(body), body.decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, round(time.time() - t0, 2), 0, ""
    except Exception:
        return 0, round(time.time() - t0, 2), 0, ""


def yt_alive(vid):
    """YouTube の oEmbed（無料・鍵なし）。True/False/None（測れず）。"""
    if not vid:
        return None
    st, _, _, _ = fetch("https://www.youtube.com/oembed?format=json&url=" +
                        urllib.parse.quote("https://www.youtube.com/watch?v=" + vid), timeout=12, want_body=False)
    if st == 200:
        return True
    if st in (401, 403, 404):
        return False
    return None


def song_url(key):
    a, s = key.split("/", 1)
    return "%s/cover-guide?artist=%s&song=%s" % (SITE, urllib.parse.quote(a), urllib.parse.quote(s))


# ────────────────────────── 1 測る ──────────────────────────
def kind_of_fail(text):
    t = str(text or "")
    if "関連" in t:
        return "kanren"
    if "コピー" in t:
        return "copy"
    if "メモ" in t or "出典" in t:
        return "memo"
    if "動画" in t or "再生" in t:
        return "douga"
    if "検索" in t:
        return "kensaku"
    if "曲ページが無い" in t or "開かない" in t or "リンク" in t or "名簿に無い" in t:
        return "ikidomari"
    if "マガジン" in t:
        return "ikidomari"
    return "misettei"


def collect_targets():
    """採点するページの一覧。曲ページ（Xなどに出した・LINEで配った・マガジンに載った）＋ 固定のページ。"""
    songs = {}
    tk = load(os.path.join(PUB, "toukou_tenken.json"), {})
    hannou = load(os.path.join(PUB, "sns_hannou.json"), {}).get("posts") or {}
    daicho = load(os.path.join(PUB, "toukou_daicho.json"), {})
    react = {}
    for p in daicho.get("posts") or []:
        k = p.get("songKey")
        h = hannou.get(p.get("id") or "") or {}
        v = 0
        for f in ("views", "likes", "shares", "saves", "comments"):
            x = h.get(f)
            if isinstance(x, (int, float)):
                v += x * (1 if f == "views" else 20)
        if k:
            react[k] = react.get(k, 0) + v
    for it in tk.get("items") or []:
        k = it.get("key")
        if not k or "/" not in k:
            continue
        s = songs.setdefault(k, {"key": k, "artist": it.get("artist"), "title": it.get("title"), "url": it.get("url") or song_url(k),
                                 "soto": [], "mags": [], "fails": [], "related": None})
        s["soto"] = sorted(set(s["soto"]) | set(it.get("platforms") or []))
        s["related"] = it.get("related")
        s["fails"] += [kind_of_fail(f) for f in it.get("fails") or []]
        sr = it.get("search") or {}
        if sr and not all(sr.values()):
            s["fails"].append("kensaku")
    # LINE で配った曲（ごきげんの種）
    gdir = os.path.join(ST, "gokigen_tane", "gou")
    try:
        for fn in os.listdir(gdir):
            g = load(os.path.join(gdir, fn), {})
            k = g.get("key") or g.get("songKey") or ((g.get("kyoku") or {}).get("key") if isinstance(g.get("kyoku"), dict) else None)
            if k and "/" in k and (g.get("sent") or g.get("haishin") or g.get("sentAt")):
                s = songs.setdefault(k, {"key": k, "artist": g.get("artist"), "title": g.get("title"), "url": song_url(k),
                                         "soto": [], "mags": [], "fails": [], "related": None})
                s["soto"] = sorted(set(s["soto"]) | {"line"})
    except OSError:
        pass
    mg = load(os.path.join(PUB, "magazine_gate.json"), {})
    for mag, rows in (mg.get("mags") or {}).items():
        for r in rows:
            k = r.get("key")
            if not k or "/" not in k:
                continue
            s = songs.setdefault(k, {"key": k, "artist": r.get("artist"), "title": r.get("title"), "url": r.get("link") or song_url(k),
                                     "soto": [], "mags": [], "fails": [], "related": None})
            s["mags"] = sorted(set(s["mags"]) | {mag})
            if s.get("related") is None:
                s["related"] = r.get("related")
            s["fails"] += [kind_of_fail(f) for f in r.get("fails") or []]
            if r.get("state") in ("no_page", "link_wrong", "link_dead"):
                s["fails"].append("ikidomari")
    for k, s in songs.items():
        s["fails"] = sorted(set(s["fails"]))
        s["react"] = react.get(k, 0)
    statics = [{"key": "page:/", "url": SITE + "/", "label": "トップ"},
               {"key": "page:/world/music", "url": SITE + "/world/music", "label": "音楽の扉（棚の入口）"},
               {"key": "page:/search", "url": SITE + "/search", "label": "検索"},
               {"key": "page:/magazine/backnumber.html", "url": SITE + "/magazine/backnumber.html", "label": "マガジンのバックナンバー"}]
    img_ng = {}
    for x in mg.get("img_ng") or []:
        if x.get("where") == "本番":
            img_ng[x.get("page")] = img_ng.get(x.get("page"), 0) + 1
    link_ng = {}
    for mag, rows in (mg.get("mags") or {}).items():
        link_ng[mag] = sum(1 for r in rows if r.get("state") in ("no_page", "link_wrong", "link_dead"))
    for mag in sorted((mg.get("mags") or {}).keys()):
        path = mag_path(mag)
        statics.append({"key": "mag:" + mag, "url": SITE + path, "label": "マガジン " + mag,
                        "imgNg": img_ng.get(path, 0), "linkNg": link_ng.get(mag, 0)})
    return songs, statics


def mag_path(mag):
    """magazine_gate の名前 → 本番の道。特集（React）は "feature:<名前>" で来るが本番は /feature/<名前>。
    2026-10-29：/magazine/feature:<名前> を測って 404→14点の偽の直し便を18本作っていたのを直した。"""
    if mag.startswith("feature:"):
        return "/feature/" + mag.split(":", 1)[1]
    return "/magazine/" + mag


HAYASA_SEN = 1.5


def probe_page(url):
    st, sec, size, body = fetch(url, timeout=25)
    # 転送される道（例 /feature/aoi-sangosho-f → /feature/aoi-sangosho）は、転送の1往復ぶん遅く測れて
    # 「遅い」の偽の直し便になる（2026-10-29 実測：2.50秒→転送先は0.45〜0.60秒）。読者が着く先で測り直す。
    final = _LAST_URL["u"]
    if st == 200 and final and final != url:
        s2, t2, z2, b2 = fetch(final, timeout=25)
        if s2 == 200:
            st, sec, size, body = s2, t2, z2, b2
    # 速さは1回だけだと回線のゆれで外れる（2026-10-29 実測：同じ曲ページが 0.26秒／5.08秒／0.53秒）。
    # 線を超えたときだけ2回測り直し、3回の真ん中を使う。直し便で直せない「ゆれ」を積まないため。
    if st == 200 and sec > HAYASA_SEN:
        secs = [sec]
        for _ in range(2):
            s2, t2, _, _ = fetch(url, timeout=25, want_body=False)
            if s2 == 200:
                secs.append(t2)
        sec = sorted(secs)[len(secs) // 2]
    ogp = {k: bool(re.search(r'<meta[^>]+property="%s"[^>]+content="[^"]+' % k, body)) for k in ("og:title", "og:description", "og:image")}
    m = re.search(r'share-image/([A-Za-z0-9_-]{11})', body) or re.search(r'(?:youtube\.com/(?:embed|watch\?v=)|youtu\.be/|i\.ytimg\.com/vi/)([A-Za-z0-9_-]{11})', body)
    return {"at": ts(), "status": st, "sec": sec, "bytes": size, "ogp": ogp,
            "misettei": len(MISETTEI_RX.findall(body)), "yt": m.group(1) if m else None,
            "ldjson": "application/ld+json" in body}


def score_checks(kind, info, probe, shiro_bad=False, dead_yt=None):
    """(点, 項目の一覧)。kind=song/page/mag。"""
    checks = []

    def add(k, ok, note=""):
        checks.append({"k": k, "ok": bool(ok), "w": W[k], "note": note})
    fails = set(info.get("fails") or [])
    p = probe or {}
    http_ok = p.get("status") == 200
    if kind == "song":
        rel = info.get("related")
        add("kanren", "kanren" not in fails and (rel is None or rel >= 4), "" if rel is None else "%s本" % rel)
        add("copy", "copy" not in fails)
        add("memo", "memo" not in fails)
        dead = ("douga" in fails) or (dead_yt is False)
        add("douga", not dead)
        add("kensaku", "kensaku" not in fails)
    if p:
        add("ikidomari", http_ok and "ikidomari" not in fails and not info.get("linkNg"),
            "" if http_ok else "HTTP %s" % p.get("status"))
        s = p.get("sec") or 99
        add("hayasa", http_ok and s <= HAYASA_SEN, "%.2f秒" % s)
        add("misettei", http_ok and not p.get("misettei") and not info.get("imgNg"),
            ("壊れた画像%d" % info.get("imgNg")) if info.get("imgNg") else "")
        og = p.get("ogp") or {}
        add("ogp", http_ok and all(og.values()), ",".join(k for k, v in og.items() if not v))
    elif kind == "song":
        add("ikidomari", "ikidomari" not in fails)
    if kind != "song":
        add("shiro", not shiro_bad)
    got = sum(c["w"] for c in checks if c["ok"])
    tot = sum(c["w"] for c in checks) or 1
    return round(100.0 * got / tot, 1), checks


def shirotobi_bad():
    d = load(os.path.join(PUB, "shirotobi.json"), {})
    return d.get("result") in ("赤", "NG", "落ち", "白飛びあり") or bool(d.get("shirokoma"))


def saiten(max_probe=MAX_PROBE, net=True):
    prev = load(SCORE, {})
    pprobe = {r["key"]: r.get("probe") for r in prev.get("pages") or [] if r.get("probe")}
    songs, statics = collect_targets()
    shiro = shirotobi_bad()
    # 本番を読む曲：外に出した・マガジンの曲を先に、前に読んだのが古い順
    order = sorted(songs.values(), key=lambda s: (0 if (s["soto"] or s["mags"]) else 1,
                                                   (pprobe.get(s["key"]) or {}).get("at") or ""))
    to_probe = set(s["key"] for s in order[:max_probe]) if net else set()
    pages = []
    for st in statics:
        pr = probe_page(st["url"]) if net else pprobe.get(st["key"])
        kind = "mag" if st["key"].startswith("mag:") else "page"
        sc, ch = score_checks(kind, st, pr, shiro_bad=(shiro and st["key"] in ("page:/", "page:/world/music")))
        pages.append({"key": st["key"], "kind": kind, "label": st["label"], "url": st["url"], "score": sc, "checks": ch,
                      "probe": pr, "soto": [], "mags": [], "react": 0})
    for s in songs.values():
        pr = pprobe.get(s["key"])
        dead = None
        if s["key"] in to_probe:
            pr = probe_page(s["url"])
            if pr.get("yt"):
                dead = yt_alive(pr["yt"])
                pr["ytAlive"] = dead
        elif pr:
            dead = pr.get("ytAlive")
        sc, ch = score_checks("song", s, pr, dead_yt=dead)
        pages.append({"key": s["key"], "kind": "song", "label": "%s「%s」" % (s.get("artist") or "", s.get("title") or ""),
                      "url": s["url"], "score": sc, "checks": ch, "probe": pr, "soto": s["soto"], "mags": s["mags"],
                      "react": s.get("react", 0)})
    pages.sort(key=lambda r: (r["score"], -need_weight(r)))
    avg = round(sum(r["score"] for r in pages) / max(1, len(pages)), 1)
    out = {"at": ts(), "what": "本番の採点（tools/kaizen_loop.py・毎時）。曲ページ＝Xなどに出した・LINEで配った・マガジンの曲。",
           "heikin": avg, "pages_n": len(pages), "manten": sum(1 for r in pages if r["score"] >= 100),
           "probed": len(to_probe) + (len(statics) if net else 0), "W": W, "NAME": NAME, "pages": pages}
    save(SCORE, out)
    with io.open(RIREKI, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": out["at"], "heikin": avg, "n": len(pages), "manten": out["manten"]}, ensure_ascii=False) + "\n")
    log("採点：%dページ・平均%.1f点・満点%d（本番を読んだ%d）" % (len(pages), avg, out["manten"], out["probed"]))
    return out


def need_weight(r):
    """直す順の重み。点が低いほど・外に出したほど・マガジンの曲ほど・反応が大きいほど先。"""
    w = (100.0 - r["score"])
    if r.get("soto"):
        w *= 2.0
        if "line" in r["soto"]:
            w *= 1.3
    if r.get("mags"):
        w *= 1.5
    if r.get("kind") in ("page", "mag"):
        w *= 1.8   # トップ・入口・マガジンは見る人が多い
    if r.get("react"):
        w *= 1.0 + min(1.0, r["react"] / 2000.0)
    return round(w, 2)


# ────────────────────────── 2 選ぶ・積む ──────────────────────────
def load_queue_items():
    try:
        import queue_store
        return (queue_store.load_queue() or {}).get("items") or []
    except Exception:
        return (load(QUEUE, {}) or {}).get("items") or []


def heikou_skip(r, fails_kinds):
    """並行の子が受け持っている範囲なら、その種類を外す。残った種類を返す。"""
    h = load(HEIKOU, {})
    kinds = list(fails_kinds)
    for c in h.get("ko") or []:
        until = c.get("until")
        if until and now().strftime("%Y-%m-%d") > until:
            continue
        scope = c.get("scope")
        hit = (scope == "magazine" and r.get("mags")) or (scope == "soto" and r.get("soto"))
        if hit:
            kinds = [k for k in kinds if k not in (c.get("kinds") or [])]
    return kinds


def kata_yameta():
    k = load(KATA, {})
    return set(x for x, v in (k.get("kata") or {}).items() if v.get("hantei") == "やめた")


def candidates(score=None, items=None, bin_=None):
    score = score or load(SCORE, {})
    items = items if items is not None else load_queue_items()
    bin_ = bin_ if bin_ is not None else load(BIN, {})
    busy_text = " ".join(str(i.get("what") or "")[:3000] + str(i.get("title") or "")
                         for i in items if i.get("status") in ("waiting", "running") and not i.get("kaizen"))
    recent = {}
    for n, b in bin_.items():
        recent.setdefault(b.get("key"), []).append(b)
    yameta = kata_yameta()
    out = []
    for r in score.get("pages") or []:
        if r["score"] >= 100:
            continue
        kinds = [c["k"] for c in r["checks"] if not c["ok"]]
        kinds = [k for k in heikou_skip(r, kinds) if k not in yameta]
        if not kinds:
            continue
        skip = False
        for b in recent.get(r["key"], []):
            if b.get("state") in ("machi", "hashiri", "kakunin"):
                skip = True
            t = b.get("at") or ""
            try:
                if (now() - datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() < COOLDOWN_H * 3600:
                    skip = True
            except Exception:
                pass
        if skip:
            continue
        # 他の仕事が同じページを持っていたら積まない（同じ仕事を二重にしない）
        if r["kind"] == "song":
            a, s = r["key"].split("/", 1)
            if ("artist=%s&song=%s" % (a, s)) in busy_text or (" %s " % r["key"]) in busy_text:
                continue
        out.append(dict(r, kinds=kinds, need=need_weight(r)))
    out.sort(key=lambda x: -x["need"])
    return out


def job_text(c):
    kinds = c["kinds"][:3]   # 1便は小さく（3種類まで）
    lines = ["【改善ループ・直し便】%s を直す（本番の点 %.0f → 上げる）" % (c["label"], c["score"]),
             "対象：%s" % c["url"],
             "落ちている所：" + "／".join("%s（%s）" % (NAME[k], next((x["note"] for x in c["checks"] if x["k"] == k), "") or "×") for k in kinds),
             "やること："]
    for k in kinds:
        lines.append("・" + NAOSHI[k])
    lines += [
        "この1件だけ。15〜30分で終わる大きさ。ほかのページ・棚（worlds.ts の shelves・admin_shelf_picks）・見た目（配置・色・大きさ）は触らない。Grok由来の変更は戻さない。",
        "直し方：joy-relief-station を直す → prebuild の関所を全部通す → `python3 tools/koutai_kanmon.py --check` が PASS → `python3 tools/uwagaki_kanmon.py --push --msg \"kaizen: …\" <ファイル>` で main へ。公開は kohyou_osu が押す（Lovable のチャットには書かない）。",
        "報告の最後の行に必ず `KAIZEN_COMMIT: <コミットのsha>` と `KAIZEN_URL: %s` を書く（点が下がったら機械が自動で戻すのに使う）。" % c["url"],
        "web_fetch・ブラウザ・git worktree は使わない。道具は無料のものだけ。調べ物は tools/wiki_lookup.py・tools/mac_fetch.py。たまごさんに質問しない。",
    ]
    return "\n".join(lines), kinds


def enqueue(text, label, kaizen_meta, priority=2):
    """queue に1件。シャッター中などで積めなければ machi に控えて False。"""
    try:
        import command_ingest
        r = command_ingest.queue_add(text, priority=priority, label=label, origin="factory", model="claude-sonnet-5")
    except Exception as e:
        r = ("failed", "積めない：%r" % (e,))
    msg = str(r[1] if isinstance(r, (list, tuple)) and len(r) > 1 else r)
    m = re.search(r"(\d+)番", msg)
    if not (isinstance(r, (list, tuple)) and r[0] == "done" and m):
        machi = load(MACHI, {"items": []})
        if not any(x.get("label") == label for x in machi["items"]):
            machi["items"].append({"at": ts(), "label": label, "text": text, "meta": kaizen_meta, "why": msg[:200]})
            machi["items"] = machi["items"][-30:]
            save(MACHI, machi)
        log("積めなかった（控えた）：%s → %s" % (label, msg[:120]))
        return None
    n = m.group(1)
    # 印を付ける（改善便・30分・待ちの先頭だけ順番を前へ）
    try:
        import queue_store
        with queue_store.queue_lock():
            q = queue_store.load_queue()
            snap = queue_store.snapshot_items(q)
            for it in q.get("items") or []:
                if str(it.get("n")) == n:
                    it["kaizen"] = True
                    it["kaizenKey"] = kaizen_meta.get("key")
                    it["limitMin"] = LIMIT_MIN if kaizen_meta.get("type") == "naoshi" else 45
                    it["priority"] = priority
                    it["kaizenPrio"] = priority
            queue_store.save_queue(q, snapshot=snap)
    except Exception as e:
        log("印を付けられなかった %s：%r" % (n, e))
    log("積んだ：%s番 %s" % (n, label))
    return n


def front_one(items):
    """改善の待ちのうち一番古い1本だけを、待ちの先頭（order=300）へ。2本目以降は並ばせる（判定日赤と半々にする）。"""
    try:
        import queue_store
        with queue_store.queue_lock():
            q = queue_store.load_queue()
            snap = queue_store.snapshot_items(q)
            kz = [it for it in q.get("items") or [] if it.get("kaizen") and it.get("status") == "waiting"]
            if any(it.get("kaizen") and it.get("status") == "running" for it in q.get("items") or []):
                kz_front = []
            else:
                kz_front = sorted(kz, key=lambda it: int(it.get("n") or 0))[:1]
            ch = False
            for it in kz:
                # 発車の並びは（urgent, 優先度, order, 番号）。先頭の1本だけ優先度1・order 300 にする
                # （判定日赤＝優先度1の列より前に1本だけ。走っている間は前に出さない＝もう1席は判定日赤へ）
                want = 300 if it in kz_front else None
                wantp = 1 if it in kz_front else int(it.get("kaizenPrio") or 2)
                if it.get("order") != want or int(it.get("priority") or 9) != wantp:
                    it.setdefault("kaizenPrio", int(it.get("priority") or 2) if it not in kz_front else 2)
                    if want is None:
                        it.pop("order", None)
                    else:
                        it["order"] = want
                    it["priority"] = wantp
                    ch = True
            if ch:
                queue_store.save_queue(q, snapshot=snap)
    except Exception as e:
        log("並べ替えできず：%r" % (e,))


def tsumu():
    items = load_queue_items()
    bin_ = load(BIN, {})
    waiting = [i for i in items if i.get("kaizen") and i.get("status") == "waiting"]
    # シャッターが上がっていれば、控えていた便を先に積む
    machi = load(MACHI, {"items": []})
    if machi["items"] and not shutter_on():
        rest = []
        for m in machi["items"]:
            n = enqueue(m["text"], m["label"], m["meta"], priority=(m["meta"] or {}).get("priority", 2)) if len(waiting) < KEEP_WAITING else None
            if n:
                bin_[n] = dict(m["meta"], n=n, at=ts(), state="machi")
                waiting.append({"n": n})
            else:
                rest.append(m)
        machi["items"] = rest
        save(MACHI, machi)
    added = 0
    for c in candidates(items=items, bin_=bin_):
        if len(waiting) >= KEEP_WAITING:
            break
        text, kinds = job_text(c)
        label = "改善：%s の%sを直す" % (c["label"][:40], "・".join(NAME[k] for k in kinds))
        meta = {"key": c["key"], "url": c["url"], "kinds": kinds, "before": c["score"], "type": "naoshi", "kind": c["kind"]}
        n = enqueue(text, label, meta)
        if n:
            bin_[n] = dict(meta, n=n, at=ts(), state="machi")
            waiting.append({"n": n})
            added += 1
        else:
            bin_["machi:" + c["key"]] = dict(meta, n=None, at=ts(), state="hikae")
            break   # 積めない時は1件だけ控えて終わる（同じ理由で全部落ちるので）
    save(BIN, bin_)
    front_one(items)
    return added


def shutter_on():
    try:
        import kinkyu_shutter
        return kinkyu_shutter.is_on()
    except Exception:
        return os.path.exists(os.path.join(ST, "KINKYU_SHUTTER"))


# ────────────────────────── 3 確かめる・戻す ──────────────────────────
def _dt(s):
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def rescore_one(b):
    """直した1ページだけ本番で採点し直す。"""
    score = load(SCORE, {})
    row = next((r for r in score.get("pages") or [] if r["key"] == b.get("key")), None)
    if not row:
        return None, None
    pr = probe_page(b["url"])
    if pr.get("status") != 200:
        return None, pr   # 回線の揺れでは判定しない
    dead = yt_alive(pr.get("yt")) if row["kind"] == "song" else None
    pr["ytAlive"] = dead
    songs, statics = collect_targets()   # 見張りの最新結果（関連・コピー等）を読み直す
    info = songs.get(b["key"]) or next((s for s in statics if s["key"] == b["key"]), {}) or {}
    sc, ch = score_checks(row["kind"], info, pr, dead_yt=dead)
    return sc, pr


def git_jrs(*a, env=None, inp=None, timeout=120):
    p = subprocess.run(["git", "-C", JRS] + list(a), capture_output=True, text=True, timeout=timeout, env=env, input=inp)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (a[0], (p.stderr or p.stdout)[-300:]))
    return p.stdout.strip()


def modosu(sha, why):
    """そのコミットだけを戻す。worktree を作らず origin/main の上に「戻す」コミットを1つ積んで push（hikkomi.py と同じ形）。
    後から同じファイルが変わっていたら機械では戻さず、戻す便を積む。Grok 由来は戻さない。"""
    if not re.match(r"^[0-9a-f]{7,40}$", sha or ""):
        return False, "shaが無い"
    git_jrs("fetch", "-q", "origin", "main")
    info = git_jrs("log", "-1", "--format=%an %ae %s %b", sha)
    if re.search(r"grok", info, re.I):
        return False, "Grok由来なので戻さない"
    files = [f for f in git_jrs("diff-tree", "--no-commit-id", "--name-only", "-r", sha).splitlines() if f]
    if not files:
        return False, "変わったファイルが無い"
    if any("worlds.ts" in f for f in files):
        return False, "棚のファイルを含むので機械では戻さない"
    base = git_jrs("rev-parse", "origin/main")
    later = git_jrs("diff", "--name-only", sha, base, "--", *files)
    if later.strip():
        return False, "後から同じファイルが変わっている（%s）" % later.splitlines()[0]
    fd, idx = tempfile.mkstemp(prefix="kaizen_idx_")
    os.close(fd)
    try:
        env = dict(os.environ, GIT_INDEX_FILE=idx)
        git_jrs("read-tree", base, env=env)
        for f in files:
            try:
                blob = git_jrs("rev-parse", "%s^:%s" % (sha, f))
                mode = git_jrs("ls-tree", "%s^" % sha, "--", f).split()[0]
                git_jrs("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, blob, f), env=env)
            except RuntimeError:
                git_jrs("update-index", "--force-remove", "--", f, env=env)   # 前は無かったファイル
        tree = git_jrs("write-tree", env=env)
    finally:
        try:
            os.remove(idx)
        except OSError:
            pass
    msg = "kaizen: 点が下がったので %s を戻す（tools/kaizen_loop.py）\n\n%s" % (sha[:10], why)
    c = git_jrs("commit-tree", tree, "-p", base, "-m", msg)
    git_jrs("push", "-q", "origin", "%s:refs/heads/main" % c)
    return True, c


def harvest_bin():
    """積んだ便の進み具合を queue から写し、終わったものを採点し直して効き目を決める。"""
    bin_ = load(BIN, {})
    if not bin_:
        return 0
    items = {str(i.get("n")): i for i in load_queue_items()}
    manabu = load(MANABU, {"rows": [], "kanmon": {}})
    ch = 0
    for n, b in list(bin_.items()):
        if not b.get("n"):
            continue
        it = items.get(str(n))
        stq = (it or {}).get("status")
        if b.get("state") in ("kiita", "kawarazu", "modoshita", "shippai", "modosenai"):
            continue
        if stq == "running" and b.get("state") != "hashiri":
            b["state"] = "hashiri"
            b["startedAt"] = it.get("startedAt")
            ch += 1
            continue
        if stq in ("waiting", "running", None, "hold") and stq != "hold":
            continue
        # 終わった（done / awaiting_check / merged / hold / cancelled …）
        if not b.get("finishedAt"):
            res = str((it or {}).get("result") or "")
            m = re.search(r"KAIZEN_COMMIT:\s*`?([0-9a-f]{7,40})", res)
            b["finishedAt"] = str((it or {}).get("finishedAt") or ts())
            b["commit"] = m.group(1) if m else None
            b["qstatus"] = stq
            b["state"] = "kakunin"
            ok_job = stq in ("done", "awaiting_check", "merged") and b["commit"]
            if not ok_job:
                b["state"] = "shippai"
                manabu["rows"].append({"at": ts(), "kind": "+".join(b.get("kinds") or []) or b.get("type"), "n": n,
                                       "why": "子が直せずに終わった（%s・コミット無し）" % stq})
            ch += 1
            continue
        if b.get("state") != "kakunin":
            continue
        fin = _dt(b.get("finishedAt")) or now()
        mins = (now() - fin).total_seconds() / 60
        if mins < 20:
            continue   # 公開（kohyou_osu）と本番の入れ替わりを待つ
        # main と本番がズレたまま（公開の鍵が切れている等）なら、Dispatch に「公開待ち」を1回出して待つ（Dispatch が deploy_project を押す）
        kan = next(iter((load(os.path.join(ST, "kohyou_kanshi.json"), {}).get("items") or [])), {}) or {}
        if kan.get("hantei") not in (None, "青") and mins < 240:
            dispatch("koukai_machi", "公開待ち｜改善ループの直し（%s番・main %s）" % (n, (b.get("commit") or "")[:9]),
                     "%s の直しが main に入ったが本番に出ていない（%s）。deploy_project を押してください。" % (b["url"], kan.get("riyuu") or kan.get("hantei")),
                     once_key="koukai|" + str(b.get("commit")), every_h=999)
            continue
        sc, pr = rescore_one(b)
        if sc is None:
            continue
        b.setdefault("afters", []).append({"at": ts(), "score": sc})
        before = b.get("before") or 0
        if sc > before:
            b["state"] = "kiita"
            b["after"] = sc
            log("効いた：%s %s → %s（%s番）" % (b["key"], before, sc, n))
        elif sc < before - 2:
            downs = [a for a in b["afters"] if a["score"] < before - 2]
            if len(downs) >= 2:
                try:
                    ok, info = modosu(b.get("commit"), "%s が %s点 → %s点（%s番の直し）" % (b["url"], before, sc, n))
                except Exception as e:
                    ok, info = False, "戻せない：%r" % (e,)
                b["after"] = sc
                b["state"] = "modoshita" if ok else "modosenai"
                b["modoshi"] = info
                manabu["rows"].append({"at": ts(), "kind": "+".join(b.get("kinds") or []), "n": n,
                                       "why": "直したら点が下がった（%s→%s）" % (before, sc)})
                dispatch("kaizen_modoshi", "改善ループ：点が下がったので戻しました" if ok else "改善ループ：点が下がったが自動で戻せない",
                         "%s %s点→%s点（%s番）%s" % (b["url"], before, sc, n, "" if ok else "／" + str(info)), once_key="modoshi|" + n, every_h=999)
                if not ok:
                    enqueue("【改善ループ・戻す便】%s番の直しで %s の点が %s → %s に下がった。コミット %s を戻す（%s）。戻したら KAIZEN_COMMIT を書く。"
                            % (n, b["url"], before, sc, b.get("commit"), info), "改善：下がった直しを戻す（%s番）" % n,
                            {"key": b["key"], "url": b["url"], "type": "modoshi"}, priority=1)
        elif mins > 180:
            b["state"] = "kawarazu"
            b["after"] = sc
        ch += 1
    save(BIN, bin_)
    save(MANABU, manabu)
    return ch


# ────────────────────────── 4 学ぶ ──────────────────────────
def manabu_kanmon():
    """同じ種類の失敗が2回 → 関所を1つ足す便を、その種類につき1回だけ積む。"""
    m = load(MANABU, {"rows": [], "kanmon": {}})
    cnt = {}
    for r in m.get("rows") or []:
        cnt[r["kind"]] = cnt.get(r["kind"], 0) + 1
    added = 0
    for kind, c in cnt.items():
        if c < 2 or kind in (m.get("kanmon") or {}):
            continue
        rows = [r for r in m["rows"] if r["kind"] == kind][-4:]
        text = ("【改善ループ・関所を1つ足す】同じ種類の失敗が%d回出た：%s\n" % (c, "・".join(NAME.get(k, k) for k in kind.split("+"))) +
                "\n".join("・%s %s番：%s" % (r["at"][:16], r.get("n"), r["why"]) for r in rows) +
                "\nやること：この失敗が次から公開前に機械で止まる関所（チェック）を1つ足す。joy-relief-station の prebuild（scripts/patrol/check-*.mjs）"
                "か tools/ の関所に、逆テスト（--self-test）つきで。台帳 tools/jidou_daicho.json に載せる。15〜30分。たまごさんに質問しない。"
                "報告の最後に KAIZEN_KANMON: <足した関所のファイル> を書く。")
        n = enqueue(text, "改善：同じ失敗2回→関所を足す（%s）" % kind, {"key": "kanmon:" + kind, "type": "kanmon"}, priority=2)
        if n:
            m.setdefault("kanmon", {})[kind] = {"at": ts(), "n": n}
            added += 1
    save(MANABU, m)
    return added


# ────────────────────────── 5 止まり検知 ──────────────────────────
def tomari_riyuu():
    """新規発車が止まっている理由（わざと止めている物）。無ければ None。"""
    if shutter_on():
        return "緊急停止（シャッター）中。解除は店主だけ（status/KINKYU_SHUTTER）"
    try:
        import shuwaku_sen
        h = shuwaku_sen.hantei()
        if h.get("stopNew"):
            return "週枠の線を超えている（%s）" % h.get("senLine")
    except Exception:
        pass
    fk = load(os.path.join(PUB, "fuka_hassha.json"), {})
    if fk.get("新規発車") == "不可":
        return "Macが重いので新規発車を止めている（%s）" % fk.get("理由")
    return None


def tomari(items=None, test_state=None):
    """30分以上どの子も動いていない、または改善の待ちが空 → 再点火して Dispatch に1行。戻り値は判定の辞書。"""
    items = items if items is not None else load_queue_items()
    st = test_state if test_state is not None else load(STATE, {})
    running = [i for i in items if i.get("status") == "running"]
    last = st.get("lastRunningAt")
    cands = [str(i.get("startedAt") or "") for i in items] + [str(i.get("finishedAt") or "") for i in items]
    cands = [c for c in cands if c[:2] == "20"]
    if cands:
        lt = max(cands)[:19]
        if not last or lt > last:
            last = lt
    if running:
        last = now().strftime("%Y-%m-%dT%H:%M:%S")
    st["lastRunningAt"] = last
    idle_min = None
    if last:
        try:
            idle_min = round((now() - datetime.strptime(last[:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() / 60)
        except Exception:
            idle_min = None
    kz_wait = [i for i in items if i.get("kaizen") and i.get("status") == "waiting"]
    res = {"at": ts(), "running": len(running), "idleMin": idle_min, "kaizenWaiting": len(kz_wait), "action": []}
    if test_state is None:
        save(STATE, dict(load(STATE, {}), lastRunningAt=last))
    if not kz_wait:
        res["action"].append("待ちが空→次の候補を積む")
        if test_state is None:
            tsumu()
    if idle_min is not None and idle_min >= TOMARI_MIN and not running:
        why = tomari_riyuu()
        res["riyuu"] = why
        if why:
            res["action"].append("理由つきの止まり：%s" % why)
            if test_state is None:
                dispatch("kaizen_tomari", "改善ループ：%d分どの子も動いていない" % idle_min,
                         "理由：%s。採点・案出し（無料の段）は回し続けています。" % why, once_key="tomari|" + why[:12], every_h=6)
        else:
            res["action"].append("理由なしの止まり→再点火")
            if test_state is None:
                for name in ("auto_launcher.py", "okoshi.py"):
                    try:
                        subprocess.Popen(["python3", os.path.join(HERE, name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
                dispatch("kaizen_tomari", "改善ループ：止まりを見つけて再点火しました",
                         "%d分どの子も動いていなかった（止める理由なし）→ 発車係と起こし役を起こした。" % idle_min,
                         once_key="tomari|saitenka", every_h=1)
    if test_state is None:
        s2 = load(STATE, {})
        s2["tomari"] = res
        save(STATE, s2)
    return res


# ────────────────────────── 6 案出し（4つの見方） ──────────────────────────
def lovable_read(name, args):
    """Lovable の読む道具だけ（lovable_kinshi の白名簿を通す）。鍵・取り直し・名乗りは kohyou_osu.Lovable をそのまま使う。失敗は None。"""
    try:
        import lovable_kinshi
        import kohyou_osu
        lovable_kinshi.mamoru("tools/call", {"name": name, "arguments": args})
        lv = kohyou_osu.Lovable()
        if not lv.ok():
            return None
        lv.hello()
        raw = lv._rpc("tools/call", {"name": name, "arguments": args})
        lines = [x for x in (raw or "").splitlines() if x.startswith("data: ")]
        if not lines:
            log("Lovableの解析が読めない：%s" % (raw or "")[:160])
            return None
        txt = json.loads(lines[-1][6:])["result"]["content"][0]["text"]
        try:
            return json.loads(txt)
        except Exception:
            return {"text": txt}
    except Exception as e:
        log("Lovableの解析が読めない：%r" % (e,))
    return None


def get_analytics():
    end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    a = lovable_read("get_project_analytics", {"project_id": PROJECT_ID,
                                               "start_date": (end - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z"),
                                               "end_date": end.strftime("%Y-%m-%dT00:00:00Z")})
    if a and a.get("timeSeries"):
        save(ANALYTICS, {"at": ts(), "data": a})
        return a
    return (load(ANALYTICS, {}) or {}).get("data")


def an_dashi(score=None, analytics=None):
    """材料から案を作り、良い順に並べる。数字の見込みは仮説として書く（効き目は後で実測）。"""
    score = score or load(SCORE, {})
    pages = score.get("pages") or []
    a = analytics or {}
    ts_ = a.get("timeSeries") or {}
    pv = (ts_.get("pageviews") or {}).get("total")
    vis = (ts_.get("visitors") or {}).get("total")
    ppv = (ts_.get("pageviewsPerVisit") or {}).get("total")
    br = (ts_.get("bounceRate") or {}).get("total")
    plist = {x.get("label"): x.get("value") for x in (((a.get("lists") or {}).get("page") or {}).get("data") or [])}
    ideas = []

    def add(i):
        i.setdefault("jidou", not i.get("mitame"))
        ideas.append(i)
    songs = [r for r in pages if r["kind"] == "song"]
    probed = [r for r in songs if r.get("probe")]
    # ② お客さん：よく開かれる曲ページの穴（関連・動画・コピー）
    cg = plist.get("/cover-guide") or 0
    low = [r for r in songs if r["score"] < 90]
    if low:
        add({"id": "kyaku-kyokupage-ana", "mikata": "②お客さん", "title": "よく開かれる曲ページの穴を先にふさぐ（%d曲が90点未満）" % len(low),
             "dare": "曲ページに来た人", "tema": "関連が足りず次の曲を探す手間・動画が見られない行き止まり",
             "dore": "曲ページ週%s回のうち、穴のあるページに当たる分" % (cg or "?"),
             "mikomi": "90点未満 %d曲 → 0曲。曲ページからの次の1ページ（回遊）が増える" % len(low),
             "metric": "kyoku_lt90", "before": len(low), "mitame": False, "ten": 50 + len(low) + cg / 20.0,
             "jikkou": "直し便（2の段）で毎時積んでいる"})
    # ③ 便利：検索
    kn = [r for r in songs if any((c["k"] == "kensaku" and not c["ok"]) for c in r["checks"])]
    sv = plist.get("/search") or 0
    if kn:
        add({"id": "benri-kensaku", "mikata": "③便利", "title": "SNSで見た曲が検索で出ない %d曲に読み（aliases）を足す" % len(kn),
             "dare": "Xで見て曲名で探す人", "tema": "検索して0件→あきらめる手間", "dore": "検索 週%s回" % (sv or "?"),
             "mikomi": "出ない曲 %d → 0" % len(kn), "metric": "kensaku_ng", "before": len(kn), "mitame": False,
             "ten": 40 + 5 * len(kn) + sv / 10.0, "jikkou": "直し便で積む"})
    # ③ 便利：構造化データ（schema.org の MusicRecording。検索エンジンに曲名・アーティストを正しく渡す）
    nold = [r for r in probed if not (r.get("probe") or {}).get("ldjson")]
    if probed and len(nold) > len(probed) / 2:
        add({"id": "benri-ldjson", "mikata": "③便利", "title": "曲ページに構造化データ（schema.org MusicRecording）を入れる",
             "dare": "Googleで曲名を調べる人", "tema": "検索結果で何のページか分からない",
             "dore": "読んだ曲ページ%d本のうち%d本に無い" % (len(probed), len(nold)),
             "mikomi": "構造化データのある曲ページ %d%% → 100%%" % round(100 * (len(probed) - len(nold)) / max(1, len(probed))),
             "metric": "ldjson_pct", "before": round(100 * (len(probed) - len(nold)) / max(1, len(probed))), "mitame": False,
             "ten": 45, "tehon": "schema.org/MusicRecording・Google 検索セントラル『構造化データの概要』",
             "shiji": "joy-relief-station の曲ページ（/cover-guide）の SSR の head に JSON-LD（@type MusicRecording：name・byArtist・url・"
                      "thumbnailUrl）を出す。見た目は変えない。全曲共通の部品1か所で。"})
    # ④ 軽い：遅いページ
    slow = sorted([r for r in pages if (r.get("probe") or {}).get("sec", 0) > 1.5], key=lambda r: -(r["probe"]["sec"]))
    if slow:
        add({"id": "karui-osoi", "mikata": "④軽い", "title": "遅いページを軽くする（%d本が1.5秒超・いちばん遅いのは%s %.1f秒）" % (len(slow), slow[0]["label"], slow[0]["probe"]["sec"]),
             "dare": "スマホで開く人", "tema": "待ち時間", "dore": "1回あたり %.1f秒 → 1.5秒以下" % slow[0]["probe"]["sec"],
             "mikomi": "1.5秒超 %d本 → 0本" % len(slow), "metric": "osoi_n", "before": len(slow), "mitame": False,
             "ten": 30 + 4 * len(slow), "jikkou": "直し便（速さ）で積む"})
    heavy = sorted([r for r in pages if (r.get("probe") or {}).get("bytes", 0) > 300000], key=lambda r: -r["probe"]["bytes"])
    if heavy:
        add({"id": "karui-omoi", "mikata": "④軽い", "title": "送る量の多いページを削る（%d本が300KB超）" % len(heavy),
             "dare": "スマホの通信量", "tema": "通信量と待ち", "dore": "最大 %dKB" % (heavy[0]["probe"]["bytes"] // 1000),
             "mikomi": "300KB超 %d本 → 0本" % len(heavy), "metric": "omoi_n", "before": len(heavy), "mitame": False, "ten": 25 + 3 * len(heavy),
             "shiji": "HTMLに埋め込まれた大きなデータ（全曲の表など）を、そのページに要る分だけにする。見た目は変えない。"})
    # ② お客さん：回遊（見た目が変わる＝A/B止まり）
    if ppv is not None or br is not None:
        add({"id": "kyaku-tsugi-ikkyoku", "mikata": "②お客さん", "title": "曲ページの最後に『次の1曲』を大きく1枚（YouTube の『次の動画』の型）",
             "dare": "曲を聴き終わった人", "tema": "次に何を聴くか探す手間", "dore": "直帰率 %s%%・1回の訪問で %sページ" % (br, ppv),
             "mikomi": "1回の訪問で見るページ %s → +0.3（仮説）" % ppv, "metric": "ppv", "before": ppv, "mitame": True, "ten": 35,
             "tehon": "YouTube の終了画面・次の動画"})
    # ① 店主：同じ赤入れを二度言わせない
    km = load(os.path.join(ST, "tenaoshi", "kimari.json"), {}).get("kimari") or []
    yowai = [k for k in km if (k.get("kaisu") or 0) >= 2 and not k.get("regex") and k.get("level") != "ng"]
    if yowai:
        k = yowai[0]
        add({"id": "tencho-akaire-%s" % k.get("id"), "mikata": "①店主", "title": "赤入れ「%s」を機械の関所にする" % k.get("namae"),
             "dare": "たまごさん", "tema": "同じ赤入れをもう一度言う手間", "dore": "%d回言われている" % k.get("kaisu"),
             "mikomi": "この赤入れ 次の30日で0回", "metric": "akaire:" + str(k.get("id")), "before": k.get("kaisu"), "mitame": False,
             "ten": 55 + 5 * (k.get("kaisu") or 0),
             "shiji": "status/tenaoshi/kimari.json の「%s」を、公開前に機械で見つけて止める関所にする（言われた言葉：%s）。"
                      "逆テストつき。見た目は変えない。" % (k.get("namae"), "／".join(x.get("kotoba", "") for x in (k.get("akaire") or [])[:3]))})
    # ① 店主：外に出した曲の満点率（SNSに出したとき安心して貼れる）
    soto = [r for r in songs if r.get("soto")]
    if soto:
        ok = sum(1 for r in soto if r["score"] >= 100)
        add({"id": "tencho-soto-manten", "mikata": "①店主", "title": "SNSに出した曲ページを全部満点に（いま %d/%d）" % (ok, len(soto)),
             "dare": "たまごさん", "tema": "投稿のあとに自分で穴を見つける手間", "dore": "満点でない %d曲" % (len(soto) - ok),
             "mikomi": "満点率 %d%% → 100%%" % round(100 * ok / len(soto)), "metric": "soto_manten", "before": ok, "mitame": False,
             "ten": 48 + (len(soto) - ok), "jikkou": "直し便の重み（外に出した×2・LINE×1.3）で先に積んでいる"})
    ideas.sort(key=lambda i: -i["ten"])
    for r, i in enumerate(ideas, 1):
        i["jun"] = r
    return {"at": ts(), "zairyou": {"pageviews7d": pv, "visitors7d": vis, "ppv": ppv, "bounce": br, "pages": plist,
                                    "akaire": len(km), "kaizenAvg": score.get("heikin")},
            "ideas": ideas}


def an(force=False):
    a = get_analytics()
    res = an_dashi(analytics=a)
    old = load(AN, {})
    done = old.get("tsunda") or {}
    yameta = kata_yameta()
    # 見た目が変わらない案で「指示」を持つもの → 1日1本まで作る便に。見た目が変わる案 → A/B案を作る便（1日1本）
    n_auto = n_ab = 0
    for i in res["ideas"]:
        if i["id"] in done or i["id"] in yameta:
            i["joutai"] = (done.get(i["id"]) or {}).get("joutai") or ("やめた" if i["id"] in yameta else "")
            continue
        if not i["mitame"] and i.get("shiji") and n_auto == 0:
            text = ("【改善ループ・案】%s（%s）\n誰の・何が：%s の %s が減る（%s）\n見込み：%s\nやること：%s\n"
                    "手本：%s\n守ること：見た目は変えない・棚は触らない・Grok由来は戻さない・無料の道具だけ・Lovableのチャットに書かない。"
                    "prebuild の関所と koutai_kanmon --check を通して uwagaki_kanmon --push。報告の最後に KAIZEN_COMMIT: <sha>。15〜30分。"
                    % (i["title"], i["mikata"], i["dare"], i["tema"], i["dore"], i["mikomi"], i["shiji"], i.get("tehon") or "なし"))
            n = enqueue(text, "改善案：%s" % i["title"][:50], {"key": "an:" + i["id"], "type": "an", "metric": i.get("metric"),
                                                             "before": i.get("before")})
            if n:
                done[i["id"]] = {"at": ts(), "n": n, "joutai": "作っている", "metric": i.get("metric"), "before": i.get("before")}
                n_auto += 1
        elif i["mitame"] and n_ab == 0:
            text = ("【改善ループ・A/B案（非公開）】%s\n誰の・何が：%s の %s が減る（%s）。見込み：%s\n"
                    "やること：本番は触らない。share/check/kaizen-ab-%s.html に A＝今のまま／B＝案 の2つを、"
                    "スマホ幅とPC幅のスクショ付きで並べる（本番のHTMLを写して差し替えた静的な見本）。気に入っている見た目（色・字・余白）はBでも変えない。"
                    "数字（%%・px）を書くなら、同じページに「実測（出どころ）」と<pre>の生データを添える（無いと push の関所 sekisho で止まり、main 全体が上がらなくなる）。"
                    "棚は触らない。報告にそのページのURL。たまごさんは進捗表の確認待ちで OK＝Bを採用／やり直し＝Aのまま、を押すだけ。"
                    % (i["title"], i["dare"], i["tema"], i["dore"], i["mikomi"], i["id"]))
            n = enqueue(text, "改善A/B：%s（選ぶだけ）" % i["title"][:40], {"key": "ab:" + i["id"], "type": "ab"})
            if n:
                done[i["id"]] = {"at": ts(), "n": n, "joutai": "A/B案を作っている", "ab": True}
                n_ab += 1
    res["tsunda"] = done
    save(AN, res)
    log("案出し：%d案（積んだ 自動%d・A/B%d）" % (len(res["ideas"]), n_auto, n_ab))
    return res


# ────────────────────────── 7 効き目 ──────────────────────────
def kouka():
    bin_ = load(BIN, {})
    kata = {}
    for b in bin_.values():
        if b.get("type") != "naoshi":
            continue
        for k in b.get("kinds") or []:
            v = kata.setdefault(k, {"kiita": 0, "kawarazu": 0, "sagatta": 0, "shippai": 0, "agari": 0.0})
            s = b.get("state")
            if s == "kiita":
                v["kiita"] += 1
                v["agari"] += (b.get("after") or 0) - (b.get("before") or 0)
            elif s == "kawarazu":
                v["kawarazu"] += 1
            elif s in ("modoshita", "modosenai"):
                v["sagatta"] += 1
            elif s == "shippai":
                v["shippai"] += 1
    for k, v in kata.items():
        tot = v["kiita"] + v["kawarazu"] + v["sagatta"] + v["shippai"]
        v["tameshita"] = tot
        rate = v["kiita"] / float(tot) if tot else 0
        v["hantei"] = "やめた" if (tot >= 4 and rate < 0.25) else ("増やす" if (v["kiita"] >= 2 and rate >= 0.6) else "様子見")
    # A/B と案の採用
    a = load(AN, {})
    items = {str(i.get("n")): i for i in load_queue_items()}
    for iid, d in (a.get("tsunda") or {}).items():
        it = items.get(str(d.get("n")))
        if not it:
            continue
        if d.get("ab") and it.get("status") == "done" and it.get("okBy") and d.get("joutai") != "採用":
            d["joutai"] = "採用（Bを作る便を積んだ）"
            enqueue("【改善ループ・A/B採用】たまごさんが OK を押した案（%s番の B）を本番に入れる。A/Bページ share/check/kaizen-ab-%s.html の B どおり。"
                    "棚は触らない。関所を通して uwagaki_kanmon --push。KAIZEN_COMMIT: <sha>。" % (d.get("n"), iid),
                    "改善A/B：採用したBを本番へ（%s）" % iid, {"key": "abok:" + iid, "type": "an"}, priority=1)
    save(AN, a)
    save(KATA, {"at": ts(), "what": "型ごとの効き目（効いた=点が上がった／変わらず／下がった=自動で戻した／失敗=子が直せず）。4回試して効いたのが25%未満の型はやめる。",
                "kata": kata})
    return kata


# ────────────────────────── 8 週報 ──────────────────────────
def shuukan(force=False):
    st = load(STATE, {})
    wk = now().strftime("%G-W%V")
    if not force:
        if now().weekday() != 6 or not (6 <= now().hour < 12) or st.get("shuukanWeek") == wk:
            return None
    since = now() - timedelta(days=7)
    good = [b for b in load(BIN, {}).values() if b.get("state") == "kiita" and (_dt(b.get("finishedAt")) or now()) >= since]
    good.sort(key=lambda b: -((b.get("after") or 0) - (b.get("before") or 0)))
    rir = [json.loads(l) for l in io.open(RIREKI, encoding="utf-8")] if os.path.exists(RIREKI) else []
    wk_rows = [r for r in rir if (_dt(r.get("at")) or now()) >= since]
    a0 = wk_rows[0]["heikin"] if wk_rows else None
    a1 = wk_rows[-1]["heikin"] if wk_rows else None
    modo = [b for b in load(BIN, {}).values() if b.get("state") == "modoshita" and (_dt(b.get("finishedAt")) or now()) >= since]
    l1 = "今週、勝手に直って公開されたページ %d本（平均 +%.0f点）%s" % (
        len(good), (sum((b.get("after") or 0) - (b.get("before") or 0) for b in good) / len(good)) if good else 0,
        ("：" + " ".join(b["url"] for b in good[:2])) if good else "")
    l2 = "サイト全体の点 %s → %s（%s）" % (a0, a1, PAGE_URL)
    ab = [d for d in (load(AN, {}).get("tsunda") or {}).values() if d.get("ab")]
    l3 = "下がって自動で戻した %d本／選ぶだけのA/B案 %d件" % (len(modo), len(ab))
    out = {"at": ts(), "week": wk, "lines": [l1, l2, l3]}
    save(PUB_SHUUKAN, out)
    dispatch("kaizen_shuukan", "今週、勝手に良くなったこと", "\n".join(out["lines"]), once_key="shuukan|" + wk, every_h=999)
    st = load(STATE, {})
    st["shuukanWeek"] = wk
    save(STATE, st)
    return out


# ────────────────────────── 進捗表・確認ページ ──────────────────────────
def esc(s):
    return (str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def shoko(bin_=None):
    """回っている証拠：直して公開した件数・点数の前後。"""
    bin_ = bin_ if bin_ is not None else load(BIN, {})
    rows = [b for b in bin_.values() if b.get("n")]
    since = now() - timedelta(hours=24)
    d = {"tsunda": len(rows), "hashiri": sum(1 for b in rows if b.get("state") == "hashiri"),
         "machi": sum(1 for b in rows if b.get("state") == "machi"),
         "kiita": sum(1 for b in rows if b.get("state") == "kiita"),
         "kiita24h": sum(1 for b in rows if b.get("state") == "kiita" and (_dt(b.get("finishedAt")) or now()) >= since),
         "modoshita": sum(1 for b in rows if b.get("state") == "modoshita"),
         "shippai": sum(1 for b in rows if b.get("state") == "shippai"),
         "hikae": len(load(MACHI, {"items": []}).get("items") or [])}
    ups = [((b.get("before") or 0), (b.get("after") or 0)) for b in rows if b.get("state") == "kiita"]
    d["mae"] = round(sum(x for x, _ in ups) / len(ups), 1) if ups else None
    d["ato"] = round(sum(y for _, y in ups) / len(ups), 1) if ups else None
    return d


def write_public():
    sc = load(SCORE, {})
    st = load(STATE, {})
    an_ = load(AN, {})
    sh = shoko()
    tm = st.get("tomari") or {}
    hitokoto = "改善ループ　平均 %s点・満点 %s/%s・直して公開 %d件（24時間 %d）・待ち %d" % (
        sc.get("heikin"), sc.get("manten"), sc.get("pages_n"), sh["kiita"], sh["kiita24h"], tm.get("kaizenWaiting") or 0)
    if tm.get("riyuu"):
        hitokoto += "｜止まり：" + tm["riyuu"][:40]
    pub = {"at": ts(), "hitokoto": hitokoto, "page": PAGE_URL, "heikin": sc.get("heikin"), "manten": sc.get("manten"),
           "pages_n": sc.get("pages_n"), "shoko": sh, "tomari": tm,
           "hikui": [{k: r.get(k) for k in ("key", "label", "url", "score")} for r in (sc.get("pages") or [])[:15]],
           "ideas": [{k: i.get(k) for k in ("jun", "mikata", "title", "dare", "tema", "dore", "mikomi", "mitame")} for i in (an_.get("ideas") or [])[:12]],
           "kata": (load(KATA, {}).get("kata") or {}), "shuukan": load(PUB_SHUUKAN, {}).get("lines")}
    save(PUB_JSON, pub)
    write_page(sc, pub, an_)
    return pub


def write_page(sc, pub, an_):
    sh = pub["shoko"]
    rows = []
    for r in (sc.get("pages") or [])[:60]:
        bad = "・".join("%s%s" % (NAME[c["k"]], ("（%s）" % c["note"]) if c.get("note") else "") for c in r["checks"] if not c["ok"])
        tag = "".join(x for x in ["X" if "x" in r.get("soto", []) else "", " LINE" if "line" in r.get("soto", []) else "",
                                  " マガジン" if r.get("mags") else ""])
        rows.append("<tr><td class=n>%s</td><td><a href=\"%s\">%s</a><div class=s>%s</div></td><td class=s>%s</td></tr>"
                    % (r["score"], esc(r["url"]), esc(r["label"]), esc(tag.strip()), esc(bad or "—")))
    ideas = []
    for i in (an_.get("ideas") or []):
        j = (an_.get("tsunda") or {}).get(i["id"]) or {}
        ideas.append("<li><b>%s %s</b>%s<div class=s>誰の：%s／減る手間：%s／どれだけ：%s／見込み：%s%s</div></li>"
                     % (esc(i["mikata"]), esc(i["title"]), " <span class=ab>A/B・選ぶだけ</span>" if i.get("mitame") else "",
                        esc(i["dare"]), esc(i["tema"]), esc(i["dore"]), esc(i["mikomi"]),
                        ("／" + esc(j.get("joutai")) + ("（%s番）" % j.get("n") if j.get("n") else "")) if j else ""))
    ab = ["<li><a href=\"../../share/check/kaizen-ab-%s.html\">%s</a>（%s番）— 進捗表の確認待ちで OK＝B／やり直し＝A</li>" % (esc(k), esc(k), esc(d.get("n")))
          for k, d in (an_.get("tsunda") or {}).items() if d.get("ab")]
    kata = "".join("<li>%s：効いた%d・変わらず%d・下がった%d・失敗%d → <b>%s</b></li>" % (esc(NAME.get(k, k)), v["kiita"], v["kawarazu"], v["sagatta"], v["shippai"], esc(v["hantei"]))
                   for k, v in (pub.get("kata") or {}).items())
    tm = pub.get("tomari") or {}
    html = """<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>改善ループ</title><style>body{font:15px/1.6 -apple-system,sans-serif;margin:16px;max-width:860px;color:#222}h1{font-size:20px}h2{font-size:16px;margin-top:22px}
table{border-collapse:collapse;width:100%%}td{border-top:1px solid #eee;padding:6px 4px;vertical-align:top}.n{font-weight:700;width:3em}.s{font-size:12px;color:#666}
.ab{background:#fde68a;border-radius:4px;padding:0 4px;font-size:12px}.box{background:#f6f6f6;border-radius:8px;padding:10px}</style></head><body>
<h1>改善ループ（自動で本番を採点→直す→確かめる）</h1>
<div class=box>%s<br>更新 %s</div>
<h2>回っている証拠</h2><div class=box>積んだ直し %d件／走っている %d／待ち %d／<b>直して公開して点が上がった %d件</b>（直す前の平均 %s → 後 %s）／下がって自動で戻した %d／直せなかった %d／シャッター等で控え %d</div>
<h2>止まり検知</h2><div class=box>最後に子が動いたのは %s分前／走っている %s本／改善の待ち %s本%s</div>
<h2>今日の案（①店主 ②お客さん ③便利 ④軽い・良い順）</h2><ol>%s</ol>
<h2>選ぶだけ（A/B）</h2><ul>%s</ul>
<h2>効いた型・やめた型</h2><ul>%s</ul>
<h2>点の低いページ（直す順の材料）</h2><table>%s</table>
<p class=s>tools/kaizen_loop.py（心臓から・毎時採点）。材料：toukou_tenken／magazine_gate／hikkomi／shirotobi／sns_hannou／Lovable解析／手直し帳。</p>
</body></html>""" % (esc(pub["hitokoto"]), esc(pub["at"]), sh["tsunda"], sh["hashiri"], sh["machi"], sh["kiita"], sh["mae"], sh["ato"],
                     sh["modoshita"], sh["shippai"], sh["hikae"], esc(tm.get("idleMin")), esc(tm.get("running")), esc(tm.get("kaizenWaiting")),
                     ("／理由：" + esc(tm.get("riyuu"))) if tm.get("riyuu") else "",
                     "".join(ideas) or "<li>まだ</li>", "".join(ab) or "<li>まだ</li>", kata or "<li>まだ（直しが終わると数え始める）</li>", "".join(rows))
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with io.open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)


# ────────────────────────── 入口 ──────────────────────────
def tick():
    import fcntl
    os.makedirs(KZ, exist_ok=True)
    lf = io.open(os.path.join(KZ, ".lock"), "a+")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        return "busy"
    did = []
    if gate("tomari", GAP_TOMARI):
        tomari()
        did.append("tomari")
    if gate("saiten", GAP_SAITEN):
        saiten()
        kouka()
        did.append("saiten")
    if gate("tsumu", GAP_TSUMU):
        harvest_bin()
        manabu_kanmon()
        tsumu()
        did.append("tsumu")
    if now().hour >= 6 and gate("an", GAP_AN):
        an()
        did.append("an")
    if shuukan():
        did.append("shuukan")
    if did:
        write_public()
    return ",".join(did) or "skip"


def self_test():
    global SCORE, STATE, BIN, MANABU, KATA, AN, MACHI, HEIKOU, RIREKI, LOG, PUB_JSON, PAGE, OUTBOX, PUB_SHUUKAN
    d = tempfile.mkdtemp(prefix="kaizen_test_")
    try:
        SCORE, STATE, BIN, MANABU, KATA, AN, MACHI, HEIKOU, RIREKI, LOG, PUB_JSON, PAGE, OUTBOX, PUB_SHUUKAN = [
            os.path.join(d, x) for x in ("score.json", "state.json", "bin.json", "manabu.json", "kata.json", "an.json", "machi.json",
                                         "heikou.json", "rireki.jsonl", "log", "pub.json", "kaizen.html", "outbox.jsonl", "shuukan.json")]
        # 採点：関連2本・コピー無し・OGP欠けの曲ページは満点にならない／全部そろえば100
        pr_ok = {"status": 200, "sec": 0.5, "ogp": {"og:title": True, "og:description": True, "og:image": True}, "misettei": 0}
        s1, _ = score_checks("song", {"related": 6, "fails": []}, pr_ok, dead_yt=True)
        assert s1 == 100.0, s1
        s2, ch = score_checks("song", {"related": 2, "fails": ["kanren", "copy"]}, dict(pr_ok, ogp={"og:title": True, "og:description": False, "og:image": True}))
        assert s2 < 70 and not [c for c in ch if c["k"] == "ogp"][0]["ok"], s2
        s3, _ = score_checks("song", {"related": 6, "fails": []}, pr_ok, dead_yt=False)
        assert s3 < 100
        # 特集は /feature/<名前>（/magazine/feature:… は404の偽の直し便になる）
        assert mag_path("feature:funky") == "/feature/funky" and mag_path("ikareru-01.html") == "/magazine/ikareru-01.html"
        # 速さ：1回目が遅くても、測り直しの真ん中が速ければ合格（回線のゆれで直し便を積まない）
        global fetch
        _f, seq = fetch, iter([(200, 5.0, 10, "<html></html>"), (200, 0.4, 0, ""), (200, 0.6, 0, "")])
        fetch = lambda *a, **k: next(seq)
        try:
            assert probe_page("u")["sec"] == 0.6
            seq = iter([(200, 3.0, 10, ""), (200, 2.8, 0, ""), (200, 0.5, 0, "")])
            assert probe_page("u")["sec"] == 2.8  # 3回中2回遅い＝本当に遅い
        finally:
            fetch = _f
        assert kind_of_fail("関連が2本（4本以上必要）") == "kanren" and kind_of_fail("コピーなし／メモなし") == "copy"
        assert MISETTEI_RX.search("<span>未設定</span>") and not MISETTEI_RX.search("<p>未設定の曲は</p>")
        # 選ぶ：外に出した曲が、同じ点のただの曲より先／並行の子の範囲は外れる
        a = {"key": "a/x", "kind": "song", "label": "A", "url": "u1", "score": 60, "checks": [{"k": "copy", "ok": False, "w": 15, "note": ""}], "soto": ["x"], "mags": []}
        b = {"key": "b/y", "kind": "song", "label": "B", "url": "u2", "score": 60, "checks": [{"k": "copy", "ok": False, "w": 15, "note": ""}], "soto": [], "mags": []}
        c = {"key": "c/z", "kind": "song", "label": "C", "url": "u3", "score": 50, "checks": [{"k": "copy", "ok": False, "w": 15, "note": ""}], "soto": [], "mags": ["m.html"]}
        save(HEIKOU, {"ko": [{"name": "マガジンの曲ページを全部点検", "scope": "magazine", "kinds": ["copy"], "until": "2099-01-01"}]})
        cs = candidates(score={"pages": [b, a, c]}, items=[], bin_={})
        assert [x["key"] for x in cs] == ["a/x", "b/y"], [x["key"] for x in cs]
        # 他の仕事が持っているページは積まない
        cs2 = candidates(score={"pages": [a]}, items=[{"status": "waiting", "what": "cover-guide?artist=a&song=x を直す"}], bin_={})
        assert cs2 == []
        # 1日に同じページは1回
        cs3 = candidates(score={"pages": [a]}, items=[], bin_={"1": {"key": "a/x", "at": ts(), "state": "kiita"}})
        assert cs3 == []
        t, kinds = job_text(dict(a, kinds=["copy"], need=1))
        assert "KAIZEN_COMMIT" in t and "棚" in t and kinds == ["copy"]
        # 止まり検知：①40分前に最後の子・理由なし→再点火 ②走っている子あり→止まりではない ③待ちが空→積む
        old = (now() - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        r1 = tomari(items=[{"status": "done", "finishedAt": old}], test_state={})
        assert r1["idleMin"] >= 40 and any("止まり" in x for x in r1["action"]) and any("待ちが空" in x for x in r1["action"]), r1
        r2 = tomari(items=[{"status": "running", "kaizen": True}, {"status": "waiting", "kaizen": True}], test_state={})
        assert r2["idleMin"] == 0 and not any("止まり" in x for x in r2["action"]), r2
        # 学ぶ：同じ種類2回で関所便（ここでは積めない環境なので machi に控える＝積もうとしたことを確かめる）
        save(MANABU, {"rows": [{"at": ts(), "kind": "copy", "n": "1", "why": "x"}, {"at": ts(), "kind": "copy", "n": "2", "why": "y"}], "kanmon": {}})
        global enqueue
        _orig = enqueue
        got = []
        enqueue = lambda text, label, meta, priority=2: (got.append(label) or "999")
        try:
            assert manabu_kanmon() == 1 and "関所" in got[0]
            assert manabu_kanmon() == 0   # 2回目は積まない
        finally:
            enqueue = _orig
        # 効き目：4回やって1回も効かない型はやめる
        save(BIN, {str(i): {"type": "naoshi", "kinds": ["hayasa"], "state": "kawarazu"} for i in range(4)})
        assert kouka()["hayasa"]["hantei"] == "やめた"
        # 案：4つの見方が出る
        sc = {"heikin": 80, "pages": [dict(a, probe={"status": 200, "sec": 2.0, "bytes": 400000, "ldjson": False}, react=0,
                                           checks=[{"k": "kensaku", "ok": False, "w": 5, "note": ""}])]}
        res = an_dashi(score=sc, analytics={"timeSeries": {"pageviewsPerVisit": {"total": 6.5}, "bounceRate": {"total": 41}},
                                            "lists": {"page": {"data": [{"label": "/cover-guide", "value": 491}]}}})
        mk = set(i["mikata"] for i in res["ideas"])
        assert {"①店主", "②お客さん", "③便利", "④軽い"} <= mk, mk
        assert any(i["mitame"] for i in res["ideas"]) and all("mikomi" in i and "dare" in i for i in res["ideas"])
        # 週報は3行
        out = shuukan(force=True)
        assert len(out["lines"]) == 3
        write_public()
        assert os.path.exists(PAGE)
        print("SELF-TEST OK")
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    if "--tick" in a:
        print(tick())
    elif "--saiten" in a:
        mx = int(a[a.index("--max") + 1]) if "--max" in a else MAX_PROBE
        saiten(max_probe=mx, net="--no-net" not in a)
        kouka()
        write_public()
    elif "--tsumu" in a:
        harvest_bin()
        manabu_kanmon()
        print("積んだ", tsumu())
        write_public()
    elif "--kakunin" in a:
        print("確かめた", harvest_bin())
        write_public()
    elif "--tomari" in a:
        print(json.dumps(tomari(), ensure_ascii=False))
        write_public()
    elif "--an" in a:
        r = an(force=True)
        print(json.dumps([(i["jun"], i["mikata"], i["title"]) for i in r["ideas"]], ensure_ascii=False))
        write_public()
    elif "--shuukan" in a:
        print(json.dumps(shuukan(force="--force" in a), ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
