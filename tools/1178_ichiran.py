#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1178番【Bufferの実データを見るだけの係】読むだけ。1回きり。最大3叩き。

■ なぜ要るか（2026-09-28 たまごさんの指示）
  「Bufferの実データを叩いて、今入っている予約を一覧で取り、上の10件と一致するか確認。
    重複や余計な予約があれば消す。API呼び出しは最小限（1日250回の枠を食い潰さない）。」
  「今後、補充する前に必ずBufferの実データを見る形にする。ローカルの数え札を信じない。」

■ 叩く回数（実測の設計。これ以上は叩かない）
    組織ID・チャンネルID … status/buffer_queue/.channel.json に覚えてあれば **0叩き**
                            覚えていない初回だけ 2叩き
    予約一覧              … 1叩き
    ＝ 合計 1〜3叩き。天井は buffer_kura.NORI。

■ 書くことは何もしない
  ★createPost / deletePost / editPost はこのファイルに1行も無い。
  消すのはたまごさんが一覧を見て「これを消す」と言ってから、別の係でやる。

■ 出すもの
  status/1178/ichiran.json  … Bufferが返した生の一覧（id・dueAt・本文）
  status/1178/ichiran.txt   … 人が読む1枚（待つ10件との照合つき）
  status/buffer_queue/.yoyaku.json … 控えも上書きする（画面を描く係は0叩きで読める）

■ 使い方
    python3 tools/1178_ichiran.py          … 見る（枠が閉まっていれば0叩きで退く）
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
import buffer_kura   # noqa: E402
import buffer_waku   # noqa: E402
import kagi          # noqa: E402
irekae = importlib.import_module("1170_irekae")

JST = datetime.timezone(datetime.timedelta(hours=9))
D = os.path.join(REPO, "status", "1178")
OUT_JSON = os.path.join(D, "ichiran.json")
OUT_TXT = os.path.join(D, "ichiran.txt")
STAMP = os.path.join(D, ".stamp")   # ★一度取れたら二度と叩かない

# ★たまごさんがChatGPT側で入れたと言った10件（2026-09-28）。照合の物差し。
#   （時刻JST, 探す文字）。本文の中にこの文字があれば「その1本」と見る。
MATSU = [
    ("2026-09-28 09:00", "OOJA"),
    ("2026-09-28 21:00", "Marvin Gaye"),
    ("2026-09-29 09:00", "エイリアンズ"),
    ("2026-09-29 21:00", "k.d. lang"),
    ("2026-09-30 09:00", "スローバラード"),
    ("2026-09-30 21:00", "Carole King"),
    ("2026-10-01 09:00", "秋桜"),
    ("2026-10-01 21:00", "Nat King Cole"),
    ("2026-10-02 09:00", "さよなら夏の日"),
    ("2026-10-02 21:00", "Earth, Wind"),
]
# ★ChatGPTが「死亡動画の疑い」で外したもの。入っていたら赤で出す（消しはしない）。
HAZUSHITA = ["駅"]


def main():
    # ★心臓の毎周回から呼ばれる。一度ちゃんと取れたら以後は0叩きで退く。
    if os.path.exists(STAMP) and "--now" not in sys.argv:
        return 0
    if not buffer_waku.ake():
        print("RETRY 枠が閉まっているので1叩きもしていない：%s" % buffer_waku.riyuu())
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    mae = buffer_kura.kyou_nan_kai()
    org, chid = irekae.channel(tok)          # 覚えてあれば0叩き
    e = ((irekae.gql(tok, irekae.Q_SCHED, {"o": org, "c": [chid]})
          .get("data") or {}).get("posts") or {}).get("edges") or []
    ps = sorted([x["node"] for x in e], key=lambda x: x.get("dueAt") or "")
    tataita = buffer_kura.kyou_nan_kai() - mae

    naraberu = buffer_kura.naraberu(ps, irekae.jst)
    os.makedirs(D, exist_ok=True)
    json.dump({"at": datetime.datetime.now(JST).strftime("%F %T"),
               "tataita": tataita, "n": len(ps), "yoyaku": naraberu},
              io.open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    buffer_kura.yoyaku_kaku({"cap": 10, "slots": ["09:00=ja", "21:00=en"],
                             "yoyaku": naraberu})

    L = []
    L.append("Bufferの実データ（%s 時点・叩いた回数 %d）"
             % (datetime.datetime.now(JST).strftime("%F %T"), tataita))
    L.append("いま入っている予約：%d 本" % len(ps))
    L.append("")
    for x in naraberu:
        L.append("  %s  %s" % (x["due"] or "?", irekae.midashi(x["text"])))

    # ── 重複（同じ時刻が2本／同じ本文が2本）
    toki, honbun, kasanari = {}, {}, []
    for x in naraberu:
        toki.setdefault(x["due"], []).append(x)
        honbun.setdefault((x["text"] or "").strip(), []).append(x)
    for k, v in toki.items():
        if len(v) > 1:
            kasanari.append("★同じ時刻に %d 本：%s" % (len(v), k))
    for k, v in honbun.items():
        if len(v) > 1:
            kasanari.append("★同じ本文が %d 本：%s" % (len(v), irekae.midashi(k)))

    # ── 待つ10件との照合
    tarinai, yobun = [], list(naraberu)
    for due, sagasu in MATSU:
        hit = [x for x in yobun if x["due"] == due and sagasu in (x["text"] or "")]
        if hit:
            yobun.remove(hit[0])
        else:
            tarinai.append("%s %s" % (due, sagasu))

    L.append("")
    L.append("── 照合（たまごさんが言った10件）")
    L.append("  一致 %d / 10" % (10 - len(tarinai)))
    for t in tarinai:
        L.append("  ✕ 無い： %s" % t)
    for x in yobun:
        L.append("  ？ 余分： %s %s" % (x["due"] or "?", irekae.midashi(x["text"])))
    L.append("")
    L.append("── 重複")
    L += ["  " + k for k in (kasanari or ["  無し"])]
    L.append("")
    L.append("── 外したはずのもの")
    for w in HAZUSHITA:
        naka = [x for x in naraberu if w in (x["text"] or "")]
        L.append("  %s「%s」" % ("★まだ入っている" if naka else "入っていない（OK）", w))
    L.append("")
    L.append("★この係は読むだけ。1本も消していない・足していない。")

    txt = "\n".join(L)
    io.open(OUT_TXT, "w", encoding="utf-8").write(txt + "\n")
    try:
        io.open(STAMP, "w", encoding="utf-8").write(
            datetime.datetime.now(JST).strftime("%F %T"))
    except Exception:
        pass
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
