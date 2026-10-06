#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/estimate_gemini_savings.py

「Geminiへ委譲できそうな大きい読み込みが、実際にどれくらいの頻度で発生しているか」を
既存の実行ログから概算する（案件：仕組み⑫Geminiを繋ぐ、2026-09-17）。

【正直な前提・当初案からの変更点】
依頼時の想定は `status/auto-launch-*.log`（762件）だったが、実際に開いて確認したところ、
このログは①起動時の宣言行と、②終了時のJSON要約（`permission_denials`＝却下されたBash/Edit等の
コマンドのみ）しか持っておらず、**成功したReadツール呼び出しの記録が一切含まれていない**
（Readは許可プロンプトが要らないため却下履歴にも残らない）ことを実測で確認した。

そのため、同じセッション群の実体である `~/.claude/projects/-Users-mac-Desktop-tamago-shinchoku/*.jsonl`
（Claude Codeが各セッションの全tool_use/tool_resultをそのまま保存している生トランスクリプト）を
直接サンプルする方式に切り替えた。ここには実際のReadツール呼び出しと、その結果本文（`cat -n`形式）が
そのまま残っているため、「350行を超える読み込みが何回発生したか」を実測できる。

正確なトークン数までは求めず、あくまで「大きい読み込みの発生頻度」の概算。
"""

import glob
import json
import os
import sys

PROJECT_DIR = os.path.expanduser(
    "~/.claude/projects/-Users-mac-Desktop-tamago-shinchoku"
)
SAMPLE_SIZE = 40  # 直近40セッションぶんを見る（依頼の「30〜50件程度」の範囲内）
LARGE_LINE_THRESHOLD = 350  # 依頼にある「350行未満は委譲に向かない」の閾値をそのまま流用


def load_jsonl(path):
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # セッション途中で切れた最終行など、壊れた行はスキップ
                continue


def result_text(content):
    """tool_resultのcontentを文字列化する（文字列 or list[dict(type=text)] の両対応）"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def main():
    files = sorted(
        glob.glob(os.path.join(PROJECT_DIR, "*.jsonl")), key=os.path.getmtime, reverse=True
    )
    sample = files[:SAMPLE_SIZE]

    if not sample:
        print(f"[estimate_gemini_savings] 対象セッションログが見つかりません: {PROJECT_DIR}", file=sys.stderr)
        sys.exit(1)

    total_read_calls = 0
    large_read_calls = 0
    sessions_with_reads = 0
    large_by_path = {}

    for path in sample:
        read_ids = {}  # tool_use_id -> file_path
        session_had_read = False

        for obj in load_jsonl(path):
            t = obj.get("type")
            if t == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and block.get("name") == "Read"
                        ):
                            read_ids[block.get("id")] = block.get("input", {}).get(
                                "file_path", "(不明)"
                            )
                            session_had_read = True
            elif t == "user":
                msg = obj.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tuid = block.get("tool_use_id")
                            if tuid in read_ids:
                                text = result_text(block.get("content"))
                                lines = text.count("\n") + (1 if text else 0)
                                total_read_calls += 1
                                if lines >= LARGE_LINE_THRESHOLD:
                                    large_read_calls += 1
                                    p = read_ids[tuid]
                                    large_by_path[p] = large_by_path.get(p, 0) + 1

        if session_had_read:
            sessions_with_reads += 1

    print(f"サンプルしたセッション数: {len(sample)}（{PROJECT_DIR}）")
    print(f"Readツール呼び出しの総数（結果を確認できたもの）: {total_read_calls}")
    print(f"うち{LARGE_LINE_THRESHOLD}行以上の大きい読み込み: {large_read_calls}")
    if total_read_calls:
        pct = large_read_calls / total_read_calls * 100
        print(f"大きい読み込みの割合: {pct:.1f}%")
    print(f"Read呼び出しが1回以上あったセッション数: {sessions_with_reads} / {len(sample)}")

    if large_by_path:
        print("\n大きい読み込みが多かったファイル（上位10件）:")
        ranked = sorted(large_by_path.items(), key=lambda kv: kv[1], reverse=True)[:10]
        for p, n in ranked:
            print(f"  {n:3d}回  {p}")


if __name__ == "__main__":
    main()
