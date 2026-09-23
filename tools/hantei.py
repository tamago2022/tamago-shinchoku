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
import json
import os
import re
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status")
JST = datetime.timezone(datetime.timedelta(hours=9))

RULE = "走った>0 かつ 取れた=0 は赤"

# 黙って飲み込まれがちな言葉。見つけたら理由として必ず表に出す（0にしない・伏せない）。
SWALLOW_WORDS = ("no_credential", "empty_credential", "401", "403",
                 "skip", "skipped", "unauthorized", "forbidden",
                 "expired", "invalid_token", "ログイン", "認証")


# 機械の言葉 → たまごさんが読んで次の一手が分かる言葉。
# ★「blocked=no_credential」は嘘ではないが、**読んでも何をすればいいか分からない**。
#   分からない表示は、結局あとで人が読み直して原因を掘ることになる＝飲み込んでいるのと同じ。
#   翻訳もここ1か所に置く（各見張りに書かない）。
YAKU = (
    ("no_credential",
     "Gmailを読む鍵（アプリパスワード）が置かれていません"
     "（置き場 /Users/mac/.tamago/gmail_app_password）。"
     "★これはたまごさんにしか置けません。置けば次の30分以内に自動で見張りが始まります"),
    ("empty_credential",
     "Gmailを読む鍵のファイルはありますが、中身が空です"
     "（置き場 /Users/mac/.tamago/gmail_app_password）。★たまごさんにしか直せません"),
    ("credentialMissingNotified",
     "鍵が無いことを1回知らせたあと、そのまま止まっています"
     "（上と同じ Gmail の鍵）。★たまごさんにしか直せません"),
    ("401", "断られました（401＝鍵が違う・切れている）"),
    ("403", "断られました（403＝その鍵に権利が無い。課金か権限の追加が要ることが多い）"),
    ("unauthorized", "断られました（鍵が通っていません）"),
    ("forbidden", "断られました（権利がありません）"),
)


def yakusu(blocked):
    """止まっている理由を、読んで次の一手が分かる言葉にする。
    元の機械の言葉は**消さずに括弧で残す**（嘘にしないため）。"""
    s = (blocked or "").strip()
    if not s:
        return s
    # ★既に日本語で理由が書いてあるものは、絶対に置き換えない。
    #   最初の版は「403」という3文字が文中にあるだけで文全体を決まり文句にすり替え、
    #   Genspark（403とは別の理由で閉まっている）の説明を消してしまった＝新しい嘘。
    #   翻訳が要るのは「no_credential」のような、そのままでは読めない短い機械語だけ。
    if len(s) > 60 or re.search(r"[ぁ-んァ-ヶ一-龥]", s):
        return s
    low = s.lower()
    for key, jp in YAKU:
        if key.lower() in low:
            return "%s（機械の言葉：%s）" % (jp, s)
    return s


def judge(runs, catches, blocked="", label=""):
    """唯一の判定。**これ以外の場所に同じifを書かない。**

    戻り値: dict(red, mark, line, runs, catches, blocked)
    """
    runs = int(runs or 0)
    catches = int(catches or 0)
    blocked = (blocked or "").strip()

    if blocked:
        red, mark = True, "🔴"
        why = "止められています：%s" % yakusu(blocked)
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


def tally(prev, run_at, caught_at, blocked=""):
    """走った／取れたの数え方。**この1か所にしか書かない。**

    1026番（2026-09-23）たまごさん：
      「直せないもの（鍵が無い・権利が無い・課金が要る）は、赤のまま理由つきで出す。
        隠さない。**投げるのをやめる**（催促も回数も増やさない）。」

    実測（2026-09-22 23:40）：
      LINE審査結果の見張り … 走った78回・取れた0回
      だがこの78回は**1度もGmailに繋ぎに行っていない**。鍵が無いので、
      state に "blocked": "no_credential" と書いて即 return しているだけ。
      それを「走った」と数えていたので、直しようのない赤が毎分ふくらんでいた。

    → **叩けもしなかった回は、走ったに数えない。**
      止まっている事実は blocked が持っていて、judge() が必ず理由ごと赤で出す。
      数が増えないだけで、赤は1件も消えない（隠していない）。

    prev: {"runs":int,"catches":int,"seenRun":float,"seenCatch":float}
    戻り値: 更新後の同じ形（prev は書き換えない）
    """
    c = dict(runs=int((prev or {}).get("runs") or 0),
             catches=int((prev or {}).get("catches") or 0),
             seenRun=(prev or {}).get("seenRun") or 0,
             seenCatch=(prev or {}).get("seenCatch") or 0)
    blocked_now = bool((blocked or "").strip())
    if run_at and run_at > (c["seenRun"] or 0):
        if not blocked_now:
            c["runs"] += 1
        # 見た跡は blocked でも進める（同じ回を何度も数えないため）
        c["seenRun"] = run_at
    if caught_at and caught_at > (c["seenCatch"] or 0):
        c["catches"] += 1
        c["seenCatch"] = caught_at
    return c


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


