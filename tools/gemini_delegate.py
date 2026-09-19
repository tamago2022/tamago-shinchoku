#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/gemini_delegate.py

「重い調べ物・要約はGemini（安いモデル）へ、判断はClaudeが持つ」を実装する委譲CLI。
下敷きはSpotify社のPortal/shunt方式（PreToolUseフックで大きい読み込みを検知し、
安いワーカーモデルへ委譲する。2026-09-03公開・Javaモノレポでbulk-read平均90%削減の実測あり）。

【この道具が向いている用途】
  - 複数ファイルの中身から質問に答える要約（bulk-read）
  - 1つの大きいファイル・ログの要約（summarize）

【この道具を絶対に使わない用途】
  - コードの編集・デバッグ
  - 設計判断・アーキテクチャの意思決定
  - 安全性が絡む推論（例：スレッド安全性・削除してよいか・公開してよいか）
    Spotifyの実測でも、ワーカーモデルはスレッド安全性バグを見逃した。
    「調べて要約する」以上の仕事はここに投げない。判断は常にClaude側が持つ。

【小さいファイルには向かない】
  委譲1回あたり10〜30秒のレイテンシが乗る。350行未満のような小さい読み込みは、
  素直にReadツールで直接読む方が速い（このツール自体は行数チェックをしないので、
  呼び出す側＝Claude Codeのフック等が「大きい時だけ」呼ぶ判断をすること）。

使い方:
  python3 tools/gemini_delegate.py bulk-read --question "認証まわりの実装は？" --paths a.py b.py
  python3 tools/gemini_delegate.py summarize --path huge.log --question "エラーの傾向を教えて"

環境変数:
  GEMINI_API_KEY  必須。.env に `GEMINI_API_KEY=<Google AI Studioで取得した値>` という行を
                  追記してください。値そのものはこのツールのどの出力にも表示されない。
  GEMINI_MODEL    任意。デフォルトは gemini-2.5-flash。
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error


SYSTEM_INSTRUCTION = (
    "あなたは正確なコード分析者です。"
    "回答は簡潔で構造化された箇条書きのみで行ってください。"
    "挨拶・前置き・言い訳・Markdownの過剰な装飾（大量の見出しや太字）は禁止です。"
    "分からない箇所は推測で埋めず「不明」と書いてください。"
)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def load_dotenv_if_present(repo_root):
    """.env に GEMINI_API_KEY 等があれば環境変数へ読み込む（値はどこにも出力しない）"""
    env_path = os.path.join(repo_root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip()
    except OSError:
        pass


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key or None


def fail_no_key():
    print(
        "[gemini_delegate] GEMINI_API_KEYが設定されていません。\n"
        "  .envに `GEMINI_API_KEY=<Google AI Studioで取得した値>` という行を追記してください。\n"
        "  （このツールはキーが入ればすぐ動く設計です。キーの値そのものはこのツールでは扱いません）",
        file=sys.stderr,
    )
    sys.exit(1)


def read_file_or_die(path):
    if not os.path.isfile(path):
        print(f"[gemini_delegate] ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"[gemini_delegate] ファイルを読めません: {path} ({e})", file=sys.stderr)
        sys.exit(1)


def extract_text(body):
    try:
        candidates = body.get("candidates", [])
        if not candidates:
            feedback = body.get("promptFeedback", {})
            raise ValueError(f"候補が空でした。promptFeedback={feedback}")
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [p.get("text", "") for p in parts if "text" in p]
        return "\n".join(texts).strip()
    except (AttributeError, KeyError, ValueError) as e:
        print(
            f"[gemini_delegate] 応答の解析に失敗しました: {e} / body={json.dumps(body, ensure_ascii=False)[:500]}",
            file=sys.stderr,
        )
        sys.exit(1)


def call_gemini(prompt, model, api_key, max_retries=3):
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    data = json.dumps(payload).encode("utf-8")

    delay = 2.0
    last_error = None
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return extract_text(body)
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {body_text[:300]}"
            if e.code in (429, 503) and attempt < max_retries:
                print(
                    f"[gemini_delegate] {e.code}を受信、{delay:.0f}秒待って再試行 "
                    f"({attempt}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay *= 2
                continue
            break
        except urllib.error.URLError as e:
            last_error = str(e.reason)
            if attempt < max_retries:
                print(
                    f"[gemini_delegate] 通信エラー、{delay:.0f}秒待って再試行 "
                    f"({attempt}/{max_retries}): {last_error}",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay *= 2
                continue
            break
        except (json.JSONDecodeError, ValueError) as e:
            # 応答がJSONとして壊れている等。APIキーを含むurl/reqは出力しない。
            last_error = f"応答の解析に失敗: {e}"
            if attempt < max_retries:
                print(
                    f"[gemini_delegate] {last_error}、{delay:.0f}秒待って再試行 "
                    f"({attempt}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay *= 2
                continue
            break

    print(f"[gemini_delegate] Gemini呼び出しに失敗しました: {last_error}", file=sys.stderr)
    sys.exit(1)


def report_delegation(elapsed, total_chars, answer, model):
    print(
        f"[gemini_delegate] 委譲完了: {elapsed:.1f}秒 / 入力約{total_chars:,}文字"
        f" / 出力約{len(answer):,}文字 / モデル={model}",
        file=sys.stderr,
    )


def cmd_bulk_read(args, api_key):
    blocks = []
    total_chars = 0
    for path in args.paths:
        content = read_file_or_die(path)
        total_chars += len(content)
        blocks.append(f'<file path="{path}">\n{content}\n</file>')
    prompt = (
        f"以下は{len(args.paths)}個のファイルの中身です。\n\n"
        + "\n\n".join(blocks)
        + f"\n\n質問: {args.question}\n"
        "箇条書きだけで、日本語で答えてください。"
    )

    start = time.time()
    answer = call_gemini(prompt, args.model, api_key)
    elapsed = time.time() - start

    report_delegation(elapsed, total_chars, answer, args.model)
    print(answer)


def cmd_summarize(args, api_key):
    content = read_file_or_die(args.path)
    total_chars = len(content)
    prompt = (
        f'以下は{args.path}の中身です。\n\n<file path="{args.path}">\n{content}\n</file>\n\n'
        f"質問: {args.question}\n"
        "箇条書きだけで、日本語で答えてください。"
    )

    start = time.time()
    answer = call_gemini(prompt, args.model, api_key)
    elapsed = time.time() - start

    report_delegation(elapsed, total_chars, answer, args.model)
    print(answer)


def build_parser():
    parser = argparse.ArgumentParser(
        description="重い調べ物・要約をGemini 2.5 Flashへ委譲するCLI（判断・編集には使わない）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_bulk = sub.add_parser("bulk-read", help="複数ファイルへの質問をまとめて委譲する")
    p_bulk.add_argument("--question", required=True)
    p_bulk.add_argument("--paths", nargs="+", required=True)
    p_bulk.set_defaults(func=cmd_bulk_read)

    p_sum = sub.add_parser("summarize", help="1つの大きいファイル・ログを要約する")
    p_sum.add_argument("--path", required=True)
    p_sum.add_argument("--question", default="日本語で要点を箇条書きにして")
    p_sum.set_defaults(func=cmd_summarize)

    return parser


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv_if_present(repo_root)

    parser = build_parser()
    args = parser.parse_args()
    args.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    api_key = get_api_key()
    if not api_key:
        fail_no_key()

    args.func(args, api_key)


if __name__ == "__main__":
    main()
