#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/modoseru.py ── 戻せる台帳（工場の安全装置）

たまごさん（2026-09-24・原文）:
  「間違えて変えてしまうものもあるかもしれないけれど、すぐ戻れるようにしといてね。」
  「時々、間違って伝わった状態でそのままになっちゃうときがあるから。」

★今日それが起きかけた。
  「トップのフッターの棚一覧リンクを消す」を、こちらが「棚一覧ページを消す」と取り違えた。
  たまごさんが「危ない危ない」と止めた。★止められなければ、棚一覧が消えていた。
  ★だから「止められなくても戻せる」形にする。

━━ 決まり ━━
  ① 本番に出したものは、1つずつ戻せる。「いつ・何を・どのコミットで」を1行残す。
  ② 戻すのは1コマンド。★たまごさんに手順を教えない。「あれを戻して」でこちらが戻す。
  ③ 戻したことも記録に残す。
  ④ ★自分が変えた範囲だけ戻す。ついでに他を巻き戻さない。
  ⑤ ★消す・畳む・非表示にする の3つは、戻せることを確かめてからでないと実行しない。
  ⑥ ★本番に出したら、その日のうちに「何を変えたか」を1行出す。黙って変えて放置しない。

━━ 戻せる期間 ━━
  ★90日。それ以前のものも git に残っていれば戻せる（gitは消えない）。
  ★git に載っていない変更は「戻せない」＝赤。載せてから出す。

使い方
  python3 tools/modoseru.py --kiroku --nani "こちらもどうぞの上段を撤去" \
      --doko joy-relief-station --file src/routes/index.tsx --kiken futsuu
      本番に出したものを1件記録する（コミットは自動で拾う）。

  python3 tools/modoseru.py --ichiran            # 戻せるもの一覧（新しい順）
  python3 tools/modoseru.py --kyou               # 今日 何を変えたかの1行ずつ
  python3 tools/modoseru.py --shiraberu          # ★全部が本当に戻せるかを実測する
  python3 tools/modoseru.py --modosu <id>        # ★1コマンドで戻す
  python3 tools/modoseru.py --kiken-check --file <path>
      ★消す・畳む・非表示 の前に通す。戻せることが確かめられなければ止める。

決まり
  - たまごさんのファイルを消さない。戻すのは git 経由だけ（必ず写しを残す）。
  - ブラウザを使わない。課金しない。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

DAICHO = os.path.join(ST, "modoseru_daicho.jsonl")      # 出したもの（追記のみ）
MODOSHITA = os.path.join(ST, "modoshita.jsonl")         # 戻したもの（追記のみ）
SHIRABE = os.path.join(ST, "modoseru.json")             # 実測の結果
HIKAE = os.path.join(ST, "modoseru_hikae")              # 戻す前の写し

MOCHIBA = {
    "joy-relief-station": "/Users/mac/Desktop/joy-relief-station",
    "tamago-shinchoku": REPO,
}

