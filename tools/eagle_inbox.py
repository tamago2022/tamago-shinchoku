#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iPhoneから放り込んだ画像を Eagle に取り込む。

2026-09-03 たまごさん：
  「iPhoneでツイート見てて、いいなと思った画像をスクショ撮って、すかさずここに入れられるのかな？
    そういうスピード感だと助かる」

使い方（たまごさん側の操作）:
  スクショ → 共有シート →「ファイルに保存」→ iCloud Drive の
  「Eagle_取り込み_iPhoneから」フォルダ。以上。

このスクリプトが5分おきに:
  1. そのフォルダの画像を拾う
  2. Eagle の API（localhost:41595）で「iPhoneから」フォルダへ登録し、タグ `_from:iphone` と取り込み日を付ける
  3. 取り込めたものは「取り込み済み」へ移す（＝入れたフォルダは常に空。処理されたか一目で分かる）
  4. 失敗したものは残したまま、理由をログに書く（黙って消さない）

ファイル名で行き先を指定することもできる。例: 「料理#夜食.jpg」→ タグ「夜食」も付く。

2026-09-07 追加（デスクトップ見回り）:
  たまごさんがUnsplash等からDLするとAVIF形式になり、それをEagleへ直接ドラッグすると
  「インポート画面が出たまま」朝まで固まって残る事故が起きた。
  同じことが起きないよう、このスクリプトは毎回デスクトップ直下も見回り、
  avif/webp/heic を先にJPEGへ変換してからEagleへ登録する（元ファイルは削除せず退避）。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

INBOX = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Eagle_取り込み_iPhoneから")
DONE = os.path.join(INBOX, "取り込み済み")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "eagle_inbox.log")
API = "http://localhost:41595"
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".avif", ".svg"}
# 2026-09-07 事故：たまごさんがUnsplashからDLした画像がAVIF形式で
#   デスクトップに溜まり、それをEagleへドラッグしたら「インポート画面が出たまま」
#   止まって朝まで残っていた（Eagleがsipsで変換前の生avifを読めなかったため）。
#   対処＝①iPhone便のEXTSにも .avif を追加 ②デスクトップ直下を定期的に見回り、
#         avif/webp/heic を先回りでJPEGへ変換してEagleへ入れてしまう（DESKTOP_SWEEP）。
DESKTOP = os.path.expanduser("~/Desktop")
DESKTOP_DONE = os.path.join(DESKTOP, "Eagle取り込み済み_変換画像")
DESKTOP_SWEEP_EXTS = {".avif", ".webp", ".heic"}
NEEDS_CONVERT_EXTS = {".heic", ".avif"}


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def api(path, payload=None, timeout=8):
    url = API + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def eagle_alive():
    try:
        api("/api/application/info", None, timeout=3)
        return True
    except Exception:
        return False


def ensure_folder(name):
    """名前のフォルダを探し、無ければ作ってIDを返す"""
    try:
        d = api("/api/folder/list")
        def walk(fs):
            for f in fs or []:
                if (f.get("name") or "") == name:
                    return f.get("id")
                got = walk(f.get("children"))
                if got:
                    return got
            return None
        got = walk(d.get("data"))
        if got:
            return got
    except Exception as e:
        log("フォルダ一覧が取れない: %s" % e)
    try:
        d = api("/api/folder/create", {"folderName": name})
        return (d.get("data") or {}).get("id")
    except Exception as e:
        log("フォルダ作成に失敗: %s" % e)
        return None


def heic_to_jpg(path):
    """HEIC/AVIFはEagleで扱いにくいのでJPGへ。macOS標準のsipsを使う（追加インストール不要）"""
    out = os.path.splitext(path)[0] + ".jpg"
    try:
        subprocess.run(["sips", "-s", "format", "jpeg", path, "--out", out],
                       check=True, capture_output=True, timeout=60)
        return out if os.path.exists(out) else None
    except Exception as e:
        log("画像変換に失敗 %s: %s" % (os.path.basename(path), e))
        return None


