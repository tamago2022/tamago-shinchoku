#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会話の自動共有（kaiwa_kyouyuu）— 2026-11-02 たまごさん指示。

たまごさん：「俺が今話している内容を、Claude Code も Grok もチャッピー（ChatGPT）も全部聞いとけよ。
  いちいちドライブやチャットを探してコピペして貼るのがもう本当に嫌だ」＝水汲みをゼロにする。

■ 何をするか（Mac の心臓 top_status の相乗り・60秒ごとに起こされ、中で2分おきに間引く＝5分以内に載る）
  ① 読む（差分だけ・前回の続きのバイトから）：
     ・Dispatch     ~/Library/Application Support/Claude/local-agent-mode-sessions/*/*/agent/*/audit.jsonl
                    （たまごさんの発言＝人の入力／Dispatch の返事＝SendUserMessage）
     ・Cowork の子   同じ場所の <8桁>/audit.jsonl（題名は local_<8桁>-*.json の title。Dispatchの指示と子の返事）
     ・Claude Code  ~/.claude/projects/*/*.jsonl（人が打った会話＝entrypoint cli／工場の claude -p）
     ・ほかのAI     joy-relief-station の Issue コメント（工場の印の無いもの＝Grok Bot・ChatGPT Codex など）
                    ＋ Reason Network の受け取り（status/grok_tsuushin/uketori.jsonl・Muse など）
     道具の出力・道具の呼び出しは載せない（会話だけ）。
  ② 伏せ字：メール・鍵（sk-/ghp_/AIza/xox/JWT/長い乱数）・パスワード/暗証番号の値・電話・カード番号・郵便番号。
  ③ 書く（非公開の tamago2022/tamago-dispatch-log。公開だったら何も書かずに止めて Dispatch へ1行）：
     kaiwa/README.md（読み方）・kaiwa/ima.md（最新300件）・kaiwa/kyou.md（要約1枚：今日の決まり・依頼・進行中）
     ・kaiwa/log/<日付>/<時>.md（1時間ごとの全部）。
  ④ Grok Bot に見せる：Grok Bot が3時間おきに読む joy-relief-station Issue #1040（全体像）に
     「会話の自動共有」の常設コメントを1つだけ持ち、要約1枚が変わるたびに同じコメントを書き換える（通知を増やさない）。
     Grok からの「受信」返事（KAIWA-PING の合言葉）を見つけたら status/public/kaiwa_kyouyuu.json に証拠として残す。

■ 使い方
  python3 tools/kaiwa_kyouyuu.py --tick       # 心臓から（中で2分に間引く）
  python3 tools/kaiwa_kyouyuu.py --now        # 間引かずに1回
  python3 tools/kaiwa_kyouyuu.py --jotai      # 状態
  python3 tools/kaiwa_kyouyuu.py --self-test  # 逆テスト（伏せ字・読み取り）

■ 軽さ
  常駐なし（心臓の相乗り1本）。読むのは前回からの差分バイトだけ。GitHub への書き込みは変わったファイルだけ（1回あたり最大4本＋コメント1本）。
  会話の控え（~/.tamago/kaiwa_kyouyuu/entries.jsonl）は36時間・4000件で自分で刈る。公開リポ（tamago-shinchoku）には会話を置かない
  （status/public/kaiwa_kyouyuu.json は件数と時刻だけ）。
