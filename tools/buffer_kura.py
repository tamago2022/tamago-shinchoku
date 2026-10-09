#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【Bufferの蔵】叩いた回数を数える・IDと予約の中身を使い回す。

■ 2026-09-27 に実測で分かったこと（これが直しの理由）
  Bufferを叩いていたのは3か所。どれも「用が無くても心臓の周回で叩く」形だった。

    tools/1166_yotei.py        心臓の毎周回 →(10分間引き後) 1回につき4叩き = 1日 576回
    tools/1167_ireru1.py       心臓＋5分間引き            1回につき3〜4叩き = 1日 約1000回
    tools/1168_kenpin_hyou.py  1168_naosu が15分ごとに呼ぶ 1回につき4叩き = 1日 384回
                                                        ────────────────────
                                                          合わせて 1日 約2000回

  Bufferの枠は **24時間250回／15分100回**。だから16分で枠が尽き、
    x-ratelimit-remaining: 0 ／ Retry-After: 73274（約20時間）
  以後なにも予約できず、投入も取り直しも全部止まった。

  さらに、その叩きの **半分は「組織IDとチャンネルIDを探すため」だけ** に使っていた。
  IDは変わらないのに毎回2回聞いていた。丸ごと無駄。

■ ここが用意するもの（どれも「叩かずに済ませる」ため）
    tsukau(who)   叩く直前に通す門。1日の天井(NORI)を超えたら False＝叩かない。
                  同時に1回ぶん数える → 「1日何回叩いたか」を数字で出せる。
    kyou_nan_kai()今日ここまでに叩いた回数
    ch_yomu/ch_kaku      組織IDとチャンネルID（一度見つけたら以後0回）
    yoyaku_yomu/yoyaku_kaku 予約と「もう出たもの」の中身
                  ★画面を描くたびに聞きに行かない。描く係はこれを読むだけ＝0回。

■ 目標（実測の見込み）
    1日6回。朝と晩に1本出るたび「取り直し1・投入1・確かめ1」＝3回 × 2本。
    天井 NORI=20 は手で叩く分の余裕込み。ここに当たったらそれ以上叩かない＝
    二度と250回を使い切らない。

■ 使い方（叩く側に足すのはこれだけ）
    import buffer_kura
    def gql(tok, q, v=None):
        if not buffer_kura.tsukau("1167_ireru1"):
            raise RuntimeError(buffer_kura.riyuu())
        ...いつもの叩き...

  buffer_waku.py（429を受けたら閉める門）とは役割が別。両方通す。
  buffer_waku が「もう閉まっている」と言う間は tsukau も False を返す。
"""
import datetime
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURA = os.path.join(REPO, "status", "buffer_queue")
KAZU = os.path.join(KURA, ".tsukatta.json")     # 今日何回叩いたか
CH = os.path.join(KURA, ".channel.json")        # 組織ID・チャンネルID
YOYAKU = os.path.join(KURA, ".yoyaku.json")     # 予約と出たものの中身
JST = datetime.timezone(datetime.timedelta(hours=9))

# ★1日の天井（Buffer自身の枠は250回／24時間）
#   2026-09-27：たまごさんの指示で予約を丸ごと組み直す（tools/1173_kumi_naoshi.py）。
#   全部下ろす＋10本入れ直す＝1回きり約23叩き。20では途中で自分の門に止められるので
#   60へ上げていた。
#   ★2026-09-28（1178番）その組み直しは中止（ChatGPTが先に10本入れたので走らせない）。
#   23叩きを見込む用が無くなったので 20 へ戻す。天井が低い方が枠を殺しにくい。
NORI = 20


def _yomu(p, kara):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return kara


def _kaku(p, d):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(d, io.open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def _kyou():
    return datetime.datetime.now(JST).strftime("%F")


# ───────── 数える ─────────

def kyou_nan_kai():
    d = _yomu(KAZU, {})
    try:
        return int(d.get("n") or 0) if d.get("day") == _kyou() else 0
    except Exception:
        return 0


def _waku_shimatteru():
    """buffer_waku（429で閉める門）が閉まっていれば True。無ければ False。"""
    try:
        import buffer_waku
        return not buffer_waku.ake()
    except Exception:
        return False


def tsukau(who=""):
    """★叩く直前に必ず通す。叩いてよければ True（同時に1回ぶん数える）。"""
    if _waku_shimatteru():
        return False
    n = kyou_nan_kai()
    if n >= NORI:
        return False
    _kaku(KAZU, {"day": _kyou(), "n": n + 1, "nori": NORI,
                 "saigo": datetime.datetime.now(JST).strftime("%F %T"),
                 "who": who})
    return True


def riyuu():
    n = kyou_nan_kai()
    if n >= NORI:
        return ("★今日はもうBufferを %d 回叩いた（天井 %d 回）。"
                "日付が変わるまで1回も叩かない。" % (n, NORI))
    if _waku_shimatteru():
        try:
            import buffer_waku
            return buffer_waku.riyuu()
        except Exception:
            return "★Bufferの枠が閉まっている"
    return "叩ける（今日 %d 回／天井 %d 回）" % (n, NORI)


# ───────── 使い回す ─────────

def ch_yomu():
    """覚えてある {org, channel_id, name}。無ければ {}。"""
    d = _yomu(CH, {})
    return d if (d.get("org") and d.get("channel_id")) else {}


def ch_kaku(org, channel_id, name=""):
    return _kaku(CH, {"org": org, "channel_id": channel_id, "name": name,
                      "at": datetime.datetime.now(JST).strftime("%F %T")})


def ch_wasureru():
    try:
        os.remove(CH)
    except Exception:
        pass


def yoyaku_yomu():
    """{"at":.., "cap":10, "yoyaku":[{id,text,dueAt,due}], "dashita":[...]}"""
    return _yomu(YOYAKU, {})


def yoyaku_kaku(d):
    d = dict(d or {})
    d["at"] = datetime.datetime.now(JST).strftime("%F %T")
    return _kaku(YOYAKU, d)


def naraberu(posts, jst_henkan):
    """Bufferのnodeの並びを、蔵に入れる形へ。jst_henkan は dueAt→JSTの関数。"""
    out = []
    for p in posts or []:
        t = None
        try:
            t = jst_henkan(p.get("dueAt") or "")
        except Exception:
            t = None
        out.append({"id": p.get("id"), "text": p.get("text") or "",
                    "dueAt": p.get("dueAt"),
                    "due": t.strftime("%F %H:%M") if t else ""})
    return out


def sugita_mono(ima=None):
    """覚えている予約のうち、出る時刻を過ぎたもの（＝もう出たはず）。"""
    ima = ima or datetime.datetime.now(JST)
    out = []
    for y in (yoyaku_yomu().get("yoyaku") or []):
        try:
            t = datetime.datetime.strptime(y.get("due") or "", "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if t.replace(tzinfo=JST) <= ima:
            out.append(y)
    return out


if __name__ == "__main__":
    print(riyuu())
    print("覚えてあるチャンネル:", json.dumps(ch_yomu(), ensure_ascii=False))
    y = yoyaku_yomu()
    print("覚えてある予約: %d 本（%s 時点）／出たはず %d 本"
          % (len(y.get("yoyaku") or []), y.get("at") or "-", len(sugita_mono())))
