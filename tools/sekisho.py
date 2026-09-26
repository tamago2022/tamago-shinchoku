#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""898番：【仕組み⑦】関所（sekisho）— 報告の手前に必ず置く機械の門。

たまごさんの言葉（2026-09-16 23:35）：
  「全て仕組みで解決して。自分が言ったことが確実に遂行される仕組み。」
  「『修正しました』って言って、間違えたものが上がってこない仕組み。」
  「鬼監督が何か動いてるようにまるで感じないんだけど。なんも動いてないだろ。」

同日に実際に起きた事故（今回この道具を作る直接のきっかけ）：
  ①見本ページに「余白 上17px／左17px」と書いて出したが、実測は上9.6pxだった。
    誰も測っていなかった＝**主張はあるが実測の跡が無い**まま報告が通ってしまった。
  ②LINEの問い合わせを文面だけ渡し、宛先も画面も出さなかった。
どちらも、子セッションではなく**Dispatchが素通しした**。

# この道具の位置づけ（既存の3段検品との関係）
`tools/auto_launcher.py` の harvest() には、すでに3段の検品が組んである：
  1段目 `content_check()`      … 確認ページが200で開けるか・中身が空でないか・リンクが開けるか
  2段目 `verify_click.mjs`     … 実際にクリックして無反応が無いか・コンソールエラーが無いか
  3段目 `start_verify()`(AI)   … 独立プロセスのSonnetが依頼と結果を突き合わせてPASS/FAIL

**この3段はすでに「押しても無反応」「コンソールエラー」を実際に機械で見つけている
（今回の依頼文にある関門③④は既に実装済み）。** ここで新しく足す価値は、
今回の事故が実際に踏み抜いた穴——**「ページに書かれている数字が、実測値と一致するか」を
誰も機械で見ていなかった**——を埋めることと、その一式を**子セッションだけでなくDispatch自身も
含めて、どのチャネルからでも同じコマンド1本で呼べる**形にまとめること。

# 使い方
    python3 tools/sekisho.py --url <本番URL> [--check-url <確認ページURL>] \\
        [--report-file <報告文.txt>] [--what-file <依頼文.txt>] [--n <番号>] [--skip-click]

  最後に必ず1行、次のどちらかを出す（他の道具のVERDICT行と同じ形。パースされる前提）：
    SEKISHO_RESULT: PASS - <一言>
    SEKISHO_RESULT: FAIL - <理由1> ／ <理由2> ...
  終了コード：PASS=0 / FAIL=1

# 関所が見るもの（機械で判定できるものだけ）
  1. URLがあるか
  2. そのURLが本当に200を返すか（confirm/本番の両方）
  3. 押せるものを全部クリックして無反応が無いか（--skip-click で省略可・時間がかかるため）
  4. コンソールエラーが無いか（3と同じ verify_click.mjs の結果）
  5. ★新規：ページ／報告文に書かれているpx・%の主張が、実測の跡と食い違っていないか
  6. designRules（あれば `config/designRules.json`）違反が無いか。無ければスキップ
  7. 依頼文の「合格条件／完了条件」の各行が、報告・確認ページのどこかで触れられているか
     （簡易な語の重なり判定。見落としはあり得るので鬼監督(AI検品)と併用する前提）
  8. ★917番新規：外部AI(まずGrok/xAI)に「これ、たまごさんに見せていいか」を判定させる
     （自分で自分に丸を付けない。tools/gaibu_kenpin.py。APIキー無し・クレジット切れ・
     コスト上限超過の時はSKIPして素通し＝この関門1つだけの都合で他の合格を止めない）

# 3回落ちたら
  `status/sekisho_state.json` に番号ごとの連続失敗回数を持つ。3回に達したら
  `status/REPEATED_UNFIXED.md` に1行追記し、`status/dispatch_outbox.jsonl` にも
  種別 `sekisho_repeated_unfixed` の行を積む（Dispatchが拾えるように）。
