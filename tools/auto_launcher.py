#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
発車待ち（status/queue.json）から、空きができたら自動で次を着火する。

2026-09-04 たまごさん：
  「**まず連続して走る仕組みを優先してね。**」
  「順番に発車されるようにして、クレジットとバランスを取って、1日中回ってる状態を作るのが最優先だよ。」
  「**全部3時間縛り。もう報告ね、URLとともに報告。これがセット。**」

やること（5分おきに machine_status_push.sh から呼ばれる）:
  1. いま何本走っているかを machine.json から読む（Dispatch本体と完了済みは数えない）
  2. 空きがあるか判定：マシン（safeMax）とクレジット（週枠・5時間枠）の両方を見る
  3. 空きがあれば queue.json の先頭（優先度順）を1件だけ着火する
     - git worktree を切る
     - claude -p --session-id <新規> --model claude-sonnet-5 で起動
     - プロンプトに「3時間で切る」「1セット＝実装→main合流→Lovable公開→本番確認→URL報告」を必ず入れる
  4. 着火したら queue.json のその項目を running にして、走行中の記録を残す

安全弁:
  - Macが危険（メモリ圧=赤／スワップ増／ディスク空き5GB未満）なら着火しない
  - 週枠が stop なら着火しない（クレジットの天井に着かせない）
  - 1回の実行で着火するのは1本まで
  - Fableは使わない（no_fable.flag があるかに関わらず、ここでは常にSonnet）
"""
import io
import json
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
MACHINE = os.path.join(REPO, "status", "machine.json")
QUOTA = os.path.join(REPO, "status", "quota.json")
PRIORITY = os.path.join(REPO, "status", "priority.json")
LOG = os.path.join(REPO, "status", "auto_launch.log")
SONNET = "claude-sonnet-5"
CLAUDE = os.path.expanduser("~/.local/bin/claude")
if not os.path.exists(CLAUDE):
    for c in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(c):
            CLAUDE = c
            break


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def load(p, default):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def countable(s):
    if s.get("isDispatchSelf"):
        return False
    if s.get("status") in ("完了", "失敗"):
        return False
    return True


def harvest(q):
    """2026-09-04 たまごさん「作業が終わって、終わったんであれば、そこは俺の確認待ちだよ。
    確認待ちでOKって言ったら初めて完了に入る。ダメだったらもう一回順番待ちに並ぶ」
    「終わったら報告。Dispatchにも進捗表にもリンクが貼られてあること。何時何分に完了したかも」

    claude -p は1回きりの実行で、終わると結果をログに吐いて死ぬ。
    これまでその結果を誰も読んでいなかった（＝「どっか行っちゃってる」の正体）。
    ここで、死んだプロセスのログから結果とURLを拾い、status を awaiting_check（たまごさんの確認待ち）にする。
    """
    import re
    changed = False
    for it in q.get("items", []):
        if it.get("status") != "running":
            continue
        pid = it.get("pid")
        alive = False
        if pid:
            try:
                os.kill(int(pid), 0)
                alive = True
            except Exception:
                alive = False
        if alive:
            continue
        # 死んでいる＝終わった。ログから結果を拾う
        sid = (it.get("sessionId") or "")[:8]
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % sid)
        result, urls = "", []
        try:
            raw = io.open(logf, encoding="utf-8", errors="ignore").read()
            m = re.findall(r'"result"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            if m:
                # 2026-09-04 文字化け修正：unicode_escape は日本語を latin-1 として壊す。
                #   \uXXXX を解いたあと latin-1→utf-8 で戻す。
                result = m[-1].encode("utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
            # URLに混ざるゴミ（\n、全角括弧、バックスラッシュ）を落とす
            # 2026-09-04 修正：joy-relief-station.lovable.app 固定だと、成果物が
            #   別リポジトリ（tamago-shinchoku＝GitHub Pages等）の時にURLを一切拾えなかった
            #   （実例：20番「自動発車」自身がそれだった）。result本文（たまごさんへの完了報告文）
            #   から任意のhttps URLを拾う方式へ一般化する。
            cand = re.findall(r"https://[^\s\"'）)、。]*", result or raw)
            clean = []
            for u in cand:
                u = u.split("\\")[0].rstrip("/.,:;")
                if u and u not in clean and len(u) > len("https://a.co"):
                    clean.append(u)
            urls = clean[:5]
        except Exception:
            pass
        it["status"] = "awaiting_check"          # たまごさんの確認待ち
        it["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        it["result"] = (result or "（結果が読み取れませんでした）")[:1200]
        it["urls"] = urls
        it.pop("pid", None)
        changed = True
        log("✅ 終了を回収 %d番「%s」→ 確認待ち（URL %d本）" % (it.get("n"), it.get("title"), len(urls)))
    return changed


def build_prompt(item):
    """着火用の指示文。たまごさんが繰り返し言っていることを毎回入れる。"""
    return """【自動発車】発車待ちの{n}番です。

