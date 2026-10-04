#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鍵の生死確認（毎朝1回）。2026-10-04・たまごさん指示「俺を動かさない仕組みを作ってくれ」。

やること（curl/urllibだけ。ブラウザ・有料呼び出しなし）：
  1. 全部の鍵・ログインを1回ずつ叩いて「生きている／死んでいる／一時の通信障害／鍵なし／本人が要る」を判定。
     ・401/403 ＝ 鍵そのものが死んでいる（invalid）。429/5xx/タイムアウト ＝ 通信障害（鍵は無実。次回やり直し）。
       （Codex #580 の助言＝invalid_grant と通信障害を区別する、と同じ考え方）
  2. 控えから復旧：鍵の正本(~/.tamago/keys/api_keys.env)が消えた・縮んだ時は .last_good から戻す。
     全部そろっている時は .last_good を更新する。消さない。
  3. 最後に成功した時刻を残す（失敗しても前回の成功時刻は消さない）。
  4. 同意が要るもの（Lovable）は、承認URLの置き場を status/kagi_shounin_url.json に用意する。
  5. 結果は status/kagi_seimei.json と status/kagi_seimei.md（★鍵の値は1文字も書かない）。

Lovable の鍵の保存・更新は lovable_token_keeper.py（別担当）の持ち場。ここは状態を読むだけで、鍵に触らない。

使い方：
    python3 tools/kagi_seimei.py            # 今日まだなら走る（朝6時以降。心臓から5分おきに呼ばれても1日1回）
    python3 tools/kagi_seimei.py --force    # 今すぐ全部叩く