AI_DAICHO = os.path.join(STATUS, "ai_daicho.json")


def gaibu_ai():
    """977番：他社AIとの往復に、同じ規則を当てる。

    走った = 投げた回数 ／ 取れた = 返ってきた回数。
    **「投げました」だけで緑にしない。**返りの実数が0なら赤。

    2026-09-22の実測で分かったこと（この行を作った理由）：
      ai-kaigi（公開掲示板）の #4/#5/#6 は、GitHub APIを直接叩いてコメント数0だった。
      こちらが捨てていたのでも、届いていなかったのでもない。**返事が存在しなかった。**
      理由＝ai-kaigi に入っている人は tamago2022 ただ1人で、botが1体も居ない。
      grok / genspark ラベルは貼れるが、それを読みに来るアプリが無い＝ラベルは飾り。
      → 「投げた回数」だけを見ていると、この穴は永遠に緑のままになる。だからここで数える。

    閉鎖中の口（投げても返らないと実測済みで、投げるのをやめた口）は
    赤にしない。赤は「直すべき穴」の色で、閉鎖は判断済みの状態だから。
    ただし黙らせない——理由をそのまま1行で出す。
    """
    import json
    try:
        with io.open(AI_DAICHO, encoding="utf-8") as f:
            d = json.load(f) or {}
    except Exception as e:  # noqa: BLE001
        return [judge(1, 0, blocked="外部AI台帳が読めません：%s" % e, label="外部AIとの往復")]
    rows = []
    for a in (d.get("ai") or []):
        label = "外部AI %s" % a.get("label", a.get("ai"))
        runs, catches = int(a.get("out") or 0), int(a.get("in") or 0)
        if a.get("blocked") and runs == 0:
            r = judge(0, 0, label=label)
            r["line"] = "⚫ %s：閉鎖中・投げていません（%s）" % (
                label, (a.get("blockedWhy") or "理由なし")[:120])
            rows.append(r)
            continue
        # 飲み込まれがちな失敗理由（401/403/no_credential/skip）は拾って表に出す
        swallowed = ""
        for e in (a.get("errs") or []):
            swallowed = surface_swallowed(e.get("err")) or swallowed
        # ★2026-09-23（1026番）実測で見つけた嘘：
        #   Grok・Genspark・Copilot は台帳に blocked=1 と理由まで書いてあるのに、
        #   過去に投げた跡（out>0）があるせいで上の if を通り抜け、
        #   「**走った3回 → 取れた0回。動いているのに何も産んでいません**」とだけ出ていた。
        #   ＝ **壊れているように見えて、本当は「課金・権利が無くて口が閉まっている」**。
        #   理由を持っているのに出さないのは、黙って飲み込むのと同じ。
        #   judge() は blocked を渡せば必ず理由を出す。渡していなかっただけ。
        r = judge(runs, catches, blocked=(a.get("blockedWhy") or "")
                  if a.get("blocked") else "", label=label)
        if swallowed and not r["red"]:
            r["line"] += "（飲み込まれかけた語：%s）" % swallowed
        rows.append(r)
    return rows


# ---------------------------------------------------------------------
# 台帳に載っていない定期便（＝誰も走った／取れたを見ていないもの）
#   ★1026番（2026-09-23）実測：8本あった。
#     kagi_daicho.unlisted_scan() は前から見つけていたが、その結果は
#     台帳のJSONの奥にしか出ず、hantei の一覧（＝赤の正本）には1行も出ていなかった。
#     見つけているのに出していない＝これも「黙って飲み込んでいる」。ここで表に出す。
# ---------------------------------------------------------------------
def daicho_gai():
    try:
        import kagi_daicho
        rows = kagi_daicho.unlisted_scan()
    except Exception as e:  # noqa: BLE001
        return [judge(1, 0, blocked="台帳外の点検が走りません：%s" % e, label="台帳外")]
    out = []
    for r in rows:
        out.append(judge(1, 0, blocked="台帳に載っていません（走ったか・取れたかを誰も見ていない）",
                         label="台帳外 %s" % r.get("script", "?")))
    return out


# ---------------------------------------------------------------------
# 見張り先の関所：**起こす引き金が無い先を、見張りに登録させない**
#   ★969番（アバターの返信拾い・81回走って0件）と977番（外部AI）で
#     まったく同じ事故が2回起きた＝個人の落ち度ではなく仕組みの不在。
#     どちらも「投げたつもりで、誰も起こしていなかった」。
#     穴を塞ぐ（今回の的だけ直す）のではなく、**登録の材料を替える**：
#     これから先、引き金の書いていない見張り先は通らない。
# ---------------------------------------------------------------------
# 実測で確かめた「起こし方」。ここに無いものは、起こせると名乗れない。
#   jules  … `jules` ラベルを貼る（公式ドキュメント＋実測）
#   codex  … `@codex` とコメントする（本文に書いても起きない・実測 #450）
#   devin  … API（別経路）
#   human  … 人間が読む板。相手が居るので引き金は要らない
WAKE_KINDS = ("jules", "codex", "devin", "human")


