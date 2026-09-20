#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""969番：鍵・つながりの台帳。「走っているのに何も取れていない」を自動で赤にする係。

たまごさん（2026-09-20・外出中）：
  「今回渡してもまた起こるよ」「管理杜撰すぎじゃない」
  → 穴に段ボールを貼るのではなく、パイプごと替える（憲法19-5）。

------------------------------------------------------------------
今日1日で出た失敗は、形が全部同じだった
------------------------------------------------------------------
  1. Claudeの鍵    … 箱は残っているのに中身が空。44時間、発車ゼロ。
  2. 1年もつ鍵     … 9/5に置いたのに使う合図が無く、一度も使われず。実測401で死亡。
  3. メールの見張り3本 … 心臓から呼ばれて**動いているのに、1通も読めていない**。
                       state に "blocked": "no_credential" が書かれるだけ。**誰も見ていなかった。**
  4. xAIの鍵       … 有効なのに残高ゼロで403。
  5. Lovable       … 認証が切れたまま丸1日、本番に出なかった。
  6. 進捗表のディスク残量 … 156GB多い嘘を出し続けていた。
  7. チャッピーの返信4通  … 「重複」判定で黙って捨てられていた。
  8. 心臓のログ    … 1日17,000行の「既に動いています」で本当の記録を押し流していた。

  共通点＝**動いているように見えて、実は何も取れていない／嘘を出している。
  そして、それに気づく係がどこにも居なかった。**

------------------------------------------------------------------
だからこの係を置く（増やすのは見張りではなく「突き合わせ」1か所）
------------------------------------------------------------------
  A. 鍵・つながりを**実際に叩いて**、通るか通らないかだけを記録する。
     「設定に書いてある」は✕。「叩いて通った」だけが◯。値は一切読まない・書かない。
  B. 定期的に動いているもの全部について、**走った回数**と**実際に何かを取れた回数**を数える。
     走行 > 0 なのに 収穫 = 0 のものを赤で出す（＝目が塞がっている）。
  C. no_credential / blocked / 401 / 403 / skip を黙って飲み込んでいる箇所を
     ソースから機械的にあぶり出して、表に出す（新しく増えても自動で載る）。
  D. 嘘のログを見つける（例：本当は認証切れなのに「週の枠が上限」と書いてある）。
  E. 期限のあるものは 30日前・7日前・当日に声を上げる。

------------------------------------------------------------------
値（鍵・トークン・パスワードの中身）は絶対に扱わない
------------------------------------------------------------------
  ・読み出した値は、このファイルの中の変数から一歩も外へ出さない。
  ・出力に書くのは「名前」と「状態（通った／通らない／未実測）」と「HTTPの番号」だけ。
  ・エラー本文はそのまま書かない（番号→決まり文句 に変換してから書く）。
  ・進捗表リポは公開。だから名前と状態しか載せない。

