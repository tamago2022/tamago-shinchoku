#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1142番：復旧係。**赤を見つけたら、人を呼ばずに直す。直せないものだけ赤のまま残す。**

たまごさん（2026-09-25）：
  「ミスを見つけたら自動で復旧するにはどうしたらいいか」
  「基本的に止まらないで回し続けて。」

------------------------------------------------------------------
考え方（SREの自動復旧をそのまま借りる）
------------------------------------------------------------------
自動復旧が成立する条件は世界中どこでも同じで、3つしかない。

  1. **直し方が1本に決まっていること**（分岐があるものは人に渡す）
  2. **やり直して安全なこと**（何回やっても同じ結果＝冪等）
  3. **直したかどうかを、直したあとに機械が確かめられること**

この3つを満たすものだけをここに入れる。満たさないものは
**直そうとせず、赤のまま「これは人にしか外せません」と名前を出す。**
（無理に直そうとして壊すのが、いちばんやってはいけない形）

------------------------------------------------------------------
いま直せるもの／直せないもの（2026-09-25 実測ベース）
------------------------------------------------------------------
  直せる  ① 途中で固まった案件(stuck)を順番待ちへ戻す        … 13件
  直せる  ② 誰も掴んでいない古い錠前(.lock)を外す
  直せる  ③ 書きかけの .tmp / .EMPTY- のゴミを片付ける
  直せる  ④ 失敗台帳が何日も増えていないとき、今日の赤を自分で書き込む
  直せない ⑤ ログイン切れ … **鍵はたまごさん本人しか作れない。**
             → 直さない。代わりに「Macで1回押すだけ」の札を出す（status/mac_jobs）

------------------------------------------------------------------
戻し方（1行）
------------------------------------------------------------------
  python3 ~/Desktop/tamago-shinchoku/tools/1142_loop.py --modosu