台帳：tools/jidou_daicho.json の "kaiwa_kyouyuu.py"
"""
import base64
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
CW = os.path.join(HOME, "Library", "Application Support", "Claude", "local-agent-mode-sessions")
CC = os.path.join(HOME, ".claude", "projects")
SD = os.path.join(HOME, ".tamago", "kaiwa_kyouyuu")
STATE = os.path.join(SD, "state.json")
ENTRIES = os.path.join(SD, "entries.jsonl")
LOG = os.path.join(SD, "log")
PUB = os.path.join(REPO, "status", "public", "kaiwa_kyouyuu.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
UKETORI = os.path.join(REPO, "status", "grok_tsuushin", "uketori.jsonl")

LOG_REPO = "tamago2022/tamago-dispatch-log"
JRS = "tamago2022/joy-relief-station"
ZENTAI = 1040
DIRN = "kaiwa"
MARK = "<!-- tamago-factory -->"
KMARK = "<!-- kaiwa-kyouyuu -->"
GATE_SEC = 110
KEEP_SEC = 36 * 3600
KEEP_MAX = 4000
IMA_N = 300
ACTIVE_SEC = 6 * 3600
FIRST_BACK = {"dispatch": 8_000_000, "cowork": 1_500_000, "cc": 1_500_000}
JST = timezone(timedelta(hours=9))

PATHS = [os.path.join(HOME, p) for p in (".local/bin", "bin")] + ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))
GH = shutil.which("gh", path=ENV["PATH"]) or "gh"


# ───────── 伏せ字 ─────────
_RED = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "［メール伏せ字］"),
    (re.compile(r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{12,}"), "［鍵伏せ字］"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"), "［鍵伏せ字］"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "［鍵伏せ字］"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "［鍵伏せ字］"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}(?:\.[A-Za-z0-9_\-]+)?"), "［鍵伏せ字］"),
    (re.compile(r"(?i)\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "［鍵伏せ字］"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "［秘密鍵伏せ字］"),
    (re.compile(r"(?i)((?:password|passwd|pass|pwd|passcode|pin|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret"
                r"|パスワード|暗証番号|合言葉|パスコード|秘密鍵|トークン)\s*[:：=＝は]\s*)([^\s、。,，）)」』]{3,})"), r"\1［伏せ字］"),
    (re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"), "［番号伏せ字］"),
    (re.compile(r"(?<![\d.])0\d{1,4}-\d{1,4}-\d{3,4}(?![\d.])"), "［電話伏せ字］"),
    (re.compile(r"(?<![\d.])0[789]0\d{8}(?![\d.])"), "［電話伏せ字］"),
    (re.compile(r"\+81[ -]?\d{1,4}[ -]?\d{1,4}[ -]?\d{3,4}"), "［電話伏せ字］"),
    (re.compile(r"〒\s?\d{3}-?\d{4}"), "〒［伏せ字］"),
]
_LONG = re.compile(r"[A-Za-z0-9+/_\-]{40,}={0,2}")


def fuseji(t):
    if not t:
        return ""
    for p, r in _RED:
        t = p.sub(r, t)
    # 長い乱数（鍵らしいもの）。git のハッシュ（16進のみ）・URLの道は残す
    def _l(m):
        s = m.group(0)
        if re.fullmatch(r"[0-9a-f]{40,64}", s):
            return s
        if "/" in s and not re.search(r"[A-Z].*[0-9]|[0-9].*[A-Z]", s.replace("/", "")):
            return s
        if re.fullmatch(r"[A-Za-z_\-/]+", s):
            return s
        return "［鍵伏せ字］"
    return _LONG.sub(_l, t)


# ───────── 小物 ─────────
def now():
    return time.time()


def jst(ts):
    return datetime.fromtimestamp(ts, JST)


def parse_ts(s):
    if not s:
        return None
    try:
        if isinstance(s, (int, float)):
            return float(s) / (1000 if s > 1e11 else 1)
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", str(s).replace("Z", "+00:00"))
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def log(msg):
    try:
        os.makedirs(SD, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%F %T ") + msg + "\n")
        if os.path.getsize(LOG) > 300_000:
            lines = open(LOG, encoding="utf-8").read().splitlines()[-1500:]
            open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    except Exception:
        pass


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    os.makedirs(SD, exist_ok=True)
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def outbox(text, kind="kaiwa_kyouyuu"):
    try:
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S+0900"), "type": kind, "text": text},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


_TAGS = re.compile(r"<(system-reminder|scheduled-task|command-[a-z-]+|local-command-[a-z-]+|ide_[a-z_]+|user-prompt-submit-hook)\b[^>]*>[\s\S]*?</\1>", re.I)


_TSUUCHI = re.compile(r'^Task "|read_transcript|^Background (?:task|agent)|^\[(?:SYSTEM|Scheduled)|^This session is being continued', re.M)


def clean_human(t):
    t = _TAGS.sub("", t or "")
    t = re.sub(r"<(system-reminder|scheduled-task)[^>]*>[\s\S]*$", "", t)  # 閉じていない
    return t.strip()


def cut(t, n):
    t = (t or "").strip()
    return t if len(t) <= n else t[:n] + "…（略）"


# ───────── 読む ─────────
def sources():
    """(path, kind, sid, label, stype)"""
    out = []
    t0 = now()
    for p in glob.glob(os.path.join(CW, "*", "*", "agent", "*", "audit.jsonl")):
        out.append((p, "dispatch", "dispatch", "Dispatch", "dispatch"))
    titles = {}
    for p in glob.glob(os.path.join(CW, "*", "*", "*", "audit.jsonl")):
        try:
            if t0 - os.path.getmtime(p) > ACTIVE_SEC:
                continue
        except OSError:
            continue
        d = os.path.dirname(p)
        name = os.path.basename(d)
        if name == "agent":
            continue
        par = os.path.dirname(d)
        if par not in titles:
            titles[par] = {}
        meta = titles[par].get(name)
        if meta is None:
            meta = ("", "")
            for j in glob.glob(os.path.join(par, "local_%s-*.json" % name))[:1]:
                try:
                    jd = json.load(open(j, encoding="utf-8"))
                    meta = (jd.get("title") or "", jd.get("sessionType") or "")
                except Exception:
                    pass
            titles[par][name] = meta
        out.append((p, "cowork", name, meta[0] or name, meta[1]))
    for p in glob.glob(os.path.join(CC, "*", "*.jsonl")):
        try:
            if t0 - os.path.getmtime(p) > ACTIVE_SEC:
                continue
        except OSError:
            continue
        proj = os.path.basename(os.path.dirname(p))
        proj = re.sub(r"^-Users-mac-", "", proj)
        out.append((p, "cc", os.path.basename(p)[:8], proj, "cc"))
    return out


def read_new(path, off, kind):
    """前回のバイト位置から、最後の改行までを読む。初めての時は後ろから少しだけ。"""
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], off
    first = off is None
    if first:
        off = max(0, size - FIRST_BACK.get(kind, 1_000_000))
    if size < off:  # 作り直された
        off = 0
    if size == off:
        return [], off
    with open(path, "rb") as f:
        f.seek(off)
        data = f.read(min(size - off, 30_000_000))
    last_nl = data.rfind(b"\n")
    if last_nl < 0:
        return [], off
    chunk = data[: last_nl + 1]
    lines = chunk.decode("utf-8", "replace").splitlines()
    if first and off > 0 and lines:
        lines = lines[1:]  # 途中から読んだ1行目は捨てる
    return lines, off + last_nl + 1


def _texts(content):
    if isinstance(content, str):
        return [content]
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text") or "")
    return out


def _has_tool_result(content):
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def parse_line(line, kind, label, stype):
    """1行 → 0個以上の (ts, who, text)"""
    try:
        d = json.loads(line)
    except Exception:
        return []
    typ = d.get("type")
    if typ not in ("user", "assistant"):
        return []
    if d.get("isMeta") or d.get("isSidechain") or d.get("parent_tool_use_id"):
        return []
    ts = parse_ts(d.get("timestamp")) or now()
    msg = d.get("message") or {}
    content = msg.get("content")
    out = []
    if typ == "user":
        if _has_tool_result(content):
            return []
        t = clean_human("\n".join(_texts(content)))
        if not t or t.startswith("<") or t.startswith("Caveat:") or t.startswith("[Request interrupted"):
            return []
        if _TSUUCHI.search(t[:300]):  # Dispatch に届く自動の知らせ（子の終了など）は人の発言ではない
            return []
        if kind == "dispatch":
            who = "たまごさん"
        elif kind == "cowork":
            who = "定期タスク→Cowork" if stype == "scheduled" else ("Dispatch→子" if stype == "dispatch_child" else "たまごさん（Cowork）")
        else:
            who = "たまごさん（Claude Code）" if d.get("entrypoint") == "cli" else "工場→Claude Code"
        out.append((ts, who, cut(t, 4000 if who.startswith("たまごさん") else 1200)))
    else:
        if not isinstance(content, list):
            return []
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                nm = b.get("name") or ""
                if re.search(r"send_?user_?message", nm, re.I):
                    m = (b.get("input") or {}).get("message") or ""
                    if m.strip():
                        who = "Dispatch→たまごさん" if kind == "dispatch" else "子→たまごさん"
                        out.append((ts, who, cut(m, 3000)))
            elif b.get("type") == "text" and kind != "dispatch":
                t = (b.get("text") or "").strip()
                if t:
                    who = "Claude（Cowork子）" if kind == "cowork" else "Claude Code"
                    out.append((ts, who, cut(t, 1500 if kind == "cowork" else 700)))
    return out


def gh(*a, inp=None, timeout=40):
    return subprocess.run([GH, *a], input=inp, capture_output=True, text=True, timeout=timeout, env=ENV)


def from_github(st):
    """joy-relief-station の Issue コメントのうち、工場の印が無いもの（Grok Bot・Codex・人）"""
    since = st.get("gh_since") or datetime.fromtimestamp(now() - 3 * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = gh("api", "repos/%s/issues/comments?since=%s&per_page=100&sort=updated&direction=asc" % (JRS, since))
    if r.returncode != 0:
        log("github comments 失敗 " + (r.stderr or "")[:200])
        return []
    try:
        arr = json.loads(r.stdout or "[]")
    except Exception:
        return []
    seen = set(st.get("gh_seen") or [])
    out = []
    newest = since
    for c in arr:
        upd = c.get("updated_at") or c.get("created_at") or since
        newest = max(newest, upd)
        cid = c.get("id")
        body = c.get("body") or ""
        if cid in seen or MARK in body or KMARK in body:
            continue
        seen.add(cid)
        user = ((c.get("user") or {}).get("login") or "")
        if user.endswith("[bot]") and "codex" not in user and "chatgpt" not in user:
            continue
        who = "ChatGPT Codex（GitHub）" if ("codex" in user or "chatgpt" in user) else "Grok Bot ほか（GitHub・%s名義）" % user
        num = (c.get("issue_url") or "").rsplit("/", 1)[-1]
        txt = "%s\n（#%s %s）" % (cut(body, 2500), num, c.get("html_url") or "")
        out.append((parse_ts(c.get("created_at")) or now(), who, txt, "github", "issue#%s" % num))
        m = re.search(r"KAIWA-PING-\d{8}-\d{4}", body)
        if m and m.group(0) == st.get("ping"):
            st["grok_yonda"] = {"at": jst(now()).strftime("%F %T JST"), "url": c.get("html_url"), "honbun": cut(body, 400)}
    st["gh_since"] = newest
    st["gh_seen"] = sorted(seen)[-500:]
    return out


def from_reason(st):
    if not os.path.exists(UKETORI):
        return []
    off = st.get("reason_off")
    if off is None:
        off = max(0, os.path.getsize(UKETORI) - 20000)
    lines, off2 = read_new(UKETORI, off, "reason")
    st["reason_off"] = off2
    out = []
    for l in lines:
        try:
            d = json.loads(l)
        except Exception:
            continue
        out.append((parse_ts(d.get("at")) or now(), "Reason Network（%s）" % (d.get("from") or "?"),
                    cut(d.get("text") or "", 2000), "reason", "reason"))
    return out


def collect(st):
    offs = st.setdefault("off", {})
    new = []
    alive = set()
    for path, kind, sid, label, stype in sources():
        alive.add(path)
        lines, off2 = read_new(path, offs.get(path), kind)
        offs[path] = off2
        for l in lines:
            for ts, who, text in parse_line(l, kind, label, stype):
                new.append((ts, who, text, kind, label))
    for p in list(offs):
        if p not in alive and not os.path.exists(p):
            offs.pop(p, None)
    # 6時間触られていない子・CCの位置は残す（また動いたら続きから）。ただし数が増えすぎたら古い順に捨てる
    if len(offs) > 3000:
        for p in sorted(offs, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0)[:-2000]:
            offs.pop(p, None)
    return new


# ───────── 控え ─────────
def load_entries():
    out = []
    try:
        for l in open(ENTRIES, encoding="utf-8"):
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return out


def save_entries(es):
    os.makedirs(SD, exist_ok=True)
    tmp = ENTRIES + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in es:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, ENTRIES)


def merge(entries, new):
    keys = {e["k"] for e in entries}
    added = []
    for ts, who, text, kind, label in new:
        text = fuseji(text)
        k = hashlib.sha1(("%s|%s|%s" % (label, who, text)).encode()).hexdigest()[:16]
        # 同じ文が数秒差で2回記録されることがある（Dispatch の人の入力）→1つに
        if k in keys:
            continue
        keys.add(k)
        e = {"ts": round(ts, 3), "who": who, "src": kind, "label": label, "text": text, "k": k}
        entries.append(e)
        added.append(e)
    entries.sort(key=lambda e: e["ts"])
    cutoff = now() - KEEP_SEC
    entries = [e for e in entries if e["ts"] >= cutoff][-KEEP_MAX:]
    return entries, added


# ───────── 書く中身 ─────────
def fmt_entry(e):
    t = jst(e["ts"]).strftime("%m-%d %H:%M")
    where = "" if e["src"] == "dispatch" else "［%s］" % e["label"]
    body = e["text"].replace("\n", "\n> ")
    return "**%s %s** %s\n> %s\n" % (t, e["who"], where, body)


HEAD_NOTE = ("自動生成（tamago-shinchoku/tools/kaiwa_kyouyuu.py・Macの心臓から約2分おき）。鍵・メール・パスワード・電話などは伏せ字。"
             "道具の出力は載せていない。")


def build_ima(entries):
    es = entries[-IMA_N:]
    s = ["# 会話の今（最新%d件・古い→新しい）" % len(es), "",
         "更新：%s　%s" % (jst(now()).strftime("%F %H:%M JST"), HEAD_NOTE), "",
         "要約1枚は [kyou.md](kyou.md)。1時間ごとの全部は log/<日付>/<時>.md。", ""]
    s += [fmt_entry(e) for e in es]
    return "\n".join(s)


def build_hour(entries, day, hour):
    es = [e for e in entries if jst(e["ts"]).strftime("%Y-%m-%d") == day and jst(e["ts"]).hour == hour]
    s = ["# 会話の記録 %s %02d時台（JST）" % (day, hour), "", HEAD_NOTE, ""]
    s += [fmt_entry(e) for e in es]
    return "\n".join(s)


KIMARI = re.compile(r"決め|決定|確定|方針|やめ|にする|でいく|で行く|採用|却下|禁止|必ず|今後|これから|ルール|憲法|OK|ＯＫ|いいね|それで")
IRAI = re.compile(r"して(?:ほしい|ください|くれ|おいて|ね|よ|。|$)|してほしい|お願い|作って|調べて|直して|やって|入れて|消して|出して|まとめて|頼む|進めて|つなげて|見て|教えて")


def sentences(t):
    return [x.strip() for x in re.split(r"(?<=[。！？!?\n])", t) if len(x.strip()) >= 6]


def build_kyou(entries, st):
    today = jst(now()).strftime("%Y-%m-%d")
    td = [e for e in entries if jst(e["ts"]).strftime("%Y-%m-%d") == today]
    tama = [e for e in td if e["who"] == "たまごさん" or e["who"].startswith("たまごさん（")]
    disp = [e for e in td if e["who"] == "Dispatch→たまごさん"]
    others = [e for e in entries if e["src"] in ("github", "reason")][-6:]
    kimari, irai = [], []
    for e in tama + disp:
        for x in sentences(e["text"]):
            if KIMARI.search(x) and not re.search(r"[？?]$|じゃん。?$|かな。?$", x) and len(kimari) < 40:
                kimari.append((e, x))
    for e in tama:
        for x in sentences(e["text"]):
            if IRAI.search(x) and len(irai) < 40:
                irai.append((e, x))
    kimari = sorted(kimari, key=lambda p: p[0]["ts"])[-15:]
    irai = sorted(irai, key=lambda p: p[0]["ts"])[-15:]
    hh = lambda e: jst(e["ts"]).strftime("%H:%M")
    s = ["# 今日の要約1枚 %s" % today, "",
         "更新：%s　%s 機械の抜き出し（キーワード）なので、正確な言葉は下の「たまごさんの発言」と [ima.md](ima.md) を見てください。"
         % (jst(now()).strftime("%H:%M JST"), HEAD_NOTE), ""]
    s += ["## 今日の決まり（たまごさん・Dispatchの返事から）", ""]
    s += ["- %s %s：%s" % (hh(e), "たまご" if e["who"].startswith("たまご") else "Dispatch", cut(x, 200)) for e, x in kimari] or ["- （まだ無し）"]
    s += ["", "## 依頼（たまごさんの言葉から）", ""]
    s += ["- %s：%s" % (hh(e), cut(x, 200)) for e, x in irai] or ["- （まだ無し）"]
    s += ["", "## 進行中（Dispatch の最新の返事）", ""]
    s += ["- %s：%s" % (hh(e), cut(e["text"].replace("\n", " "), 400)) for e in disp[-3:]] or ["- （今日はまだ返事なし）"]
    s += ["", "## ほかのAIから（Grok Bot・Codex・Reason Network）", ""]
    s += ["- %s %s：%s" % (jst(e["ts"]).strftime("%m-%d %H:%M"), e["who"], cut(e["text"].replace("\n", " "), 240)) for e in others] or ["- （無し）"]
    s += ["", "## たまごさんの発言（今日・新しい順・全件）", ""]
    s += ["- %s：%s" % (hh(e), cut(e["text"].replace("\n", " "), 600)) for e in reversed(tama)] or ["- （まだ無し）"]
    s += ["", "進捗表：https://tamago2022.github.io/tamago-shinchoku/ ／ 現在地：genzaichi.md（このリポ）", ""]
    return "\n".join(s)


README = """# kaiwa/ — 会話の自動共有（Claude Code・Grok Bot・ChatGPT・Gemini ほか全AI向け）

