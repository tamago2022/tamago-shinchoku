#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/aitara_mawasu.py ── 空いたら勝手に回す（順番は1か所）

たまごさん（2026-09-24・原文）:
  「こういうのがあるのに工場が止まってるなんてありえないんだよ。
    仕入れるなり間違いを探すなり、何かしらやっててくださいよ。」
  「何も走ってないっていうのは、クレジットが天井を打つだとか、
    そういう場合以外ないんじゃないかな。常に何かしら回ってないとおかしいよ。」

★キューが空でも止まらない。やることが無いなら自分で拾ってくる。
★止まってよいのは「クレジットが天井」のときだけ。それ以外は全部赤。

━━ 回す順番（ここが正本。他の場所に書かない）━━
  1. 間違い探し   machine   0円  全曲総当たり。URL・空の紹介文・年の矛盾・同名別人・繋ぎのズレ
  2. メイン不在の門 machine  0円  タイトルはあるがメインが無いページを数えて塞ぐ
  3. 仕入れ       ai        課金  定番の棚卸しで「無い」と出たもの。マニアックは後回し
  4. 覆面テスト   genspark  課金  100人。飴玉ゼロ率を追う     ← ★2026-09-24 停止中
  5. コピー直し   ai        課金  水道水コピー・途中で切れている紹介文
  6. 裏取り       ai        課金  出典の無い断定

━━ Gensparkの栓（2026-09-24 たまごさん）━━
  「Genspark、ストップさせようか。急にガーッと減り出したから、
    何をやるとパワーを使うのかちょっと調べる。だから一回ストップで。」
  栓の本体は tools/genspark_nagashi.py の gsk_tomatteru()（status/genspark.stop）。
  ここはその1か所を見るだけ。★止まっていれば genspark の工程を順番から外す。
  ★戻すときは status/genspark.stop を消すだけ。ここは触らなくてよい。

使い方
  python3 tools/aitara_mawasu.py            # 1回まわす（心臓から呼ばれる）
  python3 tools/aitara_mawasu.py --show     # いま何が回せるかを人が読む形で
  python3 tools/aitara_mawasu.py --tsugi    # 次に回す1本だけを返す（JSON）

決まり
  - 0円の工程（machine）は、天井に近くても止めない。
  - 課金する工程（ai）は、天井に近いときは本数を減らさずモデルを落とす。
  - ブラウザを使わない。たまごさんのファイルを消さない・動かさない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

JUNBAN_JSON = os.path.join(ST, "aitara_mawasu.json")
LOG = os.path.join(ST, "aitara_mawasu.jsonl")
NO_LAUNCH = os.path.join(ST, "no_launch.flag")
QUOTA = os.path.join(ST, "quota.json")
QUEUE = os.path.join(ST, "queue.json")

# 天井とみなす線（ここを超えたら課金する工程だけ止める。0円の工程は止めない）
TENJO_PCT = 85.0


# ────────────────────────────────────────────────────────────
# ★順番の正本。ここ以外に順番を書かない。
# ────────────────────────────────────────────────────────────
JUNBAN = [
    {
        "n": 1, "name": "間違い探し", "kind": "machine", "yen": 0,
        "what": "全曲総当たり。URL切れ・空の紹介文・年の矛盾・同名別人・繋ぎのズレ",
        # 2026-09-26（復元便）：ここは長らく `kenpin_gate.py --zenbu` を指していたが、
        #   kenpin_gate.py に --zenbu という引数は存在しない（実行すると argparse が
        #   「unrecognized arguments: --zenbu」で即エラー＝この工程は一度も成功していない）。
        #   間違い探しの本体は tools/machigai_sagashi.py（0円・全曲総当たり）。そちらへ繋ぎ直す。
        "cmd": ["python3", os.path.join(HERE, "machigai_sagashi.py")],
        "needs": [],
    },
    {
        "n": 2, "name": "メイン不在の門", "kind": "machine", "yen": 0,
        "what": "タイトルはあるがメイン（音源・動画）が無いページを数える。0件でなければ赤",
        "cmd": ["python3", os.path.join(HERE, "main_kanmon.py"), "--jissoku"],
        "needs": [],
    },
    {
        "n": 3, "name": "仕入れ", "kind": "ai", "yen": 1,
        "what": "定番の棚卸しで「無い」と出たもの。マニアックは後回し",
        "cmd": None,   # キューへ積む形（下の tsumu() が積む）
        "needs": ["claude"],
    },
    {
        "n": 4, "name": "覆面テスト", "kind": "genspark", "yen": 1,
        "what": "100人。飴玉ゼロ率を追う",
        "cmd": ["python3", os.path.join(HERE, "fukumen_kyaku.py")],
        "needs": ["genspark"],
    },
    {
        "n": 5, "name": "コピー直し", "kind": "ai", "yen": 1,
        "what": "水道水コピー・途中で切れている紹介文",
        "cmd": None,
        "needs": ["claude"],
    },
    {
        "n": 6, "name": "裏取り", "kind": "ai", "yen": 1,
        "what": "出典の無い断定",
        "cmd": None,
        "needs": ["claude"],
    },
]


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _append(path, obj):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ────────────────────────────────────────────────────────────
# 栓を見る
# ────────────────────────────────────────────────────────────
def genspark_tomatteru():
    """★Gensparkの栓。本体は tools/genspark_nagashi.py（status/genspark.stop）の1か所。"""
    try:
        import genspark_nagashi as gn
        return gn.gsk_tomatteru()
    except Exception:
        # 読めなくても、フラグが在れば止まっているとみなす（安全側）
        p = os.path.join(ST, "genspark.stop")
        if os.path.exists(p):
            try:
                return open(p, encoding="utf-8").read().strip() or "止めています"
            except Exception:
                return "止めています"
    return None


