#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: 課金なし（ファイルをコピーするだけ・AIも外部APIも呼ばない）
"""Obsidianへの受け口（2026-11-24・GH1230）

━━ なぜ ━━
  Grokボット（や他のAI）が git push するだけで Obsidian の『00 inbox』にノートが入るようにする。
  店主OK済み（2026-11-21「Obsidian 格納までが今回のテスト。一発でいけるのか。方法は任せる」）。
  Grok自身はVaultに書けない（ドライブのtamago_brainはVault→ドライブの一方向の写しで戻せない。
  shared_brain_syncはResource deadlockで停止中。Vaultに書けるのはMac上のClaude Codeだけ）。

━━ 流れ ━━
  ① Grokが tamago2022/tamago-shinchoku の vault_okuri/ 直下に .md を置いてpush。
  ② Macの心臓（heartbeat.sh・1時間おき。machine_status_push.sh の git pull で取り込み済み）が
     このスクリプトを呼び、vault_okuri/*.md を見て Vault『00 inbox/』へ一方向コピーする。
  ③ 追加のみ：同名ファイルがVaultにあればコピーしない（os.O_EXCL＝新規作成のみ・上書き不可）。
     Vault側は消さない・書き換えない。Vault→repoの逆流もしない。repo側の元ファイルも消さない。
  ④ 処理済みの記録はファイル名＋中身のハッシュで台帳（status/vault_okuri_daicho.json）に残し、
     同じものは二度コピーしない。1日の処理件数には上限（DAILY_CAP）がある。
  ⑤ 結果は status/public/vault_okuri.json に出す（GitHub PagesでGrokも読める）。
  ⑥ status/vault_okuri_off というファイルがあれば何もしない（無効化スイッチ）。

  Vaultの関所（tools/vault_kanmon.py）のPreToolUseフックはClaude CodeのWrite/Edit呼び出しを見るもので、
  heartbeat.sh経由で動くこのPythonプロセスには掛からない。genzaichi_matome.py等と同じ
  「許可された書き手」としてvault_kanmon.pyのdocstringに明記済み。

  実装はこのリポジトリ既存の tools/genzaichi_matome.py（Vaultへの安全な書き込みパターン）・
  tools/vault_kanmon.py・tools/vault_yomu.py をお手本にそのまま踏襲した
  （VAULT定数の置き方／JSON台帳の読み書き／一時ファイル→os.replaceのアトミック書き込み／
   iCloud dataless対策のbrctl download／--self-testの逆テスト構成／
   心臓(heartbeat.sh)のevery_hoursへの相乗り方法。1184号の関所票：status/original_kinshi/hyo-1795522577.json）。

━━ 使い方 ━━
    python3 tools/vault_okuri_tenso.py             # 心臓用（1回処理して結果を書く）
    python3 tools/vault_okuri_tenso.py --self-test # 逆テスト
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
INBOX = os.path.join(VAULT, "00 inbox")
OKURI = os.path.join(REPO, "vault_okuri")
DAICHO = os.path.join(REPO, "status", "vault_okuri_daicho.json")
KEKKA = os.path.join(REPO, "status", "public", "vault_okuri.json")
OFF_FLAG = os.path.join(REPO, "status", "vault_okuri_off")
MAX_BYTES = 1024 * 1024
DAILY_CAP = 50  # 1日に新規コピーしてよい件数（仕様「1日の上限を守る」）
# フォルダ自体の説明書・制御ファイルはGrokのノートではないので対象外（実測事故：README.mdを誤って
# Vaultへコピーしてしまい、2026-11-24に発見・追加した除外リスト）
EXCLUDE_NAMES = {"readme.md", "_kekka.md"}


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp.%d" % os.getpid()
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _sha256(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _ensure_dir_reachable(d):
    """iCloudでdatalessのとき対象フォルダを叩き起こす"""
    if os.path.isdir(d):
        return True
    try:
        subprocess.run(["brctl", "download", d], capture_output=True, timeout=30)
        time.sleep(2)
    except Exception:
        pass
    return os.path.isdir(d)


def run(okuri_dir=None, inbox_dir=None, daicho_path=None, kekka_path=None):
    okuri_dir = okuri_dir or OKURI
    inbox_dir = inbox_dir or INBOX
    daicho_path = daicho_path or DAICHO
    kekka_path = kekka_path or KEKKA
    today = time.strftime("%Y-%m-%d")

    if os.path.exists(OFF_FLAG):
        out = {"at": time.strftime("%F %T"), "off": True, "results": []}
        _save(kekka_path, out)
        return out

    daicho = _load(daicho_path, {})
    day = daicho.get("_day", {})
    if day.get("date") != today:
        day = {"date": today, "copied": 0}

    if not os.path.isdir(okuri_dir):
        out = {"at": time.strftime("%F %T"), "off": False, "results": [], "note": "vault_okuri/ が無い"}
        _save(kekka_path, out)
        return out
    if not _ensure_dir_reachable(inbox_dir):
        out = {"at": time.strftime("%F %T"), "off": False, "results": [], "note": "00 inbox が読めない（iCloud）"}
        _save(kekka_path, out)
        return out

    results = []
    names = sorted(f for f in os.listdir(okuri_dir) if f.lower().endswith(".md"))
    for name in names:
        if name.lower() in EXCLUDE_NAMES:
            continue  # フォルダの説明書そのものはコピー対象外
        src = os.path.join(okuri_dir, name)
        if not os.path.isfile(src):
            continue  # サブフォルダ・それ以外は無視
        try:
            size = os.path.getsize(src)
        except OSError:
            continue
        if size > MAX_BYTES:
            results.append({"name": name, "status": "skipped_too_big", "bytes": size})
            continue
        try:
            h = _sha256(src)
        except Exception as e:
            results.append({"name": name, "status": "failed", "error": str(e)})
            continue
        rec = daicho.get(name)
        if rec and rec.get("hash") == h:
            results.append({"name": name, "status": rec.get("status", "done"), "hash": h, "cached": True})
            continue
        dest = os.path.join(inbox_dir, name)
        if os.path.exists(dest):
            daicho[name] = {"hash": h, "status": "skipped_exists", "at": time.strftime("%F %T")}
            results.append({"name": name, "status": "skipped_exists", "hash": h})
            continue
        if day["copied"] >= DAILY_CAP:
            results.append({"name": name, "status": "skipped_daily_cap", "hash": h})
            continue
        try:
            with io.open(src, "rb") as rf:
                data = rf.read()
            fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "wb") as wf:
                wf.write(data)
            daicho[name] = {"hash": h, "status": "copied", "at": time.strftime("%F %T")}
            day["copied"] += 1
            results.append({"name": name, "status": "copied", "hash": h})
        except FileExistsError:
            daicho[name] = {"hash": h, "status": "skipped_exists", "at": time.strftime("%F %T")}
            results.append({"name": name, "status": "skipped_exists", "hash": h})
        except Exception as e:
            results.append({"name": name, "status": "failed", "error": str(e)})

    daicho["_day"] = day
    _save(daicho_path, daicho)
    out = {
        "at": time.strftime("%F %T"),
        "off": False,
        "inbox": "00 inbox",
        "results": results,
        "counts": {
            "copied": sum(1 for r in results if r["status"] == "copied"),
            "skipped_exists": sum(1 for r in results if r["status"] == "skipped_exists"),
            "skipped_too_big": sum(1 for r in results if r["status"] == "skipped_too_big"),
            "skipped_daily_cap": sum(1 for r in results if r["status"] == "skipped_daily_cap"),
            "cached": sum(1 for r in results if r.get("cached")),
            "failed": sum(1 for r in results if r["status"] == "failed"),
        },
        "daily_cap": DAILY_CAP,
        "daily_copied_so_far": day["copied"],
    }
    _save(kekka_path, out)
    return out


def self_test():
    tmp = tempfile.mkdtemp(prefix="vault_okuri_test_")
    try:
        okuri = os.path.join(tmp, "okuri")
        inbox = os.path.join(tmp, "inbox")
        daicho_p = os.path.join(tmp, "daicho.json")
        kekka_p = os.path.join(tmp, "kekka.json")
        os.makedirs(okuri)
        os.makedirs(inbox)

        # サブフォルダ・非.md・巨大ファイルは無視される
        os.makedirs(os.path.join(okuri, "sub"))
        io.open(os.path.join(okuri, "sub", "ignored.md"), "w", encoding="utf-8").write("x")
        io.open(os.path.join(okuri, "note.txt"), "w", encoding="utf-8").write("x")
        io.open(os.path.join(okuri, "big.md"), "w", encoding="utf-8").write("x" * (MAX_BYTES + 1))
        io.open(os.path.join(okuri, "a.md"), "w", encoding="utf-8").write("テストノートA")
        io.open(os.path.join(okuri, "README.md"), "w", encoding="utf-8").write("フォルダの説明書（コピー対象外）")

        out1 = run(okuri, inbox, daicho_p, kekka_p)
        copied1 = os.path.isfile(os.path.join(inbox, "a.md"))
        ignored_ok = (not os.path.isfile(os.path.join(inbox, "note.txt")) and
                      not os.path.isfile(os.path.join(inbox, "ignored.md")) and
                      not os.path.isfile(os.path.join(inbox, "big.md")) and
                      not os.path.isfile(os.path.join(inbox, "README.md")))

        # 2回目：同じファイル→キャッシュ扱いで再コピーせず、中身も変わらない
        before = io.open(os.path.join(inbox, "a.md"), encoding="utf-8").read()
        out2 = run(okuri, inbox, daicho_p, kekka_p)
        after = io.open(os.path.join(inbox, "a.md"), encoding="utf-8").read()
        no_dup = (before == after == "テストノートA")
        cached_ok = any(r.get("cached") for r in out2["results"] if r["name"] == "a.md")

        # 3回目：Vault側に先に同名の別内容がある→上書きしない
        io.open(os.path.join(okuri, "b.md"), "w", encoding="utf-8").write("新しい方")
        io.open(os.path.join(inbox, "b.md"), "w", encoding="utf-8").write("既にある手書きノート")
        out3 = run(okuri, inbox, daicho_p, kekka_p)
        kept = io.open(os.path.join(inbox, "b.md"), encoding="utf-8").read() == "既にある手書きノート"
        skip_ok = any(r["name"] == "b.md" and r["status"] == "skipped_exists" for r in out3["results"])

        # 4回目：off フラグがあれば何もしない
        off_flag = os.path.join(tmp, "off_flag")
        io.open(off_flag, "w").write("x")
        global OFF_FLAG
        old_off = OFF_FLAG
        OFF_FLAG = off_flag
        io.open(os.path.join(okuri, "c.md"), "w", encoding="utf-8").write("止まっているはず")
        out4 = run(okuri, inbox, daicho_p, kekka_p)
        OFF_FLAG = old_off
        off_ok = out4.get("off") is True and not os.path.isfile(os.path.join(inbox, "c.md"))

        # 5回目：1日上限チェック（DAILY_CAPを一時的に0にして新規コピーが止まることを確認）
        global DAILY_CAP
        old_cap = DAILY_CAP
        DAILY_CAP = 0
        io.open(os.path.join(okuri, "d.md"), "w", encoding="utf-8").write("上限で見送られるはず")
        out5 = run(okuri, inbox, daicho_p, kekka_p)
        DAILY_CAP = old_cap
        cap_ok = (not os.path.isfile(os.path.join(inbox, "d.md"))) and \
            any(r["name"] == "d.md" and r["status"] == "skipped_daily_cap" for r in out5["results"])

        ok = copied1 and ignored_ok and no_dup and cached_ok and kept and skip_ok and off_ok and cap_ok
        print("逆テスト：%s（1回目コピー=%s／無視ルール=%s／2回目重複なし=%s／キャッシュ扱い=%s／"
              "既存上書きなし=%s／見送り記録=%s／OFFフラグ=%s／日次上限=%s）"
              % ("合格" if ok else "不合格", copied1, ignored_ok, no_dup, cached_ok, kept, skip_ok, off_ok, cap_ok))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print(json.dumps(run(), ensure_ascii=False, indent=1))
