#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1142番：ループの計器盤。**工場に1つだけ置く「測るところ」。**

たまごさん（2026-09-25・仕事に出ている間）：
  「とにかく漏れが多すぎるから、もう仕組みで解決して。全部1個1個言いたくない。」
  「出す → 測る → 直す → また出す。測るところが無いと全部ただの作業。」

------------------------------------------------------------------
なぜ「45個目の係」ではなく、これを置くのか
------------------------------------------------------------------
2026-09-25 08:45 の実測：

  ・係は 44 本ある。そのうち **25 本が「走っているのに取れた0」**
    （status/kagi_daicho_counts.json に、ちゃんと数字で残っていた）
  ・今日の発車は 150 本。**全部「空回し」。本物は 0 本。**
  ・キューには 383 件。うち waiting 288 / hold 67 / stuck 13。
  ・ログインは 2026-09-20 04:30 から切れたまま **5日**。
    auth_keeper は 113 回それを見つけて、113 回ログに書いた。**1回も直せていない。**
  ・失敗台帳 failures.jsonl は **10日間1行も増えていない**（工場は毎日壊れているのに）。

  つまり、**足りないのは見張りではない。数字はもう全部どこかに書いてある。**
  足りないのは「全部の数字が1か所で突き合わさって、たまごさんの見る1枚に出る」こと。

  だから増やすのは見張りではなく **突き合わせ1か所**。
  （tools/kagi_daicho.py が「鍵」について既にやっていることを、工場全体に広げる）

------------------------------------------------------------------
測る6つ（これ以外を進捗表に出さない）
------------------------------------------------------------------
  ① 飴玉ゼロ率   … 走っているのに何も取れていない係の割合。**最上位の赤。**
  ② 嘘の完了     … 「完了」と書いてあるのに本番で確認が取れていない件数
  ③ 弾いた件数   … 門が実際に止めた数。**0が続いたら門が死んでいる＝赤**
  ④ 落ちた便     … 今日落ちた便の数
  ⑤ 返ってきてない … 言われたのに返事が返っていない件数
  ⑥ 週の枠       … 週クレジットの使用率

判定は自分で書かない。**tools/hantei.py の judge() 1本にだけ聞く。**
（同じ if を2か所に書いた時点で、必ず片方が嘘をつく）

------------------------------------------------------------------
戻し方（1行）
------------------------------------------------------------------
  python3 ~/Desktop/tamago-shinchoku/tools/1142_loop.py --modosu
