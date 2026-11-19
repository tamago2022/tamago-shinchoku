#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投稿動画の「後ろで流れている曲」を当てる係（Shazam方式・2026-10-11 新設）。Mac で走らせる。

  python3 tools/oto_hantei.py --setup                 # 道具をそろえる（~/.tamago/oto_venv に shazamio）
  python3 tools/oto_hantei.py --url <投稿URL> [--url ...]   # 判定して記録（本番には書かない）
  python3 tools/oto_hantei.py --test                  # 試験：【1】＋既存10本。正解率と誤判定数を出す
  python3 tools/oto_hantei.py --url <URL> --apply     # 採用なら曲ページの関連へ貼る（★関所あり）
  python3 tools/oto_hantei.py --self-test             # 判定ルールだけの机上テスト（ネット・音なし）

■ 一番大事な決め：間違った情報を出さない。分からないものは何もしない（空欄）。
  採用するのは、次の全部を満たしたときだけ：
   ① 12秒ずつ切った複数の区間を別々に Shazam に聞き、**2か所以上で同じ曲（track key）**と出た
   ② その2か所は**10秒以上離れていて**、曲の中の位置（offset）のずれが、動画の中の時間のずれと
      ±2.5秒で一致した（＝同じ曲が続けて流れている。偶然の一致を落とす）
   ③ 別の曲が2か所以上で出ていない（2曲以上が混ざる動画は保留）
   ④ 題名に remix / sped up / slowed / cover / karaoke / live 等が付いた「版違い」ではない
   ⑤ うちの曲データ（coverGuideLite）に、歌手名（名前か別名に完全一致）と曲名（完全一致）で
      **ちょうど1曲だけ**当たった（名前の部分一致では繋がない＝別人事故の再発防止）
  1つでも欠けたら「保留」で、曲ページにも投稿カードにも何も出さない。理由は記録に残す。

■ 本番に貼る関所（--apply）
  status/oto_hantei/shiken.json の最新試験で **誤判定0** でなければ、--apply は何もしない。

■ 記録（どの音源の何秒目で何と一致したか）
  status/oto_hantei/kiroku.jsonl … 1回の判定ごとに1行（区間ごとの結果つき）
  status/oto_hantei/kekka.json   … 投稿ごとの最新の結論
  status/public/oto_kono_kyoku.json … 採用された「投稿 → この曲」の対応（カードの「この曲」用のデータ）

■ 守ること
  ・音は鳴らさない（ffmpeg で切り出すだけ。再生しない）。
  ・動画は ~/.tamago/oto/ に一時保存し、判定が終わったら**消す**（空き容量を食わない）。
  ・ダウンロード前に空き容量を見て、2GB未満なら取りに行かない（「容量不足」で終了）。
  ・お金：shazamio は無料（Shazam の公開エンドポイントを使う非公式ライブラリ・鍵なし）。
    有料API（ACRCloud / AudD）は使っていない。費用は status/oto_hantei/hiyou.md。
