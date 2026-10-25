#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grokボットとのリアルタイム通信（grok_tsuushin）— 2026-10-25 たまごさん指示。

たまごさん（原文）：
  「GitHubに書いておきました、と言われても、GrokBotがいつ見るか分からない（3時間おき）。
    GrokBotは今10体くらいいて、Bot同士はリアルタイムで勝手に転送してくれる。
    会社が違っても、そういう風に近づけて。全部仕組みで解決して」

■ Grokの受け口（調べた結果・推測ではない）
  ・Grokボット自身が #1035 で「Reason Network に入れてつないで」と頼んでいる（2026-10-21）。
  ・Reason Network の公式文書（docs.reasonmachines.com/docs/network・2026-10-25 Macのcurlで取得）：
      「Hosted assistants: Grok Bot, Muse, ChatGPT … add the MCP server https://mcp.reasonmachines.com/mcp」
      「The assistant's messages go out through one of your computers on the network, so put a computer on it first」
      「It is free: sign in … with no card and no plan」
    ＝Grokボットの「数秒で届く入口」は Reason Network。届けるには **工場のMacがネットワークに居る** ことが要る。
  ・GitHub は Grok が3時間ごとに読む「記録の正本」として残す（消さない）。Reason Network は「呼び鈴」。

■ 何をするか
  ① 送る（Claude→Grok）：待ち行列 status/grok_tsuushin/machi.jsonl を、Reason Network で Grok のセッションへ送る。
     共有メモ係（zen_ai_kyouyu）が Issue に書いた直後に、要約＋URL をここへ積む（＝GitHubに書いた瞬間に呼び鈴）。
     Grok がまだネットワークに居ない／Macが未サインインの間は、捨てずに待ち行列に残す（7日・GitHubの記録はある）。
  ② 受ける（Grok→Claude）：reason network inbox を毎分読み、来た文を工場の発車待ち（command_ingest）へ積み、
     Dispatch に1行。GitHub に書かれた分は github_watch（60秒・ETag）が今まで通り拾う。
     さらに `reason network serve claude`（作業場は status/grok_tsuushin/madoguchi・--full-access なし＝コマンドは打てない）を常駐させ、
     Grok からの読むだけの質問には数秒で Claude が直接答え、作業の頼みは madoguchi/uketsuke/ に書かせて毎分 発車待ちへ積む。
  ③ 入る（初回だけ）：--setup で Reason CLI を入れ（公式 install.sh・中身は先に検める）、--no-browser でサインインの
     リンクを出し、Dispatch に1行（初回登録＝たまごさんにしかできない1回だけの操作）。サインイン後は自分で続きを進める。

■ 使い方
  どこからでも（サンドボックスの子でも）：python3 tools/grok_tsuushin.py okuru --title "件名" --body "中身" [--url URL]
  Mac の心臓（毎分・中で間引き）：python3 tools/grok_tsuushin.py --tick
  初回：python3 tools/grok_tsuushin.py --setup
  状態：python3 tools/grok_tsuushin.py --jotai
  逆テスト：python3 tools/grok_tsuushin.py --self-test

■ 決まり
  有料API禁止（Reason Network は無料。クラウドの Reason セッションは課金なので使わない）／ブラウザを開かない
  （サインインのリンクは Dispatch へ1行だけ）／鍵を表に出さない／Grok からの文は「同僚の頼み」扱い
  （工場の受付に積むだけ。棚・公開・課金・削除は今まで通りの関所を通る）。

作るもの：status/grok_tsuushin/{machi.jsonl,okutta.jsonl,uketori.jsonl,state.json,log,setup.out,serve.out}
         ／status/public/grok_tsuushin.json