"""
import io
import json
import os
import re
import subprocess
import sys
import datetime

JST = datetime.timezone(datetime.timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT = os.path.join(PUBLIC, "loop.json")
HIST = os.path.join(STATUS, "loop_history.jsonl")
LOG = os.path.join(STATUS, "loop.log")

try:
    import hantei
except Exception:                                    # hantei が壊れていても計器は動かす
    hantei = None


def _judge(runs, catches, blocked="", label=""):
    if hantei is not None:
        return hantei.judge(runs, catches, blocked=blocked, label=label)
    runs, catches = int(runs or 0), int(catches or 0)
    if blocked:
        return dict(red=True, mark="🔴", why="止められています：%s" % blocked,
                    runs=runs, catches=catches, blocked=blocked)
    if runs == 0:
        return dict(red=False, mark="⚪", why="まだ走っていません",
                    runs=runs, catches=catches, blocked="")
    if catches == 0:
        return dict(red=True, mark="🔴",
                    why="走った%d回 → 取れた0回。動いているのに何も産んでいません" % runs,
                    runs=runs, catches=catches, blocked="")
    return dict(red=False, mark="✅", why="走った%d回 → 取れた%d回" % (runs, catches),
                runs=runs, catches=catches, blocked="")


def _jload(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _now():
    return datetime.datetime.now(JST)


def ashiato(name, totta, blocked=""):
    """★足跡を、kagi_daicho が自分で見つけられる名前と形で置く。

    これを置かないと、この係自身が「跡を残していないので測れません」の赤になる。
    ＝**計器盤が45個目の見えない係になる**。いちばん間抜けな負け方なので必ず置く。
    lastProbeAt / lastCatchAt は kagi_daicho.CATCH_KEYS に入っている名前。
    """
    p = os.path.join(STATUS, "%s.json" % name)
    row = dict(lastProbeAt=time_now(), lastCatchAt=(time_now() if totta else None),
               totta=int(totta or 0), blocked=(blocked or ""),
               at=_now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        tmp = p + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except Exception:
        pass


def time_now():
    import time as _t
    return _t.time()


def _log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (_now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# ① 飴玉ゼロ率：走っているのに取れた0の係
#    ★たまごさん「動いているのに何も取れていない を最上位の赤にする」
# ════════════════════════════════════════════════════════════════
def ame_zero():
    c = _jload(os.path.join(STATUS, "kagi_daicho_counts.json"), {}) or {}
    ugoiteru, blind, names = 0, 0, []
    for k, v in c.items():
        if not isinstance(v, dict):
            continue
        runs = int(v.get("runs") or 0)
        if runs <= 0:
            continue                                  # 一度も走っていないものは母数に入れない
        ugoiteru += 1
        if int(v.get("catches") or 0) == 0:
            blind += 1
            names.append("%s(%d回)" % (k, runs))
    pct = round(blind * 100.0 / ugoiteru, 1) if ugoiteru else 0.0
    # 取れている係の数を「取れた」として judge に渡す＝全部塞がっていれば自動で赤
    r = _judge(ugoiteru, ugoiteru - blind, label="飴玉")
    return dict(key="ame", label="飴玉ゼロ率",
                value=pct, unit="%",
                sub="%d係中 %d係が「走っているのに取れた0」" % (ugoiteru, blind),
                mark=r["mark"], red=r["red"] or pct >= 50.0,
                why=r["why"], names=names[:40],
                nao="1142_fukkyuu.py が直せるものは直す。残りは名前を出す")


# ════════════════════════════════════════════════════════════════
# ② 嘘の完了：「完了」と書いてあるのに本番で確認が取れていない
# ════════════════════════════════════════════════════════════════
def uso_kanryou():
    d = _jload(os.path.join(STATUS, "dekimono.json"), {}) or {}
    items = d.get("items") or []
    bad = [i for i in items if not i.get("verified")]
    # キュー側の「完了と言って止まっているもの」も足す
    q = _jload(os.path.join(STATUS, "queue.json"), {}) or {}
    qitems = q.get("items") or []
    stuck = [i for i in qitems if str(i.get("status")) in ("stuck",)]
    n = len(bad) + len(stuck)
    return dict(key="uso", label="嘘の完了",
                value=n, unit="件",
                sub="できもの未検証%d件 ＋ 途中で固まった案件%d件" % (len(bad), len(stuck)),
                mark="🔴" if n > 0 else "✅", red=n > 0,
                why="本番で確認が取れていないものを「完了」と呼んでいる数",
                names=[str(i.get("title") or i.get("n"))[:48] for i in (bad + stuck)][:40],
                nao="検品を通すまで「完了」と書かせない（1142_kanmon.py）")


# ════════════════════════════════════════════════════════════════
# ③ 弾いた件数：門が実際に止めた数
#    ★たまごさん「弾いた数を必ず数える。弾き0が続いたら門が死んでいる＝赤」
# ════════════════════════════════════════════════════════════════
KANMON_LEDGERS = [
    ("仕入れの関所", "1142_kanmon.jsonl"),
    ("OGカードの門", "1133_og_kanmon.jsonl"),
    ("つなぎの門", "1131_kanmon_daicho.jsonl"),
    ("mainの門", "main_kanmon_daicho.jsonl"),
]


def hajiita(days=7):
    since = (_now() - datetime.timedelta(days=days)).isoformat()
    tooshi = hajiki = 0
    detail = []
    for label, fn in KANMON_LEDGERS:
        p = os.path.join(STATUS, fn)
        t = h = 0
        try:
            for line in io.open(p, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                at = str(r.get("at") or r.get("ts") or r.get("t") or "")
                if at and at < since:
                    continue
                ok = r.get("tsuuka")
                if ok is None:
                    ok = r.get("ok")
                if ok is False:
                    h += 1
                else:
                    t += 1
        except FileNotFoundError:
            detail.append("%s：台帳がまだ無い" % label)
            continue
        tooshi += t
        hajiki += h
        detail.append("%s：通した%d／弾いた%d" % (label, t, h))
    r = _judge(tooshi + hajiki, hajiki, label="門")
    return dict(key="hajiki", label="門が弾いた数",
                value=hajiki, unit="件",
                sub="直近%d日：通した%d／弾いた%d" % (days, tooshi, hajiki),
                mark=r["mark"], red=r["red"],
                why="通した数だけあって弾いた数が0なら、門は開けっぱなし＝死んでいる",
                names=detail,
                nao="弾き0が3日続いたら、わざと不正な1件を通して門の生死を実測する")


# ════════════════════════════════════════════════════════════════
# ④ 落ちた便
# ════════════════════════════════════════════════════════════════
def ochita_bin():
    o = _jload(os.path.join(STATUS, "ochita.json"), {}) or {}
    kieta = int(o.get("kietaN") or 0)
    lvl = str(o.get("level") or "")
    dansho = o.get("dansho") or []
    # 工場の実績（空回しは1本も数えない）
    honmono = kara = 0
    if hantei is not None:
        try:
            k = hantei.kojo(24)
            honmono, kara = k.get("honmono", 0), k.get("karamawashi", 0)
        except Exception:
            pass
    blocked = ""
    f = os.path.join(STATUS, "no_launch.flag")
    if os.path.exists(f):
        try:
            blocked = io.open(f, encoding="utf-8").read().strip()[:160]
        except Exception:
            blocked = "no_launch.flag があります"
    r = _judge(honmono + kara, honmono, blocked=blocked, label="発車")
    return dict(key="ochita", label="落ちた便",
                value=kieta, unit="本",
                sub="24時間：本物%d本／空回し%d本" % (honmono, kara),
                mark=r["mark"], red=r["red"] or kieta > 0,
                why=r["why"], names=list(dansho)[:10] or ([lvl] if lvl else []),
                nao="止め札の中身が「ログイン」なら 1142_fukkyuu.py が鍵の手順を出す")


# ════════════════════════════════════════════════════════════════
# ⑤ 言われたのに返ってきていない
# ════════════════════════════════════════════════════════════════
def kaettekonai():
    # ★正本は1138番の宿題台帳（status/public/shukudai.json）。無いときだけキューで代用する。
    s = _jload(os.path.join(PUBLIC, "shukudai.json"), None)
    if s:
        t = s.get("tally") or {}
        by = t.get("byState") or {}
        n = int(t.get("open") or 0)
        heri = int(t.get("closedToday") or 0)
        r = _judge(n + heri, heri, label="宿題")   # 今日1件も減っていなければ自動で赤
        return dict(key="kaeri", label="返ってきてない",
                    value=n, unit="件",
                    sub="今日 %d件 減った（%s）" % (heri, "／".join(
                        "%s%d" % (k, v) for k, v in list(by.items())[:4])),
                    mark=r["mark"], red=r["red"],
                    why="言われたのに、まだ返していない数。**今日1件も減らなければ赤**",
                    names=[str(i.get("title"))[:48] for i in (s.get("open") or [])][:40],
                    nao="減らない日が続くなら、原因は①か④（発車が止まっている）")
    q = _jload(os.path.join(STATUS, "queue.json"), {}) or {}
    items = q.get("items") or []
    waiting = [i for i in items if str(i.get("status")) == "waiting"]
    hold = [i for i in items if str(i.get("status")) == "hold"]
    # 「古い」＝3日以上動いていない waiting。ここが「言ったのに返ってきてない」の実体
    furui = []
    for i in waiting:
        lv = i.get("staleLevel")
        if lv:
            furui.append(i)
    n = len(waiting) + len(hold)
    return dict(key="kaeri", label="返ってきてない",
                value=n, unit="件",
                sub="順番待ち%d件／保留%d件（うち古い%d件）" % (len(waiting), len(hold), len(furui)),
                mark="🔴" if n > 50 else ("🟠" if n > 0 else "✅"),
                red=n > 50,
                why="言われたのに、まだ何も返していない数",
                names=[("%s %s" % (i.get("n"), str(i.get("title") or "")[:40]))
                       for i in (furui or waiting)][:40],
                nao="発車が0本の日は、この数字だけが増える。①が赤なら原因はそっち")


# ════════════════════════════════════════════════════════════════
# ⑥ 週の枠
# ════════════════════════════════════════════════════════════════
def waku():
    o = _jload(os.path.join(STATUS, "ochita.json"), {}) or {}
    w = (o.get("shuui") or {}).get("waku") or {}
    pct = w.get("allPct")
    if pct is None:
        return dict(key="waku", label="週の枠", value=None, unit="%",
                    sub="測れていません", mark="🔴", red=True,
                    why="枠が測れていない＝使い切っても気づけない", names=[],
                    nao="ochita.py の枠取得を直す")
    pct = float(pct)
    return dict(key="waku", label="週の枠",
                value=round(pct, 1), unit="%",
                sub="戻るのは %s" % (w.get("resetAt") or "不明"),
                mark="🔴" if pct >= 90 else ("🟠" if pct >= 70 else "✅"),
                red=pct >= 90,
                why="使い切ると、その週は本物が1本も出せない", names=[],
                nao="70%を超えたら Opus を止めて Sonnet だけにする")


# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# ⑦ 常駐が古い
#    ★2026-09-25 に実測で見つけた型：**心臓が3日前の自分を走らせていた。**
#      heartbeat.sh には「自分のファイルが書き換わったら自分で入れ替わる」が
#      2026-09-24 に入っていた。ところが走っているプロセスは 09-22 07:04 起動＝
#      **その入れ替わりの仕組みが入る前の自分**。だから永久に入れ替わらない。
#      ＝「直したのに反映されていない」の正体。人には絶対に見えない。
# ════════════════════════════════════════════════════════════════
def jouchuu_furui():
    import subprocess as _sp
    hb = os.path.join(REPO, "tools", "heartbeat.sh")
    try:
        fm = os.path.getmtime(hb)
    except OSError:
        return dict(key="jouchuu", label="常駐が古い", value=None, unit="",
                    sub="心臓のファイルが見つからない", mark="🔴", red=True,
                    why="心臓が無い", names=[], nao="heartbeat.sh を置き直す")
    # 起動時刻を取る（Macでのみ取れる。取れないときは赤にせず「測れない」と出す）
    started = None
    try:
        pid = _sp.run(["pgrep", "-f", "tools/heartbeat.sh"],
                      capture_output=True, text=True, timeout=10).stdout.split()
        if pid:
            o = _sp.run(["ps", "-o", "lstart=", "-p", pid[0]],
                        capture_output=True, text=True, timeout=10).stdout.strip()
            if o:
                started = o
                # ps の lstart は**そのMacの地方時**。UTC扱いすると9時間ずれて
                # 「-0.4日前」のような嘘が出る。素直に地方時として読む。
                started_ts = datetime.datetime.strptime(
                    " ".join(o.split()), "%a %b %d %H:%M:%S %Y").timestamp()
                furui = started_ts < fm
                hi = round((_now().timestamp() - started_ts) / 86400.0, 1)
                return dict(key="jouchuu", label="常駐が古い",
                            value=(1 if furui else 0), unit="本",
                            sub=("心臓は%s起動（%s日前）。ファイルは%s更新"
                                 % (o, hi,
                                    datetime.datetime.fromtimestamp(fm, JST)
                                    .strftime("%m-%d %H:%M"))),
                            mark="🔴" if furui else "✅", red=furui,
                            why=("★直したのに反映されていません。"
                                 "走っている心臓は書き換え前の自分です"
                                 if furui else "心臓は最新のファイルで走っています"),
                            names=[], nao="launchctl kickstart -k "
                                          "gui/$(id -u)/com.tamago.tamago-shinchoku.heartbeat")
    except Exception:
        pass
    return dict(key="jouchuu", label="常駐が古い", value=None, unit="",
                sub="起動時刻が測れない場所から見ています（Macから見ると測れます）",
                mark="⚪", red=False,
                why="測れないので判定しない（測れたふりをしない）",
                names=[str(started or "")], nao="")


def measure():
    cards = [ame_zero(), uso_kanryou(), hajiita(), ochita_bin(), kaettekonai(),
             waku(), jouchuu_furui()]
    # ★印と赤を必ず一致させる。「赤なのに✅」は、たまごさんが一番嫌う嘘の形
    for c in cards:
        if c["red"] and c["mark"] not in ("🔴",):
            c["mark"] = "🔴"
    akaN = sum(1 for c in cards if c["red"])
    # 一番上に出す一言。**①が赤なら必ず①を出す（最上位の赤）**
    atama = None
    for c in cards:
        if c["red"]:
            atama = c
            break
    out = dict(
        at=_now().strftime("%Y-%m-%d %H:%M:%S"),
        akaN=akaN,
        atama=(dict(label=atama["label"], value=atama["value"], unit=atama["unit"],
                    why=atama["why"], nao=atama["nao"]) if atama else None),
        hitokoto=("赤が%d個あります：%s" % (akaN, atama["label"])) if atama
                 else "赤はありません",
        cards=cards,
    )
    return out


def write(out):
    for d in (PUBLIC,):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    slim = dict(at=out["at"], akaN=out["akaN"],
                **{c["key"]: c["value"] for c in out["cards"]})
    with io.open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    # ★測れた枚数＝取れた数。0枚しか測れなければ、この係自身が赤になる
    ashiato("1142_loop", len(out["cards"]))
    _log("書きました 赤%d個 / %s" % (out["akaN"], out["hitokoto"]))


def modosu():
    """1コマンドで戻す。置いたファイルを消すだけ。本番のサイトには一切触らない。"""
    for p in (OUT, HIST, LOG,
              os.path.join(STATUS, "1142_kanmon.jsonl"),
              os.path.join(STATUS, "1142_fukkyuu.jsonl"),
              os.path.join(PUBLIC, "loop.json")):
        try:
            os.remove(p)
            print("消しました:", p)
        except FileNotFoundError:
            pass
    print("戻しました。index.html の計器盤は loop.json が無ければ自動で隠れます。")


if __name__ == "__main__":
    if "--modosu" in sys.argv:
        modosu()
        sys.exit(0)
    o = measure()
    write(o)
    if "--quiet" not in sys.argv:
        print(o["hitokoto"])
        for c in o["cards"]:
            print(" %s %s：%s%s  %s" % (c["mark"], c["label"], c["value"], c["unit"], c["sub"]))