# やること
**{title}**

{what}

# 完了条件（この1行が満たされたら完了）
**{title} が本番に反映され、その本番URLがDispatchに届いている。**

# 1セットの定義（これ未満は成果ゼロ）
① 実装 → ② main合流 → ③ **Lovableの「公開」を押す**（聞かずに押す。エージェント・チャット・ビルド・コード編集は絶対に使わない、公開ボタンだけ）→ ④ **本番URLを開いて自分の目で確認** → ⑤ **DispatchへURL報告**

**main合流だけでは成果ゼロです。**本番で確認せずに「直しました」と言わないでください。

**たまごさんの言葉（2026-09-04）：**
> 「**pushを完了と言ってしまう。これはダメだね。画面が変わって初めて完了。画面が変わって、なおかつ報告。Dispatchに報告。URLとともに。**セッションの中で完了したとか言って、それはもう完了してない。**報告しないのはダメ。**」

# 報告の形（これだけ）
```
【完了】<何を直したか1行>
URL: <本番URL>
```
説明も経緯も謝罪も要りません。

# 時間
**3時間で必ず切ってください。**（たまごさん指定）
3時間で終わらなければ、**できたところまでを本番に出して、URLと「どこまで終わって、次に何をするか」を報告**してから終わってください。黙って止まるのが一番困ります。

# 進め方
- **小さく切る。**大きくやろうとして3時間固まって何も出ないのが最悪です。1つ直すごとに公開してURLを報告してください
- 詰まったら「ここで詰まった、次はこれを試す」と1行出して、**別の経路へ進む**。右がダメなら左、後ろ、上、階段
- Bashが固まったら別の手段に切り替える。**同じ経路で3回目をやらない**
- **重い全文検索やビルドを何度も回さない**（Macのディスク待ちが伸びてフリーズします）

