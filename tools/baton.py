#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1030番【バトン】5区＝検品。外のAIが出したPRを、機械だけで検品して合否を付ける1本道。

━━ なぜ要るか（2026-09-23 実測）━━
外のAI（Jules・Devin・Codex）はPRまで運べる。実測 #464 は6分07秒で届いた。
ところが **そこから先へ運ぶ線が1本も無かった。**
  ・`github_watch.py` はPRを発車待ちに積む（#464＝n=1061）……ここまでは動いていた
  ・★検品の口（`hantei.kensa_html` / `1028_jules_saiten.py`）を呼んでいるコードは grep でゼロ件
  ・★`_965_keijiban.prmerge` を呼んでいるコードもゼロ件
＝ 拾う機械はある。判定する口もある。**運ぶ線だけが無い。**
毎回セッションが1本起きて、人が手で叩いていた。そこを埋めるのがこのファイル。

たまごさん（2026-09-23・原文）:
  「公開までがセットだよね。メインやPRに上げて終わりではないから。
    逆に、そこまでしか持っていけない人もいるわけでしょ？
    『そこまで運んできてくれてありがとう。じゃあ、ここから検品して私がバトンタッチする』
    というようなやり方もできると思う。」

━━ 区間の切り方（★ここが設計の肝。勝手に動かさない）━━
  1区〜5区（調べる・設計する・書く・PRまで運ぶ・**検品する**）＝ 全部自動。ここがこのファイル。
  ★6区（mainに入れる）・7区（本番に公開する）＝ **自動にしない。**
    main → Lovable → 本番 は**不可逆**だから。憲法第5条「止まってよい4つ」のうちの外部公開。
    6区は「押すだけ」の形でたまごさんの前に並べる（status/public/uketori_machi.json）。
  8区（出たことを確かめる）＝ 自動（tools/kakunin.py）。

★**このファイルは merge を1行も書かない。** prmerge を import すらしない。
  合格を出すところまでが仕事で、押すのは人。ここを自動にしたくなったら、上の理由を読み直すこと。

━━ 決まり（守らないと嘘の緑が戻る）━━
  ① ★判定は `tools/hantei.py` に寄せる。同じ規則を2か所に書かない。
     （26時間の嘘の緑は「同じifが2か所にあって片方だけ直った」ことが原因だった）
  ② ★検品でAIを1回も呼ばない。課金0。手本＝`tools/1028_jules_saiten.py`。
     採点の規則も**そちらにしか書かない**。ここからは呼ぶだけ。
  ③ ★「走った回数>0 なのに 取れた回数=0」は赤。
     `no_credential` / `401` / `403` / `skip` を黙って飲み込まない（hantei.surface_swallowed）。
  ④ 種類ごとに門を変える：
       JSON・データ … 件数・キー一致・型（`1028_jules_saiten.saiten`）
       HTML・ページ … `hantei.kensa_html` ＋ `oni_gate.judge`
       コード       … ビルドとテスト。★ここで走らせられないものは**通さない**（要人手）。
     ★知らない種類を「たぶん大丈夫」で通さない。分からないものは合格にしない。

━━ 使い方 ━━
  # 工場（Mac）側で直に
  python3 tools/baton.py --pr 464
  python3 tools/baton.py --pr 464 --repo tamago2022/joy-relief-station
  # サンドボックスから（api.github.comに出られないので心臓の使い走りに頼む）
  gaibu_kuchi.enqueue_job("kakunin", {"mode": "baton", "prs": [464]})
  ★心臓の使い走りは180秒上限。ループを書かない。PRは一度に5本まで。
