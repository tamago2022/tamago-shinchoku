#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
931番「Claudeが作ったChromeタブの孤児を、たまごさんの手を借りずに自分で片付ける」

たまごさんの言葉（そのまま）：
> 「それを俺に閉じさせるっていうのがまず違うんだよ。発想が。仕事を増やしちゃだめだよ。
>   食い散らかして『あと片付けておいてください』って言ってるようなもんだよ。」

何が起きていたか（実測）：
  子セッションはそれぞれ Claude in Chrome で自分のタブグループを作る。セッションが終わっても
  グループは残り、**他のセッションからは見えない・閉じられない**（tabs_context_mcp は自分の分しか
  返さない）。結果、Chromeに10枚以上のタブが溜まり、たまごさんのMacが重くなって
  タイピングも音声入力もできなくなった。

ここが埋める穴：
  「セッションが自分で閉じる」だけでは、セッションが落ちた／忘れた瞬間に孤児になる。
  **セッションの外側（Mac上で回り続ける工場）から定期的に掃く**ことで、
  誰が忘れても最後は必ず片付く形にする。

絶対に守ること（tools/prompt_rules/topic-browser-dont-steal-screen.md と同じ憲法）：
  1. **Chromeが起動していなければ何もしない。**（osascript で Chrome を起こさない）
  2. **activate しない。**前面に出さない。たまごさんの画面を奪わない。
  3. **たまごさんの作業タブは絶対に閉じない。**閉じてよいのは「Claudeが作ったと確実に言えるタブ」だけ。
     **見分けがつかないものは残す。**（迷ったら残す側へ倒す＝誤って閉じる方が害が大きい）
  4. **ウィンドウの前面タブ（active tab）は閉じない。**たまごさんが今見ている可能性があるため。
  5. **ウィンドウの最後の1枚は閉じない。**閉じるとウィンドウごと消えるため。

たまごさんの開いているタブのURLは **絶対にgit管理下へ書かない**（このリポジトリは GitHub Pages で
公開されている）。`status/*` は .gitignore で除外されているのでそこにだけ置く。

使い方:
  python3 tools/chrome_tab_sweeper.py --recon    # 数えて記録するだけ。1枚も閉じない
  python3 tools/chrome_tab_sweeper.py --sweep    # 実際に閉じる（1時間に1回だけ実走する間引き付き）
  python3 tools/chrome_tab_sweeper.py --sweep --force   # 間引きを無視して今すぐ走る
  python3 tools/chrome_tab_sweeper.py --sweep --dry-run # 閉じる対象を判定するだけで閉じない
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status")
RECON_PATH = os.path.join(STATUS, "chrome_tabs_recon.json")   # .gitignore済み（status/*）
SWEEP_LOG = os.path.join(STATUS, "chrome_sweep.json")          # .gitignore済み（status/*）
HISTORY_PATH = os.path.join(STATUS, "chrome_tab_history.json")  # .gitignore済み（status/*）
GATE_PATH = os.path.join(STATUS, ".chrome_sweep_last")
# ★2026-09-19 実測でここを詰めた。
#   直す前：1時間に1回。しかも **Chromeが起動していなくても gate を消費していた**。
#   実際のログ（status/chrome_sweep.json）：02:28「Chrome起動してない」→ 1枚も閉じずに1時間分を消費、
#   03:29 も同じ。そして 04:07 にChromeが起動して孤児タブが2枚あるのに、04:29 まで掃けない状態だった。
#   → gate は「実際に掃いたときだけ」進める。間隔も15分に詰める（osascriptで読むだけなので軽い）。
GATE_SECONDS = 900  # 15分に1回

# 「一度も前面に来ていない」を孤児の証拠として採用するまでの条件（両方満たすこと）
ORPHAN_MIN_SAMPLES = 120      # 心臓（15秒おき）で約30分ぶんの観測回数
ORPHAN_MIN_AGE_SEC = 7200     # 最初に見てから2時間以上経っている

