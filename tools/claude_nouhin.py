#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claudeの生成物の納品先は、ここ1か所で決める（2026-10-14・たまごさんの決定）。

  納品先（正本）：Googleドライブ「マイドライブ/AI生成物/Claude/<案件>/」
  案件フォルダ   ：ANKEN（下）。迷ったら「その他」。
  使わない置き場 ：Mac本体（~/Documents・デスクトップ）／iCloud Drive

Googleドライブのアプリが使えない間（マウントが Resource deadlock avoided 等で読めない）は、
iMac HDD の「Claude上げ待ち/<案件>/」に積んでおき、心臓が10分おきに flush して、
上げられるようになった時点で自動でドライブへ上げる。上げ終えたものは「Claude上げ済み/」へ移す（控え）。

使い方（Mac上で）：
  python3 tools/claude_nouhin.py put <ファイルかフォルダ> [--anken HowItHolds] [--move] [--sub EP01]
      → HDDの上げ待ちへ写して中身を突き合わせる（--move なら元を消す）。続けて flush を試す。
  python3 tools/claude_nouhin.py flush       # 上げ待ち → ドライブ（心臓から10分おき）
  python3 tools/claude_nouhin.py status      # 状態を表示
  python3 tools/claude_nouhin.py --self-test

守ること：空き容量が30GBを切ったら何もしない。Googleアカウントの接続・設定には触らない。
デスクトップには何も置かない。許可ポップアップが出る操作（osascript等）は使わない。
結果：status/public/claude_nouhin.json
"""
import filecmp, glob, json, os, shutil, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

DRIVE_DEST = "AI生成物/Claude"
ANKEN = {
    "詩と音楽_僕は見た、未来を待つ人々を": ["僕は見た", "未来を待つ", "bokumita"],
    "ポッドキャスト神回_日本語音源": ["神回", "ソロプレナー", "podcast", "ポッドキャスト", "lex fridman"],
    "HowItHolds": ["howitholds", "ep01", "ep02", "pilot", "パイロット", "nightowls", "キャラ版", "型見比べ", "ブラックスタート"],
    "わえちゃん": ["わえ", "wae"],
    "その他": [],
}
SONOTA = "その他"
HDD_ROOT = "/Volumes/iMac HDD/Mac標準置き場"
QUEUE = os.path.join(HDD_ROOT, "Claude上げ待ち")
SUMI = os.path.join(HDD_ROOT, "Claude上げ済み")
MIN_FREE_GB = 30
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
    dst = os.path.join(d, os.path.basename(src.rstrip("/")))
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
    assert anken_of("HowItHolds_EP01_ブラックスタート_540p.mp4") == "HowItHolds"
    assert anken_of("pilot_shizukesa_A_ambient_1080p.mp4") == "HowItHolds"
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
