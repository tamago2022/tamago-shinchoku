#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""振り分け所（furiwake）— 2026-10-25 たまごさん指示。

たまごさん（原文）：
  「ターミナルを打つだとか、あなたができないことでも、Grok botができたりChatGPTができたりする場合があるから、
    仕事を振るっていうことができるようになってほしい。俺に言わなくても他のエージェントができたりするかもしれないから、
    『これできる人いますか』とあなたが調べて、『これはChatGPTができる』なら仕事を回して。
    自分ができないから俺にやってもらうとかじゃなくて、俺を楽させるのが皆様方の仕事」

■ 何をするか
  ① できること台帳（status/furiwake/dekiru_daicho.json）を見て、頼みごとに一番合うAIを選ぶ
  ② GitHub（joy-relief-station）にラベル「できる人いますか」の Issue を立てる（型：やりたいこと／なぜ自分ではできないか／締め切り／完了条件）
  ③ 選んだAIが拾える形で依頼を出す
       factory  … 命令（--meirei）があれば工場の一発コマンド窓口（status/oneshot）で即実行、無ければ発車待ち（command_ingest.queue_add）
       grok     … 共有メモ（ラベル「店主の指示メモ」の企画「できる人いますか」）へ zen_ai_kyouyu で書く（3時間ごとに読まれる）
       chatgpt  … Issue に「@codex」から始まるコメント（コメントで起きる・#450実測）
       genspark … AI Drive /できる人いますか/<Issue番号>.md に置く（gsk drive upload・無料）
       dispatch … status/dispatch_outbox.jsonl に type=furiwake で1行
  ④ 返事を見張る（Issueのコメント・工場の結果ファイル・発車待ちの状態）。返ってきたら Issue に受領→閉じる→共有メモへ1件。
     締め切り（台帳の matsu_jikan）を過ぎても返らなければ、次の候補へ回す。全員だめなら Dispatch へ1行。
  ⑤ 他のAIや人が自分で「できる人いますか」ラベルの Issue を立てても、同じように拾って振り分ける。

■ 使い方
  サンドボックスの子からでも（gh を使わない・待ち行列に置くだけ）：
    python3 tools/furiwake.py dasu --yaritai "やりたいこと" --naze "自分でできない理由" \
        --kanryo "完了条件" [--shimekiri 2026-10-26] [--ate factory] [--meirei "bash /path/x.sh"]
    python3 tools/furiwake.py erabu "やりたいこと"     # 誰に回るかだけ見る
  Mac の心臓（top_status の相乗り・中で2分に間引く）：
    python3 tools/furiwake.py --tick
  一覧：python3 tools/furiwake.py --ichiran
  逆テスト：python3 tools/furiwake.py --self-test

■ 決まり
  ・たまごさんに回してよいのは パスワード・二段階認証・本人の判断 だけ（台帳の tamago_dake）。それ以外は必ず誰かに回す。
  ・有料APIは叩かない。ブラウザは開かない。許可ポップアップの出る道具は使わない。
  ・命令（--meirei）の実行は工場のMacでだけ。osascript・sudo・tccutil・システム設定を含む命令は流さない（止めて記録）。