# 区切り（タブのURL・タイトルに出ない文字を選ぶ）
SEP = "\x1f"
ROWSEP = "\x1e"


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 1. Chromeが「既に起動しているか」だけを、Chromeに触らずに見る
# ---------------------------------------------------------------------------
def chrome_is_running():
    """pgrep だけで判定する。

    `osascript -e 'tell application "Google Chrome" ...'` は、Chromeが起動していないときに
    **Chromeを起動してしまう**（たまごさんの画面に突然ブラウザが出る＝憲法違反）。
    そのため生死判定に osascript を一切使わない。
    """
    try:
        r = subprocess.run(["pgrep", "-x", "Google Chrome"],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2. タブ一覧を読む（読むだけ。activateしない）
# ---------------------------------------------------------------------------
LIST_SCRIPT = r'''
on esc(s)
  return s
end esc
tell application "Google Chrome"
  set out to ""
  set wi to 0
  repeat with w in windows
    set wi to wi + 1
    set ai to active tab index of w
    set ti to 0
    repeat with t in tabs of w
      set ti to ti + 1
      set u to ""
      set ttl to ""
      try
        set u to URL of t
      end try
      try
        set ttl to title of t
      end try
      set isActive to "0"
      if ti = ai then set isActive to "1"
      set out to out & wi & "%SEP%" & ti & "%SEP%" & isActive & "%SEP%" & u & "%SEP%" & ttl & "%ROWSEP%"
    end repeat
  end repeat
  return out
end tell
'''


def list_tabs():
    """[{win, idx, active, url, title}] を返す。Chromeが居ないときは None。"""
    if not chrome_is_running():
        return None
    script = LIST_SCRIPT.replace("%SEP%", SEP).replace("%ROWSEP%", ROWSEP)
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    rows = []
    for raw in r.stdout.split(ROWSEP):
        raw = raw.strip("\n\r")
        if not raw:
            continue
        parts = raw.split(SEP)
        if len(parts) < 5:
            continue
        try:
            rows.append({
                "win": int(parts[0]),
                "idx": int(parts[1]),
                "active": parts[2] == "1",
                "url": parts[3],
                "title": parts[4],
            })
        except ValueError:
            continue
    return rows


# ---------------------------------------------------------------------------
# 3. 「Claudeが作ったタブ」の見分け方
# ---------------------------------------------------------------------------
# ★ここが一番慎重にすべき所。**確実にClaudeのものだと言えるものしか入れない。**
#   たまごさんが自分で開いている可能性が1%でもあるURLは入れない。
#   （X・YouTube・Lovable・ChatGPT・Gmail・GitHub などは**全部たまごさんの作業タブ**でもありうるので対象外）
#
# Claude in Chrome の実際の作り方：`tabs_create_mcp` はまず空のタブ（about:blank／新しいタブ）を
# 作り、そこへ `navigate` する。セッションが落ちると、その空タブや、最後に navigate した
# 内部向けページがそのまま残る。閉じても何も失われないものだけをここに列挙する。
CLOSE_EXACT = {
    "about:blank",
    "chrome://newtab/",
    "chrome://new-tab-page/",
    "chrome://new-tab-page-third-party/",
    "",  # URLが空＝読み込み前の空タブ
}

# 前方一致で閉じてよいもの（Claudeが検品・実測で開く自分の成果物ページだけ）
CLOSE_PREFIXES = (
    "https://tamago2022.github.io/tamago-shinchoku/share/check/",
)

# ★保険：ここに1つでも当たったら、上の条件に合っていても**絶対に閉じない**。
#   たまごさんの作業タブ・ログインが要るサービス・作業中のツールを守る最後の壁。
NEVER_CLOSE_PATTERNS = (
    r"^https?://(www\.)?(x|twitter)\.com",
    r"^https?://([a-z0-9-]+\.)*youtube\.com",
    r"^https?://youtu\.be",
    r"^https?://([a-z0-9-]+\.)*lovable\.(app|dev)",
    r"^https?://([a-z0-9-]+\.)*chatgpt\.com",
    r"^https?://([a-z0-9-]+\.)*openai\.com",
    r"^https?://([a-z0-9-]+\.)*grok\.com",
    r"^https?://([a-z0-9-]+\.)*google\.com",
    r"^https?://([a-z0-9-]+\.)*gmail\.com",
    r"^https?://([a-z0-9-]+\.)*github\.com",
    r"^https?://([a-z0-9-]+\.)*devin\.ai",
    r"^https?://([a-z0-9-]+\.)*line\.me",
    r"^https?://([a-z0-9-]+\.)*claude\.ai",   # たまごさんがClaudeを使っている画面そのもの
    r"^file://",
    r"^chrome-extension://",
    r"^chrome://(?!newtab|new-tab-page)",     # 設定・拡張機能などたまごさんが開いた内部ページ
)
_never = [re.compile(p, re.I) for p in NEVER_CLOSE_PATTERNS]


# ---------------------------------------------------------------------------
# 3-b. 「一度も前面に来たことがないタブ」を実測で見つける
# ---------------------------------------------------------------------------
# URLの見た目だけでは、Claudeが開いたのか たまごさんが開いたのか分からないタブが必ず残る。
# そこで**観測**を証拠にする：この掃除機は心臓（15秒おき）から `--recon` で呼ばれ続けるので、
# 各タブが「これまで一度でも前面（active）になったか」を記録できる。
#   たまごさんが自分で開いたタブは、開いた瞬間に必ず前面になる（＝everActiveが立つ）。
#   機械が裏で作ったタブは、2時間ずっと一度も前面に来ない。
# 「2時間以上・120回以上観測して一度も前面に来ていない」なら、機械が作った孤児と見なす。
# **ただし NEVER_CLOSE_PATTERNS はこの判定より強い**（たまごさんが何日も裏に置いたままに
# しているLovableやXのタブを、触っていないという理由だけで閉じては絶対にいけない）。
def load_history():
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f).get("urls", {})
    except Exception:
        return {}


