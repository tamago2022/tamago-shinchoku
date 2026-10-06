#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1173番【組み直し】予約を全部下ろして、たまごさんの完成版10本で入れ直す。

たまごさんの言葉（2026-09-27・原文）:
  「今入っている予約を全部下げる。特に今夜20:00の山口百恵『秋桜』、ニック・ドレイク、
    コピーが弱いものは全部取り消す。」
  「朝9:00＝日本の曲／夜21:00＝海外の曲。この順番は確定。」
  「大事なのはコピーと曲のチョイス。」
  「9月中に山下達郎を1本入れる。」

■ なぜ1回で走らないか（2026-09-27 19:20 実測）
  api.buffer.com へ1回だけ枠を確かめたところ
      HTTP 429 remaining=0 limit=250 window=24h retry-after=37971（＝2026-09-28 05:5x）
  旧REST（api.bufferapp.com）も試したが
      HTTP 401 "Public API tokens are not accepted for REST API access"
  ブラウザ（Chrome 7d965dae）の publish.buffer.com はログイン画面で、鍵を打つことはしない。
  → **今夜のうちにBufferへ触る道は1本も無い。** だからこの係は枠が戻った周回で1回だけ走る。

■ やること（順番も含めてこの通り）
  ① 予約を取り直す（1叩き）
  ② 取れた全部を status/1173/oroshita.json に控えてから消す（1本1叩き）
     ★出るまで15分を切っているものは触らない（過去に動かすと事故る）
  ③ status/1173/plan.json の10本を作る（1本1叩き）。過ぎた時刻のものは飛ばす。
     ★本文はたまごさんの完成版を1文字も書き替えない。動かすのはURLの行の位置だけ（1153番の型）。
  ④ 取り直して照合する（1叩き）。自己申告で「入れました」と言わない。
  合わせて 約23叩き。Buffer自身の枠は250／24hなので余裕がある。

■ 一度走ったら二度と走らない（status/1173/.stamp）
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import importlib
import buffer_kura      # noqa: E402
import buffer_waku      # noqa: E402
import kagi             # noqa: E402
irekae = importlib.import_module("1170_irekae")

JST = datetime.timezone(datetime.timedelta(hours=9))
D = os.path.join(REPO, "status", "1173")
PLAN = os.path.join(D, "plan.json")
OROSHITA = os.path.join(D, "oroshita.json")
STAMP = os.path.join(D, ".stamp")
LOG = os.path.join(D, "kumi_naoshi.jsonl")
SEIRETSU_STAMP = os.path.join(REPO, "status", "1171", ".stamp")


def now():
    return datetime.datetime.now(JST)


