#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""904番：【仕組み⑪】着手前に「絵1枚 or ABCD」で解釈を合わせる（間違いを100→10に）

たまごさんの言葉（2026-09-17 00:35）：
  「間違いを100個やって100個修正してるのって、間違いがなければクレジットを全く減らさないで
   いいってことだからね。100間違えてんだったら10にしようよ。まず50に。4分の1に。0に近づけよう。」
  「多少の確認をしていいよ。『こういう解釈で良いですか』ってスクショ1枚見せるだとか、
   『これをこうしたいんですか』ってABCD見せるだとか。したら、間違いのズレはなくなるんじゃないの？」
  「俺の言葉だけじゃないわけじゃん。汲み取ってやってくれてるなと思って、めちゃくちゃ見当違いな
   ことで作業進めてたっていうのは無駄。それは俺にも落ち度があるから、そこの確認はしていいよ。」
  「そこの確認も分かりやすい確認してね。文字がいっぱいあってっていうんじゃなく。」

★ルールの変更点（既存の「確認するな」ルールとは別軸。必ず区別する）
  - 「やっていいですか」＝許可の確認は、今まで通りゼロ（第一条・自律走行は変わらない）。
  - 「私はこう理解しました。合ってますか」＝解釈の確認は、取ってよい。むしろ取る。

★「汲み取った」は危険信号。こちらが「たぶんこう言いたいんだろう」と補完した瞬間、そこが
  ズレる場所。補完した内容こそ、絵かABCDにして見せる。説明文は書かない、指差すだけにする。

--------------------------------------------------------------------------
使い方（着手前にどのセッションからでも呼べる）
--------------------------------------------------------------------------

1) 解釈の幅があるか判定するだけ（幅が小さい／可逆／安いなら何も作らずSKIP）:
     python3 tools/kaishaku.py judge --text "指示文をそのまま貼る"
   最後に1行 `KAISHAKU_RESULT: SKIP - ...` か `KAISHAKU_RESULT: ASK - ...` を出す。

2) 既に同じ質問が決定済みでないか先に確認する（＝同じことを二度聞かない）:
     python3 tools/kaishaku.py check --key "badge-percent-904"
   見つかれば決定内容を出して終わり。judgeでASKと出ても、checkで既決定が
   見つかった場合は改めて聞く必要はない。

3) ABCDで確認を作る（各選択肢は20字以内・2〜4択）:
     python3 tools/kaishaku.py ask --n 904 --key "badge-percent-904" \
       --title "バッジは何%？" --a "25%" --b "29%" --c "35%" --d "40%"
   status/kaishaque_pending.json に積み、status/dispatch_outbox.jsonl にも
   type=interpretation_confirm で1行積む（Dispatchが拾って取り次ぐ）。

4) 絵（升目を並べた確認ページ）で確認を作る:
     python3 tools/kaishaku.py ask-mockup --n 904 --key "badge-percent-904" \
       --title "バッジは何%？" --n-val "25%|案A" --n-val "29%|案B" --n-val "35%|案C"
   内部で tools/make_check_page.py を呼び、GitHub Pages上の確認ページURLを出す。
   指差すだけで済むよう、説明文ではなく升目（値＋短いラベル）だけを並べる。

5) たまごさんの回答が来たら確定する（決定台帳へ＝以後は二度と聞かない）:
     python3 tools/kaishaku.py answer --key "badge-percent-904" --choice B --note "29%で確定"

--------------------------------------------------------------------------
判定ロジックの方針
--------------------------------------------------------------------------
  - 「危険語」（本番・公開・全ページ・共有コンポーネント・一括・課金・削除等）と
    「曖昧語」（どちら・どれ・名前・色・サイズ・%・レイアウト等）の**両方**に
    当たった時だけ ASK にする。安い・可逆・幅が小さい指示は何も作らず SKIP する
    （第一条「自律走行」を壊さない。確認を増やすための道具ではない）。
  - 確認は文章ではなく短い選択肢だけ。ask()は選択肢が20字を超えるとエラーで
    弾く（「分かりやすい確認にしてね」を機械で強制する）。
  - 1回聞いたら answer() で ai-brain/kettei.json に kind:"interpretation" として
    残す。同じ key の check()/ask() は以後、実行せずに既決定を即答する。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
KETTEI_PATH = os.path.join(REPO, "ai-brain", "kettei.json")
PENDING_PATH = os.path.join(REPO, "status", "kaishaku_pending.json")
OUTBOX_PATH = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
MAX_CHOICE_LEN = 20