def update_history(tabs):
    """観測を1回ぶん積んで、更新後の履歴を返す。今Chromeに無いURLは捨てる（=閉じられた/移動した）。"""
    import time
    now = time.time()
    old = load_history()
    new = {}
    for t in tabs:
        url = (t.get("url") or "").strip()
        if not url:
            continue
        prev = old.get(url) or {}
        # ★観測が途切れていたら、そのURLの記録は捨てて数え直す。
        #   Chromeを終了→再起動すると「前回開いていたタブ」が復元される。復元直後のタブは
        #   たまごさんが開いたものでも「まだ一度も前面に来ていない」状態なので、
        #   古い記録を引き継ぐと**たまごさんのタブを孤児と誤判定して閉じてしまう。**
        if prev and (now - prev.get("lastSeen", 0)) > 600:
            prev = {}
        new[url] = {
            "firstSeen": prev.get("firstSeen", now),
            "lastSeen": now,
            "samples": int(prev.get("samples", 0)) + 1,
            "everActive": bool(prev.get("everActive", False)) or bool(t.get("active")),
        }
    write_json(HISTORY_PATH, {"updatedAt": now_iso(), "urls": new})
    return new


def looks_orphan(url, hist):
    h = hist.get(url)
    if not h or h.get("everActive"):
        return False
    return (h.get("samples", 0) >= ORPHAN_MIN_SAMPLES
            and (h.get("lastSeen", 0) - h.get("firstSeen", 0)) >= ORPHAN_MIN_AGE_SEC)


