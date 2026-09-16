#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""917番【仕組み⑭】外部AI（まずGrok）に「たまごさんに見せていいか」を判定させる。

たまごさんの言葉（2026-09-17 06:25）：
  「人に見せられる状態じゃないものを俺に見せてるっていうのは、間違いを見せてるってことだから。
   それをやめてくれって話なのよ。誰か、これをたまごさんに見せていいのか検品しましたか？
   あなたじゃなくて、誰がやるんですか？」
  「ChatGPTとそれを共有して『できたよ、これですけどどうですか？』って、ChatGPTもOK出すのか見てみたい。
   それ仕組みにできるの？」

同じClaude（自分）が作って自分で丸を付けると「大丈夫じゃね？」になりがちなので、
別ベンダーのAI（xAI Grok）に、依頼文・成果物URL・本文・スクリーンショット画像の3点セットを渡し、
「これは依頼を満たしていて、たまごさん（依頼者・非エンジニア）に見せていい状態か」を判定させる。

# 使い方
    python3 tools/gaibu_kenpin.py --url <本番/確認ページURL> --what-file <依頼文.txt> \
        [--report-file <報告文.txt>] [--shot <既存スクショPNG>] [--n <番号>] [--no-shot]

  画像を渡さない場合は --no-shot を付ける（依頼文には「画像を見せる」が必須と書かれているため、
  未指定時は既定でスクリーンショットを自動取得する）。

  最後に必ず1行、次のどちらかを出す（他の道具のVERDICT行と同じ形。パースされる前提）：
    GAIBU_RESULT: OK - <一言>
    GAIBU_RESULT: NG - <理由1> ／ <理由2> ...
    GAIBU_RESULT: SKIP - <理由>   … 判定不能（APIキー無し・クレジット切れ・上限超過等）。
                                     このときは関所全体をブロックしない（他の関門に委ねる＝素通し）。
  終了コード：OK=0 / NG=1 / SKIP=2

# コスト上限（たまごさん指示：上限を決めて、超えたら止まる）
  既定は1日30回・1日100円。status/gaibu_kenpin_ledger.json に実行のたびに記録する
  （xAI usage フィールドが取れた場合は実測、取れない場合は概算と明記）。
  上限を超えたらAPIを呼ばずSKIPを返す（課金が止まる。検品そのものは他の関門に委ねる）。
