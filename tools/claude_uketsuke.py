#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Code 受付係（claude_uketsuke）— 2026-10-17 たまごさん指示。

たまごさん：「Gensparkとの間で水汲み（仲介）は本当はしたくない」
実害：joy-relief-station #1015（【Claude Codeに頼む】月の特集）が置かれても、
  github_watch.py は「tamago2022 の『〜に頼む】』は受信箱に畳むだけ」で発車待ちに積まず、
  たまごさんが口で伝えるまで誰も着手しなかった。tamago-shinchoku はそもそも見ていなかった。

やること（5分に1回・心臓 top_status.py の相乗り）：
  ① joy-relief-station と tamago-shinchoku の open Issue のうち、
     タイトルに【Claude Codeに頼む】を含む新しいものを拾う
  ② 工場の発車待ち（status/queue.json）へ積む → auto_launcher が着火（人は押さない）
  ③ Issue に「受け付けました」をコメント（先頭に <!-- tamago-factory -->＝Gensparkへの返事はIssueで）
  ④ Dispatch へ1行（status/dispatch_outbox.jsonl, type=claude_uketsuke）
  ⑤ 30分に1回、Genspark AI Drive（gsk drive tree）の新しいファイルを拾って Dispatch へ1行
     （中身の取り込みはしない＝名前と置き場だけ知らせる。無料の一覧取得だけ使う）

作るもの：status/claude_uketsuke_state.json（覚え書き）／status/claude_uketsuke.log（300行で刈る）
         status/public/claude_uketsuke.json（進捗表用）。一時ファイルは作らない。