"""
from __future__ import annotations

import importlib
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hantei  # noqa: E402  ★判定はここにしか書かない

GATE_REPO = "tamago2022/joy-relief-station"
OUT_JSON = os.path.join(REPO, "status", "public", "uketori_machi.json")
LOG = os.path.join(REPO, "status", "baton.log")
MAX_PRS = 5          # 心臓の使い走り180秒の中で終わる本数（実測 1本あたり3〜6秒）

# 外のAIのGitHub名 → たまごさんが読む名前。ここに無い相手はそのまま出す（推測で埋めない）。
WHO = {
    "google-labs-jules[bot]": "Jules（Google）",
    "chatgpt-codex-connector[bot]": "Codex（OpenAI）",
    "devin-ai-integration[bot]": "Devin",
    "copilot-swe-agent[bot]": "Copilot",
}
# ★実測（2026-09-23 #464）：**Jules が立てたPRの作者は tamago2022 になる。**
#   GitHub App が持ち主の名で押すため。作者だけを見ていると、外のAIが運んできた1本が
#   全部たまごさん自身の手柄に混ざって、誰が何を運んだのか数えられなくなる。
#   → 枝（ブランチ）の名前でも見分ける。ここに無い形は**そのまま枝の名前を出す**（当てない）。
WHO_BRANCH = (
    ("jules", "Jules（Google）"),
    ("codex", "Codex（OpenAI）"),
    ("devin", "Devin"),
    ("copilot", "Copilot"),
)


def who_of(author, head):
    """運んできたのは誰か。分からないときは分からないまま出す（★推測で埋めない）。"""
    if author in WHO:
        return WHO[author]
    low = (head or "").lower()
    for key, name in WHO_BRANCH:
        if key in low:
            return name
    if head:
        return "%s（枝: %s）" % (author or "?", head)
    return author or "?"


def _log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return line


# ---------------------------------------------------------------------
# 種類の見分け（★知らない形を「たぶんデータ」に寄せない）
# ---------------------------------------------------------------------
def kind_of(files):
    """変更されたファイル名の一覧から、かける門の種類を決める。

    ★1つでも別の種類が混ざっていたら "mixed" にして**要人手**にする。
      「JSONが1個とコードが3個」を、JSONの門だけ通して合格にするのがいちばん危ない。
    """
    kinds = set()
    for name in files:
        n = (name or "").lower()
        if n.endswith((".json", ".csv", ".tsv")):
            kinds.add("data")
        elif n.endswith((".html", ".htm")):
            kinds.add("html")
        elif n.endswith((".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".css")):
            kinds.add("code")
        elif n.endswith((".md", ".txt")):
            kinds.add("doc")
        else:
            kinds.add("unknown")
    if not kinds:
        return "empty"
    if len(kinds) == 1:
        return kinds.pop()
    return "mixed"


# ---------------------------------------------------------------------
# 門（種類ごと）
#   どれも (通ったか, [理由...], 追加情報dict) を返す。
#   ★理由は「読んで次の一手が分かる言葉」で書く。機械語のまま出さない。
# ---------------------------------------------------------------------
def _gate_data(path, text, files):
    """JSON・データの門。

    ★採点の規則はここに書かない。`tools/1028_jules_saiten.py` にしかない規則を呼ぶ。
      （読みの試験＝yomi-answers/ に出たものは、投げる前に確定した基準がそちらにある）
    それ以外のJSONは「読めるか・空でないか」までしか機械で言えない。
    ★言えないものを合格にしない。**要人手**で出す。
    """
    riyu = []
    if path.startswith("yomi-answers/"):
        try:
            saiten = importlib.import_module("1028_jules_saiten")
            importlib.reload(saiten)
        except Exception as e:  # noqa: BLE001
            return None, ["採点機（tools/1028_jules_saiten.py）が読み込めません：%s" % e], {}
        # ★置き場はJulesだけではない（Codexは yomi-answers/codex.json）。
        #   採点の規則は向こうに1本だけ。こちらは「どのファイルを見るか」を渡すだけ。
        mark, rate, why = saiten.saiten(text, files, target=path)
        riyu.extend(why)
        if mark == "◯採用":
            return True, riyu, {"rate": rate, "saiten": mark}
        if mark == "✕クビ":
            return False, riyu, {"rate": rate, "saiten": mark}
        return None, riyu, {"rate": rate, "saiten": mark}

    try:
        d = json.loads(text)
    except Exception as e:  # noqa: BLE001
        return False, ["JSONとして読めません：%s" % e], {}
    n = len(d) if isinstance(d, (dict, list)) else 0
    riyu.append("JSONとして読めた（%d件）" % n)
    if n == 0:
        return False, riyu + ["中身が0件です（空のものは通しません）"], {"count": 0}
    riyu.append("★この形には投げる前に決めた合格条件がありません＝正しさを機械で言えません")
    return None, riyu, {"count": n}


def _gate_html(path, text, files):
    """HTML・ページの門。`hantei.kensa_html` と `oni_gate.judge` の両方を通す。"""
    ok, ng = hantei.kensa_html(text, path)
    riyu = ["形の検品（hantei.kensa_html）：%s" % ("◯" if ok else "✕")]
    riyu += ["　・%s" % x for x in ng]
    try:
        import oni_gate
        importlib.reload(oni_gate)
        hits = oni_gate.judge(text, label=path)
    except Exception as e:  # noqa: BLE001
        return None, riyu + ["鬼監督（tools/oni_gate.py）が読み込めません：%s" % e], {}
    if hits:
        riyu.append("鬼監督：✕ %d件" % len(hits))
        for h in hits[:5]:
            riyu.append("　・%s %s（%s）" % (h.get("code"), h.get("name"), h.get("hit")))
    else:
        riyu.append("鬼監督：◯ 指摘なし")
    return (ok and not hits), riyu, {"oniHits": len(hits)}


def _gate_code(path, text, files):
    """コードの門。

    ★ここで正直に言う：**PRのコードをこの場でビルドして走らせてはいない。**
      走らせられないものを「合格」と書いたら、それが次の嘘の緑になる。
      だからコードは必ず**要人手**で出す（不合格ではない。畳まれて人が見る列に入る）。
    """
    riyu = ["コードの変更です。ビルドとテストを通さずに合格は付けません（★要人手）"]
    try:
        if path.endswith(".py"):
            compile(text, path, "exec")
            riyu.append("Pythonとして文法は通りました（構文検査だけ。動作は見ていません）")
    except SyntaxError as e:
        return False, riyu + ["Pythonの文法で落ちました：%s 行%s" % (e.msg, e.lineno)], {}
    return None, riyu, {}


def _gate_doc(path, text, files):
    riyu = ["文書（%s）の変更です。中身の正しさは機械で言えません（★要人手）" % path]
    if len((text or "").strip()) < 20:
        return False, riyu + ["中身がほぼ空です"], {}
    return None, riyu, {}


GATES = {"data": _gate_data, "html": _gate_html, "code": _gate_code, "doc": _gate_doc}


# ---------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------
def inspect_pr(number, repo=GATE_REPO):
    """PRを1本検品する。★mergeは絶対に押さない。返り値が「押すだけ」の1行になる。"""
    import _965_keijiban as K
    importlib.reload(K)

    row = {"repo": repo, "pr": int(number), "checkedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
           "verdict": "要人手", "mark": "⚪", "reasons": [], "gatesRun": 0, "gatesPassed": 0}

    # ★prstate には PR番号だけ渡す。Issue番号を混ぜると404で全体が落ちる（2026-09-23 実測 #463）。
    st = K.run_job({"repo": repo, "action": "prstate", "numbers": [int(number)]})
    if not st.get("ok"):
        row["verdict"], row["mark"] = "検品できず", "🔴"
        row["reasons"] = ["PRの状態が取れませんでした：%s" % st.get("error")]
        row["swallowed"] = hantei.surface_swallowed(json.dumps(st, ensure_ascii=False))
        return row
    pr = (st.get("prs") or [{}])[0]
    row.update({"title": pr.get("title") or "", "url": pr.get("url") or "",
                "author": pr.get("author") or "?", "state": pr.get("state"),
                "merged": bool(pr.get("merged")), "createdAt": pr.get("createdAt"),
                "head": pr.get("head"),
                "additions": pr.get("additions"), "deletions": pr.get("deletions")})
    row["who"] = who_of(row["author"], pr.get("head"))

    if row["merged"]:
        row["verdict"], row["mark"] = "もうmainに入っています", "✅"
        row["reasons"] = ["%s に main へ入りました（6区は済み）" % (pr.get("mergedAt") or "")]
        return row
    if row["state"] != "open":
        row["verdict"], row["mark"] = "閉じられています", "⚪"
        row["reasons"] = ["mainに入らないまま閉じられました"]
        return row

    fl = K.run_job({"repo": repo, "action": "prfiles", "number": int(number)})
    files = [f.get("name") for f in (fl.get("files") or [])]
    row["files"] = files
    row["kind"] = kind_of(files)
    row["what"] = "／".join(files[:3]) + ("ほか%d本" % (len(files) - 3) if len(files) > 3 else "")

    if row["kind"] in ("mixed", "unknown", "empty"):
        row["verdict"], row["mark"] = "要人手", "⚪"
        row["reasons"] = ["変更の種類が %s です。かける門が決まらないので合格は付けません"
                          % row["kind"], "変更: %s" % ("／".join(files) or "（0本）")]
        return row

    gate = GATES[row["kind"]]
    results = []
    for path in files:
        row["gatesRun"] += 1
        c = K.run_job({"repo": repo, "action": "content", "path": path,
                       "ref": "refs/pull/%s/head" % number})
        text = c.get("text") or ""
        if not text:
            results.append(False)
            row["reasons"].append("%s … 中身が取れませんでした（%s）" % (path, c.get("error") or "空"))
            sw = hantei.surface_swallowed(json.dumps(c, ensure_ascii=False))
            if sw:
                row["reasons"].append("★黙って飲み込まれかけた言葉：%s" % hantei.yakusu(sw))
            continue
        ok, riyu, extra = gate(path, text, files)
        results.append(ok)
        row["reasons"].append("── %s（%d バイト）" % (path, len(text.encode("utf-8"))))
        row["reasons"].extend("　" + r for r in riyu)
        for k, v in (extra or {}).items():
            row.setdefault(k, v)
        if ok:
            row["gatesPassed"] += 1

    # ★判定は hantei.judge の1か所だけ。ここに同じifを書かない。
    j = hantei.judge(row["gatesRun"], row["gatesPassed"], label="PR #%s の検品" % number)
    row["hantei"] = j["line"]

    if False in results:
        row["verdict"], row["mark"] = "不合格", "🔴"
    elif None in results or not results:
        row["verdict"], row["mark"] = "要人手", "⚪"
    else:
        row["verdict"], row["mark"] = "合格", "✅"
    # ★走ったのに1つも取れていない＝赤。合格には絶対にしない。
    if j["red"] and row["verdict"] == "合格":
        row["verdict"], row["mark"] = "不合格", "🔴"
        row["reasons"].append("★" + j["why"])
    return row


def _load_out():
    try:
        return json.load(io.open(OUT_JSON, encoding="utf-8"))
    except Exception:
        return {"rows": []}


def write_out(rows):
    """★進捗表が読む1枚。合格したものだけ上に出し、それ以外は畳んで下に置く。"""
    old = {int(r.get("pr") or 0): r for r in (_load_out().get("rows") or [])}
    for r in rows:
        old[int(r["pr"])] = r
    allrows = sorted(old.values(), key=lambda r: -int(r.get("pr") or 0))
    # もうmainに入ったものは、押すボタンが要らないので落とす（並べっぱなしにしない）
    allrows = [r for r in allrows if not r.get("merged")][:40]
    doc = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rule": "5区までが自動。★6区（mainに入れる）は押すだけの形で出す＝自動にしない",
        "goukaku": [r for r in allrows if r.get("verdict") == "合格"],
        "sonota": [r for r in allrows if r.get("verdict") != "合格"],
        "rows": allrows,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_JSON)
    return doc


def run_job(payload=None):
    """心臓の使い走りから呼ばれる口。★180秒に収めるため本数を MAX_PRS で切る。"""
    payload = payload or {}
    repo = payload.get("repo") or GATE_REPO
    nums = payload.get("prs") or ([payload["pr"]] if payload.get("pr") else [])
    nums = [int(n) for n in nums][:MAX_PRS]
    if not nums:
        return {"ok": False, "error": "PR番号がありません（prs: [464] の形で渡す）", "totalYen": 0.0}
    rows = []
    for n in nums:
        try:
            rows.append(inspect_pr(n, repo))
        except Exception as e:  # noqa: BLE001
            rows.append({"repo": repo, "pr": n, "verdict": "検品できず", "mark": "🔴",
                         "reasons": ["検品の途中で例外：%s: %s" % (type(e).__name__, e)]})
        _log("PR #%s → %s" % (n, rows[-1].get("verdict")))
    doc = write_out(rows)
    return {"ok": True, "rows": rows, "goukaku": len(doc["goukaku"]),
            "out": "status/public/uketori_machi.json", "totalYen": 0.0}


def _self_test():
    """★投げる前の自己試験。ネットに出ない。ここが落ちたら線を繋がない。"""
    ng = []
    if kind_of(["a.json"]) != "data":
        ng.append("kind_of: json をデータと見ていない")
    if kind_of(["a.html"]) != "html":
        ng.append("kind_of: html を見ていない")
    if kind_of(["a.json", "b.py"]) != "mixed":
        ng.append("★kind_of: 種類が混ざったのに mixed にならない（いちばん危ない穴）")
    ok, riyu, _ = _gate_data("x/y.json", "{}", ["x/y.json"])
    if ok is not False:
        ng.append("★空のJSONを通してしまう")
    ok, riyu, _ = _gate_data("x/y.json", "{\"a\":1}", ["x/y.json"])
    if ok is not None:
        ng.append("★基準の無いJSONを合格/不合格にしている（要人手＝None のはず）")
    ok, riyu, _ = _gate_code("a.py", "def f(:\n", ["a.py"])
    if ok is not False:
        ng.append("★文法が壊れたPythonを落としていない")
    ok, riyu, _ = _gate_code("a.py", "def f():\n    return 1\n", ["a.py"])
    if ok is not None:
        ng.append("★コードに合格を付けている（要人手＝None のはず）")
    ok, riyu, _ = _gate_html("a.html", "<x>", ["a.html"])
    if ok is not False:
        ng.append("★壊れたHTMLを落としていない")
    j = hantei.judge(3, 0)
    if not j["red"]:
        ng.append("★走った3・取れた0 が赤になっていない")
    print("自己試験：%s" % ("◯ 全部通った" if not ng else "✕ %d件" % len(ng)))
    for x in ng:
        print("  -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(_self_test())
    repo = a[a.index("--repo") + 1] if "--repo" in a else GATE_REPO
    nums = []
    if "--pr" in a:
        nums = [int(x) for x in a[a.index("--pr") + 1].split(",")]
    r = run_job({"repo": repo, "prs": nums})
    print(json.dumps(r, ensure_ascii=False, indent=1))