def claude_tomatteru():
    """Claudeのログインが切れているか（AIを使う工程が回せない）。"""
    if os.path.exists(NO_LAUNCH):
        try:
            return open(NO_LAUNCH, encoding="utf-8").read().strip()[:200]
        except Exception:
            return "no_launch.flag が立っています"
    return None


def tenjo():
    """クレジットが天井か。★止まってよいのはここだけ。"""
    q = _read_json(QUOTA, {}) or {}
    pct = q.get("allPct")
    if pct is None:
        return None
    if float(pct) >= TENJO_PCT:
        return "クレジット %.0f%%（天井の線 %.0f%%）" % (float(pct), TENJO_PCT)
    return None


# ────────────────────────────────────────────────────────────
# いま回せるものを並べる
# ────────────────────────────────────────────────────────────
def shirabe():
    gsk = genspark_tomatteru()
    cld = claude_tomatteru()
    tj = tenjo()

    mawaseru, hazushita = [], []
    for k in JUNBAN:
        wake = None
        if "genspark" in k["needs"] and gsk:
            wake = "Gensparkを止めているため（%s）" % gsk.split("\n")[0][:60]
        elif "claude" in k["needs"] and cld:
            wake = "Claudeが回せないため（%s）" % cld.split("\n")[0][:60]
        elif k["yen"] and tj:
            wake = "クレジットが天井のため（%s）" % tj
        if wake:
            hazushita.append(dict(k, cmd=None, naze=wake))
        else:
            mawaseru.append(k)

    return {
        "at": now(),
        "gensparkTomatteru": bool(gsk),
        "gensparkNaze": (gsk or "").split("\n")[0] if gsk else None,
        "claudeTomatteru": bool(cld),
        "tenjo": tj,
        "mawaseruN": len(mawaseru),
        "mawaseru": [{"n": k["n"], "name": k["name"], "kind": k["kind"],
                      "yen": k["yen"], "what": k["what"]} for k in mawaseru],
        "hazushitaN": len(hazushita),
        "hazushita": [{"n": k["n"], "name": k["name"], "naze": k["naze"]}
                      for k in hazushita],
        "gensparkNashiDeMawaruN": len([k for k in JUNBAN
                                       if "genspark" not in k["needs"]]),
        "zeroenDeMawaruN": len([k for k in mawaseru if k["yen"] == 0]),
        "aka": len(mawaseru) == 0 and not tj,
        "akaNaze": ("回せる工程が0個なのに、クレジットは天井ではありません。"
                    "止まってよい理由がありません。"
                    if (len(mawaseru) == 0 and not tj) else None),
        "junbanNote": "順番の正本は tools/aitara_mawasu.py の JUNBAN。他の場所に書かない。",
    }


def queue_aiteru():
    """キューに発車待ちが在るか。在るならそちらが先。"""
    q = _read_json(QUEUE, {}) or {}
    items = q.get("items") or []
    machi = [i for i in items
             if (i.get("status") or "") in ("waiting", "ready", "queued")]
    return len(machi) == 0, len(machi)


def tsugi():
    """次に回す1本を返す。回せるものが無ければ None。"""
    s = shirabe()
    for k in JUNBAN:
        if any(m["n"] == k["n"] for m in s["mawaseru"]):
            return k, s
    return None, s