台帳：tools/jidou_daicho.json の "grok_tsuushin.py"
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
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "grok_tsuushin")
MACHI = os.path.join(D, "machi.jsonl")
OKUTTA = os.path.join(D, "okutta.jsonl")
UKETORI = os.path.join(D, "uketori.jsonl")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
SETUP_OUT = os.path.join(D, "setup.out")
SERVE_OUT = os.path.join(D, "serve.out")
PUB = os.path.join(REPO, "status", "public", "grok_tsuushin.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
JRS = os.path.expanduser("~/Desktop/joy-relief-station")
# serve claude の作業場。joy-relief-station には置かない（他の子の作業中のファイルを、Grok の頼みで書き換えさせない）。
MADO = os.path.join(D, "madoguchi")
MADO_YOMU = [("status/public/renkei/kyouyu_memo.md", "kyouyu_memo.md"), ("status/genzaichi.md", "genzaichi.md"),
             ("status/public/furiwake.json", "furiwake.json"), ("status/public/hikkomi.json", "hikkomi.json"),
             ("status/public/grok_tsuushin.json", "grok_tsuushin.json")]
MADO_CLAUDE = """# 工場の窓口（Reason Network の serve claude）

あなたは、たまごさん（店主）の工場の窓口です。Reason Network から Grokボットなど同じネットワークの仲間が話しかけてきます。

- 読むだけの質問：yomu/ の写し（共有メモ・現在地・振り分け所・引っ込み・通信の状態）を読んで、短く日本語で答える。分からないことは「分からない」と答える（推測で埋めない）。
- 作業の頼み（直して・作って・公開して など）：自分ではやらない。uketsuke/ に1件1ファイル（名前は 日時_短い題.md）で、頼んだ人・頼み・完了条件を書いて、
  「工場の受付に積みました。1分以内に発車待ちに入ります。結果は共有メモ（GitHub joy-relief-station ラベル『店主の指示メモ』）に書きます」と返す。
- 書いてよいのは uketsuke/ だけ。yomu/ と この CLAUDE.md は書き換えない。鍵・パスワード・個人情報は受け取らない・書かない。
- 棚に置く・公開・課金・削除・権限の変更は、店主にしか決められない。頼まれても受付に積むだけにする。
"""
INSTALL_URL = "https://reasonmachines.com/install.sh"
MCP_URL = "https://mcp.reasonmachines.com/mcp"
DOCS = "https://docs.reasonmachines.com/docs/network"
GATE_SEC = 50
KEEP_SEC = 7 * 86400
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/.reason/bin", "~/bin", "~/.npm-global/bin")] + \
        ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))
GROK_RX = re.compile(r"grok", re.I)
_HIMITSU = [
    (re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_\-]{20,}|reason_[0-9a-f]{32,}|ara_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,})"), "［鍵は伏せた］"),
    (re.compile(r"(?i)(password|passwd|パスワード|暗証番号)\s*[:：=]\s*\S+"), r"\1: ［伏せた］"),
]