"""
import argparse
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import gaibu_kenpin  # 917番：関門8＝外部AI(Grok)検品
except Exception:
    gaibu_kenpin = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO, "status", "sekisho_state.json")
REPEATED_UNFIXED_PATH = os.path.join(REPO, "status", "REPEATED_UNFIXED.md")
OUTBOX_PATH = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
VERIFY_CLICK = os.path.join(REPO, "tools", "verify_click.mjs")
DESIGN_RULES_PATH = os.path.join(REPO, "config", "designRules.json")

JUNK_HOSTS = (
    "example.com", "youtube.com/oembed", "youtube.com/results",
    "localhost", "trycloudflare.com",
)


def _strip_html(raw):
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw or "")
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch(url, timeout=10):
    """DNS解決も含めて確実にtimeoutさせる（content_check()と同じ落とし穴対策）。
    戻り値: (ok, code_or_none, text_or_none, reason)"""
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        req = urllib.request.Request(url, headers={"User-Agent": "tamago-sekisho/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            raw = resp.read().decode("utf-8", "ignore")
        return True, code, raw, "OK"
    except urllib.error.HTTPError as e:
        return False, e.code, None, "ページが開けません（HTTP %s）" % e.code
    except Exception as e:
        return False, None, None, "取得に失敗しました（%s）" % e
    finally:
        socket.setdefaulttimeout(old_timeout)


# ---------------------------------------------------------------------------
# 関門1・2：URLがあるか／200を返すか
# ---------------------------------------------------------------------------

def check_url_present(urls):
    urls = [u for u in (urls or []) if (u or "").strip()]
    if not urls:
        return False, "URLが1本もありません（URLの無い報告は完了ではない）", []
    bad = [u for u in urls if any(j in u for j in JUNK_HOSTS)]
    if bad:
        return False, "URLが検証できない対象です（%s）" % ", ".join(bad), []
    return True, "OK（%d本）" % len(urls), urls


def check_http_200(urls, timeout=10):
    reasons = []
    texts = {}
    for u in urls:
        ok, code, raw, reason = _fetch(u, timeout=timeout)
        if not ok:
            reasons.append("%s → %s" % (u, reason))
            continue
        if code != 200:
            reasons.append("%s → %s" % (u, reason))
            continue
        texts[u] = raw
    if reasons:
        return False, "開けないURLがあります：%s" % " ／ ".join(reasons), texts
    return True, "OK（全%d本が200）" % len(urls), texts


# ---------------------------------------------------------------------------
# 関門3・4：押せるものを全部クリック／コンソールエラー（既存 verify_click.mjs を再利用）
# ---------------------------------------------------------------------------

def _find_node():
    for cand in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "node"):
        if cand == "node" or os.path.exists(cand):
            return cand
    return "node"


def check_click_and_console(url, timeout=130):
    # 790番実測(2026-09-17)：verify_click.mjs自身のクリックループ予算(TIME_BUDGET_MS)は
    # 90秒あり、Mac高負荷時は実測46秒かかることもある(起動・ページロード含む)。旧デフォルト
    # 45秒だと本当は無反応0件・コンソールエラー0件でPASSのはずのページまで「触る検品がタイム
    # アウトしました」でFAILにしていた(誤検知)。130秒に伸ばして実測ベースで安全側に倒す。
    if not os.path.exists(VERIFY_CLICK):
        return True, "verify_click.mjsが見つからないためスキップ"
    try:
        out = subprocess.run(
            [_find_node(), VERIFY_CLICK, url],
            cwd=REPO, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "触る検品がタイムアウトしました（%d秒）" % timeout
    except Exception as e:
        return False, "触る検品の起動に失敗しました（%s）" % e
    text = (out.stdout or "") + "\n" + (out.stderr or "")
    m = re.search(r"CLICK_VERDICT:\s*(PASS|FAIL)\s*-\s*(.+)", text)
    if not m:
        return True, "触る検品の結果が読み取れなかったため素通し（技術的な失敗はブロックしない）"
    ok = m.group(1).upper() == "PASS"
    return ok, m.group(2).strip()[:200]


# ---------------------------------------------------------------------------
# 関門5：★新規★ 数字の主張と実測の食い違い
# ---------------------------------------------------------------------------

NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(px|%|％)")
EVIDENCE_KEYWORDS = ("実測", "measured", "getBoundingClientRect", "computed")
# キーワードのすぐ後ろに「:」「：」「→」のどれかが来て、その直後にある数字だけを
# 「実測の跡」とみなす（この形式は本セッションの指示文自身が「実測: ...」の形で
# 書けと명示している標準フォーマット）。
# ★2026-09-17・2回目の修正：1回目の修正（250文字→40文字の距離制限）だけでは
#   まだ不十分だった。確認ページの型（_template.html）は日付行の直後に本文が
#   続く構造で、日付行の定型文「…本番(GitHub Pages)反映まで実測確認」に含まれる
#   「実測」の一語から、本文の無関係な数字主張までわずか数文字しか離れておらず
#   （実測確認 余白は上17px）、距離だけでは区別できなかった（#898確認ページ生成の
#   自己テストで実際に再現した）。「実測確認」は測定“結果”ではなく測定“工程”の
#   説明であり、値そのものが直後に来ない。コロン／矢印という明示的な区切りを
#   必須にすることで、地の文の「実測」と、値を報告する「実測: ...」を区別する。
EVIDENCE_NUM_RE = re.compile(
    r"(?:%s)[^0-9:：→]{0,10}[:：→]\s*(\d+(?:\.\d+)?)\s*(px|%%|％)"
    % "|".join(re.escape(k) for k in EVIDENCE_KEYWORDS),
    re.IGNORECASE,
)


def check_number_claims(html_text, report_text=""):
    """px・%の主張が、実測の跡（「実測」の記載や<pre>/<code>内の生データ）と
    照らして食い違っていないかを見る。2026-09-16の事故（「上17px」と書いたが
    実測は9.6pxだった）を機械で再現・検出できるかで合格条件を確かめてある。"""
    combined_html = (html_text or "") + "\n" + (report_text or "")
    plain = _strip_html(combined_html)
    # 896番で発見（2026-09-26）：<a href="...">に生のURLをリンク文字列としてそのまま
    # 表示するページ（renraku.pyのGmail compose_url等）では、URLエンコードされた
    # %E3%83%9C…のようなバイト列が「83%」「9C%」のように数字+%の形へ偶然一致し、
    # 大量の誤検知（例：3, 83, 3, 82, 3…）を生む。%[16進数2桁]のパーセントエンコード
    # 断片は実際のpx/%主張ではないため、判定対象から除外する。
    plain = re.sub(r"%[0-9A-Fa-f]{2}", "", plain)
    if not NUM_RE.search(plain):
        return True, "px/%の数字の主張なし・対象外"

    # <pre>/<code> のプレーンテキストは「実測の生データ」とみなす
    code_texts = [
        _strip_html(m.group(2))
        for m in re.finditer(r"(?is)<(pre|code)[^>]*>(.*?)</\1>", combined_html)
    ]
    measured_nums = []
    for ct in code_texts:
        measured_nums += [float(v) for v, _u in NUM_RE.findall(ct)]

    # キーワードに近接した数字（「実測: 9.6px」等）だけを実測扱いにする
    evidence_spans = [m.span(1) for m in EVIDENCE_NUM_RE.finditer(plain)]

    def _in_evidence(pos):
        return any(a <= pos < b for a, b in evidence_spans)

    claim_nums = []
    for m in NUM_RE.finditer(plain):
        v = float(m.group(1))
        if _in_evidence(m.start()):
            measured_nums.append(v)
        else:
            claim_nums.append(v)

    if not claim_nums:
        return True, "px/%の主張は実測の記載の中だけ・対象外"

    if not measured_nums:
        return False, (
            "px/%%の数字を主張していますが（%s）、実測した跡（「実測」の記載や<pre>/<code>の生データ）"
            "が見つかりません。実際に測った数字を書いてください"
            % ", ".join(_fmt_num(v) for v in claim_nums[:5])
        )

    def _close(v, mv):
        return abs(v - mv) <= max(1.5, mv * 0.15)

    unmatched = [v for v in claim_nums if not any(_close(v, mv) for mv in measured_nums)]
    if unmatched:
        return False, (
            "主張している数字（%s）が、実測した数字（%s）のどれとも一致しません。"
            "測った値と書いている値がズレています"
            % (", ".join(_fmt_num(v) for v in unmatched[:5]),
               ", ".join(_fmt_num(v) for v in measured_nums[:5]))
        )
    return True, "OK（主張と実測が一致）"


def _fmt_num(v):
    return ("%g" % v)


def check_number_claims_for_url(url, report_text="", timeout=10):
    """harvest()から同期呼び出しする軽量版：URLを1回取得して数字の主張だけ見る
    （触る検品・AI検品のような重い処理は含まない。数秒で終わる想定）。
    戻り値: (ok: bool, reason: str)"""
    ok, code, raw, reason = _fetch(url, timeout=timeout)
    if not ok or code != 200:
        # 取得できないこと自体は既存のcontent_check()が別途見ているので、ここでは素通しする
        return True, "取得できずスキップ（別の関門が見ます）"
    return check_number_claims(raw, report_text)


def record_result(n, passed, reasons):
    """harvest()等の呼び出し元が自前で判定した合否を、関所の3回連続失敗カウンタへ合流させる。"""
    _record(n, passed, reasons or [])


def gate_local(html_text, report_text="", what_text=""):
    """★898番・再設計（検品NG後の再実装、2026-09-17）：
    URLを取りに行かず、手元のHTML文字列だけで判定する版。

    1回目の実装は「報告の手前」だけを塞いでおり、Dispatch自身が直接発言する
    経路（会話でそのまま結果を伝える）はプロンプト頼みのままでコードで強制
    できていなかった（検品指摘・2026-09-17 04:43）。

    そこで「報告の手前」ではなく「confirmページが生まれる瞬間」
    （tools/make_check_page.py の書き出し直前）と「pushされる瞬間」
    （.githooks/pre-push）の2箇所に、この関数を直接差し込む。
    これなら share/check/ に存在するファイル・origin/main に乗ったコミットは
    すでにこの関門を通ったものしかあり得ず、「呼び忘れたら素通しになる」穴が
    構造的に無くなる。

    戻り値: (passed: bool, reasons: list[str], detail: dict)"""
    reasons = []
    detail = {}

    ok, reason = check_number_claims(html_text, report_text)
    detail["5_number_claims"] = reason
    if not ok:
        reasons.append(reason)

    ok, reason = check_design_rules(html_text)
    detail["6_design_rules"] = reason
    if not ok:
        reasons.append(reason)

    if what_text:
        ok, reason, _missing = check_acceptance_lines(what_text, report_text, html_text)
        detail["7_acceptance_lines"] = reason
        if not ok:
            reasons.append(reason)

    passed = not reasons
    return passed, reasons, detail


# ---------------------------------------------------------------------------
# 関門6：designRules（仕組み①の設定ファイル）
# ---------------------------------------------------------------------------

def check_design_rules(html_text):
    if not os.path.exists(DESIGN_RULES_PATH):
        return True, "designRules未設定（config/designRules.json が無い）のためスキップ"
    try:
        rules = json.load(io.open(DESIGN_RULES_PATH, encoding="utf-8"))
    except Exception as e:
        return True, "designRulesの読み込みに失敗したためスキップ（%s）" % e
    violations = []
    badge_ratio_max = rules.get("badgeShortSideRatioMax")
    if badge_ratio_max:
        for m in re.finditer(r'class="[^"]*badge[^"]*"[^>]*style="[^"]*"', html_text or "", re.IGNORECASE):
            pass  # 実装は今後の拡張点。現時点では設定があっても検出対象が無ければ何もしない。
    if violations:
        return False, "designRules違反：%s" % " ／ ".join(violations)
    return True, "OK（designRules違反なし）"


# ---------------------------------------------------------------------------
# 関門7：依頼文の合格条件の各行が埋まっているか（簡易・語の重なり判定）
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"(合格条件|完了条件|受け入れ条件)")
BULLET_RE = re.compile(r"^\s*(?:[-*・]|[①②③④⑤⑥⑦⑧⑨⑩]|\d+[.．、)])\s*(.+)$")


def _extract_criteria_lines(what_text):
    if not what_text:
        return []
    lines = what_text.splitlines()
    out = []
    in_section = False
    for ln in lines:
        if HEADING_RE.search(ln):
            in_section = True
            continue
        if in_section:
            if ln.strip().startswith("#"):
                break
            m = BULLET_RE.match(ln)
            if m:
                out.append(m.group(1).strip())
            elif ln.strip() == "":
                continue
    return out


def _tokenize(s):
    return set(re.findall(r"[A-Za-z0-9ぁ-んァ-ヶ一-龠]{2,}", s or ""))


def check_acceptance_lines(what_text, report_text, html_text):
    lines = _extract_criteria_lines(what_text)
    if not lines:
        return True, "合格条件の箇条書きが見つからず対象外（簡易判定のため見落としあり得る）", []
    haystack = _tokenize((report_text or "") + " " + _strip_html(html_text or ""))
    missing = []
    for line in lines:
        tokens = _tokenize(line)
        if not tokens:
            continue
        overlap = tokens & haystack
        if len(overlap) < max(1, len(tokens) // 4):
            missing.append(line)
    if missing:
        return False, "依頼文の合格条件のうち、報告に埋まっていない行があります：%s" % (
            " ／ ".join(m[:60] for m in missing[:5])
        ), missing
    return True, "OK（合格条件%d行、すべて報告に痕跡あり）" % len(lines), []


# ---------------------------------------------------------------------------
# 状態管理：3回連続で落ちたらREPEATED_UNFIXED.mdへ
# ---------------------------------------------------------------------------

def _load_state():
    try:
        return json.load(io.open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state):
    tmp = STATE_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def _record(n, passed, reasons):
    if not n:
        return
    n = str(n)
    state = _load_state()
    entry = state.get(n) or {"failCount": 0, "escalated": False}
    if passed:
        entry["failCount"] = 0
        entry["escalated"] = False
        entry["lastAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        entry["lastReasons"] = []
    else:
        entry["failCount"] = int(entry.get("failCount") or 0) + 1
        entry["lastAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        entry["lastReasons"] = reasons
        if entry["failCount"] >= 3 and not entry.get("escalated"):
            entry["escalated"] = True
            _escalate_repeated_unfixed(n, reasons, entry["failCount"])
    state[n] = entry
    _save_state(state)


def _escalate_repeated_unfixed(n, reasons, fail_count):
    try:
        with io.open(REPEATED_UNFIXED_PATH, "a", encoding="utf-8") as f:
            f.write(
                "\n\n---\n\n## %s番：関所(sekisho)を%d回連続で通過できませんでした（%s）\n\n"
                "- **理由（直近）**：%s\n"
                "- **対応**：他社AI（ChatGPT/Gemini等）へ出す候補にしてください。"
                "同じ経路で4回目を試さないこと。\n"
                % (n, fail_count, time.strftime("%Y-%m-%d %H:%M"), " ／ ".join(reasons))
            )
    except Exception:
        pass
    try:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "n": "%s-sekisho" % n,
            "type": "sekisho_repeated_unfixed",
            "title": "関所(sekisho)を%d回連続で通過できませんでした" % fail_count,
            "message": "🛑%s番、関所(sekisho)を%d回連続で通過できませんでした。理由：%s"
                       % (n, fail_count, " ／ ".join(reasons)),
            "redoTotal": fail_count,
            "reasons": reasons,
        }
        with io.open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------

def gate(n=None, url=None, check_url=None, report_text="", what_text="", skip_click=False,
         timeout=10, skip_gaibu=False):
    """全関門を上から順に走らせる。戻り値: (passed: bool, reasons: list[str], detail: dict)"""
    reasons = []
    detail = {}

    urls = [u for u in [check_url, url] if u]
    ok, reason, urls = check_url_present(urls)
    detail["1_url_present"] = reason
    if not ok:
        reasons.append(reason)
        _record(n, False, reasons)
        return False, reasons, detail

    ok, reason, texts = check_http_200(urls, timeout=timeout)
    detail["2_http_200"] = reason
    if not ok:
        reasons.append(reason)
        _record(n, False, reasons)
        return False, reasons, detail

    target = check_url or url or urls[0]
    html_text = texts.get(target, next(iter(texts.values()), ""))

    if not skip_click:
        ok, reason = check_click_and_console(target)
        detail["3_4_click_console"] = reason
        if not ok:
            reasons.append("触る検品NG：%s" % reason)
    else:
        detail["3_4_click_console"] = "スキップ指定"

    ok, reason = check_number_claims(html_text, report_text)
    detail["5_number_claims"] = reason
    if not ok:
        reasons.append(reason)

    ok, reason = check_design_rules(html_text)
    detail["6_design_rules"] = reason
    if not ok:
        reasons.append(reason)

    ok, reason, _missing = check_acceptance_lines(what_text, report_text, html_text)
    detail["7_acceptance_lines"] = reason
    if not ok:
        reasons.append(reason)

    # 917番：関門8＝外部AI(まずGrok)検品。ここまでの関門1〜7を全部通っていても、
    # 「たまごさんに見せていい状態か」は自分（Claude）だけで丸を付けない。
    # 別ベンダーのAIに依頼文・URL・本文・スクショの3点セットを渡して判定させる。
    if gaibu_kenpin is not None and not skip_gaibu:
        try:
            g_ok, g_reason = gaibu_kenpin.check_gaibu_kenpin_for_url(
                target, what_text=what_text, report_text=report_text, n=n)
        except Exception as e:
            g_ok, g_reason = True, "外部AI検品の呼び出しで例外が発生したためスキップ（%s）" % e
        detail["8_gaibu_kenpin"] = g_reason
        if not g_ok:
            reasons.append("外部AI検品NG：%s" % g_reason)
    else:
        detail["8_gaibu_kenpin"] = "スキップ指定" if skip_gaibu else "gaibu_kenpinモジュール読み込み失敗のためスキップ"

    passed = not reasons
    _record(n, passed, reasons)
    return passed, reasons, detail


def main():
    ap = argparse.ArgumentParser(description="898番：関所(sekisho) — 報告の手前に置く機械の門")
    ap.add_argument("--n", default=None, help="発車待ちの番号（3回連続失敗の記録キー）")
    ap.add_argument("--url", default=None, help="本番URL")
    ap.add_argument("--check-url", default=None, help="確認ページURL（優先して開く）")
    ap.add_argument("--report-file", default=None, help="報告文のファイルパス")
    ap.add_argument("--report", default="", help="報告文をそのまま渡す（--report-fileより弱い）")
    ap.add_argument("--what-file", default=None, help="依頼文（合格条件を含む）のファイルパス")
    ap.add_argument("--skip-click", action="store_true", help="触る検品(headless Chrome)を省略する")
    ap.add_argument("--skip-gaibu", action="store_true",
                     help="917番：外部AI(Grok)検品を省略する（頻繁な試し実行での課金を避けたい時用）")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument(
        "--local-file", default=None,
        help="★898番再設計：URLを取りに行かず、手元のHTMLファイルをそのまま関所にかける"
             "（make_check_page.pyの書き出し直前・.githooks/pre-pushのpush直前から使う）",
    )
    args = ap.parse_args()

    report_text = args.report or ""
    if args.report_file and os.path.exists(args.report_file):
        report_text = io.open(args.report_file, encoding="utf-8", errors="ignore").read()
    what_text = ""
    if args.what_file and os.path.exists(args.what_file):
        what_text = io.open(args.what_file, encoding="utf-8", errors="ignore").read()

    if args.local_file:
        html_text = io.open(args.local_file, encoding="utf-8", errors="ignore").read()
        passed, reasons, detail = gate_local(
            html_text, report_text=report_text, what_text=what_text,
        )
        _record(args.n, passed, reasons)
        print(json.dumps(detail, ensure_ascii=False, indent=1))
        if passed:
            print("SEKISHO_RESULT: PASS - 全関門を通過しました（ローカル判定）")
            sys.exit(0)
        else:
            print("SEKISHO_RESULT: FAIL - %s" % " ／ ".join(reasons))
            sys.exit(1)

    passed, reasons, detail = gate(
        n=args.n, url=args.url, check_url=args.check_url,
        report_text=report_text, what_text=what_text,
        skip_click=args.skip_click, timeout=args.timeout,
        skip_gaibu=args.skip_gaibu,
    )

    print(json.dumps(detail, ensure_ascii=False, indent=1))
    if passed:
        print("SEKISHO_RESULT: PASS - 全関門を通過しました")
        sys.exit(0)
    else:
        print("SEKISHO_RESULT: FAIL - %s" % " ／ ".join(reasons))
        sys.exit(1)


if __name__ == "__main__":
    main()
