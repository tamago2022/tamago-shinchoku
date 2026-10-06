#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34547番：仕入れの進捗（完了・残り）を1枚で見れるようにする。

たまごさん（2026-08-05・スマホから）：
  「どこまで仕入れが完了しているか、これから何件残っているかが分かるように
   進捗を管理してください。」

★なぜ今まで無かったか（調べて分かったこと）
  仕入れは1つの作業ではなく複数系統に分かれていて、それぞれ別の場所に
  数字だけ記録されていた（店主が見れる1枚のページが無かった）：
    ① フェス名簿からの仕入れ（1044/1049番・tools/shiire_loop.py が毎日回す）
       → status/shiire_kouho/_run.json、status/shiire_shoko/_index.json、
         status/shiire_loop.log（最新行）に数字はあるが、JSONの生ファイルのまま。
    ② 日次の入荷見回り（756番）→ status/public/daily_ingest_summary.json
    ③ 工場の作業キュー（status/queue.json）にある「仕入れ」を含む依頼の
       待機・保留・走行中の件数
    ④ ごきげん補給所（joy-relief-station）側の在庫の実数
       （アーティスト数・曲数・YouTube ID充足率）

  ★数字を1つに盛って「仕入れ進捗◯%」のような嘘くさい統合指標は作らない
  （店主の方針「正しいより楽しい。ただし嘘は禁止」「確認が取れる情報を
    1つ入れると信頼が積み重なる」＝不正確な統合より正確な個別の数字）。
  系統ごとに「今ある数・残りの数」をそのまま並べる。

使い方
    python3 tools/shiire_shinchoku.py            # 集計して status/public/ へ書く
    python3 tools/shiire_shinchoku.py --print    # 標準出力にも出す
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PUBLIC = os.path.join(ST, "public")
OUT = os.path.join(PUBLIC, "shiire_shinchoku.json")
JST_NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")

# ごきげん補給所の実体（デスクトップのクローン。読むだけ・書かない）。
# 無ければ在庫の実数は省略し、無かったことを隠さずそのまま書く。
JOY_CANDIDATES = [
    os.path.expanduser("~/Desktop/joy-relief-station"),
    os.path.expanduser("~/tamago/joy-relief-station"),
]