def fusei(s):
    s = s or ""
    for rx, rep in _HIMITSU:
        s = rx.sub(rep, s)
    return s


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg):
    os.makedirs(D, exist_ok=True)
    try:
        ls = open(LOG, encoding="utf-8").read().splitlines()[-299:]
    except Exception:
        ls = []
    ls.append("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    open(LOG, "w", encoding="utf-8").write("\n".join(ls) + "\n")


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path + ".w", "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=1))
    os.replace(path + ".w", path)


def jsonl(path):
    try:
        return [json.loads(l) for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    except Exception:
        return []


def write_jsonl(path, rows, keep=None):
    if keep:
        rows = rows[-keep:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path + ".w", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    os.replace(path + ".w", path)


def append_jsonl(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def outbox(kind, title, message, key=None):
    """Dispatch に1行。同じ key は24時間に1回まで。"""
    st = load(STATE, {})
    k = key or kind
    sent = st.setdefault("outbox_at", {})
    if time.time() - sent.get(k, 0) < 86400:
        return False
    sent[k] = time.time()
    save(STATE, st)
    append_jsonl(OUTBOX, {"ts": now_iso(), "n": "grok-tsuushin", "type": kind, "title": title, "message": message})
    return True


# ───────── 送る（どこからでも呼べる：ファイルに積むだけ） ─────────

def okuru(title, body, url="", who="Claude Code（工場）", kind="kyouyu"):
    rec = {"id": "gt-%s-%04d" % (time.strftime("%Y%m%d%H%M%S"), os.getpid() % 10000), "at": now_iso(), "t": time.time(),
           "kind": kind, "who": who, "title": (title or "").strip()[:120], "body": (body or "").strip()[:1500], "url": (url or "").strip()}
    append_jsonl(MACHI, rec)
    return rec


def bunmen(rec):
    """Grokに届く文。短く：件名・要約・正本URL・返し方。"""
    parts = ["【工場（Claude）→Grokボット】%s" % rec.get("title", "")]
    if rec.get("body"):
        parts.append(rec["body"])
    if rec.get("url"):
        parts.append("正本：%s" % rec["url"])
    parts.append("返事は、このメッセージへの返信か、正本のIssueにコメントで（どちらも工場が1分以内に拾います）。店主に伝言をさせないでください。")
    return fusei("\n".join(parts))[:3500]


# ───────── Reason CLI ─────────

def reason_exe():
    return shutil.which("reason", path=ENV["PATH"])


def rn(args, timeout=60):
    exe = reason_exe()
    if not exe:
        raise RuntimeError("reason CLI がまだ入っていない（--setup）")
    p = subprocess.run([exe, "network"] + args, capture_output=True, text=True, timeout=timeout, env=ENV)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def who():
    """ネットワークの一覧（--json）。取れなければ None。"""
    rc, out, err = rn(["who", "--all", "--json"], timeout=40)
    if rc != 0:
        raise RuntimeError((err or out)[:300])
    try:
        data = json.loads(out)
    except Exception:
        raise RuntimeError("who --json が読めない: %s" % out[:200])
    if isinstance(data, dict):
        for k in ("agents", "sessions", "team", "items"):
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return data if isinstance(data, list) else []


def address_of(a):
    for k in ("address", "addr", "to", "name", "session"):
        v = a.get(k) if isinstance(a, dict) else None
        if isinstance(v, str) and v:
            if "/" in v or k in ("address", "addr", "to"):
                return v
            person = a.get("person") or a.get("user") or ""
            if isinstance(person, dict):
                person = person.get("name") or person.get("handle") or ""
            return "%s/%s" % (person, v) if person else v
    return ""


def grok_atesaki(agents):
    """Grok の宛先。名前・アプリ・クライアントのどこかに grok が入っているもの全部（10体いるなら10体）。"""
    out = []
    for a in agents or []:
        blob = json.dumps(a, ensure_ascii=False)
        if GROK_RX.search(blob):
            ad = address_of(a)
            if ad and ad not in out:
                out.append(ad)
    return out


def send_one(to, text):
    t0 = time.time()
    rc, out, err = rn(["send", to, text], timeout=60)
    return rc == 0, round(time.time() - t0, 2), (out or err).strip()[:300]


# ───────── 心臓の1回 ─────────

def tick(force=False):
    os.makedirs(D, exist_ok=True)
    st = load(STATE, {})
    if not force and time.time() - st.get("last", 0) < GATE_SEC:
        return
    st["last"] = time.time()
    save(STATE, st)
    jotai = {"at": now_iso(), "cli": bool(reason_exe()), "network": None, "grok": [], "machi": 0, "okutta_24h": 0,
             "uketori_24h": 0, "serve": None, "nyuukou": MCP_URL, "docs": DOCS}
    machi = [r for r in jsonl(MACHI) if time.time() - r.get("t", time.time()) < KEEP_SEC]
    jotai["machi"] = len(machi)
    if not jotai["cli"]:
        jotai["network"] = "CLI未導入（--setup 待ち）"
        _matome(jotai)
        return
    try:
        _mado(jotai)
    except Exception as e:
        log("窓口の手入れができない: %r" % (e,))
    # サインインが終わるまでは network を叩かない（叩くたびにサインインの窓が開く恐れ・2026-10-25 who が40秒固まった実測）
    try:
        _ps = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        _ps = ""
    if "network --no-browser" in _ps or "grok_tsuushin/install.sh" in _ps or "network __finish" in _ps:
        jotai["network"] = "サインイン待ち（setup が走っている）"
        write_jsonl(MACHI, machi)
        _signin_tsuuchi(st)
        _matome(jotai)
        return
    if not st.get("signed_in") and not signin_ok():
        jotai["network"] = "未サインイン"
        write_jsonl(MACHI, machi)
        _signin_tsuuchi(st)
        _matome(jotai)
        return
    st["signed_in"] = True
    save(STATE, st)
    # ネットワークに居るか・Grok は居るか
    try:
        agents = who()
        jotai["network"] = "ok"
        jotai["grok"] = grok_atesaki(agents)
        jotai["agents"] = len(agents)
    except Exception as e:
        msg = str(e)
        jotai["network"] = "未サインイン／オフライン: " + msg[:160]
        agents = None
    if agents is not None:
        _serve_mamoru(jotai, st)
        if jotai["grok"]:
            keep = []
            for rec in machi:
                text = bunmen(rec)
                okk = []
                for to in jotai["grok"]:
                    try:
                        ok, sec, res = send_one(to, text)
                    except Exception as e:
                        ok, sec, res = False, 0, repr(e)[:200]
                    okk.append({"to": to, "ok": ok, "sec": sec, "res": res})
                if any(x["ok"] for x in okk):
                    rec["okutta_at"] = now_iso()
                    rec["okureta_byou"] = round(time.time() - rec.get("t", time.time()), 1)
                    rec["ate"] = okk
                    append_jsonl(OKUTTA, rec)
                    log("送った %s → %s（積んでから%s秒）" % (rec.get("title", "")[:40], ",".join(x["to"] for x in okk if x["ok"]), rec["okureta_byou"]))
                else:
                    rec["tries"] = rec.get("tries", 0) + 1
                    rec["last_err"] = okk[-1]["res"] if okk else ""
                    keep.append(rec)
            machi = keep
            write_jsonl(MACHI, machi)
        else:
            if machi:
                outbox("grok_tsuushin", "Grokボットが Reason Network にまだ居ません",
                       "工場のMacはネットワークに入りました。Grokボットに MCP %s を足してもらう依頼を共有メモに出してあります（待ち %d 件はGrokが入った瞬間に送ります）。" % (MCP_URL, len(machi)),
                       key="grok_inai")
        # 受ける
        try:
            _uketoru(jotai)
        except Exception as e:
            log("inbox が読めない: %r" % (e,))
    else:
        write_jsonl(MACHI, machi)
        _signin_tsuuchi(st)
    jotai["machi"] = len(machi)
    _matome(jotai)


def _uketoru(jotai):
    rc, out, err = rn(["inbox", "--json"], timeout=40)
    if rc != 0:
        rc, out, err = rn(["inbox"], timeout=40)
    out = (out or "").strip()
    if rc != 0 or not out or re.search(r"(?i)no (new )?messages|empty|0 messages", out):
        return
    try:
        msgs = json.loads(out)
        if isinstance(msgs, dict):
            msgs = msgs.get("messages") or msgs.get("items") or [msgs]
    except Exception:
        msgs = [{"text": out}]
    for m in msgs:
        text = m.get("text") or m.get("message") or m.get("body") or json.dumps(m, ensure_ascii=False) if isinstance(m, dict) else str(m)
        frm = (m.get("from") if isinstance(m, dict) else "") or "Reason Network"
        rec = {"at": now_iso(), "from": frm, "text": fusei(text)[:4000]}
        append_jsonl(UKETORI, rec)
        n = None
        try:
            import command_ingest
            status, n = command_ingest.queue_add("【Grokボットから（Reason Network）】%s\n\n%s" % (frm, rec["text"]),
                                                  priority=2, label="Grok通信", origin="grok_reason")
        except Exception as e:
            log("受付に積めない: %r" % (e,))
        append_jsonl(OUTBOX, {"ts": now_iso(), "n": "grok-tsuushin", "type": "grok_kara",
                              "title": "Grokボットから届きました（%s）" % frm, "message": rec["text"][:300] + ("（受付 %s 番）" % n if n else "")})
        log("受けた %s %s" % (frm, rec["text"][:60]))
    rows = jsonl(UKETORI)
    if len(rows) > 600:
        write_jsonl(UKETORI, rows, keep=500)


def _mado(jotai):
    """serve claude の作業場を整え、uketsuke/ に書かれた頼みを工場の発車待ちへ積む。"""
    os.makedirs(os.path.join(MADO, "uketsuke", "done"), exist_ok=True)
    os.makedirs(os.path.join(MADO, "yomu"), exist_ok=True)
    cm = os.path.join(MADO, "CLAUDE.md")
    if not os.path.exists(cm) or open(cm, encoding="utf-8").read() != MADO_CLAUDE:
        open(cm, "w", encoding="utf-8").write(MADO_CLAUDE)
    for src, dst in MADO_YOMU:
        sp = os.path.join(REPO, src)
        if os.path.exists(sp):
            shutil.copyfile(sp, os.path.join(MADO, "yomu", dst))
    ud = os.path.join(MADO, "uketsuke")
    n_ok = 0
    for fn in sorted(os.listdir(ud)):
        fp = os.path.join(ud, fn)
        if not fn.endswith(".md") or not os.path.isfile(fp):
            continue
        text = fusei(open(fp, encoding="utf-8", errors="ignore").read())[:4000]
        n = None
        try:
            import command_ingest
            status, n = command_ingest.queue_add("【Reason Network の窓口から（Grokボット等）】\n%s" % text,
                                                  priority=2, label="Grok通信", origin="grok_reason")
        except Exception as e:
            log("窓口の頼みを受付に積めない: %r" % (e,))
            continue
        append_jsonl(UKETORI, {"at": now_iso(), "from": "madoguchi", "text": text[:1000], "n": n})
        append_jsonl(OUTBOX, {"ts": now_iso(), "n": "grok-tsuushin", "type": "grok_kara",
                              "title": "Grokボットから頼みが届きました（窓口）", "message": text[:300] + ("（受付 %s 番）" % n if n else "")})
        os.replace(fp, os.path.join(ud, "done", fn))
        n_ok += 1
    for fn in os.listdir(os.path.join(ud, "done")):
        fp = os.path.join(ud, "done", fn)
        if time.time() - os.path.getmtime(fp) > 30 * 86400:
            os.remove(fp)
    jotai["madoguchi_uketa"] = n_ok


def _serve_mamoru(jotai, st):
    """Grok からの質問に数秒で答える Claude の常駐（作業場は madoguchi・--full-access なし＝コマンドは打てない）。落ちていたら起こす。"""
    try:
        ps = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        ps = ""
    alive = "network serve claude" in ps
    jotai["serve"] = "動いている" if alive else "止まっている"
    if alive:
        return
    if time.time() - st.get("serve_kidou", 0) < 600:
        return
    st["serve_kidou"] = time.time()
    save(STATE, st)
    exe = reason_exe()
    subprocess.Popen(["python3", os.path.join(HERE, "1144_hanareru.py"), SERVE_OUT, exe, "network", "serve", "claude",
                      "--cwd", MADO, "--name", "tamago-claude"], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("serve claude を起こした（--full-access なし）")


def _signin_tsuuchi(st):
    """未サインイン：setup.out にリンクがあれば Dispatch へ1行（24時間に1回）。無ければ setup を走らせ直す。"""
    link = signin_link()
    if link:
        outbox("login_hitsuyou", "Reason Network のサインイン（初回だけ・1回）",
               "Grokボットにリアルタイムで届ける入口です。このリンクを開いて Google でサインイン→ネットワークを作る：%s （あとは工場が自動で続けます）" % link,
               key="signin")
    elif time.time() - st.get("setup_at", 0) > 1800:
        # サインインの待ち（network __finish）が終わった後：もう一度 --no-browser で聞く。
        # サインイン済みなら招待の行が出る（signin_ok）、まだなら新しいリンクが出る。ブラウザは開かない。
        setup(quiet=True)


def signin_ok():
    """setup.out にネットワークの招待の行（Join the Reason Network: …/network/join/）が出た＝サインインが済んだ。"""
    try:
        s = open(SETUP_OUT, encoding="utf-8", errors="ignore").read()
    except Exception:
        return False
    return "/network/join/" in s


def signin_link():
    try:
        s = open(SETUP_OUT, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    ls = re.findall(r"https://[^\s'\"<>]*reasonmachines\.com[^\s'\"<>]*", s)
    ls = [l for l in ls if "install.sh" not in l and "/docs" not in l and "/network/join/" not in l]
    return ls[-1] if ls else ""


def _matome(jotai):
    rows = jsonl(OKUTTA)
    day = time.time() - 86400
    rec24 = [r for r in rows if _ts(r.get("okutta_at")) > day]
    jotai["okutta_24h"] = len(rec24)
    if rec24:
        jotai["okureta_byou_saikin"] = rec24[-1].get("okureta_byou")
    jotai["uketori_24h"] = len([r for r in jsonl(UKETORI) if _ts(r.get("at")) > day])
    jotai["signin_link"] = bool(signin_link())
    save(PUB, jotai)
    if len(rows) > 600:
        write_jsonl(OKUTTA, rows, keep=500)


def _ts(s):
    try:
        return time.mktime(time.strptime((s or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0


# ───────── 初回の導入 ─────────

# 2026-10-25 中身を検めた結果：network の道は CLI だけ入れる（desktop_install=false・cli_only）。sudo は説明文にしか出ない。
KIKEN = re.compile(r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)|osascript|tccutil|security\s+(find|dump)-|\.ssh/id_|\bsudo\s+(rm|chmod|chown)\b", re.I)


def setup(quiet=False):
    """公式 install.sh を落として中身を検め、問題なければ --no-browser で入れる（切り離して走らせる）。"""
    os.makedirs(D, exist_ok=True)
    st = load(STATE, {})
    st["setup_at"] = time.time()
    save(STATE, st)
    sh = os.path.join(D, "install.sh")
    p = subprocess.run(["curl", "-fsSL", "-m", "40", INSTALL_URL, "-o", sh], capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(sh):
        log("install.sh が取れない: %s" % p.stderr[:200])
        return 1
    body = open(sh, encoding="utf-8", errors="ignore").read()
    hit = KIKEN.findall(body)
    if hit:
        log("install.sh に危ない行があるので入れない: %r" % (hit[:3],))
        outbox("grok_tsuushin", "Reason の install.sh を止めました", "危ない行（%r）があったので入れていません。" % (hit[:3],), key="kiken")
        return 2
    exe = reason_exe()
    if exe:
        cmd = [exe, "network", "--no-browser"]
    else:
        cmd = ["bash", sh, "--no-modify-path", "network", "--no-browser"]
    subprocess.Popen(["python3", os.path.join(HERE, "1144_hanareru.py"), SETUP_OUT] + cmd, env=ENV,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("setup を切り離して走らせた: %s" % " ".join(cmd[:3]))
    if not quiet:
        print("setup を走らせた。出力：%s" % SETUP_OUT)
    return 0  # install.sh は走り終わるまで要るので消さない（次の setup で上書き・status/ の中＝公開しない）


# ───────── 逆テスト ─────────

def self_test():
    ok = True
    a = [{"person": "tamago", "agent": "grok-bot", "session": "sns"}, {"address": "tamago/claude"},
         {"person": "tamago", "client": "Grok", "name": "jidouka"}]
    g = grok_atesaki(a)
    ok &= g == ["tamago/sns", "tamago/jidouka"] or len(g) == 2
    ok &= "tamago/claude" not in g
    t = bunmen({"title": "テスト", "body": "鍵 ghp_" + "a" * 30, "url": "https://github.com/x/y/issues/1"})
    ok &= "［鍵は伏せた］" in t and "正本：https://github.com/x/y/issues/1" in t
    ok &= bool(KIKEN.search("sudo rm -rf /")) and not KIKEN.search("mkdir -p ~/.reason/bin && chmod +x reason") and not KIKEN.search("with passwordless sudo. If")
    ok &= _ts("2026-10-25T10:00:00+0900") > 0
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?")
    ap.add_argument("--title", default="")
    ap.add_argument("--body", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--tick", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--jotai", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if a.setup:
        return setup()
    if a.tick:
        tick(force=a.force)
        return 0
    if a.jotai:
        print(json.dumps(load(PUB, {}), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "okuru":
        print(json.dumps(okuru(a.title, a.body, a.url), ensure_ascii=False))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