def classify(tab, hist=None, reserved=None):
    """('close'|'keep', 理由) を返す。迷ったら必ず keep。

    reserved: 978番「予約閉栓」で先に決まった閉じる対象 {(win, idx): 理由}。
      セッションが**開く前に**自分で置いた票の期限が切れたもの＝作った本人が
      「落ちたら閉じてよい」と宣言済みなので、NEVER_CLOSE より先に判定してよい。
      ただし前面タブ（active）は何があっても閉じない（この上の行が先に効く）。
    """
    hist = hist or {}
    url = (tab.get("url") or "").strip()
    if tab.get("active"):
        return "keep", "ウィンドウの前面タブ（たまごさんが見ている可能性）"
    if reserved and (tab.get("win"), tab.get("idx")) in reserved:
        return "close", reserved[(tab.get("win"), tab.get("idx"))]
    for rx in _never:
        if rx.search(url):
            return "keep", "たまごさんの作業タブになりうるサービス"
    if url in CLOSE_EXACT:
        # ★2026-09-26 実測で足した1行。
        #   別のセッションが新しいタブを開いた直後（まだ chrome://newtab のまま）に
        #   ここで閉じてしまい、**MCPのタブグループごと消えて作業が始められなかった**
        #   （tabs_context_mcp が "No group with id" を返し続けた）。
        #   空タブは逃げないので、90秒だけ待ってから閉じる。掃除の目的は損なわれない。
        import time as _t
        h = hist.get(url) or {}
        first = h.get("firstSeen")
        if first and (_t.time() - first) < 90:
            return "keep", "できたばかりの空タブ（他のセッションが今から使う可能性・90秒待つ）"
        if not first:
            return "keep", "はじめて見た空タブ（次の回に判断する）"
        return "close", "空タブ（閉じても何も失われない）"
    if url.startswith(CLOSE_PREFIXES):
        return "close", "Claudeが検品で開いた確認ページ"
    if looks_orphan(url, hist):
        return "close", "2時間以上・一度も前面に来ていない（機械が作った孤児）"
    return "keep", "Claudeが作ったと確証が持てない（見分けがつかないものは残す）"


# ---------------------------------------------------------------------------
# 3-c. 「同じURLが何枚も開いている」を畳む（世の中で普通に使われている手）
# ---------------------------------------------------------------------------
# 出どころ：AppleScriptでChromeの重複タブを閉じる、という定番の手
#   （Olaf Alders "Closing Duplicate Tabs With AppleScript" ほか、同種のスクリプトが多数ある）
#
# なぜこれが要るか（2026-09-19 実測）：
#   孤児の空タブを2枚掃いた後も6枚残り、その中身は
#     ・同一URLの app.devin.ai が **3枚**
#     ・同一URLの github.com/…/pull/425 が **2枚**
#   だった。これは NEVER_CLOSE（たまごさんの作業タブになりうる）で守られていて永遠に減らない。
#   しかし **同じURLの2枚目以降を閉じても、そのページは1枚目に残ったまま**で、何も失われない。
#   「見分けがつかないものは残す」という憲法に真っ向から沿ったまま、実際に枚数が減る唯一の手。
#
# 守ること：
#   ・残すのは各URLにつき1枚。前面タブがあればそれを残す。無ければ一番手前（index最小）を残す。
#   ・URLが空／about:blank／newtab は対象外（別ルールで既に扱っている）。
#   ・ウィンドウをまたいでは畳まない（別ウィンドウは別の用途で開いている可能性がある）。
def mark_duplicates(judged):
    """同一ウィンドウ内で同一URLが2枚以上あるとき、1枚だけ残して残りを close にする。"""
    groups = {}
    for i, (t, (verdict, why)) in enumerate(judged):
        url = (t.get("url") or "").strip()
        if not url or url in CLOSE_EXACT:
            continue
        groups.setdefault((t["win"], url), []).append(i)

    out = list(judged)
    for (_win, _url), idxs in groups.items():
        if len(idxs) < 2:
            continue
        # 残す1枚を決める：前面タブ優先、無ければ一番手前
        keep = None
        for i in idxs:
            if out[i][0].get("active"):
                keep = i
                break
        if keep is None:
            keep = min(idxs, key=lambda i: out[i][0]["idx"])
        for i in idxs:
            if i == keep:
                continue
            if out[i][0].get("active"):
                continue  # 念のため。前面タブは何があっても閉じない
            t = out[i][0]
            out[i] = (t, ("close", "同じURLが%d枚開いている重複（1枚は残す）" % len(idxs)))
    return out


CLOSE_SCRIPT = r'''
tell application "Google Chrome"
  set w to window %WIN%
  if (count of tabs of w) <= 1 then return "SKIP_LAST"
  set t to tab %IDX% of w
  if (URL of t) is not equal to "%URL%" then return "SKIP_MOVED"
  close t
  return "CLOSED"
end tell
'''


def close_tab(win, idx, url):
    """1枚だけ閉じる。activate しない。閉じる直前にURLを照合して取り違えを防ぐ。"""
    script = (CLOSE_SCRIPT
              .replace("%WIN%", str(win))
              .replace("%IDX%", str(idx))
              .replace("%URL%", url.replace("\\", "\\\\").replace('"', '\\"')))
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return "ERROR"
    if r.returncode != 0:
        return "ERROR"
    return r.stdout.strip() or "ERROR"


