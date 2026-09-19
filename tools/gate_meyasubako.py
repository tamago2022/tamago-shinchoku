#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目安箱（FeedbackDoor）＋フレンドテスト（FriendTest）の門番。

たまごさんの指示（2026-09-19）：
  「他のページも全部調べてないけれど、上に出ることはもうなくしてください。」
  「目安箱とフレンドテストは統合済みの1ブロック。分けない。ダブらせない。
    最後はストップモーション。」

954番で見つかった事故は「watch.tsx の中で <FeedbackDoor /> が
緑の見出しの <section> の“中”に置かれていた」。つまり
「ページごとに好きな場所へ置ける」状態が原因であって、置き場所を1回直しても
次のページで同じことが起きる。だから場所を直すのではなく、
**ページ側に置くこと自体を禁止する**。

判定（すべて機械判定・解釈の余地なし）:

  規則1 一元化  <FeedbackDoor / <FriendTest を書いてよいのは
                src/routes/__root.tsx と src/components/FriendTest.tsx だけ。
                それ以外のファイルに1個でもあればFAIL。
  規則2 順序    __root.tsx の中で <Outlet → <FriendTest → <JoyReliefFooterLoop
                の順に並んでいること（ストップモーションが最後）。
  規則3 重複    <FriendTest は __root.tsx にちょうど1個。
  規則4 入れ子  (保険) どのファイルでも、見出し／ヒーローらしき容れ物
                (<section> <header> や hero/gradient 系クラスのdiv) の
                “中”に目安箱があればFAIL。規則1をすり抜けた時の二重の網。

使い方:
    python3 tools/gate_meyasubako.py --repo /path/to/joy-relief-station
    python3 tools/gate_meyasubako.py --files a.tsx b.tsx      # 単体チェック
    python3 tools/gate_meyasubako.py --selftest               # 自己テスト

終了コード: 0=通過 / 1=違反あり
"""

import argparse
import io
import os
import re
import sys

TARGETS = ("FeedbackDoor", "FriendTest")

# 書いてよい場所（リポジトリルートからの相対パス）
ALLOWED = {
    "src/routes/__root.tsx": ("FriendTest",),          # ここだけが設置場所
    "src/components/FriendTest.tsx": ("FeedbackDoor",),  # 統合ブロックの中身
    "src/components/FeedbackDoor.tsx": (),              # 定義そのもの
}

USE_RE = re.compile(r"<\s*(FeedbackDoor|FriendTest)\b")
TAG_RE = re.compile(r"<\s*(/?)([A-Za-z][A-Za-z0-9]*)([^>]*?)(/?)>", re.S)

# 「見出し／ヒーローの箱」とみなすもの
BOX_TAGS = {"section", "header", "article", "aside"}
HERO_CLASS_RE = re.compile(
    r"(hero|bg-gradient|from-emerald|from-green|bg-emerald|bg-green|"
    r"rounded-3xl|border-b|sticky|top-0)",
    re.I,
)


def _strip_comments(src):
    """JSXコメント {/* ... */} と // 行コメントを空白に潰す（位置は保つ）。"""
    out = list(src)

    def blank(a, b):
        for i in range(a, b):
            if out[i] != "\n":
                out[i] = " "

    for m in re.finditer(r"\{\s*/\*.*?\*/\s*\}", src, re.S):
        blank(m.start(), m.end())
    for m in re.finditer(r"/\*.*?\*/", src, re.S):
        blank(m.start(), m.end())
    for m in re.finditer(r"(?m)//[^\n]*", src):
        blank(m.start(), m.end())
    return "".join(out)


def _line_of(src, pos):
    return src.count("\n", 0, pos) + 1


def check_nesting(path, src):
    """規則4：見出し／ヒーローの箱の中に目安箱が入っていないか。"""
    bad = []
    stack = []  # (tagname, line, is_hero)
    for m in TAG_RE.finditer(src):
        closing, name, attrs, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        low = name.lower()
        if name in ("FeedbackDoor", "FriendTest") and not closing:
            hero = [s for s in stack if s[2]]
            if hero:
                bad.append(
                    "%s:%d  <%s /> が <%s>（%d行目・見出し／ヒーローの箱）の中にある"
                    % (path, _line_of(src, m.start()), name, hero[-1][0], hero[-1][1])
                )
            continue
        # div は開閉の対応を正しく追えない（属性なしの </div> が大量にある）ので
        # 数えない。section/header/article/aside だけを見る。これで954番の事故
        # （<section> の中に目安箱）は確実に捕まえられ、誤検出は出ない。
        if low not in BOX_TAGS:
            continue
        if selfclose == "/":
            continue
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0].lower() == low:
                    del stack[i:]
                    break
        else:
            stack.append((low, _line_of(src, m.start()), True))
    return bad


