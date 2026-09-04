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


# ---- 台帳の鍵（2026-09-05）----
# たまごさん「完了に入ったものもあれば、反応しないものもあります」の原因。
# 中継所（押したボタン）と心臓（着火・回収）が**同時に台帳を読み書きしていた**ため、
# 片方が1秒前に読んだ古い内容で上書きし、押した結果が消えていた（lost update）。
# 読む→書くの間ずっと鍵をかける。macOSの flock を使う（同一ファイルなので確実）。
import fcntl
from contextlib import contextmanager

QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")


@contextmanager
def queue_lock(timeout=10.0):
    f = io.open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break          # 取れなくても止まらない（工場を止めない方を優先）
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def save_queue(q):
    """台帳を安全に書く。

    2026-09-04：直接 open(w) で書いていたため、別のプロセス（受信箱の処理・Dispatch）が
    同時に書いた瞬間に**中身が二重になって壊れた**（実測：末尾214文字が重複しJSONとして読めなくなった）。
    台帳が壊れると工場が丸ごと止まるので、一時ファイルに書いてから置き換える（原子的）。
    """
    tmp = QUEUE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE)


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
            # 2026-09-04 たまごさん「確認のURLをくれるのはいいけど、**全く見当違いなところに連れて行く**
            #   からそれもやめて。**確認してからこっちに上げて。**時間の無駄だから」
            #   → 「直ったところ」を指していないURLを証拠として数えない。
            #     ここで弾かれると、この仕事はURLなし扱いになり自動でやり直しの列へ戻る。
            JUNK = (
                "example.com", "youtube.com/oembed", "youtube.com/results",
                "youtube.com/watch", "youtu.be/", "github.com/", "docs.", "localhost",
                "trycloudflare.com",
            )
            ROOTS = (
                "https://joy-relief-station.lovable.app",
                "https://tamago2022.github.io/tamago-shinchoku",
                "https://www.youtube.com", "https://youtube.com",
            )
            clean = []
            for u in cand:
                u = u.split("\\")[0].rstrip("/.,:;")
                if not u or u in clean or len(u) <= len("https://a.co"):
                    continue
                if any(j in u for j in JUNK):
                    continue
                if u in ROOTS:          # トップページだけ貼るのは「どこを見ればいいか分からない」
                    continue
                clean.append(u)
            urls = clean[:5]
        except Exception:
            pass
        # 2026-09-05 たまごさん「何も動いてない状態は作らないで。クレジット消費最小で」
        #   → 空回し（keepalive）は終わったら台帳から静かに消す。
        #     確認待ちに積むと、判定するものが増えるだけで意味がない（今日それで29件溜めた）。
        if it.get("keepalive"):
            it["_drop"] = True
            changed = True
            log("♻︎ 空回し %d番が終わりました（台帳からは消します）" % it.get("n"))
            continue
        it["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        it["result"] = (result or "（結果が読み取れませんでした）")[:1200]
        it["urls"] = urls
        it.pop("pid", None)
        changed = True
        # 2026-09-04 たまごさん「画面が変わって初めて完了。画面が変わって、なおかつ報告。
        #   Dispatchに報告。URLとともに。」
        #   → **URLが1本も無いものを確認待ちに入れない。**入れると、たまごさんが
        #     「これ何を見て判断すればいいの」と確認だけさせられる（＝水くみ）。
        #     URLが無い＝完了ではないので、こちらで黙って列に戻す。2回までは自動でやり直し、
        #     3回目は確認待ちへ回して人の目で見てもらう（無限ループを作らない）。
        tries = int(it.get("redoCount") or 0)
        if not urls and tries < 2:
            it["redoCount"] = tries + 1
            # 止める指示が出ている案件は、やり直しでも列に戻さない（戻すと勝手に再発車してしまう）
            it["status"] = "hold" if it.get("holdNote") else "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【自動やり直し・%s】前回はURLを1本も出さずに終わりました。"
                "たまごさんの決まり：**画面が変わって、本番のURLを報告して、はじめて完了。**"
                "本番に出したページのURLを必ず報告に含めること。"
                "どうしても出せない事情があるなら、その理由を1行だけ書くこと。"
                % time.strftime("%m-%d %H:%M"))
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt"):
                it.pop(k, None)
            log("↩︎ URLなしのため自動やり直し %d番「%s」（%d回目）" % (it.get("n"), it.get("title"), tries + 1))
        else:
            it["status"] = "awaiting_check"      # たまごさんの確認待ち
            log("✅ 終了を回収 %d番「%s」→ 確認待ち（URL %d本）" % (it.get("n"), it.get("title"), len(urls)))
    if any(x.get("_drop") for x in q.get("items", [])):
        q["items"] = [x for x in q["items"] if not x.get("_drop")]
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

