#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字と断定の門。★これはたまごさんに出す前に必ず通る関所。

━━ なぜ作ったか（2026-09-23・1033番・たまごさん）━━

  「間違えるのはしょうがないんだけど、間違いが多すぎる。
    381円って思ってさ、『間違えてました』がすげえ多いんだよね。
    調べてから上げてこいよって。混乱するから。
    間違いが大きすぎるよ。どれが本当なんだろうって思う。
    コロコロコロコロ変わるから、報告がさぁ。」

今日こちら発で起きた間違いを並べると、原因は1つしかなかった：

  ① xAIの残高381円   → 実際1,479円（別システムの予算カウンタと取り違え）
  ② Gensparkに公開APIが無い → 公式CLI `gsk` があった
  ③ 枠を使い切った   → 各セッションが別々の上限に当たっていただけ
  ④ 空きメモリ273MBが危機 → macOSでは正常
  ⑤ Julesは決まった作業しかできない → 設計批判を返してきた
  ⑥ 絵本のアニメをお手本と並べずに渡した

  ＝ 全部「叩いて確かめる前に言った」。能力ではなく**手順が抜けている**だけ。
    手順は、思い出す人がいる限り必ず抜ける（oni_gate.py 冒頭と同じ結論）。
    だから思い出さなくても通る場所に置く。**ここを通らないと出せない。**

━━ 落とす条件は3つだけ（増やさない）━━

  KZ1  数字があるのに、どこで叩いたかが書いていない
  KZ2  「無い・できない・対応していない」と断定しているのに、実測が2本未満
  KZ3  前にたまごさんへ出した数字と食い違うのに、「訂正」と書いていない

  ★KZ3が今回いちばん効く。コロコロ変わること自体より、
    **「訂正だと言わずに変わること」**が混乱の原因だから。

━━ 出典として認める形（これ以外は出典ではない）━━

  url   叩いたURL ＋ HTTPコード ＋ 時刻   例 https://api.x.ai/v1/... 200 10:57
  file  ファイルパス ＋ 行番号             例 tools/hantei.py:119
  cmd   コマンド ＋ その出力               例 $ python3 tools/kaitsuu.py → 赤0件

  ★「設定に書いてある」「〜のはず」「おそらく」「たぶん」「と思われる」は
    全部アウト。これらは出典の代用にならない（＝381円はここで死ぬ）。

━━ 絵・映像は見ない ━━

  絵・映像の検品は別便（oni_gate.py＝鬼監督）が持っている。
  ここで同じ判定を2つ目に書かない。見つけたら「そっちへ回せ」とだけ言う。

━━ AIを1回も呼ばない ━━

  全部ただの文字列判定。課金0。毎回同じ答えが出る。甘くならない。
  （tools/1028_jules_saiten.py と同じ型）

━━ 使い方 ━━

    python3 tools/kazu_gate.py --file status/houkoku.md
    echo "残高は381円です" | python3 tools/kazu_gate.py
    python3 tools/kazu_gate.py --text "..." --record   # 通ったら台帳に記録する
    python3 tools/kazu_gate.py --self-test             # わざと悪い文で落ちるか試す
    python3 tools/kazu_gate.py --asa                   # 赤のときだけ知らせる

終了コード: 0=通過 / 1=落とした（出してはいけない）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
DAICHO = os.path.join(STATUS, "suuji_daicho.jsonl")   # ★新設。出した数字の全部
LOG = os.path.join(STATUS, "kazu_gate.log")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
ASA_STATE = os.path.join(STATUS, ".kazu_gate_asa.json")
JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# 材料：数字・出典・推測語・断定語
# ---------------------------------------------------------------------------

# 単位つきの数字。単位の無い裸の数字は見ない（日付・ID・バージョンと区別できないため）。
TANI = ("円", "ドル", "USD", "%", "％", "件", "回", "秒", "分", "時間",
        "枚", "本", "通", "人", "個", "日", "バイト", "KB", "MB", "GB", "TB")