"""
import datetime
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kagi  # noqa: E402

HOME = os.path.expanduser("~")
OUT_JSON = os.path.join(REPO, "status", "kagi_seimei.json")
OUT_MD = os.path.join(REPO, "status", "kagi_seimei.md")
OUT_URL = os.path.join(REPO, "status", "kagi_shounin_url.json")
HIST = os.path.join(REPO, "status", "kagi_seimei_history.jsonl")
TAMAGO = os.path.join(HOME, ".tamago")

ALIVE, DEAD, NET, MISSING, HUMAN, WAIT = "生きている", "死んでいる", "通信障害(鍵は無実)", "鍵なし", "本人が要る", "枠待ち(鍵は無実)"
UA = "tamago-kagi-seimei/1"
LAST_BODY = ""
ZANDAKA = "鍵は生きている・残高なし"


def http(url, headers=None, data=None, method=None, timeout=15):
    """HTTPコードだけ返す。本文・鍵は残さない。通信失敗は 0。"""
    req = urllib.request.Request(url, data=data, headers=dict({"User-Agent": UA}, **(headers or {})), method=method)
    global LAST_BODY
    LAST_BODY = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            r.read(2048)
            return r.getcode()
    except urllib.error.HTTPError as e:
        try:
            LAST_BODY = e.read(600).decode("utf-8", "ignore")  # 相手のエラー文(鍵ではない)。判定にだけ使い保存しない
        except Exception:
            pass
        return e.code
    except Exception:
        return 0


def judge(code, ok=(200,)):
    if code in ok:
        return ALIVE, "HTTP %d" % code
    if code == 403 and ("credits" in LAST_BODY or "billing" in LAST_BODY.lower() or "quota" in LAST_BODY.lower()):
        return ZANDAKA, "HTTP 403（鍵は通った。チャージ/課金が未設定。お金が動くのでAIは払わない）"
    if code in (401, 403):
        return DEAD, "HTTP %d（鍵が拒否された）" % code
    if code == 0:
        return NET, "通信できず（次回やり直し）"
    if code == 429 or code >= 500:
        return NET, "HTTP %d（相手側の一時不調）" % code
    return NET, "HTTP %d（判定保留）" % code


def bearer(url, name, ok=(200,)):
    k = kagi.get(name)
    if not k:
        return MISSING, "鍵が置かれていない"
    return judge(http(url, {"Authorization": "Bearer " + k}), ok)


# ---------------------------------------------------------------- 各サービスの1回叩き
def p_buffer():
    k = kagi.get("BUFFER_ACCESS_TOKEN")
    if not k:
        return MISSING, "鍵が置かれていない"
    try:  # 既存の門（429で閉まる・1日の天井）を必ず通る＝枠を食い潰さない
        import buffer_waku
        import buffer_kura
        if not buffer_waku.ake():
            return WAIT, "Bufferの門が閉まっている（429後の待ち）"
        if not buffer_kura.tsukau("kagi_seimei"):
            return WAIT, "Bufferの1日の天井に達している"
    except Exception:
        pass
    body = json.dumps({"query": "query { account { id } }"}).encode()
    return judge(http("https://api.buffer.com", {"Authorization": "Bearer " + k, "Content-Type": "application/json"},
                      data=body, method="POST"))


def p_openai():
    return bearer("https://api.openai.com/v1/models", "OPENAI_API_KEY")


def p_xai():
    return bearer("https://api.x.ai/v1/models", "XAI_API_KEY")


def p_youtube():
    k = kagi.get("YOUTUBE_DATA_API_KEY")
    if not k:
        return MISSING, "鍵が置かれていない"
    return judge(http("https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&key=" + k), ok=(200,))


def p_devin():
    return bearer("https://api.devin.ai/v1/sessions?limit=1", "DEVIN_API_KEY")


def p_supabase_read():
    u, k = kagi.get("SUPABASE_URL"), kagi.get("SUPABASE_PUBLISHABLE_KEY")
    if not (u and k):
        return MISSING, "URLか公開鍵が置かれていない"
    return judge(http(u.rstrip("/") + "/auth/v1/health", {"apikey": k}), ok=(200,))


def p_supabase_write():
    u, k = kagi.get("SUPABASE_URL"), kagi.get("SUPABASE_SERVICE_ROLE_KEY")
    if not k:
        return MISSING, "書き込み鍵が置かれていない（joy-relief-station/.env.local にも無い）"
    return judge(http(u.rstrip("/") + "/rest/v1/", {"apikey": k, "Authorization": "Bearer " + k}), ok=(200, 404))


def p_github():
    tok = None
    try:
        tok = open(os.path.join(TAMAGO, "gh_token")).read().strip()
    except Exception:
        pass
    tok = tok or kagi.get("GITHUB_TOKEN")
    if not tok:
        return MISSING, "トークンが置かれていない"
    return judge(http("https://api.github.com/user", {"Authorization": "token " + tok, "Accept": "application/vnd.github+json"}))


def p_gemini():
    k = kagi.get("GEMINI_API_KEY")
    if not k:
        return MISSING, "鍵が置かれていない"
    return judge(http("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", {"x-goog-api-key": k}))


def p_fal():
    k = kagi.get("FAL_KEY")
    if not k:
        return MISSING, "鍵が置かれていない"
    return judge(http("https://api.fal.ai/v1/models?endpoint_id=fal-ai/flux/dev", {"Authorization": "Key " + k}))


def p_claude():
    try:
        r = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, PATH="/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")))
        d = json.loads(r.stdout or "{}")
        if d.get("loggedIn"):
            return ALIVE, "ログイン済み（%s）" % d.get("authMethod", "?")
        return DEAD, "ログインしていない"
    except Exception:
        return NET, "claude auth status が答えない"


def p_lovable():
    """読むだけ。保存・更新は lovable_token_keeper.py の持ち場。状態は keeper が書く lovable_keeper_state.json を読む。"""
    path = os.path.join(TAMAGO, "lovable_oauth.json")
    try:
        if os.path.getsize(path) == 0:
            return DEAD, "鍵ファイルが空（承認URLを開けば戻る）"
        d = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return DEAD, "鍵ファイルが無い（承認URLを開けば戻る）"
    except Exception:
        return DEAD, "鍵ファイルが壊れている（承認URLを開けば戻る）"
    if not d.get("refresh_token"):
        return DEAD, "巻き直し用の鍵(refresh)が無い（承認URLを開けば戻る）"
    st = {}
    try:
        st = json.load(open(os.path.join(TAMAGO, "lovable_keeper_state.json"), encoding="utf-8"))
    except Exception:
        pass
    if st.get("needConsent"):
        return DEAD, "同意のやり直しが必要と記録されている（承認URLを開けば戻る）"
    if st.get("lastFailure"):
        return NET, "直近の巻き直しが失敗(%s)・次回やり直し" % st.get("lastFailure")
    return ALIVE, "refresh鍵あり・自動巻き直し中（最後の成功 %s）" % st.get("lastOkAt", "不明")


def p_none(msg):
    return lambda: (MISSING, msg)


def p_human(msg):
    return lambda: (HUMAN, msg)


# name, 呼び名, 種類, 自動更新, 期限, 本人が必要なこと, probe
REG = [
    ("buffer", "Buffer", "APIキー", "不要(無期限扱い)", "公式記載なし", None, p_buffer),
    ("openai", "OpenAI", "APIキー", "不要(無期限)", "消すまで", None, p_openai),
    ("xai", "xAI(Grok)", "APIキー", "不要(無期限)", "消すまで", None, p_xai),
    ("youtube", "YouTube Data API", "APIキー", "不要(無期限)", "消すまで", None, p_youtube),
    ("devin", "Devin", "APIキー", "不要", "不明", None, p_devin),
    ("supabase_read", "Supabase(読み)", "公開鍵", "不要(無期限)", "消すまで", None, p_supabase_read),
    ("supabase_write", "Supabase(書き込み)", "サービス鍵", "不要(無期限)", "消すまで", "初回に鍵を kagi.txt に貼る", p_supabase_write),
    ("github", "GitHub", "トークン", "不要(無期限PAT)", "設定次第", None, p_github),
    ("claude", "Claude CLI", "OAuthトークン(setup-token)", "不可(1年固定)", "約1年", "1年に1回だけ本人(ログイン)", p_claude),
    ("lovable", "Lovable", "OAuth2", "自動(期限5分前に巻き直し・失敗しても消さない)", "8時間", "巻き直せなくなった時だけ『承認URLを開く』(AIが開ける)", p_lovable),
    ("gemini", "Gemini", "APIキー", "不要(無期限)", "消すまで", "初回に鍵を kagi.txt に貼る", p_gemini),
    ("fal", "fal.ai", "APIキー", "不要", "不明", "初回に鍵を kagi.txt に貼る", p_fal),
    ("gmail", "Gmail", "アプリパスワード", "不要(無期限)", "パスワード変更まで", "初回に16文字を kagi.txt に貼る",
     lambda: (MISSING, "アプリパスワードが置かれていない") if not (kagi.get("GMAIL_APP_PASSWORD") or os.path.exists(os.path.join(TAMAGO, "gmail_app_password"))) else (ALIVE, "置かれている(叩いていない)")),
    ("notion", "Notion", "内部トークン", "不要(無期限)", "消すまで", "初回に鍵を kagi.txt に貼る", p_none("鍵が置かれていない") if not kagi.get("NOTION_TOKEN") else (lambda: (ALIVE, "置かれている(叩いていない)"))),
    ("meta", "Instagram/Meta", "長期トークン", "自動可(60日・refreshで巻き直し)", "60日", "初回に鍵を貼る", p_none("鍵が置かれていない") if not (kagi.get("META_ACCESS_TOKEN") or kagi.get("IG_ACCESS_TOKEN")) else (lambda: (ALIVE, "置かれている(叩いていない)"))),
    ("spotify", "Spotify", "OAuth refresh", "自動可(ただし半年でリセット)", "半年", "半年に1回だけ本人(同意)", p_none("鍵が置かれていない") if not kagi.get("SPOTIFY_REFRESH_TOKEN") else (lambda: (ALIVE, "置かれている(叩いていない)"))),
    ("gumroad", "Gumroad", "アクセストークン", "不要(無期限)", "消すまで", None, p_none("鍵が読み口に届いていない") if not kagi.get("GUMROAD_ACCESS_TOKEN") else (lambda: (ALIVE, "置かれている(叩いていない)"))),
    ("x", "X(Twitter)", "Chromeのcookie", "不可", "いつでも切れる", "切れたらログイン(本人)", p_human("cookie頼み。APIの鍵に置き換え可能なら置き換える")),
    ("line", "LINE", "Chromeのcookie", "不可", "いつでも切れる", "切れたらログイン(本人)", p_human("cookie頼み")),
    ("genspark", "Genspark", "Chromeのcookie/公式CLI", "不可", "いつでも切れる", "切れたらログイン(本人)", p_human("cookie頼み")),
]


# ---------------------------------------------------------------- 開け直しの台帳（一度自分で開けられたものは、必ず手順を残す）
# 形：id -> (実証, 手順, 自動化の段階, 期限前のきっかけ)
TEJUN = {
    "lovable": ("2026-10-04 Dispatch が承認URLを開き、許可済みで通った（受け皿が保存 21:02）。たまごさんの操作ゼロ。",
                "①受け皿(127.0.0.1:41999・~/.tamago/lovable_listener.py)が立っていて ~/.tamago/lovable_authorize_url.txt が新しいことを確認（心臓の lovable_auth_keeper が立て続ける）→ ②そのURLを Chrome(Claude作業用・Lovableにログイン済み)で開く → ③同意画面なら『Allow』→ 自動で戻り鍵が保存される。",
                "自動巻き直し(keeper・期限5分前から)。同意のやり直しだけ Dispatch が開く（URLの自動生成と自動クリックは安全チェックで止められ保留）",
                "keeperが needConsent=true にした瞬間（kagi_seimei が status/kagi_seimei.json の lovable_needs_consent に立てる）"),
    "claude": ("2026-09-05 setup-token で1年トークン発行（~/.tamago/claude_token）。承認URLの再取得は tools/1161_kagi_toru.py が自動で回せる。",
               "①`python3 tools/1161_kagi_toru.py`(心臓が常駐で回す)が `claude setup-token` を起動し承認URLを status/1161_url.txt に出す → ②Dispatch が Chrome でそのURLを開き『許可』→ 出たコードを status/1161_code.txt に置く → ③自動で保存・疎通確認。",
               "手順あり・URLは自動で用意、承認クリックは Dispatch", "期限の30日前（claude_token.minted から1年）。kagi_seimei が days_left を出す"),
    "github": ("gh_token は github_watch.py が GitHub App から自動で作り直す控え(6時間)。", "tools/github_watch.py が自動。失敗時は status を見る。", "完全自動", "6時間ごと"),
    "buffer": ("Buffer の鍵は初回登録(kagi.txt に貼る)のみ。", "鍵が死んだ時だけ新規発行→kagi.txt。", "初回のみ本人", "なし(期限不明)"),
}


# ---------------------------------------------------------------- 控えから復旧
def keep_backup():
    seihon = kagi.SEIHON
    good = seihon + ".last_good"
    msg = None
    try:
        cur = kagi._parse(seihon) if os.path.exists(seihon) else {}
        old = kagi._parse(good) if os.path.exists(good) else {}
        if old and (not cur or len(cur) < len(old) or any(k not in cur for k in old)):
            lost = [k for k in old if k not in cur]
            merged = dict(old)
            merged.update(cur)  # 今ある分を優先、無い分だけ控えから足す
            for k, v in merged.items():
                if k not in cur:
                    kagi.put(k, v)
            msg = "正本から消えていた %d 本を控え(.last_good)から戻した" % len(lost)
        cur = kagi._parse(seihon)
        if cur:
            tmp = "%s.%d.tmp" % (good, os.getpid())
            shutil.copyfile(seihon, tmp)
            os.chmod(tmp, 0o600)
            os.replace(tmp, good)
    except Exception as e:
        msg = "控えの処理に失敗: %s" % type(e).__name__
    return msg


# ---------------------------------------------------------------- 実行
def run(force=False):
    now = datetime.datetime.now()
    prev = {}
    try:
        prev = json.load(open(OUT_JSON, encoding="utf-8"))
    except Exception:
        pass
    today = now.strftime("%Y-%m-%d")
    if not force:
        if now.hour < 6 or prev.get("full_run_date") == today:
            return 0
    os.umask(0o077)
    restore_msg = keep_backup()
    rows, prev_rows = [], {r["id"]: r for r in prev.get("services", [])}
    for sid, name, kind, renew, expiry, human, probe in REG:
        try:
            st, detail = probe()
        except Exception as e:
            st, detail = NET, "判定中に例外 %s" % type(e).__name__
        p = prev_rows.get(sid, {})
        last_ok = p.get("last_ok")
        if st == ALIVE:
            last_ok = now.isoformat(timespec="seconds")
        rows.append({"id": sid, "name": name, "kind": kind, "auto_renew": renew, "expiry": expiry,
                     "human_needed": human, "state": st, "detail": detail,
                     "last_ok": last_ok, "checked": now.isoformat(timespec="seconds")})
    # Claudeの1年期限（作成日から）
    try:
        minted = os.path.getmtime(os.path.join(TAMAGO, "claude_token.minted"))
        days_left = 365 - int((time.time() - minted) / 86400)
    except Exception:
        days_left = None
    for r in rows:
        if r["id"] == "claude" and days_left is not None:
            r["days_left"] = days_left
            if days_left < 30:
                r["detail"] += "／期限まであと約%d日（本人のログイン1回が近い）" % days_left

    auto = [r for r in rows if r["state"] == ALIVE and not (r["human_needed"] or "").startswith(("1年", "半年", "切れたら"))]
    human_once = [r for r in rows if r not in auto]
    broken = [r for r in rows if r["state"] == DEAD]
    out = {"at": now.isoformat(timespec="seconds"), "full_run_date": today, "restore": restore_msg,
           "count_total": len(rows), "count_auto_ok": len(auto), "count_human_once": len(human_once),
           "broken_now": [r["name"] for r in broken], "services": rows}
    tmp = OUT_JSON + ".%d.tmp" % os.getpid()
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_JSON)
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": out["at"], "states": {r["id"]: r["state"] for r in rows}}, ensure_ascii=False) + "\n")

    md = ["# 鍵の生死（%s 自動）" % out["at"], "",
          "鍵の値は書かない。壊れていたら『承認URL』を AI が自分で開く（kagi_shounin_url.json）。", "",
          "| サービス | 今 | 自動更新 | 期限 | 最後に成功 | 本人が要るのは |", "|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s（%s） | %s | %s | %s | %s |" % (r["name"], r["state"], r["detail"], r["auto_renew"], r["expiry"],
                                                       r["last_ok"] or "—", r["human_needed"] or "なし"))
    md += ["", "## 本人しかできないもの（AIは頼む前に自分で開けに行く。頼んでよいのはこれだけ）", ""]
    for r in rows:
        if r in human_once:
            md.append("- %s：%s" % (r["name"], r["human_needed"] or ("チャージ(お金が動くので本人)" if r["state"] == ZANDAKA else "なし")))
    md += ["", "※パスワード・二段階認証・初回登録・お金の支払いだけが本人。同意画面(許可済み)の承認URLはAIが開く。"]
    if restore_msg:
        md += ["", "控え復旧：" + restore_msg]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    # Lovable の同意が必要になったら、承認URLの置き場に『要対応』を立てる（開くのは Dispatch／既存の受け皿）
    lv = [r for r in rows if r["id"] == "lovable"][0]
    out["lovable_needs_consent"] = (lv["state"] == DEAD)
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 手順台帳
    tj = ["# 鍵の開け直し台帳（一度自分で開けられたものは、AIが100%自分で開け直す）", "",
          "| サービス | 実証（いつ・誰が・どう） | 開け直し手順 | 自動化の段階 | 期限前のきっかけ |", "|---|---|---|---|---|"]
    for k, (a1, a2, a3, a4) in TEJUN.items():
        tj.append("| %s | %s | %s | %s | %s |" % (k, a1, a2, a3, a4))
    open(os.path.join(REPO, "status", "kagi_tejun.md"), "w", encoding="utf-8").write("\n".join(tj) + "\n")

    # 承認URLの置き場（status/ は git 管理外）
    url = {"at": out["at"], "note": "同意が要る口。AI(Dispatch)が自分でブラウザで開く。本人に頼まない。",
           "lovable": {"state": [r["state"] for r in rows if r["id"] == "lovable"][0],
                       "url_file": os.path.join(TAMAGO, "lovable_authorize_url.txt"),
                       "listener": "127.0.0.1:41999（~/.tamago/lovable_listener.py・心臓が立て続ける）",
                       "how": "Chrome『Claude作業用』は Lovable にログイン済み。承認URLを開くと同意画面→許可済みなら自動で戻り、受け皿が鍵を保存する。"}}
    json.dump(url, open(OUT_URL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("鍵%d個：自動OK%d／本人が要る%d／死んでいる%s" % (len(rows), len(auto), len(human_once), out["broken_now"] or "なし"))
    return 0


if __name__ == "__main__":
    sys.exit(run(force="--force" in sys.argv))
