#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/kanryo_mon.py ── 完了の門。★終了コードで止める。文章では止めない。

たまごさんのノート「genspark 鬼監督」（tamago_brain）が正本：

  「強制力は本人の内側にしかない。**強制力は外に置かないと効きません。**」
  「Stop フック：Claude が応答を終えようとした瞬間に発火し、
    **exit code 2 を返すと『まだ終わるな』と差し戻せる。**」
  「TaskCompleted フック：タスクを『完了』扱いにしようとした瞬間に
    **exit code 2 で完了を阻止し、フィードバックを返せる。**」
  「フックは万能ではなく、モデルが Stop フックを無視するという報告も出ています。
    だから**プロンプトの遵守ではなく、実際に走るコマンドの exit code をゲートにする。**」

★この1本がその「実際に走るコマンド」。

  返す終了コード
    0 … 通してよい（機械の検品も、外の判定も通っている）
    2 … ★通さない。標準エラーに「なぜ落ちたか」と「次に何をすればよいか」を出す。
          Claude Code の Stop / TaskCompleted フックはこれを読んで差し戻す。

★通す条件は3つ全部（ノートの3点セットに対応）
  ① 完了の定義が満たされている … 本番URLが200で返り、中身が空でない
  ② 状態がファイルに落ちている … 台帳（status/）に書かれている
     「ファイルに落ちていない進捗は消えます」（ノート）
  ③ 外の判定が入っている       … status/gaibu/soto_hantei.json にOKがある
     ★こちら側が自分で「完了」と書けない

使い方
    python3 tools/kanryo_mon.py --hook            # フックから（標準入力でJSONが来る）
    python3 tools/kanryo_mon.py --check "<報告文>" # 手で1件だけ試す
    python3 tools/kanryo_mon.py --show            # 弾いた数
    python3 tools/kanryo_mon.py --self-test

★2026-09-26 追記：**Stopフックは1154号（tools/stop_kanmon/）が既に入れている。**
  二重に作らない。.claude/settings.json のフックは1154のものが正本で、
  ここは相乗りしている：1152が持ち込んだ「★外の判定が入るまで完了にしない」だけを
  tools/stop_kanmon/kanmon.mjs の kensa() に足した（sotoNoHantei）。
  この kanryo_mon.py は、手で1件だけ試す道具として残してある（フックには刺さない）。

もとの入れ方（※いまは使わない。1154が入っているため）
    "hooks": {
      "Stop":          [{"hooks":[{"type":"command",
                          "command":"python3 tools/kanryo_mon.py --hook"}]}],
      "TaskCompleted": [{"hooks":[{"type":"command",
                          "command":"python3 tools/kanryo_mon.py --hook"}]}]
    }