NUM_RE = re.compile(
    r"(?<![0-9A-Za-z_./:-])(\$?[0-9][0-9,]*(?:\.[0-9]+)?)\s*(%s)?"
    % "|".join(re.escape(t) for t in TANI))

# 出典として認める3つの形。
SRC_URL = re.compile(r"https?://[^\s、。）)」\]]+")
SRC_CODE = re.compile(r"(?<![0-9])([1-5][0-9]{2})(?![0-9])")
SRC_TIME = re.compile(r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}")
SRC_FILE = re.compile(
    r"[\w./\-]+\.(?:py|mjs|js|jsx|ts|tsx|json|jsonl|md|html|sh|txt|csv|ya?ml|log)"
    r"\s*[:：]\s*\d+")
# ★`$` の前が半角スペースだけだと、日本語の文中に書いた「（$ python3 …」を
#   コマンドとして認めない＝正しく叩いた記録まで落ちる（2026-09-23 実測で発覚）。
#   括弧・鍵括弧・読点のあとも、コマンドの始まりとして認める。
SRC_CMD = re.compile(r"(?:^|[\s（(「『【\[、,：:])\$\s+\S+|`[^`]{3,}`")
SRC_OUT = re.compile(r"→|=>|出力[:：]|結果[:：]|httpCode|exit\s*\d")

# 出典を別行に書くときの見出し。数字の行の直後2行までを見る。
SRC_HEAD = re.compile(r"^\s*[-・*]?\s*(出典|根拠|叩いた|実測|source|src)\s*[:：]")

# ★推測語。これがあれば数字の出どころが何であれ落とす。
#   「〜のはず」で出した381円が、まさにこれ。
SUISOKU = ("のはず", "はずです", "はずだ", "おそらく", "たぶん", "多分",
           "と思われ", "と思います", "思われる", "かもしれ", "かと",
           "だろう", "でしょう", "らしい", "ようです", "みたい",
           "設定に書いて", "設定上は", "仕様上は", "推定", "見込み",
           "概算", "だいたい", "およそ", "ざっくり")

# ★「無い」断定。1本の経路が塞がっただけで言ってはいけない言葉（Gensparkの件）。
DANTEI = ("公開APIが無い", "APIが無い", "APIはありません", "存在しません",
          "存在しない", "ありません", "有りません", "対応していません",
          "対応していない", "非対応", "未対応", "できません", "出来ません",
          "使えません", "提供されていません", "提供されていない",
          "用意されていません", "実装されていません", "不可能です",
          "見つかりませんでした", "一切ありません")

# ★「無い」を言うなら、公式ドキュメントの目次を通しで読んだ記録が要る。
TOC_RE = re.compile(r"目次(?:を)?(?:通し|読|全部|走査|確認)|toc|sitemap|"
                    r"docs?/index|一覧を(?:全部|通しで)")

# 絵・映像＝別便（oni_gate.py）の持ち場。ここでは判定しない。
E_RE = re.compile(r"画像|動画|アニメ|絵本|サムネ|イラスト|映像|ポスター|"
                  r"\.(?:png|jpe?g|gif|webp|mp4|mov|svg)\b", re.I)

# 訂正の言葉。KZ3 はこれを強制する。
TEISEI_RE = re.compile(r"★?訂正")


def _norm(s):
    """比べるための正規化。全角英数と空白のゆらぎを潰す。"""
    out = []
    for ch in s or "":
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            ch = chr(o - 0xFEE0)
        out.append(ch)
    return re.sub(r"\s+", "", "".join(out))


def source_kind(s):
    """その文字列に、認められる出典が入っているか。入っていれば種類を返す。"""
    if not s:
        return ""
    if SRC_URL.search(s) and SRC_CODE.search(s) and SRC_TIME.search(s):
        return "url"
    if SRC_FILE.search(s):
        return "file"
    if SRC_CMD.search(s) and SRC_OUT.search(s):
        return "cmd"
    return ""