# ---------------------------------------------------------------------------
# 4. 記録（URLは書かない。件数と理由の内訳だけ）
# ---------------------------------------------------------------------------
def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def append_sweep_log(entry, keep=200):
    hist = []
    if os.path.exists(SWEEP_LOG):
        try:
            with open(SWEEP_LOG, encoding="utf-8") as f:
                hist = json.load(f).get("runs", [])
        except Exception:
            hist = []
    hist.append(entry)
    hist = hist[-keep:]
    total = sum(r.get("closed", 0) for r in hist)
    write_json(SWEEP_LOG, {
        "updatedAt": now_iso(),
        "closedTotalInLog": total,
        "lastRun": entry,
        "runs": hist,
    })


# ---------------------------------------------------------------------------
# 978番「予約閉栓」：セッションが途中で死んでも孤児が残らないようにする
# ---------------------------------------------------------------------------
# たまごさんの枷：**「最後にまとめて閉じる」は禁止。セッションは途中で死ぬ。**
# 2026-09-21 実測：claude-in-chrome 拡張は tabs_context_mcp がタブIDを返した直後の1手で
# 「このセッションのタブグループに無い」を5回中5回返した。その間に recon のタブ数は
# 14枚→18枚に増えている＝**タブは消えていない。拡張側の登録だけが消え、タブ本体が孤児になる。**
# この状態では「セッションが自分で閉じる」は原理的に間に合わない（閉じる相手を見失っている）。
# → タブを**開く前に**外側（この掃除機）へ票を預けさせ、心拍が止まったら掃除機が閉じる。
#
# 安全側（この道具の憲法をそのまま継承する）：
#   ・前面タブ（active）は閉じない（classify の1行目が先に効く）
#   ・ウィンドウの最後の1枚は閉じない（CLOSE_SCRIPT の SKIP_LAST）
#   ・**たまごさんが一度でも前面に出したURLは閉じない**（history の everActive）
#   ・票に書いた枚数までしか閉じない（同じURLをたまごさんも開いていたら巻き添えにしない）
#   ・閉じる直前にindexのURLが票と一致するか確認する（SKIP_MOVED）
try:
    import chrome_reserve as _reserve
except ImportError:  # 単体で置かれた場合でも掃除機は止めない
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import chrome_reserve as _reserve
    except ImportError:
        _reserve = None


def pick_reserved(tabs, hist):
    """期限切れの票から、閉じてよいタブ {(win, idx): 理由} を作る。票が無ければ空。"""
    if _reserve is None:
        return {}
    try:
        exp = _reserve.expired_urls()
    except Exception:
        return {}
    if not exp:
        return {}
    hist = hist or {}
    out = {}
    for url, info in exp.items():
        h = hist.get(url) or {}
        if h.get("everActive"):
            continue  # たまごさんが前面に出したことがある＝本人のもの。触らない
        # 同じURLのタブのうち、前面でないものを **後ろ（index大＝後から開かれた方）から** 取る
        cands = [t for t in tabs
                 if (t.get("url") or "").strip() == url and not t.get("active")]
        cands.sort(key=lambda t: (t["win"], t["idx"]), reverse=True)
        for t in cands[:max(1, int(info.get("count", 1)))]:
            out[(t["win"], t["idx"])] = ("予約閉栓：票 %s の心拍が止まった（セッションが落ちた）"
                                         % ",".join(str(i) for i in info.get("ids", [])))
    return out


def has_expired_reserve():
    """期限切れの票が1枚でもあれば、15分の間引きを待たずに今すぐ掃く。"""
    if _reserve is None:
        return False
    try:
        return bool(_reserve.expired_urls())
    except Exception:
        return False


def gate_ok(force):
    if force:
        return True
    if has_expired_reserve():
        return True  # 孤児が確定しているのに15分待つ理由が無い
    try:
        last = os.path.getmtime(GATE_PATH)
    except OSError:
        return True
    import time
    return (time.time() - last) >= GATE_SECONDS