def honmono_ga_deteru():
    """★直近6時間、本物が1本でも出ているか。

    2026-09-24 の事故：キューに204本の発車待ちがあったのに、
    ログイン切れで1本も本物が出ず、2分おきの「空回し」だけが323本走っていた。
    ★キューが満杯でも、本物が0本なら工場は止まっているのと同じ。
      そのときこそ0円の工程を回す。「何も走っていない」を作らない。
    """
    kyou = time.strftime("%Y-%m-%d")
    honmono = 0
    try:
        for f in os.listdir(ST):
            if not (f.startswith("auto-launch-") and f.endswith(".log")):
                continue
            p = os.path.join(ST, f)
            m = os.stat(p).st_mtime
            if time.time() - m > 6 * 3600:
                continue
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    if "空回し" not in fh.read(400):
                        honmono += 1
            except Exception:
                pass
    except Exception:
        pass
    return honmono


def mawasu():
    """1回まわす。

    ★0円の工程を回す条件（どちらかが当てはまれば回す）：
      ① キューが空
      ② キューは在るのに、直近6時間 本物が1本も出ていない（＝実質止まっている）
    ★止まってよいのは「クレジットが天井」のときだけ。
    """
    karappo, machiN = queue_aiteru()
    s = shirabe()
    honmono = honmono_ga_deteru()
    karamawari_dake = (not karappo) and honmono == 0

    _write(JUNBAN_JSON, dict(s, queueMachiN=machiN, queueKarappo=karappo,
                             honmono6h=honmono,
                             karamawariDake=karamawari_dake))

    if not karappo and not karamawari_dake:
        _append(LOG, {"at": now(), "shita": "何もしない",
                      "naze": "キューに発車待ちが %d 本あり、本物も %d 本出ている"
                              % (machiN, honmono)})
        return 0

    naze = ("キューが空" if karappo else
            "★キューに %d 本あるのに、直近6時間 本物が0本（空回しだけ）" % machiN)

    # ★止まらない。0円の工程から拾う。
    yatta = []
    for k in JUNBAN:
        if not any(m["n"] == k["n"] for m in s["mawaseru"]):
            continue
        if k["yen"] != 0 or not k["cmd"]:
            continue
        if not os.path.exists(k["cmd"][1]):
            continue
        try:
            r = subprocess.run(k["cmd"], capture_output=True, text=True,
                               timeout=900, cwd=REPO)
            yatta.append({"n": k["n"], "name": k["name"], "rc": r.returncode,
                          "de": (r.stdout or "")[-400:]})
        except subprocess.TimeoutExpired:
            yatta.append({"n": k["n"], "name": k["name"], "rc": None,
                          "de": "15分で返りませんでした"})
        except Exception as e:
            yatta.append({"n": k["n"], "name": k["name"], "rc": None,
                          "de": "%s: %s" % (type(e).__name__, e)})

    _append(LOG, {"at": now(), "shita": "0円の工程を回した", "naze": naze,
                  "honmono6h": honmono, "yatta": yatta,
                  "gensparkTomatteru": s["gensparkTomatteru"],
                  "aka": s["aka"], "akaNaze": s["akaNaze"]})
    return len(yatta)


def main():
    a = sys.argv[1:]
    if "--tsugi" in a:
        k, s = tsugi()
        print(json.dumps({"tsugi": (k and {"n": k["n"], "name": k["name"]}),
                          "shirabe": s}, ensure_ascii=False, indent=1))
        return 0
    if "--show" in a:
        s = shirabe()
        print("【空いたら回す順番】%s" % s["at"])
        for k in JUNBAN:
            m = next((x for x in s["mawaseru"] if x["n"] == k["n"]), None)
            h = next((x for x in s["hazushita"] if x["n"] == k["n"]), None)
            mark = "○" if m else "×"
            ato = "" if m else "　← %s" % h["naze"]
            print("  %s %d. %-12s [%s・%s] %s%s"
                  % (mark, k["n"], k["name"], k["kind"],
                     "0円" if k["yen"] == 0 else "課金", k["what"], ato))
        print()
        print("回せる %d 個／外した %d 個／Genspark無しで回る工程 %d 個／0円で回る工程 %d 個"
              % (s["mawaseruN"], s["hazushitaN"],
                 s["gensparkNashiDeMawaruN"], s["zeroenDeMawaruN"]))
        if s["aka"]:
            print("★赤：%s" % s["akaNaze"])
        return 0
    n = mawasu()
    print("回した工程：%d 個" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
