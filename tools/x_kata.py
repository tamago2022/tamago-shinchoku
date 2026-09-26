#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1153番【Xの投稿の型】URLを必ず一番最後に置く係。

たまごさん（2026-09-26）:
  「PCだとリンクが2回出てくる。統一できないかな。」
  → 2回に見える原因のうち **こちらで直せる分** は「本文の中にURLの文字列が残る」こと。
     Xは本文の末尾にあるURLからカードを作るとき、そのURLの文字列を本文から隠す。
     URLの後ろに1文字でもあると（＝末尾でないと）、カードを出した上に文字列も残る。
     出典: https://support.typefully.com/en/articles/8718061-about-links-at-the-end-of-tweets
            https://devcommunity.x.com/t/hide-url-in-final-tweet/79495

★型は文章で書いても守られないので、機械が並べ替える（憲法20：仕組み化の義務）。
★中身（言葉）は1文字も書き替えない。動かすのは「URLの行の位置」だけ。
★通信は一切しない。0円。

使い方:
    python3 tools/x_kata.py --check "<本文>"     # 型に合っているか（合っていれば終了コード0）
    python3 tools/x_kata.py --fix   "<本文>"     # 直した本文を出す
    python3 tools/x_kata.py --self-test          # 自分で自分を測る
"""
import re
import sys

URL_RE = re.compile(r"https?://[^\s]+")


def urls(text):
    return URL_RE.findall(text or "")


def check(text):
    """末尾がURLで終わっていれば True。URLが1本も無い本文も True（対象外）。"""
    t = (text or "").rstrip()
    if not urls(t):
        return True
    return bool(re.search(r"https?://[^\s]+$", t))


def normalize(text):
    """URLを本文から抜き、一番最後の行に戻す。

    ・URLが複数あるときは、出てきた順で最後にまとめる（1行1本）。
    ・URLだけの行は行ごと消す（空行が残らないようにする）。
    ・行の途中にあるURLは、その1本だけを抜いて残りの言葉はその場に残す。
    ・すでに末尾がURLなら、1文字も触らずそのまま返す。
    """
    src = (text or "").rstrip()
    found = urls(src)
    if not found or check(src):
        return src

    out_lines = []
    for line in src.split("\n"):
        stripped = line.strip()
        if stripped and URL_RE.fullmatch(stripped):
            continue                                  # URLだけの行 → 行ごと退避
        new_line = URL_RE.sub("", line)               # 行の途中のURLだけ抜く
        new_line = re.sub(r"[ \t]{2,}", " ", new_line).rstrip()
        out_lines.append(new_line)

    # URLの行を抜いたぶん空行が3つ以上続くので、空行は1つに畳む（段落の切れ目は保つ）
    squeezed = []
    for line in out_lines:
        if not line.strip() and squeezed and not squeezed[-1].strip():
            continue
        squeezed.append(line)
    out_lines = squeezed
    while out_lines and not out_lines[-1].strip():
        out_lines.pop()

    body = "\n".join(out_lines).rstrip()
    tail = "\n".join(found)
    return (body + "\n" + tail) if body else tail


LIMIT = 280
YOHAKU = 278          # ここまでで止める（ぴったり280は事故りやすいので2文字ぶん残す）


def omosa(text):
    """★1166番：Xの数え方で何文字ぶんか（Bufferがこの数で弾く）。

    実測でわかったこと（2026-09-27・Bufferの返事）:
      「Invalid post: Twitter / X posts cannot exceed 280 characters.」
    Xは素の文字数で数えない。
      ・URLは何文字あっても **23** として数える
      ・日本語・中国語・韓国語・絵文字は **1文字が2** として数える
    出典: https://developer.x.com/en/docs/counting-characters
    """
    t = URL_RE.sub("U" * 23, text or "")
    n = 0
    for ch in t:
        o = ord(ch)
        if (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0xA4CF or 0xA960 <= o <= 0xA97F
                or 0xAC00 <= o <= 0xD7FF or 0xF900 <= o <= 0xFAFF
                or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFF60
                or 0xFFE0 <= o <= 0xFFE6 or 0x1F300 <= o <= 0x1FAFF
                or 0x20000 <= o <= 0x3FFFD):
            n += 2
        else:
            n += 1
    return n


def nagasa_ok(text):
    """長さが通るか。通らないなら (False, 理由) を返す。"""
    n = omosa(text)
    if n > YOHAKU:
        return False, "Xの数え方で%d文字（上限%d）" % (n, LIMIT)
    return True, ""


def _self_test():
    ok = True
    # ★長さの数え方（1166番・実測で弾かれた2本をそのまま形にした）
    if omosa("https://joy-relief-station.lovable.app/cover-guide?artist=a&song=b") != 23:
        ok = False
        print("NG（URLは23で数える）")
    if omosa("あいう") != 6:
        ok = False
        print("NG（日本語は1文字2で数える）")
    if nagasa_ok("あ" * 200)[0]:
        ok = False
        print("NG（長すぎるのに通した）")
    cases = [
        # (入力, 期待)
        ("あ\n\nhttps://x.test/a\n\n#tag",
         "あ\n\n#tag\nhttps://x.test/a"),
        ("つかみ\n\n曲 — 人\n\nコピー\n\nhttps://x.test/a\n\n#a #b",
         "つかみ\n\n曲 — 人\n\nコピー\n\n#a #b\nhttps://x.test/a"),
        ("もう正しい形\n\n#a\nhttps://x.test/a",
         "もう正しい形\n\n#a\nhttps://x.test/a"),
        ("URLなし\n\n#a", "URLなし\n\n#a"),
        ("行の途中に https://x.test/a がある文\n\n#a",
         "行の途中に がある文\n\n#a\nhttps://x.test/a"),
    ]
    for src, want in cases:
        got = normalize(src)
        if got != want:
            ok = False
            print("NG\n入力: %r\n期待: %r\n実際: %r" % (src, want, got))
        if not check(got) and urls(got):
            ok = False
            print("NG（直したのに末尾がURLでない）: %r" % got)
    print("自己テスト: " + ("全部通った" if ok else "落ちた"))
    return 0 if ok else 1


def main():
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    mode, text = sys.argv[1], sys.argv[2]
    if mode == "--check":
        good = check(text)
        print("型に合っている（末尾がURL）" if good else "★型に合っていない（URLが末尾でない）")
        sys.exit(0 if good else 1)
    if mode == "--fix":
        sys.stdout.write(normalize(text) + "\n")
        sys.exit(0)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