def _strip_sources(line):
    """出典そのものに含まれる数字（200・行番号・時刻）を数字判定から外す。"""
    t = SRC_URL.sub(" ", line)
    t = SRC_FILE.sub(" ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?", " ", t)
    t = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?", " ", t)
    t = re.sub(r"(?:httpCode|HTTP|status|exit)\s*[:：=]?\s*\d+", " ", t, flags=re.I)
    return t


def _value(raw):
    """'1,479' や '$9.41' を数として取る。取れなければ None。"""
    s = (raw or "").replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _subject(prefix):
    """数字の前に書いてある言葉から「何の数字か」を取る。

    「xAIの残高は381円」→ 'xAIの残高'
    ★完全ではない。だから取れた分だけを台帳に載せ、取れなければ食い違いは見ない
      （見えない分を「無い」ことにしない。KZ1 が別に効いている）。
    """
    t = _strip_sources(prefix)
    t = re.sub(r"^[\s\-・*●○◯✅🔴⚪【】\[\]0-9.)）]+", "", t)
    # 直前の区切りから後ろだけを見る
    t = re.split(r"[、。：:／/｜|（(\[\]「『]", t)[-1]
    t = t.strip()
    # 語尾の助詞を落とす
    t = re.sub(r"(?:は|が|を|の|も|で|に|と|へ|から|まで|より|だけ|約|およそ)+$", "", t)
    t = _norm(t)
    return t[-24:] if len(t) > 24 else t


def _tail(key):
    """'xAIの残高' と '残高' を同じものとして拾うための短い鍵。"""
    if not key:
        return ""
    t = re.split(r"[のー・]", key)[-1]
    return t if len(t) >= 2 else key


