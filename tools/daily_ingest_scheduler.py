#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
756番：毎朝の入荷見回りを仕組みにする（707番の自動化）。

たまごさんの指摘（2026-09-11）：
「707番（入荷見回り）はこれまで手作業で2回やっただけで、毎日自動で走る仕組みになっていない。
お任せできるのかな？」

ここで、707番が手でやっていた「今日入れたものを見回って、中身と違う題名・コピーを直す」を
毎朝1回、自動で発車待ちへ積む仕組みにする。新しいlaunchd常駐は作らず、既存の心臓
（heartbeat.sh・15秒おき）に相乗りし、実際に積むのは1日1回だけに間引く
（tools/check_anthropic_reply.py と同じ「間引き」パターンをそのまま踏襲）。

積む先＝status/queue.json（command_ingest.queue_add 経由）。積んだタスクを実際に着火する
セッションが、joy-relief-station の admin_stock テーブル（created_at が入荷日時）から
前日分を見回り、①文字とビジュアルの不一致（ヤギの件）②文字だけの不一致③おすすめ導線の不一致
を検出・修正し、確認ページ（share/check/daily-ingest.html）を毎朝上書き生成する。

二重投入防止：
  ① status/.daily_ingest_last_queued に最後に積んだ日付(JST)を記録し、今日と一致すればスキップ
     （心臓が15秒おきに呼んでも、実際にqueue_addへ進むのは1日1回だけ）。
  ② タイトルに対象日付を含める。command_ingest.queue_add() 側の重複チェックは
     タイトルの完全一致／片方が片方を含む／先頭30文字一致で見ているため、日付が違う限り
     「前と同じ内容だから積まない」に誤って弾かれることはない。
"""
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import command_ingest  # noqa: E402

ROOT = os.path.dirname(HERE)
MARKER = os.path.join(ROOT, "status", ".daily_ingest_last_queued")
JST = timezone(timedelta(hours=9))


def already_queued_today(today_str):
    if not os.path.exists(MARKER):
        return False
    try:
        with open(MARKER, encoding="utf-8") as f:
            return f.read().strip() == today_str
    except Exception:
        return False


def mark_queued(today_str):
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(today_str)


def build_what(target_date_str):
    return (
        "756番の仕組みで毎朝自動投入されたタスク（707番の自動化）。\n\n"
        "★重要：既存パイプラインが joy-relief-station の origin/main に既にある。ゼロから新しい"
        "スクリプトを書かない（車輪の再発明で1回失敗済み）。着手前に必ず origin/main 起点の新しい"
        "worktree（.claude/worktrees/配下）を作ること。既存の作業ディレクトリが1000コミット以上"
        "古い可能性があるので、git fetch origin main → 差分コミット数を確認してから始める。\n\n"
        "既存パイプライン（この3本＋workflowで完結している）：\n"
        "・scripts/patrol/check-today-ingest-copy.mjs … 毎日JST0:10のcronで直近24時間の admin_stock"
        "（youtube/x, created_at基準）を集め scripts/patrol/reports/today-ingest-copy-latest.json へ"
        "レポート化（既に自動実行されている。無ければ手で1回実行してよい）。\n"
        "・scripts/patrol/templateGuard.mjs … テンプレ文（「二人の人物が」「〜する様子」等）を検出する"
        "文字列判定。ヤギの件の再発防止として既存。ただしテキストだけなので②は検出できない。\n"
        "・scripts/patrol/reports/ingest-copy-fixes-pending.json … 判定結果を書く場所（配列。既存行は"
        "消さず末尾に追記。形式は既存の行を1つ読んで真似ること：id/expectedCurrentTitle(今のtitleそのまま)"
        "/title(新題名)/whisper(新コピー)/reviewedBy/reviewedAt）。\n"
        "・scripts/patrol/apply-ingest-copy-fixes-once.mjs … pending.jsonを読み、現在DBのtitleが"
        "expectedCurrentTitleと完全一致する時だけ admin_stock を実際にUPDATEする（service_role経由）。\n"
        "・.github/workflows/tamago-daily-ingest-copy-check.yml … pending.jsonがmainへpushされると"
        "自動でapply-fixesジョブが起動しUPDATEを実行する設計。\n\n"
        "対象：%s（前日）に admin_stock へ新規登録された動画・投稿全部。0件の日は0件と書いて終わる。\n\n"
        "見つけるもの（3種類。ここが本体）：\n"
        "① 文字と中身が違う（従来型）：題名・コピーの言葉と実際の映像がずれている。\n"
        "② ★ビジュアルが違う（ヤギの件・ここが今まで抜けていた）：題名・コピーの言葉自体は合っているのに、"
        "サムネイル画像が題名の内容と別物に見える（実例：猫の動画のはずがヤギの絵ばかり出る）。"
        "today-ingest-copy-latest.json の thumbnailUrl を実際にダウンロードしてReadツールで見て、"
        "文字だけ読んで判定せず、言葉と絵が一致するか判定すること。\n"
        "③ おすすめが変：関連導線の文脈が飛んでいる（憲法「おすすめは横にずれる、ジャンプしない」）。\n\n"
        "見つけたら店主に聞かず自分で直す。コピーは水道水にしない（「代表曲のひとつ」等のテンプレ禁止）。"
        "動画を見てから書く。pending.jsonへ追記してmainへpushする（★admin_stockのUPDATEはDBデータの"
        "反映でありLovableのコードデプロイとは無関係。Lovableの「公開」は不要。pushして数分待ってから"
        "daily-review.mjs的な再取得でDBの値が実際に変わったか必ず確認する）。\n\n"
        "★過去に一度、pending.jsonをpushしてもapply-fixesジョブが成功実行された痕跡"
        "（scripts/patrol/reports/ingest-copy-fixes-applied-latest.json）が無いことがあった。"
        "毎回、push後にこのファイルが更新されたか・DBの値が実際に変わったかを確認すること。"
        "変わっていなければGitHub ActionsのSecrets(SUPABASE_SERVICE_ROLE_KEY)未設定の疑いがあるので、"
        ".claude/PENDING_DECISIONS.mdへ1行書いて店主確認を仰ぐ（作業は止めず次の一手も書く）。\n\n"
        "最後に、固定URL share/check/daily-ingest.html （tools/make_check_page.py で生成。過去日付分は"
        "share/check/daily-ingest-%s.html のように別ファイルで残し、一度渡したURLは404にしない）へ、"
        "直したもの／そのままでよかったもの／直せなかったもの、をサムネイル・前後比較付きで1枚にまとめて"
        "上書き公開する。判断がつかなかったものだけ「直せなかったもの」に出す。それ以外は自分で直す。"
    ) % (target_date_str, target_date_str)


def main():
    now = datetime.now(JST)
    today_str = now.strftime("%Y-%m-%d")
    if already_queued_today(today_str):
        return 0
    target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    label = "毎朝の入荷見回り（%s分・自動）" % target_date
    what = build_what(target_date)
    with command_ingest.queue_lock():
        status, msg = command_ingest.queue_add(what, priority=3, label=label, origin="factory")
    # 重複でスキップされた場合も「今日はもう試みた」としてマーカーは進める
    # （同日に何度も重複エラーを出し続けないため）。
    mark_queued(today_str)
    print("%s %s" % (status, msg))
    return 0 if status in ("done", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
