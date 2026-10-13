#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1049番：入荷票を1枚作って、その場で門0・門3・門4を当てて、通ったら積む。

なぜ要るか
  仕入れの1件ごとに同じJSONを手で組み立てていると、書き落としが必ず出る。
  しかも門4（コピーの形）と門3（棚）はサンドボックス側でも当てられるのに、
  当てずに積むと Mac 側の便で落ちて、理由を見に行くまで分からない。
  → **積む前にこちらで当てる。**落ちたらその場で書き直す。

使い方（フジロックの名簿を出典にする形が一番短い）
  python3 tools/shiire_tsumu.py \
      --id a-flood-of-circle-beast-mode \
      --artist "a flood of circle" --title "Beast Mode（Music Video）" \
      --yt isCIYDqvoJI \
      --channel "a flood of circle Official Channel（youtube.com/@afoc_official）" \
      --moving "Music Video。静止画だけの動画ではない。" \
      --fact 'act|a flood of circle|FUJI ROCK,フジロック|https://www.fujirockfestival.com/artist/index|FUJI ROCK FESTIVAL の出演者一覧に載っている。' \
      --copy "..."

  --fact は  key|値|手がかり語(カンマ区切り)|出典URL(カンマ区切り)|主張  の5本で1件。何個でも並べられる。
  --dry を付けると積まずに判定だけ出す。
"""
import argparse, io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import nyuka_sekisho as N  # noqa: E402


def parse_fact(s):
    p = s.split("|")
    if len(p) < 5:
        raise SystemExit("--fact は key|値|手がかり語|出典URL|主張 の5本が要る: %r" % s)
    return {"key": p[0].strip(), "value": p[1].strip(),
            "needles": [x.strip() for x in p[2].split(",") if x.strip()],
            "src": [x.strip() for x in p[3].split(",") if x.strip()],
            "claim": "|".join(p[4:]).strip()}


def main():
    a = argparse.ArgumentParser()
    for k in ("id", "artist", "title", "yt", "copy"):
        a.add_argument("--" + k, required=True)
    a.add_argument("--channel", default="")
    a.add_argument("--moving", default="")
    a.add_argument("--fact", action="append", default=[])
    a.add_argument("--context", default="")
    a.add_argument("--dry", action="store_true")
    o = a.parse_args()

    facts = [parse_fact(s) for s in o.fact]
    item = {
        "id": o.id, "artist": o.artist, "title": o.title,
        "url": "https://www.youtube.com/watch?v=" + o.yt, "youtubeId": o.yt,
        "channel": o.channel, "movingPicture": o.moving,
        "facts": facts, "copy": o.copy,
        "context": [x for x in o.context.split(",") if x.strip()],
    }

    # ★門2は「key が performer の事実」が1件も無いと必ず保留にする（別人混入を止める関所）。
    #   実測：2026-09-24、key を act/song にして積んだ3件が全部この理由で hold に落ちた。
    #   Mac側で落ちてから気づくのは遅いので、ここで先に止める。
    if not any((f.get("key") or "") == "performer" for f in facts):
        print("★積まない。--fact の key に performer が1件も無い。")
        print("  門2（別人を止める関所）は『この曲を演っているのは本人か』の裏を要求する。")
        print("  例: --fact 'performer|<本人の名前>|<曲名>|<本人の公式サイトのURL>|"
              "本人の公式サイトに<曲名>が<本人の名前>名義で載っている。演っているのは本人。'")
        return 1

    ng = N.gate4_copy_shape(item["copy"], facts)
    shelves, rejected = N.gate3_context(facts, item["context"])
    print("門4: %s" % (ng or "OK"))
    print("門3: 付く棚 %s ／ 事実で裏打ちできず却下 %s" % (shelves or "（無し）", rejected or "（無し）"))
    if ng:
        print("★積まない。コピーを書き直すこと。")
        return 1
    if o.dry:
        print("（--dry なので積んでいない）")
        return 0

    tmp = "/tmp/_shiire_%s.json" % o.id
    json.dump(item, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return subprocess.call([sys.executable, os.path.join(HERE, "nyuka_sekisho.py"),
                            "--submit", "--json", tmp])


if __name__ == "__main__":
    sys.exit(main())
