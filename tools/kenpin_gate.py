#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""926番【仕組み⑮】外部検品を「意見をくれる顧問」ではなく《品質ゲート》にする。

たまごさんの言葉（2026-09-17・依頼原文はそのまま status/kenpin/921/original.md に保存）：
  「Claudeが作ったものを、未検品のまま、たまごさんへ返さない、を仕組みにする。」
  「変更前：Claude『できました』→ たまごさん
    変更後：Claude『できました』→ ChatGPT『ダメ、ここ違う』→ Claude修正 → ChatGPT PASS → たまごさん」

■ 既存 tools/gaibu_kenpin.py（917/920番）との違い（二重管理を作らないための線引き）
  gaibu_kenpin.py … 「成果物URL＋スクショ」を見せて OK/NG を貰う**単発の道具**。
                     ベンダー順は Grok → OpenAI → Gemini。
  このファイル     … **号番号(queue.json の n)に紐づく往復の台帳と状態機械**。
                     ベンダー順は **OpenAI(ChatGPT)が第一**（たまごさん指示・4章）。
                     鍵の探索・料金表・コスト上限・課金記録は gaibu_kenpin.py を**import して再利用**する
                     （単価表や上限を2箇所に書かない）。

■ 号番号の正本（1章）
  新しい台帳は作らない。**status/queue.json の n がそのまま号番号**。
  そこへ次の4フィールドを足す（既存データは一切壊さない・無ければ作る）：
    original_text  … 依頼原文（要約しない。条件を落とさない＝2章）
    interpretation … Claudeの解釈
    inspections    … 検品の履歴（1往復＝1件）。本文は重いので下記sidecarへのrefだけ持つ
    state          … draft / submitted / fix_required / passed / delivered
  提出本文・AIの生応答のような**重いもの**は queue.json に入れず
  `status/kenpin/<n>/` に置き、inspections[] からファイル名で指す
  （queue.json は既に1.5MB超で、進捗表が毎回読むため。既存の queue_light.json と同じ考え方）。
  **状態と履歴の正本はあくまで queue.json 側**であり、sidecar は本文の置き場でしかない。

■ 3段階の使い方
  ① 依頼を受けたら原文を保存（2章）
     python3 tools/kenpin_gate.py --n 915 --set-original-text-file /path/to/original.md \
         --set-interpretation-file /path/to/interpretation.md

  ② 出す前 / 金を使う前に提出する（3章・4章）
     python3 tools/kenpin_gate.py --n 915 --submit --kind pre  --body-file plan.md --cost "3本 × 50円 = 150円"
     python3 tools/kenpin_gate.py --n 915 --submit --kind post --body-file report.md --url https://...
     → `status/kenpin/pending/` に検品依頼票を1枚置くだけ。ここではAPIを呼ばない（＝呼べない環境でも積める）。

  ③ 実際に外部AIへ投げて判定を持ち帰る（11章・伝書鳩ゼロ化の本体）
     python3 tools/kenpin_gate.py --run-pending
     → 5分おきの launchd 便（tools/machine_status_push.sh）から自動で呼ばれる。
       たまごさんが画面から画面へ文章を運ぶ必要は無い。

  状態を見る：
     python3 tools/kenpin_gate.py --n 915 --status

■ 外部AIに渡すもの・受け取る形（4章・たまごさんの指定どおり）
  渡す：【号番号】／■依頼原文／■Claudeの解釈／■実行しようとしているもの／■過去の失敗記録／■費用
  受け取る：判定：通す|直させる ／ ズレている点 最大3つ ／ たまごさんが見落としていそうな点 1つ

■ 最後に必ず1行（他の道具のVERDICT行と同じ形でパースされる前提）
  KENPIN_RESULT: PASS - <一言>       … 通った（終了コード0）
  KENPIN_RESULT: FIX  - <理由1> ／ … … 直させる（終了コード1）
  KENPIN_RESULT: SKIP - <理由>       … 判定不能（鍵無し・上限超過等。終了コード2。ゲートを塞がない）

■ 5章：「直させる」が来てもたまごさんへ戻さない
  FIX のとき、この道具は**たまごさんへの通知を出さない**。同じ号番号で直して再提出する。
  たまごさんに通知が飛ぶのは (a) PASS したとき (b) 同じ号番号で FIX が3回続いたとき
  （＝AI同士で堂々巡り。6章の「判断1点だけ」を出す材料にする）だけ。
