#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/hantei.py ── 判定日が来たら機械が見に行く係。うやむやを構造的に不可能にする。

たまごさん（2026-09-26）:
  「1行＝1依頼。列：言われた日時／内容／言われた回数／状態／1週間後の判定日／
    1ヶ月後の判定日／実際どうなったか。判定日が来たら機械が自動で状態を見に行って、
    変わっていなければ★自動で赤＋P1に繰り上げ。うやむやを構造的に不可能にする。」

★人が「まだやってます」と言えない。判定日は言われた瞬間に台帳へ焼かれ、
  その日が来たら機械が勝手に見に行って、勝手に赤にする。誰の許可も要らない。

━━ 何を見るか ━━
  status/shukudai/daicho.jsonl の状態（＝宿題台帳が正本）。
  さらに tools/oni_modoshi.py の検品結果があれば、そちらを優先する
  （自己申告の「完了」ではなく、機械が200を確認した「完了」だけを完了と読む）。

━━ 判定 ━━
  完了になっている          → 「返した」。実際どうなったかに証拠URLを書いて閉じる
  状態が言われた時から不変  → ★赤。P1に繰り上げて、その場で再発車する
  途中（走行中・確認待ち）  → 「動いてはいる」。赤にはしないが、1ヶ月判定では赤

★1ヶ月の判定日を過ぎてまだ返っていないものは、理由を問わず赤。例外を作らない。

使い方
    python3 tools/hantei.py              # 判定日が来たものを見に行く（心臓から1日1回）
    python3 tools/hantei.py --show
    python3 tools/hantei.py --self-test