台帳：tools/jidou_daicho.json の "claude_uketsuke.py"
逆テスト：python3 tools/claude_uketsuke.py --self-test
手で今すぐ回す：python3 tools/claude_uketsuke.py --force
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
STATE = os.path.join(ST, "claude_uketsuke_state.json")
LOG = os.path.join(ST, "claude_uketsuke.log")
PUBLIC = os.path.join(ST, "public", "claude_uketsuke.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
LOCK = os.path.join(ST, ".claude_uketsuke.lock")

REPOS = ["tamago2022/joy-relief-station", "tamago2022/tamago-shinchoku"]
TITLE_MARK = "【Claude Codeに頼む】"
GATE_SEC = 300            # 5分おき
DRIVE_GATE_SEC = 1800     # AI Drive は30分おき（gsk は1回が重い）
MAX_PER_RUN = 3           # 流し込み事故の防止
BOOTSTRAP_SEC = 48 * 3600 # 初回だけ48時間遡る
FACTORY_MARK = "<!-- tamago-factory -->"
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
        lines = open(LOG, encoding="utf-8").read().splitlines()
        if len(lines) > 400:
            open(LOG, "w", encoding="utf-8").write("\n".join(lines[-300:]) + "\n")
    except Exception:
        pass


def load_state():
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("seen", [])
    st.setdefault("next", 0)
    st.setdefault("driveNext", 0)
    st.setdefault("driveSeen", None)   # None＝初回（今ある分は「新しい」と数えない）
    st.setdefault("since", time.time() - BOOTSTRAP_SEC)
    st.setdefault("stats", {"runs": 0, "picked": 0, "driveNew": 0, "errors": 0})
    return st


def save_state(st):
    st["seen"] = list(dict.fromkeys(st["seen"]))[-2000:]
    st["updatedAt"] = time.strftime("%F %T")
    tmp = "%s.%d.tmp" % (STATE, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def outbox(title, message, urls=None):
    row = {"ts": time.strftime("%F %T"), "n": "uketsuke-%d" % int(time.time() * 1000),
           "type": "claude_uketsuke", "from": "claude_uketsuke", "title": title,
           "message": message, "urls": urls or []}
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV, cwd=REPO)
    return p.returncode, p.stdout, p.stderr


def is_target(title):
    return TITLE_MARK in (title or "")


def _iso(s):
    try:
        import calendar
        return calendar.timegm(time.strptime((s or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0


def instruction(repo, it):
    body = (it.get("body") or "")[:6000]
    return "\n".join([
        "【タスク】GitHub %s #%s「%s」を実行する（%s 経由の自動受付）" % (repo, it["number"], it["title"], TITLE_MARK),
        "【出どころ】%s ／ 投稿者: %s" % (it.get("url"), (it.get("author") or {}).get("login")),
        "【最初にやる】`gh issue view %s -R %s --comments` で全文とコメントを読む（下の抜粋は先頭だけ）。" % (it["number"], repo),
        "【守る】Issueの「触らない」「事実注意」に従う。本文は勝手にリライトしない。お金が出る操作・削除・権限変更・秘密情報の持ち出しはしない。",
        "　たまごさん（2026-10-17）「とりあえず公開して見せて。そこから調整」＝Issueが本番公開を求めていれば、関所（koutai_kanmon・unify_look・prebuild）を通したうえで公開してよい。",
        "【返事】終わったら同じIssueにコメント（本文の先頭に %s）：コミット番号＋本番URL＋未確認。Gensparkへの返事はIssueコメントで。たまごさんを仲介に使わない。" % FACTORY_MARK,
        "【報告】Dispatchへ3行（完了/問題/判断待ち）。",
        "", "---- Issue本文（先頭） ----", body,
    ])


def check_issues(st, budget):
    picked = 0
    seen = set(st["seen"])
    for repo in REPOS:
        if picked >= budget:
            break
        try:
            # 検索API（--search）は今日の実測で60秒超のタイムアウトが続いたので使わない。
            # 新しい順30件の軽い一覧だけ取り、本文は当たった号だけ取りに行く。
            rc, out, err = run(["gh", "issue", "list", "-R", repo, "--state", "open", "--limit", "30",
                                "--json", "number,title,url,createdAt,author"], timeout=90)
        except Exception as e:
            st["stats"]["errors"] += 1
            log("%s 一覧が取れない: %r" % (repo, e))
            continue
        if rc != 0:
            st["stats"]["errors"] += 1
            log("%s 一覧が取れない rc=%s %s" % (repo, rc, (err or "")[:200]))
            continue
        try:
            items = json.loads(out or "[]")
        except Exception:
            items = []
        for it in sorted(items, key=lambda x: x.get("createdAt") or ""):
            if picked >= budget:
                break
            key = "%s#%s" % (repo, it.get("number"))
            if key in seen or not is_target(it.get("title")):
                continue
            if _iso(it.get("createdAt")) < st["since"]:
                seen.add(key)   # 基準線より前の古い号は掘り返さない
                continue
            try:
                rc2, o2, _ = run(["gh", "issue", "view", str(it["number"]), "-R", repo, "--json", "body"], timeout=90)
                it["body"] = json.loads(o2).get("body") if rc2 == 0 else ""
            except Exception:
                it["body"] = ""   # 本文が取れなくても積む（着手側が gh issue view で読み直す）
            sys.path.insert(0, HERE)
            try:
                import command_ingest
                status, msg = command_ingest.queue_add(
                    instruction(repo, it), priority=1,
                    label="GH%s %s" % (it["number"], it["title"].replace(TITLE_MARK, "")[:50]),
                    origin="factory")
            except Exception as e:
                st["stats"]["errors"] += 1
                log("%s 発車待ちに積めない: %r" % (key, e))
                continue
            seen.add(key)
            picked += 1
            short = it["title"].replace(TITLE_MARK, "")[:60]
            try:
                run(["gh", "issue", "comment", str(it["number"]), "-R", repo, "--body",
                     "%s\n受け付けました。工場の発車待ちに積み、順に着手します（%s）。終わったらここにコミット番号と本番URLを書きます。"
                     % (FACTORY_MARK, msg)], timeout=40)
            except Exception as e:
                log("%s 受付コメントを書けない: %r" % (key, e))
            outbox("【受付】%s #%s %s" % (repo.split("/")[1], it["number"], short),
                   "【Claude Codeに頼む】を自動受付→発車待ちへ（%s）" % msg, [it.get("url")])
            log("%s「%s」→ 積んだ（%s）" % (key, short, msg))
    st["seen"] = list(seen)
    return picked


def _drive_files(js):
    """gsk drive tree の出力（JSONが1つ＋ゴミ）からファイルだけ取り出す。"""
    try:
        d, _ = json.JSONDecoder().raw_decode(js.strip())
        return {e["entry_id"]: e.get("name") for e in (d.get("data") or {}).get("entries", [])
                if e.get("kind") == "file"}
    except Exception:
        return None


def check_drive(st):
    try:
        rc, out, err = run(["gsk", "--no-input", "drive", "tree", "--path", "/"], timeout=150)
    except Exception as e:
        log("AI Drive が読めない: %r" % (e,))
        return 0
    files = _drive_files(out or "")
    if files is None:
        log("AI Drive の返事が読めない rc=%s %s" % (rc, (out or err or "")[:160]))
        return 0
    if st["driveSeen"] is None:
        st["driveSeen"] = sorted(files)
        log("AI Drive 初回：%d件を基準にした（通知しない）" % len(files))
        return 0
    old = set(st["driveSeen"])
    new = [(i, n) for i, n in files.items() if i not in old]
    if new:
        names = "、".join(n for _, n in new[:8])
        outbox("【AI Drive 新着】%d件" % len(new),
               "Genspark AI Drive に新しいファイル：%s（gsk drive で取れます）" % names, [])
        log("AI Drive 新着 %d件: %s" % (len(new), names))
    st["driveSeen"] = sorted(old | set(files))[-5000:]
    return len(new)


# ── 【納品】受付（2026-10-17 追加・2026-10-18 作り直し）──────────────────────
# 実害①（10/17）：#1015 で Genspark が AI Drive へ原稿を置き Issue に書いたのに、受付係は「新しいIssueのタイトル」しか
#   見ておらずコメントを見ていなかった／AI Drive の初回基準に原稿が吸い込まれ「新着」にならなかった。
# 実害②（10/18 たまごさん「仕事が終わっているのに、俺が言わないと動かないのはダメ」）：拾って積むところまでは動いたが、
#   ・#1018 は積んだ仕事（118330）が週の配分ゲートで「裏方」と判定され、10/18 00:13 から発車できずに止まっていた
#   ・#1018 の 2本目（tamago-magazine.skill）は gsk の一時的な fetch failed で落ち、コメントを「見た」扱いにして二度と取りに行かなかった
#   ・見ていたのは joy-relief-station のコメントだけ（tamago-shinchoku の Issue は見ていない）
#   ・AI Drive の新着は「名前を Dispatch に知らせるだけ」で、取得も積みもしなかった
#   ・#1015 は本番公開の鍵（Lovable）が切れて止まったのに、Dispatch へ「押してください」が届く道が無かった
# やること（5分おき）：
#   ① 両リポの新しいコメントの「【納品】/tamago-inbox/<番号>/<名前>」を拾う（どの Issue でも）
#   ② AI Drive /tamago-inbox/ 以下の全サブフォルダの新着ファイルも拾う（コメントが無くても。フォルダ名の数字＝Issue番号）
#   ③ gsk drive download（無料）で ~/tamago/_inbox/<番号>/ へ取る。落ちたら「取り直し待ち」に残し、次の回から最大8回取り直す
#   ④ 発車待ちへ積む（urgent・kubun=mitai＝週の配分ゲートで止めない）→ Issue に受領 → Dispatch へ1行
#   ⑤ 公開見張り：.html の納品は本番URL（配置先 or magazine/<名前>）を控え、本番が 200 で変わったら
#      Issue に「公開しました＋URL」→ Dispatch へ1行。45分たっても出ていなければ Dispatch へ「公開ボタン待ち」を1回だけ。
NOUHIN_RE = re.compile(r"【納品】\s*(/[^\s`'\"<>]+)")
HAICHI_RE = re.compile(r"配置先\s*[:：]\s*`?([^\s`'\"<>]+)")
INBOX = os.path.expanduser("~/tamago/_inbox")
DRIVE_ROOT = "/tamago-inbox"
PROD_BASE = "https://joy-relief-station.lovable.app/"
RETRY_MAX = 8
KOUKAI_NOTIFY_SEC = 45 * 60
KOUKAI_GIVEUP_SEC = 14 * 86400


def _nouhin_paths(body):
    return [p.rstrip("。.,、）)") for p in NOUHIN_RE.findall(body or "")]


def _haichi(body):
    """「配置先: …」の行（リポ内のパス）。/tamago-inbox/ を指しているもの（Gensparkの書き間違い）は捨てる。"""
    return [p.rstrip("。.,、）)") for p in HAICHI_RE.findall(body or "") if not p.startswith(DRIVE_ROOT)]


def _issue_no(url):
    m = re.search(r"/issues/(\d+)", url or "")
    return m.group(1) if m else None


def _repo_of(url):
    m = re.search(r"repos/([^/]+/[^/]+)/issues|github\.com/([^/]+/[^/]+)/issues", url or "")
    return (m.group(1) or m.group(2)) if m else REPOS[0]


def _download(drive_path, num):
    dst_dir = os.path.join(INBOX, str(num))
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(drive_path))
    # gsk drive download は「今いるフォルダ」に落とす（--output は効かない・10/17 実測）
    p = subprocess.run(["gsk", "--no-input", "drive", "download", "--path", drive_path],
                       capture_output=True, text=True, timeout=180, env=ENV, cwd=dst_dir)
    rc, out, err = p.returncode, p.stdout, p.stderr
    ok = rc == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    return dst if ok else None, (out or err or "")[:200]


def _safe_comment(num, repo, body):
    """GitHub が詰まっても受付を止めない（10/17 実測：TLS タイムアウトで例外→二重積みの危険）。"""
    try:
        rc, _, err = run(["gh", "issue", "comment", str(num), "-R", repo, "--body", body], timeout=60)
        return rc == 0
    except Exception as e:
        log("#%s コメントを書けない（受付は済み）: %r" % (num, e))
        return False


def prod_url(drive_path, haichi=None):
    """納品の本番URL。配置先があればそれ、無ければ .html は magazine/<名前>（マガジンの決まり）。"""
    name = os.path.basename(drive_path)
    for h in haichi or []:
        if os.path.basename(h) == name:
            h = h.lstrip("/")
            h = h[len("public/"):] if h.startswith("public/") else h
            return PROD_BASE + h
    if name.endswith(".html"):
        return PROD_BASE + "magazine/" + name
    return None


def _head(url):
    """(HTTPの番号, 本番の版ID)。版ID＝x-deployment-id（無ければ ETag）。"""
    import urllib.request
    try:
        req = urllib.request.Request(url + ("&" if "?" in url else "?") + "_t=%d" % int(time.time()),
                                     method="GET", headers={"User-Agent": "tamago-factory/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(400000)
            return r.status, r.headers.get("x-deployment-id") or r.headers.get("etag") or str(len(body))
    except Exception as e:
        return getattr(e, "code", 0) or 0, None


def mark_mitai(qmsg):
    """積んだ仕事を「見たいもの」に固定する（納品の仕上げ・公開は裏方ではない）。118330 が週の配分ゲートで止まった事故の再発防止。"""
    m = re.search(r"(\d+)番", qmsg or "")
    if not m:
        return False
    try:
        sys.path.insert(0, HERE)
        import command_ingest as ci
        with ci.queue_lock():
            q = ci._load_queue()
            for it in q.get("items", []):
                if str(it.get("n")) == m.group(1):
                    it["kubun"] = "mitai"
                    it.pop("urakataBlockedAt", None)
                    ci._save_queue(q)
                    return True
    except Exception as e:
        log("kubun を付けられない %s: %r" % (m.group(1), e))
    return False


def _nouhin_text(repo, num, got, src_url, haichi, urls):
    return "\n".join([
        "【タスク】GitHub %s #%s に届いた【納品】を、その Issue の依頼どおりに仕上げて本番公開→Issueに完了まで通す" % (repo, num),
        "【受け取ったファイル（Macの中）】" + " ／ ".join(got),
        "【出どころ】%s" % src_url,
        "【本番URL（予定）】" + (" ／ ".join(urls) if urls else "（配置先の指定なし）"),
        "【配置先（Genspark申告）】" + (" ／ ".join(haichi) if haichi else "（なし）"),
        "【最初にやる】`gh issue view %s -R %s --comments` で依頼と注意（触らない・事実注意・たまごさんの構成指示）を全部読む。" % (num, repo),
        "【分担】Genspark＝本文HTML・文章・章立て・曲と画像の選定・出典。工場＝<head>のメタ（og:url）・曲ページへのリンク・i18nのキー・画像の移し替え。",
        "【仕上げ】マガジンの .html は `python3 tools/magazine/nouhin_shiage.py SPEC.json` で確定の型（怒れる人々 10-18）にそろえる："
        "画像は自由ライセンスだけ残して webp に移す・og/canonical・曲ページ導線（coverGuideLite で一致したものだけ）・シェア／フォロー・5言語（訳は `--i18n`）・バックナンバー（tools/magazine/backnumber.py）。",
        "【守る】連携のルール（status/renkei/1017_zenin_rule.md）。本文を勝手にリライトしない。読者に制作側の注記（未確認・要確認・埋め込みの説明）を出さない。お金・削除・権限変更はしない。",
        "【公開】関所（koutai_kanmon・unify_look・magazine_monogatari_kanmon）を通して joy-relief-station main へ → Lovable の deploy_project。"
        "鍵が切れていたら押さずに Dispatch へ1行（公開ボタン待ち＋URL）。公開できたかは受付係（claude_uketsuke の公開見張り）が本番を見て Issue と Dispatch に出す。",
        "【.yml・.sh など動くファイルの納品】置く前に中身を全部読む：外部への送信先・秘密(secrets/トークン)の扱い・書き換えられる範囲・勝手に push しないか・工場の受付と重複しないか。危険・重複なら置かず、理由を Issue に1行。",
        "【返事】同じIssueにコメント（先頭に %s）：本番URL＋未確認。たまごさんを仲介に使わない。GitHub のURLは報告に書かない（本番URLだけ）。" % FACTORY_MARK,
    ])


def _take(st, repo, num, paths, src_url, haichi, why):
    """取る→積む→受領→Dispatch。取れなかった分は取り直し待ちへ。戻り値＝積んだら1。"""
    got_map = st.setdefault("nouhinGot", {})
    got, bad = [], []
    for p in paths[:10]:
        if p in got_map:
            continue
        try:
            dst, msg = _download(p, num)
        except Exception as e:
            dst, msg = None, repr(e)
        if dst:
            got.append(dst)
            got_map[p] = dst
        else:
            bad.append((p, msg))
    retry = st.setdefault("nouhinRetry", [])
    for p, msg in bad:
        r = next((x for x in retry if x["path"] == p), None)
        if r is None:
            retry.append({"path": p, "repo": repo, "num": num, "src": src_url, "haichi": haichi, "tries": 1, "last": msg})
        else:
            r["tries"] += 1; r["last"] = msg
    if not got:
        return 0
    urls = [u for u in (prod_url(g, haichi) for g in got) if u]
    try:
        sys.path.insert(0, HERE)
        import command_ingest
        # urgent：たまごさん 10/17「店主が1回言うだけで自動投稿まで」＝納品は列の後ろに並ばせない
        status, qmsg = command_ingest.queue_add(_nouhin_text(repo, num, got, src_url, haichi, urls), priority=1,
                                                label="GH%s 納品の受け取り" % num, origin="factory", urgent=True)
    except Exception as e:
        log("#%s 納品を積めない: %r" % (num, e))
        for g in got:
            for k, v in list(got_map.items()):
                if v == g:
                    got_map.pop(k)
        return 0
    mark_mitai(qmsg)
    machi = st.setdefault("koukaiMachi", [])
    for u in urls:
        if not any(x["url"] == u for x in machi):
            code, ver = _head(u)
            machi.append({"url": u, "repo": repo, "num": num, "since": time.time(), "code0": code, "ver0": ver, "notified": False})
    _safe_comment(num, repo, "%s\n【Claude Code】納品を受け取りました（%d件・%s）。工場の発車待ちに積みました（%s）。本番に出たら、ここに本番URLを書きます。"
                  % (FACTORY_MARK, len(got), why, qmsg))
    outbox("【納品受付】#%s %d件" % (num, len(got)), "%s → 自動で取得→発車待ちへ（%s）" % (why, qmsg), urls or [src_url])
    log("#%s 納品 %d件を取得・積んだ（%s・%s）" % (num, len(got), why, qmsg))
    save_state(st)
    return 1


def check_nouhin(st):
    st.setdefault("nouhinSeen", [])
    st.setdefault("nouhinSince", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 6 * 3600)))
    seen = set(st["nouhinSeen"])
    n_ok = 0
    all_ok = True
    for repo in REPOS:
        try:
            rc, out, err = run(["gh", "api", "repos/%s/issues/comments?sort=created&direction=desc&per_page=100&since=%s"
                                % (repo, st["nouhinSince"])], timeout=90)
            rows = json.loads(out or "[]") if rc == 0 else None
        except Exception as e:
            rows = None
            log("%s 納品コメントが読めない: %r" % (repo, e))
        if rows is None:
            all_ok = False   # 読めなかった回は since を進めない（取りこぼさない）
            continue
        for c in sorted(rows, key=lambda x: x.get("created_at") or ""):
            cid = str(c.get("id"))
            body = c.get("body") or ""
            if cid in seen or FACTORY_MARK in body:
                continue
            seen.add(cid)
            paths = _nouhin_paths(body)
            num = _issue_no(c.get("issue_url") or c.get("html_url"))
            if not paths or not num:
                continue
            n_ok += _take(st, repo, num, paths, c.get("html_url"), _haichi(body), "Issueの【納品】コメント")
    st["nouhinSeen"] = list(seen)[-3000:]
    if all_ok:
        st["nouhinSince"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1800))
    return n_ok


def retry_nouhin(st):
    """取り直し待ち（gsk の一時的な fetch failed 等）を取り直す。8回だめなら Issue と Dispatch に1行出して諦める。"""
    n = 0
    keep = []
    for r in list(st.get("nouhinRetry", [])):
        if r["path"] in st.get("nouhinGot", {}):
            continue
        if _take(st, r["repo"], r["num"], [r["path"]], r["src"], r.get("haichi") or [], "取り直し%d回目" % r["tries"]):
            n += 1
            continue
        r2 = next((x for x in st.get("nouhinRetry", []) if x["path"] == r["path"]), r)
        if r2["tries"] >= RETRY_MAX:
            _safe_comment(r["num"], r["repo"], "%s\n【Claude Code】`%s` を%d回取りに行きましたが取れませんでした（%s）。AI Drive の同じ場所に置き直してください。"
                          % (FACTORY_MARK, r["path"], r2["tries"], (r2.get("last") or "")[:120]))
            outbox("【納品が取れない】#%s" % r["num"], "%s を%d回取り直しても取れない" % (r["path"], r2["tries"]), [r["src"]])
            continue
        keep.append(r2)
    st["nouhinRetry"] = keep
    return n


def _drive_tree(path):
    """gsk drive tree の entries を {フルパス: entry} にする（parent_id をたどる）。"""
    rc, out, err = run(["gsk", "--no-input", "drive", "tree", "--path", path], timeout=150)
    d, _ = json.JSONDecoder().raw_decode((out or "").strip())
    data = d.get("data") or {}
    root = data.get("root") or {}
    name = {root.get("entry_id"): path.rstrip("/")}
    ents = data.get("entries", [])
    out_map = {}
    for _ in range(12):  # 深さ（親が後ろに出ても解ける）
        for e in ents:
            pid = e.get("parent_id")
            if e["entry_id"] not in name and pid in name:
                name[e["entry_id"]] = name[pid] + "/" + e["name"]
    for e in ents:
        if e.get("kind") == "file" and e["entry_id"] in name:
            out_map[name[e["entry_id"]]] = e
    return out_map, data.get("has_more")


def check_inbox(st):
    """AI Drive /tamago-inbox/ 以下（全サブフォルダ）の新着を、コメントが無くても取る。"""
    try:
        files, more = _drive_tree(DRIVE_ROOT)
    except Exception as e:
        log("AI Drive /tamago-inbox が読めない: %r" % (e,))
        return 0
    seen = st.setdefault("inboxSeen", None)
    if seen is None:
        # 初回：すでに取ったもの（コメント経由）以外も「新着」として扱う（10/17 は初回の基準に原稿が吸い込まれた）
        seen = []
    seen = set(seen)
    n = 0
    for path, e in sorted(files.items()):
        key = "%s@%s" % (path, e.get("size_bytes"))
        if key in seen:
            continue
        if path in st.get("nouhinGot", {}) or any(x["path"] == path for x in st.get("nouhinRetry", [])):
            seen.add(key)
            continue
        local = os.path.join(INBOX, path[len(DRIVE_ROOT):].strip("/"))
        if os.path.exists(local) and os.path.getsize(local) == (e.get("size_bytes") or -1):
            st.setdefault("nouhinGot", {})[path] = local   # 前に（コメント経由で）取ってあるもの
            seen.add(key)
            continue
        parts = path[len(DRIVE_ROOT):].strip("/").split("/")
        num = parts[0] if len(parts) >= 2 and parts[0].isdigit() else None
        if not num:
            seen.add(key)
            log("AI Drive 番号の無い置き場は取らない: %s" % path)
            continue
        if _take(st, REPOS[0], num, [path], "https://github.com/%s/issues/%s" % (REPOS[0], num), [], "AI Drive の新着（%s）" % path):
            n += 1
        seen.add(key)
    st["inboxSeen"] = sorted(seen)[-5000:]
    if more:
        log("AI Drive /tamago-inbox の一覧が途中まで（has_more）")
    return n


def check_koukai(st):
    """公開見張り：本番が 200 で変わったら Issue に「公開しました」＋Dispatch へ1行。出ていなければ45分で1回だけ「公開ボタン待ち」。"""
    keep = []
    for x in st.get("koukaiMachi", []):
        code, ver = _head(x["url"])
        changed = code == 200 and (x.get("code0") != 200 or (ver and ver != x.get("ver0")))
        if changed:
            _safe_comment(x["num"], x["repo"], "%s\n【Claude Code】公開しました：%s" % (FACTORY_MARK, x["url"]))
            outbox("【公開しました】#%s" % x["num"], x["url"], [x["url"]])
            log("#%s 本番に出た %s（%s→%s）" % (x["num"], x["url"], x.get("code0"), code))
            continue
        age = time.time() - x["since"]
        if age > KOUKAI_NOTIFY_SEC and not x.get("notified"):
            outbox("【公開ボタン待ち】#%s" % x["num"], "Lovable の公開（deploy_project）を押してください：%s（今 HTTP %s）" % (x["url"], code), [x["url"]])
            x["notified"] = True
        if age < KOUKAI_GIVEUP_SEC:
            keep.append(x)
    st["koukaiMachi"] = keep


def write_public(st, picked, dnew):
    try:
        json.dump({"at": time.strftime("%F %T"), "kankaku": "5分", "repos": REPOS, "mark": TITLE_MARK,
                   "kondo": picked, "drive_kondo": dnew, "stats": st["stats"]},
                  open(PUBLIC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def main(force=False):
    import fcntl
    lf = open(LOCK, "a+")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        return 0
    st = load_state()
    now = time.time()
    if not force and now < st["next"]:
        return 0
    st["next"] = now + GATE_SEC
    save_state(st)               # 先に次の時刻を書く（重い回の二重起動を防ぐ）
    st["stats"]["runs"] += 1
    started = now - 10
    picked = check_issues(st, MAX_PER_RUN)
    st["stats"]["picked"] += picked
    for name, fn in (("nouhin", check_nouhin), ("nouhinRetry", retry_nouhin), ("koukai", check_koukai)):
        try:
            r = fn(st)
            if isinstance(r, int):
                st["stats"][name] = st["stats"].get(name, 0) + r
        except Exception as e:
            log("納品受付（%s）で例外: %r" % (name, e))
    if picked < MAX_PER_RUN:
        st["since"] = started
    dnew = 0
    if force or now >= st["driveNext"]:
        st["driveNext"] = now + DRIVE_GATE_SEC
        dnew = check_drive(st)
        st["stats"]["driveNew"] += dnew
        try:
            st["stats"]["inbox"] = st["stats"].get("inbox", 0) + check_inbox(st)
        except Exception as e:
            log("AI Drive の受け取りで例外: %r" % (e,))
    save_state(st)
    write_public(st, picked, dnew)
    return 0


def self_test():
    assert is_target("【Claude Codeに頼む】月の特集")
    assert not is_target("【Julesに頼む】間違い探し")
    assert not is_target("Claude Codeに頼む（括弧なし）")
    j = '{"data":{"entries":[{"entry_id":"a","kind":"file","name":"x.html"},{"entry_id":"b","kind":"directory","name":"d"}]}}\nAlarm'
    assert _drive_files(j) == {"a": "x.html"}
    assert _drive_files("fetch failed") is None
    t = instruction("tamago2022/x", {"number": 1, "title": TITLE_MARK + "t", "url": "u", "body": "b", "author": {"login": "a"}})
    assert FACTORY_MARK in t and "gh issue view 1" in t
    assert _nouhin_paths("【Genspark】\n【納品】/tamago-inbox/1015/a.html\n【納品】 /tamago-inbox/1015/b.md。") == \
        ["/tamago-inbox/1015/a.html", "/tamago-inbox/1015/b.md"]
    assert _nouhin_paths("納品しました /x.html") == []
    assert _issue_no("https://api.github.com/repos/a/b/issues/1015") == "1015"
    assert _haichi("配置先: magazine/a.html\n配置先: /tamago-inbox/1/a.html") == ["magazine/a.html"]
    assert prod_url("/tamago-inbox/1018/x.html") == PROD_BASE + "magazine/x.html"
    assert prod_url("/tamago-inbox/1015/x.html", ["public/magazine/x.html"]) == PROD_BASE + "magazine/x.html"
    assert prod_url("/tamago-inbox/1018/t.skill") is None
    assert _repo_of("https://api.github.com/repos/tamago2022/tamago-shinchoku/issues/5") == "tamago2022/tamago-shinchoku"
    global run
    _run = run
    run = lambda cmd, timeout=60: (0, json.dumps({"data": {"root": {"entry_id": "R"}, "entries": [
        {"entry_id": "F1", "parent_id": "D1", "kind": "file", "name": "a.html", "size_bytes": 3},
        {"entry_id": "D1", "parent_id": "R", "kind": "directory", "name": "1018"}]}}) + "\nAlarm", "")
    try:
        files, _m = _drive_tree("/tamago-inbox")
        assert list(files) == ["/tamago-inbox/1018/a.html"], files
    finally:
        run = _run
    print("SELF-TEST OK")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main(force="--force" in sys.argv))
