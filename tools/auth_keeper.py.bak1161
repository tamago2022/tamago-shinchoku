#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""975番：Claudeのログインを「切れない形」にする係。ここ1か所に集約する。

たまごさん（2026-09-20）：
  「何十回ログインすればいいんだって話なんだよ。つないどいてよ、ちゃんと。」
  「直しました、じゃなくて『もう起きません。◯◯を1か所にしたから』と言い切れること。」

------------------------------------------------------------------
なぜ切れたのか（2026-09-20 実測。推測ではない）
------------------------------------------------------------------
キーチェーン項目 "Claude Code-credentials" の中身の**形だけ**を調べた結果：

    claudeAiOauth.accessToken       = 長さ0（空）
    claudeAiOauth.refreshToken      = 長さ0（空）
    claudeAiOauth.expiresAt         = 0
    claudeAiOauth.refreshTokenExpiresAt = 1790992399718（2026年10月頃）

**鍵の箱は残っているのに、中の鍵が2本とも空文字になっていた。**
更新用の鍵(refreshToken)まで空なので、CLIは自力で作り直せない
＝`claude -p` は必ず `Failed to authenticate: OAuth session expired and
could not be refreshed` になる。2026-09-18 03:19 に工場が発車を止めたのは
これが理由（status/auth_expired.flag・no_launch.flag の時刻が一致）。

保険として置いてあった ~/.tamago/claude_token（2026-09-05 作成・1年もつはずの
setup-token）も実測したが `401 OAuth access token is invalid` で死んでいた。
しかも ~/.tamago/use_token が無かったので、**この保険は一度も使われていなかった。**
（auto_launcher.py / command_ingest.py / auth_watch.py の claude_env() は
  use_token が無いと環境変数を渡さない仕様。置いただけで効くと思われていた。）

公式ドキュメント（https://code.claude.com/docs/en/authentication）より：
  - 認証の優先順位は ①クラウド ②ANTHROPIC_AUTH_TOKEN ③ANTHROPIC_API_KEY
    ④apiKeyHelper ⑤CLAUDE_CODE_OAUTH_TOKEN ⑥プロファイル ⑦/loginのOAuth。
  - `claude setup-token` は**1年もつ**OAuthトークンを出す。どこにも保存しないので
    自分で保管して CLAUDE_CODE_OAUTH_TOKEN に入れる。Max契約のまま使える。
  - /login のOAuthは有効期限が短く、期限切れの3日前に警告が出るだけ。
    **無人で走らせるものに /login のOAuthを使うのが、そもそも間違いだった。**

------------------------------------------------------------------
だからこうする（1か所）
------------------------------------------------------------------
1. 正本を「キーチェーンの/loginのOAuth」から「1年もつsetup-token」へ移す。
   置き場は ~/.tamago/claude_token（600）。使う合図は ~/.tamago/use_token。
   **この係が、生きているときだけ use_token を立て、死んだら自分で外す。**
   （置きっぱなしの死んだトークンが正しい鍵を上書きする 2026-09-05 の事故は、
     これで構造的に起きない＝「生きていることを確かめた鍵しか立てない」）
2. 実際に通るかを30分に1回だけ確かめる（無駄打ちしない）。
   通ったら auth_expired.flag / no_launch.flag を自分で外す。
3. 1年の期限が近づいたら、30日前・14日前・7日前・3日前に1回ずつだけ知らせる。
   **切れてから慌てない。切れる前に言う。**
4. 本当に鍵が無くなったときだけ、たまごさんに1行で頼む。
   頼み方は**「いつも使っているClaudeのアプリで、1回ログインし直す」だけ**。
   ファイルを渡さない・ダブルクリックさせない・ターミナルを開かせない
   （2026-09-20 たまごさん指定。過去に「ダブルクリックで開きます」が開けず実害あり）。
   鍵が戻ったことはこの係が自分で気づいて、発車も自分で再開する。

値（トークン本体）は読み出さない・ログにも報告にも書かない。長さと生死だけ扱う。
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
STATE_PATH = os.path.join(STATUS, "auth_keeper.json")
AUTH_FLAG = os.path.join(STATUS, "auth_expired.flag")
NO_LAUNCH = os.path.join(STATUS, "no_launch.flag")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
LOG = os.path.join(STATUS, "auth_keeper.log")

TOKEN_PATH = os.path.expanduser("~/.tamago/claude_token")
USE_TOKEN = os.path.expanduser("~/.tamago/use_token")
MINTED_PATH = os.path.expanduser("~/.tamago/claude_token.minted")

CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break

# ---- 1158番：claude は必ず関所を通す（2026-09-26）----
# 同時起動の競合で refreshToken が空を書き戻され鍵ごと消える事故を、
# 起動口で物理的に止める。上限は status/dojisu_jougen.json の「同時上限」。
# 関所は引数をそのまま素通しするので、呼ぶ側のコードは1文字も変わらない。
_KANMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1158_kanmon.py")
if os.path.exists(_KANMON):
    os.environ.setdefault("KANMON_CLAUDE_BIN", CLAUDE)
    CLAUDE = _KANMON


PROBE_INTERVAL_OK = 1800       # 通っているときは30分に1回
PROBE_INTERVAL_NG = 600        # 切れているときは10分に1回（戻ったら即再開したい）
TOKEN_LIFETIME_DAYS = 365      # setup-token の公称寿命
WARN_DAYS = (30, 14, 7, 3, 1)
NOTIFY_COOLDOWN = 6 * 3600     # 同じお願いを6時間に1回より多く言わない


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
        # 太らせない
        if os.path.getsize(LOG) > 200000:
            lines = io.open(LOG, encoding="utf-8").read().splitlines()[-500:]
            io.open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    except Exception:
        pass


def load_state():
    try:
        return json.load(io.open(STATE_PATH, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    try:
        tmp = STATE_PATH + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


def notify(key, message, st, cooldown=None):
    """dispatch_outbox.jsonl へ1行だけ。同じ用件は既定6時間に1回まで。"""
    last = (st.get("notified") or {}).get(key, 0)
    if time.time() - last < (cooldown if cooldown else NOTIFY_COOLDOWN):
        return
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "975-auth-%s" % key,
                "type": "auth_keeper",
                "title": "Claudeのログイン",
                "message": message,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    st.setdefault("notified", {})[key] = time.time()
    log("通知: %s" % key)


def token_text():
    try:
        t = io.open(TOKEN_PATH, encoding="utf-8").read().strip()
        return t if t.startswith("sk-ant-") else ""
    except Exception:
        return ""


def probe(use_token):
    """実際に1回だけ叩いて生死を見る。戻り値 (ok, 短い理由)。値は絶対に返さない。"""
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    env.pop("ANTHROPIC_API_KEY", None)
    if use_token:
        t = token_text()
        if not t:
            return False, "トークンファイルが無い/形が違う"
        env["CLAUDE_CODE_OAUTH_TOKEN"] = t
    try:
        r = subprocess.run([CLAUDE, "-p", "--model", "claude-sonnet-5",
                            "--output-format", "json", "1+1は？数字だけ"],
                           capture_output=True, text=True, timeout=120, env=env)
    except Exception as e:
        return False, "叩けなかった(%s)" % type(e).__name__
    out = (r.stdout or "") + (r.stderr or "")
    if "OAuth session expired" in out:
        return False, "OAuth session expired（更新用の鍵ごと無効）"
    if "OAuth access token is invalid" in out:
        return False, "トークンが無効（作り直しが要る）"
    if "Failed to authenticate" in out:
        return False, "認証に失敗"
    if '"result"' in out and '"is_error":true' not in out.replace(" ", ""):
        return True, "ok"
    if '"result"' in out:
        return False, "実行はできたがエラー応答"
    return False, "応答が読めない"


def set_use_token(on):
    try:
        if on:
            io.open(USE_TOKEN, "w", encoding="utf-8").write(
                "975番・auth_keeperが『実際に通ること』を確かめて立てた合図 %s\n" % time.strftime("%F %T"))
        elif os.path.exists(USE_TOKEN):
            os.remove(USE_TOKEN)
    except Exception:
        pass


def clear_flags():
    for p in (AUTH_FLAG, NO_LAUNCH):
        try:
            if os.path.exists(p):
                # no_launch.flag は「週次上限」など別の理由でも立つ。認証の文言のときだけ外す。
                if p == NO_LAUNCH:
                    txt = io.open(p, encoding="utf-8").read()
                    if "ログイン" not in txt and "OAuth" not in txt:
                        continue
                os.remove(p)
        except Exception:
            pass


def raise_flags(reason):
    """止めるときは**本当の理由**を書く。『週の枠が上限』と混ざらないようにする。"""
    try:
        io.open(AUTH_FLAG, "w", encoding="utf-8").write(time.strftime("%F %H:%M"))
        io.open(NO_LAUNCH, "w", encoding="utf-8").write(
            "Claudeのログインが切れています（%s）。枠の問題ではありません。"
            "status/LOGIN.md の1行をターミナルに貼ってEnterを押すと、1年もつ形に入れ替わります。"
            "戻ったことはこちらで気づいて、発車も自動で再開します。%s\n"
            % (reason, time.strftime("%F %H:%M")))
    except Exception:
        pass


def token_days_left():
    """setup-tokenの残り日数（分からなければ None）。"""
    try:
        minted = float(io.open(MINTED_PATH, encoding="utf-8").read().strip())
    except Exception:
        try:
            minted = os.path.getmtime(TOKEN_PATH)
        except Exception:
            return None
    return int((minted + TOKEN_LIFETIME_DAYS * 86400 - time.time()) // 86400)


def main():
    st = load_state()
    now = time.time()
    interval = PROBE_INTERVAL_NG if os.path.exists(AUTH_FLAG) else PROBE_INTERVAL_OK
    if now - float(st.get("lastProbeAt") or 0) < interval:
        return 0
    st["lastProbeAt"] = now

    # ---- ① いまの正本（use_tokenが立っていればトークン、無ければキーチェーン）で確かめる ----
    using_token = os.path.exists(USE_TOKEN)
    ok, why = probe(using_token)

    # ---- ② ダメなら、もう片方も1回だけ試す（正本の付け替えは自動でやる） ----
    if not ok:
        other_ok, other_why = probe(not using_token)
        if other_ok:
            set_use_token(not using_token)
            log("正本を切り替えました（%s → %s）"
                % ("トークン" if using_token else "キーチェーン",
                   "キーチェーン" if using_token else "トークン"))
            ok, why, using_token = True, "ok", (not using_token)
        else:
            why = "%s／もう片方も %s" % (why, other_why)
            # 死んだトークンを立てっぱなしにしない（2026-09-05の事故の構造的封じ）
            if using_token:
                set_use_token(False)

    st["state"] = "ok" if ok else "expired"

    if ok:
        st["lastOkAt"] = now
        st["ngSince"] = None
        st["source"] = "setup-token(1年)" if using_token else "キーチェーンの/loginのOAuth"
        clear_flags()
        # ---- ③ 切れる前に言う ----
        if using_token:
            d = token_days_left()
            if d is not None:
                st["tokenDaysLeft"] = d
                for w in WARN_DAYS:
                    if d <= w and not (st.get("warned") or {}).get(str(w)):
                        st.setdefault("warned", {})[str(w)] = True
                        notify("expire-%d" % w,
                               "🔑 Claudeのログインが、あと%d日で期限切れになります。"
                               "いつものClaudeのアプリで1回ログインし直しておいてください"
                               "（切れてから慌てないように、先に声をかけています）。" % d, st)
                        break
        else:
            # キーチェーンの/loginのOAuthで動いている＝**競合でいつでも消える形のまま。**
            # 2026-09-25の実測：refreshTokenは1回しか使えず、同時に十数本走るこの工場では
            # 負けた側が「空っぽ」を書き戻して正しい鍵ごと消す。黙って動かすと必ずまた落ちる。
            # だから3日に1回だけ「1本貼れば1年もつ形になる」と声をかける（毎回は言わない）。
            notify("kirenai-katachi",
                   "🔑 いまのログインは数日で切れる形（/loginのOAuth）で動いています。"
                   "同時に何本も走らせると競合で鍵ごと消えるので、また必ず落ちます。"
                   "status/LOGIN.md の1行を貼ってEnterすると1年もつ形に替わります（課金は変わりません）。",
                   st, cooldown=3 * 86400)
        log("生きています（%s）" % st["source"])
    else:
        raise_flags(why)
        st["lastNgWhy"] = why
        # いつから切れているか（進捗表の赤に「◯日から」と出すため）。
        # 一度立てたら、通るまで上書きしない＝5日経っていることが数字で見える。
        if not st.get("ngSince"):
            st["ngSince"] = time.strftime("%F %H:%M")
        notify("expired",
               "🔑 Claudeのログインが切れました（%s）。枠の問題ではありません。"
               "鍵だけはAIには作れません。status/LOGIN.md の1行を貼ってEnterを押してください"
               "（1年もつ形に入れ替わるので、次は来年までありません）。"
               "戻ったことはこちらで気づいて、発車も自動で再開します。" % why, st)
        log("切れています（%s）" % why)

    save_state(st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
