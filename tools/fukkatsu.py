#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/fukkatsu.py ── 復活係。**1分おきに「本物が何本走っているか」を数えて、0本の時間を記録する。**

たまごさん（2026-09-26）:
  「復帰する仕組みも作ってよ。『落ちました』じゃなくて、復活させてよ。止まるのが一番最悪。」
  「クロマティは本当に止まんなかったよ、バンバンタスクをさばいてたから。」

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★この係が「作らない」もの（すでに在るので絶対に二重実装しない）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  目標本数を実測から決める ……… tools/inochi.py（status/launch_cap.json を書く。
                                 落ちた率 status/ochita.jsonl 込みで既に効いている）
  発車0本の検知と蹴り直し ……… tools/launch_watchdog.py（心臓から30秒おき）
  固まった便を順番待ちへ戻す … tools/1142_fukkyuu.py（stuck→waiting・冪等）
  キューが空でも仕事を拾う ……… tools/aitara_mawasu.py（JUNBAN が順番の正本）
  次の1本を着火する …………… tools/auto_launcher.py

  ★この係はそれらを「呼ぶ」だけ。順番も上限も、正本は上の各ファイルのまま。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★この係が「足す」もの（2026-09-26 時点で本当に無かったのはこの2つだけ）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ① **本物が0本だった時間を、分で積算して毎日記録する。**
     いまは「空回し(🧪)が何本」「見送りが何回」は残るが、
     **本物0本が何分続いたかが、どこにも積み上がっていない。**
     → status/fukkatsu.jsonl（1分1行）と status/zero_bon.json（日別の合計）。
     ★空回しは走行本数に数えない。数えると「回っているのに何も作っていない」を見逃す。

  ② **Claudeが使えない間、空回しの代わりに0円の本物仕事を回す。**
     auto_launcher.py は本物が出せないとき【空回し】2分タスクを入れる。
     止まって見えないための工夫だが、**0円で回せる本物（間違い探し・メイン不在の門）が
     待っているのに空回しを選ぶ**のは損。ここでその0円工程を直接回す。
     ★auto_launcher.py 本体は触らない（154KBの心臓部・壊すと全停止するため）。

使い方
  python3 tools/fukkatsu.py            # 1回まわす（心臓から1分おき）
  python3 tools/fukkatsu.py --show     # いまの状態を人が読む形で