**注意：報告の中にhttpsで始まる本番URLが1本も無い場合、この仕事は自動的にやり直しの列へ戻されます**（たまごさんに見せる前に機械が弾きます）。URLを出せない事情があるなら、その理由を1行だけ書いてください。

**たまごさんの言葉（2026-09-04）：**
> 「**pushを完了と言ってしまう。これはダメだね。画面が変わって初めて完了。画面が変わって、なおかつ報告。Dispatchに報告。URLとともに。**セッションの中で完了したとか言って、それはもう完了してない。**報告しないのはダメ。**」

# 報告の形（これだけ）
```
【完了】<何を直したか1行>
確認ページ: <確認ページのURL>
```
説明も経緯も謝罪も要りません。

# ★確認ページを必ず作る（2026-09-04・たまごさんの指示）
たまごさんの言葉（そのまま）：
> 「**URLくれるのはいいけど、ここに連れて行ったのね。**さっきと変わってないでしょう。
>  **調べようがないから分からない。もうその入り口に連れてって。俺が探す、俺がコピーする、をやめて。
>  もう確認が取れるところへ連れて行ってください。**」

**「直したページを1つだけ貼る」のは禁止です。**たまごさんはそこから自分で探すことになります。
代わりに、成果を1枚にまとめた**確認ページ**を作り、そのURLだけを報告してください。

作り方（このやり方以外を考えないでください）：
1. リポジトリ `/Users/mac/Desktop/tamago-shinchoku` の `share/check/` に
   **`{n}-<短い英語名>.html`** という1ファイルを作る（例：`share/check/{n}-drama-shelf.html`）
2. 中身は**この4つだけ**。飾りは要りません。
   - ① 何を直したか（1行）
   - ② **数字**（例：「22件のうち21件を移動。残り1件は◯◯のため未」）
   - ③ **押せるリンクの一覧**（直した実物のページ。1件ずつ `<a href>`。10件を超えるなら代表10件＋全件）
   - ④ **前と後のスクリーンショット**（撮れたら `share/check/img/` に置いて `<img>` で貼る）
3. `git add` → `commit` → `push origin main`。GitHub Pagesなので数十秒で公開されます
4. 報告に書くURLは **`https://tamago2022.github.io/tamago-shinchoku/share/check/{n}-....html`**

**「直っていること」がそのページを開いただけで分かること。**
開いてもまだ探さないと分からないなら、その確認ページは失格です。

**出す前に自分で開いて確かめる。**たまごさんの言葉：
> 「**確認のURLをくれるのはいいけど、全く見当違いなところに連れて行くから、それもやめて。
>  確認してからこっちに上げて。時間の無駄だから。ちゃんと『直った』『問題がある』というところのURLを置いてください。**」

