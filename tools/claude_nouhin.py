#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claudeの生成物の納品先は、ここ1か所で決める（2026-10-14決定・2026-10-15たまごさんの置き場ルール）。

  納品先（正本）：Googleドライブ「マイドライブ/AI生成物/Claude/<案件>/」＝Claude専用の置き場はここ1か所
  案件フォルダ   ：ANKEN（下）。迷ったら「その他」。動画（棒人間・HowItHolds・パイロット・キャラ試作）は「棒人間」。
                   HowItHolds は棒人間プロジェクトの一部＝HowItHolds 名のフォルダは作らない。
  フォルダは最小限：案件フォルダの下に小分けを作らない（あれば中身を案件フォルダへ移して空にする）。
                   空フォルダは作らない・見つけたら片付ける（中身があるものは消さない）。
  ファイル名     ：「日付_★最新_種類_中身.拡張子」例「2026-10-15_★最新_動画_EP01男の子_音軽い版_540p.mp4」
                   種類＝動画／静止画／音声／文書（拡張子で自動）。古い版は★を外す（put --saishin で上げると、
                   同じフォルダの同じ中身名（種類の次の語）から★を外す）。
  一覧           ：「AI生成物/Claude/00_一覧_新しい順.csv」（★最新を上にまとめ、その下を新しい順。リンク付き）
  知らせ         ：ドライブに上がった1件ごとに Dispatch へ1行「何を｜ドライブのURL」（status/dispatch_outbox.jsonl）
  使わない置き場 ：Mac本体（~/Documents・デスクトップ）／iCloud Drive

Googleドライブのアプリが使えない間は、iMac HDD の「Claude上げ待ち/<案件>/」に積み、心臓が10分おきに flush して
上げる。上げ終えたものは「Claude上げ済み/」へ移す（控え）。

使い方（Mac上で）：
  python3 tools/claude_nouhin.py put <ファイル> [--anken 棒人間] [--saishin] [--move]
  python3 tools/claude_nouhin.py flush       # 上げ待ち → ドライブ → 知らせ → 整理・一覧（心臓から10分おき）
  python3 tools/claude_nouhin.py ichiran     # 整理（名前・小分け・空フォルダ）と一覧の作り直し
  python3 tools/claude_nouhin.py status
  python3 tools/claude_nouhin.py --self-test