def desktop_avif_sweep():
    """デスクトップ直下に転がっている avif/webp/heic を、次にEagleが止まる前に先回りで片付ける。
    元ファイルは削除せず DESKTOP_DONE へ退避するだけ（作り直せないものは消さない方針）。"""
    if not os.path.isdir(DESKTOP):
        return
    try:
        names = [f for f in os.listdir(DESKTOP)
                 if not f.startswith(".") and os.path.isfile(os.path.join(DESKTOP, f))
                 and os.path.splitext(f)[1].lower() in DESKTOP_SWEEP_EXTS]
    except Exception as e:
        log("デスクトップ見回りに失敗: %s" % e)
        return
    if not names:
        return
    if not eagle_alive():
        log("Eagleが起動していないのでデスクトップ見回りを見送り（%d件はそのまま待機）" % len(names))
        return

    os.makedirs(DESKTOP_DONE, exist_ok=True)
    stage_dir = os.path.expanduser("~/Library/Caches/TamagoEagleInbox")
    os.makedirs(stage_dir, exist_ok=True)
    ok = ng = 0
    for f in names:
        src = os.path.join(DESKTOP, f)
        try:
            s1 = os.path.getsize(src)
            time.sleep(0.4)
            if os.path.getsize(src) != s1 or s1 == 0:
                continue  # ダウンロード途中の可能性。次回に回す
        except Exception:
            continue

        conv = heic_to_jpg(src)
        if not conv:
            ng += 1
            continue
        stem = os.path.splitext(os.path.basename(src))[0]
        stage = os.path.join(stage_dir, "%d_%s.jpg" % (int(time.time()), stem))
        try:
            shutil.copyfile(conv, stage)
        except Exception as e:
            ng += 1
            log("デスクトップ画像の控え作成に失敗 %s: %s" % (f, e))
            continue
        payload = {"path": stage, "name": stem,
                   "tags": ["_from:desktop_sweep", "_in:" + time.strftime("%Y-%m-%d")],
                   "annotation": "デスクトップに置かれた%s画像を自動変換して取り込み %s"
                                 % (os.path.splitext(f)[1].lstrip("."), time.strftime("%Y-%m-%d %H:%M"))}
        try:
            api("/api/item/addFromPath", payload)
            time.sleep(3)
            ok += 1
            shutil.move(src, os.path.join(DESKTOP_DONE, f))
            if os.path.exists(conv):
                os.remove(conv)  # sipsが作った変換ファイル本体はstageに控えがあるので消してよい
            log("デスクトップ見回り登録OK %s" % f)
        except Exception as e:
            ng += 1
            log("デスクトップ見回り登録に失敗 %s: %s" % (f, e))

    if ok or ng:
        log("デスクトップ見回り: 成功%d / 失敗%d" % (ok, ng))
        print("デスクトップ見回り: 成功%d / 失敗%d" % (ok, ng))


