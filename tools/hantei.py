#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判定は、ここにしか書かない。

1018番（2026-09-22）たまごさん
  「走った回数と実際に取れた回数を両方数える。走った>0 なのに 取れた=0 は赤」
  「3層が同じ嘘を見ていた、を繰り返さない」

━━ なぜ新しいファイルを1つ増やしたか（増やさない主義に対する例外の理由）━━

実測で分かったのは「3層が同じ嘘を見ていた」ではなく、**もっと悪い形**だった。
2026-09-22 07:00 時点、同じ工場について3つの紙が3つの違うことを言っていた：

  ・status/genzaichi.md   … 「✅ 発車：10分以内に動いている」        ← 緑
  ・鍵台帳 probe_hassha() … 「発車が止められています（ログイン切れ）」← 赤（正しい）
  ・auto_launch.log       … 本物0本／空回し316本／見送り2453回        ← 赤（正しい）

＝ 正しい答えは既に工場の中にあった。**それを持っていない紙が、緑を出していた。**
たまごさんが最初に読む1枚（genzaichi.md）だけが嘘だったので、26時間気づけなかった。

さらに、判定そのものも2か所に別々に書かれていた：
  ・kagi_daicho.py watcher_rows() 696行目
      red = (bool(run_at) and not caught_at) or ...   ← 正しい型が既にあった
  ・genzaichi.py                                       ← 同じ型が無かった
同じ規則を2回書けば、片方だけ直る日が必ず来る。実際そうなっていた。

→ だから規則を**この1ファイルに引っ越す**。kagi_daicho も genzaichi も、
  これから足すどの見張りも、判定は必ずここを呼ぶ。ここを直せば全部が直る。
  新しい常駐は1つも増えない（このファイルは呼ばれるだけで、自分では走らない）。

━━ 規則（これが全部）━━

  走った = 0            → ⚪ まだ何も走っていない（異常ではない）
  走った > 0・取れた > 0 → ✅ 働いている
  走った > 0・取れた = 0 → 🔴 **動いているのに何も産んでいない**
  止めている理由がある   → 🔴 理由をそのまま出す（推測で埋めない・黙って飲み込まない）

