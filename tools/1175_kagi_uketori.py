#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1175番【鍵の受け取り口】— 貼るのは1回。以後ブラウザのログインを二度と頼まない。

たまごさん（2026-09-28）：
  「1回ログインしたら、人間はもう二度とやらなくていい、を実現している世界の事例を
    集めて、うちに移植する。目標は本人操作 月0回。」

なぜこれを最初に作ったか（調べた結果の要約）：
  ・GitHub（fine-grained PATは無期限を選べる）・Supabase（service_role / sb_secret_ は
    ダッシュボードで消すまで無期限）・Buffer・Lovable・Gmail（アプリパスワード）は
    **公式が長期の鍵を出している**。つまりブラウザでログインし続ける必要がそもそも無い。
  ・ところが、うちで毎回「ログインして」に戻っていた本当の原因は鍵の技術ではなく
    **渡された鍵をしまう口が鍵ごとにバラバラで、口が無い鍵は毎回ブラウザに落ちていた**こと。
    実際に在るのは buffer_kagi_install.py（Bufferだけ）と 1163_kagi_machi.py（Supabaseだけ）。
  ・Chrome側でどれだけ粘っても、Chrome 127以降の App-Bound Encryption で
    プロファイルからcookieを取り出す道は塞がっている（＝cookieを延命する策は伸びしろが無い）。
  → だから「鍵を1か所に貼れば、機械が正しい場所へしまう」口を1本だけ作る。