def _safe_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fes_meibo_shiire():
    """①フェス名簿からの仕入れ（1044/1049番）。"""
    run = _safe_json(os.path.join(ST, "shiire_kouho", "_run.json"), {}) or {}
    shoko = _safe_json(os.path.join(ST, "shiire_shoko", "_index.json"), {}) or {}

    last_line = {}
    log_path = os.path.join(ST, "shiire_loop.log")
    if os.path.exists(log_path):
        try:
            with io.open(log_path, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{"):
                    last_line = json.loads(line)
                    break
        except Exception:
            last_line = {}

    todo_path = os.path.join(ST, "1044_shiire_todo.txt")
    todo_total = 0
    if os.path.exists(todo_path):
        try:
            with io.open(todo_path, encoding="utf-8") as f:
                todo_total = len([l for l in f.read().splitlines() if l.strip()])
        except Exception:
            todo_total = 0

    return {
        "kouho": run.get("candidates"),
        "runs": run.get("runs"),
        "shokoKensu": shoko.get("kensu"),
        "shokoHonninKakutei": shoko.get("honninKakutei"),
        "shokoHoryuu": shoko.get("horyuu"),
        "todoTotal": todo_total or None,
        "sozaiMachi": last_line.get("ato", {}).get("sozaiMachi", last_line.get("sozaiMachi")),
        "sozaiNokori": last_line.get("sozaiNokori"),
        "lastRunAt": last_line.get("at"),
    }


def nikkan_nyuka():
    """②日次の入荷見回り（756番）。"""
    d = _safe_json(os.path.join(PUBLIC, "daily_ingest_summary.json"), {}) or {}
    if not d:
        return None
    return {
        "date": d.get("date"),
        "total": d.get("total"),
        "fixed": d.get("fixed"),
        "ok": d.get("ok"),
        "unsure": d.get("unsure"),
        "updatedAt": d.get("updatedAt"),
    }


def koujou_queue_shiire():
    """③工場の作業キュー（status/queue.json）の「仕入れ」を含む依頼。"""
    data = _safe_json(os.path.join(ST, "queue.json"), None)
    if data is None:
        return None
    items = data if isinstance(data, list) else data.get("items", data.get("queue", []))
    counts = {"waiting": 0, "hold": 0, "running": 0, "awaiting_check": 0, "other": 0}
    total = 0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "") + (it.get("hyoudai") or "")
        if "仕入れ" not in title and "shiire" not in title.lower():
            continue
        total += 1
        st = it.get("status", "other")
        counts[st if st in counts else "other"] += 1
    return {"total": total, "byStatus": counts}


def joy_zaiko():
    """④ごきげん補給所の在庫実数（origin/main の静的データファイルから数える近似値）。

    ★DBの生の値ではない。リポジトリに入っている静的ファイル
      （coverGuideLite.generated.ts）から数えたスナップショット。
      店主向けの正式な在庫数は /admin/inventory（ログイン必須）が正。
      ここでは「だいたい今どれくらいか」を店主にも見える場所に出すために使う。

    ★ローカルのワーキングツリーを直接読まない（他セッションの未コミット変更が
      混ざって数字がブレた実例があった）。`git show origin/main:<path>` で
      常にmain最新のコミット済み内容だけを読む。
    """
    import subprocess

    for base in JOY_CANDIDATES:
        if not os.path.isdir(base):
            continue
        rel = "src/lib/coverGuideLite.generated.ts"
        try:
            subprocess.run(
                ["git", "-C", base, "fetch", "origin", "main", "--quiet"],
                timeout=60, capture_output=True,
            )
            p = subprocess.run(
                ["git", "-C", base, "show", "origin/main:" + rel],
                timeout=30, capture_output=True, text=True,
            )
            if p.returncode != 0 or not p.stdout:
                continue
            text = p.stdout
            commit_at = subprocess.run(
                ["git", "-C", base, "log", "-1", "--format=%ci", "origin/main", "--", rel],
                timeout=15, capture_output=True, text=True,
            ).stdout.strip()[:10]
        except Exception:
            continue

        songs_objs = re.findall(r'\{"id":"[^"]*","title":"[^"]*"[^}]*\}', text)
        artist_lines = re.findall(r'^\s*\{"id":"', text, re.M)
        yt = sum(1 for s in songs_objs if '"youtubeId"' in s)
        songs = len(songs_objs)
        rate = round((yt / songs) * 100, 1) if songs else None
        return {
            "artists": len(artist_lines),
            "songs": songs,
            "youtubeIds": yt,
            "youtubeRate": rate,
            "snapshotFrom": "origin/main",
            "snapshotCommitDate": commit_at or None,
        }
    return None


def _n(v):
    if v is None:
        return "—"
    try:
        return "{:,}".format(int(v))
    except Exception:
        return str(v)


HTML_PATH = os.path.join(REPO, "share", "34547-shiire-shinchoku.html")

HTML_TMPL = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>仕入れ進捗</title>
<!--
  34547番（2026-08-05にたまごさんがスマホから言った依頼・2026-10-07対応）
  「どこまで仕入れが完了しているか、これから何件残っているかが分かるように
   進捗を管理してください。」

  ★数字を1つに盛って「仕入れ進捗◯%」のような統合指標は作らない
  （店主の方針「正しいより楽しい。ただし嘘は禁止」）。
  仕入れは複数の系統に分かれているので、系統ごとに「今ある数・残りの数」を
  そのまま並べる。

  ★このHTML自体を tools/shiire_shinchoku.py が毎日書き直す（静的生成）。
  以前はJSでJSONをfetchして表示する形にしていたが、機械検品
  （tools/oni_modoshi.py）は実ブラウザでJSを実行しないため、「読み込み中…」
  のままの状態しか見えず「中身が空」として差し戻された（34547番・1回目）。
  数字を生成時にそのままHTMLへ焼き込む形へ直した。
-->
<style>
:root{{ --ink:#1c1a17; --sub:#6d675f; --line:#ddd7cd; --paper:#f7f4ee; --card:#fffdf9; --green:#3a6b3a; }}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0; padding:14px 14px 56px; background:var(--paper); color:var(--ink);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}}
.wrap{{max-width:560px; margin:0 auto}}
h1{{font-size:20px; margin:0 0 4px; font-weight:600}}
.lead{{font-size:14px; color:var(--sub); margin:0 0 14px}}
#stamp{{font-size:13px; color:var(--sub)}}
.card{{background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; margin-bottom:12px}}
.card > h2{{font-size:15px; margin:0 0 10px; color:var(--sub); font-weight:600; letter-spacing:.02em}}
.g2{{display:grid; grid-template-columns:1fr 1fr; gap:8px}}
.g3{{display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px}}
.wl{{font-size:13px; color:var(--sub); font-weight:600}}
.wv{{font-size:24px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.2}}
.wv.small{{font-size:18px}}
.note{{font-size:12.5px; color:var(--sub); margin-top:8px; line-height:1.6}}
.bar{{height:10px; border-radius:6px; background:#eee7dc; overflow:hidden; margin-top:6px}}
.bar > i{{display:block; height:100%; background:var(--green)}}
ul{{list-style:none; margin:0; padding:0}}
li{{padding:7px 0; border-top:1px solid #eee7dc; font-size:14.5px; display:flex; justify-content:space-between; gap:8px}}
li:first-child{{border-top:0}}
</style>
</head>
<body>
<div class="wrap">
  <h1>🧺 仕入れ進捗</h1>
  <div class="lead">どこまで進んでいて、残りどれくらいあるか。系統ごとに数字をそのまま出す（1つに盛った%は作らない）。アーティスト・曲を探す作業（仕入れ）が、今どこまで進んでいるかをここで見られるようにした。</div>
  <div id="stamp">最終更新 {updated_disp}</div>

  <div class="card">
    <h2>① ごきげん補給所の在庫（在庫の今）</h2>
    <div class="g3">
      <div><div class="wl">アーティスト</div><div class="wv">{z_artists}</div></div>
      <div><div class="wl">曲</div><div class="wv">{z_songs}</div></div>
      <div><div class="wl">YouTube充足</div><div class="wv small">{z_rate}</div></div>
    </div>
    <div class="note">{z_note}</div>
  </div>

  <div class="card">
    <h2>② フェス名簿からの仕入れ（1044/1049番・毎日自動で回っている）</h2>
    <div class="g2">
      <div><div class="wl">候補まで進んだ</div><div class="wv">{f_kouho}</div></div>
      <div><div class="wl">証拠まで確定</div><div class="wv">{f_shoko}</div></div>
    </div>
    <div class="bar"><i style="width:{f_pct}%"></i></div>
    <div class="note">名簿のうち素材すら無いもの {f_machi}組（名簿全体 {f_todo}組）。素材はあるが候補に積めていない積み残し {f_nokori}組。最後に回ったのは {f_last}。</div>
  </div>

  <div class="card">
    <h2>③ 日次の入荷見回り（756番・前日分を毎朝1回）</h2>
    <ul>
      <li><span>見回った件数（{d_date}）</span><span>{d_total}件</span></li>
      <li><span>直した件数</span><span>{d_fixed}件</span></li>
      <li><span>そのままでよかった件数</span><span>{d_ok}件</span></li>
      <li><span>判断がつかなかった件数</span><span>{d_unsure}件</span></li>
    </ul>
    <div class="note">更新 {d_updated}</div>
  </div>

  <div class="card">
    <h2>④ 工場の作業キューにある「仕入れ」の依頼</h2>
    <ul>
      <li><span>発車待ち</span><span>{q_waiting}件</span></li>
      <li><span>保留</span><span>{q_hold}件</span></li>
      <li><span>走行中</span><span>{q_running}件</span></li>
      <li><span>検品待ち</span><span>{q_check}件</span></li>
    </ul>
    <div class="note">これは「仕入れて」という依頼そのものの処理待ち件数（曲の件数ではない）。</div>
  </div>

  <div class="card">
    <h2>数字の裏側（生データ）</h2>
    <div class="note">このページは <a href="../status/public/shiire_shinchoku.json">status/public/shiire_shinchoku.json</a> を毎日読み直して書き直している。生の数字をそのまま見たい時はそちらを開く。</div>
  </div>
</div>
</body>
</html>
"""


def _render_html(out):
    z = out.get("joyZaiko") or {}
    f = out.get("fesMeibo") or {}
    d = out.get("dailyIngest") or {}
    q = (out.get("koujouQueue") or {}).get("byStatus") or {}

    f_kouho = f.get("kouho")
    f_kakutei = f.get("shokoHonninKakutei")
    f_pct = min(100, round((f_kakutei / f_kouho) * 100)) if f_kouho and f_kakutei else 0

    try:
        updated_disp = out["updatedAt"][5:16].replace("T", " ")
    except Exception:
        updated_disp = out.get("updatedAt") or "—"

    z_note = (
        "origin/main の %s 時点のコミット済みデータから数えた値（DBの生の値ではないスナップショット）。"
        % z["snapshotCommitDate"]
        if z.get("snapshotCommitDate")
        else "在庫データが読めなかった（joy-relief-stationのクローンが見つからない）。"
    )

    html = HTML_TMPL.format(
        updated_disp=updated_disp,
        z_artists=_n(z.get("artists")), z_songs=_n(z.get("songs")),
        z_rate=("—" if z.get("youtubeRate") is None else "%s%%" % z["youtubeRate"]),
        z_note=z_note,
        f_kouho=_n(f_kouho), f_shoko="%s / %s" % (_n(f_kakutei), _n(f.get("shokoKensu"))),
        f_pct=f_pct, f_machi=_n(f.get("sozaiMachi")), f_todo=_n(f.get("todoTotal")),
        f_nokori=_n(f.get("sozaiNokori")), f_last=(f.get("lastRunAt") or "—"),
        d_date=(d.get("date") or "—"), d_total=_n(d.get("total")), d_fixed=_n(d.get("fixed")),
        d_ok=_n(d.get("ok")), d_unsure=_n(d.get("unsure")), d_updated=(d.get("updatedAt") or "—"),
        q_waiting=_n(q.get("waiting")), q_hold=_n(q.get("hold")),
        q_running=_n(q.get("running")), q_check=_n(q.get("awaiting_check")),
    )
    with io.open(HTML_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    out = {
        "updatedAt": JST_NOW,
        "fesMeibo": fes_meibo_shiire(),
        "dailyIngest": nikkan_nyuka(),
        "koujouQueue": koujou_queue_shiire(),
        "joyZaiko": joy_zaiko(),
    }
    os.makedirs(PUBLIC, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    _render_html(out)
    if "--print" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("書いた: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