たまごさん（2026-11-02）：「俺が今話している内容を、Claude Code も Grok もチャッピーも全部聞いとけよ。
いちいちドライブやチャットを探してコピペして貼るのがもう本当に嫌だ」

- **kyou.md** … 今日の要約1枚（決まり・依頼・進行中・たまごさんの発言全件）。まずこれ。
- **ima.md** … 最新300件の会話（Dispatch＝Coworkの会話／Coworkの子／Claude Code／Grok Bot・Codex のGitHubコメント／Reason Network）。
- **log/<日付>/<時>.md** … 1時間ごとの全部（JST）。

Macの心臓が約2分おきに差分だけ書く（tools/kaiwa_kyouyuu.py）。書く前に、鍵・メール・パスワード・電話・カード番号は伏せ字。道具の出力は載せない。
このリポは非公開。公開になっていたら書き出しは自動で止まる。

## 読む人へ
- Grok Bot：joy-relief-station Issue #1040 の「会話の自動共有」コメント（同じコメントを書き換え続ける）に要約1枚が載る。全部はこのフォルダ。
- ChatGPT：GitHub 連携でこのリポ（tamago2022/tamago-dispatch-log）を選べば kaiwa/kyou.md・ima.md を読める。
- 返事・頼みは joy-relief-station の Issue にコメント（共有メモ #1040 など）。ここに集まり、Dispatch と工場が読む。
"""


def build_comment(kyou, st):
    ping = st.get("ping") or ""
    head = ("%s\n%s\n## 会話の自動共有（このコメントは約2分おきに自動で書き換わります）\n\n"
            "たまごさんと Dispatch・Claude Code・Coworkの子の会話を、5分以内に非公開リポ "
            "[tamago-dispatch-log/kaiwa](https://github.com/%s/tree/main/%s) へ書き出しています"
            "（[kyou.md 要約1枚](https://github.com/%s/blob/main/%s/kyou.md)・[ima.md 最新300件](https://github.com/%s/blob/main/%s/ima.md)）。"
            "コピペの水汲みはもう要りません。\n\n"
            "**Grok Bot さんへ（1回だけのお願い）**：これを読んだら、このIssueに「Grok Bot受信 %s」と、"
            "kaiwa/ima.md の一番最後の発言の時刻を1行で返してください（読めた証拠として工場が自動で記録します）。"
            "Muse など他のAIとのやり取りも、このIssueにコメントすれば自動でここに集まります。\n\n---\n\n"
            % (MARK, KMARK, LOG_REPO, DIRN, LOG_REPO, DIRN, LOG_REPO, DIRN, ping))
    base = "https://github.com/%s/blob/main/%s/" % (LOG_REPO, DIRN)
    body = head + kyou.replace("](ima.md)", "](%sima.md)" % base).replace("](kyou.md)", "](%skyou.md)" % base)
    return body[:60000]


# ───────── GitHub ─────────
def repo_is_private(st):
    if now() - st.get("priv_at", 0) < 3600 and st.get("priv") is True:
        return True
    r = gh("api", "repos/%s" % LOG_REPO, "--jq", ".private")
    ok = r.returncode == 0 and r.stdout.strip() == "true"
    st["priv"] = ok
    st["priv_at"] = now()
    return ok


def put_file(st, path, text, msg):
    shas = st.setdefault("sha", {})
    hs = st.setdefault("hash", {})
    h = hashlib.sha1(text.encode()).hexdigest()
    if hs.get(path) == h:
        return True
    for attempt in range(2):
        sha = shas.get(path)
        if sha is None or attempt == 1:
            r = gh("api", "repos/%s/contents/%s" % (LOG_REPO, path), "--jq", ".sha")
            sha = r.stdout.strip() if r.returncode == 0 else None
        body = {"message": msg, "content": base64.b64encode(text.encode()).decode(), "branch": "main"}
        if sha:
            body["sha"] = sha
        r = gh("api", "-X", "PUT", "repos/%s/contents/%s" % (LOG_REPO, path), "--input", "-", inp=json.dumps(body), timeout=60)
        if r.returncode == 0:
            try:
                shas[path] = json.loads(r.stdout)["content"]["sha"]
            except Exception:
                shas.pop(path, None)
            hs[path] = h
            return True
        shas.pop(path, None)
        err = (r.stderr or r.stdout or "")[:200]
    log("PUT 失敗 %s %s" % (path, err))
    return False


def put_comment(st, body):
    # 時刻の行だけが変わった時は書き換えない（Claude Code のつぶやきだけでは #1040 を揺らさない）
    h = hashlib.sha1(re.sub(r"更新：[^\n]*", "", body).encode()).hexdigest()
    if st.get("comment_hash") == h:
        return True
    cid = st.get("comment_id")
    if cid:
        r = gh("api", "-X", "PATCH", "repos/%s/issues/comments/%s" % (JRS, cid), "--input", "-", inp=json.dumps({"body": body}))
        if r.returncode == 0:
            st["comment_hash"] = h
            return True
        if "Not Found" not in (r.stderr + r.stdout):
            log("コメント書き換え失敗 " + (r.stderr or "")[:200])
            return False
    r = gh("api", "-X", "POST", "repos/%s/issues/%d/comments" % (JRS, ZENTAI), "--input", "-", inp=json.dumps({"body": body}))
    if r.returncode != 0:
        log("コメント作成失敗 " + (r.stderr or "")[:200])
        return False
    try:
        d = json.loads(r.stdout)
        st["comment_id"] = d["id"]
        st["comment_url"] = d.get("html_url")
    except Exception:
        pass
    st["comment_hash"] = h
    return True


def write_pub(st, entries, added, ok):
    try:
        os.makedirs(os.path.dirname(PUB), exist_ok=True)
        last_t = max((e["ts"] for e in entries if e["who"] == "たまごさん"), default=None)
        d = {"kousin": jst(now()).strftime("%F %T JST"), "ok": ok,
             "basho": "https://github.com/%s/tree/main/%s（非公開）" % (LOG_REPO, DIRN),
             "grok_mado": st.get("comment_url"),
             "kankaku": "約2分おき（心臓の相乗り・差分だけ）",
             "kensuu_36h": len(entries), "kondo_tsuika": len(added),
             "tamago_saigo": jst(last_t).strftime("%F %T JST") if last_t else None,
             "ping": st.get("ping"), "grok_yonda": st.get("grok_yonda"),
             "tomatta": st.get("tomatta")}
        json.dump(d, open(PUB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def tick(force=False):
    st = load_state()
    if not force and now() - st.get("last", 0) < GATE_SEC:
        return 0
    st["last"] = now()
    if not st.get("ping"):
        st["ping"] = "KAIWA-PING-" + jst(now()).strftime("%Y%m%d-%H%M")
    entries = load_entries()
    new = collect(st)
    try:
        new += [(a, b, c, d, e) for a, b, c, d, e in from_github(st)]
    except Exception as ex:
        log("github 読み失敗 %r" % ex)
    try:
        new += from_reason(st)
    except Exception as ex:
        log("reason 読み失敗 %r" % ex)
    entries, added = merge(entries, new)
    save_entries(entries)

    if not repo_is_private(st):
        st["tomatta"] = "tamago-dispatch-log が非公開でない（または確かめられない）ので書き出しを止めた"
        if now() - st.get("tomatta_at", 0) > 6 * 3600:
            outbox("会話の自動共有を止めました：tamago-dispatch-log が非公開と確かめられません（公開なら書き出さない決まり）。")
            st["tomatta_at"] = now()
        save_state(st)
        write_pub(st, entries, added, False)
        log("止めた：非公開でない／確かめられない")
        return 1
    st.pop("tomatta", None)

    ok = True
    stamp = jst(now()).strftime("%m-%d %H:%M")
    if not st.get("readme"):
        if put_file(st, DIRN + "/README.md", README, "会話の自動共有：読み方"):
            st["readme"] = 1
    hours = sorted({(jst(e["ts"]).strftime("%Y-%m-%d"), jst(e["ts"]).hour) for e in added})
    if not st.get("backfilled"):
        hours = sorted({(jst(e["ts"]).strftime("%Y-%m-%d"), jst(e["ts"]).hour) for e in entries
                        if e["ts"] >= now() - 24 * 3600})
    for day, hr in hours[-30:]:
        ok &= put_file(st, "%s/log/%s/%02d.md" % (DIRN, day, hr), build_hour(entries, day, hr), "会話 %s %02d時（自動）" % (day, hr))
    st["backfilled"] = 1
    kyou = build_kyou(entries, st)
    if added or not st.get("hash", {}).get(DIRN + "/ima.md"):
        ok &= put_file(st, DIRN + "/ima.md", build_ima(entries), "会話の今 %s（自動）" % stamp)
        ok &= put_file(st, DIRN + "/kyou.md", kyou, "今日の要約 %s（自動）" % stamp)
    if added or not st.get("comment_id"):
        ok &= put_comment(st, build_comment(kyou, st))
    st["last_ok"] = now() if ok else st.get("last_ok")
    save_state(st)
    write_pub(st, entries, added, ok)
    log("tick 追加%d 控え%d ok=%s" % (len(added), len(entries), ok))
    return 0 if ok else 1


# ───────── 逆テスト ─────────
def self_test():
    bad = 0
    cases = [
        ("連絡は eggypop2010@gmail.com まで", "eggypop2010@gmail.com"),
        ("鍵 sk-ant-api03-AbCdEfGhIjKlMnOpQrSt を使う", "sk-ant-api03-AbCdEfGhIjKlMnOpQrSt"),
        ("ghp_ABCDEFGHIJKLMNOPQRSTUVWX12345 です", "ghp_ABCDEFGHIJKLMNOPQRSTUVWX12345"),
        ("パスワード：hunter2xyz で入って", "hunter2xyz"),
        ("password=abc12345", "abc12345"),
        ("電話 090-1234-5678 へ", "090-1234-5678"),
        ("カード 4111 1111 1111 1111", "4111 1111 1111 1111"),
        ("token: Zx9QwErTyUiOp1234567890AbCdEfGhIjKlMnOpQ12", "Zx9QwErTyUiOp1234567890AbCdEfGhIjKlMnOpQ12"),
    ]
    for src, secret in cases:
        out = fuseji(src)
        if secret in out:
            print("NG 伏せ字できていない:", src, "→", out)
            bad += 1
    keep = ["コミット 77906bce17b0123456789abcdef0123456789abcd を見て", "https://github.com/tamago2022/tamago-dispatch-log/tree/main/kaiwa",
            "曲は全部で 1234 曲"]
    for k in keep:
        if fuseji(k) != k:
            print("NG 消しすぎ:", k, "→", fuseji(k))
            bad += 1
    human = json.dumps({"type": "user", "timestamp": "2026-11-02T13:00:00Z",
                        "message": {"role": "user", "content": "<system-reminder>x</system-reminder>これ作って。決めた、これでいく"}})
    tool = json.dumps({"type": "user", "timestamp": "2026-11-02T13:00:00Z",
                       "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": "秘密"}]}})
    send = json.dumps({"type": "assistant", "timestamp": "2026-11-02T13:00:01Z", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "SendUserMessage", "input": {"message": "了解です"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}, {"type": "text", "text": "内部メモ"}]}})
    r1 = parse_line(human, "dispatch", "Dispatch", "dispatch")
    r2 = parse_line(tool, "dispatch", "Dispatch", "dispatch")
    r3 = parse_line(send, "dispatch", "Dispatch", "dispatch")
    r4 = parse_line(send, "cowork", "子", "dispatch_child")
    if not (len(r1) == 1 and r1[0][1] == "たまごさん" and "system-reminder" not in r1[0][2]):
        print("NG 人の発言", r1); bad += 1
    if r2:
        print("NG 道具の出力が載った", r2); bad += 1
    if not (len(r3) == 1 and r3[0][2] == "了解です"):
        print("NG Dispatchの返事", r3); bad += 1
    if not (len(r4) == 2 and any(w == "Claude（Cowork子）" for _, w, _ in r4)):
        print("NG 子の返事", r4); bad += 1
    es, added = merge([], [(r1[0][0], r1[0][1], r1[0][2], "dispatch", "Dispatch"), (r1[0][0] + 5, r1[0][1], r1[0][2], "dispatch", "Dispatch")])
    if len(added) != 1:
        print("NG 二重の発言を1つにできない"); bad += 1
    print("self-test", "OK" if bad == 0 else "NG %d" % bad)
    return 0 if bad == 0 else 1


def jotai():
    st = load_state()
    print(json.dumps({k: st.get(k) for k in ("last", "last_ok", "comment_url", "ping", "grok_yonda", "priv", "tomatta")},
                     ensure_ascii=False, indent=1))
    print("追う会話ファイル:", len(st.get("off", {})))


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--jotai" in a:
        jotai(); sys.exit(0)
    if "--now" in a or "--tick" in a:
        lock = os.path.join(SD, ".lock")
        os.makedirs(SD, exist_ok=True)
        if os.path.exists(lock) and now() - os.path.getmtime(lock) < 600:
            sys.exit(0)
        try:
            open(lock, "w").write(str(os.getpid()))
            sys.exit(tick(force="--now" in a))
        finally:
            try:
                os.remove(lock)
            except OSError:
                pass
    print(__doc__)