"""
from __future__ import annotations

import datetime
import fcntl
import io
import json
import os
import re
import sys
import time
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

HATSUGEN = os.path.join(ST, "kioku", "hatsugen.jsonl")
DAICHO = os.path.join(ST, "shukudai", "daicho.jsonl")
KENPIN = os.path.join(ST, "oni_modoshi", "kenpin.jsonl")
LOG = os.path.join(ST, "kioku", "hantei.jsonl")

# 34533番で実測した事故：tools/kioku.py（8tickごと）と tools/hantei_hiduke.py
# （40tickごと）が、どちらも鍵なしで HATSUGEN を読む→書くしていた。
# kioku.pyがこのファイルを読んだ直後にhantei_hiduke.pyが判定して
# hanteiSumi（判定済みの印）を書き込んでも、kioku.pyが古い内容のまま
# 書き戻すと★その判定が消える（lost update）。消えると次の判定日チェックで
# 「まだ判定していない」扱いに戻り、★同じ案件を何度も★赤＋再発車してしまう
# （実例：id f81962a0e496「1件ずつの個別対応ではなく仕組み自体を作ってほしい」が
# 2026-10-02 01:03 と 01:34 の2回、どちらもhanteiSumiが空の状態から判定され、
# 2回とも再発車されていた＝queue.jsonに34530〜34533番という同一発言の重複案件が
# 積まれた直接の原因）。
# ★kioku.py側にも同じロック（同じファイルパス）を入れてある。
HATSUGEN_LOCK = os.path.join(ST, ".hatsugen.lock")


@contextmanager
def hatsugen_lock(timeout=10.0):
    f = io.open(HATSUGEN_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()

JST = datetime.timezone(datetime.timedelta(hours=9))
_YOUBI = "月火水木金土日"


def now():
    return datetime.datetime.now(JST)


def today():
    return now().strftime("%Y-%m-%d")


def stamp():
    return now().strftime("%Y-%m-%d %H:%M")


def norm(s):
    return re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "").lower()


# 34536番で実測した事故：この係(kuriageru)がP1に繰り上げて再発車するとき、
# queueのタイトルに「判定日赤｜」というプレフィックスを付ける
# （oni_modoshi.py側の差し戻しも「差し戻し｜」を付ける）。
# ★その再発車されたqueue案件がoni_modoshi.pyの検品を通って kenpin.jsonl に
# ok:true で記録されても、ima_no_jotai() はタイトルをそのまま norm() して
# キーにするため、プレフィックスが付いた分だけ元の発言(kioku由来)のキーと
# 食い違い、★二度とマッチしない。結果、仕組み自体（hantei_hiduke.py /
# oni_modoshi.py）が実装・動作していても、元の発言は「1ヶ月経っても未着手」
# のまま永久に赤判定→再発車を繰り返す（同一要望「1件ずつの個別対応ではなく
# 仕組み自体を作ってほしい」が34403/34480/34503/34533/34536/35588番として
# 積み上がっていたのが実例）。★1件ずつ直すのではなく、プレフィックスを剥がして
# 比較する側を直すのが「仕組み自体」の修正。
_SAIHASSHA_PREFIX = re.compile(r"^(判定日赤｜|差し戻し｜|【差し戻し】)+")


def kihon_title(t):
    """再発車のときに付くラベルのプレフィックスを剥がし、元の発言のキーに揃える。"""
    return _SAIHASSHA_PREFIX.sub("", t or "")


# ────────────────────────────── 34639番：セッション内完結の検出（恒久対策） ──
# DAICHOに一度も登録されない発言（hatsugen.jsonl直の行）が、その場で完結していても
# 機械に伝わらない問題（1996番の再発）への対応。元の会話ログ（r["from"]）を直接開き、
# 完了報告の有無と、その後の明確な否定の有無を見る。
_COMPLETION_KEYWORDS = ("完了しました", "できました", "直しました", "完了済み",
                        "やりました", "終わりました", "対応しました")
_DENIAL_KEYWORDS = ("まだ", "できてない", "直ってない", "ダメ", "だめ", "違う", "できない", "直ってなく")
_SESSION_LOG_CACHE = {}
_PROJECTS_DIRS_CACHE = None


def _projects_dirs():
    """~/.claude/projects 直下のディレクトリ一覧（1000件超）を1回だけ列挙してキャッシュする。
    判定日が来た件数ぶん毎回 os.listdir を回すと重くなる（34639番の実測でタイムアウトした）。"""
    global _PROJECTS_DIRS_CACHE
    if _PROJECTS_DIRS_CACHE is not None:
        return _PROJECTS_DIRS_CACHE
    base = os.path.expanduser("~/.claude/projects")
    try:
        _PROJECTS_DIRS_CACHE = [os.path.join(base, d) for d in os.listdir(base)]
    except Exception:
        _PROJECTS_DIRS_CACHE = []
    return _PROJECTS_DIRS_CACHE


def _find_session_log(from_name):
    """r["from"]（例: "e23675ff-....jsonl"）の実体を ~/.claude/projects/*/ から探す。
    毎回ディスクを掘らないよう、ディレクトリ一覧自体と名前→パスの結果を両方キャッシュする。"""
    if not from_name:
        return None
    if from_name in _SESSION_LOG_CACHE:
        return _SESSION_LOG_CACHE[from_name]
    path = None
    try:
        for d in _projects_dirs():
            cand = os.path.join(d, from_name)
            if os.path.exists(cand):
                path = cand
                break
    except Exception:
        path = None
    _SESSION_LOG_CACHE[from_name] = path
    return path


_SESSION_ROWS_CACHE = {}


def _load_session_rows(path):
    """会話ログ(jsonl)を1ファイル1回だけ読む。同じfromを持つhatsugen行が複数
    あっても、ファイルの再読み込み・再パースを繰り返さない（34639番の実測で
    タイムアウトした原因の1つ）。"""
    if path in _SESSION_ROWS_CACHE:
        return _SESSION_ROWS_CACHE[path]
    rows = []
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        rows = []
    _SESSION_ROWS_CACHE[path] = rows
    return rows


def _message_text(row):
    msg = row.get("message")
    if not isinstance(msg, dict):
        return "", None
    role = msg.get("role")
    content = msg.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                text += c.get("text", "")
    return text, role


def _jst_to_utc_iso(s):
    """r["firstSaid"]等 "2026-08-07 00:08"(JST) をログのtimestamp(UTC ISO)と
    比較できる形に変換する。パースできなければ None（＝絞り込まず全文を見る）。"""
    dt = parse_hi(s)
    if dt is None:
        return None
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _session_log_shows_completion(r, log_rows=None):
    """同一セッションログ内で、この発言（firstSaid）より後にassistantの完了報告が
    あり、その後のuser発言に明確な否定が続いていなければ True。
    log_rows を渡せばテスト用にファイルを経由せず判定できる。
    firstSaid以降に絞るのは、ファイル内のどこか別件の完了報告を拾って
    無関係な発言まで「完結済み」と誤判定しないため。"""
    rows = log_rows
    if rows is None:
        path = _find_session_log(r.get("from"))
        if not path:
            return False
        rows = _load_session_rows(path)
    since = _jst_to_utc_iso(r.get("firstSaid")) if log_rows is None else None
    completed = False
    denied_after = False
    for row in rows:
        if since:
            ts = row.get("timestamp") or ""
            if ts and ts < since:
                continue
        text, role = _message_text(row)
        if not text:
            continue
        if role == "assistant" and any(k in text for k in _COMPLETION_KEYWORDS):
            completed = True
            denied_after = False
            continue
        if completed and role == "user" and any(k in text for k in _DENIAL_KEYWORDS):
            denied_after = True
    return completed and not denied_after


def jsonl(p):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def append(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def kazu(text, label=""):
    """数字と断定の門への薄い橋渡し（919号で発見・修正）。

    kenpin_gate.py が `import hantei as _h; _h.kazu(text, label=...)` の形で呼ぶが、
    実体（KZ1〜KZ3の判定）は tools/kazu_gate.py にしかない（1018番「同じ規則を
    2か所に書いて片方だけ直った」を繰り返さないため、ここでは呼ぶだけにする）。
    このラッパー自体が長らく存在せず、呼び出し側が毎回 AttributeError で落ちていた。

    戻り値: dict(red=bool, blocked=str, line=str) ── kenpin_gate.py 側の期待形に合わせる。
    """
    try:
        import kazu_gate
    except Exception as e:  # noqa: BLE001
        return {"red": False, "blocked": "", "line": "（数字の門が読めません：%s）" % e}
    res = kazu_gate.judge(text or "")
    if res.get("ok"):
        return {"red": False, "blocked": "",
                "line": "%s: 数字%d件、全部に出どころがあります" % (label or "kazu", res.get("counted", 0))}
    parts = []
    for h in res.get("hits", []):
        one = "[%s] %s" % (h.get("code", ""), h.get("why", ""))
        if h.get("line"):
            one += "／その行: %s" % h["line"][:110]
        parts.append(one)
    return {"red": True, "blocked": "／[".join(parts), "line": label or "kazu"}


def ja_nichiji(dt):
    return "%s(%s) %s" % (dt.strftime("%Y-%m-%d"), _YOUBI[dt.weekday()], dt.strftime("%H:%M"))


def parse_hi(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(s)[:16], f).replace(tzinfo=JST)
        except Exception:
            continue
    return None


# ────────────────────────────────────────── いまの状態を見に行く


def ima_no_jotai():
    """題名 → いまの状態。★機械が確認した完了を、自己申告より上に置く。"""
    # 1451番実例（2026-09-28）：DAICHO に一度書き込まれた actionable は、
    # tools/shukudai.py sync() が再実行されるまで更新されない。ところが
    # shukudai.actionable() 側は1377番の教訓で「調べてみて、ちゃんと。」のような
    # 動詞抜きの相槌を actionable=False に直したのに、DAICHO 側の古い行は
    # actionable=True のまま残り、この係（hantei）が sync を待たずに独立して
    # DAICHO を読むせいで、直したはずのロジックが素通りして★赤＋再発車を
    # 繰り返していた（1385/1451/1849番で実測確認）。
    # ★sync() の実行タイミングに依存しないよう、ここで毎回 actionable() を
    # 呼び直して最新判定で上書きする。DAICHO の値はフォールバックにしか使わない。
    try:
        sys.path.insert(0, HERE)
        import shukudai as _shukudai
    except Exception:
        _shukudai = None
    by = {}
    for r in jsonl(DAICHO):
        act = r.get("actionable")
        if _shukudai is not None:
            try:
                act = _shukudai.actionable(r)
            except Exception:
                pass
        by.setdefault(norm(r.get("title"))[:24],
                      {"state": r.get("state") or "未着手", "evidence": r.get("evidence"),
                       "actionable": act})
    # 検品を通った（＝URLが200で中身が入っていた）ものだけ、完了に上書きしてよい
    for k in jsonl(KENPIN):
        if not k.get("ok"):
            continue
        key = norm(kihon_title(k.get("title")))[:24]
        if key:
            by[key] = {"state": "完了", "evidence": k.get("url"), "actionable": None}
    return by


def hantei_1ken(r, ima):
    """1件を判定する。返すのは（赤か、実際どうなったか、いまの状態）。"""
    key = norm(r.get("title"))[:24]
    in_daicho = key in ima
    cur = ima.get(key) or {"state": "未着手", "evidence": None, "actionable": None}
    st = cur["state"]
    t = today()
    w = r.get("hantei1w") or ""
    m = r.get("hantei1m") or ""
    kita = [x for x in (("1週間", w), ("1ヶ月", m))
            if x[1] and x[1] <= t and x[0] not in (r.get("hanteiSumi") or [])]
    if not kita:
        return None
    which = kita[-1][0]

    # 1370番実例（2026-09-27発見）：actionable=false（＝shukudai.pyが「具体的な
    # 作業指示が読み取れない発言」と既に判定済みの行）は、赤にしない・再発車しない。
    # 例：店主の発言「急ぎではないけど、この1週間以内にやってほしい。」は前置きだけで
    # 本体の要望が別の発言に含まれていたため、この行単体には実行対象が無い。
    # 既存の tomaranai.py（3回言わせた案件の繰り上げ）は actionable を見ているのに、
    # ここ（判定日の係）だけ見ておらず、実行不能なタスクを判定日のたびに★赤＋P1で
    # re発車させ続け、AIセッションが空回りする事故が起きていた。
    #
    # 1462番で「shukudai.actionable()を未確定(None)時のフォールバックに使う」案を
    # 試したが、self-test「テストの一手を直してほしい」がその判定器の粗い動詞リスト
    # （直す/作る/足す…）に一致せず誤って非タスク扱いになり自己試験がNGになったため
    # 撤回した。誤って赤を隠す方が、赤が多すぎることより悪い
    # （★1ヶ月の判定日を過ぎてまだ返っていないものは理由を問わず赤。例外を作らない、
    # という本ファイルの大原則に反するため）。actionable の判定は、明示的に
    # False と書き込まれた行にだけ適用する（＝ここでは変更しない）。
    if r.get("actionable") is False or cur.get("actionable") is False:
        return {"which": which, "aka": False, "state": st,
                "sonogo": "実行可能な要望が読み取れない発言のため判定対象外（再発車しない・要確認のまま残す）"}

    # 1996番実例（2026-10-01）：db49d38d7864（「あ、ダブルできてるんじゃなくて
    # 直してくれたんだね。」）のように、DAICHO（宿題台帳）に一度も登録されない
    # まま判定日を迎える hatsugen.jsonl 直の行には、上のチェック（r/curの
    # actionable）が一切届かない（DAICHOにこのidが無いため cur.actionable は
    # 常にNone）。1462番で shukudai.actionable() まるごと（_TASKISH込み）を
    # フォールバックに使うのは誤検知が広すぎて撤回されているので、ここでは
    # 粗い動詞判定を伴わない _NOT_TASK（明確な非タスク文言）への一致だけを、
    # 限定的に先に弾く。
    try:
        sys.path.insert(0, HERE)
        import shukudai as _shukudai_notask
        if _shukudai_notask._NOT_TASK.search(r.get("title") or ""):
            return {"which": which, "aka": False, "state": st,
                    "sonogo": "実行可能な要望が読み取れない発言のため判定対象外（再発車しない・要確認のまま残す）"}
    except Exception:
        pass

    # 34639番実例（2026-10-08）：円卓会議ノート5本の「書き直し」依頼は、DAICHO
    # （宿題台帳）に一度も登録されないまま、依頼した当日のうちに同一セッション内で
    # 実行・完了し、たまごさんも受領していた。それでも機械は完了を検知できず、
    # 2ヶ月後に「1ヶ月経っても未着手」と誤って★赤＋再発車した
    # （1996番と同じ根本原因の再発＝2回目）。
    # ★ DAICHO未登録の行だけに限定し、同一セッション内（元の発言と同じ from
    # ファイル）でassistantの完了報告があり、その後に明確な否定（まだ／ダメ等）
    # が続いていない場合だけ「セッション内で完結済み」とみなす。
    # 1462番の原則（「誤って赤を隠す方が、赤が多すぎることより悪い」）を壊さない
    # よう、完了報告と否定の有無を両方厳しく見てから外す（見逃し優先ではなく
    # 「その場で完結したことが確認できる場合」だけの限定的な例外）。
    if not in_daicho and st == "未着手" and _session_log_shows_completion(r):
        return {"which": which, "aka": False, "state": "完了（セッション内確認）",
                "sonogo": ("DAICHO未登録だが、同一セッション内でassistantの完了報告と"
                           "それに続く明確な否定の不在を確認できたため、赤判定・再発車の"
                           "対象外とした（34639番の恒久対策）")}

    if st == "完了":
        return {"which": which, "aka": False, "state": st,
                "sonogo": "返した（%s／%s）" % (cur.get("evidence") or "証拠URLなし", t)}
    if st in ("走行中", "確認待ち"):
        aka = (which == "1ヶ月")     # ★1ヶ月の判定日を過ぎて返っていなければ、途中でも赤
        return {"which": which, "aka": aka, "state": st,
                "sonogo": ("★%s経っても返っていない（%s のまま）" % (which, st)) if aka
                          else "%s後：まだ %s。返っていない" % (which, st)}
    # 未着手・止まっている・引き継ぎ ＝ 言われた時から1ミリも動いていない
    return {"which": which, "aka": True, "state": st,
            "sonogo": "★%s経っても %s のまま。1ミリも動いていない" % (which, st)}


def kuriageru(r, naze):
    """★自動でP1に繰り上げて、その場で再発車する。たまごさんに聞かない。"""
    try:
        import command_ingest
        # command_ingest.queue_add() が内部で queue_lock を取得する。
        # ここで同じ lock を外側から取ると自己デッドロックするため、二重取得しない。
        body = "\n".join([
            "【判定日で赤になった案件】%s" % r.get("title"),
            "【言われた日時】%s（%d回言われている）" % (r.get("firstSaidJa") or r.get("firstSaid"),
                                                    int(r.get("count") or 1)),
            "【なぜ赤か】%s" % naze,
            "【完了条件】本番URLが200で返り、中身が空でないこと。",
            "★自己申告では完了になりません（tools/oni_modoshi.py の検品を通ること）。",
            "たまごさんに質問しない。直して、URLを報告に貼る。",
        ])
        s, msg = command_ingest.queue_add(body, priority=1,
                                          label=("判定日赤｜" + (r.get("title") or ""))[:60],
                                          origin="user")
        return "%s:%s" % (s, msg)
    except Exception as e:
        return "failed:%s" % e


def hashiru(dry=False):
    # ★読む→書くの間、ずっと鍵をかける（kioku.pyと同じ鍵・同じファイル）。
    # これが無いと、kioku.pyの古い読み込みがこの関数の新しい書き込みを
    # 後から上書きして消す（lost update）。詳しい事故の実測はHATSUGEN_LOCK定義の
    # コメント参照。
    with hatsugen_lock():
        rows = {r["id"]: r for r in jsonl(HATSUGEN) if r.get("id")}
        ima = ima_no_jotai()
        mita, aka, tojita = 0, 0, 0
        for r in rows.values():
            h = hantei_1ken(r, ima)
            if not h:
                continue
            mita += 1
            r["state"] = h["state"]
            r["sonogo"] = h["sonogo"]
            r["hanteiAt"] = stamp()
            r["hanteiSumi"] = sorted(set((r.get("hanteiSumi") or []) + [h["which"]]))
            if h["aka"]:
                aka += 1
                r["aka"] = True
                r["p"] = 1                      # ★自動でP1に繰り上げ
                if not dry:
                    r["saihassha"] = kuriageru(r, h["sonogo"])
            else:
                r["aka"] = False
                if h["state"] == "完了":
                    tojita += 1
            if not dry:
                append(LOG, {"at": stamp(), "id": r["id"], "title": (r.get("title") or "")[:80],
                             "which": h["which"], "aka": h["aka"], "state": h["state"],
                             "sonogo": h["sonogo"]})
        if not dry and rows:
            body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                           for r in sorted(rows.values(),
                                           key=lambda x: (-int(x.get("count") or 1),
                                                          str(x.get("firstSaid") or ""))))
            write_text(HATSUGEN, body)
    return {"mita": mita, "aka": aka, "tojita": tojita, "zen": len(rows)}


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        ima = {}
        r = {"id": "x", "title": "テストの一手を直してほしい", "count": 1,
             "firstSaid": "2020-01-01 00:00", "hantei1w": "2020-01-08",
             "hantei1m": "2020-01-31", "hanteiSumi": []}
        h = hantei_1ken(r, ima)
        if not h or not h["aka"]:
            ng.append("判定日を過ぎた未着手が赤にならない")
        r2 = dict(r, hanteiSumi=["1週間", "1ヶ月"])
        if hantei_1ken(r2, ima) is not None:
            ng.append("判定済みをもう一度判定している")
        r3 = dict(r, hantei1w="2999-01-01", hantei1m="2999-01-01")
        if hantei_1ken(r3, ima) is not None:
            ng.append("判定日が来ていないのに判定している")
        # 1370番実例：actionable=falseは判定日が来ても赤にしない・再発車しない
        r4 = dict(r, id="y", title="急ぎではないけど、この1週間以内にやってほしい。",
                  actionable=False)
        h4 = hantei_1ken(r4, ima)
        if not h4 or h4["aka"]:
            ng.append("actionable=falseなのに赤／再発車の対象にしている（1370番の再発）")
        # 34536番の再発防止：「判定日赤｜」「差し戻し｜」プレフィックスを剥がせるか
        if kihon_title("判定日赤｜1件ずつの個別対応ではなく、仕組み自体を作ってほしい") \
                != "1件ずつの個別対応ではなく、仕組み自体を作ってほしい":
            ng.append("「判定日赤｜」プレフィックスを剥がせない（34536番の再発）")
        if kihon_title("差し戻し｜テスト") != "テスト":
            ng.append("「差し戻し｜」プレフィックスを剥がせない（34536番の再発）")
        # 34639番の再発防止：DAICHO未登録でもセッション内で完結していれば赤にしない
        rows_done = [
            {"message": {"role": "user", "content": "それを書き直してみてください。"}},
            {"message": {"role": "assistant", "content": "5本とも書き直し完了しました。"}},
            {"message": {"role": "user", "content": "ありがとう、ありがとうね。"}},
        ]
        if not _session_log_shows_completion({"from": "dummy"}, log_rows=rows_done):
            ng.append("セッション内完結の検出ができていない（34639番の再発防止）")
        rows_denied = [
            {"message": {"role": "assistant", "content": "直しました。"}},
            {"message": {"role": "user", "content": "まだ直ってないよ。"}},
        ]
        if _session_log_shows_completion({"from": "dummy"}, log_rows=rows_denied):
            ng.append("否定発言の後もセッション内完結と誤判定している（34639番の再発防止）")
        rows_none = [
            {"message": {"role": "user", "content": "それを書き直してみてください。"}},
        ]
        if _session_log_shows_completion({"from": "dummy"}, log_rows=rows_none):
            ng.append("完了報告が無いのにセッション内完結と誤判定している（34639番の再発防止）")
        # hantei_1ken経由の統合テスト：ログが見つからない時は従来通り赤のまま（見逃し優先にしない）
        r5 = {"id": "z", "title": "セッション内完結テスト用タイトルです", "count": 1, "from": "dummy-not-found.jsonl",
              "firstSaid": "2020-01-01 00:00", "hantei1w": "2020-01-08",
              "hantei1m": "2020-01-31", "hanteiSumi": []}
        h5 = hantei_1ken(r5, {})
        if not h5 or not h5["aka"]:
            ng.append("セッションログが見つからない時に誤って救済している（34639番の再発防止）")
        # 34536番の再発防止：再発車タイトル（プレフィックス付き）で検品合格した記録が
        # プレフィックス無しの元の発言キーに「完了」として反映されるか（実ファイルは汚さない）
        import tempfile
        fd, tmp_kenpin = tempfile.mkstemp()
        os.close(fd)
        _orig_kenpin = globals()["KENPIN"]
        try:
            append(tmp_kenpin, {"ok": True,
                                 "title": "判定日赤｜テスト専用の仕組み確認タイトルです",
                                 "url": "https://example.test/ok"})
            globals()["KENPIN"] = tmp_kenpin
            by = ima_no_jotai()
            key = norm("テスト専用の仕組み確認タイトルです")[:24]
            if (by.get(key) or {}).get("state") != "完了":
                ng.append("再発車タイトルの検品合格が元の発言キーに反映されない（34536番の再発）")
        finally:
            globals()["KENPIN"] = _orig_kenpin
            try:
                os.remove(tmp_kenpin)
            except Exception:
                pass
        s = hashiru(dry=True)
        print("自己試験：%s／台帳 %d件・判定日が来ている %d件（うち赤 %d）"
              % ("OK" if not ng else "NG", s["zen"], s["mita"], s["aka"]))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        rows = jsonl(LOG)
        print("【判定日の係】これまでに判定した %d件／うち赤 %d件"
              % (len(rows), len([r for r in rows if r.get("aka")])))
        for r in rows[-10:]:
            print("  %s %s … %s" % ("🔴" if r.get("aka") else "✅",
                                    (r.get("title") or "")[:40], r.get("sonogo")))
        return 0
    s = hashiru()
    print("判定日が来た %d件を見に行った → ★赤 %d件／返っていた %d件（台帳 %d件）"
          % (s["mita"], s["aka"], s["tojita"], s["zen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
