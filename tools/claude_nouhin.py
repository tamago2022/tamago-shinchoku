#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claudeの生成物の納品先は、ここ1か所で決める（2026-10-14・たまごさんの決定）。

  納品先（正本）：Googleドライブ「マイドライブ/AI生成物/Claude/<案件>/」＝Claude専用の置き場はここ1か所
  案件フォルダ   ：ANKEN（下）。迷ったら「その他」。動画（棒人間・HowItHolds 等）は「棒人間_Opus」。
  ファイル名     ：頭に必ず日付「YYYY-MM-DD_」（put が自動で付ける）→ 名前順＝新しい順に並ぶ
  一覧           ：「AI生成物/Claude/00_一覧_新しい順.csv」（全ファイル：日付／案件／名前／最新orボツ／ひとこと／リンク）
                   flush のたびに作り直す（2026-10-15・たまごさん「『あれ、どこだっけ？』をなくしたい」）
  使わない置き場 ：Mac本体（~/Documents・デスクトップ）／iCloud Drive

Googleドライブのアプリが使えない間（マウントが Resource deadlock avoided 等で読めない）は、
iMac HDD の「Claude上げ待ち/<案件>/」に積んでおき、心臓が10分おきに flush して、
上げられるようになった時点で自動でドライブへ上げる。上げ終えたものは「Claude上げ済み/」へ移す（控え）。

使い方（Mac上で）：
  python3 tools/claude_nouhin.py put <ファイルかフォルダ> [--anken 棒人間_Opus] [--move] [--sub EP01]
      → HDDの上げ待ちへ写して中身を突き合わせる（--move なら元を消す）。続けて flush を試す。
  python3 tools/claude_nouhin.py flush       # 上げ待ち → ドライブ（心臓から10分おき）
  python3 tools/claude_nouhin.py status      # 状態を表示
  python3 tools/claude_nouhin.py ichiran     # 一覧（CSV）だけ作り直す
  python3 tools/claude_nouhin.py --self-test