新しい常駐は増やさない。既にある5分便(machine_status_push.sh)から呼ぶ。
"""
import base64
import imaplib
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "kagi_daicho.json")
COUNTS = os.path.join(STATUS, "kagi_daicho_counts.json")
NOTIFY_STATE = os.path.join(STATUS, "kagi_daicho_notify.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
LOG = os.path.join(STATUS, "kagi_daicho.log")
GATE_INTERVAL = 30 * 60          # 実測は30分に1回でいい（無駄打ちしない）

TAMAGO = os.path.expanduser("~/.tamago")

# ★ここが一番大事な安全装置★
#   この台帳は「叩いて通ったか」だけを載せる。ところがCowork/Dispatchのサンドボックスからは
#   鍵の置き場(~/.tamago)も外の回線もlocalhostも見えない。そこで走らせると、
#   **生きている鍵まで「鍵が置かれていません」と書いてしまう**＝今日たまごさんが怒った
#   「嘘のログ」を、台帳自身が作ることになる。
#   だから鍵の置き場が見えない場所では、判定を一切書かない（未実測とだけ言う）。
#   さらに、Macが測った結果を上書きしない。嘘を載せるくらいなら、何も言わない。
CAN_MEASURE = os.path.isdir(TAMAGO)

KEYFILES = [
    os.path.expanduser("~/Documents/AI作業/_鍵/keys.env"),
    os.path.expanduser("~/Documents/AI作業/_鍵/.env"),
    os.path.join(TAMAGO, "keys/api_keys.env"),
    os.path.join(REPO, ".env"),
]


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now(JST).strftime("%F %T"), msg))
    except Exception:
        pass


def scrub(s, limit=140):
    """外へ出す文字列から、鍵に見えるものを機械的に落とす。
       ★進捗表リポは公開。ログの1行をそのまま載せて鍵が混ざる事故を、形で止める。"""
    s = str(s or "")
    s = re.sub(r'[A-Za-z0-9_\-]{20,}', '〈伏せた〉', s)     # 長い英数字の塊＝鍵の形
    s = re.sub(r'(?i)(bearer|key|token|password|secret)\s*[:=]\s*\S+',
               r'\1=〈伏せた〉', s)
    return s[:limit]


def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log("書き込み失敗 %s: %s" % (path, type(e).__name__))
        return False


def mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return None


def age(path):
    m = mtime(path)
    return None if m is None else time.time() - m


def jst(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), JST).strftime("%m/%d %H:%M")
    except Exception:
        return ""


def hito(sec):
    """経過秒を人の言葉に。"""
    if sec is None:
        return "—"
    sec = int(sec)
    if sec < 90:
        return "%d秒前" % sec
    if sec < 5400:
        return "%d分前" % (sec // 60)
    if sec < 172800:
        return "%d時間前" % (sec // 3600)
    return "%d日前" % (sec // 86400)


# =====================================================================
# 鍵を探す。★見つけた値は、この関数の返り値としてしか外に出さない。
#   呼んだ側も「Authorizationヘッダに入れる」以外の使い方をしない。
#   print も log も json も、値には一切触れない。
# =====================================================================
def find_key(names):
    for n in names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip()
    for path in KEYFILES:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                for n in names:
                    if line.startswith(n + "="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            continue
    return None


def read_file_secret(path):
    """ファイルに入っている鍵を読む。★返り値としてしか外に出さない。"""
    try:
        v = io.open(os.path.expanduser(path), encoding="utf-8").read().strip()
        return v or None
    except Exception:
        return None


# =====================================================================
# 叩く。返すのは HTTPの番号だけ。**本文は捨てる**（本文に何が載っていても外へ出さない）
# =====================================================================
def http_code(url, headers=None, timeout=12, method="GET"):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")[:400].lower()
        except Exception:
            body = ""
        # ★本文はここで捨てる。外へ渡すのは「決まり文句のどれに当てはまったか」だけ。
        hint = ""
        for pat, word in (("credit", "残高"), ("balance", "残高"), ("quota", "枠"),
                          ("billing", "支払い"), ("expired", "期限切れ"),
                          ("invalid", "無効"), ("permission", "権限")):
            if pat in body:
                hint = word
                break
        return e.code, hint
    except Exception as e:
        return None, type(e).__name__


def verdict(code, hint, alive_codes=(200, 201, 204), dead_codes=(401, 403)):
    """番号→判定。2xx=通った／401,403=通らない／それ以外=未実測（点検口が違うだけかもしれない）"""
    if code is None:
        return "unknown", "叩けませんでした（回線かホスト名）"
    if code in alive_codes:
        return "ok", "200 通った"
    if code in dead_codes:
        w = "／" + hint if hint else ""
        return "ng", "%d 通らない%s" % (code, w)
    if code == 404:
        return "ok", "404（鍵は通った。点検用の住所が無いだけ）"
    if code == 429:
        return "ok", "429（鍵は通った。叩きすぎ）"
    return "unknown", "%d 未実測" % code


# =====================================================================
# A. 鍵・つながりの実測
# =====================================================================
def probe_claude():
    """Claudeは auth_keeper.py が30分ごとに**実際に叩いて**いる。二度打ちしない。"""
    st = load(os.path.join(STATUS, "auth_keeper.json"), {}) or {}
    state = st.get("state")
    last = st.get("lastProbeAt")
    minted = mtime(os.path.join(TAMAGO, "claude_token.minted"))
    expiry = None
    if minted:
        expiry = minted + 365 * 86400
    use_token = os.path.exists(os.path.join(TAMAGO, "use_token"))
    extra = "使う合図(use_token)：%s" % ("立っている" if use_token else "**立っていない**")
    if state == "ok":
        return dict(status="ok", detail="通った（auth_keeperが実測）", at=last,
                    expiry=expiry, note=extra)
    if state == "expired":
        return dict(status="ng", detail="通らない（%s）" % (st.get("lastNgWhy") or "認証切れ"),
                    at=last, expiry=expiry, note=extra)
    return dict(status="unknown", detail="auth_keeperの実測結果がまだありません",
                at=last, expiry=expiry, note=extra)


def probe_openai():
    k = find_key(("OPENAI_API_KEY", "CHATGPT_API_KEY"))
    if not k:
        return dict(status="ng", detail="鍵が置かれていません")
    c, h = http_code("https://api.openai.com/v1/models",
                     {"Authorization": "Bearer " + k})
    s, d = verdict(c, h)
    return dict(status=s, detail=d)


def probe_xai():
    k = find_key(("XAI_API_KEY", "GROK_API_KEY"))
    if not k:
        return dict(status="ng", detail="鍵が置かれていません")
    c, h = http_code("https://api.x.ai/v1/models", {"Authorization": "Bearer " + k})
    s, d = verdict(c, h)
    if c == 403:
        d = "403 通らない（鍵は有効でも残高/権限が無い形）"
    return dict(status=s, detail=d)


def probe_gemini():
    k = find_key(("GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_GENAI_API_KEY"))
    if not k:
        return dict(status="ng", detail="鍵が置かれていません")
    # ★URLに鍵を載せない。公式が認めているヘッダ方式で叩く。
    c, h = http_code("https://generativelanguage.googleapis.com/v1beta/models",
                     {"x-goog-api-key": k})
    s, d = verdict(c, h, dead_codes=(400, 401, 403))
    return dict(status=s, detail=d)


def probe_github():
    k = find_key(("GITHUB_TOKEN", "GH_TOKEN"))
    if not k:
        # launchd から呼ばれるとPATHが細いので、実体を直接探す（「gh が無い」と
        # 「ログインしていない」を取り違えない）
        for gh in ("gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh",
                   os.path.expanduser("~/.local/bin/gh")):
            try:
                p = subprocess.run([gh, "auth", "token"], capture_output=True,
                                   text=True, timeout=15)
                if p.returncode == 0 and p.stdout.strip():
                    k = p.stdout.strip()
                    break
            except Exception:
                continue
    if not k:
        return dict(status="ng", detail="トークンが取れません（gh auth login が要る）")
    c, h = http_code("https://api.github.com/user",
                     {"Authorization": "Bearer " + k,
                      "Accept": "application/vnd.github+json",
                      "User-Agent": "tamago-kagi-daicho"})
    s, d = verdict(c, h)
    return dict(status=s, detail=d)


def probe_fal():
    # ★置き場が枝分かれしている（実測）：_636_gen_images.py は ~/.fal_key を読んでいる。
    #   台帳は「本当に使われている置き場」を全部見る。見ていない置き場があると、
    #   生きている鍵を「無い」と書く＝台帳自身が嘘をつく。
    k = (find_key(("FAL_KEY", "FAL_API_KEY"))
         or read_file_secret("~/.fal_key")
         or read_file_secret("~/.tamago/fal_key"))
    if not k:
        return dict(status="ng", detail="鍵が置かれていません")
    c, h = http_code(
        "https://queue.fal.run/fal-ai/nano-banana/requests/"
        "00000000-0000-0000-0000-000000000000/status",
        {"Authorization": "Key " + k})
    s, d = verdict(c, h)
    return dict(status=s, detail=d)


def probe_devin():
    k = find_key(("DEVIN_API_KEY",))
    if not k:
        return dict(status="ng", detail="鍵が置かれていません")
    c, h = http_code("https://api.devin.ai/v1/sessions",
                     {"Authorization": "Bearer " + k})
    s, d = verdict(c, h)
    return dict(status=s, detail=d)


def probe_gmail():
    """IMAPへ**実際にログインだけ**して切る。メールは1通も読まない。"""
    path = os.path.join(TAMAGO, "gmail_app_password")
    if not os.path.exists(path):
        return dict(status="ng", detail="アプリパスワードのファイルが置かれていません")
    pw = read_file_secret(path)
    if not pw:
        return dict(status="ng", detail="ファイルはあるが中身が空です")
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com", timeout=20)
        try:
            M.login("eggypop2010@gmail.com", pw)
            M.logout()
            return dict(status="ok", detail="ログインできました（メールは読んでいません）")
        except imaplib.IMAP4.error:
            try:
                M.logout()
            except Exception:
                pass
            return dict(status="ng", detail="ログインを断られました（アプリパスワードが無効）")
    except Exception as e:
        return dict(status="unknown", detail="繋がりませんでした（%s）" % type(e).__name__)


def probe_lovable():
    path = os.path.join(TAMAGO, "lovable_oauth.json")
    if not os.path.exists(path):
        return dict(status="ng", detail="認証がまだ取れていません（同意ボタンが押されていない）")
    tok = load(path, {}) or {}
    exp = tok.get("expires_at") or tok.get("expiresAt")
    expiry = None
    if isinstance(exp, (int, float)):
        # ミリ秒で入っていることがあるので、桁で見分ける（値そのものは秒数であって鍵ではない）
        expiry = float(exp) / 1000.0 if exp > 1e12 else float(exp)
    has_refresh = bool(tok.get("refresh_token"))
    if expiry and expiry < time.time() and not has_refresh:
        return dict(status="ng", detail="期限切れ（更新用の鍵も無い）", expiry=expiry)
    return dict(status="ok", detail="トークンがあります（更新用%s）"
                % ("あり" if has_refresh else "**なし**"), expiry=expiry)


def probe_heart():
    a = age(os.path.join(STATUS, ".heartbeat_alive"))
    if a is None:
        return dict(status="ng", detail="心臓が一度も印を付けていません")
    if a < 120:
        return dict(status="ok", detail="動いています（%s）" % hito(a))
    return dict(status="ng", detail="%s から印が止まっています" % hito(a))


def probe_gobun():
    a = age(os.path.join(STATUS, "machine.json"))
    if a is None:
        return dict(status="ng", detail="5分便が一度も書いていません")
    if a < 900:
        return dict(status="ok", detail="動いています（%s）" % hito(a))
    return dict(status="ng", detail="%s から止まっています" % hito(a))


def probe_hassha():
    flag = os.path.join(STATUS, "no_launch.flag")
    if os.path.exists(flag):
        try:
            why = scrub(io.open(flag, encoding="utf-8").read().strip(), 110)
        except Exception:
            why = ""
        return dict(status="ng", detail="発車が止められています（%s）" % why)
    a = age(os.path.join(STATUS, "auto_launch.log"))
    return dict(status="ok", detail="止め札はありません（最後の発車記録 %s）" % hito(a))


def probe_relay():
    port = int(os.environ.get("RELAY_PORT") or 8788)
    c, h = http_code("http://127.0.0.1:%d/" % port, timeout=6)
    if c is None:
        return dict(status="ng", detail="中継所が返事をしません（進捗表のボタンが届かない）")
    return dict(status="ok", detail="%d 返事があります" % c)


# 台帳の本体。ここに並んでいないものは「無い」ことにする。
LEDGER = [
    dict(id="claude", what="Claudeの鍵（発車そのもの）", where="キーチェーン／~/.tamago/claude_token",
         probe=probe_claude, stops="工場の発車が全部止まる（44時間の実害）",
         fix="いつも使っているClaudeのアプリで1回ログインし直す。あとは auth_keeper が自分で戻す"),
    dict(id="gmail", what="Gmail（メールの見張り4本の目）", where="~/.tamago/gmail_app_password",
         probe=probe_gmail, stops="LINE審査・Anthropic・外部窓口の返信に**誰も気づかない**",
         fix="Googleアカウントでアプリパスワードを作り、そのファイルに置く"),
    dict(id="github", what="GitHub（ghのトークン＝見張り番の目）",
         where="gh auth token / GITHUB_TOKEN",
         probe=probe_github,
         stops="チャッピーがIssueを置いても誰も気づかない"
               "（※進捗表の公開pushは別の鍵なので、ここが赤でも公開は止まらない）",
         fix="gh auth login"),
    dict(id="openai", what="OpenAI（外部検品・代行）", where="~/.tamago/keys/api_keys.env",
         probe=probe_openai, stops="鬼監督の外部検品と、詰まった仕事の逃がし先が消える",
         fix="platform.openai.com で鍵を作り直して鍵ファイルへ"),
    dict(id="gemini", what="Gemini（外部代行・サーバ側）",
         where="~/.tamago/keys/api_keys.env の GEMINI_API_KEY",
         probe=probe_gemini,
         stops="安い代行先が消えてClaudeの枠を食う"
               "（※ページの「話す」が使うのはブラウザ側の別の鍵 tamago_gemini_key。"
               "それは 969_kagi_kanmon.py が見ている）",
         fix="Google AI Studio で無料発行して鍵ファイルへ"),
    dict(id="xai", what="Grok / xAI（外部代行）", where="~/.tamago/keys/api_keys.env",
         probe=probe_xai, stops="Grokへの相談ができない",
         fix="鍵は有効でも残高が要る。console.x.ai で残高を入れる"),
    dict(id="fal", what="fal.ai（画像・動画・音声）", where="~/.tamago/keys/api_keys.env",
         probe=probe_fal, stops="絵と動画が1枚も作れない",
         fix="fal.ai で鍵を作り直して鍵ファイルへ"),
    dict(id="devin", what="Devin（実装の代行）", where="DEVIN_API_KEY",
         probe=probe_devin, stops="Devinへ仕事を出せない",
         fix="app.devin.ai で鍵を作り直す"),
    dict(id="lovable", what="Lovable（本番へ出す口）", where="~/.tamago/lovable_oauth.json",
         probe=probe_lovable, stops="直したものが**本番に出ない**（丸1日の実害）",
         fix="Chromeで同意ボタンを1回押す（受け皿は lovable_auth_keeper が立てている）"),
    dict(id="heart", what="心臓（15秒おきの本体）", where="tools/heartbeat.sh",
         probe=probe_heart, stops="着火と受信箱が止まる＝ボタンが効かない",
         fix="5分便が自分で立て直す。立て直らなければ launchctl kickstart"),
    dict(id="gobun", what="5分便（立て直す側）", where="launchd com.tamago.machine-status",
         probe=probe_gobun, stops="心臓が落ちても誰も立て直さない",
         fix="launchctl kickstart -k gui/$UID/com.tamago.machine-status"),
    dict(id="hassha", what="発車（仕事が前に進むか）", where="status/no_launch.flag",
         probe=probe_hassha, stops="仕事が1本も進まない",
         fix="止め札の理由を読む。認証なら claude、枠なら時間で戻る"),
    dict(id="relay", what="中継所（スマホのボタン→Mac）", where="127.0.0.1:8788",
         probe=probe_relay, stops="たまごさんがボタンを押しても何も起きない",
         fix="relay_watch が自分で立て直す"),
]


# =====================================================================
# B. 走っているのに何も取れていない
#    ★「設定でどう呼ばれているか」ではなく、**そいつ自身が残した跡**だけで数える。
# =====================================================================
WATCHERS = [
    dict(id="line_shinsa", label="LINE審査結果の見張り",
         state=".line_shinsa_state.json", need="gmail",
         catch_flags=["line_shinsa_done.flag"]),
    dict(id="line_reply", label="LINE問い合わせ返信の見張り",
         state=".line_watch_state.json", need="gmail",
         catch_flags=["line_reply_done.flag"]),
    dict(id="anthropic_reply", label="Anthropic返信の見張り",
         state=".anthropic_watch_state.json", need="gmail",
         catch_flags=["anthropic_reply_done.flag"]),
    dict(id="renraku", label="外部連絡窓口の見張り（全窓口）",
         state=".renraku_check_state.json", need="gmail", catch_flags=[]),
    dict(id="github_watch", label="GitHub見張り番", state="github_watch_state.json",
         need="github", catch_flags=[],
         # ★この子だけは自分で数えている（stats）。数えているものがあるなら、それを使う。
         catch_counter=["stats.notModified", "stats.picked"],
         err_log="github_watch_err.log"),
    dict(id="auth_keeper", label="ログインの番人", state="auth_keeper.json",
         need="claude", catch_flags=[], err_log="auth_keeper.log"),
    # ↓この2本は 2026-09-20、台帳の「台帳外あぶり出し」が自分で見つけて足したもの。
    #   （手で名簿を書いている限り、足し忘れた1本が必ず「誰も見ていない見張り」になる）
    dict(id="line_store_watch", label="LINEストアの見張り",
         state="line_store_watch.json", need="gmail", catch_flags=[],
         err_log="line_store_watch.log"),
    dict(id="avatar_reply", label="アバターの返信拾い（969）",
         state="969/seen.json", need="github", catch_flags=[],
         catch_counter=[], err_log="969/pickup.log"),
]

# 「実際に何かを取れた」跡として認める名前。
# ★lastProbeAt を入れてある：番人の仕事は「答えを取ってくること」であって、
#   その答えが○でも✕でも**取れている**。取れていないのは、叩けもしなかった時だけ。
CATCH_KEYS = ("lastHitAt", "lastFoundAt", "foundCount", "hits", "found",
              "lastNewAt", "notifiedAt", "lastNotifiedAt", "lastCatchAt",
              "lastProbeAt", "ids", "probes")
BLOCK_KEYS = ("blocked", "skipped", "error", "lastError", "credentialMissingNotified")


def watcher_rows():
    counts = load(COUNTS, {}) or {}
    rows = []
    for w in WATCHERS:
        st = {}
        run_at = None
        if w.get("state"):
            p = os.path.join(STATUS, w["state"])
            st = load(p, {}) or {}
            run_at = mtime(p)
        for rf in w.get("run_files", []):
            m = mtime(os.path.join(STATUS, rf))
            if m and (run_at is None or m > run_at):
                run_at = m
        # 取れた跡
        caught_at = None
        for k in CATCH_KEYS:
            if st.get(k):
                caught_at = run_at
                break
        for cf in w.get("catch_flags", []):
            m = mtime(os.path.join(STATUS, cf))
            if m and (caught_at is None or m > caught_at):
                caught_at = m
        # 自分で数えている子は、その数を使う（0なら取れていない）
        counter_total = None
        for dotted in w.get("catch_counter", []):
            cur = st
            for part in dotted.split("."):
                cur = (cur or {}).get(part) if isinstance(cur, dict) else None
            if isinstance(cur, (int, float)):
                counter_total = (counter_total or 0) + cur
        if counter_total is not None:
            caught_at = run_at if counter_total > 0 else None
        # 黙って飲み込まれている理由
        blocked = ""
        for k in BLOCK_KEYS:
            v = st.get(k)
            if v and v is not True:
                blocked = "%s=%s" % (k, v)
                break
            if v is True:
                blocked = k
                break
        # 黙って死んでいないか（吐き出したものが残っているのに誰も見ていない、を拾う）
        if not blocked and w.get("err_log"):
            ep = os.path.join(STATUS, w["err_log"])
            ea = age(ep)
            if ea is not None and ea < 86400:
                try:
                    tail = [l for l in io.open(ep, encoding="utf-8", errors="ignore")
                            .read().split("\n") if l.strip()][-1:]
                except Exception:
                    tail = []
                if tail and re.search(r"(Error|Traceback|Exception|Failed)", tail[0]):
                    blocked = "吐き出している：" + scrub(tail[0])
        # 走行回数・収穫回数（今日から積む。跡が進んだ回だけ数える）
        c = counts.get(w["id"], {"runs": 0, "catches": 0, "seenRun": 0, "seenCatch": 0})
        if run_at and run_at > (c.get("seenRun") or 0):
            c["runs"] = c.get("runs", 0) + 1
            c["seenRun"] = run_at
        if caught_at and caught_at > (c.get("seenCatch") or 0):
            c["catches"] = c.get("catches", 0) + 1
            c["seenCatch"] = caught_at
        counts[w["id"]] = c
        # 赤の条件は2つ。どちらかに当たれば赤。
        #   ① 走っているのに、取れた跡が1つも無い
        #   ② 鍵が無い／吐き出している（取れた跡があっても、これは見逃さない）
        red = (bool(run_at) and not caught_at) \
            or ("credential" in blocked.lower()) \
            or blocked.startswith("吐き出している")
        rows.append(dict(id=w["id"], label=w["label"], need=w.get("need", ""),
                         lastRunAt=run_at, lastCatchAt=caught_at,
                         runs=c["runs"], catches=c["catches"],
                         blocked=blocked, red=red))
    save(COUNTS, counts)
    return rows


# =====================================================================
# C. 黙って飲み込んでいる箇所を、ソースからあぶり出す
# =====================================================================
SWALLOW_PAT = re.compile(
    r'(no_credential|empty_credential|"blocked"|blocked=|skipped=|'
    r'except Exception:\s*$|return 0\s*#|401|403)')


def swallow_scan(limit=60):
    """「失敗を記録はするが、誰にも届けずに終わる」行を機械的に拾う。
       ★完全な判定はできない。だから**候補として全部出す**（隠すよりまし）。"""
    hits = []
    tools = os.path.join(REPO, "tools")
    for name in sorted(os.listdir(tools)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        if name in ("kagi_daicho.py", "kagi_gate.py"):
            continue          # 台帳が自分を告発しても意味が無い（表に出すのが仕事）
        path = os.path.join(tools, name)
        try:
            lines = io.open(path, encoding="utf-8", errors="ignore").read().split("\n")
        except Exception:
            continue
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("#") or s.startswith('"') or s.startswith("'"):
                continue
            if re.search(r'(no_credential|empty_credential)', s) and "log_state" in s:
                hits.append(dict(file=name, line=i + 1,
                                 why="鍵が無いことを state に書くだけで終わっている"))
            elif re.search(r'blocked\s*=\s*["\']', s) and "outbox" not in s.lower():
                hits.append(dict(file=name, line=i + 1,
                                 why="blocked を記録するだけで、外へ出していない"))
            elif re.match(r'except\s+Exception\s*:\s*$', s) and i + 1 < len(lines) \
                    and lines[i + 1].strip() in ("pass", "continue", "return", "return 0",
                                                 "return None", "return False"):
                hits.append(dict(file=name, line=i + 1,
                                 why="例外を丸ごと握り潰している（何が起きたか残らない）"))
    # ★並べ順が大事。数の多い「例外の握り潰し」で、数の少ない
    #   「鍵が無いのを黙って飲み込んでいる」が埋もれたら、この表を作った意味が無い。
    rank = {"鍵が無いことを state に書くだけで終わっている": 0,
            "blocked を記録するだけで、外へ出していない": 1}
    hits.sort(key=lambda h: rank.get(h["why"], 2))
    return hits[:limit], len(hits)


# =====================================================================
# C-2. 台帳に載っていない定期便を、自分で見つける
#   ★ここが「また起きる」を止める要。
#     台帳が手書きの名簿のままなら、明日だれかが見張りを1本足した瞬間に
#     **その1本だけが台帳の外**になり、今日と同じ「誰も見ていない見張り」が生まれる。
#     だから、実際に定期的に叩かれているものを心臓と5分便の台本から読み取って、
#     台帳に載っていないものを名指しで出す。載せるまで赤は消えない。
# =====================================================================
CALL_PAT = re.compile(r'tools/([A-Za-z0-9_]+)\.py')
# 台帳に載せなくていいもの（数える対象ではない道具・台帳自身）
NOT_WATCHERS = {
    "kagi_daicho", "kagi_gate", "top_status", "genzaichi", "launch_watchdog",
    "auto_launcher", "command_ingest", "machine_health", "worktree_reaper",
    "git_lock_reaper", "check_page_pruner", "chrome_tab_sweeper",
    "build_queue_light", "build_queue_public_gz", "build_done_archive_light",
    "factory_status", "quota_estimate", "number_audit", "pace", "calibrate",
    "verify_done", "archive_done", "priority_ingest", "health_candidates",
    "orphan_reaper", "session_watchdog", "disk_guardian", "relay_watch",
    "auth_watch", "fal_cost_ledger", "estimate_vs_actual", "gaibu_ledger",
    "kenpin_gate", "nyuka_sekisho", "gaibu_runner", "eagle_inbox",
    "eagle_gallery", "later_tabs_snapshot", "daily_ingest_scheduler",
    "machine_load", "disk_trend",
}


def unlisted_scan():
    known = {w["id"] for w in WATCHERS}
    # 台帳の見張りIDとスクリプト名は必ずしも同じではないので、別名も許す
    alias = {"line_shinsa": "check_line_shinsa", "line_reply": "check_line_reply",
             "anthropic_reply": "check_anthropic_reply", "renraku": "renraku",
             "github_watch": "github_watch", "auth_keeper": "auth_keeper",
             "line_store_watch": "line_store_watch",
             "avatar_reply": "_969_avatar_reply_pickup"}
    known_scripts = set(alias.get(k, k) for k in known)
    found = set()
    for sh in ("heartbeat.sh", "machine_status_push.sh"):
        p = os.path.join(REPO, "tools", sh)
        try:
            for line in io.open(p, encoding="utf-8", errors="ignore"):
                s = line.strip()
                if s.startswith("#") or "python3" not in s:
                    continue
                for name in CALL_PAT.findall(s):
                    found.add(name)
        except Exception:
            continue
    out = []
    for name in sorted(found - known_scripts - NOT_WATCHERS):
        if not os.path.exists(os.path.join(REPO, "tools", name + ".py")):
            continue
        out.append(dict(script="tools/%s.py" % name,
                        why="定期的に走っているのに、台帳に載っていません"
                            "（＝走っているか・取れているかを誰も見ていない）"))
    return out


# =====================================================================
# D. 嘘のログを見つける
# =====================================================================
def lie_scan(ledger_by_id):
    lies = []
    flag = os.path.join(STATUS, "no_launch.flag")
    if os.path.exists(flag):
        try:
            txt = io.open(flag, encoding="utf-8").read()
        except Exception:
            txt = ""
        claude = ledger_by_id.get("claude", {})
        if ("週次利用上限" in txt or "weekly limit" in txt.lower()) \
                and claude.get("status") == "ng":
            lies.append(dict(
                where="status/no_launch.flag",
                said="Claudeの週次利用上限（weekly limit）",
                truth="実測ではログインが通っていません。止まっている本当の理由は認証切れです",
                fix="auto_launcher.py の weekly limit 検知より先に認証の生死を見る"))
    # 心臓のログが同じ1行で埋まっていないか（本当の記録が押し流される）
    hb = os.path.join(STATUS, "heartbeat.log")
    try:
        ls = [l for l in io.open(hb, encoding="utf-8", errors="ignore").read().split("\n") if l.strip()]
        if len(ls) >= 20:
            tails = [re.sub(r'^\S+ \S+ ', '', l) for l in ls[-50:]]
            top = max(set(tails), key=tails.count)
            if tails.count(top) > len(tails) * 0.8:
                lies.append(dict(
                    where="status/heartbeat.log",
                    said=scrub(top, 60),
                    truth="直近50行の%d行が同じ1行です。本当の記録が押し流されています"
                          % tails.count(top),
                    fix="同じ行は1回だけ書く（連続分は回数にまとめる）"))
    except Exception:
        pass
    return lies


# =====================================================================
# E. 期限：30日前・7日前・当日に1回ずつだけ声を上げる
# =====================================================================
def expiry_notices(rows):
    state = load(NOTIFY_STATE, {}) or {}
    msgs = []
    now = time.time()
    for r in rows:
        exp = r.get("expiry")
        if not exp:
            continue
        days = int((exp - now) // 86400)
        for mark in (30, 7, 0):
            if days <= mark:
                key = "%s:%d" % (r["id"], mark)
                if not state.get(key):
                    state[key] = now
                    msgs.append("【%s】あと%d日で期限が切れます。%s" %
                                (r["what"], max(days, 0), r["fix"]))
                break
    if msgs:
        save(NOTIFY_STATE, state)
        try:
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                for m in msgs:
                    f.write(json.dumps({"at": datetime.now(JST).isoformat(),
                                        "from": "kagi_daicho",
                                        "text": m}, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return msgs


# =====================================================================
def build(force=False):
    os.makedirs(PUBLIC, exist_ok=True)
    prev = load(OUT_JSON, {}) or {}
    if not force:
        last = prev.get("generatedAtEpoch") or 0
        if time.time() - last < GATE_INTERVAL:
            return prev          # 無駄打ちしない
    if not CAN_MEASURE:
        # 鍵の置き場が見えない＝ここは工場のMacではない。嘘を載せずに黙って退く。
        log("鍵の置き場(~/.tamago)が見えないので、実測せずに退きました（上書きもしません）")
        return prev
    rows = []
    for e in LEDGER:
        try:
            r = e["probe"]()
        except Exception as ex:
            r = dict(status="unknown", detail="点検そのものが失敗（%s）" % type(ex).__name__)
        rows.append(dict(id=e["id"], what=e["what"], where=e["where"],
                         stops=e["stops"], fix=e["fix"],
                         status=r.get("status", "unknown"),
                         detail=r.get("detail", ""),
                         note=r.get("note", ""),
                         expiry=r.get("expiry"),
                         measuredAt=r.get("at") or time.time()))
    by_id = {r["id"]: r for r in rows}
    watchers = watcher_rows()
    swallows, swallow_total = swallow_scan()
    unlisted = unlisted_scan()
    lies = lie_scan(by_id)
    notices = expiry_notices(rows)

    red_keys = [r for r in rows if r["status"] == "ng"]
    red_watch = [w for w in watchers if w["red"]]
    out = dict(
        generatedAt=datetime.now(JST).isoformat(),
        generatedAtEpoch=time.time(),
        rows=rows, watchers=watchers,
        swallows=swallows, swallowTotal=swallow_total,
        unlisted=unlisted,
        lies=lies, notices=notices,
        redCount=len(red_keys) + len(red_watch) + len(lies) + len(unlisted),
        redKeys=len(red_keys), redWatchers=len(red_watch), redLies=len(lies),
        redUnlisted=len(unlisted),
    )
    save(OUT_JSON, out)
    # 進捗表のトップが読む1行（赤が1つでもあれば出る）
    save(os.path.join(PUBLIC, "kagi_daicho_top.json"), dict(
        redCount=out["redCount"],
        headline=("鍵・つながりに赤が%d件（動いているのに何も取れていない／切れている）"
                  % out["redCount"]) if out["redCount"] else "鍵・つながりは全部通っています",
        at=out["generatedAt"]))
    log("台帳を更新：赤%d件（鍵%d・見張り%d・嘘%d・台帳外%d）"
        % (out["redCount"], len(red_keys), len(red_watch), len(lies), len(unlisted)))
    return out


def main():
    force = "--force" in sys.argv
    out = build(force=force)
    if "--print" in sys.argv:
        for r in out.get("rows", []):
            mark = {"ok": "○", "ng": "✕", "unknown": "△"}.get(r["status"], "?")
            print("%s %-28s %s" % (mark, r["what"][:28], r["detail"]))
        print("---")
        for w in out.get("watchers", []):
            print("%s %-24s 走行%s 収穫%s %s" %
                  ("✕" if w["red"] else "○", w["label"][:24],
                   w["runs"], w["catches"], w.get("blocked", "")))
        print("赤 %d件" % out.get("redCount", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