"""
import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(REPO, "status", "gaibu_kenpin_ledger.json")
SHOT_TOOL = os.path.join(REPO, "tools", "gaibu_kenpin_shot.mjs")
TMP_SHOT_DIR = os.path.join(REPO, "status", "gaibu_kenpin_shots")

XAI_URL = "https://api.x.ai/v1/chat/completions"
# ★モデル名は変わりやすいので上から順に試す（最初に通ったものを使う）。
#   2026-09-17時点で実機確認済み（xAIチームにクレジットが無くHTTP 403
#   permission-deniedで弾かれたが、これは「モデル名は実在する」証拠。
#   逆に"grok-2-1212"(grokChat.server.tsの既定値)・"grok-2-vision-1212"・
#   "grok-4-vision"・"grok-vision-beta"・"grok-4-1212"はHTTP 400 Model not found
#   で実在しなかった＝旧世代のモデル名はこのアカウントでは廃止されている。
#   vision専用の別名は見つからず、"grok-4"系が入力にimage_urlを含む形で
#   マルチモーダルに対応している想定（クレジット有効化後に実際の判定で要再確認）。
MODEL_CANDIDATES = [
    "grok-4",
    "grok-4-fast",
    "grok-4-0709",
    "grok-3",
]

DEFAULT_DAILY_CALL_CAP = 30
DEFAULT_DAILY_YEN_CAP = 100.0
USD_TO_YEN = 150.0
# xAI公式の正確な単価がAPIから確認できなかった（クレジット無しで/v1/modelsが403）ため、
# 概算単価は「GPT-4o-mini vision級の相場」を仮置きし、常に note で「概算」と明記する。
ASSUMED_INPUT_USD_PER_M = 5.0
ASSUMED_OUTPUT_USD_PER_M = 15.0
ASSUMED_IMAGE_USD = 0.01


def _find_env_key(names=("XAI_API_KEY",)):
    """値そのものをログに出さず、複数の既知の.envファイルから環境変数を拾う。
    優先順位：①このプロセスの環境変数 ②tamago-shinchoku/.env ③joy-relief-station/.env.local
    ④joy-relief-station/.env （ごきげん補給所ローカルクローンに既に登録済みのキーを再利用する。
    店主に新しく値を貼らせない＝機密情報を扱う既存ルールに沿う）。"""
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
    candidates = [
        os.path.join(REPO, ".env"),
        os.path.join(REPO, ".env.local"),
        "/Users/mac/Desktop/joy-relief-station/.env.local",
        "/Users/mac/Desktop/joy-relief-station/.env",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for name in names:
                    if line.startswith(name + "="):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# コスト帳簿（上限管理・記録）
# ---------------------------------------------------------------------------

def _load_ledger():
    try:
        return json.load(io.open(LEDGER_PATH, encoding="utf-8"))
    except Exception:
        return {"records": [], "dailyCallCap": DEFAULT_DAILY_CALL_CAP,
                "dailyYenCap": DEFAULT_DAILY_YEN_CAP}


def _save_ledger(ledger):
    tmp = LEDGER_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER_PATH)


def _today_records(ledger):
    today = time.strftime("%Y-%m-%d")
    return [r for r in ledger.get("records", []) if (r.get("date") or "") == today]


def check_cost_cap(ledger=None):
    """今日の呼び出し回数・円換算額が上限を超えていないか。超えていれば (False, 理由)。"""
    ledger = ledger or _load_ledger()
    todays = _today_records(ledger)
    call_cap = ledger.get("dailyCallCap", DEFAULT_DAILY_CALL_CAP)
    yen_cap = ledger.get("dailyYenCap", DEFAULT_DAILY_YEN_CAP)
    calls = len(todays)
    yen = sum(float(r.get("costYen") or 0) for r in todays)
    if calls >= call_cap:
        return False, "本日の呼び出し回数が上限(%d回)に達しました（%d回実行済み）" % (call_cap, calls)
    if yen >= yen_cap:
        return False, "本日の費用が上限(%.0f円)に達しました（%.1f円使用済み）" % (yen_cap, yen)
    return True, "OK（本日%d回・%.1f円／上限%d回・%.0f円）" % (calls, yen, call_cap, yen_cap)


def record_cost(n, title, model, usage, verdict, note=""):
    ledger = _load_ledger()
    cost_usd = None
    if usage:
        tok_in = int(usage.get("prompt_tokens") or 0)
        tok_out = int(usage.get("completion_tokens") or 0)
        cost_usd = (tok_in / 1_000_000.0) * ASSUMED_INPUT_USD_PER_M \
            + (tok_out / 1_000_000.0) * ASSUMED_OUTPUT_USD_PER_M \
            + ASSUMED_IMAGE_USD
    else:
        cost_usd = ASSUMED_IMAGE_USD + 0.001
    cost_yen = round(cost_usd * USD_TO_YEN, 2)
    row = {
        "date": time.strftime("%Y-%m-%d"),
        "n": n,
        "title": title or "",
        "model": model or "",
        "verdict": verdict,
        "costUsd": round(cost_usd, 5),
        "costYen": cost_yen,
        "note": (note + "（xAI公式単価が未確認のため概算。usage tokensベースの推定値）").strip(),
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }
    ledger.setdefault("records", []).append(row)
    ledger.setdefault("dailyCallCap", DEFAULT_DAILY_CALL_CAP)
    ledger.setdefault("dailyYenCap", DEFAULT_DAILY_YEN_CAP)
    _save_ledger(ledger)
    return row


# ---------------------------------------------------------------------------
# スクリーンショット取得
# ---------------------------------------------------------------------------

def _find_node():
    for cand in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "node"):
        if cand == "node" or os.path.exists(cand):
            return cand
    return "node"


def take_screenshot(url, out_path=None, timeout=40):
    if not os.path.exists(TMP_SHOT_DIR):
        os.makedirs(TMP_SHOT_DIR, exist_ok=True)
    if not out_path:
        safe = re.sub(r"[^A-Za-z0-9]+", "_", url)[-60:]
        out_path = os.path.join(TMP_SHOT_DIR, "shot_%s_%d.png" % (safe, int(time.time())))
    try:
        out = subprocess.run(
            [_find_node(), SHOT_TOOL, url, out_path],
            cwd=REPO, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "スクリーンショット取得がタイムアウトしました（%d秒）" % timeout
    except Exception as e:
        return None, "スクリーンショット取得の起動に失敗しました（%s）" % e
    if out.returncode != 0 or not os.path.exists(out_path):
        return None, "スクリーンショット取得に失敗しました（%s）" % ((out.stderr or out.stdout or "")[:200])
    return out_path, "OK"


def _image_data_url(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64,%s" % b64


# ---------------------------------------------------------------------------
# Grok呼び出し
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "あなたは「ごきげん補給所／卵商店街」という日本語プロジェクトの外部検品担当AIです。"
    "依頼者（たまごさん）は非エンジニアで、専門用語や中の人向けの検査画面を見せられても判断できません。"
    "渡されたもの：①依頼文（そのまま） ②成果物のURL ③成果物の本文テキスト ④スクリーンショット画像（あれば）。"
    "判定基準：\n"
    "1. 依頼を満たしているか。\n"
    "2. たまごさん（非エンジニア・依頼者本人）にこのまま見せてよい状態か"
    "（中身が空・プレースホルダーのまま・「あ」「検査用」等の意味のない文字だけ・"
    "明らかに開発者向けの生データ画面・エラー画面ではないか）。\n"
    "OKなら日本語で「OK」とだけ答えてください。"
    "NGなら見せてはいけない理由を日本語の箇条書きで短く挙げてください。"
    "必ずJSON形式 {\"verdict\": \"OK\"または\"NG\", \"reasons\": [\"理由1\", ...]} で返してください"
    "（OKのときはreasonsは空配列でよい）。"
)


def _build_user_content(what_text, url, report_text, image_data_url=None):
    parts = [
        {"type": "text", "text": (
            "【依頼文（そのまま）】\n%s\n\n"
            "【成果物URL】\n%s\n\n"
            "【本文・報告テキスト】\n%s\n"
        ) % (what_text or "(依頼文なし)", url or "(URLなし)", (report_text or "(本文なし)")[:4000])},
    ]
    if image_data_url:
        parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
    return parts


def call_grok_judge(what_text, url, report_text, image_path=None, api_key=None):
    """戻り値: (verdict: "OK"/"NG"/None, reasons: list[str], model_used: str, usage: dict, err: str)"""
    api_key = api_key or _find_env_key()
    if not api_key:
        return None, [], "", None, "XAI_API_KEYが見つかりません（tamago-shinchoku/.env にも" \
            " joy-relief-station/.env.local にも無い）"

    image_data_url = None
    if image_path and os.path.exists(image_path):
        try:
            image_data_url = _image_data_url(image_path)
        except Exception as e:
            image_data_url = None

    body_base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_content(what_text, url, report_text, image_data_url)},
        ],
        "response_format": {"type": "json_object"},
    }

    err_list = []
    for model in MODEL_CANDIDATES:
        body = dict(body_base)
        body["model"] = model
        try:
            req = urllib.request.Request(
                XAI_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            j = json.loads(raw)
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = j.get("usage") or {}
            try:
                parsed = json.loads(content)
            except Exception:
                # JSONで返らなかった場合は本文の先頭に"OK"があるかで簡易判定
                verdict = "OK" if re.match(r"^\s*OK\b", content or "", re.IGNORECASE) else "NG"
                parsed = {"verdict": verdict, "reasons": [] if verdict == "OK" else [content[:200]]}
            verdict = (parsed.get("verdict") or "").upper()
            if verdict not in ("OK", "NG"):
                verdict = "NG"
                parsed.setdefault("reasons", ["Grokの応答形式が不明でした：%s" % content[:200]])
            return verdict, parsed.get("reasons") or [], model, usage, ""
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            err_list.append("%s: HTTP %s %s" % (model, e.code, err_body[:150]))
            continue
        except Exception as e:
            err_list.append("%s: %s" % (model, e))
            continue
    return None, [], "", None, "全モデル候補で呼び出しに失敗しました（%s）" % " / ".join(err_list)


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------

def judge(n=None, url=None, what_text="", report_text="", title="", shot_path=None,
          no_shot=False):
    """戻り値: (verdict: "OK"/"NG"/"SKIP", reasons: list[str], detail: dict)"""
    detail = {}
    ok_cap, cap_reason = check_cost_cap()
    detail["cost_cap"] = cap_reason
    if not ok_cap:
        return "SKIP", [], detail

    own_shot = False
    if not shot_path and not no_shot and url:
        shot_path, shot_reason = take_screenshot(url)
        detail["screenshot"] = shot_reason
        own_shot = True
    elif shot_path:
        detail["screenshot"] = "指定済み：%s" % shot_path

    verdict, reasons, model, usage, err = call_grok_judge(
        what_text, url, report_text, image_path=shot_path)
    detail["model"] = model
    detail["usage"] = usage
    if verdict is None:
        detail["error"] = err
        return "SKIP", [err], detail

    row = record_cost(n, title, model, usage, verdict,
                       note="画像%sで判定" % ("あり" if shot_path else "なし"))
    detail["ledger"] = row

    if own_shot and shot_path and os.path.exists(shot_path):
        # 一時スクショは帳簿に残した後は消してよい（証拠として渡したURLではなく判定用の使い捨て）
        try:
            os.remove(shot_path)
        except Exception:
            pass

    return verdict, reasons, detail


def check_gaibu_kenpin_for_url(url, what_text="", report_text="", n=None, title=""):
    """sekisho.py から呼ぶ軽量エントリポイント。
    戻り値: (ok: bool, reason: str) … ok=Trueは「OK」または「SKIP」（ブロックしない）。"""
    verdict, reasons, detail = judge(n=n, url=url, what_text=what_text,
                                      report_text=report_text, title=title)
    if verdict == "OK":
        return True, "外部AI(Grok)検品OK"
    if verdict == "SKIP":
        return True, "外部AI(Grok)検品はスキップしました（%s）" % (reasons[0] if reasons else detail.get("error", ""))
    return False, "外部AI(Grok)がNGと判定しました：%s" % " ／ ".join(reasons or ["(理由なし)"])


def main():
    ap = argparse.ArgumentParser(description="917番：外部AI(Grok)検品 — たまごさんに見せていいかの判定")
    ap.add_argument("--n", default=None)
    ap.add_argument("--url", default=None, help="成果物URL（確認ページ・本番のどちらでもよい）")
    ap.add_argument("--title", default="")
    ap.add_argument("--what-file", default=None)
    ap.add_argument("--what", default="")
    ap.add_argument("--report-file", default=None)
    ap.add_argument("--report", default="")
    ap.add_argument("--shot", default=None, help="既存のスクショPNGを使う場合のパス")
    ap.add_argument("--no-shot", action="store_true", help="画像を渡さずテキストのみで判定する")
    args = ap.parse_args()

    what_text = args.what
    if args.what_file and os.path.exists(args.what_file):
        what_text = io.open(args.what_file, encoding="utf-8", errors="ignore").read()
    report_text = args.report
    if args.report_file and os.path.exists(args.report_file):
        report_text = io.open(args.report_file, encoding="utf-8", errors="ignore").read()

    verdict, reasons, detail = judge(
        n=args.n, url=args.url, what_text=what_text, report_text=report_text,
        title=args.title, shot_path=args.shot, no_shot=args.no_shot,
    )
    print(json.dumps(detail, ensure_ascii=False, indent=1, default=str))
    if verdict == "OK":
        print("GAIBU_RESULT: OK - たまごさんに見せてよいと判定されました")
        sys.exit(0)
    elif verdict == "SKIP":
        print("GAIBU_RESULT: SKIP - %s" % (reasons[0] if reasons else detail.get("error", "判定不能")))
        sys.exit(2)
    else:
        print("GAIBU_RESULT: NG - %s" % " ／ ".join(reasons or ["(理由なし)"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
