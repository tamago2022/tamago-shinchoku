#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番【本丸】工場側の代行係 — サンドボックスの代わりに外部AIを叩く。

■ なぜ要るか（2026-09-18 実測）
  Cowork/Dispatch のサンドボックスからは api.openai.com / api.x.ai /
  generativelanguage.googleapis.com に**回線が出ない**（名前解決で落ちる）。
  たまごさんのMac（＝工場）からは**出る**（tools/kenpin_gate.py が実際に往復している）。
  だから「外部AIを叩くコード」は工場側で動かす。この1本がその窓口。

■ 動き方（新しいlaunchd常駐は増やさない＝既存方針）
  tools/machine_status_push.sh の 15秒おきの軽い巡回（quick_tick）から呼ばれる。
  status/gaibu_jobs/pending/ が空なら**数ミリ秒で何もせず終わる**ので、工場は重くならない。

■ 仕事の種類
  kiku   … tools/kiku.py   の run_job（3社に同じ前提で聞く）
  tanomu … tools/tanomu.py の run_job（リサーチ・画像などの成果物を作らせる）

■ 二重起動しない
  status/gaibu_jobs/.runner.lock を見る。古い（10分超）ロックは壊れたものとみなして奪う。
"""
import argparse
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402

LOCK = os.path.join(gkuchi.JOBS_DIR, ".runner.lock")
RUNLOG = os.path.join(REPO, "status", "gaibu_runner.log")
LOCK_STALE_SEC = 600

# =====================================================================
# ★2026-09-23：どの仕事にも「壁掛け時計」を付ける（2回目の同じ不具合なので仕組みを替える）
# ---------------------------------------------------------------------
# 何が起きたか（実測）：
#   11:32:10 `kakunin`（出したページが200で見えるか叩くだけ・60秒で終わるはず）を開始 →
#   9分以上返らない。うしろに6件が並んだまま。**公開が黙って出ない。**
#   同じ症状が今日だけで2回。
# なぜ起きるか（構造）：
#   仕事の中身を **この1本のプロセスの中で import して呼んでいる**。
#   中で socket が返らなければ、runner ごと永久に止まる。
#   subprocess で呼んでいる種類（recon・ghwatch）には timeout が付いているのに、
#   **import して呼ぶ種類には時間の上限が1つも無かった。**
#   ＝「止まらない仕事」を作れてしまう作りだった。
# だからこうする：
#   種類ごとに上限秒を決め、**超えたら例外にして殺し、理由を残して次へ行く。**
#   ★黙って飲み込まない（no_credential と同じ扱いで、必ず結果に書く）。
#   ★止まった1本のせいで列が死なない。これが「黙って出ない」の再発を止める形。
import signal  # noqa: E402

JOB_TIMEOUT = {
    "kakunin": 90,     # GETで200を見るだけ。90秒かかる理由が無い
    "keijiban": 90,
    "daicho": 120,
    "ghwatch": 150,
    "recon": 150,
    "diag": 90,
    "douga": 90,
    "horu": 240,
    "jrsdata": 180,
    "jrspush": 180,
    "oausage": 90,
    "watashi": 420,    # 1048番 渡す前の門。本物のブラウザで開いて押すので長め
    "sumaho": 330,     # 1043番 スマホの門。ブラウザを起こして4回押すので長め
    "zandaka": 180,    # 1034番 財布の残高。GET7本＋CLI2本。1本15秒の上限つき
}
JOB_TIMEOUT_DEFAULT = 180


class JobTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise JobTimeout()


def _job_limit(job):
    try:
        v = (job.get("payload") or {}).get("timeoutSec")
        if v:
            return max(5, min(int(v), 600))
    except Exception:
        pass
    return JOB_TIMEOUT.get(job.get("kind"), JOB_TIMEOUT_DEFAULT)


def _arm(sec):
    """上限秒を仕掛ける。仕掛けられない場所（メインスレッド以外）では黙って何もしない。"""
    try:
        signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(int(sec))
        return True
    except Exception:
        return False


def _disarm():
    try:
        signal.alarm(0)
    except Exception:
        pass


def _log(msg):
    try:
        with io.open(RUNLOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _take_lock():
    os.makedirs(gkuchi.JOBS_DIR, exist_ok=True)
    if os.path.exists(LOCK):
        try:
            age = time.time() - os.path.getmtime(LOCK)
        except Exception:
            age = 0
        # ★中身が「released」なら、消せなかっただけの抜け殻。塞いでいない。
        try:
            head = io.open(LOCK, encoding="utf-8").read(16)
        except Exception:
            head = ""
        if not head.startswith("released") and age < LOCK_STALE_SEC:
            return False
        if not head.startswith("released"):
            _log("古いロック(%.0f秒)を奪いました" % age)
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write("%d %s\n" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S")))
        return True
    except Exception:
        return False


def _release_lock():
    """ロックを外す。
    ★2026-09-18 実測：Cowork(サンドボックス)のマウント越しだと os.remove が通らないことがある
    （.git の index.lock が片付けられなかったのと同じ現象・tools/git_lock_reaper.py の経緯）。
    消せなかった場合に次の起動が門前払いされ続けると、窓口が丸ごと死ぬ。
    そこで **消せなければ更新時刻を大昔にする**。上の _take_lock() は経過時間で
    「壊れたロック」と判定して奪うので、どちらに転んでも詰まらない。"""
    try:
        os.remove(LOCK)
        return
    except Exception:
        pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write("released %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        os.utime(LOCK, (0, 0))
    except Exception:
        pass


def _pending():
    try:
        return sorted(f for f in os.listdir(gkuchi.JOBS_PENDING) if f.endswith(".json"))
    except Exception:
        return []


def run_once(max_jobs=3, quiet=True, only_job=None):
    """only_job … その仕事票1枚だけを処理する（自己テストが本物の待ち行列を食べないため）。"""
    # ★空なら即終了。15秒おきに呼ばれるので、ここが軽いことが一番大事。
    if not os.path.isdir(gkuchi.JOBS_PENDING) or not _pending():
        return 0
    if not gkuchi.net_ok():
        _log("回線が出ないホストで起動されました。何もしません。")
        return 0
    if not _take_lock():
        return 0

    done_n = 0
    try:
        todo = _pending()
        if only_job:
            todo = [f for f in todo if f.startswith(only_job)]
        for name in todo[:max_jobs]:
            src = os.path.join(gkuchi.JOBS_PENDING, name)
            try:
                job = json.load(io.open(src, encoding="utf-8"))
            except Exception as e:
                _log("読めない仕事票を退けました %s: %s" % (name, e))
                try:
                    os.replace(src, os.path.join(gkuchi.JOBS_RUNNING, name + ".broken"))
                except Exception:
                    pass
                continue

            jid = job.get("jobId") or name[:-5]
            os.makedirs(gkuchi.JOBS_RUNNING, exist_ok=True)
            try:  # pendingから外して二重実行を防ぐ
                os.replace(src, os.path.join(gkuchi.JOBS_RUNNING, name))
            except Exception:
                continue

            t0 = time.time()
            _log("開始 %s kind=%s" % (jid, job.get("kind")))
            _limit = _job_limit(job)
            _armed = _arm(_limit)
            try:
                if job.get("kind") == "kiku":
                    import kiku
                    out = kiku.run_job(job["payload"])
                elif job.get("kind") == "tanomu":
                    import tanomu
                    out = tanomu.run_job(job["payload"])
                elif job.get("kind") == "sweep":
                    # Chromeタブ掃除機を工場側で今すぐ走らせる（サンドボックスからは
                    # osascriptが使えないため）。呼べるのはこの1本だけ＝白名簿。
                    import subprocess
                    cmd = [sys.executable, os.path.join(HERE, "chrome_tab_sweeper.py"),
                           "--recon", "--sweep", "--force"]
                    if job["payload"].get("dryRun"):
                        cmd.append("--dry-run")
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    out = {"ok": r.returncode == 0, "stdout": r.stdout[-2000:],
                           "stderr": r.stderr[-1000:], "totalYen": 0.0}
                elif job.get("kind") == "jrsdata":
                    import importlib, _952_data_fetch
                    importlib.reload(_952_data_fetch)
                    out = _952_data_fetch.run_job(job.get("payload") or {})
                elif job.get("kind") == "jrspush":
                    import importlib, _957_push
                    importlib.reload(_957_push)
                    out = _957_push.run_job(job.get("payload") or {})
                elif job.get("kind") == "oausage":
                    # 960番 OpenAIの実額を読むだけ（GETのみ・課金0・鍵の値は出さない）。
                    import importlib, _960_oa_usage
                    importlib.reload(_960_oa_usage)
                    out = _960_oa_usage.run_job(job.get("payload") or {})
                elif job.get("kind") == "diag":
                    # 窓口が通らないとき「向こうに何が有るのか」を工場側で聞きに行く。
                    # 鍵の値は出さない（gaibu_diag.py 側で保証）。
                    import gaibu_diag
                    out = gaibu_diag.run_job(job["payload"])
                elif job.get("kind") == "keijiban":
                    # 965番 AI掲示板（GitHub Issue）。GET/POSTともに api.github.com の
                    # 白名簿repoだけ（_965_keijiban.py 側の ALLOW_REPO で保証）。課金0。
                    import importlib, _965_keijiban
                    importlib.reload(_965_keijiban)
                    out = _965_keijiban.run_job(job.get("payload") or {})
                elif job.get("kind") == "daicho":
                    # 977番：外部AI台帳の回収係。投げたのに返り0のスレッドだけを名指しで読む。
                    # GETのみ・課金0・行き先は _965_keijiban.ALLOW_REPO の中だけ。
                    import importlib, ai_daicho
                    importlib.reload(ai_daicho)
                    out = ai_daicho.run_job(job.get("payload") or {})
                elif job.get("kind") == "ghwatch":
                    # 977番：GitHubの見張り番を工場側で今すぐ1回走らせる。
                    #   サンドボックスからは api.github.com に出られないので、
                    #   「投げた直後に返りを確かめる」ができなかった（＝15秒〜15分待つしかない）。
                    #   呼べるのは github_watch.py の1本だけ＝白名簿。引数も取らない。
                    import subprocess
                    r = subprocess.run([sys.executable, os.path.join(HERE, "github_watch.py"), "--force"],
                                       capture_output=True, text=True, timeout=120)
                    out = {"ok": r.returncode == 0, "stdout": (r.stdout or "")[-3000:],
                           "stderr": (r.stderr or "")[-1500:], "totalYen": 0.0}
                elif job.get("kind") == "kakunin":
                    # 961番 出したページが本当に200で見えるかを工場側から叩く。
                    # GETのみ・課金0・行き先は tamago2022.github.io の中だけ
                    # （白名簿は kakunin.py 側の ALLOW_PREFIX で保証）。
                    import importlib, kakunin
                    importlib.reload(kakunin)
                    out = kakunin.run_job(job.get("payload") or {})
                elif job.get("kind") == "horu":
                    # 2026-09-22 仕入れ：周辺を掘る係を工場側で走らせる。
                    #   サンドボックスからは musicbrainz.org / last.fm に**出られない**
                    #   （プロキシが 403 でトンネルを塞ぐ。実測 2026-09-22 07:41）。
                    #   ＝向こうは「どこを掘るか」を書いた票を置くだけ。掘るのはここ。
                    #   GETだけ・鍵を使わない・**課金0**。棚には一切書かない
                    #   （書き先は status/shiire_kouho/ だけ＝shuhen_horu.py 側で保証）。
                    import importlib, shuhen_horu
                    importlib.reload(shuhen_horu)
                    out = shuhen_horu.run_job(job.get("payload") or {})
                elif job.get("kind") == "zandaka":
                    # 1034番：財布の残高を工場側から読む。**GETだけ・白名簿の外に出られない・
                    #   鍵の値を返さない・課金0**（zandaka.py 側の ALLOW と _mask で保証）。
                    #   サンドボックスからは api.x.ai / api.openai.com / rest.alpha.fal.ai /
                    #   api.devin.ai すべて curl が 000 で、鍵も届かないため。
                    import importlib, zandaka
                    importlib.reload(zandaka)
                    out = zandaka.run_job(job.get("payload") or {})
                elif job.get("kind") == "nagekomi":
                    # 1036番【投げ込み箱】放り込まれたURLの題名・チャンネル・公開日・長さを
                    #   **工場側で**調べて埋める。サンドボックスからは youtube/x ともに
                    #   403（Tunnel connection failed。実測 2026-09-23 12:56）で出られない。
                    #   GETだけ・課金0・★Lovableの棚には一切書かない
                    #   （書き先は status/nagekomi.jsonl だけ＝nagekomi.py 側で保証）。
                    import importlib, nagekomi
                    importlib.reload(nagekomi)
                    out = nagekomi.run_job(job.get("payload") or {})
                elif job.get("kind") == "douga":
                    # 2026-09-22 仕入れ：候補の動画が「公式か／静止画だけでないか」を確かめる。
                    #   YouTube の oEmbed（鍵不要・**課金0**）だけを叩く。行き先は
                    #   www.youtube.com/oembed の1本だけ＝douga_check.py 側の白名簿で保証。
                    import importlib, douga_check
                    importlib.reload(douga_check)
                    out = douga_check.run_job(job.get("payload") or {})
                elif job.get("kind") == "relayup":
                    # ★1038番：中継所の受け口を**その場で入れ直す**手動の梃子。
                    #   relay_server.py は起動時に command_ingest を import するので、
                    #   走り続けている限り新しい指示を覚えない（＝箱から投げても
                    #   「使えない指示」で弾かれる）。ふだんは relay_watch.py が2分おきに
                    #   自分で入れ直すが、サンドボックスからは待つしかないので、
                    #   工場に「今すぐ入れ直せ」と言える口をここに置く。
                    #   ★受け口（localhost:8788）だけ。トンネルもLovableの棚も触らない。
                    import importlib, relay_watch
                    importlib.reload(relay_watch)
                    if (job.get("payload") or {}).get("force"):
                        try:
                            os.utime(relay_watch.SERVER_STAMP, (0, 0))
                        except OSError:
                            pass
                    did = relay_watch.restart_server_if_stale()
                    import subprocess as _sp
                    _h = _sp.run(["curl", "-s", "-m", "5", "-o", "/dev/null",
                                  "-w", "%{http_code}", "http://127.0.0.1:8788/health"],
                                 capture_output=True, text=True, timeout=10)
                    out = {"ok": (_h.stdout or "").strip() == "200",
                           "restarted": bool(did),
                           "health": (_h.stdout or "").strip(),
                           "totalYen": 0.0}
                elif job.get("kind") == "tana":
                    # 1039番 棚の口（GETと、自分が足した行だけ）。Lovableの画面は通らない。
                    import importlib, tana
                    importlib.reload(tana)
                    out = tana.run_job(job.get("payload") or {})
                elif job.get("kind") == "tanaire":
                    # ★1039番：投げ込み箱→棚。コピーを書いて、関所を通して、入れる。
                    #   入れた行は status/nagekomi_ireta.jsonl に控え、op=modoshi でその便の分だけ消す。
                    import importlib, nagekomi_shelf
                    importlib.reload(nagekomi_shelf)
                    out = nagekomi_shelf.run_job(job.get("payload") or {})
                elif job.get("kind") == "mainichi":
                    # ★1038番：毎日やることの専用の口。列（queue.json）に積まない。
                    #   admin_stock を **GETだけ**で読んで下書きを作る。棚には1文字も書かない。
                    #   サンドボックスからは Supabase へ出られない（Tunnel 403）ので工場側で。
                    import importlib, mainichi_kuchi
                    importlib.reload(mainichi_kuchi)
                    out = mainichi_kuchi.run_job(job.get("payload") or {})
                elif job.get("kind") == "vault":
                    # ★1044番：Obsidian Vault のノートを**読むだけ**。
                    #   サンドボックスは ~/Library/Mobile Documents/ をマウントして
                    #   いない（Readもbashも届かない。実測 2026-09-24）。
                    #   書き込み・削除なし・Vaultの外へ出ない・外へ1本も出ない・課金0
                    #   （vault_yomu.py 側の _safe と ALLOW_EXT で保証）。
                    import importlib, vault_yomu
                    importlib.reload(vault_yomu)
                    out = vault_yomu.run_job(job.get("payload") or {})
                elif job.get("kind") == "watashi":
                    # ★1048番の門（渡す前に実際に開いて押す）をMac側で走らせる口。
                    #   公開(kohyou)がこの記録を要求する。記録が無いものは出せない。
                    import importlib, watashi_gate
                    importlib.reload(watashi_gate)
                    out = watashi_gate.run_job(job.get("payload") or {})
                elif job.get("kind") == "sumaho":
                    # ★1043番：たまごさんのiPhoneのSafariと同じ条件（モバイルUA・375px・
                    #   タッチ）でheadless Chromeから箱のボタンを実際に押す門。
                    #   curl/pythonの投げは preflight(OPTIONS) を出さないので、
                    #   CORSで止められていることに1038〜1042番は気づけなかった。
                    #   ★たまごさんの普段のブラウザには触らない（使い捨てプロファイル）。
                    import importlib, sumaho_gate
                    importlib.reload(sumaho_gate)
                    out = sumaho_gate.run_job(job.get("payload") or {})
                elif job.get("kind") == "relaytest":
                    # ★1038番：スマホの代わりに中継所へ1本投げて、道が本当に通るか実測する。
                    #   「たまごさんに試させて確かめる」をやめるための口。棚には触らない。
                    import importlib, relay_nage
                    importlib.reload(relay_nage)
                    out = relay_nage.run_job(job.get("payload") or {})
                else:
                    out = {"ok": False, "error": "知らない仕事の種類です: %s" % job.get("kind")}
            except JobTimeout:
                # ★時間切れ。黙って飲み込まない。理由を必ず結果に書いて、次の仕事へ進む。
                out = {"ok": False, "timedOut": True, "limitSec": _limit,
                       "error": "上限 %d秒を超えたので打ち切りました（kind=%s）。"
                                "★1本が止まっても列は止めません。"
                                % (_limit, job.get("kind")), "totalYen": 0.0}
                _log("⏱ 打ち切り %s kind=%s 上限%d秒" % (jid, job.get("kind"), _limit))
            except Exception:
                out = {"ok": False, "error": "工場側で例外が出ました:\n" + traceback.format_exc()[-1500:]}
            finally:
                if _armed:
                    _disarm()

            out["jobId"] = jid
            out["ranOn"] = "factory"
            out["ranAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
            out["elapsedSec"] = round(time.time() - t0, 1)
            gkuchi.write_job_result(jid, out)
            _log("完了 %s ok=%s %.1f秒 %.3f円" % (jid, out.get("ok"), out["elapsedSec"],
                                                out.get("totalYen") or 0))
            try:
                os.remove(os.path.join(gkuchi.JOBS_RUNNING, name))
            except Exception:
                pass
            done_n += 1
            if not quiet:
                print("処理しました: %s (ok=%s)" % (jid, out.get("ok")))
    finally:
        _release_lock()
    return done_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--max-jobs", type=int, default=3)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        print("回線（api.openai.com）：%s" % ("出る ✅" if gkuchi.net_ok() else "出ない ❌"))
        print("鍵：%s" % json.dumps(gkuchi.key_status(), ensure_ascii=False))
        print("待ち：%d件 / 済み：%d件"
              % (len(_pending()),
                 len(os.listdir(gkuchi.JOBS_DONE)) if os.path.isdir(gkuchi.JOBS_DONE) else 0))
        return 0

    n = run_once(max_jobs=a.max_jobs, quiet=a.quiet)
    if not a.quiet:
        print("処理件数: %d" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
