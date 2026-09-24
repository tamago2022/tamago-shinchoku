#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/inochi.py ── 命綱
================================================================
★穴を1つずつ塞ぐのではなく、パイプごと替えるための1枚。

これまで：止まったものを見つけるたびに、そのものを直す見張りを1本足してきた
（auth_watch / relay_watch / git_lock_reaper / launch_watchdog / heartbeat_watchdog …）。
見張りが増えるほど「見張り自身が黙って死んだ」ことに誰も気づかなくなった。

ここから：**全部を1つの台帳に載せる。**
  ① 生きている印を1箇所に集める（status/inochi_health.json）
     ※ status/health.json は machine_health.py が先に使っているので名前を分けた。
  ② 印が止まったら「死んだ」と1行残す（status/shinda.jsonl）
  ③ 死んだら人を待たずに起こす。**同じものが3回続けて死んだら起こすのをやめる。**
  ④ こちらでは絶対に直せない1点（ログイン切れ）だけを赤に出す。それ以外は黙って直す。

使い方
  python3 tools/inochi.py              # 1回まわす（心臓から30秒おきに呼ばれる）
  python3 tools/inochi.py --ikiteru X  # 常駐が自分で生存印を押す
  python3 tools/inochi.py --show       # いまの台帳を人が読む形で
  python3 tools/inochi.py --aka        # genzaichi用：人の手が要る行だけ返す
  python3 tools/inochi.py --selftest   # わざと止めて、自分で起きるかを実測する

決まり
  - auto_launcher.py はここから叩かない（対話待ちに落ちるため）。
  - たまごさんのファイルを消さない・動かさない。消すのは自分が作ったロック類だけ。
  - 課金しない。ブラウザを使わない。
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status")
HEALTH = os.path.join(ST, "inochi_health.json")   # 生存印（最終生存時刻）
SHINDA = os.path.join(ST, "shinda.jsonl")         # 死亡台帳（追記のみ）
STATE = os.path.join(ST, "inochi_state.json")     # 連続死亡回数・起こした回数
LOG = os.path.join(ST, "inochi.log")

MAC = sys.platform == "darwin"


# ────────────────────────────────────────────────────────────
# 小道具
# ────────────────────────────────────────────────────────────
def now():
    return time.time()


def ts(t=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t or now()))


def log(msg):
    try:
        os.makedirs(ST, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (ts(), msg))
    except Exception:
        pass


def _load(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _age(path):
    """ファイルの最終更新から何秒たったか。無ければ None。"""
    try:
        return now() - os.path.getmtime(path)
    except Exception:
        return None


def _sh(cmd, timeout=25):
    """短いシェル。失敗しても落ちない。(ok, 出力)"""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout, cwd=REPO)
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return False, str(e)


