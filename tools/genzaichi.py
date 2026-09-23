#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""いまの現在地を1枚にする（status/genzaichi.md + status/genzaichi.json）。
Dispatchが会話の最初に必ず読む1枚。ルールではなく「今の状態」を書く。

2026-09-12 新設の理由：
  たまごさん「何も引き継がれてない。この現象が嫌だから何度も念を押したのに。二度と起こらぬよう仕組み化して」
  憲法の0番に「いまの現在地_チャット貼付用.md を読め（30分おき自動更新）」と書いてあったが、
  **そのファイルもGitHub版も生成スクリプトも存在しなかった。**
  そのせいで「Lovableの本番が5日止まっている」が誰にも引き継がれず、5日間放置された。

2026-09-12 22:26 たまごさんの「まだ直っていない」指摘を受けての改修（787番）：
  - 30分おき自動更新の実体が無かった → heartbeat.sh（心臓）に相乗りし、内部で1500秒ゲートして
    実質30分おきにだけ本体処理を走らせる（新しいlaunchd常駐は増やさない）。
  - 本番(Lovable)生死判定がClaudeサンドボックスからのurlopenで「Tunnel connection failed」を
    誤検知していた（実機のheartbeat.shから叩けば200が返ることを確認済み）→ リトライ3回＋
    タイムアウト短縮で一時的な失敗を吸収する。
  - 「今日の完了数」が常に0だった → queue.json の doneAt は誰も書いていない（実体はfinishedAt）。
    finishedAt と dispatch_outbox.jsonl の両方を突き合わせて数える。
  - 「まだ渡していない完成品」に同じ番号が2回出る／番号と無関係なURLが混ざる事故 →
    番号ごとに最後の1件だけを残し、URLのファイル名が自分の番号で始まっていないものは捨てる。
  - Vault（Obsidian）側にも新規ファイルとして同じ7項目を置く（既存ノートは1文字も触らない）。

2026-09-17 900番「仕組み⑨：引き継ぎで落ちない」での追記：
  - 「待っているもの（返事待ち・本人しかできないこと）」を新設。中身は802番で既に計算済みだった
    pending_decision_count（awaiting_check かつ origin=user）を、件数だけでなく実際の番号・題名まで
    レンダリングするようにした（今までjsonのpendingDecisionCountにしか出ておらず、genzaichi.md
    本体にはカウントすら出ていなかった）。
  - 「今週の残り枠」を新設。pace.json の remainWeek/daysLeft/perDayEven を使う（新しい計測は増やさない）。
  - 決定台帳 ai-brain/kettei.json（新設）と合わせて、「新しい担当は genzaichi.md と kettei.json の
    2つだけ読めば仕事に入れる」を狙う。ルール（憲法）はREADME.mdに置いたまま、数字の実体
    （バッジ28%等）はkettei.jsonへ集約し、根拠になった実物（画像）を必ず紐づける
    （「実物は文書より強い」＝akikoのSpartacusバッジを文書の古い数字に合わせて縮めてしまった
    事故の再発防止）。