作るもの：status/furiwake/{dekiru_daicho.json,machi.jsonl,irai.json,state.json,log,kaeri/*.out}
         ／status/public/furiwake.json ／share/check/furiwake.html（台帳と依頼の一覧）
台帳：tools/jidou_daicho.json の "furiwake.py"（log 300行・irai は終わって30日で刈る・kaeri は7日で消す）
"""
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "furiwake")
DAICHO = os.path.join(D, "dekiru_daicho.json")
MACHI = os.path.join(D, "machi.jsonl")
IRAI = os.path.join(D, "irai.json")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
KAERI = os.path.join(D, "kaeri")
PUB = os.path.join(REPO, "status", "public", "furiwake.json")
PAGE = os.path.join(REPO, "share", "check", "furiwake.html")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
MACJOBS = os.path.join(REPO, "status", "oneshot", "pending")   # 工場の一発コマンド窓口（oneshot_runner・心臓が毎周拾う）

REPO_GH = "tamago2022/joy-relief-station"
LABEL = "できる人いますか"
LABEL_COLOR = "F9D0C4"
PREFIX = "【できる人いますか】"
MARK = "<!-- tamago-factory furiwake -->"
FACTORY_MARK = "<!-- tamago-factory"
GATE_SEC = 120
KIKAKU = "できる人いますか"
DRIVE_DIR = "/できる人いますか"
TEMPLATE_PATH = ".github/ISSUE_TEMPLATE/dekiru-hito-imasuka.md"
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/furiwake.html"
FURIWAKE_URL = "https://github.com/%s/issues?q=label%%3A%s" % (REPO_GH, "%E3%81%A7%E3%81%8D%E3%82%8B%E4%BA%BA%E3%81%84%E3%81%BE%E3%81%99%E3%81%8B")

PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))

TAMAGO_DAKE_RX = re.compile(r"パスワード|二段階|2段階|暗証|ワンタイム|認証コード|本人確認")
KIKEN_RX = re.compile(r"\b(osascript|sudo|tccutil|defaults\s+write|csrutil|spctl)\b|rm\s+-rf\s+[~/]")

TEMPLATE_BODY = """---
name: できる人いますか（振り分け所）
about: 自分ではできない仕事を、できるAIに回す。たまごさんに頼む前にまずここ。
title: "【できる人いますか】"
labels: ["できる人いますか"]
---

## やりたいこと


## なぜ自分ではできないか


## 締め切り


## 完了条件


<!-- 担当は工場の振り分け係（tools/furiwake.py）が、できること台帳から選んで自動で依頼します。
     できること台帳：%s
     たまごさんに回してよいのは パスワード・二段階認証・本人の判断 だけ。 -->
""" % PAGE_URL


def exe(name):
    return shutil.which(name, path=ENV["PATH"]) or name


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg):
    try:
        os.makedirs(D, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
        ls = open(LOG, encoding="utf-8").read().splitlines()
        if len(ls) > 400:
            open(LOG, "w", encoding="utf-8").write("\n".join(ls[-300:]) + "\n")
    except Exception:
        pass


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".w"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def daicho():
    return load(DAICHO, {"ai": []})


# ---------------------------------------------------------------- 担当を選ぶ
def erabu(text, tags=None, ate=None, nozoku=()):
    """候補を良い順に返す。[(id, 点, 理由)]。たまごさんにしかできないものは [('tamago',..)]。"""
    text = text or ""
    if TAMAGO_DAKE_RX.search(text):
        return [("tamago", 99, "パスワード・二段階認証はたまごさんだけ")]
    t = text.lower()
    tags = set(tags or [])
    out = []
    for a in daicho().get("ai", []):
        if a["id"] in nozoku:
            continue
        if ate and a["id"] == ate:
            out.append((a["id"], 100, "指名"))
            continue
        hit_t = sorted(tags & set(a.get("dekiru", [])))
        hit_k = [k for k in a.get("kotoba", []) if k.lower() in t]
        score = len(hit_t) * 3 + len(hit_k)
        if score > 0:
            out.append((a["id"], score, "できること:%s 言葉:%s" % ("・".join(hit_t) or "-", "・".join(hit_k[:5]) or "-")))
    jun = {a["id"]: a.get("jun", 9) for a in daicho().get("ai", [])}
    out.sort(key=lambda x: (-x[1], jun.get(x[0], 9)))
    if not out:  # 誰の言葉にも当たらない＝何でも屋の工場→Dispatch
        out = [(i, 0, "当てはまる人がいないので順番どおり") for i in ("factory", "dispatch") if i not in nozoku]
    return out


def ai_info(aid):
    for a in daicho().get("ai", []):
        if a["id"] == aid:
            return a
    return {"id": aid, "namae": aid, "matsu_jikan": 12}


# ---------------------------------------------------------------- 出す（どこからでも）
def dasu(yaritai, naze, kanryo, shimekiri="", ate="", meirei="", tags=None, who="Claude"):
    os.makedirs(D, exist_ok=True)
    rec = {"id": "fw-%s-%s" % (time.strftime("%Y%m%d%H%M%S"), hashlib.sha1((yaritai + str(time.time())).encode()).hexdigest()[:5]),
           "at": now_iso(), "who": who, "yaritai": (yaritai or "").strip()[:200], "naze": (naze or "").strip()[:1500],
           "kanryo": (kanryo or "").strip()[:1500], "shimekiri": (shimekiri or "").strip()[:40],
           "ate": (ate or "").strip(), "meirei": (meirei or "").strip()[:2000], "tags": list(tags or [])}
    with open(MACHI, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def issue_body(r):
    return "%s\n<!-- fwid:%s -->\n## やりたいこと\n%s\n\n## なぜ自分ではできないか\n%s\n\n## 締め切り\n%s\n\n## 完了条件\n%s\n\n%s\n（出した人：%s・%s／できること台帳：%s）" % (
        MARK, r.get("id", ""), r["yaritai"], r.get("naze") or "（未記入）", r.get("shimekiri") or "なし（できしだい）",
        r.get("kanryo") or "（未記入）",
        ("## 命令（工場のMacで実行）\n```\n%s\n```\n" % r["meirei"]) if r.get("meirei") else "",
        r.get("who", ""), r.get("at", "")[:16], PAGE_URL)


def parse_issue(body):
    """人や他のAIが型で立てた Issue を読む。"""
    def sec(name):
        m = re.search(r"^##[ \t]*%s[ \t]*\n(.*?)(?=^##\s|\Z)" % re.escape(name), body or "", re.S | re.M)
        return re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip() if m else ""
    return {"yaritai": sec("やりたいこと"), "naze": sec("なぜ自分ではできないか"),
            "shimekiri": sec("締め切り"), "kanryo": sec("完了条件")}


# ---------------------------------------------------------------- gh（Macだけ）
def gh(args, timeout=90):
    p = subprocess.run([exe("gh")] + args, capture_output=True, text=True, timeout=timeout, env=ENV)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "")[:300])
    return p.stdout.strip()


def gh_comment(num, body):
    return gh(["api", "repos/%s/issues/%s/comments" % (REPO_GH, num), "-f", "body=" + body, "--jq", ".html_url"])


def setup(st):
    """ラベルとIssueの型を1回だけ用意（冪等）。"""
    if not st.get("label"):
        try:
            gh(["label", "create", LABEL, "-R", REPO_GH, "--color", LABEL_COLOR,
                "--description", "自分ではできない仕事を、できるAIに回す振り分け所（tools/furiwake.py）"])
            log("ラベルを作った")
        except RuntimeError as e:
            if "already exists" not in str(e):
                raise
        st["label"] = True
    if not st.get("template"):
        import base64
        sha = ""
        try:
            sha = gh(["api", "repos/%s/contents/%s" % (REPO_GH, TEMPLATE_PATH), "--jq", ".sha"])
        except RuntimeError:
            pass
        args = ["api", "-X", "PUT", "repos/%s/contents/%s" % (REPO_GH, TEMPLATE_PATH),
                "-f", "message=振り分け所：Issueの型「できる人いますか」を足す（tools/furiwake.py）",
                "-f", "content=" + base64.b64encode(TEMPLATE_BODY.encode("utf-8")).decode(), "--jq", ".content.html_url"]
        if sha:
            args[5:5] = ["-f", "sha=" + sha]
        st["template"] = gh(args)
        log("Issueの型を置いた %s" % st["template"])


# ---------------------------------------------------------------- 回す
def okuru(ir, aid):
    """選んだAIへ依頼を出す。戻り値：何をしたかの一言。"""
    num = ir["issue"]
    url = ir.get("url", "")
    a = ai_info(aid)
    head = "%s\n**振り分け**：%s さんに回しました（%s）。締め切りの目安 %s時間。\n" % (
        MARK, a.get("namae", aid), ir.get("riyuu", ""), a.get("matsu_jikan", 12))
    if aid == "factory":
        if ir.get("meirei"):
            if KIKEN_RX.search(ir["meirei"]):
                raise RuntimeError("危ない命令（osascript/sudo/tccutil 等）なので流さない")
            os.makedirs(KAERI, exist_ok=True)
            out = os.path.join(KAERI, "%s.out" % ir["id"])
            job = os.path.join(MACJOBS, "fw_%s.sh" % ir["id"].replace("-", "_"))
            inner = ("{ echo \"== start $(date '+%%F %%T')\"; ( %s ) ; echo \"== rc=$? end $(date '+%%F %%T')\"; } > %s 2>&1; mv %s %s"
                     % (ir["meirei"], shq(out + ".part"), shq(out + ".part"), shq(out)))
            os.makedirs(MACJOBS, exist_ok=True)
            with open(job + ".w", "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n# 振り分け所 %s（Issue #%s）。180秒の枠を越えても切れないよう裏で走らせる\n"
                        "( nohup /bin/bash -c %s ) </dev/null >/dev/null 2>&1 &\necho started\nexit 0\n"
                        % (ir["id"], num, shq(inner)))
            os.replace(job + ".w", job)
            ir["kaeri_file"] = out
            gh_comment(num, head + "工場のMacの一発コマンド窓口（status/oneshot）で命令を実行します。結果はこのIssueに貼ります。")
            return "工場の使い走りに置いた"
        import command_ingest
        text = "【振り分け所 #%s】%s\n\n%s\n\n完了条件：%s\n締め切り：%s\n\n終わったら結果の一言を、このIssueにコメントで返す：%s" % (
            num, ir["yaritai"], ir.get("naze", ""), ir.get("kanryo", ""), ir.get("shimekiri") or "なし", url)
        status, msg = command_ingest.queue_add(text, priority=1, label="振り分け所", origin="factory")
        m = re.search(r"(\d{3,})", msg or "")
        ir["queue_n"] = m.group(1) if m else ""
        gh_comment(num, head + "工場の発車待ちに積みました（%s：%s）。" % (status, (msg or "")[:120]))
        return "発車待ちに積んだ %s" % ir["queue_n"]
    if aid == "grok":
        import zen_ai_kyouyu
        zen_ai_kyouyu.kaku("Grokボットさんへ：%s" % ir["yaritai"],
                           "振り分け所から、Grokボットさんにお願いです。\n依頼の本体：%s\n\n完了条件：%s\n締め切り：%s\n"
                           "終わったら、上の依頼のIssueにコメントで結果を返してください（店主に伝言をさせない）。" % (
                               url, ir.get("kanryo", ""), ir.get("shimekiri") or "なし"), kikaku=KIKAKU)
        gh_comment(num, head + "共有メモ（ラベル「店主の指示メモ」・企画「%s」）に書きました。Grokボットは3時間ごとに読みます。" % KIKAKU)
        return "共有メモに書いた"
    if aid == "chatgpt":
        gh_comment(num, "@codex 上の「やりたいこと」をお願いします。完了条件を満たしたら、このIssueにコメントで結果（1行目に結論）を返してください。人間への確認は不要です。\n" + MARK)
        return "@codex で起こした"
    if aid == "genspark":
        txt = "# 振り分け所からの依頼（Issue #%s）\n\n%s\n\n%s\n\n返し方：AI Drive /tamago-inbox/%s/ に納品するか、%s にコメント。\n" % (
            num, url, issue_body(ir), num, url)
        p = subprocess.run([exe("gsk"), "drive", "upload", "--upload_path", "%s/%s.md" % (DRIVE_DIR, num),
                            "--file_content", txt, "--overwrite", "true", "--no-input"],
                           capture_output=True, text=True, timeout=120, env=ENV)
        if p.returncode != 0:
            raise RuntimeError("AI Drive に置けない: %s" % (p.stderr or p.stdout or "")[:160])
        gh_comment(num, head + "Genspark の AI Drive %s/%s.md に置きました。" % (DRIVE_DIR, num))
        return "AI Drive に置いた"
    if aid == "dispatch":
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%F %T"), "n": "furiwake-%s" % ir["id"], "type": "furiwake",
                                "from": "furiwake", "title": "できる人いますか：%s" % ir["yaritai"][:60],
                                "message": "Dispatch さんにお願い。完了条件：%s／結果は Issue にコメントで。" % ir.get("kanryo", "")[:200],
                                "urls": [url]}, ensure_ascii=False) + "\n")
        gh_comment(num, head + "Dispatch に1行出しました。")
        return "Dispatchに出した"
    raise RuntimeError("知らない担当 %s" % aid)


def shq(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


# ---------------------------------------------------------------- 見張る
def henji_issue(ir):
    """依頼後に付いた、振り分け係以外のコメント（＝返事）。"""
    out = gh(["api", "repos/%s/issues/%s/comments?per_page=100" % (REPO_GH, ir["issue"]),
              "--jq", '.[] | [.created_at, .user.login, .html_url, (.body|gsub("\\n";" ")|.[0:400])] | @tsv'])
    res = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        at, who, u, body = parts[:4]
        if body.startswith(FACTORY_MARK):
            continue
        if body.startswith("@codex"):
            continue
        if at < ir.get("okutta_at_utc", ""):
            continue
        res.append({"at": at, "who": who, "url": u, "body": body})
    return res


def henji_factory(ir):
    f = ir.get("kaeri_file")
    if f:
        if os.path.exists(f):
            body = open(f, encoding="utf-8", errors="replace").read()
            m = re.search(r"== rc=(\d+) end", body)
            if m and m.group(1) != "0":  # 命令が失敗・止めた（STOP）＝終わっていない。結果を貼って次の候補へ
                ir["factory_ng"] = "rc=%s" % m.group(1)
                try:
                    gh_comment(ir["issue"], "%s\n**工場の結果（失敗 rc=%s）**\n```\n%s\n```" % (MARK, m.group(1), body[-2500:]))
                except Exception:
                    pass
                return []
            return [{"who": "工場（Mac）", "url": "", "body": body[-3000:]}]
        return []
    n = ir.get("queue_n")
    if not n:
        return []
    q = load(os.path.join(REPO, "status", "queue.json"), {})
    items = q.get("items", q) if isinstance(q, dict) else q
    for it in items:
        if str(it.get("n")) == str(n):
            stt = it.get("status") or it.get("state") or ""
            if stt in ("done", "awaiting_check", "merged", "passed"):
                return [{"who": "工場（Claude Code）", "url": it.get("touchUrl", ""), "body": (it.get("result") or stt)[:1500]}]
            if stt in ("cancelled", "fix_required", "hold"):
                ir["factory_ng"] = stt
    return []


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def susumeru(ir, st):
    """1件の依頼を1歩進める。"""
    if ir["jotai"] in ("owari", "dare_mo", "tamago"):
        return
    if ir["jotai"] == "mada":
        kouho = erabu(ir["yaritai"] + " " + ir.get("naze", "") + " " + ir.get("meirei", ""), ir.get("tags"),
                      ir.get("ate"), nozoku=ir.get("tameshita", []))
        if kouho and kouho[0][0] == "tamago":
            ir["jotai"] = "tamago"
            gh_comment(ir["issue"], MARK + "\nパスワード・二段階認証が要るので、ここだけはたまごさんの番です（台帳の tamago_dake）。")
            outbox("たまごさんの番：%s" % ir["yaritai"][:60], "パスワード・二段階認証が要る依頼です", [ir.get("url", "")])
            return
        if not kouho:
            ir["jotai"] = "dare_mo"
            gh_comment(ir["issue"], MARK + "\nできること台帳の全員に回しましたが、返事がありませんでした。Dispatch に上げます。")
            outbox("誰もできなかった：%s" % ir["yaritai"][:60], "試した：%s" % "・".join(ir.get("tameshita", [])), [ir.get("url", "")])
            return
        aid, score, riyuu = kouho[0]
        ir["ate_ima"], ir["riyuu"] = aid, riyuu
        ir["okutta_at"], ir["okutta_at_utc"] = time.time(), utc_now()
        ir.setdefault("tameshita", []).append(aid)
        ir["shita"] = okuru(ir, aid)
        ir["jotai"] = "matsu"
        log("回した #%s → %s（%s）" % (ir["issue"], aid, ir["shita"]))
        return
    # matsu：返事を見る
    aid = ir["ate_ima"]
    hen = henji_factory(ir) if aid == "factory" else []
    if not hen:
        hen = henji_issue(ir)
    if hen:
        h = hen[-1]
        ir["jotai"], ir["kaeri"], ir["owari_at"] = "owari", h, time.time()
        body = h["body"]
        if aid == "factory" and ir.get("kaeri_file"):
            gh_comment(ir["issue"], "%s\n**工場の結果**\n```\n%s\n```" % (MARK, body[-2500:]))
        gh_comment(ir["issue"], "%s\n受け取りました（%s・%s）。共有メモに書いて閉じます。" % (MARK, h.get("who", ""), h.get("url", "")))
        try:
            gh(["issue", "close", str(ir["issue"]), "-R", REPO_GH])
        except Exception as e:
            log("閉じられない #%s %r" % (ir["issue"], e))
        try:
            import zen_ai_kyouyu
            zen_ai_kyouyu.kaku("終わった：%s（%s）" % (ir["yaritai"][:60], ai_info(aid).get("namae", aid)),
                               "%s\n担当：%s\n結果：%s" % (ir.get("url", ""), ai_info(aid).get("namae", aid), body[-800:]), kikaku=KIKAKU)
        except Exception as e:
            log("共有メモに書けない %r" % (e,))
        log("返ってきた #%s ← %s" % (ir["issue"], aid))
        return
    kigen = float(ai_info(aid).get("matsu_jikan", 12)) * 3600
    if ir.get("factory_ng") or time.time() - ir.get("okutta_at", 0) > kigen:
        gh_comment(ir["issue"], "%s\n%s さんから締め切りまでに返事が無かったので、次の候補に回します。" % (MARK, ai_info(aid).get("namae", aid)))
        ir["jotai"] = "mada"
        ir.pop("kaeri_file", None)
        ir.pop("factory_ng", None)


def outbox(title, message, urls):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%F %T"), "n": "furiwake-%d" % int(time.time() * 1000), "type": "furiwake",
                            "from": "furiwake", "title": title, "message": message, "urls": urls}, ensure_ascii=False) + "\n")


def tick(force=False):
    st = load(STATE, {})
    if not force and time.time() - st.get("last", 0) < GATE_SEC:
        return
    st["last"] = time.time()
    save(STATE, st)
    irai = load(IRAI, [])
    try:
        setup(st)
    except Exception as e:
        log("用意ができない %r" % (e,))
    # ① 待ち行列 → Issue
    try:
        machi = [json.loads(l) for l in open(MACHI, encoding="utf-8").read().splitlines() if l.strip()]
    except Exception:
        machi = []
    keep = []
    aru = {}
    if machi:  # 前回タイムアウトしたが実は立っていた、の二重立てを防ぐ（本文の fwid で照合）
        try:
            for it in json.loads(gh(["issue", "list", "-R", REPO_GH, "--label", LABEL, "--state", "all", "--limit", "100",
                                     "--json", "number,url,body"], timeout=120) or "[]"):
                m = re.search(r"<!-- fwid:(\S+) -->", it.get("body") or "")
                if m:
                    aru[m.group(1)] = (it["number"], it["url"])
        except Exception as e:
            log("一覧が取れない（立てるのは次回）%r" % (e,))
            return save(STATE, st)
    for r in machi:
        try:
            if r["id"] in aru:
                num, u = aru[r["id"]]
            else:
                u = gh(["issue", "create", "-R", REPO_GH, "--label", LABEL, "--title", PREFIX + r["yaritai"][:80], "--body", issue_body(r)], timeout=150)
                num = int(u.rstrip("/").rsplit("/", 1)[-1])
            r.update({"issue": num, "url": u, "jotai": "mada"})
            irai.append(r)
            log("Issueを立てた %s" % u)
        except Exception as e:
            r["tries"] = r.get("tries", 0) + 1
            log("Issueを立てられない（%d回目）%r" % (r["tries"], e))
            if r["tries"] < 20:
                keep.append(r)
    with open(MACHI + ".w", "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep))
    os.replace(MACHI + ".w", MACHI)
    # ② 人や他のAIが立てた「できる人いますか」も拾う
    try:
        known = {i.get("issue") for i in irai}
        out = gh(["issue", "list", "-R", REPO_GH, "--label", LABEL, "--state", "open", "--limit", "50",
                  "--json", "number,title,body,url,author"])
        for it in json.loads(out or "[]"):
            if it["number"] in known or (it.get("body") or "").startswith(FACTORY_MARK):
                continue
            p = parse_issue(it.get("body"))
            p["yaritai"] = p["yaritai"] or it["title"].replace(PREFIX, "").strip()
            irai.append(dict(p, id="fw-gh-%s" % it["number"], at=now_iso(), who=(it.get("author") or {}).get("login", ""),
                             issue=it["number"], url=it["url"], jotai="mada", meirei="", ate="", tags=[]))
            log("よそが立てた依頼を拾った #%s" % it["number"])
    except Exception as e:
        log("一覧が取れない %r" % (e,))
    # ③ 進める
    for ir in irai:
        try:
            susumeru(ir, st)
        except Exception as e:
            ir["err"] = str(e)[:200]
            log("進められない #%s %r" % (ir.get("issue"), e))
    # ④ 刈る・書き出す
    cut = time.time() - 30 * 86400
    irai = [i for i in irai if not (i.get("jotai") in ("owari", "dare_mo") and i.get("owari_at", time.time()) < cut)]
    for fn in (os.listdir(KAERI) if os.path.isdir(KAERI) else []):
        p = os.path.join(KAERI, fn)
        if time.time() - os.path.getmtime(p) > 7 * 86400:
            os.remove(p)
    save(IRAI, irai)
    save(STATE, st)
    kakidasu(irai)


# ---------------------------------------------------------------- 一覧（公開）
JOTAI = {"mada": "これから回す", "matsu": "返事待ち", "owari": "終わった", "dare_mo": "誰もできなかった", "tamago": "たまごさんの番"}


def _yomikuchi_section(d):
    """2026-10-25 読み口（どのAIがどの部屋を読めて・書けるか）をこの台帳ページに統合。壊れていても台帳は出す。"""
    try:
        import yomikuchi
        return yomikuchi.html_table(json.loads(json.dumps(d)))
    except Exception:
        return ""


def kakidasu(irai):
    d = daicho()
    pub = {"kousin": time.strftime("%F %T"), "furiwakejo": FURIWAKE_URL, "daicho": PAGE_URL,
           "ai": [{k: a.get(k) for k in ("id", "namae", "dekiru", "uketsuke", "henji", "dekinai", "youkakunin")} for a in d.get("ai", [])],
           "irai": [{"issue": i.get("issue"), "url": i.get("url"), "yaritai": i.get("yaritai"), "jotai": JOTAI.get(i.get("jotai"), i.get("jotai")),
                     "ate": i.get("ate_ima", ""), "tameshita": i.get("tameshita", []), "kaeri": (i.get("kaeri") or {}).get("body", "")[-300:]}
                    for i in reversed(irai[-50:])]}
    save(PUB, pub)
    tagi = d.get("_tag_no_imi", {})
    E = html.escape
    rows = []
    for a in d.get("ai", []):
        rows.append("<tr><th>%s</th><td>%s</td><td>%s</td><td>%s</td><td class=y>%s</td></tr>" % (
            E(a["namae"]), "<br>".join(E(tagi.get(t, t)) for t in a.get("dekiru", [])),
            E(a.get("uketsuke", "")), "<br>".join(E(x) for x in a.get("dekinai", [])),
            "<br>".join("要確認：" + E(x) for x in a.get("youkakunin", [])) or "—"))
    irows = "".join("<tr><td><a href='%s'>#%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        E(i["url"] or ""), i["issue"], E(i["yaritai"] or ""), E(i["jotai"] or ""), E(ai_info(i["ate"]).get("namae", i["ate"]) if i["ate"] else "")) for i in pub["irai"]) \
        or "<tr><td colspan=4>まだありません</td></tr>"
    page = """<!doctype html><html lang=ja><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>できること台帳｜振り分け所</title><style>body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:16px;line-height:1.6;color:#222}
table{border-collapse:collapse;width:100%%;font-size:14px;margin:8px 0 24px}th,td{border:1px solid #ddd;padding:6px;vertical-align:top;text-align:left}
th{background:#faf6ef;white-space:nowrap}.y{color:#a35a00}h1{font-size:20px}h2{font-size:17px;margin-top:24px}</style>
<h1>できること台帳（振り分け所）</h1>
<p>自分でできないことは、たまごさんに頼む前に<a href="%s">振り分け所（GitHub・ラベル「できる人いますか」）</a>へ。担当は工場の振り分け係が自動で選んで依頼し、返事まで見張ります。<br>
たまごさんに回してよいのは <b>パスワード・二段階認証・本人の判断</b> だけ。更新 %s</p>
<h2>誰が何をできるか</h2><div style="overflow-x:auto"><table><tr><th>AI</th><th>できること</th><th>頼み方</th><th>できないこと</th><th>要確認</th></tr>%s</table></div>
%s
<h2>依頼の一覧（新しい順）</h2><table><tr><th>Issue</th><th>やりたいこと</th><th>状態</th><th>担当</th></tr>%s</table>
<p><a href="https://tamago2022.github.io/tamago-shinchoku/">進捗表へ戻る</a></p></html>
""" % (FURIWAKE_URL, pub["kousin"], "".join(rows), _yomikuchi_section(d), irows)
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    open(PAGE, "w", encoding="utf-8").write(page)


# ---------------------------------------------------------------- 逆テスト
def self_test():
    assert erabu("Mac上で install.sh を実行して launchd に登録")[0][0] == "factory"
    assert erabu("Xのポストを読んで要約")[0][0] == "grok"
    assert erabu("記事用の画像を作って")[0][0] == "genspark"
    assert erabu("ログインのパスワードを入れて")[0][0] == "tamago"
    assert erabu("なにか", ate="chatgpt")[0][0] == "chatgpt"
    assert erabu("Mac で実行", nozoku=("factory",))[0][0] != "factory"
    assert erabu("ふわっとした話")[0][0] == "factory"
    p = parse_issue("## やりたいこと\nA\n\n## なぜ自分ではできないか\nB\n## 締め切り\n\n## 完了条件\nC <!-- x -->\n")
    assert p == {"yaritai": "A", "naze": "B", "shimekiri": "", "kanryo": "C"}, p
    b = issue_body({"yaritai": "Y", "naze": "N", "kanryo": "K", "meirei": "bash x.sh", "who": "w", "at": "2026"})
    assert b.startswith(MARK) and "## 完了条件\nK" in b and "bash x.sh" in b
    assert KIKEN_RX.search("sudo rm x") and KIKEN_RX.search("osascript -e") and not KIKEN_RX.search("bash install.sh")
    assert parse_issue(TEMPLATE_BODY)["yaritai"] == ""
    print("furiwake self-test OK")


def main(a):
    if "--self-test" in a:
        return self_test()
    if "--tick" in a:
        return tick(force="--force" in a)
    if "--ichiran" in a:
        for i in load(IRAI, []):
            print("#%s %s ／ %s ／ 担当 %s" % (i.get("issue"), JOTAI.get(i.get("jotai"), i.get("jotai")), i.get("yaritai"), i.get("ate_ima", "")))
        return
    def opt(k):
        return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
    if a and a[0] == "erabu":
        for aid, s, why in erabu(" ".join(x for x in a[1:] if not x.startswith("--")), ate=opt("--ate")):
            print("%s（%s点）%s" % (ai_info(aid).get("namae", aid), s, why))
        return
    if a and a[0] == "dasu":
        if not opt("--yaritai"):
            raise SystemExit("--yaritai が要ります")
        r = dasu(opt("--yaritai"), opt("--naze"), opt("--kanryo"), opt("--shimekiri"), opt("--ate"), opt("--meirei"),
                 [t for t in opt("--tags").split(",") if t], who=opt("--who") or "Claude")
        k = erabu(r["yaritai"] + " " + r["naze"] + " " + r["meirei"], r["tags"], r["ate"])
        print("振り分け所に出しました（2分以内にIssue化→%s へ）：%s" % (ai_info(k[0][0]).get("namae", k[0][0]), r["id"]))
        return
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