def kiroku(rec):
    rec = dict(rec)
    rec.setdefault("at", now().strftime("%F %T"))
    try:
        os.makedirs(D, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def kata(text):
    """1153番の型：URLを一番最後に置く。★言葉は1文字も書き替えない。"""
    try:
        import x_kata
        return x_kata.normalize(text or "")
    except Exception:
        return text or ""


def due_utc(s):
    y, mo, d = [int(x) for x in s[:10].split("-")]
    h, mi = [int(x) for x in s[11:16].split(":")]
    local = datetime.datetime(y, mo, d, h, mi, tzinfo=JST)
    return local.astimezone(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), local


def yomu_plan():
    p = json.load(io.open(PLAN, encoding="utf-8"))
    return p.get("hon") or []


def miru():
    """0叩き。何をどう組み直すかだけ出す。"""
    print("Bufferの枠:", buffer_waku.riyuu())
    print("今日の叩き:", buffer_kura.riyuu())
    y = buffer_kura.yoyaku_yomu()
    print("── いま入っているもの（控え %s 時点・%d 本）"
          % (y.get("at") or "-", len(y.get("yoyaku") or [])))
    for e in (y.get("yoyaku") or []):
        print("  ✕ %s  %s" % (e.get("due"), irekae.midashi(e.get("text"))))
    print("── 入れ直すもの")
    for e in yomu_plan():
        print("  ○ %s  %s  [%s]" % (e["due_jst"], e["midashi"], e["lang"]))
    return 0


def main():
    if "--miru" in sys.argv:
        return miru()
    if os.path.exists(STAMP) and "--now" not in sys.argv:
        return 0
    # ★1178番（2026-09-28）止め札。ChatGPTが先に入れた10本を消さないため。
    #   --now でも通れない＝手で叩いても止まる。剥がすのは札を消すときだけ。
    import buffer_tomeru
    _t = buffer_tomeru.tomete()
    if _t:
        print(_t)
        kiroku({"result": "止め札で退いた", "riyuu": _t})
        return 0
    if not buffer_waku.ake():
        # ★枠が閉まっている間は1叩きもしない。心臓から毎周回呼ばれてもここで退く。
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    hon = yomu_plan()
    org, chid = irekae.channel(tok)

    def hiku():
        e = ((irekae.gql(tok, irekae.Q_SCHED, {"o": org, "c": [chid]})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return sorted([x["node"] for x in e], key=lambda x: x.get("dueAt") or "")

    mae = hiku()

    # ── ② 控えてから下ろす
    hikae = []
    for p in mae:
        t = irekae.jst(p.get("dueAt") or "")
        hikae.append({"id": p.get("id"), "due": t.strftime("%F %H:%M") if t else "",
                      "midashi": irekae.midashi(p.get("text")),
                      "text": p.get("text")})
    os.makedirs(D, exist_ok=True)
    io.open(OROSHITA, "w", encoding="utf-8").write(json.dumps(
        {"_これは何": "★組み直しで下ろした予約の本文。消えて終わりにしないための控え。",
         "at": now().strftime("%F %T"), "hon": hikae}, ensure_ascii=False, indent=1))
    print("下ろすものの本文を控えた: %s（%d 本）" % (OROSHITA, len(hikae)))

    oroshita, nokoshita = [], []
    for p in mae:
        t = irekae.jst(p.get("dueAt") or "")
        mid = irekae.midashi(p.get("text"))
        if t and t <= now() + datetime.timedelta(minutes=15):
            nokoshita.append({"due": t.strftime("%F %H:%M"), "midashi": mid,
                              "naze": "出るまで15分を切っていたので触らなかった"})
            print("  … 触らない %s %s" % (t.strftime("%F %H:%M"), mid))
            continue
        r = irekae.gql(tok, irekae.M_DEL, {"input": {"id": p.get("id")}})
        dp = (r.get("data") or {}).get("deletePost") or {}
        ok = bool((dp.get("post") or {}).get("id"))
        oroshita.append({"midashi": mid, "ok": ok, "error": dp.get("message") or ""})
        print("  %s 下ろした %s %s" % ("○" if ok else "★失敗",
                                      t.strftime("%F %H:%M") if t else "?", mid))

    # ── ③ 入れ直す
    ireta = []
    for e in hon:
        iso, local = due_utc(e["due_jst"])
        if local <= now() + datetime.timedelta(minutes=5):
            ireta.append({"midashi": e["midashi"], "ok": False,
                          "error": "その時刻はもう過ぎている"})
            print("  … 飛ばす（時刻が過ぎている） %s %s" % (e["due_jst"], e["midashi"]))
            continue
        r = irekae.gql(tok, irekae.M_CREATE, {"input": {
            "text": kata(e["text"]), "channelId": chid, "assets": [],
            "needsApproval": False, "schedulingType": "automatic",
            "mode": "customScheduled", "dueAt": iso}})
        cp = (r.get("data") or {}).get("createPost") or {}
        pid = (cp.get("post") or {}).get("id")
        ireta.append({"midashi": e["midashi"], "due": e["due_jst"], "ok": bool(pid),
                      "id": pid, "error": cp.get("message") or ""})
        print("  %s 入れた %s %s" % ("○" if pid else "★失敗",
                                    e["due_jst"], e["midashi"]))

    # ── ④ 取り直して照合
    ato = hiku()
    print("── 組み直したあと（%d 本）" % len(ato))
    for p in ato:
        t = irekae.jst(p.get("dueAt") or "")
        print("  %s  %s" % (t.strftime("%F %H:%M") if t else "?",
                            irekae.midashi(p.get("text"))))
    buffer_kura.yoyaku_kaku({"cap": 10, "slots": ["09:00=ja", "21:00=en"],
                             "yoyaku": buffer_kura.naraberu(ato, irekae.jst)})

    machi_ok = sum(1 for x in ireta if x["ok"])
    kiroku({"result": "組み直した", "oroshita": oroshita, "nokoshita": nokoshita,
            "ireta": ireta, "n_mae": len(mae), "n_ato": len(ato)})
    try:
        io.open(STAMP, "w", encoding="utf-8").write(now().strftime("%F %T"))
        # ★1171（並べ直し）はもう要らない。同じ所を二度触らせない。
        os.makedirs(os.path.dirname(SEIRETSU_STAMP), exist_ok=True)
        io.open(SEIRETSU_STAMP, "w", encoding="utf-8").write(
            "1173で組み直したので不要 " + now().strftime("%F %T"))
    except Exception:
        pass
    print("入れ直せたもの %d / %d 本" % (machi_ok, len(hon)))
    return 0 if machi_ok == len(hon) else 9


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        kiroku({"result": "落ちた", "error": str(ex)[:300]})
        print("落ちた:", ex)
        sys.exit(1)
