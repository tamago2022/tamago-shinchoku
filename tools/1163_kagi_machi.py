#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1163番【鍵が来た瞬間に、たまごさんが何もしなくても棚が動く】

■ なぜ要るか（2026-09-26 実測）
  棚（admin_stock / admin_shelves / admin_shelf_picks）に**書ける道は service_role だけ**。
  これは事故ではなく、74号（supabase/migrations/20260801170000_rls_owner_only_lockdown.sql）で
  たまごさん自身が「私と私が許したAIだけ」と決めた設計そのもの。
  実測でも、Macの中に service_role の鍵は1本も無かった：
    ~/.tamago/supabase_service_role            … 無し
    joy-relief-station/.env.local の
      SUPABASE_SERVICE_ROLE_KEY                … **中身が空（長さ0）**
    joy-relief-station/.env, ~/.tamago/keys/api_keys.env, ~/.tamago/1138-jrs/.env
                                               … PUBLISHABLE（読み取り用）だけ
    supabase CLI / keychain                    … ログインの跡なし
  つまり「service_role を使わずに通る扉」は**今のRLSでは存在しない**。
  （anon/authenticated には INSERT のポリシーが1本も作られていない）

■ この係がやること
  鍵が ~/.tamago/supabase_service_role に置かれた**その周回で**、
  たまごさんがコマンドを1つも打たずに、たまっている分を全部棚へ入れる。
    1. 本当に書けるか実測する（200が返っても行数0なら「書けない」と判定する）
    2. tools/1152_ireru.py        … スープ棚の新設＋名指しの5本
    3. tools/nagekomi_shelf.py --force … 投げ込み箱に溜まっている残り
    4. tools/nagekomi_list.py    … 受付一覧を作り直す（箱の「入った記録」の元データ）
  結果は status/1163/kagi_machi.json に残す。**鍵の値は1バイトも書かない。**

■ 二度走りしない
  鍵ファイルの mtime を status/1163/.kagi_stamp に控える。同じ鍵で一度通ったら走らない。
  （鍵を貼り直したら mtime が変わるので、もう一度だけ走る）
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
OUT_DIR = os.path.join(STATUS, "1163")
OUT = os.path.join(OUT_DIR, "kagi_machi.json")
STAMP = os.path.join(OUT_DIR, ".kagi_stamp")
KEY_PATH = os.path.expanduser("~/.tamago/supabase_service_role")
LOG = os.path.join(OUT_DIR, "kagi_machi.log")


def note(msg):
    os.makedirs(OUT_DIR, exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), msg))


def run(cmd, sec=600):
    p = subprocess.run([sys.executable] + cmd, cwd=REPO, capture_output=True,
                       text=True, timeout=sec)
    return p.returncode, (p.stdout or "")[-4000:], (p.stderr or "")[-2000:]


def kakeru():
    """★書けるかを実測する。200でも書けた行が0なら False。鍵の値は外へ出さない。"""
    sys.path.insert(0, HERE)
    import tana                      # noqa: E402
    import urllib.parse              # noqa: E402
    diag = []
    url, key, keyname, where = tana.keys(diag)
    if not url:
        return False, "Supabaseの入口が見つからない"
    st, rows = tana._req(url, key, "/rest/v1/admin_stock?select=id,whisper&limit=1")
    if not rows:
        return False, "admin_stock が1行も読めない（HTTP %s）" % st
    tid, w = rows[0]["id"], rows[0]["whisper"]
    st2, back = tana._req(
        url, key, "/rest/v1/admin_stock?id=eq.%s" % urllib.parse.quote(tid, safe=""),
        method="PATCH", body={"whisper": w}, prefer="return=representation")
    if not back:
        return False, "まだ書けない（HTTP %s・書けた行は0＝RLSが黙って弾いている）" % st2
    return True, ""


def main():
    if not os.path.exists(KEY_PATH):
        return
    try:
        mt = str(int(os.path.getmtime(KEY_PATH)))
    except OSError:
        return
    try:
        if io.open(STAMP, encoding="utf-8").read().strip() == mt:
            return                    # この鍵ではもう通した
    except OSError:
        pass

    os.makedirs(OUT_DIR, exist_ok=True)
    res = {"at": time.strftime("%F %T"), "steps": []}
    ok, why = kakeru()
    res["kakeru"] = ok
    res["why"] = why
    if not ok:
        note("鍵は在るがまだ書けない：%s" % why)
        io.open(OUT, "w", encoding="utf-8").write(
            json.dumps(res, ensure_ascii=False, indent=1))
        return                        # stampは進めない（正しい鍵が来たら次の周回で通す）

    for cmd, name in ((["tools/1152_ireru.py"], "名指しの分を棚へ"),
                      (["tools/nagekomi_shelf.py", "--force"], "箱に溜まっている分を棚へ"),
                      (["tools/nagekomi_list.py"], "受付一覧を作り直す")):
        try:
            rc, out, err = run(cmd)
        except Exception as e:
            rc, out, err = 1, "", repr(e)
        res["steps"].append({"name": name, "cmd": " ".join(cmd), "rc": rc,
                             "tail": out[-1500:], "err": err[-600:]})
        note("%s rc=%s" % (name, rc))

    io.open(OUT, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    io.open(STAMP, "w", encoding="utf-8").write(mt)
    note("通した")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:      # 心臓を止めない
        note("落ちた：%r" % (e,))