def check_file(rel, src):
    """1ファイル分の判定。(違反リスト, 使用箇所リスト) を返す。"""
    src = _strip_comments(src)
    uses = [(m.group(1), _line_of(src, m.start())) for m in USE_RE.finditer(src)]
    bad = []

    allowed = ALLOWED.get(rel.replace(os.sep, "/"))
    if allowed is None:
        for name, line in uses:
            bad.append(
                "%s:%d  <%s /> をページ側に置いている。"
                "目安箱は __root.tsx の1箇所だけ（規則1）" % (rel, line, name)
            )
    else:
        for name, line in uses:
            if name not in allowed:
                bad.append(
                    "%s:%d  このファイルに <%s /> は置けない（規則1）" % (rel, line, name)
                )

    bad += check_nesting(rel, src)
    return bad, uses


FUNC_RE = re.compile(r"(?m)^\s*(?:export\s+)?(?:default\s+)?function\s+([A-Za-z0-9_]+)\s*\(")


def _blocks(src):
    """ファイル中のトップレベル function を (名前, 開始, 終了) で返す。"""
    starts = [(m.group(1), m.start()) for m in FUNC_RE.finditer(src)]
    out = []
    for i, (name, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else len(src)
        out.append((name, s, e))
    return out


def _mount_tag_for(src, tag):
    """`tag` が RootComponent 直下に無い場合、それを内側に持つ関数名（＝設置タグ）を返す。"""
    blocks = _blocks(src)
    for name, s, e in blocks:
        if name == "RootComponent":
            continue
        if re.search(r"<\s*%s\b" % tag, src[s:e]):
            return name
    return tag


def check_root(rel, src):
    """規則2・3：__root.tsx の並び順と個数。

    <FriendTest /> は RoomRecommendationsMount のような別関数の中に書かれていて、
    RootComponent ではその関数名のタグで設置されることがある。行番号をそのまま
    比べると誤判定になるので、RootComponent の本体の中だけで、
    「実際に画面へ出している方のタグ」の位置を比べる。"""
    src = _strip_comments(src)
    bad = []

    body = src
    for name, s, e in _blocks(src):
        if name == "RootComponent":
            body = src[s:e]
            offset = s
            break
    else:
        offset = 0

    friend_tag = "FriendTest"
    if not re.search(r"<\s*FriendTest\b", body):
        friend_tag = _mount_tag_for(src, "FriendTest")

    def first(tag):
        m = re.search(r"<\s*%s\b" % tag, body)
        return m.start() + offset if m else -1

    n_friend = len(re.findall(r"<\s*FriendTest\b", src))
    if n_friend == 0:
        bad.append("%s  <FriendTest /> が無い。目安箱がどのページにも出なくなる（規則3）" % rel)
    elif n_friend > 1:
        bad.append("%s  <FriendTest /> が %d 個ある。ダブらせない（規則3）" % (rel, n_friend))

    p_outlet, p_friend, p_loop = first("Outlet"), first(friend_tag), first("JoyReliefFooterLoop")
    if p_outlet >= 0 and p_friend >= 0 and p_friend < p_outlet:
        bad.append(
            "%s:%d  目安箱（<%s />）が <Outlet />（%d行目）より上にある。"
            "本文より上に目安箱が出る（規則2）"
            % (rel, _line_of(src, p_friend), friend_tag, _line_of(src, p_outlet))
        )
    if p_loop >= 0 and p_friend >= 0 and p_loop < p_friend:
        bad.append(
            "%s:%d  ストップモーション <JoyReliefFooterLoop /> が 目安箱（<%s />・%d行目）"
            "より上にある。最後はストップモーション（規則2）"
            % (rel, _line_of(src, p_loop), friend_tag, _line_of(src, p_friend))
        )
    return bad


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def scan_repo(repo):
    bad, checked, uses_all = [], 0, []
    src_dir = os.path.join(repo, "src")
    if not os.path.isdir(src_dir):
        return ["%s に src/ が無い。リポジトリのルートを --repo に渡す" % repo], 0, []
    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".output", "dist")]
        for fn in sorted(filenames):
            if not fn.endswith((".tsx", ".jsx")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, repo).replace(os.sep, "/")
            src = read(full)
            checked += 1
            if "FeedbackDoor" not in src and "FriendTest" not in src:
                continue
            b, u = check_file(rel, src)
            bad += b
            uses_all += [(rel, n, l) for n, l in u]
            if rel == "src/routes/__root.tsx":
                bad += check_root(rel, src)
    return bad, checked, uses_all