守ること：空き容量が30GBを切ったら何もしない。Googleアカウントの接続・設定には触らない。ファイルは消さない。
デスクトップには何も置かない。許可ポップアップが出る操作（osascript等）は使わない。
結果：status/public/claude_nouhin.json（URLは status/claude_ichiran.json＝公開しない）
"""
import csv, filecmp, glob, json, os, re, shutil, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

DRIVE_DEST = "AI生成物/Claude"
ANKEN = {
    "詩と音楽_僕は見た、未来を待つ人々を": ["僕は見た", "未来を待つ", "bokumita"],
    "ポッドキャスト神回_日本語音源": ["神回", "ソロプレナー", "podcast", "ポッドキャスト", "lex fridman"],
    "棒人間": ["棒人間", "howitholds", "ep01", "ep02", "pilot", "パイロット", "shizukesa", "静けさ",
             "nightowls", "キャラ版", "キャラの土台", "型見比べ", "ブラックスタート", "男の子", "顔の案", "頭身"],
    "地球観察日記_第2作": ["地球観察日記", "montage de voyage", "chikyu2", "奇妙なお祭り"],
    "わえちゃん": ["わえ", "wae"],
    "その他": [],
}
SONOTA = "その他"
HDD_ROOT = "/Volumes/iMac HDD/Mac標準置き場"
QUEUE = os.path.join(HDD_ROOT, "Claude上げ待ち")
SUMI = os.path.join(HDD_ROOT, "Claude上げ済み")
MIN_FREE_GB = 30
ICHIRAN = "00_一覧_新しい順.csv"
OUT = os.path.join(REPO, "status", "public", "claude_nouhin.json")
ICHIRAN_JSON = os.path.join(REPO, "status", "claude_ichiran.json")
TSUUCHI_MACHI = os.path.join(REPO, "status", "claude_nouhin_tsuuchi_machi.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
STAR = "★最新"
SHURUI = {"動画": (".mp4", ".mov", ".webm", ".m4v"),
          "静止画": (".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic"),
          "音声": (".mp3", ".m4a", ".wav", ".aac", ".flac"),
          "文書": (".txt", ".md", ".pdf", ".csv", ".docx", ".html")}
# 一覧の「ひとこと」。名前に含まれる語で決める（上から先に当たったもの）。
HITOKOTO = [
    ("_写し", "上の行と同じ中身の写し"),
    ("検品シート", "静けさパイロットの検品シート"),
    ("音軽い版", "EP01 ブラックスタート・男の子版の音を軽くした版"),
    ("EP01男の子", "EP01 ブラックスタート・男の子が出る版（9分56秒）"),
    ("サムネ案", "EP01 サムネイル案"),
    ("顔の案", "顔の案の比較"),
    ("静けさ", "和紙・ミニマム系の静けさパイロット（ボツ）"),
    ("キャラの土台", "キャラの土台（2〜2.5頭身）の試作（ボツ）"),
]


def free_gb(p="/"):
    s = os.statvfs(p)
    return s.f_bavail * s.f_frsize / 1e9


def anken_of(text):
    t = (text or "").lower()
    for name, kws in ANKEN.items():
        if any(k.lower() in t for k in kws):
            return name
    return SONOTA


def shurui_of(name):
    ext = os.path.splitext(name)[1].lower()
    for k, exts in SHURUI.items():
        if ext in exts:
            return k
    return "文書"


def seikei_name(name, path=None, saishin=None):
    """「日付_[★最新_]種類_中身.ext」にそろえる。saishin=None なら今の★をそのまま、True/False で付け外し。"""
    m = DATE_RE.match(name)
    if m:
        d, rest = m.group(1), name[m.end():]
    else:
        t = os.path.getmtime(path) if path and os.path.exists(path) else time.time()
        d, rest = time.strftime("%Y-%m-%d", time.localtime(t)), name
    star = rest.startswith(STAR + "_")
    if star:
        rest = rest[len(STAR) + 1:]
    sh = shurui_of(name)
    for k in SHURUI:
        if rest.startswith(k + "_"):
            rest = rest[len(k) + 1:]
            break
    if saishin is not None:
        star = bool(saishin)
    return "_".join([d] + ([STAR] if star else []) + [sh, rest])


def nakami_key(name):
    """★の付け外しで「同じもの」とみなす鍵＝種類の次の語（例：EP01男の子）。"""
    n = seikei_name(name)
    parts = n.split("_")
    i = 2 + (1 if parts[1] == STAR else 0)
    return parts[i] if len(parts) > i else ""


def hitokoto_of(name):
    for k, hk in HITOKOTO:
        if k.lower() in name.lower():
            return hk
    return ""


def drive_roots():
    rs = glob.glob(HOME + "/Library/CloudStorage/GoogleDrive-*/マイドライブ") + \
         glob.glob(HOME + "/Library/CloudStorage/GoogleDrive-*/My Drive")
    # 「GoogleDrive-…(2026-10-13 14:58)」のような取り残しの古いフォルダは使わない（同期されない）
    return [r for r in rs if " (" not in os.path.dirname(r)]


def _run(cmd, timeout):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 1, repr(e)


def drive_alive():
    """ドライブに書けるか。固まることがあるので必ず別プロセス＋時間切れで見る。空の案件フォルダは作らない。"""
    for r in drive_roots():
        rc, out = _run(["ls", r], 20)
        if rc != 0:
            return None, "読めない: " + out.strip()[:120]
        base = os.path.join(r, DRIVE_DEST)
        rc, out = _run(["mkdir", "-p", base], 30)
        if rc != 0:
            return None, "フォルダを作れない: " + out.strip()[:120]
        return base, "ok"
    return None, "ドライブのフォルダが無い（アプリ未起動）"


def drive_id(p):
    rc, out = _run(["xattr", "-p", "com.google.drivefs.item-id#S", p], 10)
    return out.strip() if rc == 0 else ""


def drive_url(p):
    i = drive_id(p)
    if not i:
        return ""
    return ("https://drive.google.com/drive/folders/%s" if os.path.isdir(p) else
            "https://drive.google.com/file/d/%s/view") % i


def _same(a, b):
    return os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)


def put(src, anken=None, sub=None, move=False, saishin=None):
    """上げ待ちへ写す。sub（小分け）は受け付けるが使わない（フォルダは最小限）。フォルダを渡したら中のファイルを1件ずつ。"""
    src = os.path.abspath(src)
    if free_gb() < MIN_FREE_GB:
        return {"ok": False, "why": "空き容量30GB未満のため止めた"}
    if not os.path.isdir(HDD_ROOT):
        return {"ok": False, "why": "iMac HDD がつながっていない（本体には溜めない）"}
    anken = anken if anken in ANKEN else anken_of(src)
    files = [src] if os.path.isfile(src) else sorted(
        os.path.join(dp, f) for dp, _, fs in os.walk(src) for f in fs if not f.startswith("."))
    d = os.path.join(QUEUE, anken)
    os.makedirs(d, exist_ok=True)
    out = []
    for s in files:
        dst = os.path.join(d, seikei_name(os.path.basename(s), s, saishin))
        shutil.copyfile(s, dst)
        if not _same(s, dst):
            return {"ok": False, "why": "写した中身が一致しない", "dst": dst}
        out.append(dst)
    if move:
        shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)
    return {"ok": True, "anken": anken, "dst": out, "moved": move}


def queued():
    out = []
    for dp, _, fs in os.walk(QUEUE):
        for f in fs:
            if not f.startswith("."):
                out.append(os.path.relpath(os.path.join(dp, f), QUEUE))
    return sorted(out)


MEDIA = (".mp4", ".mov", ".mp3", ".m4a", ".wav", ".png", ".jpg", ".jpeg", ".pdf")
SWEEP = [HOME + "/Documents/AI作業"]   # 工場が完成品を直に置いてしまう本体側の置き場


def sweep():
    """本体(~/Documents/AI作業 直下)に置かれた完成品を、30分たったら上げ待ちへ移す（本体に溜めない）。"""
    moved = []
    if not os.path.isdir(HDD_ROOT) or free_gb() < MIN_FREE_GB:
        return moved
    for d in SWEEP:
        for f in (os.listdir(d) if os.path.isdir(d) else []):
            p = os.path.join(d, f)
            if os.path.islink(p) or not os.path.isfile(p) or not f.lower().endswith(MEDIA):
                continue
            if time.time() - os.path.getmtime(p) < 1800:
                continue
            r = put(p, move=True)
            if r.get("ok"):
                moved += r["dst"]
    return moved


# ---- ドライブ上の整理（名前・小分け・空フォルダ・★） ----

def _mv(p, q):
    return not os.path.exists(q) and _run(["mv", "-n", p, q], 60)[0] == 0


def hoshi_hazusu(folder, keep):
    """keep と同じ中身名の、ほかのファイルから★を外す。"""
    key = nakami_key(keep)
    for f in os.listdir(folder):
        if f == keep or f.startswith(".") or not key:
            continue
        if STAR in f and nakami_key(f) == key:
            _mv(os.path.join(folder, f), os.path.join(folder, seikei_name(f, saishin=False)))


def seiri(base):
    """①案件フォルダより下の小分けの中身を案件フォルダへ移す ②名前をそろえる ③空フォルダを片付ける（AI生成物の中）。"""
    log = []
    for a in sorted(os.listdir(base)):
        top = os.path.join(base, a)
        if a.startswith(".") or not os.path.isdir(top):
            continue
        for dp, ds, fs in os.walk(top):
            ds[:] = [x for x in ds if not x.startswith(".")]
            for f in fs:
                if f.startswith(".") or f.endswith((".gdoc", ".gsheet", ".gslides")):
                    continue
                p = os.path.join(dp, f)
                q = os.path.join(top, seikei_name(f, p))
                if p != q and _mv(p, q):
                    log.append(os.path.relpath(q, base))
    root = os.path.dirname(base)   # AI生成物
    for dp, ds, fs in sorted(os.walk(root, topdown=False), key=lambda x: -len(x[0])):
        if dp == root or dp == base:
            continue
        try:
            if not [x for x in os.listdir(dp) if x != ".DS_Store"]:
                if os.path.exists(os.path.join(dp, ".DS_Store")):
                    os.remove(os.path.join(dp, ".DS_Store"))
                os.rmdir(dp)
                log.append("空フォルダを片付けた: " + os.path.relpath(dp, root))
        except OSError:
            pass
    return log


def ichiran(base=None):
    """整理してから、★最新を上・その下を新しい順にした一覧CSV（リンク付き）を置く。"""
    if base is None:
        base, why = drive_alive()
        if not base:
            return {"ok": False, "why": why}
    log = seiri(base)
    rows = []
    for a in sorted(os.listdir(base)):
        top = os.path.join(base, a)
        if a.startswith(".") or not os.path.isdir(top):
            continue
        for f in os.listdir(top):
            if f.startswith(".") or not os.path.isfile(os.path.join(top, f)):
                continue
            m = DATE_RE.match(f)
            rows.append({"日付": m.group(1) if m else "", "最新": STAR if STAR in f else "",
                         "種類": shurui_of(f), "案件": a, "名前": f, "ひとこと": hitokoto_of(f),
                         "リンク": drive_url(os.path.join(top, f))})
    rows.sort(key=lambda r: (r["日付"], r["名前"]), reverse=True)
    rows.sort(key=lambda r: r["最新"] == "")          # ★最新を上にまとめる（中は新しい順のまま）
    cols = ["最新", "日付", "種類", "案件", "名前", "ひとこと", "リンク"]
    tmp = os.path.join(HDD_ROOT if os.path.isdir(HDD_ROOT) else "/tmp", "." + ICHIRAN)
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    rc, _ = _run(["cp", tmp, os.path.join(base, ICHIRAN)], 60)
    os.remove(tmp)
    folders = {"AI生成物/Claude": drive_url(base)}
    for a in sorted(os.listdir(base)):
        if os.path.isdir(os.path.join(base, a)) and not a.startswith("."):
            folders["AI生成物/Claude/" + a] = drive_url(os.path.join(base, a))
    res = {"ok": rc == 0, "count": len(rows), "folders": folders,
           "ichiran": drive_url(os.path.join(base, ICHIRAN)), "seiri": log}
    try:
        with open(ICHIRAN_JSON, "w", encoding="utf-8") as fh:
            json.dump(dict(list(res.items()) + [("at", time.strftime("%F %T"))]), fh, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return res


# ---- 上げた1件ごとに Dispatch へ1行 ----

def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def tsuuchi(base, new=()):
    """上げたファイルのURLが取れたら Dispatch へ「何を｜URL」を1行。取れるまで待ち、24時間でURLなしで出す。"""
    machi = _load(TSUUCHI_MACHI, []) + [{"rel": r, "at": time.time()} for r in new]
    rest, sent = [], []
    for m in machi:
        p = os.path.join(base, m["rel"])
        url = drive_url(p) if os.path.exists(p) else ""
        if url or time.time() - m["at"] > 86400:
            line = {"at": time.strftime("%F %T"), "from": "claude_nouhin", "type": "drive_nouhin",
                    "what": "ドライブに上げた：%s｜%s" % (m["rel"], url or "URL未取得（ドライブの同期待ち）"),
                    "url": url}
            with open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
            sent.append(m["rel"])
        else:
            rest.append(m)
    with open(TSUUCHI_MACHI, "w", encoding="utf-8") as f:
        json.dump(rest, f, ensure_ascii=False, indent=1)
    return sent


def flush():
    res = {"at": time.strftime("%F %T"), "uploaded": [], "errors": []}
    try:
        res["swept"] = sweep()
    except Exception as e:
        res["swept_err"] = repr(e)
    base = None
    if free_gb() < MIN_FREE_GB:
        res["state"] = "空き容量30GB未満のため止めた"
    else:
        base, why = drive_alive()
        res["drive"] = why
        if not base:
            res["state"] = "ドライブが使えないので上げ待ちのまま"
        elif os.path.isdir(QUEUE):
            for rel in queued():
                s = os.path.join(QUEUE, rel)
                t = os.path.join(base, rel)
                rc, out = _run(["mkdir", "-p", os.path.dirname(t)], 30)
                rc, out = _run(["cp", s, t], 900) if rc == 0 else (rc, out)
                if rc == 0 and os.path.getsize(s) == os.path.getsize(t):
                    if STAR in os.path.basename(t):
                        hoshi_hazusu(os.path.dirname(t), os.path.basename(t))
                    k = os.path.join(SUMI, rel)
                    os.makedirs(os.path.dirname(k), exist_ok=True)
                    shutil.move(s, k)
                    res["uploaded"].append(rel)
                else:
                    res["errors"].append({"file": rel, "err": out.strip()[:200]})
                    break
            res["state"] = "上げた"
    if base:
        try:
            res["tsuuchi"] = tsuuchi(base, res["uploaded"])
        except Exception as e:
            res["tsuuchi_err"] = repr(e)
        if res["uploaded"] or not os.path.exists(ICHIRAN_JSON) or time.time() - os.path.getmtime(ICHIRAN_JSON) > 3600:
            try:
                r = ichiran(base)
                res["ichiran"] = {"ok": r["ok"], "count": r["count"]}
            except Exception as e:
                res["ichiran_err"] = repr(e)
    res["queued"] = queued() if os.path.isdir(QUEUE) else []
    res["queued_count"] = len(res["queued"])
    res["drive_dest"] = "マイドライブ/" + DRIVE_DEST + "/<案件>"
    res["anken"] = list(ANKEN)
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return res


def self_test():
    assert anken_of("/x/2026-10-14_僕は見た、未来を待つ人々を_音楽と朗読.mp3").startswith("詩と音楽")
    assert anken_of("ピーター・レベルズ（Lex Fridman 440）神回") == "ポッドキャスト神回_日本語音源"
    assert anken_of("HowItHolds_EP01_ブラックスタート_540p.mp4") == "棒人間"
    assert anken_of("pilot_shizukesa_A_ambient_1080p.mp4") == "棒人間"
    assert anken_of("wae/絵_01.png") == "わえちゃん"
    assert anken_of("なにか.txt") == SONOTA
    assert seikei_name("2026-10-11_EP01男の子_軽い版.mp4") == "2026-10-11_動画_EP01男の子_軽い版.mp4"
    assert seikei_name("2026-10-11_EP01男の子_軽い版.mp4", saishin=True) == "2026-10-11_★最新_動画_EP01男の子_軽い版.mp4"
    assert seikei_name("2026-10-11_★最新_動画_EP01男の子.mp4", saishin=False) == "2026-10-11_動画_EP01男の子.mp4"
    assert seikei_name("2026-10-11_★最新_動画_EP01男の子.mp4") == "2026-10-11_★最新_動画_EP01男の子.mp4"
    assert seikei_name("2026-10-14_01_machi.png") == "2026-10-14_静止画_01_machi.png"
    assert DATE_RE.match(seikei_name("x.m4a")) and "_音声_" in seikei_name("x.m4a")
    assert nakami_key("2026-10-11_★最新_動画_EP01男の子_1080p.mp4") == "EP01男の子"
    assert nakami_key("2026-10-12_動画_EP01男の子_540p.mp4") == "EP01男の子"
    assert all(" (" not in os.path.dirname(r) for r in drive_roots())
    print("self-test OK")


def main(a):
    if not a or a[0] == "status":
        print(json.dumps({"free_gb": round(free_gb(), 1), "drive": drive_alive()[1],
                          "queued": queued() if os.path.isdir(QUEUE) else []}, ensure_ascii=False, indent=1))
    elif a[0] == "--self-test":
        self_test()
    elif a[0] == "ichiran":
        print(json.dumps(ichiran(), ensure_ascii=False, indent=1))
    elif a[0] == "flush":
        print(json.dumps(flush(), ensure_ascii=False, indent=1))
    elif a[0] == "put":
        kw = {"anken": None, "sub": None, "move": "--move" in a, "saishin": True if "--saishin" in a else None}
        for k in ("anken", "sub"):
            if "--" + k in a:
                kw[k] = a[a.index("--" + k) + 1]
        print(json.dumps(put(a[1], **kw), ensure_ascii=False))
        flush()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