def wake_gate(targets):
    """見張り先の一覧を受け取り、(通った先, 止めた理由の行) を返す。

    targets: [{"repo": "...", "number": 1, "wake": "jules"}, ...]
    wake が無い／知らない値／起こした跡が無い先は **通さない**。
    通さなかったことは必ず行として返す（黙って捨てない）。
    """
    ok, stopped = [], []
    for t in (targets or []):
        key = "%s#%s" % (t.get("repo"), t.get("number"))
        wake = (t.get("wake") or "").strip().lower()
        if not wake:
            stopped.append(judge(1, 0, label="見張り先 %s" % key,
                                 blocked="起こす引き金が書いてありません"
                                         "（jules/codex/devin/human のどれかを wake に書く）"))
            continue
        if wake not in WAKE_KINDS:
            stopped.append(judge(1, 0, label="見張り先 %s" % key,
                                 blocked="知らない起こし方です：%s（実測で確かめたのは %s）"
                                         % (wake, "・".join(WAKE_KINDS))))
            continue
        if wake != "human" and not t.get("wokeAt"):
            stopped.append(judge(1, 0, label="見張り先 %s" % key,
                                 blocked="まだ1度も起こしていません（wake=%s の引き金を打つまで、"
                                         "ここは永久に0件のまま走り続けます）" % wake))
            continue
        ok.append(t)
    return ok, stopped


# ---------------------------------------------------------------------
#  コミットの口 ― 「積んだ枚数」と「回収された枚数」を数える（1027番・2026-09-23）
# ---------------------------------------------------------------------
#
# なぜ足したか（実測）:
#   2026-09-22に「コミットする口を1本にした」。ところが翌日 09:53 に置いた3枚が
#   10:01 まで回収されず、前のセッションは「口が詰まっている」と判断して止まった。
#   ★実測すると詰まっていなかった。回収は 10:01:53 に成功している（commit_kuchi.log）。
#   詰まりではなく**遅さ**だった。今日1日の実測：
#       受付 09:53:12 → 回収 10:01:53   （8分41秒）
#       受付 00:30:34 → 回収 00:40:45   （10分11秒）
#       受付 22:10:30 → 回収 23:17:47   （7分17秒）
#     さらに main のコミット間隔は 9〜28分（「5分便」という名前だが5分ではない）。
#
#   ＝ 「5分で出る」と思って待った人が、8分で「壊れている」と誤診する。
#     直すべきは口ではなく、**待ち時間が誰にも見えないこと**だった。
#     穴（回収されない）を塞ぐのではなく、**素材（何分待っているか）を出す。**
#
# 規則（上の RULE と同じ型で書く）:
#   積んだ = 0                       → ⚪ まだ何も置いていない
#   積んだ > 0・回収 = 積んだ          → ✅ 全部出ている
#   積んだ > 0・回収 < 積んだ          → 待っている紙がある。
#       最古の紙が LATE_SEC 以内     → ✅（正常な待ち。慌てて触らない）
#       最古の紙が LATE_SEC を超えた → 🔴 **回収が止まっている**
#
# ★LATE_SEC を 15分にした理由：実測の最悪が 10分11秒。5分便は1回の起動が約260秒
#   走り、launchd は5分おき＝最悪で約9分ずれる。15分を超えたら実測の外＝本物の異常。
LATE_SEC = 15 * 60