守ること：空き容量が30GBを切ったら何もしない。Googleアカウントの接続・設定には触らない。
デスクトップには何も置かない。許可ポップアップが出る操作（osascript等）は使わない。
結果：status/public/claude_nouhin.json
"""
import csv, filecmp, glob, json, os, re, shutil, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

DRIVE_DEST = "AI生成物/Claude"
ANKEN = {
    "詩と音楽_僕は見た、未来を待つ人々を": ["僕は見た", "未来を待つ", "bokumita"],
    "ポッドキャスト神回_日本語音源": ["神回", "ソロプレナー", "podcast", "ポッドキャスト", "lex fridman"],
    "棒人間_Opus": ["棒人間", "howitholds", "ep01", "ep02", "pilot", "パイロット", "shizukesa", "静けさ",
                   "nightowls", "キャラ版", "型見比べ", "ブラックスタート", "男の子", "顔の案", "頭身"],
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
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")
# 一覧の「最新orボツ」「ひとこと」。ファイル名に含まれる語で決める（上から先に当たったもの）。
KUBUN = [
    ("_写し", "★最新", "同じ中身の写し（上の行と同じ動画）"),
    ("検品シート", "ボツ", "静けさパイロットの検品シート"),
    ("男の子版", "★最新", "EP01 本編・男の子が出る版（9分56秒）"),
    ("顔の案", "★最新", "顔の案の比較"),
    ("サムネ案", "★最新", "EP01 サムネイル案"),
    ("ブラックスタート", "★最新", "EP01 ブラックスタート"),
    ("静けさ", "ボツ", "和紙・ミニマム系の静けさパイロット"),
    ("shizukesa", "ボツ", "和紙・ミニマム系の静けさパイロット"),
    ("キャラ", "ボツ", "キャラの土台（2〜2.5頭身）の試作"),
    ("nightowls", "ボツ", "キャラの土台（2〜2.5頭身）の試作"),
]


def hiduke_name(name, path=None):
    """名前の頭に日付が無ければ、元ファイルの更新日を付ける（名前順＝日付順にするため）。"""
    if DATE_RE.match(name):
        return name
    t = os.path.getmtime(path) if path and os.path.exists(path) else time.time()
    return time.strftime("%Y-%m-%d_", time.localtime(t)) + name


def kubun_of(name):
    low = name.lower()
    for k, kb, hk in KUBUN:
        if k.lower() in low:
            return kb, hk
    return "", ""
OUT = os.path.join(REPO, "status", "public", "claude_nouhin.json")


def free_gb(p="/"):
    s = os.statvfs(p)
    return s.f_bavail * s.f_frsize / 1e9


def anken_of(text):
    t = (text or "").lower()
    for name, kws in ANKEN.items():
        if any(k.lower() in t for k in kws):
            return name
    return SONOTA


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
    """ドライブに書けるか。固まることがあるので必ず別プロセス＋時間切れで見る。"""
    for r in drive_roots():
        rc, out = _run(["ls", r], 20)
        if rc != 0:
            return None, "読めない: " + out.strip()[:120]
        base = os.path.join(r, DRIVE_DEST)
        rc, out = _run(["mkdir", "-p"] + [os.path.join(base, a) for a in ANKEN], 30)
        if rc != 0:
            return None, "フォルダを作れない: " + out.strip()[:120]
        return base, "ok"
    return None, "ドライブのフォルダが無い（アプリ未起動）"


def _same(a, b):
    if os.path.isdir(a):
        for dp, _, fs in os.walk(a):
            for f in fs:
                if f.startswith("."):
                    continue
                p = os.path.join(dp, f)
                q = os.path.join(b, os.path.relpath(p, a))
                if not (os.path.isfile(q) and filecmp.cmp(p, q, shallow=False)):
                    return False
        return True
    return os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)


def put(src, anken=None, sub=None, move=False):
    src = os.path.abspath(src)
    if free_gb() < MIN_FREE_GB:
        return {"ok": False, "why": "空き容量30GB未満のため止めた"}
    if not os.path.isdir(HDD_ROOT):
        return {"ok": False, "why": "iMac HDD がつながっていない（本体には溜めない）"}
    anken = anken if anken in ANKEN else anken_of(src)
    d = os.path.join(QUEUE, anken, *( [sub] if sub else [] ))
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, hiduke_name(os.path.basename(src.rstrip("/")), src))
    if os.path.isdir(src):
        # HDDはexFAT：属性の写しで Errno 22 になるので中身だけ写す
        shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copyfile)
    else:
        shutil.copyfile(src, dst)
    if not _same(src, dst):
        return {"ok": False, "why": "写した中身が一致しない", "dst": dst}
    if move:
        shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)
    return {"ok": True, "anken": anken, "dst": dst, "moved": move}


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
                moved.append(r["dst"])
    return moved


def drive_id(p):
    rc, out = _run(["xattr", "-p", "com.google.drivefs.item-id#S", p], 10)
    return out.strip() if rc == 0 else ""


def hiduke_tsukeru(base):
    """ドライブ上の日付なしファイルに日付を付ける（名前を変えるだけ・消さない）。"""
    done = []
    for dp, ds, fs in os.walk(base):
        ds[:] = [d for d in ds if not d.startswith(".")]
        for f in fs:
            if f.startswith(".") or f == ICHIRAN or DATE_RE.match(f):
                continue
            p = os.path.join(dp, f)
            q = os.path.join(dp, hiduke_name(f, p))
            if not os.path.exists(q) and _run(["mv", "-n", p, q], 30)[0] == 0:
                done.append(os.path.relpath(q, base))
    return done


def ichiran(base=None):
    """ドライブの AI生成物/Claude を全部なめて、新しい順の一覧CSVを置く（リンクつき）。"""
    if base is None:
        base, why = drive_alive()
        if not base:
            return {"ok": False, "why": why}
    try:
        hiduke_tsukeru(base)
    except Exception:
        pass
    rows = []
    for dp, ds, fs in os.walk(base):
        ds[:] = [d for d in ds if not d.startswith(".")]
        for f in fs:
            if f.startswith(".") or f == ICHIRAN:
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, base)
            m = DATE_RE.match(f)
            kb, hk = kubun_of(rel)
            i = drive_id(p)
            rows.append({"日付": f[:10] if m else "", "案件": rel.split(os.sep)[0] if os.sep in rel else "",
                         "名前": f, "最新orボツ": kb, "ひとこと": hk,
                         "リンク": ("https://drive.google.com/file/d/%s/view" % i) if i else "",
                         "場所": rel})
    rows.sort(key=lambda r: (r["日付"], r["名前"]), reverse=True)
    cols = ["日付", "案件", "名前", "最新orボツ", "ひとこと", "リンク", "場所"]
    tmp = os.path.join(HDD_ROOT if os.path.isdir(HDD_ROOT) else "/tmp", "." + ICHIRAN)
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    rc, out = _run(["cp", tmp, os.path.join(base, ICHIRAN)], 60)
    os.remove(tmp)
    folders = {"AI生成物/Claude": drive_id(base)}
    for a in ANKEN:
        folders["AI生成物/Claude/" + a] = drive_id(os.path.join(base, a))
    res = {"ok": rc == 0, "count": len(rows), "folders": {k: ("https://drive.google.com/drive/folders/" + v) if v else ""
                                                        for k, v in folders.items()},
           "ichiran": "https://drive.google.com/file/d/%s/view" % drive_id(os.path.join(base, ICHIRAN)), "rows": rows}
    try:
        with open(os.path.join(REPO, "status", "claude_ichiran.json"), "w", encoding="utf-8") as fh:
            json.dump(dict([(k, v) for k, v in res.items() if k != "rows"] + [("at", time.strftime("%F %T"))]), fh,
                      ensure_ascii=False, indent=1)
    except Exception:
        pass
    return res


def flush():
    res = {"at": time.strftime("%F %T"), "uploaded": [], "errors": []}
    try:
        res["swept"] = sweep()
    except Exception as e:
        res["swept_err"] = repr(e)
    if free_gb() < MIN_FREE_GB:
        res["state"] = "空き容量30GB未満のため止めた"
    elif not os.path.isdir(QUEUE):
        res["state"] = "上げ待ちなし（HDD未接続または空）"
    else:
        base, why = drive_alive()
        res["drive"] = why
        if not base:
            res["state"] = "ドライブが使えないので上げ待ちのまま"
        else:
            for rel in queued():
                s = os.path.join(QUEUE, rel)
                t = os.path.join(base, rel)
                rc, out = _run(["mkdir", "-p", os.path.dirname(t)], 30)
                rc, out = _run(["cp", s, t], 900) if rc == 0 else (rc, out)
                if rc == 0 and os.path.getsize(s) == os.path.getsize(t):
                    k = os.path.join(SUMI, rel)
                    os.makedirs(os.path.dirname(k), exist_ok=True)
                    shutil.move(s, k)
                    res["uploaded"].append(rel)
                else:
                    res["errors"].append({"file": rel, "err": out.strip()[:200]})
                    break
            res["state"] = "上げた"
            # 一覧は「上げたとき」か「1時間たったとき」に作り直す
            ij = os.path.join(REPO, "status", "claude_ichiran.json")
            if res["uploaded"] or not os.path.exists(ij) or time.time() - os.path.getmtime(ij) > 3600:
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
    assert anken_of("HowItHolds_EP01_ブラックスタート_540p.mp4") == "棒人間_Opus"
    assert anken_of("pilot_shizukesa_A_ambient_1080p.mp4") == "棒人間_Opus"
    assert hiduke_name("2026-10-11_EP01.mp4") == "2026-10-11_EP01.mp4"
    assert DATE_RE.match(hiduke_name("x.mp4"))
    assert kubun_of("2026-10-11_EP01_ブラックスタート_男の子版.mp4")[0] == "★最新"
    assert kubun_of("2026-10-15_静けさパイロット_v2.mp4")[0] == "ボツ"
    assert anken_of("wae/絵_01.png") == "わえちゃん"
    assert anken_of("なにか.txt") == SONOTA
    assert all(" (" not in os.path.dirname(r) for r in drive_roots())
    print("self-test OK")


def main(a):
    if not a or a[0] == "status":
        print(json.dumps({"free_gb": round(free_gb(), 1), "drive": drive_alive()[1],
                          "queued": queued() if os.path.isdir(QUEUE) else []}, ensure_ascii=False, indent=1))
    elif a[0] == "--self-test":
        self_test()
    elif a[0] == "ichiran":
        r = ichiran()
        r.pop("rows", None)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a[0] == "flush":
        print(json.dumps(flush(), ensure_ascii=False, indent=1))
    elif a[0] == "put":
        kw = {"anken": None, "sub": None, "move": "--move" in a}
        for k in ("anken", "sub"):
            if "--" + k in a:
                kw[k] = a[a.index("--" + k) + 1]
        print(json.dumps(put(a[1], **kw), ensure_ascii=False))
        flush()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