"""
import argparse
import asyncio
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9))
ST = os.path.join(REPO, "status", "oto_hantei")
KIROKU = os.path.join(ST, "kiroku.jsonl")
KEKKA = os.path.join(ST, "kekka.json")
SHIKEN = os.path.join(ST, "shiken.json")
KONO = os.path.join(REPO, "status", "public", "oto_kono_kyoku.json")
HOME = os.path.expanduser("~")
VENV = os.path.join(HOME, ".tamago", "oto_venv")
WORK = os.path.join(HOME, ".tamago", "oto")
YTDLP = os.path.join(HOME, ".tamago", "bin", "yt-dlp")
PATHS = ["/opt/homebrew/bin", "/usr/local/bin", os.path.join(HOME, ".tamago", "bin")]
os.environ["PATH"] = ":".join(PATHS + [os.environ.get("PATH", "")])

WIN = 12          # 1区間の長さ（秒）
STEP = 10         # 区間の開始をずらす幅（秒）
MAX_WIN = 8       # 1本で聞く区間の上限
MIN_APART = 10    # 一致とみなす2区間の最低の離れ（秒）
OFF_TOL = 2.5     # 曲の中の位置のずれ の許し幅（秒）
MIN_FREE_GB = 2.0

BAD_VERSION = re.compile(r"remix|\bmix\b|sped|slowed|nightcore|cover|karaoke|instrumental|\blive\b|acoustic|"
                         r"reverb|\b8d\b|tiktok|mashup|bootleg|カバー|リミックス|ライブ|弾いてみた|歌ってみた", re.I)
SAFE_PAREN = re.compile(r"remaster|version|mono|stereo|single|album|edit$|radio edit|feat\.?|ft\.|from ", re.I)

# 試験の正解（kitai）。None＝正解が分からない投稿（採用したら「要確認」として数える）。
#   cover=True … 演奏・歌が本人ではない（原曲と出たら誤判定）。
TEST = [
    {"url": "https://x.com/G10Hung/status/2106882557421744248", "kitai": "mj/beat-it", "why": "たまごさん判断"},
    {"url": "https://x.com/Photomusicrock/status/2060773706171908336", "kitai": "ac-dc/highway-to-hell", "why": "danceCards：Highway to Hell が流れる"},
    {"url": "https://x.com/mcucolo57/status/2096379872268472634", "kitai": "righteous-brothers/unchained-melody-2", "why": "extraCards：後ろで流れているのは"},
    {"url": "https://x.com/eskisarkiIar/status/2092084563854172628", "kitai": None, "cover": True, "why": "白髪の女性が歌う（本人ではない）"},
    {"url": "https://x.com/no_earthquake/status/2095415265605648765", "kitai": None, "cover": True, "why": "子どもたちのものまね（本人ではない）"},
    {"url": "https://x.com/tositaisto/status/2097417413268525145", "kitai": None, "why": "BGM未確認"},
    {"url": "https://x.com/ThoNg676733/status/2038964541166404025", "kitai": None, "why": "BGM未確認"},
    {"url": "https://x.com/Li_Qianmo/status/2059910043185852777", "kitai": None, "why": "料理動画・BGM未確認"},
    {"url": "https://x.com/XWorldCuisines/status/2060704796932182057", "kitai": None, "why": "料理動画・BGM未確認"},
    {"url": "https://x.com/mikazzz2024/status/2077197765063647700", "kitai": None, "why": "料理動画・BGM未確認"},
    {"url": "https://x.com/akafaceUS/status/2053244622995165691", "kitai": None, "why": "BGM未確認"},
]


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def strip_title(t):
    """(…) / [ … ] / - … の付け足しを外す。版違いの印があれば (None, 理由) を返す。"""
    t0 = str(t or "")
    extras = re.findall(r"[\(\[（【]([^\)\]）】]*)[\)\]）】]", t0)
    dash = re.split(r"\s[-–—]\s", t0, maxsplit=1)
    if len(dash) == 2:
        extras.append(dash[1])
    for e in extras:
        if BAD_VERSION.search(e):
            return None, "版違い（%s）" % e.strip()
    if BAD_VERSION.search(dash[0]):
        return None, "版違い（%s）" % dash[0].strip()
    base = re.sub(r"\s*[\(\[（【][^\)\]）】]*[\)\]）】]", "", dash[0])
    return norm(base), ""


def split_artists(sub):
    parts = re.split(r"\s*(?:,|&|＆| x | feat\.? | ft\.? | and |、)\s*", str(sub or ""), flags=re.I)
    return [norm(p) for p in parts if p.strip()]


# ------------------------------------------------------------------ うちの曲データ
def lite_path():
    for p in [os.path.join(HOME, "Desktop", "joy-relief-station", "src", "lib", "coverGuideLite.generated.ts"),
              os.path.join(REPO, "status", "_v1oc", "jrs", "src", "lib", "coverGuideLite.generated.ts")]:
        if os.path.exists(p):
            return p
    return None


_LITE = {}


def load_lite():
    if _LITE.get("a") is not None:
        return _LITE["a"]
    arts = []
    p = lite_path()
    if p:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line.startswith('{"id":'):
                try:
                    arts.append(json.loads(line.rstrip(",")))
                except Exception:
                    pass
    _LITE["a"] = arts
    return arts


def artist_names(a):
    names = {norm(a.get("name"))}
    # 「Michael Jackson / The Jackson 5」のような並び書きは、それぞれも本人名として扱う
    for piece in re.split(r"\s*/\s*", a.get("name") or ""):
        if piece.strip():
            names.add(norm(piece))
    for x in a.get("aliases") or []:
        names.add(norm(x))
    return {n for n in names if n}


def find_song(title, subtitle, arts=None):
    """(artistId, songId, 理由)。ちょうど1曲だけ当たったときだけ返す。"""
    base, why = strip_title(title)
    if base is None:
        return None, None, why
    cand_art = split_artists(subtitle)
    if not cand_art:
        return None, None, "歌手名が空"
    hits = []
    for a in (arts if arts is not None else load_lite()):
        names = artist_names(a)
        if norm(subtitle) in names or cand_art[0] in names:
            for s in a.get("songs") or []:
                b2, _ = strip_title(s.get("title"))
                if b2 is not None and b2 == base:
                    hits.append((a["id"], s["id"]))
    hits = sorted(set(hits))
    if len(hits) == 1:
        return hits[0][0], hits[0][1], ""
    if not hits:
        return None, None, "曲ページ無し（%s／%s）" % (subtitle, title)
    return None, None, "曲ページが複数当たる（%s）" % ", ".join("%s/%s" % h for h in hits)


# ------------------------------------------------------------------ 判定ルール（ネット無しで試せる部分）
def decide(windows):
    """windows: [{start, key, title, subtitle, offset}]（keyが無い＝一致なし）。
    返す: {status, key?, title?, subtitle?, pair?, why}"""
    by = {}
    for w in windows:
        if w.get("key"):
            by.setdefault(w["key"], []).append(w)
    multi = {k: v for k, v in by.items() if len(v) >= 2}
    if not by:
        return {"status": "保留", "why": "どの区間でも一致なし"}
    if not multi:
        return {"status": "保留", "why": "一致が1か所だけ（二重チェック不成立）"}
    good = {}
    for k, v in multi.items():
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                a, b = v[i], v[j]
                dt = b["start"] - a["start"]
                if abs(dt) < MIN_APART or a.get("offset") is None or b.get("offset") is None:
                    continue
                if abs((b["offset"] - a["offset"]) - dt) <= OFF_TOL:
                    good.setdefault(k, (a, b))
    if len(multi) >= 2:
        return {"status": "保留", "why": "別の曲も2か所以上で出た（%s）" % " / ".join(
            "%s—%s" % (v[0].get("subtitle"), v[0].get("title")) for v in multi.values())}
    if not good:
        return {"status": "保留", "why": "2か所で同じ曲だが、曲の中の位置のずれが動画の時間と合わない"}
    k, (a, b) = list(good.items())[0]
    return {"status": "一致", "key": k, "title": a.get("title"), "subtitle": a.get("subtitle"),
            "isrc": a.get("isrc"), "shazamUrl": a.get("url"),
            "pair": [{"start": a["start"], "offset": a["offset"]}, {"start": b["start"], "offset": b["offset"]}],
            "hits": len(by[k]), "of": len(windows), "why": ""}


# ------------------------------------------------------------------ 道具
def free_gb():
    st = os.statvfs(HOME)
    return st.f_bavail * st.f_frsize / 1e9


def have_shazamio():
    try:
        import shazamio  # noqa: F401
        return True
    except Exception:
        return False


def reexec_in_venv():
    py = os.path.join(VENV, "bin", "python3")
    if os.path.exists(py) and os.path.realpath(sys.executable) != os.path.realpath(py):
        os.execv(py, [py] + sys.argv)


def setup():
    if free_gb() < MIN_FREE_GB:
        return {"ok": False, "why": "容量不足（空き%.1fGB）" % free_gb()}
    py = None
    for c in ["/opt/homebrew/bin/python3.12", "/opt/homebrew/bin/python3.11", "/opt/homebrew/bin/python3",
              "/usr/local/bin/python3", "python3"]:
        if shutil.which(c) or os.path.exists(c):
            py = c
            break
    if not os.path.exists(os.path.join(VENV, "bin", "python3")):
        subprocess.run([py, "-m", "venv", VENV], check=False)
    pip = os.path.join(VENV, "bin", "pip")
    r = subprocess.run([pip, "install", "-q", "--upgrade", "pip", "shazamio"], capture_output=True, text=True, timeout=170)
    return {"ok": r.returncode == 0, "py": py, "err": (r.stderr or "")[-400:], "ffmpeg": shutil.which("ffmpeg")}


def download(url):
    """動画を ~/.tamago/oto/ に一時保存。(path, why)"""
    if free_gb() < MIN_FREE_GB:
        return None, "容量不足（空き%.1fGB）" % free_gb()
    os.makedirs(WORK, exist_ok=True)
    if not os.path.exists(YTDLP):
        return None, "yt-dlp が無い（tools/insta_get.py で入る）"
    r = subprocess.run([YTDLP, "--no-playlist", "-q", "--no-warnings", "-f", "ba/b[ext=mp4]/b",
                        "--max-filesize", "150M", "-o", os.path.join(WORK, "%(id)s.%(ext)s"),
                        "--print", "after_move:filepath", url], capture_output=True, text=True, timeout=120)
    paths = [l for l in (r.stdout or "").splitlines() if os.path.exists(l.strip())]
    if not paths:
        return None, "取得失敗：%s" % ((r.stderr or "").strip().splitlines() or ["?"])[-1][:160]
    return paths[-1].strip(), ""


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def cut(path, start, out):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(start), "-t", str(WIN), "-i", path,
                    "-vn", "-ac", "1", "-ar", "16000", out], check=False)
    return os.path.exists(out) and os.path.getsize(out) > 1000


async def _recognize(shazam, p):
    fn = getattr(shazam, "recognize", None) or getattr(shazam, "recognize_song")
    return await fn(p)


def listen(path):
    """区間ごとに Shazam に聞く。音は鳴らさない。"""
    from shazamio import Shazam
    dur = duration(path)
    starts = [0]
    while starts[-1] + STEP + 6 <= dur and len(starts) < MAX_WIN:
        starts.append(starts[-1] + STEP)
    out = []
    shazam = Shazam()
    loop = asyncio.new_event_loop()
    for s in starts:
        wav = os.path.join(WORK, "_w_%d_%d.wav" % (os.getpid(), s))
        if not cut(path, s, wav):
            out.append({"start": s, "err": "切り出し失敗"})
            continue
        try:
            res = loop.run_until_complete(_recognize(shazam, wav)) or {}
        except Exception as e:  # noqa: BLE001
            res = {"_err": str(e)[:120]}
        finally:
            try:
                os.remove(wav)
            except OSError:
                pass
        tr = res.get("track") or {}
        m0 = (res.get("matches") or [{}])[0]
        w = {"start": s}
        if tr.get("key"):
            w.update({"key": tr.get("key"), "title": tr.get("title"), "subtitle": tr.get("subtitle"),
                      "isrc": tr.get("isrc"), "url": tr.get("url"), "offset": m0.get("offset"),
                      "timeskew": m0.get("timeskew"), "frequencyskew": m0.get("frequencyskew")})
        elif res.get("_err"):
            w["err"] = res["_err"]
        out.append(w)
        time.sleep(1.5)
    loop.close()
    return dur, out


def judge(url, keep=False):
    rec = {"at": now(), "url": url, "how": "shazamio（無料）＋2区間一致＋位置ずれ照合"}
    path, why = download(url)
    if not path:
        rec.update({"status": "取得できず", "why": why})
        return rec
    try:
        dur, wins = listen(path)
    finally:
        if not keep:
            try:
                os.remove(path)
            except OSError:
                pass
    rec.update({"dur": round(dur, 1), "windows": wins})
    d = decide(wins)
    rec.update(d)
    if d["status"] == "一致":
        aid, sid, why2 = find_song(d["title"], d["subtitle"])
        if aid:
            rec.update({"status": "採用", "artistId": aid, "songId": sid,
                        "page": "https://joy-relief-station.lovable.app/cover-guide?artist=%s&song=%s" % (aid, sid)})
        else:
            rec.update({"status": "保留", "why": why2})
    return rec


def save(rec):
    os.makedirs(ST, exist_ok=True)
    with io.open(KIROKU, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        k = json.load(io.open(KEKKA, encoding="utf-8"))
    except Exception:
        k = {}
    k[rec["url"]] = {x: rec.get(x) for x in ("at", "status", "why", "title", "subtitle", "artistId", "songId", "page", "pair", "hits", "of")}
    io.open(KEKKA + ".tmp", "w", encoding="utf-8").write(json.dumps(k, ensure_ascii=False, indent=1))
    os.replace(KEKKA + ".tmp", KEKKA)


def shiken_ok():
    try:
        s = json.load(io.open(SHIKEN, encoding="utf-8"))
        return s.get("gohantei") == 0 and s.get("judged", 0) >= 10
    except Exception:
        return False


def apply(rec):
    """★関所：試験で誤判定0のときだけ。採用以外は何もしない。"""
    if rec.get("status") != "採用":
        return {"applied": False, "why": "採用ではない"}
    if not shiken_ok():
        return {"applied": False, "why": "試験の誤判定が0でない／試験未実施のため本番に入れない"}
    sys.path.insert(0, HERE)
    import oto_tsunagu
    r = oto_tsunagu.tsunagu(rec["artistId"], rec["songId"], rec["url"],
                            note="この曲が後ろで流れている投稿。", by="自動判定",
                            kiroku={"pair": rec.get("pair"), "shazam": "%s — %s" % (rec.get("subtitle"), rec.get("title"))})
    try:
        kk = json.load(io.open(KONO, encoding="utf-8"))
    except Exception:
        kk = {}
    kk[rec["url"]] = {"artistId": rec["artistId"], "songId": rec["songId"], "page": rec["page"], "at": now(), "by": "自動判定"}
    os.makedirs(os.path.dirname(KONO), exist_ok=True)
    io.open(KONO + ".tmp", "w", encoding="utf-8").write(json.dumps(kk, ensure_ascii=False, indent=1))
    os.replace(KONO + ".tmp", KONO)
    return {"applied": True, "tsunagu": r}


def run_test(only=None):
    rows = []
    for t in TEST:
        if only is not None and t["url"] not in only:
            continue
        rec = judge(t["url"])
        save(rec)
        got = "%s/%s" % (rec["artistId"], rec["songId"]) if rec.get("status") == "採用" else None
        if rec.get("status") == "取得できず":
            hyouka = "対象外（取得できず）"
        elif t.get("kitai"):
            hyouka = "正解" if got == t["kitai"] else ("見送り（空欄）" if got is None else "誤判定")
        elif t.get("cover"):
            hyouka = "正解（空欄）" if got is None else "誤判定（本人ではない演奏を原曲と判定）"
        else:
            hyouka = "空欄" if got is None else "要確認（正解不明・採用した）"
        rows.append({"url": t["url"], "kitai": t.get("kitai"), "got": got, "status": rec.get("status"),
                     "why": rec.get("why"), "shazam": rec.get("title") and "%s — %s" % (rec.get("subtitle"), rec.get("title")),
                     "hyouka": hyouka})
    judged = [r for r in rows if not r["hyouka"].startswith("対象外")]
    s = {"at": now(), "n": len(rows), "judged": len(judged),
         "seikai": sum(1 for r in judged if r["hyouka"].startswith("正解")),
         "gohantei": sum(1 for r in judged if r["hyouka"].startswith("誤判定")),
         "youkakunin": sum(1 for r in judged if r["hyouka"].startswith("要確認")),
         "miokuri": sum(1 for r in judged if r["hyouka"].startswith("見送り")),
         "hiyouYen": 0, "rows": rows}
    os.makedirs(ST, exist_ok=True)
    io.open(SHIKEN, "w", encoding="utf-8").write(json.dumps(s, ensure_ascii=False, indent=1))
    return s


MACHI = os.path.join(ST, "machi.jsonl")


def run_machi(limit=2):
    """取り込み（nagekomi.add）が置いた待ち列を、心臓の便で少しずつ判定する。
    空きが2GB未満・道具が無い・試験未合格のときは、判定だけ／何もしない（落とさず次の便へ）。"""
    if free_gb() < MIN_FREE_GB:
        return {"ok": True, "skip": "容量不足（空き%.1fGB）" % free_gb()}
    try:
        done = set(json.load(io.open(KEKKA, encoding="utf-8")).keys())
    except Exception:
        done = set()
    todo = []
    try:
        for line in io.open(MACHI, encoding="utf-8"):
            try:
                u = json.loads(line).get("url")
            except Exception:
                continue
            if u and u not in done and u not in todo:
                todo.append(u)
    except OSError:
        return {"ok": True, "skip": "待ちなし"}
    out = []
    for u in todo[:limit]:
        rec = judge(u)
        save(rec)
        rec["apply"] = apply(rec)
        out.append({"url": u, "status": rec.get("status"), "apply": rec["apply"].get("applied")})
    return {"ok": True, "done": out, "left": max(0, len(todo) - limit)}


def self_test():
    W = lambda s, k, off, t="Beat It", a="Michael Jackson": {"start": s, "key": k, "offset": off, "title": t, "subtitle": a}
    ok = True
    ok &= decide([W(0, "1", 30.0), W(10, "1", 40.2)])["status"] == "一致"
    ok &= decide([W(0, "1", 30.0), W(10, "1", 80.0)])["status"] == "保留"          # 位置が飛ぶ＝偶然
    ok &= decide([W(0, "1", 30.0), {"start": 10}])["status"] == "保留"            # 1か所だけ
    ok &= decide([W(0, "1", 30.0), W(10, "1", 40.0), W(20, "2", 5.0), W(30, "2", 15.0)])["status"] == "保留"  # 2曲
    ok &= decide([{"start": 0}, {"start": 10}])["status"] == "保留"
    arts = [{"id": "mj", "name": "Michael Jackson / The Jackson 5", "songs": [{"id": "beat-it", "title": "Beat It"}]},
            {"id": "x", "name": "Harry Styles", "songs": [{"id": "s", "title": "Sign of the Times"}]}]
    ok &= find_song("Beat It (Single Version)", "Michael Jackson", arts)[:2] == ("mj", "beat-it")
    ok &= find_song("Beat It (Sped Up)", "Michael Jackson", arts)[0] is None          # 版違い
    ok &= find_song("Beat It", "Michael Jacksonn", arts)[0] is None                   # 名前違い
    ok &= find_song("Sign of the Times", "NON STYLE", arts)[0] is None                 # 別人事故
    ok &= find_song("Beat It - Remix", "Michael Jackson", arts)[0] is None
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--url", action="append")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--only", action="append")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--machi", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.machi and free_gb() < MIN_FREE_GB:
        print(json.dumps({"ok": True, "skip": "容量不足（空き%.1fGB）" % free_gb()}, ensure_ascii=False))
        return 0
    if a.setup:
        print(json.dumps(setup(), ensure_ascii=False))
        return 0
    if not have_shazamio():
        reexec_in_venv()
        if not have_shazamio():
            print(json.dumps({"ok": False, "why": "shazamio が無い（--setup を先に）"}, ensure_ascii=False))
            return 1
    if not shutil.which("ffmpeg"):
        print(json.dumps({"ok": False, "why": "ffmpeg が無い"}, ensure_ascii=False))
        return 1
    if a.test:
        print(json.dumps(run_test(a.only), ensure_ascii=False, indent=1))
        return 0
    if a.machi:
        print(json.dumps(run_machi(), ensure_ascii=False))
        return 0
    for u in a.url or []:
        rec = judge(u)
        save(rec)
        if a.apply:
            rec["apply"] = apply(rec)
        print(json.dumps({k: rec.get(k) for k in ("url", "status", "why", "title", "subtitle", "page", "apply")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