def touch_gate():
    os.makedirs(STATUS, exist_ok=True)
    with open(GATE_PATH, "w") as f:
        f.write(now_iso())


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recon", action="store_true", help="数えて記録するだけ。1枚も閉じない")
    ap.add_argument("--sweep", action="store_true", help="孤児タブを閉じる")
    ap.add_argument("--dry-run", action="store_true", help="判定するだけで閉じない")
    ap.add_argument("--force", action="store_true", help="1時間の間引きを無視する")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not (args.recon or args.sweep):
        args.recon = True

    # ★間引きは「閉じる工程」だけに効かせる。--recon（数えるだけ）は毎回走ってよい
    #   （osascriptでタブ一覧を読むのは1秒かからず、たまごさんの画面にも一切出ない）。
    if args.sweep and not gate_ok(args.force):
        args.sweep = False
        if not args.recon:
            if not args.quiet:
                print("SWEEP_RESULT: SKIP - まだ1時間経っていません")
            return 0

    tabs = list_tabs()
    if tabs is None:
        # ★ここでも必ず記録を残す。これが無いと「Chromeが起動していないので何もしていない」と
        #   「この道具がそもそも呼ばれていない」の区別がつかず、次の担当が実際に迷う
        #   （2026-09-18、この道具を作った本人が23分ぶん迷った）。
        if args.recon:
            write_json(RECON_PATH, {
                "updatedAt": now_iso(),
                "windows": 0, "tabs": 0, "wouldClose": 0,
                "note": "Chromeが起動していません（起動はしません）",
                "detail": [],
            })
        if args.sweep:
            # ★touch_gate() を**呼ばない**。Chromeが居ないのは「掃く仕事が無かった」であって
            #   「掃いた」ではない。ここで gate を進めると、Chromeが起きた直後の一番溜まって
            #   いる時間帯を素通りしてしまう（2026-09-19 実測でそうなっていた）。
            append_sweep_log({"ts": now_iso(), "closed": 0, "seen": 0,
                              "note": "Chromeが起動していない（gateは進めない）"})
        if not args.quiet:
            print("SWEEP_RESULT: SKIP - Chromeが起動していません（起動はしません）")
        return 0

    hist = update_history(tabs)
    reserved = pick_reserved(tabs, hist)
    judged = [(t, classify(t, hist, reserved)) for t in tabs]
    judged = mark_duplicates(judged)
    targets = [(t, why) for t, (verdict, why) in judged if verdict == "close"]

    if args.recon:
        # ★URLは status/ 配下（.gitignore済み）にのみ置く。公開されるstatus/public/には絶対に置かない。
        write_json(RECON_PATH, {
            "updatedAt": now_iso(),
            "windows": len(set(t["win"] for t in tabs)),
            "tabs": len(tabs),
            "wouldClose": len(targets),
            "detail": [
                {"win": t["win"], "idx": t["idx"], "active": t["active"],
                 "url": t["url"], "title": t["title"],
                 "verdict": v, "why": w}
                for t, (v, w) in judged
            ],
        })
        if not args.quiet:
            print("RECON_RESULT: OK - ウィンドウ%d / タブ%d枚 / 閉じる候補%d枚 → %s"
                  % (len(set(t["win"] for t in tabs)), len(tabs), len(targets), RECON_PATH))
        if not args.sweep:
            return 0

    closed = 0
    skipped = 0
    # ★後ろのタブから閉じる。前から閉じるとindexがずれて別のタブを閉じてしまう。
    for t, _why in sorted(targets, key=lambda x: (x[0]["win"], x[0]["idx"]), reverse=True):
        if args.dry_run:
            skipped += 1
            continue
        res = close_tab(t["win"], t["idx"], t["url"])
        if res == "CLOSED":
            closed += 1
        else:
            skipped += 1

    touch_gate()
    append_sweep_log({
        "ts": now_iso(),
        "seen": len(tabs),
        "candidates": len(targets),
        "closed": closed,
        "skipped": skipped,
        "dryRun": bool(args.dry_run),
    })
    if not args.quiet:
        print("SWEEP_RESULT: OK - %d枚閉じました（候補%d／見たタブ%d）"
              % (closed, len(targets), len(tabs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
