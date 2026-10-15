#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/1719_sakujo_ichiran.py ── 削除とゴミ箱：必ず何を消すか見せて確認する係（1719番）。

たまごさんの言葉（2026-09-10 08:50の事故を受けて）：
  「削除は絶対に俺に確認だよ。」

━━ 何が問題だったか ━━
  disk_guardian.py はすでに「壺と金庫（写真・Vault・Drive実体・Eagle等）には
  最初からパスのキーワードで触れない」「ほこりと落ち葉（アプリキャッシュ・
  __pycache__・古いログ等＝TIDY_KINDS）だけは黙って毎回掃く」という2段構えの
  安全策を持っている。

  ただし ~/.Trash 直下（たまごさんが Finder で「削除」を選んだ後の最終置き場＝
  trash_old）は、意図的に TIDY_KINDS に入れていない＝自動では1バイトも消さない。
  一方で「7日以上ゴミ箱にある」という候補データ(status/disk_candidates.json)は
  作られていたが、それを**人が見るための一覧**がどこにも無かった。
  「1週間経っても未着手」の実体はここ＝**見せる場所が無かった**こと。

━━ ここで作るもの ━━
  disk_candidates.json（disk_guardian.pyが継続更新）から、
    ① ゴミ箱で7日以上経過し「消していいか確認待ち」の項目（trash_old）
    ② 機械の落とし物（3日待って自動で片づく trash_auto。worktree_reaperの
       バックアップ等）の件数・合計サイズ
    ③ 壺と金庫として保護され今回は1件も触っていないことが分かる件数
  を集計し、確認ページが読み込める形で status/public/1719_sakujo_ichiran.json
  に保存するだけ（★ここでは何も消さない。消すのは従来どおり別経路・人の確認後）。

使い方
    python3 tools/1719_sakujo_ichiran.py            # 集計してJSONを書き出す
    python3 tools/1719_sakujo_ichiran.py --show      # 集計結果を画面にも出す
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
CANDIDATES_JSON = os.path.join(ST, "disk_candidates.json")
OUT_JSON = os.path.join(ST, "public", "1719_sakujo_ichiran.json")

# disk_guardian.py の TIDY_KINDS と同じ定義（黙って掃いてよいもの＝機械の落とし物）。
# trash_old はここに含まれない＝自動では消さない、が本実装の核。
JIDOU_SOUJI_KINDS = (
    "app_cache", "__pycache__", "old_log", "queue_history_old",
    "claude_session_old", "claude_session_attachments",
    "trash_auto", "claude_vm_old",
)


def load_json(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    data = load_json(CANDIDATES_JSON, None)
    if data is None:
        print("disk_candidates.json が読めない（disk_guardian.py が未実行）", file=sys.stderr)
        return 1

    cs = data.get("candidates", [])
    trash_old = [c for c in cs if c.get("kind") == "trash_old"]
    trash_auto = [c for c in cs if c.get("kind") == "trash_auto"]
    protected = [c for c in cs if c.get("protected")]
    jidou = [c for c in cs if c.get("kind") in JIDOU_SOUJI_KINDS]

    def mb(lst):
        return round(sum(c.get("size_mb", 0) for c in lst), 1)

    # 見せる一覧はサイズが大きい順・最大30件まで（確認ページが長くなりすぎないため）
    trash_old_sorted = sorted(trash_old, key=lambda c: -c.get("size_mb", 0))[:30]
    for c in trash_old_sorted:
        try:
            c["days_in_trash"] = round(
                (time.time() - os.path.getmtime(c["path"])) / 86400, 1
            )
        except Exception:
            c["days_in_trash"] = None

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_measured_at": data.get("measured_at"),
        "kakunin_machi": {
            "kensu": len(trash_old),
            "goukei_mb": mb(trash_old),
            "settumei": "ゴミ箱(~/.Trash)直下で7日以上経過。自動では消さない。"
                        "消すにはたまごさんの名指し確認が要る。",
            "ichiran": trash_old_sorted,
        },
        "jidou_souji": {
            "kensu": len(jidou),
            "goukei_mb": mb(jidou),
            "uchi_trash_auto_kensu": len(trash_auto),
            "uchi_trash_auto_mb": mb(trash_auto),
            "settumei": "機械の落とし物(アプリキャッシュ・__pycache__・古いログ・"
                        "worktree_reaperのバックアップ等)。期限が来たら黙って掃く対象。",
        },
        "tsubo_to_kinko": {
            "kensu_hogo_sumi": len(protected),
            "settumei": "候補の時点でprotected=trueと判定され今回は触っていない件数。"
                        "写真・Vault・Google Drive実体・Eagle・dmg等はパスの時点で"
                        "候補リストにすら入らない(is_forbiddenで除外済み・disk_guardian.py)。",
        },
        "zentai_kouho_kensu": len(cs),
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_JSON)

    if "--show" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(
            "確認待ち(ゴミ箱7日超) %d件 %.1fMB / 自動掃除対象 %d件 %.1fMB / "
            "壺と金庫として保護済み %d件"
            % (
                out["kakunin_machi"]["kensu"],
                out["kakunin_machi"]["goukei_mb"],
                out["jidou_souji"]["kensu"],
                out["jidou_souji"]["goukei_mb"],
                out["tsubo_to_kinko"]["kensu_hogo_sumi"],
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