# 「幅が大きい／やり直しが高くつく」を機械的に見分けるためのキーワード表。
# 増やしたい語が見つかったら、ここへ追記するだけでよい（コード本体は触らない）。
COSTLY_KEYWORDS = [
    "本番", "公開", "全ページ", "複数ページ", "共有コンポーネント",
    "一括", "課金", "削除", "全部", "大規模", "全曲", "全アーティスト", "本番反映",
]
AMBIGUOUS_KEYWORDS = [
    "どちら", "どれ", "どんな", "何パターン", "何パーセント", "%", "パーセント",
    "案", "名前", "色", "サイズ", "レイアウト", "見た目", "デザイン", "配置", "余白",
]


def _now():
    return datetime.datetime.now().astimezone().isoformat()


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _append_outbox(entry):
    os.makedirs(os.path.dirname(OUTBOX_PATH), exist_ok=True)
    with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def judge(text):
    """指示文の解釈の幅を判定する。ambiguous=Trueなら確認を作るべき。"""
    costly_hits = [k for k in COSTLY_KEYWORDS if k in text]
    ambiguous_hits = [k for k in AMBIGUOUS_KEYWORDS if k in text]
    ambiguous = bool(costly_hits) and bool(ambiguous_hits)
    if ambiguous:
        reason = "危険語(%s)と曖昧語(%s)の両方に当たったため確認が必要" % (
            "・".join(costly_hits), "・".join(ambiguous_hits),
        )
    else:
        reason = "幅が小さい・可逆・安いと判定（確認は作らない。自律走行のまま進めてよい）"
    return {
        "ambiguous": ambiguous,
        "costly_hits": costly_hits,
        "ambiguous_hits": ambiguous_hits,
        "reason": reason,
    }


def find_decision(key):
    kettei = _load_json(KETTEI_PATH, {"decisions": []})
    for d in kettei.get("decisions", []):
        if d.get("kind") == "interpretation" and d.get("key") == key:
            return d
    return None


def _validate_choices(choices):
    for label, value in choices:
        if value is not None and len(value) > MAX_CHOICE_LEN:
            raise SystemExit(
                "選択肢%sが%d字あります(%d字以内)。分かりやすい確認にするため短くしてください: %r"
                % (label, len(value), MAX_CHOICE_LEN, value)
            )