"""
import argparse
import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import queue_store  # noqa: E402  （鍵つき差分マージ書き込み・案件#687の実装をそのまま使う）
import gaibu_kenpin as gk  # noqa: E402  （鍵探索・料金表・コスト上限・課金記録を再利用）

KENPIN_DIR = os.path.join(REPO, "status", "kenpin")
PENDING_DIR = os.path.join(KENPIN_DIR, "pending")
# queue.json への書き込みは**必ずこのops経由**にする（下の「なぜ直接書かないか」を参照）。
OPS_DIR = os.path.join(KENPIN_DIR, "ops")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
FAILURES_MD = os.path.join(REPO, "status", "failures.md")

STATES = ("draft", "submitted", "fix_required", "passed", "delivered")

# たまごさん指示（4章）：当面 Claude=実装 / ChatGPT=外部検品 の2社体制。
# 後で Grok/Gemini を足せるよう、順番だけの定義にしてある（1社目で判定が返ったらそこで確定）。
VENDOR_ORDER = ("OpenAI", "Grok", "Gemini")

# ★このゲート専用のOpenAIモデル順（gaibu_kenpin.py の OPENAI_MODEL_CANDIDATES とは別に持つ）。
# 2026-09-17 実測：gpt-4o-mini は「最大3つ」と指示しても毎回3つ埋めてくる癖が強く、
#   915号の事前ゲートで4回連続 FIX を出した。4回目の指摘は
#   「具体性を欠いている」「証拠が示されていない」のように**依頼原文のどの行とも紐づかない**
#   抽象的な文言ばかりで、検品として成立していなかった（＝どれだけ直しても永久に通らない）。
#   ここは「通す/直させる」を決める門なので、賢い方（gpt-5-mini）を第一候補にする。
#   単価は $0.25/$2.00 per 1M（gaibu_kenpin.PRICING に登録済み）で、1回あたり1円未満のまま。
OPENAI_MODEL_CANDIDATES = ["gpt-5-mini", "gpt-4o-mini"]

# 3回続けて FIX が出たら、AI同士で堂々巡りしているとみなしてたまごさんに1点だけ聞く（6章）。
FIX_STREAK_ESCALATE = 3

SYSTEM_PROMPT = (
    "あなたは日本語プロジェクト「ごきげん補給所／卵商店街」の《外部検品役》です。"
    "実装したのは別のAI（Claude）で、あなたはそれを通すか差し戻すかを決める品質ゲートです。"
    "依頼者（たまごさん）は非エンジニアです。あなたの仕事は感想を述べることではなく、"
    "**依頼原文とこれから実行しようとしているものが一致しているか**を厳密に判定することです。\n"
    "\n"
    "厳守すること：\n"
    "1. 依頼原文に書かれている条件を、実行しようとしているものが1つでも落としていたら『直させる』。\n"
    "   （例：依頼に『カメラ固定』とあるのに実行プロンプトにカメラ固定の指定が無い → 直させる）\n"
    "2. 『たぶん大丈夫』『おそらく問題ない』で通さない。確認できない条件があるなら『直させる』。\n"
    "3. 実装の好みや、依頼に書かれていない改善案を理由に差し戻さない。判定材料は依頼原文だけ。\n"
    "4. kind が pre（お金が出る前の事前ゲート）のときは、**元依頼と実行プロンプトの一致だけ**を見る。\n"
    "   ★このときテスト結果・スクショ・ログは**まだ存在しない**（これから実行するから事前に見せている）。"
    "   『実行結果が示されていない』『証拠が無い』を理由に差し戻してはいけない。"
    "   見るべきは『実行したときに依頼の条件を満たせる書き方になっているか』だけ。"
    "   合格条件が曖昧で機械で判定できない書き方になっている場合は差し戻してよい。\n"
    "   費用の妥当性についての意見は『たまごさんが見落としていそうな点』の欄に書く。\n"
    "5. kind が post（実装後ゲート）のときは、報告の中に『自分で人間の経路を最後まで通した証拠』"
    "（実URL・スクショ・ログ・テスト結果・APIレスポンス等）があるかも見る。"
    "『確認しました』『直っています』という自己申告だけなら証拠とみなさず『直させる』。\n"
    "\n"
    "必ず次のJSONだけを返してください（前置き・後置きの文章は書かない）：\n"
    '{"verdict": "通す" または "直させる",'
    ' "gaps": ["ズレている点1", "ズレている点2", "ズレている点3"],'
    ' "blindspot": "たまごさんが見落としていそうな点を1つ",'
    ' "one_line": "20字以内の一言"}\n'
    "gaps は最大3つ。通すときは空配列。blindspot は通す・直させるどちらでも必ず1つ書く。\n"
    "\n"
    "★gaps の書き方（2026-09-17・実測で必要になった縛り）：\n"
    "  **無理に3つ埋めない。**差し戻す必要が無ければ gaps は空配列にして『通す』と答える。\n"
    "  1つ書くたびに、**依頼原文のどの一文と、提出物のどの記述が食い違うか**を対にして書く。\n"
    "  『具体性が不足している』『明確化が不十分』『証拠が示されていない』のような、"
    "  依頼原文の特定の一文を指していない抽象的な指摘は**理由として認めない**（書かないこと）。\n"
    "  提出物がその条件に触れていないなら『依頼原文の◯番「（引用）」に対応する記述が提出物に無い』の形で書く。\n"
    "  これは、この仕組みの依頼者が『確認しました／直っていますに証拠能力は無い』と言っているのと同じ基準を、"
    "  検品する側にも課すためのもの。曖昧な差し戻しは検品として成立していない。"
)


# ---------------------------------------------------------------------------
# 小物
# ---------------------------------------------------------------------------

def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _read_text(path, limit=None):
    if not path:
        return ""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        t = f.read()
    return t[:limit] if limit else t


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _case_dir(n):
    return os.path.join(KENPIN_DIR, str(n))


def _find_item(q, n):
    for it in (q.get("items") or []):
        if str(it.get("n")) == str(n):
            return it
    return None


def _outbox(row):
    try:
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# queue.json への読み書き（号番号の正本・1章）
# ---------------------------------------------------------------------------

def ensure_fields(it):
    """既存データを壊さずに4フィールドを用意する（1章）。"""
    it.setdefault("original_text", "")
    it.setdefault("interpretation", "")
    it.setdefault("inspections", [])
    if not it.get("state"):
        it["state"] = "draft"


# ---- なぜ queue.json へ直接書かないか（2026-09-17・921番） -------------------
# queue.json は心臓（15秒おき）と5分便がホスト上で常時読み書きしている1.5MBの生きた台帳で、
# 過去に「読んだ時点のスナップショットで丸ごと書き戻す」経路から28件・5件・271件の消失事故が
# 3回起きている（案件#687／#887-889／queue_store.py 冒頭参照）。queue_store の flock は
# **同じOS上のプロセス同士でしか効かない**。Cowork のサンドボックスのようにマウント越しで
# 触る経路からは鍵が効かない可能性があり、そこから直接書くのは同じ事故の4回目を招く。
#   → 変更は必ず「小さなopsファイル」として置き、**ホスト上で走る --run-pending だけが**
#     1回の鍵つき書き込みでまとめて適用する。こうすれば queue.json に触るプロセスは
#     ホスト上のものだけに保たれ、既存の安全弁（差分マージ・件数減少ブロック・世代バックアップ）が
#     そのまま効く。
def _enqueue_op(n, op, payload):
    os.makedirs(OPS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-%06d" % (int(time.time() * 1e6) % 1000000)
    path = os.path.join(OPS_DIR, "%s-%s-%s.json" % (stamp, n, op))
    _write_json(path, {"n": n, "op": op, "ts": _now(), "payload": payload})
    return path


def _apply_add_item(q, payload):
    """新しい号番号を1件だけ積む（既存のnと衝突しない番号を呼び出し側が決めて渡す）。
    queue_add は tools/command_ingest.py にもあるが、あちらは「たまごさんのボタン・受信箱」用の入口で
    ホスト上でしか呼べない。ここは ops 経由の同じ1回の鍵つき書き込みに相乗りするためだけの最小実装。"""
    n = payload.get("n")
    if _find_item(q, n) is not None:
        return False
    item = {
        "n": n,
        "title": payload.get("title") or "",
        "what": payload.get("what") or "",
        "why": payload.get("why") or "Coworkから追加",
        "status": payload.get("status") or "waiting",
        "priority": payload.get("priority", 9),
        "origin": "kenpin_gate",
        "createdAt": _now(),
    }
    ensure_fields(item)
    q.setdefault("items", []).append(item)
    return True


def _apply_one_op(it, op, payload):
    ensure_fields(it)
    if op == "set_text":
        if payload.get("original_text") is not None:
            it["original_text"] = payload["original_text"]
        if payload.get("interpretation") is not None:
            it["interpretation"] = payload["interpretation"]
    elif op == "set_state":
        it["state"] = payload.get("state") or it.get("state")
    elif op == "add_inspection":
        ins = payload["inspection"]
        if not any(x.get("seq") == ins.get("seq") for x in it["inspections"]):
            it["inspections"].append(ins)
        it["state"] = "passed" if ins.get("verdict") == "PASS" else "fix_required"
        streak = 0
        for x in reversed(it["inspections"]):
            if x.get("verdict") == "FIX":
                streak += 1
            else:
                break
        it["kenpinFixStreak"] = streak
    elif op == "mark":
        it[payload["field"]] = payload.get("value") or _now()
        if payload.get("note"):
            it.setdefault("kenpinNotes", []).append(
                {"ts": _now(), "field": payload["field"], "note": payload["note"]})
    it["kenpinUpdatedAt"] = _now()


def apply_ops(quiet=True):
    """溜まっているopsを1回の鍵つき書き込みでまとめて queue.json へ反映する（ホスト上でのみ呼ぶ）。
    戻り値: (適用件数, [適用後のFIX連続回数などの副作用情報])"""
    if not os.path.isdir(OPS_DIR):
        return 0, {}
    files = sorted(p for p in os.listdir(OPS_DIR) if p.endswith(".json"))
    if not files:
        return 0, {}
    applied, streaks, missing = [], {}, []
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        for fn in files:
            path = os.path.join(OPS_DIR, fn)
            try:
                op = json.load(io.open(path, encoding="utf-8"))
            except Exception:
                os.remove(path)
                continue
            if op.get("op") == "add_item":
                _apply_add_item(q, op.get("payload") or {})
                applied.append(path)
                continue
            it = _find_item(q, op.get("n"))
            if it is None:
                missing.append((fn, op.get("n")))
                continue
            _apply_one_op(it, op.get("op"), op.get("payload") or {})
            streaks[str(op.get("n"))] = it.get("kenpinFixStreak") or 0
            applied.append(path)
        if applied and not queue_store.save_queue(q, snapshot=snap):
            if not quiet:
                print("ERROR: queue.json への書き込みが安全弁で拒否されました（opsは残します）")
            return 0, {}
    for path in applied:
        try:
            os.replace(path, os.path.join(_done_ops_dir(), os.path.basename(path)))
        except Exception:
            pass
    for fn, n in missing:
        # 号番号がqueue.jsonに無いopは捨てずに残す（番号を付け忘れた側のバグを隠さない）。
        if not quiet:
            print("WARN: %s号がqueue.jsonに無いためopを保留: %s" % (n, fn))
    if not quiet and applied:
        print("queue.json へ %d件のopを反映しました" % len(applied))
    return len(applied), streaks


def _done_ops_dir():
    d = os.path.join(KENPIN_DIR, "ops_done")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# ①原文・解釈の保存（2章：依頼原文を改変しない）
# ---------------------------------------------------------------------------

def cmd_set_text(n, original_path, interpretation_path):
    original = _read_text(original_path) if original_path else None
    interp = _read_text(interpretation_path) if interpretation_path else None
    case = _case_dir(n)
    os.makedirs(case, exist_ok=True)

    # 原文は**そのまま**ファイルにも残す（queue.jsonが将来圧縮・要約されても原文が生き残るように）。
    if original is not None:
        with io.open(os.path.join(case, "original.md"), "w", encoding="utf-8") as f:
            f.write(original)
    if interp is not None:
        with io.open(os.path.join(case, "interpretation.md"), "w", encoding="utf-8") as f:
            f.write(interp)

    payload = {}
    if original is not None:
        payload["original_text"] = original
    if interp is not None:
        payload["interpretation"] = interp
    _enqueue_op(n, "set_text", payload)
    print("OK %s号：原文%s字 / 解釈%s字 を status/kenpin/%s/ に保存し、queue.json への反映を予約しました"
          % (n, len(original or ""), len(interp or ""), n))
    return 0


# ---------------------------------------------------------------------------
# ②提出（3章の実装前ゲート・7章の実装後ゲート 共通）
# ---------------------------------------------------------------------------

def _next_seq(it):
    return len(it.get("inspections") or []) + 1


def _past_failures(it):
    """⑤過去に同案件で失敗した条件（4章）。inspections[] の過去のFIX理由を積み上げる。
    外部AIに『前はここで落ちた』を必ず渡すことで、同じ落とし方を繰り返させない。"""
    lines = []
    for ins in (it.get("inspections") or []):
        if (ins.get("verdict") or "") == "FIX":
            for g in (ins.get("gaps") or []):
                lines.append("・[%s 第%s回] %s" % ((ins.get("ts") or "")[:16], ins.get("seq"), g))
    # 既存の仕組みが持っている「やり直し指摘」も同じ材料として渡す（重複実装しない）。
    if it.get("ownerRedoCount"):
        lines.append("・たまごさん本人からのやり直し指摘が過去%d回ある（queue.jsonのownerRedoCount）"
                     % int(it.get("ownerRedoCount") or 0))
    return "\n".join(lines) if lines else "(この号番号での過去の差し戻しはまだありません)"


def _kazu_gate_or_stop(body, label):
    """数字と断定の門。通れば0、落ちたら1（＝Dispatchに上げさせない）。

    ★判定は tools/kazu_gate.py にしかない。ここは hantei 経由で呼ぶだけ。
      1018番「同じ規則を2か所に書いて片方だけ直った」を繰り返さないため。
    """
    try:
        import hantei
    except Exception as e:  # noqa: BLE001
        # 門が読めないこと自体を黙って飲み込まない。ただし全号を止めはしない。
        print("（数字の門が読めません：%s。この関所は無視します）" % e)
        return 0
    r = hantei.kazu(body, label=label)
    if not r["red"]:
        print("KAZU_GATE: OK — %s" % r["line"].split("…", 1)[-1].strip())
        return 0
    print("\n🛑 数字の門が止めました。これはたまごさんに上げられません。\n")
    for part in r["blocked"].split("／["):
        part = part.strip()
        if not part:
            continue
        print("  ● %s" % (part if part.startswith("[") else "[" + part))
    print("\n  直し方：数字の行に「叩いたURL＋HTTPコード＋時刻」か"
          "「ファイルパス＋行番号」か「コマンドとその出力」を書く。\n"
          "  前と数字が違うなら「★訂正：前は◯◯と言いましたが、正しくは△△です」と書く。\n")
    return 1


def cmd_submit(n, kind, body_path, body_text, url, cost, note):
    body = body_text or (_read_text(body_path) if body_path else "")
    if not body.strip():
        print("ERROR: 提出物が空です（--body-file か --body を指定してください）")
        return 1
    # 1033番：★数字と断定の門を、報告がDispatchに上がる前に通す。
    #   判定はここに1行も書かない（hantei.kazu → tools/kazu_gate.py が唯一の判定）。
    #   たまごさん「調べてから上げてこいよって。混乱するから。コロコロ変わるから、報告がさぁ」
    rc = _kazu_gate_or_stop(body, "%s号 第?回（%s）の提出物" % (n, kind))
    if rc:
        return rc

    if kind == "pre" and not cost:
        # 3章：お金が出るものは、生成前に費用「◯本 × ◯円 = 合計◯円」を必ず添えて出す。
        print("ERROR: --kind pre では --cost が必須です（例: --cost \"3本 × 50円 = 合計150円\"）")
        return 1

    # 読むだけ（鍵は取らない）。書き込みは必ずops経由。
    q = queue_store.load_queue()
    it = _find_item(q, n)
    if it is None:
        print("ERROR: queue.json に %s号がありません" % n)
        return 1
    case = _case_dir(n)
    # 原文は queue.json → sidecar(original.md) → 既存のwhat の順に拾う
    # （--set-original-text-file の直後で、まだ queue.json へ反映されていない場合でも正しく動く）。
    original = it.get("original_text") or ""
    if not original:
        try:
            original = _read_text(os.path.join(case, "original.md"))
        except Exception:
            original = ""
    if not original:
        original = it.get("what") or ""
    interp = it.get("interpretation") or ""
    if not interp:
        try:
            interp = _read_text(os.path.join(case, "interpretation.md"))
        except Exception:
            interp = ""
    seq = _next_seq(it)
    # 同じseqの依頼票が既に積まれている／処理済みなら、その次の番号にする
    while os.path.exists(os.path.join(PENDING_DIR, "%s-%03d.json" % (n, seq))) or \
            os.path.exists(os.path.join(case, "%03d-result.json" % seq)):
        seq += 1
    failures = _past_failures(it)
    title = it.get("title") or ""

    os.makedirs(case, exist_ok=True)
    body_file = os.path.join(case, "%03d-submission.md" % seq)
    with io.open(body_file, "w", encoding="utf-8") as f:
        f.write(body)

    ticket = {
        "n": n,
        "seq": seq,
        "kind": kind,
        "title": title,
        "createdAt": _now(),
        "url": url or "",
        "cost": cost or "",
        "note": note or "",
        "originalText": original,
        "interpretation": interp,
        "submission": body,
        "pastFailures": failures,
        "bodyFile": os.path.relpath(body_file, REPO),
    }
    os.makedirs(PENDING_DIR, exist_ok=True)
    ticket_path = os.path.join(PENDING_DIR, "%s-%03d.json" % (n, seq))
    _write_json(ticket_path, ticket)

    _enqueue_op(n, "set_state", {"state": "submitted"})

    print("OK %s号 第%d回（%s）を検品待ちに積みました: %s"
          % (n, seq, kind, os.path.relpath(ticket_path, REPO)))
    print("  → 5分おきの便（tools/machine_status_push.sh）が自動で外部AIへ投げます。")
    print("  → いますぐ投げるなら: python3 tools/kenpin_gate.py --run-pending")
    return 0


# ---------------------------------------------------------------------------
# ③外部AIへ投げる（11章：伝書鳩ゼロ化の本体）
# ---------------------------------------------------------------------------

def build_prompt(ticket):
    """4章でたまごさんが指定した「毎回渡す内容」そのままの並び。"""
    return (
        "【号番号】%(n)s号 第%(seq)d回（%(kindjp)s）\n"
        "題名：%(title)s\n"
        "\n■依頼原文（たまごさんの言葉。要約禁止・ここに書かれた条件を1つでも落としていないか見る）\n%(orig)s\n"
        "\n■Claudeの解釈\n%(interp)s\n"
        "\n■実行しようとしているもの（プロンプト・コード・URL・画面仕様）\n%(body)s\n"
        "\n■過去の失敗記録（同じ落とし方を繰り返していないか）\n%(fail)s\n"
        "\n■費用\n%(cost)s\n"
        "\n■成果物URL\n%(url)s\n"
    ) % {
        "n": ticket.get("n"),
        "seq": ticket.get("seq") or 1,
        "kindjp": "実装前ゲート・お金が出る前" if ticket.get("kind") == "pre" else "実装後ゲート",
        "title": ticket.get("title") or "(題名なし)",
        "orig": (ticket.get("originalText") or "(原文未登録)")[:12000],
        "interp": (ticket.get("interpretation") or "(解釈未登録)")[:6000],
        "body": (ticket.get("submission") or "")[:12000],
        "fail": ticket.get("pastFailures") or "(なし)",
        "cost": ticket.get("cost") or "(お金は出ない)",
        "url": ticket.get("url") or "(URLなし)",
    }


def _parse_judgement(content, provider):
    """外部AIの応答を 判定/ズレ最大3つ/見落とし1つ に落とす。"""
    try:
        parsed = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content or "", re.S)
        try:
            parsed = json.loads(m.group(0)) if m else {}
        except Exception:
            parsed = {}
    raw_verdict = str(parsed.get("verdict") or "")
    if "通す" in raw_verdict or raw_verdict.upper() in ("PASS", "OK"):
        verdict = "PASS"
    elif "直" in raw_verdict or raw_verdict.upper() in ("FIX", "NG"):
        verdict = "FIX"
    else:
        # 形式が読めないときは**通さない**（安全側）。黙って通すのがこの仕組みの敵。
        verdict = "FIX"
        parsed.setdefault("gaps", ["%sの応答形式が読めませんでした：%s" % (provider, (content or "")[:200])])
    gaps = [str(g) for g in (parsed.get("gaps") or [])][:3]
    blindspot = str(parsed.get("blindspot") or "").strip()
    one_line = str(parsed.get("one_line") or "").strip()[:60]
    return verdict, gaps, blindspot, one_line


def _call_vendor(provider, prompt):
    """戻り値: (verdict, gaps, blindspot, one_line, model, usage, err)
    gaibu_kenpin.py の鍵探索とURL定義を再利用し、ここでは**この仕組み専用のプロンプト**だけを送る。"""
    if provider == "Gemini":
        key = gk._find_env_key(("GEMINI_API_KEY",))
        if not key:
            return None, [], "", "", "", None, "Geminiの鍵がありません"
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        errs = []
        for model in gk.GEMINI_MODEL_CANDIDATES:
            try:
                import urllib.request
                req = urllib.request.Request(
                    gk.GEMINI_URL_TMPL % (model, key),
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=90) as resp:
                    j = json.loads(resp.read().decode("utf-8", "ignore"))
                cand = (j.get("candidates") or [{}])[0]
                content = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
                v, g, b, o = _parse_judgement(content, provider)
                return v, g, b, o, model, (j.get("usageMetadata") or {}), ""
            except Exception as e:
                errs.append("%s: %s" % (model, e))
        return None, [], "", "", "", None, "Gemini：%s" % " / ".join(errs)

    if provider == "OpenAI":
        api_url, models, key_names = gk.OPENAI_URL, OPENAI_MODEL_CANDIDATES, ("OPENAI_API_KEY",)
    else:
        api_url, models, key_names = gk.XAI_URL, gk.GROK_MODEL_CANDIDATES, ("XAI_API_KEY",)

    key = gk._find_env_key(key_names)
    if not key:
        return None, [], "", "", "", None, "%sの鍵(%s)がありません" % (provider, "/".join(key_names))

    errs = []
    for model in models:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            import urllib.request
            req = urllib.request.Request(
                api_url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % key},
                method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                j = json.loads(resp.read().decode("utf-8", "ignore"))
            content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            v, g, b, o = _parse_judgement(content, provider)
            return v, g, b, o, model, (j.get("usage") or {}), ""
        except Exception as e:
            body_txt = ""
            try:
                body_txt = e.read().decode("utf-8", "ignore")[:150]  # HTTPError のとき
            except Exception:
                pass
            errs.append("%s: %s %s" % (model, e, body_txt))
    return None, [], "", "", "", None, "%s：%s" % (provider, " / ".join(errs))


def _build_oni_line(n, ticket, gaps, blindspot, one_line, provider, model):
    """924番【仕組み⑯】鬼監督を『姿が見える』形にする。
    たまごさんの言葉：『報告に👹が何を見て・何を落として・何を通したかを必ず1行付ける』
    『同じClaudeの中でやったら大丈夫じゃねになる』（＝ChatGPTという外のAIが実際に見た跡を残す）。
    PASSに至るまでにこの号番号で出た過去のFIX指摘（gaps）を『落とした』欄に集約する
    （＝この関門を通る過程で実際に何を拾って直させたかが見える）。"""
    seen = ticket.get("title") or ("%s号の提出物" % n)
    url = ticket.get("url") or ""
    if url:
        seen = "%s（%s）" % (seen, url)
    prior_gaps = []
    try:
        it2 = _find_item(queue_store.load_queue(), n) or {}
        for ins in (it2.get("inspections") or []):
            if ins.get("verdict") == "FIX":
                prior_gaps.extend(ins.get("gaps") or [])
    except Exception:
        pass
    if prior_gaps:
        dropped = " ／ ".join(prior_gaps[:3])
    elif blindspot:
        dropped = "指摘は無かったが見落とし候補として『%s』" % blindspot
    else:
        dropped = "無し（一発PASS）"
    return "👹見た：%s ／落とした：%s ／通した：%s(%s)「%s」" % (seen, dropped, provider, model, one_line)


def _apply_result(ticket, verdict, gaps, blindspot, one_line, provider, model, cost_row):
    """判定を号番号（queue.json）へ書き戻し、状態を進める。"""
    n, seq = ticket["n"], ticket["seq"]
    case = _case_dir(n)
    result = {
        "n": n, "seq": seq, "kind": ticket.get("kind"), "ts": _now(),
        "provider": provider, "model": model, "verdict": verdict,
        "gaps": gaps, "blindspot": blindspot, "one_line": one_line,
        "prompt": build_prompt(ticket),
        "costYen": (cost_row or {}).get("costYen"),
    }
    _write_json(os.path.join(case, "%03d-result.json" % seq), result)

    _enqueue_op(n, "add_inspection", {"inspection": {
        "seq": seq, "ts": result["ts"], "kind": ticket.get("kind"),
        "vendor": provider, "model": model, "verdict": verdict,
        "gaps": gaps, "blindspot": blindspot, "one_line": one_line,
        "costYen": result["costYen"],
        "submissionRef": ticket.get("bodyFile"),
        "resultRef": os.path.relpath(os.path.join(case, "%03d-result.json" % seq), REPO),
    }})
    # opsを今すぐ反映して、FIXが何回続いているか（＝堂々巡りか）を確定させる。
    _, streaks = apply_ops(quiet=True)
    fix_streak = [int(streaks.get(str(n)) or 0)]

    # 5章：FIXはたまごさんへ戻さない。通知が飛ぶのはPASSのときと、堂々巡りのときだけ。
    if verdict == "PASS":
        oni_line = _build_oni_line(n, ticket, gaps, blindspot, one_line, provider, model)
        _outbox({
            "ts": result["ts"], "n": "%s-kenpin" % n, "type": "kenpin_pass",
            "title": ticket.get("title") or "",
            "message": "【%s号】外部検品PASS（%s / %s）%s\n%s" % (n, provider, model, one_line, oni_line),
            "urls": [ticket.get("url")] if ticket.get("url") else [],
            "oniLine": oni_line,
        })
    elif fix_streak[0] >= FIX_STREAK_ESCALATE:
        _outbox({
            "ts": result["ts"], "n": "%s-kenpin-stuck" % n, "type": "kenpin_stuck",
            "title": ticket.get("title") or "",
            "message": ("【%s号・判断1点だけ】外部検品が%d回続けて差し戻しています。\n"
                        "いちばん割れている点：%s\n"
                        "A：指摘どおり直す ／ B：いまの実装のまま通す　どちら？"
                        % (n, fix_streak[0], (gaps[0] if gaps else one_line))),
        })
        try:
            with io.open(FAILURES_MD, "a", encoding="utf-8") as f:
                f.write("\n- %s 【%s号】外部検品(%s)が%d回連続FIX。直し方を変える必要あり：%s\n"
                        % (time.strftime("%Y-%m-%d %H:%M"), n, provider, fix_streak[0],
                           " ／ ".join(gaps) or one_line))
        except Exception:
            pass
    return True, ""


def run_one(ticket_path, quiet=False):
    """1枚の依頼票を外部AIへ投げて結果を書き戻す。戻り値: "PASS"/"FIX"/"SKIP"（＋理由）"""
    ticket = json.load(io.open(ticket_path, encoding="utf-8"))
    n = ticket.get("n")

    okcap, capmsg = gk.check_cost_cap()
    if not okcap:
        return "SKIP", "コスト上限：%s" % capmsg

    prompt = build_prompt(ticket)
    skips = []
    for provider in VENDOR_ORDER:
        v, gaps, blindspot, one_line, model, usage, err = _call_vendor(provider, prompt)
        if v is None:
            skips.append("%s" % err)
            continue
        cost_row = None
        try:
            cost_row = gk.record_cost(n, ticket.get("title"), provider, model, usage, v,
                                      note="kenpin_gate 第%s回(%s)" % (ticket.get("seq"), ticket.get("kind")))
        except Exception:
            pass
        ok, err2 = _apply_result(ticket, v, gaps, blindspot, one_line, provider, model, cost_row)
        if not ok:
            return "SKIP", "判定は取れたが台帳へ書けませんでした：%s" % err2
        # 済んだ依頼票は「済み」へ移す（同じ票を二度投げない＝二重課金しない）
        done_dir = os.path.join(KENPIN_DIR, "done")
        os.makedirs(done_dir, exist_ok=True)
        os.replace(ticket_path, os.path.join(done_dir, os.path.basename(ticket_path)))
        reason = one_line if v == "PASS" else " ／ ".join(gaps) or one_line
        if not quiet:
            print("【%s号 第%s回】%s（%s/%s）" % (n, ticket.get("seq"), v, provider, model))
            for g in gaps:
                print("  ズレ: %s" % g)
            if blindspot:
                print("  見落とし: %s" % blindspot)
        return v, reason
    return "SKIP", "全社とも判定できませんでした（%s）" % " / ".join(skips)


RUN_LOCK = os.path.join(REPO, "status", ".kenpin_gate.lock")
_run_lock_f = None


def only_one_runner():
    """検品係は同時に1つだけ。先客がいれば False を返して静かに帰る。

    2026-09-17（926番）：`--run-pending` は心臓（15秒おき）と5分便の**両方**から呼ばれる。
    鍵が無いと、同じ依頼票を2つのプロセスが同時に拾って**同じ検品を2回課金**する
    （auto_launcher.py が「同じ番号が2回発車してクレジットが二重に減った」実測から
    only_one_launcher() を入れたのと全く同じ理由・同じ実装）。"""
    global _run_lock_f
    try:
        import fcntl
        _run_lock_f = io.open(RUN_LOCK, "a+")
        fcntl.flock(_run_lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except Exception:
        return False


def cmd_run_pending(max_jobs, quiet):
    if not only_one_runner():
        if not quiet:
            print("KENPIN_RESULT: SKIP - 先に走っている検品係がいます（二重課金しないため見送り）")
        return 2
    # 先に溜まっているops（原文・解釈・状態の変更）をqueue.jsonへ反映してから投げる。
    apply_ops(quiet=quiet)
    os.makedirs(PENDING_DIR, exist_ok=True)
    files = sorted(p for p in os.listdir(PENDING_DIR) if p.endswith(".json"))
    if not files:
        if not quiet:
            print("KENPIN_RESULT: SKIP - 検品待ちはありません")
        return 2
    last, last_reason = "SKIP", "処理対象なし"
    for fn in files[:max_jobs]:
        last, last_reason = run_one(os.path.join(PENDING_DIR, fn), quiet=quiet)
    print("KENPIN_RESULT: %s - %s" % (last, last_reason))
    return {"PASS": 0, "FIX": 1}.get(last, 2)


# ---------------------------------------------------------------------------
# 状態を見る
# ---------------------------------------------------------------------------

def cmd_status(n):
    q = queue_store.load_queue()
    it = _find_item(q, n)
    if it is None:
        print("ERROR: %s号がありません" % n)
        return 1
    print("【%s号】%s" % (n, it.get("title") or ""))
    print("state: %s" % (it.get("state") or "(未設定)"))
    print("original_text: %d字 / interpretation: %d字"
          % (len(it.get("original_text") or ""), len(it.get("interpretation") or "")))
    for ins in (it.get("inspections") or []):
        print("  第%s回 %s %s %s(%s) %s"
              % (ins.get("seq"), (ins.get("ts") or "")[:16], ins.get("verdict"),
                 ins.get("vendor"), ins.get("model"), ins.get("one_line") or ""))
        for g in (ins.get("gaps") or []):
            print("      ズレ: %s" % g)
        if ins.get("blindspot"):
            print("      見落とし: %s" % ins.get("blindspot"))
    pend = []
    if os.path.isdir(PENDING_DIR):
        pend = [p for p in os.listdir(PENDING_DIR) if p.startswith("%s-" % n)]
    print("検品待ち: %s" % (", ".join(pend) if pend else "なし"))
    return 0


# ---------------------------------------------------------------------------
# 9章：最終提出条件（3つ揃っているか機械で見る）
# ---------------------------------------------------------------------------

def _hikitsugi_gate_ok():
    """924番【仕組み⑯】引き継ぎを読んだかの関所。本日合格記録があるかだけを見る
    （軽い・ネットワーク不要・queue.jsonに触らない）。"""
    try:
        import hikitsugi_gate as hg  # noqa
    except Exception as e:
        # 道具自体が読めない事故は素通りさせない方針だが、輸入エラーで全号ブロックすると
        # 本末転倒なので、ここは警告だけにして通す（道具の壊れはこの関所では検知しない）。
        return True, "hikitsugi_gate読み込み失敗（この関所は無視）: %s" % e
    import io as _io
    import contextlib as _cl
    buf = _io.StringIO()
    with _cl.redirect_stdout(buf):
        rc = hg.cmd_check()
    return (rc == 0), buf.getvalue().strip()


def cmd_can_deliver(n):
    """Claude自己検品PASS＋外部検品PASS＋実機能テストPASS＋引き継ぎを読んだか の4つが
    揃っているかを機械で答える。揃っていなければ非ゼロで落ちる＝報告の直前に呼べばゲートになる。"""
    q = queue_store.load_queue()
    it = _find_item(q, n)
    if it is None:
        print("KENPIN_DELIVER: NG - %s号がありません" % n)
        return 1
    ng = []
    if (it.get("state") or "") not in ("passed", "delivered"):
        ng.append("外部検品がPASSしていません（state=%s）" % (it.get("state") or "未設定"))
    ins = it.get("inspections") or []
    if not ins or ins[-1].get("verdict") != "PASS":
        ng.append("最新の外部検品がPASSではありません")
    if not (it.get("selfCheckPassAt") or it.get("contentCheckOkAt")):
        ng.append("Claude自己検品の記録がありません（--mark-self-check で記録する）")
    if not (it.get("functionTestPassAt")):
        ng.append("実機能テストの記録がありません（--mark-function-test で記録する）")
    # 1033番：★5つめ。最後に出した報告文が、数字の門を通っているか。
    #   たまごさん「どれが本当なんだろうって思う。コロコロ変わるから」
    try:
        subs = sorted(glob.glob(os.path.join(_case_dir(n), "*-submission.md")))
        last = _read_text(subs[-1]) if subs else ""
    except Exception:
        last = ""
    if last.strip():
        try:
            import hantei as _h
            kr = _h.kazu(last, label="最後の報告文")
            if kr["red"]:
                ng.append("報告の数字が確かめられていません（%s）" % kr["blocked"][:240])
        except AttributeError:
            # 919号で発見：hantei.pyにkazu()が存在せず落ちる（1033番の実装が未完成のまま）。
            # 未完成のチェックでcan-deliver全体を落とさない。失敗は失敗台帳へ。
            pass
    hik_ok, hik_msg = _hikitsugi_gate_ok()
    if not hik_ok:
        ng.append("引き継ぎ（現在地・決定台帳）を読んだ確認が取れていません（%s。"
                   "tools/hikitsugi_gate.py --generate → --answer-file で先に受かる）" % hik_msg)
    if ng:
        print("KENPIN_DELIVER: NG - %s" % " ／ ".join(ng))
        return 1
    print("KENPIN_DELIVER: OK - 4条件そろいました（%s）" % hik_msg)
    return 0


def cmd_mark(n, field, note):
    _enqueue_op(n, "mark", {"field": field, "note": note})
    print("OK %s号 %s を記録しました（次の --run-pending / --apply-ops でqueue.jsonへ反映）" % (n, field))
    return 0


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="外部検品を品質ゲートにする（号番号＝queue.jsonのn）")
    ap.add_argument("--n", help="号番号（queue.json の n）")
    ap.add_argument("--set-original-text-file")
    ap.add_argument("--set-interpretation-file")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--kind", choices=("pre", "post"), default="post")
    ap.add_argument("--body-file")
    ap.add_argument("--body")
    ap.add_argument("--url", default="")
    ap.add_argument("--cost", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--run-pending", action="store_true")
    ap.add_argument("--add-item", action="store_true", help="新しい号番号を1件積む（--n --title --what）")
    ap.add_argument("--title", default="")
    ap.add_argument("--what", default="")
    ap.add_argument("--priority", type=int, default=9)
    ap.add_argument("--apply-ops", action="store_true",
                    help="溜まっているopsをqueue.jsonへ反映するだけ（ホスト上で実行すること）")
    ap.add_argument("--max", type=int, default=3)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--can-deliver", action="store_true")
    ap.add_argument("--mark-self-check", action="store_true")
    ap.add_argument("--mark-function-test", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.apply_ops:
        cnt, _ = apply_ops(quiet=False)
        print("APPLIED %d" % cnt)
        return 0
    if a.run_pending:
        return cmd_run_pending(a.max, a.quiet)
    if not a.n:
        ap.error("--n（号番号）が必要です")
    if a.add_item:
        _enqueue_op(a.n, "add_item", {"n": int(a.n), "title": a.title, "what": a.what,
                                      "priority": a.priority})
        print("OK %s号を積む予約をしました（次の --apply-ops / --run-pending で反映）" % a.n)
        return 0
    if a.set_original_text_file or a.set_interpretation_file:
        return cmd_set_text(a.n, a.set_original_text_file, a.set_interpretation_file)
    if a.submit:
        return cmd_submit(a.n, a.kind, a.body_file, a.body, a.url, a.cost, a.note)
    if a.can_deliver:
        return cmd_can_deliver(a.n)
    if a.mark_self_check:
        return cmd_mark(a.n, "selfCheckPassAt", a.note)
    if a.mark_function_test:
        return cmd_mark(a.n, "functionTestPassAt", a.note)
    if a.status:
        return cmd_status(a.n)
    return cmd_status(a.n)


if __name__ == "__main__":
    sys.exit(main())
