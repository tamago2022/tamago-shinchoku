# -*- coding: utf-8 -*-
"""1051番【外の判定役】Macの上で生きている「別のAI」に、JSONで1問だけ答えさせる口。

なぜ要るか（実測 2026-09-24 03:20-03:26、Mac上で叩いて確かめた）:
  ・`claude` … **そもそもMacに入っていない**（PATHにも /usr/local/bin にも
    /opt/homebrew/bin にも /Users/mac/.claude/local/ にも無い）。
    ★「認証が切れている」ではなく「居ない」。穴を塞ぐ相手が存在しないので、
    **パイプごと替える**しかない。
  ・`OPENAI_API_KEY` … Macの環境にも .env にも無い。だから入荷の関所の門5
    （外部AIに採点させる）は、鍵が無い＋予算の栓が0円で**二重に止まっていた。**
  ・`codex`（/Users/mac/.npm-global/bin/codex, codex-cli 0.144.5）… **生きている。**
    model=gpt-5.6-terra, provider=openai, 認証は ~/.codex/auth.json。
    実測で「1+1」に「2」と答えた。★ChatGPTのログインで動く口なので、
    **1回ごとの課金は出ない（0円）。** APIの鍵は使わない。
  ・`gsk`（Genspark）… 生きている（plan=plus・残1924.937クレジット）。
    ★2026-10-04 にプラン終了で残りは消える＝**使っても追加の金は出ない。**
    ただし1回が数分かかる非同期なので、採点のような速い判定には向かない。控えに置く。

決め:
  ・**金が出る口（OpenAI API・xAI・Gemini）はここでは一切叩かない。**
    叩くのは、既に払い終わっているもの（codex＝ChatGPTログイン、gsk＝期限切れ前のクレジット）だけ。
  ・判定役が1つも居なければ **None を返す。**呼んだ側は「判定役が今いない」と記録して、
    ★**門は通さない側に倒す。**甘い点を自分で付けて通す、は禁止。
"""
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# ★2026-09-24：待ち行列（enqueue_job / wait_job / JOBS_*）は
#   **`tools/shigoto_queue.py` が正本。**ここはそこから再輸出しているだけ。
#   このファイルを丸ごと作り替えても工場は死なない（それが03:38に起きた事故）。
#   ★待ち行列の中身をここに書き戻さないこと。増やすなら shigoto_queue.py 側。
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shigoto_queue import (  # noqa: E402,F401
    JOBS_DIR, JOBS_PENDING, JOBS_DONE, JOBS_RUNNING,
    enqueue_job, wait_job, write_job_result, pending_names,
)

CODEX = "/Users/mac/.npm-global/bin/codex"
GSK = "/Users/mac/.npm-global/bin/gsk"
JSON_OBJ = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.S)


def _hiroi_json(text):
    """出力の中から**いちばん後ろの**JSONオブジェクトを拾う。
    codex は前置き（model: / session id: など）を先に出すので、前から拾うと化ける。"""
    best = None
    for m in JSON_OBJ.finditer(text or ""):
        try:
            d = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(d, dict) and d:
            best = d
    return best


def codex_aru():
    return os.path.exists(CODEX)


def kiku_codex(system, user, timeout=150, model=None):
    """codex に1問だけ聞いてJSONで返させる。戻り値 (dict|None, who, err)"""
    if not os.path.exists(CODEX):
        return None, "", "codexがMacにありません（%s）" % CODEX
    prompt = ("%s\n\n%s\n\n"
              "★返すのはJSONひとつだけ。前置きも説明も、```も付けないでください。"
              % (system, user))
    # ★お題は標準入力から渡す（`-`）。argv に長文を積むと環境ごとに上限で切れる。
    base = [CODEX, "exec"]
    if model:
        base += ["-m", model]
    out = ""
    for extra in (["--skip-git-repo-check"], []):
        try:
            p = subprocess.run(base + extra + ["-"], input=prompt,
                               capture_output=True, text=True, timeout=timeout,
                               cwd="/tmp")
        except subprocess.TimeoutExpired:
            return None, "codex", "時間切れ（%d秒）" % timeout
        except Exception as e:
            return None, "codex", "走らせられない：%r" % e
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        if p.returncode == 0 or "unexpected argument" not in out:
            break
    d = _hiroi_json(out)
    if d is None:
        return None, "codex", "JSONが返ってこない（rc=%s）%s" % (p.returncode, out[-300:])
    return d, "codex(gpt-5.6-terra)", ""


def gsk_zandaka():
    if not os.path.exists(GSK):
        return None
    try:
        p = subprocess.run([GSK, "me"], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return None
        return float(((json.loads(p.stdout) or {}).get("data") or {}).get("credit_balance"))
    except Exception:
        return None


def dare_ga_iru():
    """いま判定役が誰か。報告にそのまま書ける形で返す。"""
    out = []
    if os.path.exists(CODEX):
        out.append({"who": "codex(gpt-5.6-terra)", "kane": "0円（ChatGPTのログイン。1回ごとの課金なし）"})
    z = gsk_zandaka()
    if z is not None:
        out.append({"who": "genspark(gsk)", "kane": "0円（前払い済みのクレジット %.3f・10/4に消える）" % z})
    return out


def kiku(system, user, timeout=150):
    """判定役に聞く。codex → （将来）gsk の順。誰も居なければ (None, '', 理由)。"""
    d, who, err = kiku_codex(system, user, timeout=timeout)
    if d is not None:
        return d, who, ""
    return None, "", err or "判定役が今いない"


if __name__ == "__main__":
    import sys
    if "--dare" in sys.argv:
        print(json.dumps(dare_ga_iru(), ensure_ascii=False, indent=1))
    else:
        d, who, err = kiku("あなたは計算係です。",
                           '2たす3はいくつですか。{"answer": 数} の形で返してください。')
        print("who=%s err=%s d=%s" % (who, err, d))