def cmd_judge(args):
    result = judge(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("KAISHAKU_RESULT: %s - %s" % ("ASK" if result["ambiguous"] else "SKIP", result["reason"]))
    return 0


def cmd_ask(args):
    existing = find_decision(args.key)
    if existing:
        print("既に決定済み。二度聞きません。")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        print("KAISHAKU_RESULT: KNOWN - %s" % existing.get("value"))
        return 0

    choices = [("A", args.a), ("B", args.b), ("C", args.c), ("D", args.d)]
    choices = [(l, v) for l, v in choices if v]
    if len(choices) < 2:
        raise SystemExit("選択肢は最低2つ必要です（--a --bなど）")
    if len(args.title) > MAX_CHOICE_LEN * 2:
        raise SystemExit("質問文が長すぎます。絵かABCDで見せるので説明文は書かないでください")
    _validate_choices(choices)

    pending = _load_json(PENDING_PATH, [])
    pending = [p for p in pending if p.get("key") != args.key]
    pending.append({
        "key": args.key,
        "n": args.n,
        "title": args.title,
        "choices": [{"label": l, "value": v} for l, v in choices],
        "askedAt": _now(),
    })
    _save_json(PENDING_PATH, pending)

    lines = "\n".join("%s. %s" % (l, v) for l, v in choices)
    message = "%s番「%s」\n%s\n（指差すだけでOK。文章の返信は不要）" % (args.n, args.title, lines)
    _append_outbox({
        "ts": _now(), "n": args.n, "type": "interpretation_confirm",
        "title": args.title, "message": message, "key": args.key,
        "choices": [v for _l, v in choices],
    })
    print(message)
    print("KAISHAKU_RESULT: ASKED - pending保存・dispatch_outboxへ1行送信")
    return 0


def cmd_ask_mockup(args):
    existing = find_decision(args.key)
    if existing:
        print("既に決定済み。二度聞きません。")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        print("KAISHAKU_RESULT: KNOWN - %s" % existing.get("value"))
        return 0

    nums = []
    for raw in args.n_val:
        if "|" not in raw:
            raise SystemExit("形式は '値|説明' です: %r" % raw)
        value, label = raw.split("|", 1)
        value, label = value.strip(), label.strip()
        if len(value) > MAX_CHOICE_LEN:
            raise SystemExit("升目の値が長すぎます(20字以内): %r" % value)
        nums.append((value, label))
    if len(nums) < 2:
        raise SystemExit("升目は最低2つ必要です（--n-valを複数回指定）")

    slug = "kaishaku-%s" % args.key
    cmd = [
        sys.executable, os.path.join(HERE, "make_check_page.py"),
        "--n", str(args.n), "--slug", slug,
        "--title", args.title,
        "--what", "解釈合わせ：どれが正しいか、絵（升目）で確認します。指差すだけでOK。",
        "--allow-no-screenshot", "解釈確認は選択肢の升目だけで足りるため画像なしで作成",
        "--print-url",
    ]
    for value, label in nums:
        cmd += ["--num", "%s|%s" % (value, label)]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        print("KAISHAKU_RESULT: FAIL - 確認ページ生成に失敗")
        return 1
    url = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("http"):
            url = line
        elif "http" in line:
            url = line.split(" ")[-1].strip()

    pending = _load_json(PENDING_PATH, [])
    pending = [p for p in pending if p.get("key") != args.key]
    pending.append({
        "key": args.key, "n": args.n, "title": args.title,
        "choices": [{"label": v, "value": v, "note": l} for v, l in nums],
        "checkUrl": url, "askedAt": _now(),
    })
    _save_json(PENDING_PATH, pending)

    _append_outbox({
        "ts": _now(), "n": args.n, "type": "interpretation_confirm",
        "title": args.title,
        "message": "%s番「%s」を絵で確認してください：%s" % (args.n, args.title, url),
        "key": args.key, "checkUrl": url,
    })
    print("KAISHAKU_RESULT: ASKED - %s" % url)
    return 0


def cmd_answer(args):
    pending = _load_json(PENDING_PATH, [])
    match = None
    rest = []
    for p in pending:
        if p.get("key") == args.key and match is None:
            match = p
        else:
            rest.append(p)
    _save_json(PENDING_PATH, rest)

    value = args.choice
    if match:
        for c in match.get("choices", []):
            if c.get("label") == args.choice:
                value = c.get("value")
                break

    kettei = _load_json(KETTEI_PATH, {"decisions": []})
    kettei.setdefault("decisions", [])
    kettei["decisions"] = [
        d for d in kettei["decisions"]
        if not (d.get("kind") == "interpretation" and d.get("key") == args.key)
    ]
    decision = {
        "id": "interpretation-%s" % args.key,
        "kind": "interpretation",
        "key": args.key,
        "decidedAt": datetime.date.today().isoformat(),
        "decidedBy": "たまごさん（kaishaku.py経由の絵/ABCD確認）",
        "what": match.get("title") if match else args.key,
        "value": value,
        "note": args.note or "",
        "queueRef": match.get("n") if match else None,
    }
    kettei["decisions"].append(decision)
    _save_json(KETTEI_PATH, kettei)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print("KAISHAKU_RESULT: SAVED - %s" % value)
    return 0


def cmd_check(args):
    d = find_decision(args.key)
    if d:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        print("KAISHAKU_RESULT: KNOWN - %s" % d.get("value"))
    else:
        print("KAISHAKU_RESULT: UNKNOWN - まだ決定なし")
    return 0


def main():
    ap = argparse.ArgumentParser(description="着手前に絵1枚orABCDで解釈を合わせる道具（904番）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("judge", help="解釈の幅があるか判定するだけ")
    p1.add_argument("--text", required=True)
    p1.set_defaults(func=cmd_judge)

    p2 = sub.add_parser("ask", help="ABCDの確認を作る")
    p2.add_argument("--n", required=True)
    p2.add_argument("--key", required=True)
    p2.add_argument("--title", required=True)
    p2.add_argument("--a")
    p2.add_argument("--b")
    p2.add_argument("--c")
    p2.add_argument("--d")
    p2.set_defaults(func=cmd_ask)

    p3 = sub.add_parser("ask-mockup", help="絵（升目）の確認ページを作る")
    p3.add_argument("--n", required=True)
    p3.add_argument("--key", required=True)
    p3.add_argument("--title", required=True)
    p3.add_argument("--n-val", action="append", required=True, dest="n_val", metavar="値|説明")
    p3.set_defaults(func=cmd_ask_mockup)

    p4 = sub.add_parser("answer", help="回答を決定台帳へ確定する（以後は二度と聞かない）")
    p4.add_argument("--key", required=True)
    p4.add_argument("--choice", required=True)
    p4.add_argument("--note")
    p4.set_defaults(func=cmd_answer)

    p5 = sub.add_parser("check", help="既に決定済みか確認する（二度聞かないためのlookup）")
    p5.add_argument("--key", required=True)
    p5.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