# ---------------------------------------------------------------------------
# 台帳：たまごさんへ出した数字を全部おぼえる
# ---------------------------------------------------------------------------
def load_daicho():
    rows = []
    try:
        with io.open(DAICHO, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return rows


def _index(rows):
    """鍵 → 最後に出した記録。tail鍵も同じ表に入れる（衝突したら本鍵が勝つ）。"""
    idx = {}
    for r in rows:
        k = r.get("key")
        if not k:
            continue
        idx[k] = r
    for r in rows:
        k = _tail(r.get("key") or "")
        if k and k not in idx:
            idx[k] = r
    return idx


def record(text, why=""):
    """通った報告文の数字を台帳に書く。★通ったものしか書かない。"""
    got = scan(text)
    now = datetime.now(JST).isoformat()
    n = 0
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        for g in got:
            if not g["key"] or g["value"] is None:
                continue
            f.write(json.dumps({
                "at": now, "key": g["key"], "tail": _tail(g["key"]),
                "value": g["value"], "unit": g["unit"], "raw": g["raw"],
                "line": g["line"][:160], "src": g["src"], "why": why,
            }, ensure_ascii=False) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------------------
# 読み取り
# ---------------------------------------------------------------------------
def scan(text):
    """報告文から、数字の言明を全部拾う。"""
    lines = (text or "").splitlines()
    got = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        # 出典は、その行と、直後2行の「出典：」行まで見る
        nearby = line
        for j in range(i + 1, min(i + 3, len(lines))):
            if SRC_HEAD.match(lines[j]):
                nearby += "\n" + lines[j]
        src = source_kind(nearby)
        clean = _strip_sources(line)
        for m in NUM_RE.finditer(clean):
            raw, unit = m.group(1), (m.group(2) or "")
            if not unit and not raw.startswith("$"):
                continue          # 単位の無い裸の数字は見ない
            v = _value(raw)
            if v is None:
                continue
            got.append({
                "no": i + 1, "line": line.strip(), "raw": raw,
                "unit": unit or "ドル", "value": v, "src": src,
                "key": _subject(clean[:m.start()]),
            })
    return got


# ---------------------------------------------------------------------------
# 判定（★これが唯一の判定。ほかのどの道具もこれを呼ぶ。同じifを2か所に書かない）
# ---------------------------------------------------------------------------
def judge(text, daicho=None):
    """報告文を見て、出していいかを返す。

    戻り値: dict(ok, hits[], e_bin, counted)
      hits: [{"code","why","line"}...]
    """
    t = text or ""
    hits = []
    rows = load_daicho() if daicho is None else daicho
    idx = _index(rows)

    # ---- KZ1 数字に出典が無い / 推測語で代用している ----
    got = scan(t)
    mita = set()   # 同じ行の同じ数字を何度も読ませない（同じ話を並べない）
    for g in got:
        k = (g["no"], g["raw"], g["unit"])
        if k in mita:
            continue
        mita.add(k)
        sui = [w for w in SUISOKU if w in g["line"]]
        if sui:
            hits.append({
                "code": "KZ1", "line": g["line"],
                "why": "%s%s と書いていますが、同じ行に「%s」があります。"
                       "★推測は出典の代わりになりません（381円がこれでした）"
                       % (g["raw"], g["unit"], "・".join(sui[:2]))})
            continue
        if not g["src"]:
            hits.append({
                "code": "KZ1", "line": g["line"],
                "why": "%s%s の出どころが書いてありません。"
                       "★叩いたURL＋HTTPコード＋時刻／ファイルパス＋行番号／"
                       "コマンドとその出力、のどれかを同じ行に書いてください"
                       % (g["raw"], g["unit"])})

    # ---- KZ2 「無い」の断定に実測が2本そろっていない ----
    for w in DANTEI:
        if w not in t:
            continue
        jissoku = _count_jissoku(t)
        toc = bool(TOC_RE.search(t))
        if jissoku < 2 or not toc:
            tarinai = []
            if jissoku < 2:
                tarinai.append("実測が%d本（2本以上要る）" % jissoku)
            if not toc:
                tarinai.append("公式ドキュメントの目次を通しで読んだ記録が無い")
            hits.append({
                "code": "KZ2", "line": _line_of(t, w),
                "why": "「%s」と断定していますが、%s。"
                       "★1つの経路が塞がっただけで「無い」と言わない"
                       "（Genspark：名前解決しない・403だけを見て「無い」と言い、"
                       "公式CLI `gsk` を見落としました）"
                       % (w, "／".join(tarinai))})
        break   # 同じ話を何度も読ませない

    # ---- KZ3 前に出した数字と食い違うのに「訂正」と書いていない ----
    teisei = bool(TEISEI_RE.search(t))
    for g in got:
        if not g["key"] or g["value"] is None:
            continue
        prev = idx.get(g["key"]) or idx.get(_tail(g["key"]))
        if not prev or prev.get("value") is None:
            continue
        if prev.get("unit") != g["unit"]:
            continue
        if abs(float(prev["value"]) - g["value"]) < 1e-9:
            continue
        mae = "%s%s" % (prev.get("raw"), prev.get("unit") or "")
        ima = "%s%s" % (g["raw"], g["unit"])
        if not teisei:
            hits.append({
                "code": "KZ3", "line": g["line"],
                "why": "「%s」は前に %s と出しています（%s）。今回は %s。"
                       "★食い違うときは必ずこう書いてください："
                       "「★訂正：前は%sと言いましたが、正しくは%sです」"
                       % (g["key"], mae, (prev.get("at") or "")[:16], ima, mae, ima)})
            continue
        if mae not in t and _norm(mae) not in _norm(t):
            hits.append({
                "code": "KZ3", "line": g["line"],
                "why": "訂正とは書いてありますが、前に出した %s が本文にありません。"
                       "★前の数字をそのまま書いてください（何が変わったか分からないため）"
                       % mae})

    return {
        "ok": not hits,
        "hits": hits,
        "counted": len(got),
        "e_bin": bool(E_RE.search(t)),
    }


def _count_jissoku(t):
    """実測の本数＝認められる出典が何本あるか。"""
    n = 0
    for line in t.splitlines():
        if source_kind(line):
            n += 1
    return n


def _line_of(t, w):
    for line in t.splitlines():
        if w in line:
            return line.strip()
    return ""


# ---------------------------------------------------------------------------
# 見せ方
# ---------------------------------------------------------------------------
def show(res):
    if res["e_bin"]:
        print("（絵・映像が入っています。そちらは別便の門へ："
              "python3 tools/oni_gate.py <file> --strict）")
    if res["ok"]:
        print("KAZU_GATE: OK — 数字%d件、全部に出どころがあります" % res["counted"])
        return 0
    print("\n🛑 数字の門が止めました。たまごさんに出す前に、叩いて確かめてください。\n")
    for h in res["hits"]:
        print("  ● [%s] %s" % (h["code"], h["why"]))
        if h["line"]:
            print("    その行: %s" % h["line"][:110])
        print("")
    return 1


def _log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now(JST).strftime("%F %T"), line))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 自己試験：★わざと悪い報告文を入れて、落ちることを実測で示す
#   門が「実は何も見ていなかった」を防ぐのは、この試験だけ。
# ---------------------------------------------------------------------------
CASES = [
    # (番号, 入れた文, 落ちてほしい規則 or None, なぜ)
    ("①", "xAIの残高は381円です。", "KZ1",
     "出典なし。今日いちばん大きかった間違いそのもの"),
    ("①-2", "残高は381円のはずです。", "KZ1",
     "「のはず」は出典の代わりにならない"),
    ("①-3", "設定に書いてあるので、枠は4.50ドルです。", "KZ1",
     "「設定に書いてある」は叩いた記録ではない"),
    ("②", "Gensparkには公開APIが無い。403が返ってきました。", "KZ2",
     "1経路だけ。実測2本と目次読破の記録が無い"),
    ("④", "空きメモリ273MBで危機的です。", "KZ1",
     "出典なし＋比べる基準なし"),
    ("◯", "xAIの残高は $9.41 です（https://console.x.ai/team/billing 200 "
           "2026-09-23 11:20 で確認）。", None,
     "叩いたURL＋200＋時刻がある＝通る"),
    ("◯-2", "判定の規則は tools/hantei.py:119 の1か所だけ、計1件です。", None,
     "ファイルパス＋行番号＝通る"),
]