「動いている」の根拠に、プロセスの生死・ログの更新・着火の有無を使わない。
それらは全部「空回しでも点く緑」になる。**取れた本数だけが根拠になる。**
"""
from __future__ import annotations

import datetime
import io
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status")
JST = datetime.timezone(datetime.timedelta(hours=9))

RULE = "走った>0 かつ 取れた=0 は赤"

# 黙って飲み込まれがちな言葉。見つけたら理由として必ず表に出す（0にしない・伏せない）。
SWALLOW_WORDS = ("no_credential", "empty_credential", "401", "403",
                 "skip", "skipped", "unauthorized", "forbidden",
                 "expired", "invalid_token", "ログイン", "認証")


def judge(runs, catches, blocked="", label=""):
    """唯一の判定。**これ以外の場所に同じifを書かない。**

    戻り値: dict(red, mark, line, runs, catches, blocked)
    """
    runs = int(runs or 0)
    catches = int(catches or 0)
    blocked = (blocked or "").strip()

    if blocked:
        red, mark = True, "🔴"
        why = "止められています：%s" % blocked
    elif runs == 0:
        red, mark = False, "⚪"
        why = "まだ走っていません"
    elif catches == 0:
        red, mark = True, "🔴"
        why = "**走った%d回 → 取れた0回。動いているのに何も産んでいません**" % runs
    else:
        red, mark = False, "✅"
        why = "走った%d回 → 取れた%d回" % (runs, catches)

    line = "%s %s%s" % (mark, (label + "：") if label else "", why)
    return dict(red=red, mark=mark, line=line, why=why,
                runs=runs, catches=catches, blocked=blocked)


def surface_swallowed(text):
    """no_credential / 401 / 403 / skip を黙って飲み込ませない。
    見つけた語をそのまま返す（無ければ空文字）。推測で言い換えない。"""
    if not text:
        return ""
    low = str(text).lower()
    found = [w for w in SWALLOW_WORDS if w.lower() in low]
    return "・".join(dict.fromkeys(found))


# ---------------------------------------------------------------------
# 工場そのものの「走った／取れた」
#   走った = 着火した本数（空回し🧪 も本物🚀 も含む）
#   取れた = 本物🚀 だけ。**空回しは1本も数に入れない。**
# ---------------------------------------------------------------------
AUTO_LAUNCH_LOG = os.path.join(STATUS, "auto_launch.log")
NO_LAUNCH_FLAG = os.path.join(STATUS, "no_launch.flag")
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def kojo(hours=6):
    """直近hours時間の工場の実績。戻り値は judge() と同じ形。"""
    since = datetime.datetime.now(JST) - datetime.timedelta(hours=hours)
    karamawashi = honmono = 0
    reasons = {}
    try:
        with io.open(AUTO_LAUNCH_LOG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = _TS.match(line)
                if not m:
                    continue
                try:
                    ts = datetime.datetime.strptime(
                        m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
                except ValueError:
                    continue
                if ts < since:
                    continue
                if "🚀" in line:
                    honmono += 1
                elif "🧪" in line:
                    karamawashi += 1
                elif "見送り:" in line:
                    r = line.split("見送り:", 1)[1].split("（")[0].strip()
                    reasons[r] = reasons.get(r, 0) + 1
    except FileNotFoundError:
        return judge(0, 0, blocked="auto_launch.log がありません", label="稼ぎ")

    blocked = ""
    # 止め札があるなら、それが一番強い理由。中身をそのまま出す（要約しない）。
    if os.path.exists(NO_LAUNCH_FLAG):
        try:
            blocked = io.open(NO_LAUNCH_FLAG, encoding="utf-8").read().strip()[:160]
        except Exception:
            blocked = "no_launch.flag があります（中身が読めません）"
    elif reasons:
        r, c = sorted(reasons.items(), key=lambda kv: -kv[1])[0]
        blocked = "%s（直近%d時間で%d回）" % (r, hours, c)

    res = judge(karamawashi + honmono, honmono, blocked=blocked, label="稼ぎ")
    res["karamawashi"] = karamawashi
    res["honmono"] = honmono
    res["hours"] = hours
    return res


def kojo_line(hours=6):
    """genzaichi.md などにそのまま貼る1行（複数行になることがある）。"""
    r = kojo(hours)
    head = "- %s 稼ぎ：直近%d時間 走った%d本（うち空回し%d本）→ **取れた%d本**" % (
        r["mark"], hours, r["runs"], r.get("karamawashi", 0), r["catches"])
    if not r["red"]:
        return head
    out = [head]
    if r["blocked"]:
        out.append("  - 止めているもの：%s" % r["blocked"])
        sw = surface_swallowed(r["blocked"])
        if sw:
            out.append("  - 飲み込まれがちな印：**%s**（0件にせず必ず表に出す）" % sw)
        if "ログイン" in r["blocked"] or "認証" in r["blocked"]:
            out.append("  - **これはたまごさんにしか外せません。"
                       "いつものClaudeのアプリで1回ログインし直すだけで、自動で再開します。**")
    return "\n".join(out)


# ---------------------------------------------------------------------
# 自己点検：「動いている」と言っている紙を全部集めて、同じ規則を当てる
#   ここに載っていない緑があったら、それが次に嘘をつく場所。
# ---------------------------------------------------------------------
GH_STATE = os.path.join(STATUS, "github_watch_state.json")


def suteta_henji():
    """捨てた返信を理由ごとに出す（github_watch の drops）。

    1018番：この見張りは「走った65回→取れた64回」で緑だった。
    だがその緑は「1件でも積めたか」でしかなく、**同じ回に何通捨てたかを誰も数えていなかった。**
    2026-09-19「重複と判定して4通」も 2026-09-22「Botだからと15通」も、ここで無言に消えていた。
    捨てること自体はやめない（捨てるべきものもある）。**数と理由を必ず表に出す。**
    """
    import json
    try:
        with io.open(GH_STATE, encoding="utf-8") as f:
            drops = (json.load(f) or {}).get("drops") or {}
    except Exception:
        return []
    rows = []
    for reason, n in sorted(drops.items(), key=lambda kv: -kv[1]):
        # 捨てて当然のものは緑。人間が知るべきものだけ赤にする。
        harmless = reason in ("工場自身の音", "今さっき号ごと積んだ", "基準線より前")
        rows.append(judge(n, n if harmless else 0,
                          blocked="" if harmless else reason,
                          label="捨てた返信 %d通" % n))
    return rows


def audit():
    """全部の緑に同じ規則を当てた結果を返す（リスト）。"""
    out = [kojo(6)]
    out.extend(suteta_henji())
    try:
        import kagi_daicho  # 同じtools/にある。判定はこちらへ寄せる。
        for row in kagi_daicho.watcher_rows():
            out.append(judge(row.get("runs"), row.get("catches"),
                             blocked=row.get("blocked", ""),
                             label=row.get("label") or row.get("id")))
    except Exception as e:  # noqa: BLE001
        # 読めなかったことを黙って飲み込まない。読めなかったと書く。
        out.append(judge(1, 0, blocked="鍵台帳が読めません：%s" % e, label="鍵台帳"))
    return out


if __name__ == "__main__":
    print("規則：%s\n" % RULE)
    for r in audit():
        print(r["line"])