def _alive_pid(pidfile):
    try:
        pid = int(io.open(pidfile).read().strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
# ① 生きている印
# ────────────────────────────────────────────────────────────
def ikiteru(name, extra=None):
    """常駐・便・runner が「自分は生きている」と押す印。
    呼び方（python から）:  from inochi import ikiteru; ikiteru("gaibu_runner")
    呼び方（shell から）  :  python3 tools/inochi.py --ikiteru gaibu_runner
    """
    h = _load(HEALTH, {})
    rec = h.get(name) or {}
    rec["at"] = now()
    rec["atText"] = ts()
    if extra:
        rec.update(extra)
    h[name] = rec
    try:
        _save(HEALTH, h)
    except Exception:
        pass
    return True


def hakatta(name, ran=0, took=0):
    """走った回数／取れた回数を印に足す。
    ★「走った>0 なのに 取れた=0」を最悪の壊れ方として拾うため。"""
    h = _load(HEALTH, {})
    rec = h.get(name) or {}
    rec["at"] = now()
    rec["atText"] = ts()
    rec["ran"] = int(rec.get("ran", 0)) + int(ran)
    rec["took"] = int(rec.get("took", 0)) + int(took)
    h[name] = rec
    try:
        _save(HEALTH, h)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# 見張る対象（★止まり方8個がここに全部載る）
# ────────────────────────────────────────────────────────────
# probe   : () -> (生きているか, 何が見えたか)
# revive  : () -> (起こせたか, 何をしたか)      None なら起こせない
# hito    : True なら「人の手が要る」＝赤に出す。False なら黙って直す
# yurusu  : 何秒黙ったら死んだと見なすか

def _p_file(path, limit):
    def f():
        a = _age(path)
        if a is None:
            return False, "印そのものが無い（%s）" % os.path.basename(path)
        return a <= limit, "最終更新 %.0f秒前" % a
    return f


def _p_heartbeat():
    return _p_file(os.path.join(ST, ".heartbeat_progress"), 600)()


def _p_runner():
    """runnerの生死は『プロセスが居るか』ではなく
    『待ち行列に仕事があるのに拾っていないか』で見る。
    ★これが3番目の止まり方（03:35以降拾っていない）の正体。"""
    pend = os.path.join(ST, "gaibu_jobs", "pending")
    done = os.path.join(ST, "gaibu_jobs", "done")
    try:
        waiting = [x for x in os.listdir(pend) if x.endswith(".json")]
    except Exception:
        waiting = []
    if not waiting:
        return True, "待ち行列は空（仕事が無いだけ）"
    # 一番古い待ちが何秒待たされているか
    oldest = min(os.path.getmtime(os.path.join(pend, x)) for x in waiting)
    wait = now() - oldest
    # 既に done にあるのに pending に残っている＝取りこぼしの掃除も兼ねる
    for x in list(waiting):
        if os.path.exists(os.path.join(done, x)):
            try:
                os.remove(os.path.join(pend, x))
                log("runner: 済んだのに列に残っていた %s を外した" % x)
                waiting.remove(x)
            except Exception:
                pass
    if not waiting:
        return True, "済み分を列から外した"
    return wait <= 420, "%d件が最大%.0f秒待ち" % (len(waiting), wait)


def _p_karamawari():
    """★走った回数>0 なのに 取れた回数=0 ＝ 動いているのに何も産んでいない。
    黙って緑になるのが一番まずいので、ここで必ず赤にする。"""
    h = _load(HEALTH, {})
    r = h.get("gaibu_runner") or {}
    ran, took = int(r.get("ran", 0)), int(r.get("took", 0))
    if ran <= 0:
        return True, "まだ走っていない"
    if took > 0:
        return True, "走った%d／取れた%d" % (ran, took)
    return False, "走った%d本すべて空回し（取れた0本）" % ran


def _p_gitlock():
    lock = os.path.join(REPO, ".git", "index.lock")
    if not os.path.exists(lock):
        return True, "ロック無し"
    return False, "index.lock が %.0f秒 残っている" % (_age(lock) or 0)


def _r_gitlock():
    """★外し方は tools/git_lock_reaper.py が正本。ここで二重実装しない。
    （あちらは『mtimeが古い』『gitのプロセスが居ない』を確かめてから外す）"""
    lock = os.path.join(REPO, ".git", "index.lock")
    if (_age(lock) or 0) < 120:
        return False, "まだ新しい（走っている最中かもしれない）ので触らない"
    ok, out = _sh("python3 %s --quiet" % json.dumps(os.path.join(REPO, "tools", "git_lock_reaper.py")), timeout=60)
    # 自分（inochi）が置いた印の後始末も、ついでにここで。たまごさんのファイルには触らない。
    for gomi in (".git/_inochi_probe",):
        p = os.path.join(REPO, gomi)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    if not os.path.exists(lock):
        return True, "git_lock_reaper.py がロックを外した"
    return False, "git_lock_reaper.py を呼んだが、まだ残っている"


def _p_login():
    """Claudeのログイン切れ。★更新用の鍵が空＝また必ず切れる。
    これはこちらでは絶対に直せない唯一のもの。"""
    marks = []
    for name in ("auth_state.json", "auth_watch.json", "auth_keeper.json"):
        d = _load(os.path.join(ST, name), None)
        if isinstance(d, dict):
            marks.append(json.dumps(d, ensure_ascii=False))
    blob = " ".join(marks)
    # 飲み込まれがちな印は必ず表に出す
    NG = ("expired", "invalid_grant", "no_credential", "401", "403",
          "refresh", "revoked", "ログイン")
    hit = [w for w in NG if w in blob]
    # 現在地の紙が既に赤にしているならそれも拾う
    try:
        g = io.open(os.path.join(ST, "genzaichi.md"), encoding="utf-8").read()
        if "ログインが切れ" in g:
            hit.append("genzaichi:ログイン切れ")
    except Exception:
        pass
    if not hit:
        return True, "ログインは生きている"
    # ★真因は「更新用の鍵(refreshToken)が空」。だから切れたら自力で戻れない＝また必ず切れる。
    #   1年もつ鍵(setup-token)への入れ替えは `claude setup-token` が要るが、これは
    #   対話待ちのコマンドで、こちらからは叩けない（実測：auth_keeper.py の記録）。
    #   ＝できない。閉じている口は「対話待ちの setup-token 発行」。
    return False, ("いつものClaudeのアプリで1回ログインし直してください。"
                   "そのあと `claude setup-token` を1回だけ実行すると、1年切れなくなります"
                   "（この2つはこちらからは押せません）。印：%s"
                   % "・".join(sorted(set(hit))[:3]))


def _p_tunnel():
    """中継所（トンネル）。relay_watch.py が既に外から叩いて200を見ている。
    その結果の鮮度だけをここで見る。"""
    f = os.path.join(ST, "relay_watch.json")
    d = _load(f, None)
    if d is None:
        a = _age(f)
        return (a is not None and a < 1800), "relay_watchの記録が読めない"
    ok = bool(d.get("ok", d.get("alive", True)))
    return ok, "relay_watch=%s" % ("200が返る" if ok else "繋がらない")


def _r_tunnel():
    ok, out = _sh("python3 %s" % json.dumps(os.path.join(REPO, "tools", "relay_watch.py")))
    return ok, "relay_watch.py を走らせ直した"


def _p_kosession():
    """子セッションが途中で黙って死ぬ。落ちた記録がどこにも残らないのが問題なので、
    machine_health の reap 記録を正本にして、残骸が溜まっていないかを見る。"""
    f = os.path.join(ST, "machine_health.json")
    a = _age(f)
    if a is None:
        return True, "記録なし"
    return a < 1800, "machine_health が %.0f秒前" % a


def _r_kosession():
    ok, _ = _sh("python3 %s --reap" % json.dumps(os.path.join(REPO, "tools", "machine_health.py")), timeout=60)
    return ok, "machine_health.py --reap を走らせた"


def _p_yosan():
    """★予算の栓が0円のまま＝門が閉じたまま pending が溜まる。"""
    for name in ("budget.json", "yosan.json", "kazu_gate.json"):
        d = _load(os.path.join(ST, name), None)
        if isinstance(d, dict):
            for k in ("remainYen", "nokori", "cap", "limitYen", "yen"):
                if k in d:
                    try:
                        v = float(d[k])
                    except Exception:
                        continue
                    if v <= 0:
                        return False, "%s の %s が %s 円" % (name, k, v)
                    return True, "%s=%s円" % (k, v)
    return True, "栓の記録が無い（見送り）"


def _p_tsumi():
    """★積んだのに一度も走らない仕事（列の最後尾で永遠に来ない）。
    一番古い待ちが1時間を超えたら、列を積み直す。"""
    pend = os.path.join(ST, "gaibu_jobs", "pending")
    try:
        xs = [os.path.join(pend, x) for x in os.listdir(pend) if x.endswith(".json")]
    except Exception:
        return True, "列が無い"
    if not xs:
        return True, "列は空"
    old = now() - min(os.path.getmtime(x) for x in xs)
    return old < 3600, "最古の待ちが %.0f分" % (old / 60.0)


def _r_tsumi():
    """積み直し：一番古いものを列の先頭に出し直す（mtimeを更新するだけ。消さない）。"""
    pend = os.path.join(ST, "gaibu_jobs", "pending")
    try:
        xs = [os.path.join(pend, x) for x in os.listdir(pend) if x.endswith(".json")]
        xs.sort(key=os.path.getmtime)
        if not xs:
            return False, "積み直すものが無い"
        os.utime(xs[0], None)
        return True, "%s を積み直した" % os.path.basename(xs[0])
    except Exception as e:
        return False, str(e)


def _r_launchd(label):
    def f():
        if not MAC:
            return False, "Macでないので蹴れない"
        ok, out = _sh('launchctl kickstart -k "gui/$(id -u)/%s"' % label)
        return ok, "launchd %s を蹴り直した" % label
    return f


def _r_heartbeat():
    """心臓の起こし直し。★常駐は直しただけでは反映されない（走っているループは
    古いファイルを見続ける）ので、入れ替えたら必ず起こし直す。
    ただし auto_launcher.py は絶対にここから叩かない（対話待ちに落ちる）。"""
    if not MAC:
        return False, "Macでないので起こせない"
    ok, _ = _sh('launchctl kickstart -k "gui/$(id -u)/com.tamago.heartbeat"')
    if ok:
        return True, "launchdから心臓を起こし直した"
    ok2, _ = _sh('nohup bash %s >/dev/null 2>&1 &' % json.dumps(os.path.join(REPO, "tools", "heartbeat.sh")))
    return ok2, "heartbeat.sh を直接起こし直した"


def _r_runner():
    """runnerを1回まわす。常駐ではなく都度起動型なので、蹴れば列を拾う。"""
    ok, out = _sh("python3 %s --quiet" % json.dumps(os.path.join(REPO, "tools", "gaibu_runner.py")), timeout=120)
    return ok, "gaibu_runner.py を蹴った"


# ────────────────────────────────────────────────────────────
# ★1175番（2026-09-24）：発車の門を1か所にする
# ────────────────────────────────────────────────────────────
# なぜ足したのか（実測。推測ではない）
#   3本が同時に消えた便（status/ochita.jsonl 18件）を数えたら、
#     同時1本=落ちた回0/1回・2本=1/3回(33%)・3本=1/2回(50%)
#     4本=4/5回(80%)・6本=2/2回(100%)
#   落ちた回の容疑は12回すべて「ログイン切れ」。枠(waku)のNGは0回。
#   ＝**発車の門が2つに分かれていたのが本体。**
#     ① auto_launcher.py は status/no_launch.flag と status/launch_cap.json を見る
#     ② Dispatch（別の口）はどちらも見ない → 鍵が死んでいる間も便を出し続けた
#   しかも本数の数字が3か所にあった（実測 2026-09-24 14:45 の status/machine.json）：
#     safeMax=4 ／ cap=1・target=1（＝機械自身の実測は1本）／ calibratedSafeN=3
#     launch_cap.json は cap=5 で 2026-09-20 から更新が止まっていた（4日古い）
#   auto_launcher は min(safeMax, launch_cap.cap) = min(4,5) = **4本** を採った。
#   ＝機械が「1本」と測っているのに4本出した。今日4本走っていたのはこれ。
#
# だからこうする（1か所）
#   この係が status/public/hassha_gate.json を1枚だけ書く。
#   ★発車して良いか（鍵）と、何本までか（本数）を、同じ1枚に載せる。
#   ★launch_cap.json も同時に書き替える（auto_launcher が既に見ている口なので、
#     ここを正本にすれば launcher 側のコードを触らずに数字が1か所になる）。
#   ★古くならない：この係は心臓から30秒おきに呼ばれるので、毎回書き直る。
HASSHA_GATE = os.path.join(ST, "public", "hassha_gate.json")
LAUNCH_CAP = os.path.join(ST, "launch_cap.json")
KAZU_TENJO = 2      # ★実測の天井。3本以上は落ちる率50%超（上の数字）
KAZU_FURUI = 1800   # 門の紙が30分古くなったら書き直す


def _kazu_jissoku():
    """いま何本までが安全か。★機械が自分で測った数字だけを使う。無ければ天井。"""
    m = _load(os.path.join(ST, "machine.json"), {}) or {}
    moto = []
    kouho = [KAZU_TENJO]
    moto.append("実測の天井 %d本（status/ochita.jsonl 18件：3本で50%%・4本で80%%落ちた）" % KAZU_TENJO)
    for k in ("cap", "target", "calibratedSafeN", "safeMax"):
        v = m.get(k)
        if isinstance(v, int) and v > 0:
            kouho.append(v)
            moto.append("status/machine.json の %s=%d" % (k, v))
    n = max(1, min(kouho))
    return n, moto, m


def _p_kazu():
    """★本数の門。紙が無い／古い／天井より大きい＝門が壊れている。"""
    n, _, _ = _kazu_jissoku()
    g = _load(HASSHA_GATE, None)
    a = _age(HASSHA_GATE)
    if not isinstance(g, dict):
        return False, "門の紙が無い（%s）" % os.path.basename(HASSHA_GATE)
    if a is None or a > KAZU_FURUI:
        return False, "門の紙が %.0f分 古い" % ((a or 0) / 60.0)
    if int(g.get("maxParallel") or 99) > n:
        return False, "門の紙が %s本、実測は %d本（緩い方を向いている）" % (g.get("maxParallel"), n)
    c = (_load(LAUNCH_CAP, {}) or {}).get("cap")
    if not isinstance(c, int) or c > n:
        return False, "launch_cap.json が %s本、実測は %d本" % (c, n)
    return True, "門=%d本・紙は%.0f分前" % (n, (a or 0) / 60.0)


def _r_kazu():
    """★門を書き直す。これが「1か所」。人を待たない。"""
    n, moto, m = _kazu_jissoku()
    # 鍵（発車して良いか）も同じ紙に載せる。ここを見れば Dispatch も判断できる。
    nl = os.path.join(ST, "no_launch.flag")
    tomete = os.path.exists(nl)
    naze = ""
    if tomete:
        try:
            naze = io.open(nl, encoding="utf-8").read().strip()[:300]
        except Exception:
            naze = "status/no_launch.flag が置かれている（中身が読めない）"
    _save(HASSHA_GATE, {
        "at": ts(),
        "hasshaOK": (not tomete),
        "why": naze or "鍵は生きている",
        "maxParallel": n,
        "moto": moto,
        "machineMeasuredAt": m.get("measuredAt"),
        "note": ("★発車の門はこの1枚。auto_launcher も Dispatch もここだけを見る。"
                 "hasshaOK=false のあいだは本物を1本も出さない（出しても鍵が無いので必ず落ちる）。"
                 "maxParallel を超えて出さない。書いているのは tools/inochi.py の _r_kazu。"),
    })
    _save(LAUNCH_CAP, {
        "cap": n,
        "updatedAt": ts(),
        "why": "tools/inochi.py が実測から書いた（正本は status/public/hassha_gate.json）",
    })
    return True, "門を書き直した（%d本・発車%s）" % (n, "可" if not tomete else "止")


def hassha_gate():
    """他の便から呼ぶ入口。(発車して良いか, 何本まで, 理由)"""
    g = _load(HASSHA_GATE, {}) or {}
    return bool(g.get("hasshaOK")), int(g.get("maxParallel") or 1), g.get("why") or ""


MIHARI = [
    # name,            見出し,                      yurusu, probe,         revive,         hito
    ("kazu",           "発車の門（鍵と本数）",       10**9, _p_kazu,        _r_kazu,        False),
    ("heartbeat",      "心臓（30秒ごとの本体）",       600,  _p_heartbeat,   _r_heartbeat,   False),
    ("machine_status", "立て直しの便（5分便）",       1800,  _p_kosession,   _r_launchd("com.tamago.machine-status"), False),
    ("gaibu_runner",   "工場のrunner（待ち行列）",     420,  _p_runner,      _r_runner,      False),
    ("karamawari",     "空回し（走ったのに取れない）", 10**9, _p_karamawari,  None,           False),
    ("gitlock",        ".git/index.lock",            10**9, _p_gitlock,     _r_gitlock,     False),
    ("tunnel",         "中継所のトンネル",            1800,  _p_tunnel,      _r_tunnel,      False),
    ("kosession",      "子セッションの後始末",        1800,  _p_kosession,   _r_kosession,   False),
    ("yosan",          "予算の栓",                   10**9, _p_yosan,       None,           False),
    ("tsumi",          "積んだまま走らない仕事",      10**9, _p_tsumi,       _r_tsumi,       False),
    # ★ここだけ人の手が要る。こちらでは絶対に直せない。
    ("login",          "Claudeのログイン",           10**9, _p_login,       None,           True),
]

AKIRAMERU = 3   # ★同じものが3回続けて死んだら、起こすのをやめる


# ────────────────────────────────────────────────────────────
# ②③ 1周まわす
# ────────────────────────────────────────────────────────────
def mawasu(quiet=True):
    st = _load(STATE, {})
    aka = []       # 人の手が要る行
    kekka = []
    for name, midashi, yurusu, probe, revive, hito in MIHARI:
        try:
            alive, mieta = probe()
        except Exception as e:
            alive, mieta = False, "見に行けなかった: %s" % e

        s = st.get(name) or {"renzoku": 0, "okoshita": 0, "damedatta": 0, "sizumeta": False}

        if alive:
            if s.get("renzoku", 0) or s.get("sizumeta"):
                log("%s: 戻った（%s）" % (name, mieta))
            s["renzoku"] = 0
            s["sizumeta"] = False
            s["lastAlive"] = ts()
            kekka.append((name, midashi, "生", mieta, s))
            st[name] = s
            continue

        # ── 死んだ ──
        s["renzoku"] = int(s.get("renzoku", 0)) + 1
        _append(SHINDA, {
            "at": ts(), "name": name, "midashi": midashi,
            "mieta": mieta, "renzoku": s["renzoku"], "hito": hito,
        })

        if hito:
            # ★こちらでは絶対に直せないものだけ、赤に出す。
            aka.append("%s：%s" % (midashi, mieta))
            s["sizumeta"] = True
            st[name] = s
            kekka.append((name, midashi, "死(人の手)", mieta, s))
            continue

        if revive is None:
            s["sizumeta"] = True
            st[name] = s
            kekka.append((name, midashi, "死(起こす手が無い)", mieta, s))
            continue

        if s["renzoku"] > AKIRAMERU:
            # ★無限に起こし続けない。素材を替える判定に落とす。
            if not s.get("sizumeta"):
                log("%s: %d回続けて死んだので起こすのをやめた（素材を替える）" % (name, s["renzoku"]))
            s["sizumeta"] = True
            st[name] = s
            kekka.append((name, midashi, "死(諦め)", mieta, s))
            continue

        try:
            ok, shita = revive()
        except Exception as e:
            ok, shita = False, "起こしに行けなかった: %s" % e
        s["okoshita"] = int(s.get("okoshita", 0)) + 1
        if not ok:
            s["damedatta"] = int(s.get("damedatta", 0)) + 1
        log("%s: 死んだ（%s）→ %s（%s）" % (name, mieta, shita, "起こせた" if ok else "駄目だった"))
        s["lastRevive"] = ts()
        st[name] = s
        kekka.append((name, midashi, "死→起こした" if ok else "死→起こせず", "%s / %s" % (mieta, shita), s))

    _save(STATE, st)
    ikiteru("inochi")

    # 人の手が要る行だけを外に出す口
    _save(os.path.join(ST, "inochi_aka.json"), {"at": ts(), "aka": aka})

    if not quiet:
        for name, midashi, kind, mieta, s in kekka:
            print("%-14s %-26s %-14s %s" % (name, midashi, kind, mieta))
    return aka, kekka


def aka_lines():
    """genzaichi.py から呼ぶ。★人の手が要る1点だけを返す。"""
    d = _load(os.path.join(ST, "inochi_aka.json"), {})
    return list(d.get("aka") or [])


def show():
    h = _load(HEALTH, {})
    st = _load(STATE, {})
    print("── 生きている印 ──")
    for k, v in sorted(h.items()):
        a = now() - float(v.get("at", 0))
        ex = ""
        if "ran" in v:
            ex = "  走った%s／取れた%s" % (v.get("ran"), v.get("took", 0))
        print("  %-16s %6.0f秒前%s" % (k, a, ex))
    print("── 起こした記録 ──")
    for k, v in sorted(st.items()):
        print("  %-16s 連続死%s 起こした%s 駄目%s %s"
              % (k, v.get("renzoku", 0), v.get("okoshita", 0),
                 v.get("damedatta", 0), "【諦め】" if v.get("sizumeta") else ""))
    print("── 人の手が要る ──")
    for a in aka_lines() or ["（なし）"]:
        print("  " + a)


# ────────────────────────────────────────────────────────────
# ★実証：わざと止めて、自分で起きることを見せる
# ────────────────────────────────────────────────────────────
def selftest():
    """実測。★起きなかったものは「起きなかった」と書く。
    本物の心臓は止めない（たまごさんの工場を止めるわけにいかない）ので、
    同じ判定・同じ起こし方を、別の場所に作った偽物の工場でまわして測る。"""
    import tempfile
    out = []

    def sokutei(midashi, shikake, probe, revive, matsu=30):
        t0 = time.time()
        shikake()
        alive0, m0 = probe()
        if alive0:
            out.append((midashi, None, "止められなかった（%s）" % m0))
            return
        ok, shita = revive()
        # 起きたか？
        byou = None
        for _ in range(matsu):
            alive, m = probe()
            if alive:
                byou = time.time() - t0
                break
            time.sleep(1)
        if byou is None:
            out.append((midashi, None, "起きなかった（%s／%s）" % (m0, shita)))
        else:
            out.append((midashi, byou, shita))

    # ① .git/index.lock を置く → 自分で外すか
    #   ★本物の .git に偽ロックを置くと、外し損ねたときに本物の心臓の自動コミットを
    #     止めてしまう。なので偽物の .git を作ってそこで測る。判定と外し方は同じ関数。
    niwa = tempfile.mkdtemp(prefix="inochi-selftest-")
    nise_git = os.path.join(niwa, ".git")
    os.makedirs(nise_git, exist_ok=True)
    nise_lock = os.path.join(nise_git, "index.lock")

    def p_lock():
        if not os.path.exists(nise_lock):
            return True, "ロック無し"
        return False, "index.lock が %.0f秒 残っている" % (now() - os.path.getmtime(nise_lock))

    def r_lock():
        if now() - os.path.getmtime(nise_lock) < 120:
            return False, "まだ新しいので触らない"
        os.remove(nise_lock)
        return True, "index.lock を外した"

    def shikake():
        io.open(nise_lock, "w").write("inochi-selftest")
        os.utime(nise_lock, (now() - 300, now() - 300))   # 120秒の猶予を越えた状態
    sokutei(".git/index.lock を置く", shikake, p_lock, r_lock, matsu=5)
    shutil.rmtree(niwa, ignore_errors=True)   # ★自分が作った庭だけ片付ける

    # ② 待ち行列に仕事を積んで、runnerが拾わない状態を作る → 積み直すか
    pend = os.path.join(ST, "gaibu_jobs", "pending")
    os.makedirs(pend, exist_ok=True)
    jid = "inochi-selftest-%d" % int(now())
    jf = os.path.join(pend, jid + ".json")

    def shikake2():
        _save(jf, {"jobId": jid, "kind": "_selftest", "payload": {},
                   "queuedAt": ts(), "queuedFrom": "inochi-selftest"})
        os.utime(jf, (now() - 7200, now() - 7200))       # 2時間前から待っている状態
    sokutei("列の最後尾で来ない仕事", shikake2, _p_tsumi, _r_tsumi, matsu=5)
    try:
        os.remove(jf)   # ★自分が作ったものだけ片付ける
    except Exception:
        pass

    # ③ 生存印を止める → 死んだと判定して台帳に残るか（起こす先は偽物）
    nise = os.path.join(ST, ".inochi_selftest_alive")
    io.open(nise, "w").write("")
    os.utime(nise, (now() - 9999, now() - 9999))
    probe3 = _p_file(nise, 60)
    n0 = sum(1 for _ in io.open(SHINDA, encoding="utf-8")) if os.path.exists(SHINDA) else 0

    def revive3():
        io.open(nise, "w").write("")
        return True, "印を押し直した（常駐の再起動に相当）"
    sokutei("常駐が黙る（生存印が止まる）", lambda: None, probe3, revive3, matsu=5)
    try:
        os.remove(nise)
    except Exception:
        pass

    # ④ ★起こしても起きないものを、3回でちゃんと諦めるか。
    #   （今日の実測：心臓が launchctl kickstart を17秒おきに無限に打ち続けていた。
    #     この「無限に起こし続ける」を止められることを、ここで数字で見せる。）
    st_bak = _load(STATE, {})
    okoshita = {"n": 0}
    name = "_selftest_okinai"
    MIHARI.append((name, "起きない常駐（わざと）", 10**9,
                   lambda: (False, "わざと死なせている"),
                   lambda: (okoshita.__setitem__("n", okoshita["n"] + 1), (False, "起こしたが起きない"))[1],
                   False))
    try:
        for _ in range(8):
            mawasu(quiet=True)
        s = (_load(STATE, {}) or {}).get(name) or {}
        out.append(("起きない常駐を8回まわす",
                    0.0 if s.get("sizumeta") and okoshita["n"] <= AKIRAMERU else None,
                    "8回まわして起こしたのは%d回でやめた（諦め=%s）"
                    % (okoshita["n"], "はい" if s.get("sizumeta") else "いいえ")))
    finally:
        MIHARI.pop()
        st_now = _load(STATE, {})
        st_now.pop(name, None)
        _save(STATE, st_now)

    # ⑤ ★発車の門をわざと緩める（本数を9本に書き換える）→ 自分で締め直すか
    #   （2026-09-24 の実害：launch_cap.json が4日古い cap=5 のまま残り、
    #     機械が「1本」と測っている横で4本出た。同じことが起きないかを機械で見る）
    mae_gate = _load(HASSHA_GATE, None)
    mae_cap = _load(LAUNCH_CAP, None)
    try:
        _save(LAUNCH_CAP, {"cap": 9, "updatedAt": ts(), "why": "inochi-selftest（わざと緩めた）"})
        _save(HASSHA_GATE, {"at": ts(), "hasshaOK": True, "maxParallel": 9,
                            "why": "inochi-selftest（わざと緩めた）"})
        sokutei("発車の門をわざと9本に緩める", lambda: None, _p_kazu, _r_kazu, matsu=3)
        n, _, _ = _kazu_jissoku()
        ima = (_load(LAUNCH_CAP, {}) or {}).get("cap")
        out.append(("門の数字が実測どおりに戻る",
                    0.0 if ima == n else None,
                    "launch_cap.json=%s本／実測=%d本" % (ima, n)))
    finally:
        # ★自分が書き換えたものは、実測どおりの正しい値で締め直して終わる（緩いまま残さない）
        _r_kazu()
        _ = (mae_gate, mae_cap)

    print("── わざと止めた実測 ──")
    for midashi, byou, shita in out:
        if byou is None:
            print("  %-28s ✗ %s" % (midashi, shita))
        else:
            print("  %-28s ✓ %.1f秒で復帰（%s）" % (midashi, byou, shita))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--ikiteru":
        ikiteru(a[1] if len(a) > 1 else "unknown")
    elif a and a[0] == "--hakatta":
        # --hakatta <name> <走った> <取れた>
        hakatta(a[1], int(a[2]), int(a[3]))
    elif a and a[0] == "--show":
        show()
    elif a and a[0] == "--aka":
        for x in aka_lines():
            print(x)
    elif a and a[0] == "--selftest":
        selftest()
    else:
        mawasu(quiet=("--quiet" in a))