やること（心臓から1分おきに呼ばれる。たまごさんはターミナルを開かない）：
  1. ~/Desktop/kagi.txt（無ければ作って、書き方を中に書いておく）と
     ~/Desktop/*_token.txt / ~/.tamago/_drop/*.txt を見る
  2. `NAME=値` でも、**値だけ貼ってあっても**、形（ghp_ / sk- / xai- / AIza / eyJ / 16文字）で
     どの鍵かを自分で当てる
  3. 叩いて確かめられる鍵は1回だけ叩いて、本物だと分かったものだけしまう
  4. 正しい置き場（~/.tamago/keys/api_keys.env か 専用ファイル）へ chmod 600 でしまう
  5. しまえた行だけ平文を消す（しまえなかった行は残して、何が駄目だったかを書き足す）
  6. 値は1バイトもログ・JSON・リポジトリに書かない（先頭4文字＋末尾2文字だけ）

置き場所:
  受け取り口  ~/Desktop/kagi.txt
  しまう先    ~/.tamago/keys/api_keys.env ／ ~/.tamago/gmail_app_password 等
  紙          status/1175_kagi_uketori.json（伏せ字あり・非公開）
              status/public/1175_kagi_uketori.json（伏せ字も無い・公開）
  ログ        status/kagi_daicho.log（既存の1本に相乗り。新しいログを増やさない）

使い方:
  python3 tools/1175_kagi_uketori.py              … 心臓から呼ばれる形
  python3 tools/1175_kagi_uketori.py --self-test  … 外へ1回も出ずに当て方だけ試す
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
TAMAGO = os.path.expanduser("~/.tamago")
KEYS = os.path.join(TAMAGO, "keys", "api_keys.env")
LOG = os.path.join(STATUS, "kagi_daicho.log")
OUT = os.path.join(STATUS, "1175_kagi_uketori.json")
OUT_PUB = os.path.join(PUBLIC, "1175_kagi_uketori.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
STAMP = os.path.join(STATUS, ".1175_shirase_at")

TRAY = os.path.expanduser("~/Desktop/kagi.txt")
TRAY_HEAD = """# ここに鍵を貼るだけ。1回貼れば、もう二度とログインを頼みません。
# 貼り方はどちらでもいい：
#   GMAIL_APP_PASSWORD=abcdefghijklmnop
#   ghp_xxxxxxxxxxxxxxxx          ← 値だけでも、機械が何の鍵か当てます
# 保存したら1分以内に機械がしまいます（このファイルの中身は自動で消えます）。
# 分からなかった行だけ、理由を付けてここに残します。
"""

# ---------------------------------------------------------------------------
# 鍵の名簿。★ここに1行足すだけで新しい鍵の受け取り口が増える。
#   dest  : ("env", 環境変数名) か ("file", 絶対パス)
#   sniff : 値だけ貼られたときに当てるための正規表現（Noneなら名前が要る）
#   verify: 叩いて確かめる関数名（Noneなら未検証のまましまう）
#   fix   : 鍵が無いときにたまごさんへ出す1行（どこで作るか）
# ---------------------------------------------------------------------------
def _http(url, headers=None, data=None, timeout=15):
    req = urllib.request.Request(url, data=data,
                                 headers=headers or {"User-Agent": "tamago-1175"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read()[:400].decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read()[:300].decode("utf-8", "ignore")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return None, repr(e)[:200]


def v_github(tok):
    c, b = _http("https://api.github.com/user",
                 {"Authorization": "Bearer %s" % tok, "User-Agent": "tamago-1175"})
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:120])


def v_openai(tok):
    c, b = _http("https://api.openai.com/v1/models",
                 {"Authorization": "Bearer %s" % tok})
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:120])


def v_xai(tok):
    c, b = _http("https://api.x.ai/v1/models", {"Authorization": "Bearer %s" % tok})
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:120])


def v_gemini(tok):
    c, b = _http("https://generativelanguage.googleapis.com/v1beta/models?key=%s" % tok)
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:120])


def v_buffer(tok):
    c, b = _http("https://api.buffer.com",
                 {"Authorization": "Bearer %s" % tok,
                  "Content-Type": "application/json", "User-Agent": "tamago-1175"},
                 data=json.dumps({"query": "{ account { id } }"}).encode())
    # 429（叩きすぎ）は「鍵は通った」の意味。ここで嘘の×を付けない。
    if c == 429:
        return True, "HTTP 429（鍵は通った。叩きすぎ）"
    if c == 200 and '"errors"' in b:
        return False, "200 だが errors: %s" % b[:120]
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:120])


def v_meta(tok):
    c, b = _http("https://graph.facebook.com/v21.0/me?access_token=%s" % tok)
    return (c == 200), "HTTP %s %s" % (c, "" if c == 200 else b[:160])


def v_gmail(pw):
    """アプリパスワードは実際にIMAPへ1回ログインして確かめる（副作用なし）。"""
    addr = ""
    for p in (os.path.join(TAMAGO, "gmail_address"),):
        try:
            addr = io.open(p, encoding="utf-8").read().strip()
        except Exception:
            pass
    addr = addr or "eggypop2010@gmail.com"
    try:
        import imaplib
        m = imaplib.IMAP4_SSL("imap.gmail.com", timeout=20)
        try:
            m.login(addr, pw.replace(" ", ""))
            m.logout()
            return True, "IMAPに通った（%s）" % addr
        except Exception as e:
            try:
                m.logout()
            except Exception:
                pass
            return False, "IMAPが断りました：%s" % repr(e)[:160]
    except Exception as e:
        return False, "IMAPに繋げませんでした：%s" % repr(e)[:160]


SPECS = [
    dict(id="gmail", label="Gmail（見張り4本の目）",
         names=["GMAIL_APP_PASSWORD", "GMAIL_APP_PW", "GMAIL_PASSWORD"],
         dest=("file", os.path.join(TAMAGO, "gmail_app_password")),
         sniff=re.compile(r"^(?:[a-z]{4}\s?){4}$"), verify=v_gmail,
         fix="myaccount.google.com/apppasswords で16文字を1回作って kagi.txt に貼る"),
    dict(id="github", label="GitHub（見張り番の目）",
         names=["GITHUB_TOKEN", "GH_TOKEN"], dest=("env", "GITHUB_TOKEN"),
         sniff=re.compile(r"^(?:ghp_|github_pat_|gho_)[A-Za-z0-9_]{20,}$"), verify=v_github,
         fix="github.com/settings/personal-access-tokens で有効期限「無期限」で作る",
         # ★gh が既に持っているなら「無い」と言わない（鍵台帳は gh auth token を見ている）
         extra=lambda: _gh_token_exists()),
    dict(id="openai", label="OpenAI（外部検品・代行）",
         names=["OPENAI_API_KEY"], dest=("env", "OPENAI_API_KEY"),
         sniff=re.compile(r"^sk-[A-Za-z0-9_\-]{20,}$"), verify=v_openai,
         fix="platform.openai.com/api-keys"),
    dict(id="xai", label="Grok / xAI（文字での外部代行）",
         names=["XAI_API_KEY", "GROK_API_KEY"], dest=("env", "XAI_API_KEY"),
         sniff=re.compile(r"^xai-[A-Za-z0-9]{20,}$"), verify=v_xai,
         fix="console.x.ai（★残高が要る）"),
    dict(id="gemini", label="Gemini（安い外部代行）",
         names=["GEMINI_API_KEY", "GOOGLE_API_KEY"], dest=("env", "GEMINI_API_KEY"),
         sniff=re.compile(r"^AIza[A-Za-z0-9_\-]{30,}$"), verify=v_gemini,
         fix="aistudio.google.com/apikey（無料）"),
    dict(id="buffer", label="Buffer（Xへの予約投稿の口）",
         names=["BUFFER_ACCESS_TOKEN", "BUFFER_TOKEN"],
         dest=("env", "BUFFER_ACCESS_TOKEN"),
         sniff=re.compile(r"^1/[A-Za-z0-9]{20,}$"), verify=v_buffer,
         fix="publish.buffer.com/settings/api"),
    dict(id="meta", label="Meta / Instagram（投稿・取得）",
         names=["META_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "IG_ACCESS_TOKEN"],
         dest=("env", "META_ACCESS_TOKEN"),
         sniff=re.compile(r"^(?:EAA|IGQ)[A-Za-z0-9_\-]{30,}$"), verify=v_meta,
         fix="developers.facebook.com でアプリを作り long-lived token を発行（60日・自動更新できる）"),
    dict(id="supabase_service", label="Supabase（棚に書ける鍵・無期限）",
         names=["SUPABASE_SERVICE_ROLE", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET"],
         dest=("file", os.path.join(TAMAGO, "supabase_service_role")),
         sniff=re.compile(r"^sb_secret_[A-Za-z0-9_\-]{10,}$"), verify=None,
         fix="supabase.com のプロジェクト設定 → API Keys（無期限）"),
    dict(id="spotify_refresh", label="Spotify（refresh token・★半年で切れる仕様）",
         names=["SPOTIFY_REFRESH_TOKEN"], dest=("env", "SPOTIFY_REFRESH_TOKEN"),
         sniff=None, verify=None,
         fix="developer.spotify.com（2026-06-18の変更で refresh token は6ヶ月で失効。半年に1回だけ人の手が要る）"),
    dict(id="devin", label="Devin（実装の代行）",
         names=["DEVIN_API_KEY"], dest=("env", "DEVIN_API_KEY"),
         sniff=None, verify=None, fix="app.devin.ai"),
    dict(id="fal", label="fal.ai（画像・動画・音声）",
         names=["FAL_KEY", "FAL_API_KEY", "FAL_AI_KEY", "FAL_KEY_ID"],
         dest=("env", "FAL_KEY"),
         sniff=None, verify=None, fix="fal.ai/dashboard/keys",
         # ★置き場が枝分かれしている（実測・kagi_daicho.py と同じ場所を見る）
         extra=lambda: any(os.path.exists(os.path.expanduser(p))
                           for p in ("~/.fal_key", "~/.tamago/fal_key"))),
    dict(id="lovable", label="Lovable（本番へ出す口・公式APIキー）",
         names=["LOVABLE_API_KEY"], dest=("env", "LOVABLE_API_KEY"),
         sniff=None, verify=None, fix="Lovable のワークスペース設定 → API keys",
         # ★既にOAuthで通っているなら「無い」と言わない（嘘の赤を出さない）
         extra=lambda: os.path.exists(os.path.join(TAMAGO, "lovable_oauth.json"))),
]


# ---------------------------------------------------------------------------
def mask(v):
    if not v:
        return "(空)"
    return v[:4] + "…" + v[-2:] + "(%d文字)" % len(v)


def log(msg):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [1175_kagi_uketori] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def jwt_role(v):
    """eyJ… が来たとき、service_role なのか anon なのかを中身から見る。"""
    try:
        body = v.split(".")[1]
        body += "=" * (-len(body) % 4)
        return (json.loads(base64.urlsafe_b64decode(body).decode()) or {}).get("role")
    except Exception:
        return None


def guess(value):
    """値だけ貼られたときに、どの鍵かを当てる。当てられなければ None。"""
    v = value.strip()
    if v.startswith("eyJ") and v.count(".") == 2:
        role = jwt_role(v)
        if role == "service_role":
            return "supabase_service"
        return None            # anon鍵などは黙って置かない（間違った場所へ入れない）
    for sp in SPECS:
        if sp["sniff"] and sp["sniff"].match(v):
            return sp["id"]
    return None


def spec(sid):
    for sp in SPECS:
        if sp["id"] == sid:
            return sp
    return None


def put_env(name, value):
    os.makedirs(os.path.dirname(KEYS), exist_ok=True)
    lines = []
    if os.path.exists(KEYS):
        lines = io.open(KEYS, encoding="utf-8").read().splitlines()
    out, done = [], False
    for ln in lines:
        if ln.strip().startswith(name + "="):
            out.append("%s=%s" % (name, value))
            done = True
        else:
            out.append(ln)
    if not done:
        out.append("%s=%s" % (name, value))
    tmp = "%s.%d.tmp" % (KEYS, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, KEYS)


def put_file(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(value.strip() + "\n")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, path)


def _gh_token_exists():
    """gh が既にトークンを持っているか（鍵台帳と同じ見方）。値は受け取らない。"""
    # ★launchd から走ると PATH が細いので、gh の在りかを決め打ちでも探す
    for exe in ("gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh",
                os.path.expanduser("~/.local/bin/gh"),
                os.path.expanduser("~/.npm-global/bin/gh")):
        try:
            import subprocess
            p = subprocess.run([exe, "auth", "token"], capture_output=True, timeout=15)
            if p.returncode == 0 and p.stdout.strip():
                return True
        except Exception:
            continue
    return False


def have(sp):
    """もう持っているか。読み口は既存の tools/kagi.py に合わせる。"""
    try:
        if sp.get("extra") and sp["extra"]():
            return True
    except Exception:
        pass
    kind, target = sp["dest"]
    if kind == "file":
        try:
            return bool(io.open(target, encoding="utf-8").read().strip())
        except Exception:
            return False
    sys.path.insert(0, HERE)
    try:
        import kagi
        if kagi.get(target):
            return True
    except Exception:
        pass
    for nm in sp["names"]:
        if os.environ.get(nm):
            return True
    try:
        txt = io.open(KEYS, encoding="utf-8").read()
    except Exception:
        return False
    if any(re.search(r"(?m)^%s=\S" % re.escape(nm), txt) for nm in sp["names"]):
        return True
    # ★名前の言い回しが違うだけで「無い」と言わない（嘘の赤を出さない）。
    #   鍵の名前の芯（FAL / GITHUB など）で緩く1回見る。
    core = sp["names"][0].split("_")[0]
    return bool(re.search(r"(?m)^[A-Z0-9]*%s[A-Z0-9_]*=\S" % re.escape(core), txt))


# ---------------------------------------------------------------------------
def trays():
    d = os.path.expanduser("~/Desktop")
    out = [TRAY]
    for base in (d, os.path.join(TAMAGO, "_drop")):
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            p = os.path.join(base, fn)
            if p == TRAY or not os.path.isfile(p):
                continue
            if fn.endswith("_token.txt") or (base.endswith("_drop") and fn.endswith(".txt")):
                out.append(p)
    return out


def parse(text):
    """貼られた文字列を (鍵id, 値, 元の行) の並びと、当てられなかった行に分ける。"""
    got, unknown = [], []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        sid, val = None, None
        m = re.match(r"^([A-Za-z0-9_]+)\s*[=:]\s*(.+)$", ln)
        if m:
            nm, val = m.group(1).strip().upper(), m.group(2).strip().strip('"').strip("'")
            for sp in SPECS:
                if nm in sp["names"]:
                    sid = sp["id"]
                    break
            if sid is None:
                sid = guess(val)
        else:
            val = ln.strip().strip('"').strip("'")
            sid = guess(val)
        if sid and val:
            got.append((sid, val, raw))
        else:
            unknown.append(raw)
    return got, unknown


def shiraseru(rows):
    """新しくしまえた鍵を1行だけ知らせる（既にある口に相乗り）。"""
    if not rows:
        return
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "1175-kagi-uketori",
                "type": "kagi_shimatta",
                "title": "鍵をしまいました（もうログインは頼みません）",
                "message": "／".join(rows),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def kaku(shimatta, nokori, matanai, unknown):
    paper = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "shimatta": shimatta,        # 今回しまえたもの（伏せ字あり）
        "tsuuranakatta": nokori,     # 通らなかったもの
        "mada": matanai,             # まだ無いもの＋どこで作るか
        "wakaranakattaGyou": len(unknown),
        "tray": TRAY,
    }
    try:
        os.makedirs(PUBLIC, exist_ok=True)
        with io.open(OUT, "w", encoding="utf-8") as f:
            json.dump(paper, f, ensure_ascii=False, indent=1)
        pub = dict(paper)
        pub["shimatta"] = [{"id": r["id"], "label": r["label"]} for r in shimatta]
        pub["tsuuranakatta"] = [{"id": r["id"], "why": r["why"]} for r in nokori]
        with io.open(OUT_PUB, "w", encoding="utf-8") as f:
            json.dump(pub, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def main():
    if "--self-test" in sys.argv:
        cases = [("ghp_" + "a" * 36, "github"), ("sk-" + "b" * 40, "openai"),
                 ("xai-" + "c" * 40, "xai"), ("AIza" + "d" * 35, "gemini"),
                 ("abcd efgh ijkl mnop", "gmail"), ("sb_secret_" + "e" * 20,
                                                    "supabase_service"),
                 ("1/" + "f" * 30, "buffer"), ("EAA" + "g" * 40, "meta"),
                 ("ただの文章です", None)]
        bad = [(v[:12], guess(v), want) for v, want in cases if guess(v) != want]
        print("当て方の自己確認：%d件中%d件ずれ %s"
              % (len(cases), len(bad), bad if bad else ""))
        return 0 if not bad else 1

    if not os.path.isdir(TAMAGO):
        # 鍵の置き場が見えない＝サンドボックス。判定を1つも書かない。
        return 3

    # 受け取り口が無ければ作る（書き方を中に書いておく）。1回だけ。
    if not os.path.exists(TRAY):
        try:
            put_file(TRAY, TRAY_HEAD)
            os.chmod(TRAY, stat.S_IRUSR | stat.S_IWUSR)
            log("受け取り口 %s を作りました（ここに貼れば自動でしまいます）" % TRAY)
        except Exception as e:
            log("受け取り口を作れませんでした：%r" % e)

    shimatta, nokori, unknown_all = [], [], []
    for path in trays():
        try:
            text = io.open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        got, unknown = parse(text)
        if not got:
            unknown_all += [(path, u) for u in unknown]
            continue
        kept = []
        for sid, val, raw in got:
            sp = spec(sid)
            ok, why = True, "未検証（叩いて確かめる口が無い鍵）"
            if sp["verify"]:
                ok, why = sp["verify"](val)
            if not ok:
                nokori.append({"id": sid, "label": sp["label"], "masked": mask(val),
                               "why": why})
                kept.append("%s   # ← しまえませんでした：%s" % (raw, why))
                log("%s は通らなかったので、しまいませんでした %s（%s）"
                    % (sp["label"], mask(val), why))
                continue
            kind, target = sp["dest"]
            if kind == "env":
                put_env(target, val)
                where = "~/.tamago/keys/api_keys.env の %s" % target
            else:
                put_file(target, val)
                where = target.replace(os.path.expanduser("~"), "~")
            shimatta.append({"id": sid, "label": sp["label"], "masked": mask(val),
                             "where": where, "verify": why})
            log("%s をしまいました %s → %s ／ %s ／ 平文は消しました"
                % (sp["label"], mask(val), where, why))
        # 平文の始末。しまえた行は消し、駄目だった行と分からなかった行だけ残す
        rest = [ln for ln in kept] + [ln for ln in unknown]
        unknown_all += [(path, u) for u in unknown]
        try:
            if path == TRAY:
                put_file(TRAY, TRAY_HEAD + ("\n".join(rest) + "\n" if rest else ""))
            elif rest:
                put_file(path, "\n".join(rest) + "\n")
            else:
                os.remove(path)
        except Exception as e:
            log("平文の始末に失敗しました（%s）：%r" % (path, e))

    matanai = [{"id": sp["id"], "label": sp["label"], "fix": sp["fix"]}
               for sp in SPECS if not have(sp)]
    kaku(shimatta, nokori, matanai, unknown_all)
    if shimatta:
        shiraseru(["%s（%s）" % (r["label"], r["where"]) for r in shimatta])
    return 0


if __name__ == "__main__":
    sys.exit(main())