# ---------------------------------------------------------------------------
# 自己テスト：954番で実際に起きた事故のコードで「捕まえられるか」を確かめる
# ---------------------------------------------------------------------------
BAD_SAMPLE = """
import { FeedbackDoor } from "@/components/FeedbackDoor";
export function Watch() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-emerald-50">
      <h1>ごきげん補給所</h1>
      <FeedbackDoor />
    </section>
  );
}
"""

GOOD_ROOT = """
export function RootComponent() {
  return (
    <div>
      <div className="min-h-[100svh] w-full"><Outlet /></div>
      <div className="max-w-3xl mx-auto px-6 pb-16"><FriendTest /></div>
      <JoyReliefFooterLoop />
      <BottomTabNav />
    </div>
  );
}
"""

BAD_ROOT = """
export function RootComponent() {
  return (
    <div>
      <FriendTest />
      <div className="min-h-[100svh] w-full"><Outlet /></div>
      <JoyReliefFooterLoop />
    </div>
  );
}
"""


INDIRECT_ROOT_GOOD = """
function RoomRecommendationsMount() {
  return (<><OtherRoomsStrip /><FriendTest /></>);
}
function RootComponent() {
  return (
    <div>
      <div className="min-h-[100svh] w-full"><Outlet /></div>
      <RoomRecommendationsMount />
      <JoyReliefFooterLoop />
      <BottomTabNav />
    </div>
  );
}
"""

INDIRECT_ROOT_BAD = """
function RoomRecommendationsMount() {
  return (<><OtherRoomsStrip /><FriendTest /></>);
}
function RootComponent() {
  return (
    <div>
      <div className="min-h-[100svh] w-full"><Outlet /></div>
      <JoyReliefFooterLoop />
      <RoomRecommendationsMount />
    </div>
  );
}
"""


def selftest():
    fails = []

    if check_root("src/routes/__root.tsx", INDIRECT_ROOT_GOOD):
        fails.append("別関数ごしの正しい設置を誤ってFAILにした")
    if not check_root("src/routes/__root.tsx", INDIRECT_ROOT_BAD):
        fails.append("ストップモーションが目安箱より上なのを見逃した")

    b, _ = check_file("src/routes/watch.tsx", BAD_SAMPLE)
    if len(b) < 2:
        fails.append("事故サンプルを捕まえられない（規則1と規則4の両方で出るはず）: %r" % b)

    b = check_root("src/routes/__root.tsx", GOOD_ROOT)
    b2, _ = check_file("src/routes/__root.tsx", GOOD_ROOT)
    if b or b2:
        fails.append("正しい__root.tsxを誤ってFAILにした: %r %r" % (b, b2))

    b = check_root("src/routes/__root.tsx", BAD_ROOT)
    if not b:
        fails.append("Outletより上のFriendTestを見逃した")

    # コメントの中の <FeedbackDoor /> は違反にしない
    b, _ = check_file("src/routes/x.tsx", "{/* <FeedbackDoor /> は置かない */}\nconst a=1;\n")
    if b:
        fails.append("コメント内の記述を違反と誤判定した: %r" % b)

    for f in fails:
        print("NG  " + f)
    if fails:
        return 1
    print("OK  自己テスト6件すべて通過（事故サンプル検出／正常系素通し／順序違反検出／別関数ごしの設置／ストップモーション最後／コメント誤検出なし）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    bad, checked, uses = [], 0, []
    if a.repo:
        bad, checked, uses = scan_repo(a.repo)
    elif a.files:
        for p in a.files:
            rel = p.replace(os.sep, "/")
            for k in ALLOWED:
                if rel.endswith(k):
                    rel = k
                    break
            src = read(p)
            checked += 1
            b, u = check_file(rel, src)
            bad += b
            uses += [(p, n, l) for n, l in u]
            if rel == "src/routes/__root.tsx":
                bad += check_root(rel, src)
    else:
        ap.error("--repo か --files か --selftest のどれかを渡す")

    print("=== 目安箱の門番 ===")
    print("見たファイル: %d 枚 ／ 目安箱の使用箇所: %d 件" % (checked, len(uses)))
    for rel, name, line in uses:
        print("  - %s:%d  <%s />" % (rel, line, name))
    if bad:
        print("")
        print("NG  違反 %d 件" % len(bad))
        for b in bad:
            print("  ✗ " + b)
        print("")
        print("直し方：ページ側の <FeedbackDoor /> を消すだけでよい。")
        print("        目安箱は src/routes/__root.tsx が全ページに1回出している。")
        return 1
    print("")
    print("OK  目安箱が本文より上に出ているページは 0 枚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
