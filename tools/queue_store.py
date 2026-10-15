#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
status/queue.json への読み書きを1箇所に集約する（案件#687・2026-09-13新設）。

■ 起きた事故（実測）
  777〜804番の28件が queue.json から消えた。原因は2つが重なったこと。
  ① `tools/command_ingest.py` の `queue_add()` 等は、`process()` 経由で呼ばれた時だけ
     `with queue_lock():` の中に入るが、`tools/relay_server.py`・`daily_ingest_scheduler.py`・
     `kenpou_check.py`・`auto_launcher.py` は `command_ingest.queue_add()` を**直接**呼んでおり、
     この経路には鍵が一切かかっていなかった。
  ② `tools/auto_launcher.py` の `save_queue(q)` は、鍵を持ったまま長時間（git worktree作成・
     claude -p 起動）保持していた `q`（読み込んだ時点のスナップショット）を**丸ごと**書き戻す
     実装だった。①の無鍵の書き込みが割り込むと、②が最後に書き戻した瞬間に①の追加分ごと消える。

■ ここでの直し方（4点）
  1. 鍵（queue_lock）を再入可能にし、`save_queue()` 自身が鍵を取る。
     → 呼び出し元が鍵を取っていてもいなくても、内部の読み書きは必ず保護される。
  2. `save_queue()` は「丸ごと上書き」をやめ、**差分マージ書き込み**にする。
     書く直前にディスクの最新を読み直し、自分が実際に触った項目だけを重ね書きする。
     自分が触っていない項目・自分の読み込み後に他プロセスが足した項目は絶対に消さない。
  3. 件数が減る書き込みは拒否する。書かずに `status/queue_write_blocked.jsonl` へ理由を記録して中止する。
  4. 書き込みのたびに世代バックアップ（`status/queue_history/queue-YYYYMMDD-HHMMSS-ffffff.json`）
     を残す。直近50世代だけ保持し、それより古いものは削除する。