# KZ3 は台帳が要るので、専用の見本でためす
CASE_KZ3_MAE = ("xAIの残高は381円です（https://x.test/a 200 2026-09-23 09:00）。")
CASE_KZ3_ATO = ("xAIの残高は1,479円です（https://x.test/b 200 2026-09-23 11:20）。")
CASE_KZ3_NAOSHI = ("★訂正：前は381円と言いましたが、正しくは1,479円です"
                   "（https://x.test/b 200 2026-09-23 11:20）。")


def self_test(verbose=True):
    """戻り値: (落ちた件数, 不合格件数, 記録[])"""
    ng = 0
    kiroku = []
    for no, sample, want, why in CASES:
        res = judge(sample, daicho=[])
        codes = sorted({h["code"] for h in res["hits"]})
        ok = (want in codes) if want else (not codes)
        if not ok:
            ng += 1
        kiroku.append({"no": no, "input": sample, "want": want or "（通る）",
                       "got": "／".join(codes) if codes else "（違反なし）",
                       "ok": ok, "why": why,
                       "detail": res["hits"][0]["why"] if res["hits"] else ""})
        if verbose:
            print("%s %-5s 入れた: %s" % ("✅" if ok else "❌", no, sample[:54]))
            print("        → %s（ねらい %s）" % (kiroku[-1]["got"], want or "通る"))

    # KZ3：同じ対象で数字が変わったら、訂正と書くまで通さない
    d = []
    for g in scan(CASE_KZ3_MAE):
        if g["key"] and g["value"] is not None:
            d.append({"at": "2026-09-23T09:00:00+09:00", "key": g["key"],
                      "value": g["value"], "unit": g["unit"], "raw": g["raw"]})
    r_nashi = judge(CASE_KZ3_ATO, daicho=d)
    r_ari = judge(CASE_KZ3_NAOSHI, daicho=d)
    for label, r, want, sample in (
            ("③", r_nashi, "KZ3", CASE_KZ3_ATO),
            ("③-2", r_ari, None, CASE_KZ3_NAOSHI)):
        codes = sorted({h["code"] for h in r["hits"]})
        ok = (want in codes) if want else (not codes)
        if not ok:
            ng += 1
        kiroku.append({"no": label, "input": sample, "want": want or "（通る）",
                       "got": "／".join(codes) if codes else "（違反なし）",
                       "ok": ok,
                       "why": "台帳に381円がある状態で1,479円を出した"
                              if want else "訂正と前の数字を両方書いた",
                       "detail": r["hits"][0]["why"] if r["hits"] else ""})
        if verbose:
            print("%s %-5s 入れた: %s" % ("✅" if ok else "❌", label, sample[:54]))
            print("        → %s（ねらい %s）" % (kiroku[-1]["got"], want or "通る"))

    if verbose:
        print("\n見本試験：%d件中 %d件 合格" % (len(kiroku), len(kiroku) - ng))
    return len(kiroku), ng, kiroku