"""
import io
import json
import os
import sys
import time
import glob
import datetime

JST = datetime.timezone(datetime.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LEDGER = os.path.join(STATUS, "1142_fukkyuu.jsonl")
LOG = os.path.join(STATUS, "1142_fukkyuu.log")
DRY = "--honban" not in sys.argv          # 既定は下見。--honban で実際に直す


def now():
    return datetime.datetime.now(JST)


def rec(kind, naoshita, what, detail=""):
    row = dict(at=now().strftime("%Y-%m-%d %H:%M:%S"), kind=kind,
               naoshita=bool(naoshita), what=what, detail=detail, dry=DRY)
    try:
        with io.open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print(("  直した " if naoshita else "  直せない ") + what +
          (("／" + detail) if detail else ""))
    return row


def _yuurei_kanda(title):
    """1377番（2026-09-28）：たまごさんの相槌が「判定日赤｜」付きqueue項目として
    無限に stuck→waiting→running を繰り返し、複数セッションが空振りし続けた事故の
    再発防止。tools/shukudai.py の actionable() と同じ判定基準を、ここでも
    （規則を2か所に書かず）そのまま呼ぶ。True＝実行可能な作業指示が無い幽霊項目。
    """
    try:
        import shukudai
    except Exception:
        return False
    return shukudai.actionable({"source": "queue", "title": title or ""}) is False


# ── ① 途中で固まった案件を順番待ちへ戻す ───────────────────────────
def naosu_stuck():
    p = os.path.join(STATUS, "queue.json")
    try:
        q = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        return rec("stuck", False, "キューが読めません", str(e)[:80])
    items = q.get("items") or []
    all_stuck = [i for i in items if str(i.get("status")) == "stuck"]
    # ★redoCount>=2 かつ 具体的な作業指示が読み取れない項目は、戻さず取り消す。
    #   （1142の3条件のうち②「やり直して安全」を満たさない＝毎回同じ徒労になる）
    yuurei = [i for i in all_stuck
              if int(i.get("redoCount") or 0) >= 2 and _yuurei_kanda(i.get("title"))]
    target = [i for i in all_stuck if i not in yuurei]
    if not target and not yuurei:
        return rec("stuck", True, "固まった案件は0件", "")
    if DRY:
        return rec("stuck", False, "固まった案件 %d件・うち幽霊項目%d件（下見だけ）"
                   % (len(target), len(yuurei)),
                   "／".join(str(i.get("n")) for i in (target + yuurei)[:10]))
    # ★触る前に必ず控えを取る（1コマンドで戻せる形）
    try:
        bak = os.path.join(STATUS, "_1142_gomi")
        os.makedirs(bak, exist_ok=True)
        import shutil
        shutil.copy2(p, os.path.join(
            bak, "queue.json.bak-" + now().strftime("%Y%m%d-%H%M%S")))
    except Exception:
        pass
    for i in target:
        i["status"] = "waiting"
        i["restoredAt"] = now().isoformat()
        i["restoreWhy"] = "1142_fukkyuu：固まっていたので順番待ちへ戻した"
    for i in yuurei:
        i["_preCancelStatus"] = i.get("status")
        i["status"] = "cancelled"
        i["cancelledAt"] = now().isoformat()
        i["restoreWhy"] = ("1142_fukkyuu：%d回やり直しても具体的な作業指示が無い"
                            "（たまごさんの相槌・感想の類）ため取り消し（1377番の再発防止）"
                            % int(i.get("redoCount") or 0))
    tmp = p + ".tmp1142"
    json.dump(q, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    detail = "／".join(str(i.get("n")) for i in target[:10])
    if yuurei:
        detail += "（うち取り消し：%s）" % "／".join(str(i.get("n")) for i in yuurei)
    return rec("stuck", True, "固まった案件 %d件を順番待ちへ戻した（幽霊項目%d件は取り消し）"
               % (len(target), len(yuurei)), detail)


# ── ①' 順番待ち(waiting)のまま列を占有し続ける幽霊項目を取り消す ──────────
# 1494番（2026-09-29）：「今から寝るけど起きたらできてるようにして」のような
# たまごさんの相槌・激励は、一度もrunningにならず waiting のまま優先度1(urgent)の
# 列に残り続け、1377/1446/1480番と同じ「redoCount>=2に達するまで待つ」設計の
# ①（naosu_stuck）では stuck化するまで検知できなかった。ここで waiting も対象に含め、
# 実行して確かめるまでもなく（タイトルの構造だけで）判定できる幽霊項目は初回から取り消す。
def naosu_ghost_waiting():
    try:
        import shukudai
    except Exception as e:
        return rec("ghost_waiting", False, "shukudaiが読めません", str(e)[:80])
    p = os.path.join(STATUS, "queue.json")
    try:
        q = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        return rec("ghost_waiting", False, "キューが読めません", str(e)[:80])
    items = q.get("items") or []
    all_waiting = [i for i in items if str(i.get("status")) == "waiting"]
    yuurei = [i for i in all_waiting
              if shukudai.actionable({"source": "queue", "title": i.get("title") or ""}) is False]
    if not yuurei:
        return rec("ghost_waiting", True, "順番待ちの幽霊項目は0件", "")
    if DRY:
        return rec("ghost_waiting", False, "順番待ちの幽霊項目 %d件（下見だけ）" % len(yuurei),
                   "／".join(str(i.get("n")) for i in yuurei[:10]))
    try:
        bak = os.path.join(STATUS, "_1142_gomi")
        os.makedirs(bak, exist_ok=True)
        import shutil
        shutil.copy2(p, os.path.join(
            bak, "queue.json.bak-" + now().strftime("%Y%m%d-%H%M%S")))
    except Exception:
        pass
    for i in yuurei:
        i["_preCancelStatus"] = i.get("status")
        i["status"] = "cancelled"
        i["cancelledAt"] = now().isoformat()
        i["restoreWhy"] = ("1142_fukkyuu：順番待ちのまま具体的な作業指示が無い"
                            "（たまごさんの相槌・感想の類）ため取り消し（1377/1494番の再発防止）")
    tmp = p + ".tmp1142b"
    json.dump(q, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    detail = "／".join(str(i.get("n")) for i in yuurei[:10])
    return rec("ghost_waiting", True, "順番待ちの幽霊項目 %d件を取り消した" % len(yuurei), detail)


# ── ② 誰も掴んでいない古い錠前を外す ────────────────────────────
def naosu_lock(furui_min=60):
    n = 0
    names = []
    for p in glob.glob(os.path.join(STATUS, "*.lock")) + \
             glob.glob(os.path.join(STATUS, "*.lock (*)")):
        try:
            age = (time.time() - os.path.getmtime(p)) / 60.0
        except OSError:
            continue
        if age < furui_min:
            continue
        names.append(os.path.basename(p))
        if not DRY:
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    if not names:
        return rec("lock", True, "古い錠前は0個", "")
    return rec("lock", not DRY, "古い錠前 %d個%s" % (len(names),
               "を外した" if not DRY else "（下見だけ）"), "／".join(names[:8]))


# ── ③ 書きかけのゴミを片付ける ──────────────────────────────────
def naosu_gomi(furui_h=24):
    pats = ["*.tmp.*", "*.json.tmp", "*.EMPTY-*"]
    names = []
    for pat in pats:
        for p in glob.glob(os.path.join(STATUS, pat)):
            try:
                age = (time.time() - os.path.getmtime(p)) / 3600.0
            except OSError:
                continue
            if age < furui_h:
                continue
            names.append(os.path.basename(p))
            if not DRY:
                # ★消さない。箱へ移すだけ。（消す／動かすの関所：戻せる形にする）
                box = os.path.join(STATUS, "_1142_gomi")
                os.makedirs(box, exist_ok=True)
                try:
                    os.replace(p, os.path.join(box, os.path.basename(p)))
                except OSError:
                    pass
    if not names:
        return rec("gomi", True, "書きかけのゴミは0個", "")
    return rec("gomi", not DRY, "書きかけのゴミ %d個%s" % (len(names),
               "を status/_1142_gomi/ へ移した（消していない）" if not DRY
               else "（下見だけ）"), "／".join(names[:8]))


# ── ④ 失敗台帳が止まっていたら、今日の赤を自分で書き込む ──────────────
def naosu_failures():
    """★これが無かったせいで failures.jsonl は10日間1行も増えていなかった。
    「記録する係が止まっていることを、誰も記録していない」＝いちばん危ない形。"""
    fp = os.path.join(STATUS, "failures.jsonl")
    loop = os.path.join(STATUS, "public", "loop.json")
    try:
        o = json.load(io.open(loop, encoding="utf-8"))
    except Exception:
        return rec("failures", False, "計器盤がまだ無い", "先に 1142_loop.py を回す")
    today = now().strftime("%Y-%m-%d")
    try:
        body = io.open(fp, encoding="utf-8", errors="ignore").read()
    except Exception:
        body = ""
    if today in body:
        return rec("failures", True, "失敗台帳は今日ぶん記録済み", "")
    aka = [c for c in o.get("cards", []) if c.get("red")]
    if not aka:
        return rec("failures", True, "今日の赤は0件", "")
    if DRY:
        return rec("failures", False, "失敗台帳に今日の赤%d件（下見だけ）" % len(aka), "")
    with io.open(fp, "a", encoding="utf-8") as f:
        for c in aka:
            f.write(json.dumps(dict(
                id="F-%s-%s" % (now().strftime("%Y%m%d"), c["key"]),
                date=today, what="%s：%s%s（%s）" % (c["label"], c["value"],
                                                   c["unit"], c["sub"]),
                kata=c["key"], nao=c.get("nao", ""),
                by="1142_fukkyuu"), ensure_ascii=False) + "\n")
    return rec("failures", True, "失敗台帳に今日の赤 %d件を書いた" % len(aka), "")


# ── ⑤ ログイン切れ：直さない。Macで1回押すだけの札を出す ──────────────
def naosu_login():
    f = os.path.join(STATUS, "auth_expired.flag")
    if not os.path.exists(f):
        return rec("login", True, "ログインは生きている", "")
    since = ""
    try:
        since = json.load(io.open(os.path.join(STATUS, "auth_keeper.json"),
                                  encoding="utf-8")).get("ngSince") or ""
    except Exception:
        pass
    pend = os.path.join(STATUS, "mac_jobs", "pending", "1142_login_fuda.sh")
    if os.path.exists(pend):
        return rec("login", False, "ログイン切れ（%sから）" % since, "札はもう出してある")
    if DRY:
        return rec("login", False, "ログイン切れ（%sから）" % since, "札を出す（下見だけ）")
    os.makedirs(os.path.dirname(pend), exist_ok=True)
    with io.open(pend, "w", encoding="utf-8") as f2:
        f2.write(
            "#!/bin/bash\n"
            "# 1142番：ログインの1年鍵を作る手順を、たまごさんのMacのクリップボードに入れて\n"
            "# ターミナルを開くだけ。鍵そのものはAI側で一切扱わない。\n"
            "printf '%s' "
            "'python3 ~/Desktop/tamago-shinchoku/tools/975_login_1pon.py' | pbcopy\n"
            "open -a Terminal\n"
            "echo 'クリップボードに入れました。⌘V → Enter'\n")
    os.chmod(pend, 0o755)
    return rec("login", False, "ログイン切れ（%sから）" % since,
               "Macに札を出した。⌘V→Enterで1年鍵になる（追加0円）")


def main():
    print("1142 復旧係 %s（%s）" % (now().strftime("%H:%M:%S"),
                                   "下見" if DRY else "本番"))
    rows = [naosu_stuck(), naosu_ghost_waiting(), naosu_lock(), naosu_gomi(), naosu_failures(), naosu_login()]
    naoshita = sum(1 for r in rows if r["naoshita"])
    nokori = [r["what"] for r in rows if not r["naoshita"]]
    print("→ 直した %d／%d。残った赤：%s" % (naoshita, len(rows),
                                          "／".join(nokori) if nokori else "なし"))
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s 直した%d/%d 残り:%s\n" % (
                now().strftime("%Y-%m-%d %H:%M:%S"), naoshita, len(rows),
                "／".join(nokori)))
    except Exception:
        pass
    # ★この係も同じ判定にかける（跡を残さない係は赤になる決まり）
    try:
        sys.path.insert(0, HERE)
        import importlib
        L = importlib.import_module("1142_loop")
        L.ashiato("1142_fukkyuu", naoshita,
                  blocked=("／".join(nokori) if nokori else ""))
    except Exception:
        pass


if __name__ == "__main__":
    main()