"""
import copy
import fcntl
import io
import json
import os
import sys
import threading
import time
from contextlib import contextmanager

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(REPO, "status", "queue.json")
QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")
BLOCKED_LOG = os.path.join(REPO, "status", "queue_write_blocked.jsonl")
HISTORY_DIR = os.path.join(REPO, "status", "queue_history")
HISTORY_KEEP = 50
# 2026-09-13 18:55事故（271件→0件）を受けて追加：この件数を下回ったら壊れているとみなす。
# 通常運用では常に100件以上あるので、10件は絶対に安全な閾値（誤検知しない）。
MIN_HEALTHY_ITEMS = 10


# ---- 鍵：再入可能にする ----
# 同一プロセス内で `with queue_lock():` の中からさらに `save_queue()` が
# `with queue_lock():` を呼んでも、二重に flock してデッドロックしないようにする。
# （flockはファイルディスクリプタ単位なので、同じプロセスでも別fdで取ろうとすると
#   自分自身の鍵待ちで固まる＝自己デッドロックする。ここで深さを数えて2回目以降は素通りする）
_local = threading.local()


@contextmanager
def queue_lock(timeout=180.0):
    depth = getattr(_local, "depth", 0)
    if depth > 0:
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth = depth
        return

    f = io.open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                f.close()
                raise RuntimeError("queue_lock timeout")
            time.sleep(0.05)
    _local.depth = 1
    try:
        yield
    finally:
        _local.depth = 0
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def _caller_identity():
    """誰が(どのpid・どのコマンドライン)書こうとしたかを、queue_write_blocked.jsonlへ残すため。"""
    try:
        return {"pid": os.getpid(), "argv": sys.argv}
    except Exception:
        return {"pid": None, "argv": None}


def _latest_healthy_backup(min_items=MIN_HEALTHY_ITEMS):
    """queue_history/の中から、直近でmin_items件以上ある世代を新しい順に探す。"""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        files = sorted(
            (p for p in os.listdir(HISTORY_DIR) if p.startswith("queue-") and p.endswith(".json")),
            reverse=True,
        )
    except Exception:
        files = []
    for fn in files:
        path = os.path.join(HISTORY_DIR, fn)
        try:
            backup = json.load(io.open(path, encoding="utf-8"))
        except Exception:
            continue
        if len(backup.get("items") or []) >= min_items:
            return fn, backup
    return None, None


def _self_heal_if_corrupted(raw_text, q):
    """queue.jsonが壊れて(件数が極端に少なく)いたら、直近の健全な世代バックアップから
    自動で戻す。人を呼ばない（案件#687・2026-09-13 18:55の271件→0件事故で追加）。

    save_queue()を経由しない直接書き込み（tools/verify_check_pages.py等・想定していない
    書き込み経路）から壊れた場合でも、load_queue()を呼んだ**どのプロセスからでも**
    この時点で気づいて自動修復できるようにする（書き込み側だけを塞ぐより裾野が広い安全弁）。
    """
    count = len(q.get("items") or [])
    if count >= MIN_HEALTHY_ITEMS:
        return q
    fn, backup = _latest_healthy_backup()
    if backup is None:
        return q  # 直せる材料が無い。壊れたまま返す（これ以上悪化はさせない）
    try:
        broken_path = os.path.join(
            REPO, "status", "queue.json.EMPTY-%s" % time.strftime("%Y%m%d-%H%M%S"))
        with io.open(broken_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
    except Exception:
        pass
    tmp = QUEUE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE)
    try:
        who = _caller_identity()
        with io.open(os.path.join(REPO, "status", "queue_self_heal.log"), "a", encoding="utf-8") as f:
            f.write("%s 🚑 自己修復: queue.jsonが%d件に壊れていた（読んだのはpid=%s %s）→ %s(%d件)から自動復元\n"
                     % (time.strftime("%Y-%m-%d %H:%M:%S"), count, who.get("pid"), who.get("argv"),
                        fn, len(backup.get("items") or [])))
    except Exception:
        pass
    return backup


def load_queue():
    """queue.jsonを読む（鍵は取らない＝素早い先読み・二重発車チェック用にはこちらを使う）。
    件数が壊れるほど少ない（MIN_HEALTHY_ITEMS未満）場合は、読んだこのタイミングで
    直近の健全な世代バックアップから自動修復してから返す。"""
    try:
        with io.open(QUEUE, encoding="utf-8") as f:
            raw = f.read()
        q = json.loads(raw) if raw.strip() else {"items": []}
    except Exception:
        return {"items": []}
    if len(q.get("items") or []) < MIN_HEALTHY_ITEMS:
        q = _self_heal_if_corrupted(raw, q)
    return q


def snapshot_items(q):
    """save_queue()に渡す「自分がロードした時点の中身」。項目ごとの変更検出に使う。"""
    return {it.get("n"): copy.deepcopy(it) for it in (q.get("items") or []) if it.get("n") is not None}


def _write_history_backup(disk_q):
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S") + "-%06d" % (int(time.time() * 1e6) % 1000000)
        path = os.path.join(HISTORY_DIR, "queue-%s.json" % stamp)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(disk_q, f, ensure_ascii=False, indent=1)
        # 直近50世代だけ残す
        files = sorted(
            (p for p in os.listdir(HISTORY_DIR) if p.startswith("queue-") and p.endswith(".json")),
        )
        excess = len(files) - HISTORY_KEEP
        for old in files[:max(0, excess)]:
            try:
                os.remove(os.path.join(HISTORY_DIR, old))
            except Exception:
                pass
    except Exception as e:
        try:
            with io.open(os.path.join(REPO, "status", "queue_history_errors.log"), "a", encoding="utf-8") as f:
                f.write("%s 世代バックアップ失敗: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), e))
        except Exception:
            pass


def _log_blocked(disk_items, mine_items, merged_items, reason):
    try:
        who = _caller_identity()
        os.makedirs(os.path.dirname(BLOCKED_LOG), exist_ok=True)
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "reason": reason,
            "pid": who.get("pid"),
            "argv": who.get("argv"),
            "disk_count": len(disk_items),
            "mine_count": len(mine_items),
            "merged_count": len(merged_items),
            "disk_ns": sorted([n for n in disk_items if n is not None]),
            "mine_ns": sorted([n for n in mine_items if n is not None]),
            "missing_ns": sorted([n for n in disk_items if n not in merged_items]),
        }
        with io.open(BLOCKED_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def save_queue(q, snapshot=None, deleted_ns=None):
    """安全な書き込み（差分マージ）。

    - `snapshot` は `snapshot_items()` で取った「自分がロードした時点の中身」。
      渡さなかった場合は「自分が持っている項目は全部自分が変更した」とみなす
      （＝以前の丸ごと上書きに近い挙動になるので、なるべく渡すこと）。
    - `deleted_ns` は「自分が今回**意図的に**消した項目番号」のリスト（queue_delete・
      queue_dedupe・harvestの重複整理など）。ここに挙げた番号だけは、ディスクにあっても
      消してよい。**ここに挙げていない番号は、たとえ自分の手元の items から消えていても
      絶対に復活させて残す**（＝「なんとなく items から漏れていた」を削除と誤認しない）。
    - ディスクの最新を読み直し、
        ・自分が触っていない／ディスクにしか無い項目 → ディスク側を採用（消さない）
        ・自分が実際に変更した項目 → 自分の版を採用
        ・deleted_ns に挙げた項目 → 消す
      で合成する。
    - 合成後、`deleted_ns` で説明の付かない項目の消失（＝事故）が1件でもあれば
      **書かずに中止**し、理由を `status/queue_write_blocked.jsonl` に記録する。
    - 書く前に世代バックアップを `status/queue_history/` へ残す（直近50世代）。

    戻り値: 実際に書いたら True、説明の付かない件数減少で拒否したら False。
    """
    deleted_ns = set(deleted_ns or [])
    with queue_lock():
        disk = load_queue()
        disk_items = {it.get("n"): it for it in (disk.get("items") or []) if it.get("n") is not None}
        mine_items = {it.get("n"): it for it in (q.get("items") or []) if it.get("n") is not None}

        merged = dict(disk_items)
        for n, it in mine_items.items():
            orig = snapshot.get(n) if snapshot is not None else None
            changed = (snapshot is None) or (orig != it) or (n not in disk_items)
            if changed:
                merged[n] = it
        for n in deleted_ns:
            merged.pop(n, None)

        # 説明の付かない消失（＝事故）が無いかを確認する。
        # 上のロジック上、mergedはdisk_itemsから出発してdeleted_nsの分だけ間引く構造なので、
        # 通常はここで unexplained が非空になることは無い（＝事故が構造的に起きない設計）。
        # それでも将来この関数の実装が変わって壊れた時のための、最後のトリップワイヤーとして残す。
        missing = set(disk_items) - set(merged)
        unexplained = missing - deleted_ns
        if unexplained:
            merged_items = list(merged.values())
            _log_blocked(disk_items, mine_items, merged_items, "unexplained_item_loss:%s"
                         % ",".join(str(n) for n in sorted(unexplained)))
            return False

        merged_items = list(merged.values())
        if len(merged_items) < len(disk_items) and not deleted_ns:
            # 上のunexplainedチェックを通り抜けるケースは無いはずだが、念のための二重の安全弁。
            _log_blocked(disk_items, mine_items, merged_items, "item_count_decreased_no_deleted_ns")
            return False

        # 2026-09-13 18:55事故（271件→0件）を受けた最後の絶対安全弁：
        # deleted_nsの計算がどれだけ正しくても、結果が異常に少なくなる書き込みは通さない
        # （呼び出し側のバグでdeleted_nsに大量の番号が誤って入っていた、等のケースまで拾う）。
        if len(disk_items) >= MIN_HEALTHY_ITEMS and len(merged_items) < MIN_HEALTHY_ITEMS:
            _log_blocked(disk_items, mine_items, merged_items,
                         "would_go_below_min_healthy:%d->%d" % (len(disk_items), len(merged_items)))
            return False

        _write_history_backup(disk)

        result = dict(q)
        # 2026-09-19（GitHub見張り番の工事中に実機で踏んだ）：
        #   ここで n をそのまま並べ替えていたため、**1件でも n が文字列("950")の項目が
        #   混ざっていると TypeError で保存が丸ごと落ちる。**
        #   実害：その状態のまま、発車待ちへの追加が全部失敗していた（スマホの
        #   「＋発車待ちに追加」もDispatchからの積み込みも同じ道を通る）。しかも
        #   呼び出し側は例外を握りつぶす場所が多く、**黙って積まれない**（誰も気づけない）。
        #   → 並べ替えの時は数として見る。ついでに項目自身の n も数へ直しておく。
        def _n_as_int(v):
            try:
                return int(v)
            except Exception:
                return None
        for _it in merged_items:
            _v = _n_as_int(_it.get("n"))
            if _v is not None and _it.get("n") != _v:
                _it["n"] = _v
        result["items"] = sorted(merged_items,
                                 key=lambda x: (_n_as_int(x.get("n")) is None,
                                                _n_as_int(x.get("n")) or 0))
        if "repo" not in result and "repo" in disk:
            result["repo"] = disk["repo"]

        tmp = QUEUE + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        os.replace(tmp, QUEUE)
        return True