"""
import io
import os
import sys
import json
import time
import datetime
import subprocess

JST = datetime.timezone(datetime.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

QUEUE = os.path.join(ST, "queue.json")
CAP = os.path.join(ST, "launch_cap.json")
NOLAUNCH = os.path.join(ST, "no_launch.flag")
LOG = os.path.join(ST, "fukkatsu.jsonl")
ZERO = os.path.join(ST, "zero_bon.json")

# 1回のtickで何分ぶんを積算するか（心臓からの呼び出し間隔）。
TICK_MIN = 1.0


def now():
    return datetime.datetime.now(JST)


def load(path, dflt=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dflt


def save_atomic(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def kazoeru():
    """走行中を数える。★空回し(keepalive/test)は本物に数えない。"""
    q = load(QUEUE, {}) or {}
    items = q.get("items") or []
    honmono, karamawashi = [], []
    for it in items:
        if it.get("status") != "running":
            continue
        if it.get("pid") and not pid_alive(it.get("pid")):
            continue  # もう死んでいる
        (karamawashi if (it.get("keepalive") or it.get("test")) else honmono).append(it)
    machi = [it for it in items if it.get("status") == "waiting"
             and not (it.get("keepalive") or it.get("test"))]
    return items, honmono, karamawashi, machi


def naze_tomatteru():
    """本物が出せない理由を1行で。出せるなら None。"""
    if os.path.exists(NOLAUNCH):
        try:
            t = io.open(NOLAUNCH, encoding="utf-8").read().strip()
        except Exception:
            t = "(読めませんでした)"
        return t[:200]
    return None


def mokuhyou():
    """目標本数。正本は inochi.py が書く status/launch_cap.json。ここでは決めない。"""
    c = (load(CAP, {}) or {}).get("cap")
    return c if isinstance(c, int) else 1


def yobu(script, args=None, secs=90):
    """既にある係を呼ぶ。落ちても自分は死なない。"""
    cmd = ["python3", os.path.join(HERE, script)] + (args or [])
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=secs)
        return {"script": script, "rc": p.returncode}
    except subprocess.TimeoutExpired:
        return {"script": script, "rc": "timeout"}
    except Exception as e:
        return {"script": script, "rc": "err:%s" % e}


def zero_tsumu(fueta_min, honmono_n, riyuu):
    """0本だった時間を日別に積む。★クレジット天井のときだけは赤にしない。"""
    d = load(ZERO, {}) or {}
    key = now().strftime("%Y-%m-%d")
    day = d.get(key) or {"zeroMin": 0.0, "hasshaMin": 0.0, "tenjoMin": 0.0, "why": {}}
    tenjo = bool(riyuu and "週次利用上限" in riyuu)
    if honmono_n > 0:
        day["hasshaMin"] = round(day["hasshaMin"] + fueta_min, 1)
    elif tenjo:
        # 天井だけが止まってよい理由。0本時間には積むが、赤にはしない。
        day["tenjoMin"] = round(day["tenjoMin"] + fueta_min, 1)
        day["zeroMin"] = round(day["zeroMin"] + fueta_min, 1)
    else:
        day["zeroMin"] = round(day["zeroMin"] + fueta_min, 1)
        k = (riyuu or "理由不明")[:60]
        day["why"][k] = round((day["why"].get(k) or 0) + fueta_min, 1)
    d[key] = day
    d["updatedAt"] = now().strftime("%Y-%m-%d %H:%M:%S")
    save_atomic(ZERO, d)
    return day


def zerodeni_shigoto(riyuu):
    """★Claudeが使えない間、空回しの代わりに0円の本物を回す。
    順番は aitara_mawasu.py の JUNBAN が正本。ここは「回せる0円工程」を聞いて回すだけ。"""
    yatta = []
    try:
        p = subprocess.run(["python3", os.path.join(HERE, "aitara_mawasu.py"), "--tsugi"],
                           capture_output=True, timeout=60)
        info = json.loads(p.stdout.decode("utf-8", "replace"))
    except Exception as e:
        return [{"step": "aitara_mawasu --tsugi", "rc": "err:%s" % e}]
    for st in (info.get("shirabe", {}).get("mawaseru") or []):
        if st.get("kind") != "machine" or st.get("yen"):
            continue  # 0円の機械工程だけ
        # 本体の在り処は aitara_mawasu.py の JUNBAN に書いてある。名前で引く。
        nm = st.get("name")
        script = {"間違い探し": "machigai_sagashi.py", "メイン不在の門": "main_kanmon.py"}.get(nm)
        if not script:
            continue
        args = ["--jissoku"] if script == "main_kanmon.py" else []
        r = yobu(script, args, secs=240)
        r["name"] = nm
        yatta.append(r)
    return yatta


def main():
    show = "--show" in sys.argv
    items, honmono, kara, machi = kazoeru()
    riyuu = naze_tomatteru()
    target = mokuhyou()
    ugoki = []

    # ── ① まず、固まった便を戻す（既にある係を呼ぶだけ）──
    if machi or honmono or riyuu:
        ugoki.append(yobu("1142_fukkyuu.py", secs=120))

    # ── ② 本物が出せるのに走行が目標を下回っていたら、その場で発車 ──
    if not riyuu and len(honmono) < target:
        for _ in range(max(0, target - len(honmono))):
            ugoki.append(yobu("auto_launcher.py", secs=120))
            time.sleep(2)  # ★同時に鍵を掴ませない（2026-09-20 の鍵消失の再発防止）

    # ── ③ 本物が1本も出せないなら、空回しでなく0円の本物を回す ──
    if riyuu and not honmono:
        ugoki += zerodeni_shigoto(riyuu)

    # ── ④ 0本だった時間を積む ──
    day = zero_tsumu(TICK_MIN, len(honmono), riyuu)

    rec = {
        "t": now().strftime("%Y-%m-%d %H:%M:%S"),
        "honmono": len(honmono),          # ★空回しを除いた走行本数
        "karamawashi": len(kara),
        "target": target,
        "machi": len(machi),              # 未着手の本物
        "tomatteruRiyuu": riyuu,
        "kyouZeroMin": day["zeroMin"],
        "kyouHasshaMin": day["hasshaMin"],
        "ugoki": ugoki,
        "aka": bool(riyuu and "週次利用上限" not in riyuu and not honmono),
    }
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if show:
        print("【復活係】%s" % rec["t"])
        print("  本物の走行 %d本／目標 %d本／空回し %d本／未着手 %d件"
              % (rec["honmono"], target, rec["karamawashi"], rec["machi"]))
        print("  今日：本物0本だった時間 %.0f分／本物が走っていた時間 %.0f分"
              % (day["zeroMin"], day["hasshaMin"]))
        if riyuu:
            print("  止まっている理由：%s" % riyuu)
        for u in ugoki:
            print("   ・%s → %s" % (u.get("name") or u.get("script"), u.get("rc")))
        if rec["aka"]:
            print("  🚨 赤：クレジット天井以外の理由で本物が0本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
