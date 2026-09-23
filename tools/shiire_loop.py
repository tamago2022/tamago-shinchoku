#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1044番：仕入れを止めずに回し続ける自前の口。

たまごさん（2026-09-24）:
  「大量仕入れまたやりたいんだけど。ひたすら仕入れは続けてほしいな。」
  「★列に積まない。自前の口が毎日走る形。」

■ なぜこの形か（2026-09-24 実測）
  サンドボックスから musicbrainz / last.fm / wikipedia / deezer / itunes へ
  **1つも出られない**（全部 Tunnel connection failed: 403）。通るのは github.com と pypi だけ。
  `tools/shuhen_horu.py` はこの403で落ち続けていた＝**走った96回・取れた0回**の原因。
  証拠：status/shiire_kouho/otyken.json の identifyProblem。

  だから仕入れを2つに割る。**回線が要るのは前半だけ。**
    ① 素材集め（回線が要る） …… Jules（Googleの回線）が status/shiire_raw/ を書く
    ② 候補づくり（回線が要らない）… ここ。tools/_1026_kouho_write.py を呼ぶだけ

■ この口がやること（毎日1回）
  1. shiire_raw にあって shiire_kouho に無い slug を全部②に通す
  2. 積み残しが SAIKO_NOKORI を切ったら、①をJulesへ投げ直す（tools/nageru.py）
  3. 前後の件数と「それはありませんね率」を数えて _run.json に書き残す

■ ★やらないこと
  ・棚（coverGuide.ts）に入れない。書き先は status/shiire_kouho/ だけ。採否はたまごさん。
  ・同定が通らない組の曲を引かない（_1026_kouho_write.py が拒む。ここでは上書きしない）。
  ・お金を使わない。外へ出るのは nageru.py に投げる1回だけ。

  使い方:
    python3 tools/shiire_loop.py          # 1回まわす
    python3 tools/shiire_loop.py --dry    # 数えるだけ（書かない・投げない）