def main():
    if not os.path.isdir(INBOX):
        os.makedirs(INBOX, exist_ok=True)
        log("取り込みフォルダを作成: %s" % INBOX)
        return 0
    files = [f for f in os.listdir(INBOX)
             if not f.startswith(".") and os.path.isfile(os.path.join(INBOX, f))
             and os.path.splitext(f)[1].lower() in EXTS]
    if not files:
        return 0
    if not eagle_alive():
        log("Eagleが起動していないので見送り（%d件はそのまま待機）" % len(files))
        return 0

    fid = ensure_folder("iPhoneから")
    os.makedirs(DONE, exist_ok=True)
    ok = ng = 0
    for f in files:
        src = os.path.join(INBOX, f)
        # 同期の途中でサイズが変わっているものは次回に回す（壊れた画像を登録しない）
        try:
            s1 = os.path.getsize(src)
            time.sleep(0.4)
            if os.path.getsize(src) != s1 or s1 == 0:
                continue
        except Exception:
            continue

        path = src
        if os.path.splitext(f)[1].lower() in NEEDS_CONVERT_EXTS:
            conv = heic_to_jpg(src)
            if not conv:
                ng += 1
                continue
            path = conv

        stem = os.path.splitext(os.path.basename(path))[0]
        # 2026-09-04 たまごさん「これ『可愛い』フォルダに入れといてくんない？」
        #   → ファイル名に「@フォルダ名」を書けば、そのフォルダへ入る。
        #     書式：「名前#タグ#タグ@フォルダ名」。@が無ければ既定の「iPhoneから」。
        #     フォルダ名は Eagle の既存フォルダを名前で探す（入れ子の子フォルダもたどる）。無ければ作る。
        target_fid, target_name = fid, "iPhoneから"
        if "@" in stem:
            stem, _, fname = stem.partition("@")
            fname = fname.strip()
            if fname:
                got = ensure_folder(fname)
                if got:
                    target_fid, target_name = got, fname
        parts = stem.split("#")
        name = parts[0].strip() or stem
        tags = ["_from:iphone", "_in:" + time.strftime("%Y-%m-%d")] + [t.strip() for t in parts[1:] if t.strip()]
        payload = {"path": os.path.abspath(path), "name": name, "tags": tags,
                   "annotation": "iPhoneから取り込み %s（%s）" % (time.strftime("%Y-%m-%d %H:%M"), target_name)}
        if target_fid:
            payload["folderId"] = target_fid
        # 2026-09-04 事故と対処：
        #   APIは成功を返したのにEagleの画面に「1個の項目はインポートできません」と出て入らなかった。
        #   原因＝addFromPath はEagleが「あとから」そのパスを読みに行く方式なのに、
        #   こちらがAPI成功の直後に元ファイルを「取り込み済み」へ move してしまい、読む前に消えていた。
        #   対処＝①iCloudではないローカルの控えを作り、そのパスを渡す ②控えは消さずに残す
        #        ③元ファイルの移動はEagleが読み終わるだけ待ってから。
        stage_dir = os.path.expanduser("~/Library/Caches/TamagoEagleInbox")
        os.makedirs(stage_dir, exist_ok=True)
        stage = os.path.join(stage_dir, "%d_%s" % (int(time.time()), os.path.basename(path)))
        try:
            shutil.copyfile(path, stage)
        except Exception as e:
            ng += 1
            log("控えの作成に失敗 %s: %s" % (f, e))
            continue
        payload["path"] = stage
        try:
            api("/api/item/addFromPath", payload)
            time.sleep(3)  # Eagleが控えを読み込むまで待つ
            ok += 1
            shutil.move(src, os.path.join(DONE, f))
            if path != src and os.path.exists(path):
                shutil.move(path, os.path.join(DONE, os.path.basename(path)))
            log("登録OK %s → フォルダ「%s」" % (name, target_name))
        except Exception as e:
            ng += 1
            log("登録に失敗 %s: %s" % (f, e))

    # 古い控え（2日以上前）は掃除する。Eagleは取り込み時に自分のライブラリへコピーしているので消して問題ない
    try:
        stage_dir = os.path.expanduser("~/Library/Caches/TamagoEagleInbox")
        now_t = time.time()
        for g in os.listdir(stage_dir):
            gp = os.path.join(stage_dir, g)
            if os.path.isfile(gp) and now_t - os.path.getmtime(gp) > 172800:
                os.remove(gp)
    except Exception:
        pass

    if ok or ng:
        log("取り込み: 成功%d / 失敗%d" % (ok, ng))
        print("取り込み: 成功%d / 失敗%d" % (ok, ng))
    return 0


def main_with_desktop_sweep():
    rc = main()
    try:
        desktop_avif_sweep()
    except Exception as e:
        log("デスクトップ見回りで例外: %s" % e)
    return rc


if __name__ == "__main__":
    sys.exit(main_with_desktop_sweep())