KIGEN_NICHI = 90          # ★戻せる期間
KIKEN_GO = ("kesu", "tatamu", "hihyouji")   # 消す・畳む・非表示


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _yomu(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _git(root, *args, timeout=60):
    try:
        r = subprocess.run(["git"] + list(args), cwd=root, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return 1, "", "%s: %s" % (type(e).__name__, e)


# ────────────────────────────────────────────────────────────
# ★記録する
# ────────────────────────────────────────────────────────────
def kiroku(nani, doko="joy-relief-station", files=None, kiken="futsuu", memo=""):
    root = MOCHIBA.get(doko, doko)
    files = files or []
    rc, head, _ = _git(root, "rev-parse", "HEAD")
    commit = head if rc == 0 else None
    rc2, dirty, _ = _git(root, "status", "--porcelain")
    yogoreta = [ln[3:] for ln in (dirty or "").split("\n") if ln.strip()]

    # ★このファイルがコミットに載っているか＝戻せるか
    noseteru = []
    for f in files:
        noseteru.append(f in yogoreta)

    rec = {
        "id": "M%s" % time.strftime("%y%m%d%H%M%S"),
        "at": now(),
        "nani": nani,
        "doko": doko,
        "root": root,
        "files": files,
        "commit": commit,
        "kiken": kiken,
        "memo": memo,
        # ★コミットに載っていない＝gitに残っていない＝戻せない
        "commitNiNotteru": bool(commit) and not any(noseteru),
        "mikomitFiles": [f for f, d in zip(files, noseteru) if d],
    }
    _append(DAICHO, rec)
    return rec


# ────────────────────────────────────────────────────────────
# ★本当に戻せるかを実測する
# ────────────────────────────────────────────────────────────
def _anzen_ten(root):
    """★戻れる点（いまの状態をまるごと閉じ込めた印）。無ければ作る。

    git stash create / commit-tree で作るので、
    ★作業ツリーにも index にも一切触らない。
    """
    rc, out, _ = _git(root, "tag", "-l", "anzen-*")
    tags = [t for t in (out or "").split("\n") if t.strip()]
    if tags:
        return sorted(tags)[-1]
    # 無ければ作る（本物のindexを汚さないよう、別のindexで）
    idx = os.path.join("/tmp", "anzen_idx_%d" % int(time.time()))
    env = dict(os.environ, GIT_INDEX_FILE=idx)
    try:
        subprocess.run(["git", "read-tree", "HEAD"], cwd=root, env=env,
                       capture_output=True, timeout=120)
        subprocess.run(["git", "add", "-A"], cwd=root, env=env,
                       capture_output=True, timeout=300)
        tree = subprocess.run(["git", "write-tree"], cwd=root, env=env,
                              capture_output=True, text=True, timeout=120).stdout.strip()
        if not tree:
            return None
        c = subprocess.run(["git", "commit-tree", tree, "-p", "HEAD", "-m",
                            "anzen: 戻れる点（%s）" % now()],
                           cwd=root, capture_output=True, text=True, timeout=120).stdout.strip()
        if not c:
            return None
        tag = "anzen-%s" % time.strftime("%Y%m%d-%H%M%S")
        subprocess.run(["git", "tag", "-f", tag, c], cwd=root,
                       capture_output=True, timeout=60)
        return tag
    except Exception:
        return None
    finally:
        try:
            os.remove(idx)
        except Exception:
            pass


def shiraberu(naosu=True):
    """★戻せるかを実測する。naosu=True なら、戻せないものを戻せる形にする。

    「戻せる」＝ 前に戻す先（commit）と、いまを閉じ込めた点（anzen）の両方がある。
      ・前に戻す先が無い → 何も戻せない ＝ 赤
      ・いまを閉じ込めた点が無い → 戻したあと元に戻れない ＝ 赤
    ★未コミットのファイルは、anzen の印を作れば「いまの状態」が git に固定される。
      これで「戻せません」が消える。
    """
    recs = _yomu(DAICHO)
    modoseru, modosenai, naoshita = [], [], []
    anzen_cache = {}
    for r in recs:
        root = r.get("root") or MOCHIBA.get(r.get("doko"), "")
        wake = None
        if not root or not os.path.isdir(root):
            wake = "置き場が見つかりません（%s）" % root
        elif not r.get("commit"):
            wake = "戻す先のコミットが記録されていません"
        else:
            rc, _, _ = _git(root, "cat-file", "-e", r["commit"] + "^{commit}")
            if rc != 0:
                wake = "戻す先のコミットが git に見つかりません（%s）" % r["commit"][:8]

        if not wake and r.get("mikomitFiles"):
            # ★未コミット。戻れる点があれば「いま」も git に固定されている＝戻せる。
            if root not in anzen_cache:
                anzen_cache[root] = _anzen_ten(root) if naosu else None
            tag = r.get("anzenTag") or anzen_cache.get(root)
            if tag:
                r = dict(r, anzenTag=tag,
                         chuui=("このファイルには今日以外の未コミットの変更も混ざっています。"
                                "ファイル単位で戻すと、そちらも一緒に戻ります。"
                                "これから出すものは1件1コミットにするので、次からは混ざりません。"))
                naoshita.append(r)
            else:
                wake = ("git に載っていません（未コミット）：%s"
                        % "／".join(r["mikomitFiles"][:3]))

        if wake:
            modosenai.append(dict(r, naze=wake))
        else:
            modoseru.append(r)

    out = {
        "at": now(),
        "zenN": len(recs),
        "modoseruN": len(modoseru),
        "modosenaiN": len(modosenai),
        "aka": len(modosenai) > 0,
        "kigenNichi": KIGEN_NICHI,
        "modosenai": modosenai[:100],
        "anzenTen": sorted(set(v for v in anzen_cache.values() if v)),
        "naoshitaN": len(naoshita),
        "naoshita": naoshita[:100],
        "note": ("modosenaiN が1件でもあれば赤。"
                 "『戻せません』を無くすのがこの台帳の目的。"
                 "未コミットのものは anzen の印（戻れる点）で いまの状態を git に固定した。"
                 "これで戻したあとも元に戻れる。"),
    }
    tmp = SHIRABE + ".tmp"
    os.makedirs(ST, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SHIRABE)
    return out


# ────────────────────────────────────────────────────────────
# ★1コマンドで戻す（自分が変えた範囲だけ）
# ────────────────────────────────────────────────────────────
def modosu(mid, honki=True):
    recs = _yomu(DAICHO)
    r = next((x for x in recs if x.get("id") == mid), None)
    if not r:
        return {"ok": False, "naze": "その記録がありません：%s" % mid}
    root = r.get("root") or MOCHIBA.get(r.get("doko"), "")
    if not os.path.isdir(root):
        return {"ok": False, "naze": "置き場が見つかりません：%s" % root}
    files = r.get("files") or []
    if not files:
        return {"ok": False, "naze": "どのファイルを戻すかが記録されていません"}

    # ★戻す前に必ず写しを取る（戻したものを戻せるように）
    hikae_dir = os.path.join(HIKAE, "%s-%s" % (mid, time.strftime("%Y%m%d%H%M%S")))
    os.makedirs(hikae_dir, exist_ok=True)
    for f in files:
        src = os.path.join(root, f)
        if os.path.exists(src):
            dst = os.path.join(hikae_dir, f.replace("/", "__"))
            shutil.copy2(src, dst)

    # ★そのコミットの中身に、そのファイルだけ戻す。他は触らない。
    naoshita, shippai = [], []
    for f in files:
        rc, _, err = _git(root, "checkout", r["commit"], "--", f)
        (naoshita if rc == 0 else shippai).append(f if rc == 0 else "%s（%s）" % (f, err[:80]))

    rec = {"at": now(), "modoshitaId": mid, "nani": r.get("nani"),
           "commit": r.get("commit"), "naoshita": naoshita,
           "shippai": shippai, "hikae": hikae_dir}
    _append(MODOSHITA, rec)
    return {"ok": not shippai, "modoshita": rec}


# ────────────────────────────────────────────────────────────
# ★消す・畳む・非表示 の前に必ず通す
# ────────────────────────────────────────────────────────────
def kiken_check(path, doko="joy-relief-station", go="kesu"):
    """戻せることを確かめてからでないと、消す・畳む・非表示にしない。"""
    root = MOCHIBA.get(doko, doko)
    if not os.path.isdir(root):
        return False, "置き場が見つかりません：%s" % root
    rc, out, _ = _git(root, "log", "-1", "--pretty=%H", "--", path)
    if rc != 0 or not out:
        return False, ("★止めます：%s は git に1回も載っていません。"
                       "消したら戻せません。先にコミットしてください。" % path)
    rc2, dirty, _ = _git(root, "status", "--porcelain", "--", path)
    if dirty.strip():
        return False, ("★止めます：%s に未コミットの変更があります。"
                       "この状態で消すと、その分は戻せません。" % path)
    return True, "戻せます（最後に載ったコミット %s）。%s を実行してよい。" % (out[:8], go)


def main():
    a = sys.argv[1:]

    def arg(name, default=None):
        return a[a.index(name) + 1] if name in a else default

    if "--kiroku" in a:
        files = [x for x in a if x.endswith((".tsx", ".ts", ".css", ".json", ".md"))]
        f1 = arg("--file")
        if f1 and f1 not in files:
            files.append(f1)
        r = kiroku(arg("--nani", "（何を変えたかが書かれていません）"),
                   doko=arg("--doko", "joy-relief-station"),
                   files=files, kiken=arg("--kiken", "futsuu"),
                   memo=arg("--memo", ""))
        print("記録しました：%s　%s" % (r["id"], r["nani"]))
        if r["mikomitFiles"]:
            print("★赤：git に載っていません → %s" % "／".join(r["mikomitFiles"]))
        return 0

    if "--shiraberu" in a:
        o = shiraberu()
        print("戻せる %d 件／★戻せない %d 件（全 %d 件・戻せる期間 %d日）"
              % (o["modoseruN"], o["modosenaiN"], o["zenN"], o["kigenNichi"]))
        for m in o["modosenai"][:20]:
            print("  ★%s %s … %s" % (m.get("id"), m.get("nani"), m.get("naze")))
        return 1 if o["aka"] else 0

    if "--ichiran" in a:
        for r in reversed(_yomu(DAICHO)):
            print("%s  %s  [%s]  %s" % (r.get("id"), r.get("at"),
                                        r.get("kiken"), r.get("nani")))
        return 0

    if "--kyou" in a:
        kyou = time.strftime("%Y-%m-%d")
        n = 0
        print("【今日 本番に出したもと戻し方】%s" % kyou)
        for r in _yomu(DAICHO):
            if (r.get("at") or "").startswith(kyou):
                n += 1
                print("  ・%s　→ 戻すなら「%s を戻して」の一言で戻ります"
                      % (r.get("nani"), r.get("nani")))
        if n == 0:
            print("  （台帳に記録されたものはありません）")
        return 0

    if "--modosu" in a:
        o = modosu(arg("--modosu"))
        print(json.dumps(o, ensure_ascii=False, indent=1))
        return 0 if o.get("ok") else 1

    if "--kiken-check" in a:
        ok, wake = kiken_check(arg("--file", ""), doko=arg("--doko", "joy-relief-station"),
                               go=arg("--go", "kesu"))
        print(("通す：" if ok else "★止める：") + wake)
        return 0 if ok else 1

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