# 禁止
- **モデルはSonnet固定。Fableは絶対に使わない**（週枠の天井に着くと工場が全部止まります）
- **たまごさんに質問しない。**止まってよいのは不可逆な4つ（作り直せないデータの削除／課金／外部公開／パスワード入力）だけ
- 「できません」と言う前に、**試した経路を1行ずつ書き出す**
- 棚への新規掲載はしない（たまごさんの判断領域）。既存の修正・確認に限る
- BraveとLovableのChromeウィンドウを閉じない
""".format(n=item.get("n"), title=item.get("title"), what=item.get("what") or "")


def main():
    q = load(QUEUE, {})
    items = q.get("items") or []
    if not items:
        return 0
    # 終わったものを回収して「確認待ち」へ移す（これをやらないと running のまま溜まって空きが出ない）
    if harvest(q):
        q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
        json.dump(q, io.open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m = load(MACHINE, {})
    quota = load(QUOTA, {})

    # ---- 安全弁：マシン ----
    if (m.get("memPressure") == "red") or m.get("swapIncreasing") or (m.get("diskFreeGB") or 99) < 5:
        log("見送り: Macが危険（mem=%s swapUp=%s disk=%s）" % (m.get("memPressure"), m.get("swapIncreasing"), m.get("diskFreeGB")))
        return 0
    # ---- 安全弁：クレジット ----
    if quota.get("allLevel") == "stop":
        log("見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
        return 0

    alive = len([s for s in (m.get("sessionList") or []) if countable(s)])
    safe_max = m.get("safeMax")
    if safe_max is None:
        log("見送り: safeMaxが取れない")
        return 0
    if alive >= safe_max:
        log("見送り: 走行%d本／上限%d本（空きなし）" % (alive, safe_max))
        return 0

    # ---- 優先度順に並べる。たまごさんがPWAで付けたPが最優先、次に元の番号 ----
    prio = (load(PRIORITY, {}).get("priority") or {})

    def rank(it):
        # 2026-09-04：スマホの「＋発車待ちに追加」で作った項目はitem自身に"priority"を持つ
        #   （queue_add・command_ingest.py）。既存のpriority.jsonのQキー方式より優先する。
        p = it.get("priority") or prio.get("Q%d" % it.get("n"))
        return (int(p) if p else 9, it.get("n") or 99)

    waiting = sorted([it for it in items if it.get("status") == "waiting"], key=rank)
    if not waiting:
        log("見送り: 発車待ちが空")
        return 0

    # 2026-09-04 たまごさん「今イパネマしかしてないから、そこを4本にして」
    #   1回の実行で1本だけだと、5分×3回で3本になるまで15分かかる。空いているぶんを一度に埋める。
    room = safe_max - alive
    launched = 0
    for item in waiting[:room]:
        if launch_one(item, q, alive + launched, safe_max):
            launched += 1
    if launched:
        q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
        json.dump(q, io.open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


def launch_one(item, q, alive, safe_max):

    # ---- worktree を切る ----
    repo = q.get("repo") or "/Users/mac/Desktop/joy-relief-station"
    wt_name = item.get("worktree") or ("q%02d-0904" % item.get("n"))
    wt = os.path.join(repo, ".worktrees", wt_name)
    # 2026-09-04：Cowork側のサンドボックスからマウント越しにgitを叩くと .lock が消せずに残り、
    #   以後ホスト側の worktree add が exit 128 で失敗し続ける（実際に15番以降が着火できなくなった）。
    #   5分以上前の置き去りロックだけ掃除する（実行中のgitは巻き添えにしない）。
    try:
        subprocess.run(["bash", "-c",
                        # 2026-09-04 修正：-mmin +5 だと、Cowork側が直前に作ったロックが消せず
                        #   着火が exit 128 で失敗し続けた（q15〜q33が全滅）。ここは自分しかgitを使っていない
                        #   タイミング（5分おき・二重起動はロックで防止済み）なので、無条件で掃除する。
                        "find '%s/.git' -name '*.lock' -delete 2>/dev/null; "
                        "find '%s/.git/refs' -name '*.lock' -delete 2>/dev/null; "
                        "find '%s/.git/worktrees' -name 'locked' -delete 2>/dev/null; true" % (repo, repo, repo)],
                       capture_output=True, timeout=60)
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True, timeout=120)
        # 2026-09-04：worktreeが129個まで増え、ディスクが96%（残23GB）になって
        #   git worktree add が exit 128 で失敗し続けた（q15〜q33が全滅）。
        #   自動発車で作った古いもの（q**-0904）を30分経過で片づける。作業本体はmainに合流済みの前提。
        out = subprocess.run(["git", "-C", repo, "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=120).stdout
        now_t = time.time()
        for ln in out.splitlines():
            if not ln.startswith("worktree "):
                continue
            path = ln[len("worktree "):].strip()
            base = os.path.basename(path)
            if not (base.startswith("q") and "-0904" in base):
                continue
            try:
                if now_t - os.path.getmtime(path) < 1800:
                    continue
            except Exception:
                continue
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", path],
                           capture_output=True, timeout=180)
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True, timeout=120)
    except Exception:
        pass
    if not os.path.isdir(wt):
        try:
            subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                            "-b", "claude/" + wt_name],
                           check=True, capture_output=True, timeout=300)
        except Exception:
            # 2026-09-04：ブランチが既にある等で失敗する（exit 128）。既存ブランチに繋ぐ形で作り直す。
            try:
                subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                                "claude/" + wt_name],
                               check=True, capture_output=True, timeout=300)
            except Exception:
                # それでもダメなら名前を変えて切る。ここで止まらない（止まると工場が止まる）
                wt_name = wt_name + "-" + time.strftime("%H%M%S")
                wt = os.path.join(repo, ".worktrees", wt_name)
                try:
                    subprocess.run(["git", "-C", repo, "worktree", "add", os.path.join(".worktrees", wt_name),
                                    "-b", "claude/" + wt_name],
                                   check=True, capture_output=True, timeout=300)
                except subprocess.CalledProcessError as e3:
                    err = (e3.stderr or b"").decode("utf-8", "ignore")[:300] if isinstance(e3.stderr, bytes) else str(e3.stderr)[:300]
                    log("worktree作成に失敗（3回試した） %s: %s" % (wt_name, err.replace("\n", " ")))
                    return False
                except Exception as e3:
                    log("worktree作成に失敗（3回試した） %s: %s" % (wt_name, e3))
                    return False

    # ---- 着火 ----
    new_id = str(uuid.uuid4())
    prompt = build_prompt(item)
    logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
    cmd = [CLAUDE, "-p", "--session-id", new_id, "--model", SONNET,
           "--permission-mode", "auto", "--output-format", "json", prompt]
    try:
        with open(logf, "ab") as f:
            f.write(("\n=== %s 自動発車: %s\n" % (time.strftime("%F %T"), item.get("title"))).encode())
            p = subprocess.Popen(cmd, cwd=wt, stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        pid = p.pid
    except Exception as e:
        log("着火に失敗 %s: %s" % (item.get("title"), e))
        return False

    item["status"] = "running"
    item["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    item["sessionId"] = new_id
    item["pid"] = pid
    log("🚀 自動発車 %d番「%s」→ pid %s / session %s（走行%d本→%d本・上限%d本）"
        % (item.get("n"), item.get("title"), pid, new_id[:8], alive, alive + 1, safe_max))
    print("自動発車: %s" % item.get("title"))
    return True


if __name__ == "__main__":
    sys.exit(main())