"""
import glob
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RAW = os.path.join(REPO, "status", "shiire_raw")
KOUHO = os.path.join(REPO, "status", "shiire_kouho")
RUN = os.path.join(KOUHO, "_run.json")
TODO = os.path.join(REPO, "status", "1044_shiire_todo.txt")
LOG = os.path.join(REPO, "status", "shiire_loop.log")

# 積み残しがこれを切ったら、Julesへ素材集めを投げ直す。
SAIKO_NOKORI = 10
# 1回でJulesに渡す名前の数。多すぎるとPRが重くなって返ってこない。
HITOTABI = 30


def r_at():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _slugs(d):
    out = set()
    for p in glob.glob(os.path.join(d, "*.json")):
        b = os.path.basename(p)[:-5]
        if not b.startswith("_"):
            out.add(b)
    return out


def kazoeru():
    """候補が今いくつあるか。★数えるだけ。ここで書かない。"""
    tot = files = 0
    for p in glob.glob(os.path.join(KOUHO, "*.json")):
        if os.path.basename(p).startswith("_"):
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        tot += len(d.get("candidates") or [])
        files += 1
    return tot, files


def nai_rate():
    """「それはありませんね率」。取れなければ (None, None) を返す。**推測で埋めない。**"""
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "fes_meibo.py")],
                       capture_output=True, text=True, timeout=180)
        d = json.load(io.open(
            os.path.join(REPO, "status", "fes_meibo", "_coverage.json"),
            encoding="utf-8"))
        f = (d.get("festivals") or [{}])[0]
        return f.get("naiRate"), f.get("naiRateWithKouho")
    except Exception:
        return None, None


def hakobu(slugs):
    """素材 → 候補。回線を1回も使わない。"""
    if not slugs:
        return 0, []
    p = subprocess.run(
        [sys.executable, os.path.join(HERE, "_1026_kouho_write.py")] + sorted(slugs),
        capture_output=True, text=True, timeout=900)
    ok, kotowari = 0, []
    for line in (p.stdout or "").splitlines():
        if "→ status/shiire_kouho/" in line:
            ok += 1
        elif line.startswith("★") or "★" in line[:40]:
            kotowari.append(line.strip())
    return ok, kotowari


def nageru_jules(names):
    """素材集めをJulesへ投げ直す。★投げるだけ。返事はgithub_watchが拾う。"""
    if not names:
        return "投げる名前が無い"
    body = io.open(os.path.join(REPO, "status", "1044_jules_shiire.md"),
                   encoding="utf-8").read()
    body += "\n\n## 今回の名前（%d組）\n\n" % len(names) + "\n".join(names) + "\n"
    tmp = os.path.join(REPO, "status", "_1044_jules_body.md")
    io.open(tmp, "w", encoding="utf-8").write(body)
    try:
        p = subprocess.run(
            [sys.executable, os.path.join(HERE, "nageru.py"), "jules",
             "仕入れの素材集め（status/shiire_raw/ だけ書く・棚は触らない）",
             "--body-file", tmp],
            capture_output=True, text=True, timeout=300)
        return (p.stdout or p.stderr or "").strip()[-400:]
    except Exception as e:
        return "投げられなかった：%s" % e


def main():
    dry = "--dry" in sys.argv
    mae_n, mae_f = kazoeru()
    mae_r, mae_rk = nai_rate()

    # ★同定が通らずに断った組は、何度通しても同じ理由で断られる。
    #   （例：「IO」＝ブラジルのIO と カナダの i.o が並んで1組に絞れない）
    #   毎回それを積み残しに数えると、口が永久に「まだ残っている」と思い込んで
    #   次の素材集めを投げなくなる。だから **断った理由ごと控えに残して外す。**
    #   ★消すのではない。裏が取れれば戻せるように、理由を持たせて置いておく。
    KOTOWARI = os.path.join(KOUHO, "_kotowari.json")
    try:
        sumi = json.load(io.open(KOTOWARI, encoding="utf-8"))
    except Exception:
        sumi = {}
    nokori = sorted(_slugs(RAW) - _slugs(KOUHO) - set(sumi))
    tsuketa, kotowari = (0, []) if dry else hakobu(nokori)
    if not dry:
        for line in kotowari:
            sl = line.split()[0]
            sumi[sl] = {"at": r_at(), "why": line[len(sl):].strip()[:300]}
        io.open(KOTOWARI, "w", encoding="utf-8").write(
            json.dumps(sumi, ensure_ascii=False, indent=1))

    ato_n, ato_f = kazoeru()
    ato_r, ato_rk = nai_rate()

    # まだ素材すら無い名前
    machi = []
    if os.path.exists(TODO):
        have = _slugs(RAW) | _slugs(KOUHO)
        for n in io.open(TODO, encoding="utf-8").read().splitlines():
            n = n.strip()
            if n and n.lower().replace(" ", "-") not in have:
                machi.append(n)

    nage = ""
    if not dry and len(nokori) - tsuketa < SAIKO_NOKORI and machi:
        nage = nageru_jules(machi[:HITOTABI])

    r = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "mae": {"kouho": mae_n, "hon": mae_f, "naiRate": mae_r,
                 "naiRateWithKouho": mae_rk},
         "ato": {"kouho": ato_n, "hon": ato_f, "naiRate": ato_r,
                 "naiRateWithKouho": ato_rk},
         "tsuketa": tsuketa, "sozaiNokori": len(nokori) - tsuketa,
         "sozaiMachi": len(machi),
         "kotowari": kotowari, "jules": nage, "dry": dry}

    print("候補 %d件→%d件（+%d）／ 本数 %d→%d" %
          (mae_n, ato_n, ato_n - mae_n, mae_f, ato_f))
    if ato_rk is not None:
        print("それはありませんね率 %s%% ／ 候補まで含めた率 %s%% → %s%%"
              % (ato_r, mae_rk, ato_rk))
    else:
        print("★率が取れなかった（fes_meibo が動かない）。埋めずに空で残す。")
    print("素材の積み残し %d組 ／ まだ素材も無い %d組" % (len(nokori) - tsuketa, len(machi)))
    if kotowari:
        print("★同定が通らず断ったもの %d組（推測で埋めていない）：" % len(kotowari))
        for k in kotowari[:12]:
            print("   " + k[:150])
    if nage:
        print("Julesへ投げた：" + nage.splitlines()[0][:120] if nage else "")

    if not dry:
        io.open(LOG, "a", encoding="utf-8").write(
            json.dumps(r, ensure_ascii=False) + "\n")
        try:
            d = json.load(io.open(RUN, encoding="utf-8"))
        except Exception:
            d = {"runs": 0, "candidates": 0, "history": []}
        d["runs"] = d.get("runs", 0) + 1
        d["candidates"] = ato_n
        d.setdefault("history", []).append(
            {"at": r["at"], "dug": len(nokori), "added": ato_n - mae_n,
             "by": "shiire_loop"})
        d["history"] = d["history"][-50:]
        io.open(RUN, "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