"""
import io, json, os, re, glob, subprocess, datetime, urllib.request, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status")
# 797番：テスト時にモンキーパッチできるよう、書き込み先をモジュール変数として出しておく
# （本番はstatus/配下、テストはtempディレクトリに差し替えて実行し、本番の受信箱を汚さない）。
DISPATCH_OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
FAILURES_MD = os.path.join(ST, "failures.md")
JST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(JST)

# ---- heartbeat.sh に相乗りする時のゲート（新しい常駐は増やさない・2026-09-12） ----
# heartbeat.sh は15秒おきに全部を叩きに来るので、ここで「1500秒（25分）経っていなければ
# 何もせず即終了」にして、実質30分おきの動作にする。単体で手動実行した時は
# GENZAICHI_FORCE=1 で常に本体を走らせる（検証・逆テスト用）。
GATE = os.path.join(ST, ".genzaichi_last_run")
def gate_ok():
    if os.environ.get("GENZAICHI_FORCE") == "1":
        return True
    try:
        age = time.time() - os.path.getmtime(GATE)
        if age < 1500:
            return False
    except FileNotFoundError:
        pass
    return True

def touch_gate():
    try:
        with open(GATE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def jread(p, d=None):
    try:
        with open(os.path.join(ST, p), encoding="utf-8") as f: return json.load(f)
    except Exception: return d if d is not None else {}


def deploy_key(raw):
    """x-deployment-idは 'psr2.<デプロイUUID>.<リクエストごとのタイムスタンプ>.<リクエストごとのハッシュ>'
    という形で、末尾2つはリクエストごとに毎回変わる（実測: 同じ本番に3回HEADを打つと3回とも
    末尾が別の値になった＝生の文字列を丸ごと比較すると『毎回デプロイが変わった』と誤判定し、
    本番が止まっていても永遠に緑になるバグがあった。2026-09-12 787番で発見・修正）。
    実際にデプロイが変わった時だけ変化する真ん中のUUID部分だけを取り出して比較する。"""
    if not raw:
        return raw
    parts = raw.split(".")
    return parts[1] if len(parts) >= 2 else raw


def deploy_alive():
    """本番(Lovable)が生きているか。x-deployment-id（の安定部分＝deploy_key）を前回と比べる。
    一時的な網の詰まり（プロキシ切断・タイムアウト）で誤って赤にしないよう3回まで試す。"""
    url = "https://joy-relief-station.lovable.app/"
    did = None
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "genzaichi/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                did = r.headers.get("x-deployment-id") or r.headers.get("x-nf-request-id") or ""
            break
        except Exception as e:
            last_err = e
            time.sleep(2)
    hist_p = os.path.join(ST, "deploy_history.json")
    try:
        hist = json.load(open(hist_p, encoding="utf-8"))
    except Exception:
        hist = {}
    if did is None:
        # 3回とも失敗。ただし前回の記録が新しければ「たぶんまだ生きている」扱いにせず、
        # 正直に「確認できず」を返す（でっち上げない）。
        return None, "取得できず(%s)" % str(last_err)[:40]
    key = deploy_key(did)
    last_key = hist.get("key") or deploy_key(hist.get("id"))  # 旧形式(id生値)からの移行
    last_at = hist.get("at")
    if key and key != last_key:
        hist = {"id": did, "key": key, "at": now.isoformat(), "prevKey": last_key}
        json.dump(hist, open(hist_p, "w", encoding="utf-8"), ensure_ascii=False)
        return 0.0, did
    if last_at:
        try:
            h = (now - datetime.datetime.fromisoformat(last_at)).total_seconds() / 3600
            return h, did
        except Exception: pass
    # 履歴が無い最初の1回。今の値を基準として保存する。
    hist = {"id": did, "key": key, "at": now.isoformat()}
    json.dump(hist, open(hist_p, "w", encoding="utf-8"), ensure_ascii=False)
    return 0.0, did


def child_costs_today():
    tot = 0.0; n = 0
    today = now.strftime("%Y-%m-%d")
    for f in glob.glob(os.path.join(ST, "auto-launch-*.log")) + [os.path.join(ST, "auto_launch.log")]:
        try: lines = open(f, encoding="utf-8", errors="ignore").read().split("\n")
        except Exception: continue
        cur = False
        for ln in lines:
            if re.match(r"=== " + today + r" ", ln): cur = True
            m = re.search(r'"total_cost_usd":([0-9.]+)', ln)
            if m and cur:
                tot += float(m.group(1)); n += 1; cur = False
    return n, tot


def done_today_ns(items):
    """今日finishedAt（実体。doneAtは誰も書いていない）を持つ番号 と
    dispatch_outbox.jsonlでtoday+ok報告済みの番号 を合わせて数える（片方が欠けても取り漏らさない）。"""
    today = now.strftime("%Y-%m-%d")
    ns = set()
    for x in items:
        if x.get("status") != "done":
            continue
        # ★1055番（2026-09-24）機械が自動で畳んだ票を「今日の完了」に数えない。
        #   自動検知・憲法点検が出したチケットは、見張りの対象が元に戻れば機械が閉じる。
        #   それは**誰も何も作っていない**ので、完了の本数に混ぜると数字が嘘になる。
        if "自動で閉じました" in (x.get("doneNote") or ""):
            continue
        if x.get("test") or x.get("keepalive"):
            continue
        d = str(x.get("finishedAt") or x.get("doneAt") or x.get("updatedAt") or "")[:10]
        if d == today:
            ns.add(x.get("n"))
    try:
        for line in open(os.path.join(ST, "dispatch_outbox.jsonl"), encoding="utf-8"):
            try: d = json.loads(line)
            except Exception: continue
            if d.get("ok") and str(d.get("ts", ""))[:10] == today:
                ns.add(d.get("n"))
    except Exception:
        pass
    return ns


def _reported_ns():
    """802番（2026-09-14）修正：このファイルは長らく "reported" キーを読んでいたが、
    dispatch_reported.json の実際のキーは "ns"（tools/dispatch_arrivals.pyが書く形）。
    ずっと空集合が返り続けており、既に報告済みの番号まで「まだ渡していない完成品」に
    混ざって出ていた（実例：検品NG済みの750番がunreportedDoneに出ていた）。
    正本は追記式の dispatch_reported.jsonl（802番で新設）。旧.jsonも保険として合わせて読む。"""
    ns = set()
    try:
        with io.open(os.path.join(ST, "dispatch_reported.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row.get("n"), int):
                    ns.add(row["n"])
    except Exception:
        pass
    try:
        data = json.load(open(os.path.join(ST, "dispatch_reported.json"), encoding="utf-8"))
        if isinstance(data, dict):
            ns.update(n for n in (data.get("ns") or []) if isinstance(n, int))
    except Exception:
        pass
    return ns


def unreported_completions():
    """まだ渡していない完成品。同じ番号は最後の1件だけ、URLのファイル名が
    自分の番号で始まっていないもの（番号違いのURL誤記録）は捨てる。"""
    today = now.strftime("%Y-%m-%d")
    rep = _reported_ns()
    picked = {}
    try:
        for line in open(os.path.join(ST, "dispatch_outbox.jsonl"), encoding="utf-8"):
            try: d = json.loads(line)
            except Exception: continue
            if not d.get("ok") or d.get("n") in rep:
                continue
            urls = [x for x in (d.get("urls") or []) if "share/" in x or "lovable.app" in x]
            if not urls:
                continue
            n_ = d.get("n")
            good = [u for u in urls if os.path.basename(u).split("-", 1)[0] == str(n_)]
            u_ = good[0] if good else urls[0]
            picked[n_] = (n_, (d.get("title") or "")[:40], u_, str(d.get("ts", ""))[:10])
    except Exception:
        pass
    ordered = sorted(picked.values(), key=lambda t: t[3])
    return [(n_, t_, u_) for n_, t_, u_, _ in ordered]


# ---- 797番：「発車0本が10分続いていないか」の検知＋自己復旧 ----
# 実測（2026-09-13）：05:26〜05:42の16分間、auto_launcher.pyが45秒killを14回連続で
# 食らい、その間ずっと発車0本だった。心臓（heartbeat.sh）自体は「動いています」ログを
# 出し続けており、既存の7項目（★止まっていないか）だけでは検知できなかった
# （心臓のプロセスが生きている＝正常、という判定だったため）。
# 「発車」は auto_launcher.py が本物・空回しテスト問わず何か1本着火するたびに
# status/.last_launch_at を書き換える（798番=auto_launcher.py側で実装）。
# 発車待ちが空でクレジットも十分な「本当に出すものが無い」状態でも、
# 安全弁（credit_stop×running_any=false時）は必ず2分ごとに空回しタスクを1本入れる設計
# なので、10分間1本も出ないのは異常の強いシグナルとして扱ってよい。
LAST_LAUNCH_STAMP = os.path.join(ST, ".last_launch_at")
LAUNCH_SILENCE_ALERT_STAMP = os.path.join(ST, ".launch_silence_alerted_at")


# ---- 1018番（2026-09-22）「走った」と「取れた」を別々に数える ----
# たまごさん「走った回数と実際に取れた回数を両方数える。走った>0 なのに 取れた=0 は赤」
#
# 実測でこうなっていた（status/auto_launch.log 全体・2026-09-21 04:42〜09-22 06:45）：
#   空回し発車(🧪) 316本 ／ 本物の発車(🚀) **0本** ／ 見送り「ログインが切れています」2453回
#   ＝ **26時間、本物の仕事が1本も出ていない。**
# ところが同じ時間、この紙は「✅ 発車：10分以内に動いている」と緑で出し続けていた。
# 理由は上の223行のコメントに書いてあるとおり、`.last_launch_at` を
# **本物・空回しテストを問わず**書き換える設計だから。空回しは2分ごとに必ず入るので、
# この緑は「工場が動いている」ではなく「空回しが入った」しか意味していなかった。
# ＝ 動いているのに何も取れていない、という一番たちの悪い壊れ方を、
#   自分で緑に塗って隠していた。憲法で言えば嘘のログ。
#
# 穴を塞がない（空回しを静かにする等）。**何をもって「工場が動いている」とするかの素材を替える。**
# 緑の根拠を「着火があったか」から「**本物が取れたか**」に置き換える。
# 空回しは1本も数に入れない。取れた=0 なら、何本空回ししていようが赤。
AUTO_LAUNCH_LOG = os.path.join(ST, "auto_launch.log")


def toreta_line():
    """★止まっていないかの一番上に出す1行。ここが赤なら工場は何も産んでいない。

    **判定はここに書かない。**tools/hantei.py が唯一の判定。
    同じ規則を2か所に書くと、片方だけ直る日が必ず来る（実際そうなっていた）。
    """
    try:
        import hantei
        return hantei.kojo_line(6)
    except Exception as e:  # noqa: BLE001
        # 読めなかったことを黙って飲み込まない。緑にもしない。
        return "- ⚠️ **稼ぎ：判定(tools/hantei.py)が読めません：%s**" % e


def launch_silence_min():
    try:
        age = time.time() - os.path.getmtime(LAST_LAUNCH_STAMP)
        return age / 60.0
    except FileNotFoundError:
        return None  # まだ一度も発車したことが無い（新規環境）。異常とは扱わない


def _launch_has_room():
    """走行本数が安全上限（safeMax）未満か＝新規発車の余地があるかを判定する。

    894番（2026-09-16）で見つけた誤検知：安全弁の空回しタスクは
    `running_now=[]かつlaunchable=[]`の時にしか追加されない（auto_launcher.py）。
    つまり「発車待ちはあるが、走行本数が既に上限いっぱい」という**正当な満員状態**では
    空回しタスクも入らず、.last_launch_at が10分を超えて更新されないことが普通に起こる。
    それを毎回「異常」として扱うと、満員で待っているだけの正常時にまで自己修復
    （心臓/5分便の蹴り直し）を誤爆させてしまう（実機で確認：走行4本／上限4本の満員中に
    18分沈黙で誤って「異常」判定・自己修復が動いた）。
    machine.json.safeMax が取れない間は、auto_launcher.py 側の安全な既定値と同じ3本を使う
    （894番の別項目「測れないときに止まらない」との一貫性）。"""
    try:
        m = json.load(io.open(os.path.join(ST, "machine.json"), encoding="utf-8"))
    except Exception:
        m = {}
    safe_max = m.get("safeMax")
    if safe_max is None:
        safe_max = 3
    alive = m.get("sessions")
    if alive is None:
        return True  # 走行本数も分からない→安全側（余地ありとみなし、通常どおり沈黙を疑う）
    return alive < safe_max


def _self_heal_launch_silence(silence_min):
    """止まっていたら、たまごさんに言われる前に自分で立て直しを試みる。
    やること（既存の安全な手段だけを使う。新しい破壊的操作はしない）：
      ① heartbeat.sh のPIDが死んでいれば立て直す（machine_status_push.shと同じ判定・同じ起動コマンド）。
      ② no_launch.flag が「ログインが切れています」以外の理由で残ったままなら、
         中身をログへ残すだけにする（正当性が読み取れないものを機械で勝手に消すのは危険なので、
         消すところまではやらず、Dispatchへの通知に理由を含めて人の目で判断できるようにする）。
    戻り値：実際に行った手当ての説明（1行、日本語）。何もできなければその理由。"""
    actions = []
    hbpid_path = os.path.join(ST, "heartbeat.pid")
    hb_alive = False
    try:
        pid = int(io.open(hbpid_path, encoding="utf-8").read().strip())
        os.kill(pid, 0)
        hb_alive = True
    except Exception:
        hb_alive = False
    if not hb_alive:
        try:
            subprocess.Popen(
                ["bash", os.path.join(REPO, "tools", "heartbeat.sh")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
            actions.append("心臓(heartbeat.sh)のPIDが死んでいたので立て直しました")
        except Exception as e:
            actions.append("心臓の立て直しを試みましたが失敗: %s" % str(e)[:100])
    else:
        try:
            # 2026-09-17（894番）：高負荷下（実機実測 load 10.9・スワップ6.9GB）で
            # launchctl kickstart 自体が10秒でタイムアウトすることを確認した
            # （launchdへの応答も遅れるほどの負荷では10秒は短すぎる）。20秒へ延ばす。
            subprocess.run(
                ["launchctl", "kickstart", "-k", "gui/%d/com.tamago.machine-status" % os.getuid()],
                capture_output=True, timeout=20,
            )
            actions.append("心臓は生きていたので、5分便(machine-status)へ蹴り直しを依頼しました")
        except Exception as e:
            actions.append("5分便の蹴り直しを試みましたが失敗: %s" % str(e)[:100])
    flag_path = os.path.join(ST, "no_launch.flag")
    if os.path.exists(flag_path):
        try:
            content = io.open(flag_path, encoding="utf-8").read().strip()
        except Exception:
            content = "(読めず)"
        actions.append("no_launch.flagが残っています（内容：%s）。正当な理由か人の目で確認してください" % content[:120])
    return "／".join(actions) if actions else "手当てできる対象が見つかりませんでした"


def check_launch_silence():
    """10分間発車が無ければ赤で報告し、その場で立て直しを試みる。
    連続して赤の間は1回だけ dispatch_outbox・failures.md へ書く（毎30分スパムしない）。
    発車が再開したら次の沈黙エピソードのためにアラート済みスタンプを消す。"""
    silence_min = launch_silence_min()
    if silence_min is None or silence_min <= 10 or _launch_has_room() is False:
        try:
            if os.path.exists(LAUNCH_SILENCE_ALERT_STAMP):
                os.remove(LAUNCH_SILENCE_ALERT_STAMP)
        except Exception:
            pass
        return None
    already_alerted = os.path.exists(LAUNCH_SILENCE_ALERT_STAMP)
    heal_msg = _self_heal_launch_silence(silence_min)
    if not already_alerted:
        try:
            with open(LAUNCH_SILENCE_ALERT_STAMP, "w") as f:
                f.write(now.isoformat())
        except Exception:
            pass
        msg = ("🛑発車が%.0f分止まっていました。見つけて自分で直しました：%s" % (silence_min, heal_msg))
        try:
            row = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "launch-silence-%s" % now.strftime("%Y%m%d%H%M"),
                "type": "launch_silence_self_heal",
                "title": "発車0本が10分以上続いた",
                "message": msg,
                "silenceMin": round(silence_min, 1),
            }
            with io.open(DISPATCH_OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass
        try:
            with io.open(FAILURES_MD, "a", encoding="utf-8") as f:
                f.write(
                    "\n\n---\n\n## 797番自動記録：発車が%.0f分止まっていたので自分で直しました\n\n"
                    "- **症状**：status/.last_launch_at が%.0f分更新されておらず、10分ルールに抵触しました。\n"
                    "- **対応**：%s\n"
                    "- **日付**：%s\n"
                    % (silence_min, silence_min, heal_msg, now.strftime("%Y-%m-%d %H:%M"))
                )
        except Exception:
            pass
    return "🔴 **発車：%.0f分 沈黙**（見つけて直しました：%s）" % (silence_min, heal_msg)


def write_vault_mirror(md_text):
    """Vault（Obsidian）側にも同じ7項目を置く。既存ノートは1文字も触らない＝新規ファイルのみ。
    iCloudが同期待ちで読めない等は静かに諦める（本体の出力には影響させない）。"""
    try:
        vault_rules = os.path.expanduser(
            "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/AI出力/_ルール"
        )
        if not os.path.isdir(vault_rules):
            return "skip: vault dir not found"
        out = os.path.join(vault_rules, "工場の生死7項目_自動生成.md")
        header = ("<!-- 自動生成・新規ファイル。既存ノートは書き換えない。生成元: "
                   "tamago-shinchoku/tools/genzaichi.py（heartbeat.sh相乗り・実質30分おき） -->\n\n")
        with open(out, "w", encoding="utf-8") as f:
            f.write(header + md_text)
        return "ok"
    except Exception as e:
        return "error: %s" % str(e)[:120]


def run_stale_marker_and_get_red_flags():
    """933番(7/7)：tools/stale_marker.py（awaiting_check件数の見張り＋7日以上停滞の印付け）を
    この相乗りタイミングでついでに走らせ、赤旗行を作る。新しい常駐プロセスは追加しない
    （run_shikumi_and_get_red_flags()と同じ、既存heartbeat.sh 30分おきゲートへの相乗り）。"""
    try:
        subprocess.run(
            ["python3", os.path.join(REPO, "tools", "stale_marker.py")],
            cwd=REPO, capture_output=True, timeout=60,
        )
    except Exception as e:
        return ["stale_marker：実行に失敗しました(%s)" % str(e)[:80]]
    s = jread("stale_summary.json", {})
    lines = []
    n_check = int(s.get("awaitingCheckCount") or 0)
    if s.get("awaitingCheckOverLimit"):
        lines.append("確認待ちが%d件（10件超）たまっています。鬼監督で仕分けてください" % n_check)
    red = s.get("red") or []
    if red:
        top = "・".join("%s番(%s日)" % (r.get("n"), r.get("ageDays")) for r in red[:5])
        more = "、他%d件" % (len(red) - 5) if len(red) > 5 else ""
        lines.append("7日以上動いていない案件が%d件：%s%s" % (len(red), top, more))
    return lines


def run_shikumi_and_get_red_flags():
    """799番：仕組みの生死表（tools/shikumi.py）を、この相乗りタイミングでついでに走らせる。
    新しい常駐プロセスは作らない——既存のheartbeat.sh 30分おきゲート（このgenzaichi.build()自体の
    ゲート）にそのまま乗せる。サブプロセスで独立実行するので、shikumi.py側で何が起きても
    genzaichi本体の出力（進捗表1画面目）を壊さない。"""
    try:
        subprocess.run(
            ["python3", os.path.join(REPO, "tools", "shikumi.py")],
            cwd=REPO, capture_output=True, timeout=90,
        )
    except Exception as e:
        return ["仕組みの生死表：実行に失敗しました(%s)" % str(e)[:80]]
    data = jread("shikumi.json", {})
    return list(data.get("redFlags") or [])


def build():
    try:
        import sys
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import shukan_haibun as _shukan_haibun
        _haibun = _shukan_haibun.build_haibun()
    except Exception:
        _haibun = None

    q = jread("queue.json", {"items": []}); items = q.get("items") or []
    # 802番（2026-09-14）：「たまごさんのOK待ち（判断待ち）」件数。
    #   index.html側の checkSec は details が開かれた時しかqueue.jsonを取りに行かない
    #   （軽さ優先の既存設計）ため、「一番上に常に出す」バナーはこのgenzaichi.json（既に
    #   ページ最上部で常時読まれている）に相乗りさせる。判定は renderCheck() と同じ条件。
    pending_decision_items = [
        x for x in items if x.get("status") == "awaiting_check" and x.get("origin") == "user"
    ]
    pending_decision_count = len(pending_decision_items)
    h = jread("health.json"); p = jread("pace.json")
    today = now.strftime("%Y-%m-%d")
    done_ns = done_today_ns(items)
    running = [x for x in items if x.get("status") == "running"]
    running_count = len(running)  # health.jsonのsessionsはmachine_load.sh依存で壊れると0になる→queue.jsonの実数を正とする
    try:
        # Python 3.9のfromisoformatは health.json の "+0900"(コロン無し)形式を読めないためstrptimeを使う
        h_measured = datetime.datetime.strptime(h.get("measuredAt"), "%Y-%m-%dT%H:%M:%S%z")
        health_age_min = (now - h_measured).total_seconds() / 60
    except Exception:
        health_age_min = None
    safe_max_display = "測定できていません" if (health_age_min is None or health_age_min > 40) else h.get("safeMax")
    waiting = [x for x in items if x.get("status") == "waiting"]
    p1 = [x for x in waiting if x.get("priority") == 1]
    n_child, cost = child_costs_today()
    avg = (cost / n_child) if n_child else 0.0
    dep_h, dep_id = deploy_alive()

    hb = os.path.join(ST, "heartbeat.log")
    try:
        hb_min = (now - datetime.datetime.fromtimestamp(os.path.getmtime(hb), JST)).total_seconds() / 60
    except Exception:
        hb_min = None

    red_flags = []
    if dep_h is None:
        red_flags.append("本番(Lovable)：確認できず — %s" % dep_id)
    elif dep_h > 24:
        red_flags.append("本番(Lovable)：%.0f時間 更新なし" % dep_h)
    if hb_min is None:
        red_flags.append("心臓：ログが読めない")
    elif hb_min > 10:
        red_flags.append("心臓：%.0f分 沈黙" % hb_min)
    launch_silence_line = check_launch_silence()
    if launch_silence_line:
        red_flags.append(launch_silence_line.replace("🔴 **", "").replace("**", ""))

    # 799番：仕組みの生死表（dead判定・waiting3日超放置）もここで合流させる。
    # 新しいUIコードは書かず、既存のred_flags描画（genzaichi.md／genzaichi.jsonのredFlags）に乗せる。
    shikumi_lines = run_shikumi_and_get_red_flags()
    red_flags.extend(shikumi_lines)
    stale_lines = run_stale_marker_and_get_red_flags()
    red_flags.extend(stale_lines)

    L = []
    A = L.append
    A("# いまの現在地（%s 時点・自動生成・実質30分おき）" % now.strftime("%m-%d %H:%M"))
    try:
        import sys
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import konshu_mitai as _konshu_mitai
        if _konshu_mitai.need_ask():
            A("")
            A("⚠️ **今週見たいものを3つ教えてください**（`status/konshu_mitai.json`が空です）")
    except Exception:
        pass
    A("")
    A("**Dispatchは会話の最初に、返事をする前にこの1枚を読む。ルールではなく『今の状態』がここにある。**")
    A("")
    A("## ★止まっていないか（ここが赤なら他を全部止めてでも直す）")
    # 1018番：一番上は「本物が取れているか」。他の行が全部緑でも、ここが赤なら工場は無産。
    A(toreta_line())
    if dep_h is None:
        A("- 🔴 **本番(Lovable)：確認できず** — %s" % dep_id)
    elif dep_h > 24:
        A("- 🔴 **本番(Lovable)：%.0f時間 更新なし** ← コードを直しても画面は変わらない。最優先で復旧" % dep_h)
    else:
        A("- ✅ 本番(Lovable)：%.1f時間前に更新あり" % dep_h)
    if hb_min is None:
        A("- ⚠️ 心臓：ログが読めない")
    elif hb_min > 10:
        A("- 🔴 **心臓：%.0f分 沈黙**" % hb_min)
    else:
        A("- ✅ 心臓：%.0f分前に動いた" % hb_min)
    if launch_silence_line:
        A("- %s" % launch_silence_line)
    else:
        # 1018番：この緑は「着火があった」しか意味しない（空回しでも点く）。
        # 工場が産んでいるかどうかは上の「稼ぎ」の行が答える。ここで誤解させない。
        A("- ✅ 着火：10分以内に動いている（空回しを含む。産んだ本数は上の「稼ぎ」を見る）")
    # ★2026-09-24（命綱）：tools/inochi.py が「自分では絶対に直せない」と判定した1点だけ、
    #   ここに出す。それ以外（runner・トンネル・index.lock・列の積み直し等）はあちらが
    #   黙って直すので、ここには出さない。人に見せる＝人の手が要るとき、に意味を寄せる。
    try:
        import inochi as _inochi
        for _l in _inochi.aka_lines():
            A("- 🔴 **【人の手が要る】%s**" % _l)
    except Exception:
        pass
    for line in shikumi_lines:
        A("- 🔴 **%s**" % line)
    for line in stale_lines:
        A("- 🔴 **%s**" % line)
    A("")
    A("## 数字")
    A("- 走行 **%s / %s**（発車待ち %d件・うちP1 %d件）" % (running_count, safe_max_display, len(waiting), len(p1)))
    A("- 今日の完了 **%d件**（9/06のピークは60件。20件を切ったら何かが詰まっている）" % len(done_ns))
    A("- 今日の子セッション **%d本・合計 $%.2f・1本平均 $%.2f**%s" % (n_child, cost, avg, "  ← 🔴 $3超は異常" if avg > 3 else ""))
    A("- クレジット 今日 **%s / %s**・週 **%s%%**" % (p.get("usedToday"), p.get("budgetToday"), p.get("allPct")))
    if p.get("remainWeek") is not None:
        A("- 今週の残り枠 **%.0f%%**（あと%.1f日・1日目安%.1f%%）" % (
            p.get("remainWeek") or 0, p.get("daysLeft") or 0, p.get("perDayEven") or 0))
    if _haibun:
        A("- 今週の配分：見たいもの %.0f%% / 裏方 %.0f%% / 予備 %.0f%%%s" % (
            _haibun.get("mitaiPct", 0), _haibun.get("urakataPct", 0), _haibun.get("yobiPct", 0),
            "  🔴逆転" if _haibun.get("reversed") else ""))
    else:
        A("- 今週の配分：未計測")
    A("")
    A("## 今すぐ走っているもの")
    if running:
        for x in running:
            st = x.get("startedAt") or x.get("launchedAt") or ""
            el = ""
            try:
                secs = (now - datetime.datetime.fromisoformat(st)).total_seconds()
                el = "（%.1fh%s）" % (secs / 3600, " ★3時間超" if secs > 10800 else "")
            except Exception: pass
            A("- %s %s%s" % (x.get("n"), (x.get("label") or "")[:44], el))
    else:
        A("- **0本**（クレジットが残っているなら、これは異常）")
    A("")
    A("## 次に出る（P1の先頭5件）")
    for x in sorted(p1, key=lambda y: -(y.get("n") or 0))[:5]:
        A("- %s %s" % (x.get("n"), (x.get("label") or "")[:48]))
    A("")
    A("## 待っているもの（返事待ち・本人しかできないこと）")
    if pending_decision_items:
        A("- 件数 **%d件**（たまごさんの確認・OK待ち）" % pending_decision_count)
        for x in sorted(pending_decision_items, key=lambda y: -(y.get("n") or 0))[:5]:
            A("- %s %s" % (x.get("n"), (x.get("title") or "")[:48]))
        if pending_decision_count > 5:
            A("- 他 %d件（進捗表の『判断待ち』欄で全件見られる）" % (pending_decision_count - 5))
    else:
        A("- なし")
    A("")
    A("## まだ渡していない完成品")
    unrep = unreported_completions()
    if unrep:
        for n_, t_, u_ in unrep[-8:]:
            A("- %s %s" % (n_, t_)); A("  %s" % u_)
    else:
        A("- なし")
    A("")
    A("## 未解決の失敗（924番・引き継ぎで見落とすな）")
    try:
        import failures_ledger as _fl
        _entries = _fl.load_all()
        _open = _fl.list_open(_entries)
        _recur = [e for e in _open if (e.get("recurrence") or 0) >= 1]
        if _open:
            A("- 未解決 **%d件**（うち再発 **%d件**）── `python3 tools/failures_ledger.py --list-open`"
              % (len(_open), len(_recur)))
            for e in sorted(_open, key=lambda x: x.get("date", ""), reverse=True)[:3]:
                A("- %s %s" % (e.get("id"), (e.get("what") or "")[:56]))
        else:
            A("- なし（すべて再発防止まで潰し済み）")
    except Exception as _e:
        A("- （failures_ledger読み込み失敗: %s）" % _e)
    A("")
    A("---")
    A("*このファイルは tools/genzaichi.py が自動生成する。手で書き換えない。*")

    md = "\n".join(L) + "\n"
    out = os.path.join(ST, "genzaichi.md")
    with open(out, "w", encoding="utf-8") as f: f.write(md)

    # 進捗表（GitHub Pages）が読む機械可読版。同じ7項目をJSONでも出す。
    payload = {
        "generatedAt": now.isoformat(),
        "redFlags": red_flags,
        "deploy": {"hoursSinceUpdate": dep_h, "deploymentId": dep_id},
        "heartbeatSilentMin": hb_min,
        "launchSilentMin": round(launch_silence_min() or 0, 1) if launch_silence_min() is not None else None,
        "running": {"count": running_count, "safeMax": safe_max_display},
        "waitingCount": len(waiting),
        "pendingDecisionCount": pending_decision_count,  # 802番：たまごさんのOK待ち件数
        "pendingDecisionItems": [  # 900番：待っているもの（返事待ち・本人しかできないこと）を一覧でも
            {"n": x.get("n"), "title": (x.get("title") or "")[:48]}
            for x in sorted(pending_decision_items, key=lambda y: -(y.get("n") or 0))[:5]
        ],
        "weekRemainPct": p.get("remainWeek"),  # 900番：今週の残り枠
        "p1Count": len(p1),
        "doneToday": len(done_ns),
        "childSessionsToday": n_child,
        "costToday": round(cost, 2),
        "avgCostPerChild": round(avg, 2),
        "creditToday": {"used": p.get("usedToday"), "budget": p.get("budgetToday")},
        "creditWeekPct": p.get("allPct"),
        "runningNow": [
            {"n": x.get("n"), "label": (x.get("label") or "")[:44]} for x in running
        ],
        "nextP1": [
            {"n": x.get("n"), "label": (x.get("label") or "")[:48]}
            for x in sorted(p1, key=lambda y: -(y.get("n") or 0))[:5]
        ],
        "unreportedDone": [
            {"n": n_, "title": t_, "url": u_} for n_, t_, u_ in unrep[-8:]
        ],
        "weekHaibun": _haibun,
    }
    with open(os.path.join(ST, "genzaichi.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    vault_status = write_vault_mirror(md)
    print("wrote", out, "and genzaichi.json / vault:", vault_status)
    return md


def main():
    if not gate_ok():
        return  # heartbeat.shの15秒ループに相乗り。25分未満なら何もしない。
    touch_gate()
    build()


if __name__ == "__main__":
    main()