# ---------------------------------------------------------------------------
# 毎朝：★赤のときだけ知らせる。緑なら1文字も書かない（kaitsuu.py と同じ作法）
# ---------------------------------------------------------------------------
def asa(force=False):
    now = datetime.now(JST)
    if now.hour < 7 and not force:
        return 0
    today = now.strftime("%F")
    st = {}
    try:
        with io.open(ASA_STATE, encoding="utf-8") as f:
            st = json.load(f) or {}
    except Exception:
        pass
    if st.get("lastDay") == today and not force:
        return 0

    n, ng, _ = self_test(verbose=False)
    # 昨日1日で門が何回止めたか
    tometa = 0
    kinou = (now - timedelta(days=1)).strftime("%F")
    try:
        with io.open(LOG, encoding="utf-8") as f:
            for line in f:
                if line.startswith((today, kinou)) and " NG " in line:
                    tometa += 1
    except FileNotFoundError:
        pass

    st["lastDay"] = today
    try:
        os.makedirs(os.path.dirname(ASA_STATE), exist_ok=True)
        with io.open(ASA_STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass

    if ng == 0:
        return 0        # ★門が効いている＝黙る
    text = ("【数字の門】★門そのものが効かなくなっています："
            "見本試験%d件中%d件が不合格。"
            "出典の無い数字がたまごさんまで素通りします。"
            "直すまで報告の数字を信じないでください"
            "（直近2日でこの門が止めた回数：%d回）" % (n, ng, tometa))
    try:
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now.isoformat(), "from": "kazu_gate",
                                "text": text}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print(text)
    return 1


def main():
    ap = argparse.ArgumentParser(
        description="数字と断定の門 — たまごさんに出す前に機械で落とす")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--file", default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--record", action="store_true",
                    help="通ったら台帳（status/suuji_daicho.jsonl）に数字を記録する")
    ap.add_argument("--why", default="", help="--record のときの但し書き")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--asa", action="store_true")
    ap.add_argument("--now", action="store_true", help="--asa を今すぐ試す")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    if a.self_test:
        n, ng, _ = self_test()
        return 1 if ng else 0
    if a.asa:
        return asa(force=a.now)

    if a.text is not None:
        text = a.text
    else:
        p = a.file or (a.files[0] if a.files else None)
        if p:
            p = p if os.path.isabs(p) else os.path.join(REPO, p)
            text = io.open(p, encoding="utf-8", errors="replace").read()
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            ap.print_help()
            return 0

    res = judge(text)
    if a.json:
        with io.open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    rc = show(res)
    _log("%s counted=%d hits=%s" % (
        "OK" if res["ok"] else "NG", res["counted"],
        ",".join(h["code"] for h in res["hits"]) or "-"))
    if rc == 0 and a.record:
        print("台帳に記録しました：%d件 → status/suuji_daicho.jsonl"
              % record(text, a.why))
    return rc


if __name__ == "__main__":
    sys.exit(main())