"""
from __future__ import annotations

import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DIR = os.path.join(ST, "kanryo_mon")
LOG = os.path.join(DIR, "mon.jsonl")     # ★弾いた数はこの行数
JST = datetime.timezone(datetime.timedelta(hours=9))

TOOSU, TOMERU = 0, 2     # ★2 で止める（Claude Code のフックの約束）


def stamp():
    return datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def append(o):
    try:
        os.makedirs(DIR, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    except Exception:
        pass


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


def kanryo_to_itteru(text):
    """「完了」を名乗っているか。名乗っていなければ門は素通りさせる
    （途中の報告まで止めると仕事が進まない）。"""
    t = (text or "")
    return any(w in t for w in ("完了", "できました", "出来ました", "終わりました",
                                "反映しました", "対応しました", "done", "Done"))


def shiraberu(text):
    """通してよいかを調べる。返すのは (通すか, 落ちた理由, 次に何をすればよいか)。"""
    try:
        import oni_modoshi
    except Exception as e:
        # 門が読めないときは**止める**。通すのではない（安全側）。
        return False, "門（oni_modoshi）を読めない: %s" % e, "tools/oni_modoshi.py を直してください。"

    urls = oni_modoshi.urls_in(text)
    if not urls:
        return (False,
                "報告に本番URLが1本も無い。「やりました」は証拠になりません。",
                "本番に出して、開いて200が返るURLを報告に貼ってから、もう一度終わってください。")

    if not oni_modoshi.soto_ni_derareru():
        return (False,
                "回線が無いのでURLを叩けない＝完了かどうか確かめられない。",
                "回線のある所（Macの心臓）から tools/oni_modoshi.py を走らせてください。")

    k = oni_modoshi.kenpin("（フックからの検品）", text)
    if k.get("sotomachi"):
        return (False,
                "機械の検品は通ったが、★外の判定がまだ無い。こちら側では完了にできません。",
                "tools/gaibu_shinsa.py が外（Genspark／Codex）へ出した監査の返事を待ってください。"
                "急ぐなら python3 tools/gaibu_shinsa.py --hirou で取り込み直せます。")
    if not k.get("ok"):
        return False, k.get("naze") or "検品に落ちた", "落ちた所を直して、直したURLを貼ってください。"
    return True, None, None


def hook():
    """フックから呼ばれる口。標準入力のJSONから報告文を拾う。

    ★入力が読めなくても止めない（通す）。門が壊れて仕事が全部止まる方が高くつく。
      ただし「完了」を名乗っているのに調べられない場合だけは止める。
    """
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        pass
    text = raw
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            text = " ".join(str(d.get(k) or "") for k in
                            ("last_message", "message", "transcript", "result",
                             "output", "summary", "task", "text"))
            if not text.strip():
                text = raw
    except Exception:
        pass

    if not kanryo_to_itteru(text):
        return TOOSU     # 完了を名乗っていない＝途中の報告。止めない

    ok, naze, tsugi = shiraberu(text)
    append({"at": stamp(), "ok": ok, "naze": naze, "len": len(text or "")})
    if ok:
        return TOOSU
    sys.stderr.write(
        "★この完了は受け付けられません。\n"
        "【落ちた理由】%s\n"
        "【次にやること】%s\n"
        "（完了はこちら側では書けません。機械の検品と外の判定を通ったときだけ付きます。"
        "決めているのは tools/kanryo_mon.py の終了コードです。）\n" % (naze, tsugi))
    return TOMERU


def main():
    a = sys.argv[1:]
    if "--hook" in a:
        return hook()
    if "--self-test" in a:
        ng = []
        if kanryo_to_itteru("途中です。あと少し"):
            ng.append("完了を名乗っていない報告を止めようとしている")
        if not kanryo_to_itteru("完了しました"):
            ng.append("完了の名乗りを見落とす")
        ok, naze, tsugi = shiraberu("完了しました。やっておきました。")
        if ok:
            ng.append("★URLの無い自己申告を通してしまう（門が効いていない）")
        if not naze or not tsugi:
            ng.append("落ちた理由と次にやることを返していない")
        print("自己試験：%s／止めるときの終了コード=%d・通すとき=%d／これまでに弾いた %d件"
              % ("OK" if not ng else "NG", TOMERU, TOOSU,
                 len([r for r in jsonl(LOG) if not r.get("ok")])))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        rows = jsonl(LOG)
        print("【完了の門】通した %d件／★弾いた %d件"
              % (len([r for r in rows if r.get("ok")]),
                 len([r for r in rows if not r.get("ok")])))
        for r in rows[-8:]:
            print("  %s %s" % ("✅" if r.get("ok") else "🔴", r.get("naze") or "通した"))
        return 0
    if "--check" in a:
        i = a.index("--check")
        text = a[i + 1] if len(a) > i + 1 else ""
        ok, naze, tsugi = shiraberu(text)
        print("通す" if ok else "★止める：%s → %s" % (naze, tsugi))
        return TOOSU if ok else TOMERU
    print(__doc__.strip().splitlines()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