def commit_kuchi():
    """コミットの口：積んだ枚数と回収された枚数を数えて、差が出たら赤にする。"""
    inbox = os.path.join(STATUS, "commit_inbox")
    if not os.path.isdir(inbox):
        return judge(1, 0, label="コミットの口",
                     blocked="status/commit_inbox/ がありません（口そのものが無い）")

    def _papers(d):
        p = os.path.join(inbox, d) if d else inbox
        if not os.path.isdir(p):
            return []
        return [os.path.join(p, f) for f in os.listdir(p) if f.endswith(".json")]

    machi = _papers("")            # まだ回収されていない紙
    sumi = _papers("done")         # 回収された紙
    dame = _papers("rejected")     # 関所で断られた紙
    tsunda = len(machi) + len(sumi) + len(dame)
    kaishu = len(sumi) + len(dame)

    if tsunda == 0:
        return judge(0, 0, label="コミットの口")

    if not machi:
        r = judge(tsunda, kaishu, label="コミットの口")
        r["line"] = "✅ コミットの口 … 積んだ%d枚／回収%d枚（差0）" % (tsunda, kaishu)
        return r

    now = time.time()
    matsu = int(now - min(os.path.getmtime(p) for p in machi))
    fun = matsu // 60
    if matsu <= LATE_SEC:
        r = judge(tsunda, kaishu, label="コミットの口")
        r["line"] = ("✅ コミットの口 … 積んだ%d枚／回収%d枚／★待ち%d枚（最古%d分・"
                     "%d分までは正常な待ちです。触らないでください）"
                     % (tsunda, kaishu, len(machi), fun, LATE_SEC // 60))
        return r

    return judge(tsunda, kaishu, label="コミットの口",
                 blocked=("★待ち%d枚が%d分たっても回収されていません（正常は%d分以内）。"
                          "Mac側の5分便（tools/machine_status_push.sh）が動いているか、"
                          "status/commit_kuchi.log の最後の『✅ 回収』の時刻を見てください"
                          % (len(machi), fun, LATE_SEC // 60)))


# ---------------------------------------------------------------------
#  ★1038番（2026-09-23）積んだのに一度も走っていない ― 3日を超えたら赤
#
#  なぜ要るか（実測）：毎朝1件ずつ積む係は11日ぶん全部動いていたのに、
#  発車待ちが164件あって優先度3で最後尾に積まれるので、**一度も順番が来なかった。**
#  積む側も走る側も「自分は動いている」と言えてしまうので、どの緑にも引っかからない。
#  だから「積んだ日から3日を超えて、まだ一度も走っていない」だけを、ここで赤にする。
# ---------------------------------------------------------------------
NEVER_RAN_DAYS = 3          # これを超えて一度も走っていなければ赤
_TIME_KEYS = ("createdAt", "startedAt", "finishedAt", "checkedAt", "stuckAt",
              "cutAt", "demotedAt", "revivedAt", "recoveredAt", "heldAt",
              "reopenedAt", "costAskedAt", "urakataBlockedAt", "kenpinUpdatedAt")


def _ts(s):
    """'2026-09-12T01:20:00+09:00' でも '2026-09-12 01:20' でも秒に直す。読めなければ None。"""
    s = (s or "").strip()
    if not s:
        return None
    t = s.replace("T", " ")[:19]
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(t[:len(time.strftime(f))], f))
        except (ValueError, OverflowError):
            continue
    return None


def _item_oldest_ts(it):
    got = [_ts(it.get(k)) for k in _TIME_KEYS]
    got = [g for g in got if g]
    return min(got) if got else None


def hassha_machi():
    """発車待ちのうち「積んだのに一度も走っていない」を数える。3日超えが1件でもあれば赤。

    ★日付の出どころ：その1件が持っているいちばん古い時刻。持っていない件は、
      **番号が自分より大きくて時刻を持っている件**のいちばん古い時刻を上限にする
      （番号は積んだ順に増えるので、それより前に積まれたのは確か）。
      推測で古くしない＝上限すら取れない件は「日数不明」として数え、赤にはしない。
    """
    p = os.path.join(STATUS, "queue.json")
    try:
        items = json.load(io.open(p, encoding="utf-8")).get("items") or []
    except Exception as e:  # noqa: BLE001
        return judge(1, 0, label="発車待ち",
                     blocked="status/queue.json が読めません：%s" % e)

    known = sorted((it.get("n"), _item_oldest_ts(it)) for it in items
                   if isinstance(it.get("n"), int) and _item_oldest_ts(it))
    known = [(n, t) for n, t in known if t]

    def upper_bound(n):
        """番号 n より後に積まれた件が持つ、いちばん早い時刻（＝n はそれ以前に積まれた）。"""
        cand = [t for m, t in known if m > n]
        return min(cand) if cand else None

    now = time.time()
    waiting = [it for it in items if it.get("status") == "waiting"]
    never = [it for it in waiting if not it.get("startedAt")]
    rows, fumei = [], 0
    for it in never:
        t = _item_oldest_ts(it) or upper_bound(it.get("n") if isinstance(it.get("n"), int) else 10 ** 9)
        if not t:
            fumei += 1
            continue
        days = (now - t) / 86400.0
        if days > NEVER_RAN_DAYS:
            rows.append((round(days, 1), it.get("n"), (it.get("title") or "")[:38]))
    rows.sort(reverse=True)

    runs, catches = len(waiting), len(waiting) - len(never)
    if not rows:
        r = judge(max(runs, 1), max(catches, 1), label="発車待ち")
        r["line"] = ("✅ 発車待ち … %d件、うち一度も走っていないのは%d件（%d日超えは0件"
                     "／日数不明%d件）" % (len(waiting), len(never), NEVER_RAN_DAYS, fumei))
        r["rows"] = []
        return r

    top = "／".join("%s番（%s日）%s" % (n, d, t) for d, n, t in rows[:5])
    r = judge(runs, catches, label="発車待ち",
              blocked=("★積んだのに一度も走っていない件が%d件（%d日超え）。"
                       "古い順に %s。発車待ち全体は%d件。"
                       "★列が長すぎて順番が来ていないだけかもしれません。"
                       "毎日やることは列に積まず、自前の口で走らせてください"
                       % (len(rows), NEVER_RAN_DAYS, top, len(waiting))))
    r["rows"] = rows
    return r


# ---------------------------------------------------------------------
#  1028番（2026-09-23）ごきげん補給所の「重さ」― 前より重くなったら赤
# ---------------------------------------------------------------------
#
# たまごさん：「とにかく重いんだ。軽くしてくれるだけでもいい。」
#
# ★この節がやることは1つだけ：**物差しの目盛りを、進捗表の1行にする。**
#   軽くする工事はここではやらない。ただし「軽くしました」と言った人が本当かどうかを、
#   この行が毎回答える。今まで物差しが無かったので、誰も答えられなかった。
#
# 判定の型（judge() をそのまま使う。同じifを2か所に書かない）:
#   測っていない            → ⚪ まだ測っていません
#   前回より重い（+5%超）   → 🔴 **重くなりました**（どれが増えたかを名指しする）
#   前回と同じか軽い        → ✅ 何バイトか・一番でかいのは何かを出す
#
# ★しきい値+5%の根拠：同じページを続けて測っても、広告なしの静的配信でも
#   数%はぶれる（206の途中までしか来ない動画など）。5%以下は「ぶれ」、超えたら「変化」。
OMOSA_LAST = os.path.join(STATUS, "omosa_last.json")
OMOSA_LOG = os.path.join(STATUS, "omosa_log.jsonl")
OMOSA_BURE = 0.05  # 5%までは測りのぶれとみなす


def _mb(n):
    try:
        return "%.2fMB" % (float(n) / 1048576.0)
    except Exception:
        return "?"


def _omosa_read(path):
    import json as _json
    try:
        with io.open(path, encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None


def _omosa_prev(url=None, not_at=None):
    """1つ前の測定。無ければ None。

    ★比べる相手は「同じURLを・下見ではなく本測定で・測ったもの」に限る。
      ここを緩くすると、別のページの数字と比べて嘘の赤／嘘の緑が出る。
      （2026-09-23、実際に下見の数字と比べて「軽くなりました」と出かけた）
    """
    import json as _json
    if not os.path.exists(OMOSA_LOG):
        return None
    try:
        with io.open(OMOSA_LOG, encoding="utf-8") as f:
            rows = [x for x in f.read().splitlines() if x.strip()]
    except Exception:
        return None
    for line in reversed(rows):
        try:
            d = _json.loads(line)
        except Exception:
            continue
        if d.get("reconOnly"):
            continue
        if url and d.get("url") != url:
            continue
        if not_at and d.get("measuredAt") == not_at:
            continue
        if _omosa_total(d) > 0:
            return d
    return None


def _omosa_total(d, width="1280"):
    try:
        return int(((d.get("byWidth") or {}).get(width) or {}).get("bytes", {}).get("total") or 0)
    except Exception:
        return 0


def omosa():
    """ごきげん補給所の重さ。前より重くなったら赤。

    数字は tools/omosa.mjs が実測して status/omosa_last.json に置いたものだけを読む。
    ★ここでは一切測らない（測るのは工場側。ここは読むだけ＝常駐を増やさない）。
    """
    cur = _omosa_read(OMOSA_LAST)
    if not cur:
        return judge(0, 0, label="ごきげん補給所の重さ",
                     blocked=("まだ一度も測っていません。"
                              "工場側で `node tools/omosa.mjs` を走らせてください"
                              "（サンドボックスからは kind=kakunin / mode=omosa で頼めます）"))
    if cur.get("error"):
        return judge(1, 0, label="ごきげん補給所の重さ",
                     blocked="測ろうとして失敗しました：%s" % str(cur["error"])[:160])

    w = (cur.get("byWidth") or {}).get("1280") or {}
    b = w.get("bytes") or {}
    total = int(b.get("total") or 0)
    if total <= 0:
        return judge(1, 0, label="ごきげん補給所の重さ",
                     blocked="測ったのにバイト数が0でした（＝何も取れていません）")

    top = (b.get("top") or [{}])[0]
    hannin = "%s %s" % (top.get("name", "?"), _mb(top.get("bytes")))
    itsu = cur.get("measuredAt", "")

    # スマホ幅・棚編集・URL貼りも、取れていれば一緒に出す（別の行にしない＝見る紙を増やさない）
    oi = []
    m375 = (cur.get("byWidth") or {}).get("375") or {}
    if (m375.get("bytes") or {}).get("total"):
        oi.append("375pxは%s" % _mb(m375["bytes"]["total"]))
    te = w.get("tanaHenshu") or {}
    if te.get("stillLoading"):
        oi.append("★棚編集は%d秒待っても中身が出ない" % int((te.get("gaveUpAfterMs") or 0) / 1000))
    elif te.get("readyMs") is not None:
        oi.append("棚編集は%.1f秒で出る" % (te["readyMs"] / 1000.0))
    pa = w.get("paste") or w.get("pasteFallback") or {}
    if pa.get("tried"):
        oi.append("URL貼り%d回中%d回落ちた" % (pa["tried"], pa["ochita"]))
    elif pa.get("skipWhy"):
        oi.append("URL貼りは測れず（%s）" % pa["skipWhy"])
    oi_s = ("／" + "／".join(oi)) if oi else ""

    prev = _omosa_prev(url=cur.get("url"), not_at=cur.get("measuredAt"))
    ptotal = _omosa_total(prev) if prev else 0
    if ptotal > 0:
        sa = total - ptotal
        wari = sa / float(ptotal)
        if wari > OMOSA_BURE:
            return judge(1, 0, label="ごきげん補給所の重さ",
                         blocked=("**前より重くなりました** %s → %s（+%s・+%.0f%%）。"
                                  "一番でかいのは %s。測ったのは %s"
                                  % (_mb(ptotal), _mb(total), _mb(sa), wari * 100, hannin, itsu)))
        r = judge(1, 1, label="ごきげん補給所の重さ")
        muki = "軽くなりました" if sa < 0 else "前回と同じ"
        r["line"] = ("✅ ごきげん補給所の重さ … トップ%s（前回%s・%s）／一番でかいのは %s%s"
                     % (_mb(total), _mb(ptotal), muki, hannin, oi_s))
        r["red"] = False
        return r

    r = judge(1, 1, label="ごきげん補給所の重さ")
    r["line"] = ("✅ ごきげん補給所の重さ … トップ%s（★これが1本目の目盛り。"
                 "次に測ったときここより重ければ赤になります）／一番でかいのは %s%s"
                 % (_mb(total), hannin, oi_s))
    r["red"] = False
    return r


# ---------------------------------------------------------------------
#  区間5（検品）― 出していいかを、AIに聞かずに機械だけで判定する
# ---------------------------------------------------------------------
#
# なぜ機械だけでやるか（実測）:
#   Claude子セッションの自己検品は310件中169件合格＝54.5%。
#   ＝**自分の仕事を自分では見られていない。**（oni_gate.py の冒頭と同じ理由）
#   だからここではAIを1回も呼ばない。全部ただの文字列判定。課金0。毎回同じ答えが出る。
#
# 使い道：外から来たPRを **mainに入れる前に** 通す受け口。
#   「そこまで運んできてくれてありがとう。ここから先はこちらが運ぶ」の“ここ”。
# 375px（iPhone SE / mini の幅）で横スクロールが出る書き方を、静的に見つける。
#   ★ただし「表だけを箱の中で横スクロールさせる」のは、たまごさんのページで
#     ずっと使ってきた**正しい型**（.wrap{overflow-x:auto} で囲んだ table）。
#     これを赤にすると、直っているページまで赤くなって誰も見なくなる。
#     だから **箱（overflow-x:auto）がある表は通す。それ以外の固定幅だけ止める。**
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_CSS_WIDTH = re.compile(r"(?:^|[;\s])(?:min-)?width\s*:\s*(\d{3,5})px", re.I)


def kensa_html(text, name=""):
    """HTMLの中身を機械だけで検品する。返り値: (通ったか, [理由...])"""
    ng = []
    t = text or ""
    if len(t.strip()) < 200:
        ng.append("中身が空か短すぎます（%dバイト）" % len(t.encode("utf-8")))
    if "</html>" not in t.lower():
        ng.append("</html> まで届いていません（途中で切れた可能性）")
    if "<title" not in t.lower():
        ng.append("<title> がありません")
    if "name=\"viewport\"" not in t.lower().replace("'", '"'):
        ng.append("viewport の指定がありません（スマホで縮小表示になります）")
    hako = "overflow-x:auto" in t.replace(" ", "").lower()
    for sel, decl in _CSS_RULE.findall(t):
        m = _CSS_WIDTH.search(";" + decl)
        if not m or int(m.group(1)) <= 375:
            continue
        s = sel.strip().lower()
        if hako and ("table" in s or s.startswith("th") or s.startswith("td")):
            continue  # 箱で横スクロールさせる表＝正しい型なので通す
        ng.append("375pxより広い固定幅があります（%s に %spx）＝画面ごと横に流れます"
                  % (sel.strip()[:40], m.group(1)))
        break
    if len(t.encode("utf-8")) > 1024 * 1024:
        ng.append("1MBを超えています（公開に載せない決まり）")
    return (not ng), ng


# ---------------------------------------------------------------------
#  1033番（2026-09-23）数字と断定の門 ― 報告がDispatchに上がる前に通す
# ---------------------------------------------------------------------
#
# たまごさん：「調べてから上げてこいよって。混乱するから。
#               コロコロコロコロ変わるから、報告がさぁ。」
#
# ★判定の中身はここに1行も書かない。tools/kazu_gate.py にしかない。
#   ここは呼ぶだけ。1018番の「同じifを2か所に書いて片方だけ直った」を繰り返さない。
def kazu(text, label="報告の数字"):
    """報告文を数字の門に通す。judge() と同じ形で返す。"""
    try:
        import kazu_gate
    except Exception as e:  # noqa: BLE001
        return judge(1, 0, blocked="数字の門が読めません：%s" % e, label=label)
    r = kazu_gate.judge(text or "")
    if r["ok"]:
        res = judge(1, 1, label=label)
        res["line"] = "✅ %s … 数字%d件、全部に出どころがあります" % (label, r["counted"])
        return res
    return judge(1, 0, label=label,
                 blocked="／".join("[%s] %s" % (h["code"], h["why"])
                                   for h in r["hits"])[:600])


def kazu_kanmon():
    """★門そのものが効いているかを毎回みる。

    門は、効かなくなっても静かに素通りするので、誰も気づかない。
    見本（わざと悪い報告文）で落ちるかを毎回試して、落ちなくなったら赤。
    """
    try:
        import kazu_gate
        n, ng, _ = kazu_gate.self_test(verbose=False)
    except Exception as e:  # noqa: BLE001
        return judge(1, 0, blocked="数字の門の見本試験が走りません：%s" % e,
                     label="数字の門")
    if ng:
        return judge(n, n - ng, label="数字の門",
                     blocked="★見本%d件中%d件で落とせませんでした＝"
                             "出典の無い数字がたまごさんまで素通りします" % (n, ng))
    r = judge(n, n, label="数字の門")
    r["line"] = ("✅ 数字の門 … わざと悪い報告文%d件を全部落としました"
                 "（出典なし／推測語／「無い」の断定／前と食い違うのに訂正なし）" % n)
    return r


def audit():
    """全部の緑に同じ規則を当てた結果を返す（リスト）。"""
    out = [kojo(6), commit_kuchi(), omosa(), kazu_kanmon(), hassha_machi()]
    out.extend(suteta_henji())
    out.extend(gaibu_ai())
    out.extend(daicho_gai())
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


# ══════════════════════════════════════════════════════════════════════
# 案内人（卵コンシェルジュ）の採点 ― ★規則はここにしか書かない
#   紙の基準：status/annai_saiten_kijun.md（v1・2026-09-23確定）
#   問：status/annai_300.json（tools/annai_toi.py が作る）
#   ★AIを1回も呼ばない。文字合わせだけで決める。
# ══════════════════════════════════════════════════════════════════════

# 出た札に必ず書かれている「知らない◯◯の世界だけど」から分野を読む。
ANNAI_FIELD_RE = re.compile(r"知らない(音楽|食べ物|かわいい|笑い|旅|踊り|喜び)の世界")

# 「案内人のセリフ」と「出てきたカードの題名」を分ける線。
# 題名は短くて句読点が無い。人が読むセリフは文になっている。
def annai_is_speech(line):
    return len(line) >= 10 and any(c in line for c in "。、！？!?…")


def annai_split(lines):
    """画面に増えた行を セリフ／札 に分ける。"""
    sp = [l for l in lines if annai_is_speech(l)]
    ca = [l for l in lines if not annai_is_speech(l)]
    return sp, ca


# 「わかりません」だけを返した＝黙ったのと同じ。
ANNAI_DAMARI = ("わかりません", "分かりません", "わからない", "見つかりません",
                "ありません", "該当なし", "該当しません", "エラー",
                "もう一度", "すみません、", "ごめんなさい、")

# かわせている＝「それは分からない」と言えている。曲を出していないことが前提。
ANNAI_KAWASE = ANNAI_DAMARI + ("音楽", "曲", "案内", "専門", "お答え", "ここでは",
                               "できません", "苦手", "範囲")

ANNAI_SPEECH_MAX_LINES = 2     # これを超えたら喋りすぎ
ANNAI_SPEECH_MAX_CHARS = 120   # これを超えたら喋りすぎ


def saiten_annai(toi, ans):
    """1問を採点する。★1問につきラベルは必ず1個（上から順）。

    toi … {"q","field","words","kawasu"}            （annai_300.json の1行）
    ans … {"text","lines","error"}                   （どこで叩いても同じ形にして渡す）
    返り … {"label","mark","why","field_got","hit"}

    ラベルは5つだけ：
      ✕ 無反応(落ちた) ／ ✕ 無反応(黙った) ／ ✕ トンチンカン ／ ✕ 喋りすぎ
      △ そっけない ／ ◯ 合格
    """
    text = (ans.get("text") or "").strip()
    lines = ans.get("lines")
    if lines is None:
        lines = [x.strip() for x in text.split("\n") if x.strip()]
    err = (ans.get("error") or "").strip()
    speech, cards = annai_split(lines)
    sp = "\n".join(speech).strip()
    got = sorted(set(ANNAI_FIELD_RE.findall(text)))
    kawasu = bool(toi.get("kawasu"))

    def out(label, mark, why, hit=None):
        return {"label": label, "mark": mark, "why": why,
                "field_got": got, "hit": hit, "q": toi.get("q", "")}

    # ── 1. 無反応 ────────────────────────────────────────────────
    if err:
        return out("無反応(落ちた)", "✕", "投げられなかった：%s" % err[:80])
    if len(text) < 4:
        return out("無反応(黙った)", "✕", "返事が%d文字" % len(text))
    only_damari = (not cards) and sp and all(
        any(w in l for w in ANNAI_DAMARI) for l in speech)
    if only_damari and not kawasu:
        return out("無反応(黙った)", "✕", "「わかりません」だけ")
    if not cards and not kawasu:
        # 曲を聞かれて曲を1枚も出していない＝お客さんから見れば何も返っていない。
        return out("無反応(黙った)", "✕", "曲・棚が1枚も出ていない")

    # ── 2. トンチンカン ─────────────────────────────────────────
    if kawasu:
        # 答えられなくて当然の問。★正解は「曲を出さずにかわす」。
        if cards:
            return out("トンチンカン", "✕",
                       "答えられない問なのに曲を%d枚出した（絶無>誤り）" % len(cards))
        if not any(w in text for w in ANNAI_KAWASE):
            return out("トンチンカン", "✕", "かわせていない（分からないと言っていない）")
    else:
        field = toi.get("field")
        words = toi.get("words") or []
        hit = next((w for w in words if w and w.lower() in text.lower()), None)
        field_ok = bool(field and got and field in got)
        # ★「1つも結びつかない」ときだけ✕。分野が合う か 言葉が当たる のどちらかで◯。
        if not field_ok and not hit:
            return out("トンチンカン", "✕",
                       "聞いたのは%sだが出たのは%s／手がかりの語が1つも出ない"
                       % (field or "?", "・".join(got) or "分野不明"))

    # ── 3. 喋りすぎ ────────────────────────────────────────────
    if len(speech) > ANNAI_SPEECH_MAX_LINES or len(sp) > ANNAI_SPEECH_MAX_CHARS:
        return out("喋りすぎ", "✕",
                   "セリフ%d行・%d文字（1行＋短い一言まで）" % (len(speech), len(sp)))

    # ── 4. そっけない ──────────────────────────────────────────
    if not sp:
        return out("そっけない", "△", "セリフゼロ（曲名だけ返した）")

    # ── 5. 合格 ────────────────────────────────────────────────
    return out("合格", "◯", "")


ANNAI_LABELS = ["無反応(落ちた)", "無反応(黙った)", "トンチンカン", "喋りすぎ",
                "そっけない", "合格"]


def saiten_annai_matome(rows):
    """1周ぶんをまとめる。★トンチンカン率＝✕の数÷出した問の数。"""
    b = {k: 0 for k in ANNAI_LABELS}
    for r in rows:
        b[r["label"]] = b.get(r["label"], 0) + 1
    asked = len(rows)
    ng = sum(b[k] for k in ANNAI_LABELS if k != "合格" and k != "そっけない")
    warn = b["そっけない"]
    return {
        "asked": asked,
        "ng": ng,
        "ng_rate": round(ng / asked, 4) if asked else 0.0,
        "warn": warn,
        "warn_rate": round(warn / asked, 4) if asked else 0.0,
        "breakdown": {k: v for k, v in b.items() if v},
    }


def saiten_annai_ku(rows, tois):
    """区分ごとの不合格率。★どこが一番悪いかを見て、直す1つを選ぶための表。"""
    byq = {t["q"]: t for t in tois}
    ku = {}
    for r in rows:
        t = byq.get(r["q"]) or {}
        k = t.get("区分", "?")
        d = ku.setdefault(k, {"asked": 0, "ng": 0, "labels": {}})
        d["asked"] += 1
        if r["label"] not in ("合格", "そっけない"):
            d["ng"] += 1
        d["labels"][r["label"]] = d["labels"].get(r["label"], 0) + 1
    for d in ku.values():
        d["ng_rate"] = round(d["ng"] / d["asked"], 4) if d["asked"] else 0.0
    return ku


if __name__ == "__main__":
    print("規則：%s\n" % RULE)
    for r in audit():
        print(r["line"])