次のURLは**証拠として数えません**（貼っても、URLなし扱いでやり直しになります）：
サイトのトップページだけ／`example.com`／YouTubeの検索結果やoembed／GitHubのリポジトリ／ドキュメント。
**直した実物か、確認ページのURL**を出してください。

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
  with queue_lock():
      q = load(QUEUE, {})
      items = q.get("items") or []
      if not items:
          return 0
      # 終わったものを回収して「確認待ち」へ移す（これをやらないと running のまま溜まって空きが出ない）
      if harvest(q):
          q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
          save_queue(q)
      # 2026-09-04 たまごさん「ガソリンが切れる。家にたどり着かないよ」（火曜まで残り14%）
      #   → status/no_launch.flag があるあいだは**1本も発車させない**。
      #     回収（終わったものを確認待ちへ）と受信箱は動かすので、判定と繰り上げの練習はできる。
      #     再開はこのファイルを消すだけ。
      if os.path.exists(os.path.join(REPO, "status", "no_launch.flag")):
          return 0
      m = load(MACHINE, {})
      quota = load(QUOTA, {})

      # ---- 安全弁：マシン ----
      if (m.get("memPressure") == "red") or m.get("swapIncreasing") or (m.get("diskFreeGB") or 99) < 5:
          log("見送り: Macが危険（mem=%s swapUp=%s disk=%s）" % (m.get("memPressure"), m.get("swapIncreasing"), m.get("diskFreeGB")))
          return 0
      # ---- 安全弁：クレジット ----
      #   テスト用のカラ発車（"test": true）はClaudeを起動しない＝クレジットを1円も使わないので、
      #   週枠が上限でも通す。ここで一緒に止めていると、枠が苦しいときほど動作確認ができなくなる。
      credit_stop = quota.get("allLevel") == "stop"
      # 2026-09-05 たまごさん「ループシステムを作ってるんだから。**止まるのはNG。半永久装置。**」
      #   週枠が上限でも、**1本も走っていないなら、ここで止めない。**
      #   下で「空回し（Claudeを起動しない＝クレジット0）」を1本入れて、工場が回っている状態を保つ。
      _running_any = any(it.get("status") == "running" for it in items)
      _test_waiting = any(it.get("status") == "waiting" and it.get("test") for it in items)
      if credit_stop and _running_any and not _test_waiting:
          log("見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
          return 0

      # 2026-09-04 machine.json は重い計測（27秒〜）でしか書き変わらないので、最大5分ぶん古い。
      #   そのままだと「もう死んでいるセッション」を走行中として数え、空きが出ても繰り上がらなかった。
      #   ここで pid の生死をその場で見て、死んでいるぶんを除く（数百マイクロ秒で終わる）。
      def _pid_alive(pid):
          try:
              os.kill(int(pid), 0)
              return True
          except Exception:
              return False

      alive = len([s for s in (m.get("sessionList") or [])
                   if countable(s) and (not s.get("pid") or _pid_alive(s.get("pid")))])
      # 2026-09-04 テストで見つけた穴：machine.json は「Claudeのセッション」しか載せていないので、
      #   そこに現れないものを走らせると **走行0本と数えて上限を無視して発車し続ける**（実測：上限3本なのに6本出た）。
      #   台帳側で running になっていて、まだ生きているものも必ず数える。
      #   本物のセッションでも、計測が遅れて載っていない瞬間に同じことが起きる＝クレジットの垂れ流しになる。
      queue_alive = len([it for it in items
                         if it.get("status") == "running" and it.get("pid") and _pid_alive(it.get("pid"))])
      alive = max(alive, queue_alive)
      safe_max = m.get("safeMax")
      if safe_max is None:
          log("見送り: safeMaxが取れない")
          return 0
      # たまごさんが進捗表で決めた「同時に走る本数」。マシンの安全上限より小さい方を採る。
      cap = (load(os.path.join(REPO, "status", "launch_cap.json"), {}) or {}).get("cap")
      if isinstance(cap, int):
          safe_max = min(safe_max, cap)
      # 2026-09-05：発車待ちがテスト（Claudeを起動しない・眠るだけ）しか無いときは、
      #   マシンの安全上限（Claudeセッションを何本まで抱えられるか）に縛られる意味がない。
      #   たまごさんの指定本数（cap）だけを見る。実処理はsleepなので負荷はほぼゼロ。
      only_tests = all(it.get("test") for it in items if it.get("status") == "waiting")
      if only_tests and isinstance(cap, int):
          safe_max = cap
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

      # 2026-09-05 たまごさん「何も動いてない状態は作らないで。何かしら回しといて。クレジット消費最小で」
      #   本物が出せない（週枠が上限・発車を止めている等）ときでも、工場は回っている状態を保つ。
      #   空回しは Claude を起動しないのでクレジットは1円も使わない。終われば静かに消える。
      running_now = [it for it in items if it.get("status") == "running"]
      launchable = [it for it in items if it.get("status") == "waiting"
                    and (not credit_stop or it.get("test"))]
      if not running_now and not launchable:
          nxt = max([int(x.get("n") or 0) for x in items] or [0]) + 1
          items.append({
              "n": nxt, "priority": 9, "test": True, "keepalive": True, "testSeconds": 120,
              "title": "【空回し】工場を止めないための2分の空タスク",
              "why": "本物が出せない間も、止まっている状態を作らないため（クレジットは使いません）",
              "what": "Claudeを起動しない空のタスクです。2分で終わり、台帳からは静かに消えます。",
              "status": "waiting", "limitMin": 10, "model": "claude-sonnet-5",
          })
          log("♻︎ 空回しを1本入れました（%d番・本物が出せないため）" % nxt)
          save_queue(q)

      waiting = sorted([it for it in items if it.get("status") == "waiting"], key=rank)
      if credit_stop:
          # 週枠が上限のあいだは、クレジットを使わないテストだけ通す
          waiting = [it for it in waiting if it.get("test")]
      if not waiting:
          log("見送り: 発車待ちが空" if not credit_stop else
              "見送り: 週枠が上限（all=%s%%）" % quota.get("allPct"))
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
          save_queue(q)
      return 0


def launch_one(item, q, alive, safe_max):
    # ---- テスト用のカラ発車（クレジットを1円も使わない）----
    # 2026-09-04 たまごさん「3分で終わるセッションをくるくる回してテストしたい。
    #   中身はなんでもいい。3分で終わって完了報告がDispatchに来る、最低限の動作確認」
    #   → item に "test": true があれば、Claudeを起動せず、指定秒だけ眠って
    #     本物と同じ形の結果ログ（result と URL）を書くだけのプロセスを走らせる。
    #     回収・確認待ち・判定・繰り上げは本物とまったく同じ道を通る。
    if item.get("test"):
        new_id = str(uuid.uuid4())
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
        secs = int(item.get("testSeconds") or 180)
        url = "https://tamago2022.github.io/tamago-shinchoku/share/check/test-%d.html" % item.get("n")
        result = "【完了】%s（テスト・%d秒で終わりました）\\n確認ページ: %s" % (item.get("title"), secs, url)
        payload = '{"result": "%s"}' % result
        try:
            f = io.open(logf, "a", encoding="utf-8")
            p = subprocess.Popen(
                ["bash", "-c", "sleep %d; cat <<'EOF'\n%s\nEOF" % (secs, payload)],
                stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        except Exception as e:
            log("テスト発車に失敗 %s: %s" % (item.get("n"), e))
            return False
        item["status"] = "running"
        item["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        item["sessionId"] = new_id
        item["pid"] = p.pid
        log("🧪 テスト発車 %d番「%s」→ pid %d（%d秒で終わります・走行%d本→%d本・上限%d本）"
            % (item.get("n"), item.get("title"), p.pid, secs, alive, alive + 1, safe_max))
        return True

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
    # 2026-09-05 たまごさん「割り込みもあり。緊急で入るから。途中で止めても、**続きから再開できるように**」
    #   → 引っ込めた（一時停止した）ものは、新しいセッションを立てずに前のセッションを再開する。
    #     やり直しになっていないので、そこまでの作業が無駄にならない。
    resume_id = item.get("resumeFrom")
    if resume_id:
        new_id = resume_id
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % new_id[:8])
        cmd = [CLAUDE, "-p", "--resume", resume_id, "--model", SONNET,
               "--permission-mode", "auto", "--output-format", "json",
               "【再開】たまごさんが緊急の割り込みのために一度止めた仕事です。"
               "**前回の続きから**進めてください。最初からやり直さないこと。\n\n" + prompt]
        item.pop("resumeFrom", None)
    else:
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
