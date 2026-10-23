#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【投稿前の2重検品】Bufferに入れるXの文を、①機械 ②書いたのとは別のAI の2回通してから入れる。

たまごさん（2026-10-24）:
  「Bufferに予約するX投稿の文を、機械の検品（同じ締めの型の連続、薄い、前の文がないと意味不明、
   出典のない断定）＋書いたのとは別のAIの点検に通してから予約する。予約済みの秋の投稿にもかける
   （文を直すだけ、予約時刻は変えない）。」

■ どこで効くか（入口は1か所）
  tools/buffer_yoyaku.py の gql() が createPost / editPost を叩く直前に mon_gql() を呼ぶ。
  落ちた文は Buffer に送らず、GraphQL のエラーの形で返す（呼んだ側は「入らなかった」として扱う）。
  buffer_yoyaku.gql を使う係（buffer_yoyaku・buffer_hokyuu・buffer_api_post・秋の yoyaku_aki）は全部ここを通る。
  ★Xへ直接投稿はしない。この道具は Buffer に貼る文を見るだけ。

■ ①機械（0円）
  1. 締めの型の連続 … 本文の最後の一文の型（「AかBか」「Which〜?」「〜なんですよ」「AではなくB」…）が、
     時刻で隣の投稿と同じなら落とす。
  2. 薄い          … 題の行・URL・タグを除いた本文が短すぎる（日本語30字・英語70字未満）か、事実が1つも無い。
  3. 前の文がないと意味不明 … 書き出しが「それ」「この」「そして」「And」「Also」「Another」等、
     または「前の投稿」「上の」「as mentioned」等。
  4. 出典のない断定 … 年・数字・「初」「first」「third single」「written by」「カバー」等の断定があるのに、
     出典（Wikipedia等）が無い・YouTubeだけ・開けない・**本文の数字が出典の中に無い**。
  5. 手直し帳で決まりになったもの（status/tenaoshi/kimari.json の regex）。
  6. AIクローンメーカー（~/.claude/skills/ai-clone-maker）の check_style.py（❌があれば落とす）。
② 別のAI … Gemini → OpenAI → Codex CLI → Claude CLI(sonnet・何も知らない新しい1回) の順。
  ★財布の停止札（status/saifu_teishi.json）がある間は有料APIを叩かず、サブスク内の Codex → Claude だけ。
  鍵・1日の上限・家計簿は tools/gaibu_kenpin.py のものを使い回す。同じ文はもう一度AIに見せない（結果を覚えておく）。
  AIに届かなかった（鍵なし・上限）ときは「通さない」側に倒す＝予約しない。

使い方:
  python3 tools/x_nijuu_kenpin.py --text "本文"                   … 1本だけ見る（機械＋AI）
  python3 tools/x_nijuu_kenpin.py --yoyaku-zumi                    … Bufferに予約済みの投稿を全部見る（読むだけ）
  python3 tools/x_nijuu_kenpin.py --naosu status/x_nijuu/naoshi_XXXX.json … 直した文を2重検品に通してから
                                         editPost で本文だけ差し替える（予約時刻は触らない・前後を照合）
  python3 tools/x_nijuu_kenpin.py --self-test
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "x_nijuu")
KEKKA = os.path.join(D, "kekka.jsonl")          # 文ごとの判定（同じ文はもう一度AIに見せない）
SHUTTEN = os.path.join(D, "shutten.json")       # 曲 → 出典URL（手で足す分）
SRC_CACHE = os.path.join(D, "src_cache")
PUB = os.path.join(REPO, "status", "public", "x_nijuu.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
KIMARI = os.path.join(REPO, "status", "tenaoshi", "kimari.json")
AKI_POSTS = os.path.join(REPO, "status", "aki1019", "posts_repl.json")
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
SKILL = os.path.expanduser("~/.claude/skills/ai-clone-maker")
CLONE = os.path.expanduser("~/jrs-clone/ai-clone")
JST = datetime.timezone(datetime.timedelta(hours=9))

URL_RE = re.compile(r"https?://\S+")
TAG_RE = re.compile(r"(?:^|\s)#\S+")


def _now():
    return datetime.datetime.now(JST).isoformat(timespec="seconds")


def _key(text):
    t = unicodedata.normalize("NFKC", text or "")
    return hashlib.sha256(re.sub(r"\s+", " ", t).strip().encode()).hexdigest()[:16]


def _jp(s):
    return bool(re.search(r"[぀-ヿ一-鿿]", s or ""))


# ---------------------------------------------------------------- 文を分ける
def bunkai(text):
    """題の行（Artist — Title / Artist「Title」）・本文・URL・タグに分ける。"""
    lines = [l.rstrip() for l in (text or "").split("\n")]
    title, body = "", []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if URL_RE.fullmatch(s) or URL_RE.match(s) and len(URL_RE.sub("", s).strip()) < 3:
            continue
        if re.fullmatch(r"(#\S+\s*)+", s):
            continue
        if not title and (re.search(r"\s[—–-]\s", s) or re.search(r"「[^」]+」(（\d{4}）)?$", s)) and len(s) < 80 \
                and not re.search(r"[。.!?！？]$", s):
            title = s
            continue
        body.append(URL_RE.sub("", s).strip())
    b = "\n".join(x for x in body if x)
    return title, b


def bun(body):
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=[.!?])\s+|(?<=[.!?]['\"’”])\s+|\n+", body or "")
    return [p.strip() for p in parts if p and p.strip()]


def shime_kata(body):
    ss = bun(body)
    if not ss:
        return "（本文なし）"
    s = ss[-1]
    if re.search(r"\bor\b[^?]*\?$", s, re.I) or re.search(r"(それとも|か、|派[？?])", s):
        return "AかBか？"
    if re.match(r"(Which|What|Who|Where|When|How|Have|Do|Did|Are|Is)\b", s) and s.endswith("?"):
        return "%s〜？" % s.split()[0]
    if re.search(r"[?？]$", s):
        return "問いかけ"
    if re.search(r"んですよ[。！]?$", s):
        return "〜なんですよ"
    if re.search(r"(ではなく|じゃなく|not .+ but)", s, re.I):
        return "AではなくB"
    if re.search(r"(てください|ましょう|てみて)[。！]?$", s):
        return "呼びかけ"
    return "言い切り"


# ---------------------------------------------------------------- 出典
def _aki_index():
    try:
        rows = json.load(io.open(AKI_POSTS, encoding="utf-8"))
    except Exception:
        rows = []
    try:
        extra = json.load(io.open(SHUTTEN, encoding="utf-8"))
    except Exception:
        extra = {}
    idx = {}
    for r in rows:
        try:
            src = json.loads(r.get("src") or "[]") if isinstance(r.get("src"), str) else (r.get("src") or [])
        except Exception:
            src = []
        idx[r["key"]] = {"artist": r.get("artist", ""), "title": r.get("title", ""), "src": src}
    for k, v in (extra.get("songs") or {}).items():
        idx.setdefault(k, {"artist": v.get("artist", ""), "title": v.get("title", ""), "src": []})
        idx[k]["src"] = v.get("src") or idx[k]["src"]
        idx[k]["artist"] = v.get("artist") or idx[k]["artist"]
        idx[k]["title"] = v.get("title") or idx[k]["title"]
    return idx


def song_key(text, post_id=None):
    m = re.search(r"cover-guide\?artist=([^&\s]+)&song=([^&\s]+)", text or "")
    if m:
        return "%s/%s" % (m.group(1), m.group(2))
    if post_id:
        try:
            for l in io.open(DASHITA, encoding="utf-8"):
                if post_id in l:
                    return json.loads(l).get("song_key")
        except Exception:
            pass
    title, _ = bunkai(text)
    low = unicodedata.normalize("NFKC", title).lower()
    for k, v in _aki_index().items():
        if v["title"] and v["title"].lower() in low and v["artist"].lower()[:4] in low:
            return k
    return None


def src_of(text, post_id=None, src=None):
    if src:
        return list(src)
    k = song_key(text, post_id)
    if not k:
        return []
    return (_aki_index().get(k) or {}).get("src") or []


def _src_text(url):
    """出典の本文（Wikipediaは公式APIの本文）。Mac側でだけ取れる。取れなければ None。"""
    os.makedirs(SRC_CACHE, exist_ok=True)
    cp = os.path.join(SRC_CACHE, hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")
    if os.path.exists(cp):
        return io.open(cp, encoding="utf-8").read()
    m = re.match(r"https://(\w+)\.wikipedia\.org/wiki/(.+)", url)
    if not m:
        return None
    try:
        import urllib.parse
        import wiki_lookup
        t, u, ext = wiki_lookup.wiki(m.group(1), urllib.parse.unquote(m.group(2)).replace("_", " "))
    except Exception:
        return None
    if not ext:
        return None
    io.open(cp, "w", encoding="utf-8").write(ext)
    return ext


DANTEI = re.compile(
    r"\b(1[89]\d\d|20\d\d)\b|\d{4}年|\d+\s*(位|万|枚|回|週|million|weeks?)|"
    r"\b(first|debut|second|third|fourth|fifth|last|only|number one|No\.\s?1|#1|record|"
    r"written by|wrote|produced by|covered|cover|original|Grammy|award)\b|"
    r"初の|初めて|最初|史上|唯一|作詞|作曲|編曲|カバー|原曲|オリジナル|代表曲|受賞|1曲目|\d+作目|本人いわく", re.I)


def shutten_kenpin(text, post_id=None, src=None):
    """戻り値: (ok, 理由)。断定が無ければ見ない。"""
    _, body = bunkai(text)
    hits = sorted(set(m.group(0) for m in DANTEI.finditer(body)))
    if not hits:
        return True, ""
    srcs = [s for s in src_of(text, post_id, src) if s]
    real = [s for s in srcs if "youtube.com" not in s and "youtu.be" not in s]
    if not real:
        return False, "出典のない断定（%s）：出典が%s" % ("・".join(hits[:4]), "YouTubeだけ" if srcs else "無い")
    texts = [t for t in (_src_text(s) for s in real) if t]
    if not texts:
        if any("wikipedia.org" in s for s in real):
            return False, "出典が開けない（%s）" % real[0]
        return True, "出典あり（中身は照合していない：%s）" % real[0]
    allt = unicodedata.normalize("NFKC", "\n".join(texts))
    nai = []
    nb = re.sub(r"'\d0s|\d0年代|\d0s\b", "", unicodedata.normalize("NFKC", body))
    for n in re.findall(r"\d{4}|\d+", nb):
        if len(n) >= 2 and n not in allt:
            nai.append(n)
    if nai:
        return False, "出典に無い数字：%s（出典 %s）" % ("・".join(sorted(set(nai))), "／".join(real))
    return True, "出典と数字が一致（%s）" % "／".join(real)


# ---------------------------------------------------------------- ①機械
MAE_JA = re.compile(r"^(それ|その|この|あの|これ|そして|でも|しかし|だから|さらに|また|しかも|一方|ちなみに|続いて|今回も|こちらも|次は|前回|同じく)")
MAE_EN = re.compile(r"^(And|But|So|Also|Plus|Then|Meanwhile|Again|Another|Next|This one|That one|Same)\b")
MAE_ANY = re.compile(r"(前の投稿|上の投稿|先ほど|さっきの|昨日の投稿|前回の|as mentioned|mentioned above|last post|earlier post|the above)", re.I)


def _kimari():
    try:
        return json.load(io.open(KIMARI, encoding="utf-8")).get("kimari") or []
    except Exception:
        return []


def kikai(text, mae=None, ato=None, post_id=None, src=None):
    """①機械。戻り値: {"ok":bool, "ng":[...], "check":[...]}"""
    ng, check = [], []
    title, body = bunkai(text)
    try:
        import x_kata
        lok, lwhy = x_kata.nagasa_ok(text)
        if not lok:
            ng.append("長すぎる：" + lwhy)
    except Exception:
        pass
    # 2. 薄い
    n = len(re.sub(r"\s", "", body))
    if (_jp(body) and n < 30) or (not _jp(body) and n < 70):
        ng.append("薄い：本文が%d字しかない（題の行・URL・タグを除く）" % n)
    if body and not re.search(r"\d|[A-Z][a-z]+|「|『", body):
        ng.append("薄い：事実（年・名前・作品名）が1つも無い")
    # 3. 前の文がないと意味不明
    ss = bun(body)
    if ss and (MAE_JA.match(ss[0]) or MAE_EN.match(ss[0])):
        ng.append("前の文がないと意味不明：書き出しが「%s」" % ss[0][:20])
    m = MAE_ANY.search(body)
    if m:
        ng.append("前の文がないと意味不明：「%s」" % m.group(0))
    # 1. 締めの型の連続
    k = shime_kata(body)
    for name, other in (("前", mae), ("次", ato)):
        if other:
            if shime_kata(bunkai(other)[1]) == k:
                ng.append("締めの型の連続：%sの投稿と同じ「%s」で締めている" % (name, k))
    # 4. 出典のない断定
    ok, why = shutten_kenpin(text, post_id, src)
    (check if ok else ng).append(why) if why else None
    # 5. 手直し帳で決まりになったもの
    for r in _kimari():
        rx = r.get("regex")
        if rx and re.search(rx, text or "", re.I):
            (ng if r.get("level") == "ng" else check).append("手直し帳の決まり「%s」（%s）" % (r.get("namae"), r.get("id")))
    return {"ok": not ng, "ng": ng, "check": [c for c in check if c], "shime": k}


def clone_check(texts):
    """AIクローンメーカーの check_style.py --batch。戻り値: (ok, 出力の要約)。道具が無ければ (True, 理由)。"""
    cs = os.path.join(SKILL, "scripts", "check_style.py")
    if not os.path.exists(cs):
        return True, "AIクローンメーカーが無い（この機械では見ない）"
    rules = os.path.join(CLONE, "検品の決まり.json")
    if not os.path.exists(rules):
        return True, "AIクローンの作業場が無い（%s）" % CLONE
    work = tempfile.mkdtemp(prefix="x_nijuu_")
    try:
        paths = []
        for i, t in enumerate(texts):
            p = os.path.join(work, "x-%d.md" % (i + 1))
            io.open(p, "w", encoding="utf-8").write("---\nmedia: x\ntitle: 予約%d\nstatus: draft\n---\n\n%s\n" % (i + 1, t))
            paths.append(p)
        cmd = ["python3", cs] + paths + ["--batch", "--rules", rules]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
        ng = [l.strip() for l in out.splitlines() if "❌" in l]
        return r.returncode == 0, "\n".join(ng[:6]) if ng else "❌ゼロ"
    except Exception as e:
        return True, "check_style が走らなかった：%s" % str(e)[:80]
    finally:
        shutil.rmtree(work, ignore_errors=True)     # ★使ったらしまう


# ---------------------------------------------------------------- ②別のAI
AI_SYSTEM = (
    "あなたはX(旧Twitter)の投稿文の点検係です。書いたのは別のAI(Claude)です。"
    "音楽の案内所「ごきげん補給所」の運営者(たまごさん)が、Bufferに予約する前の文を見せます。"
    "次の4点で厳しく点検してください。\n"
    "1. 締めの型が前後の投稿と同じで、続けて読むと飽きる\n"
    "2. 薄い（読んでも『へぇ』が1つも無い・当たり障りのない感想・『名曲です』のような水道水コピー・雰囲気だけのポエム）\n"
    "3. 前の投稿を読んでいないと意味が分からない（それ・この・Also などで始まる、何の曲か分からない）\n"
    "4. 出典で確かめられない断定（年・順位・『初』・作詞作曲・カバー関係）。渡した出典の抜粋と食い違う事実は必ずNG\n"
    "★店主が決めた型（2026-10-20）：題の行＋一言＋事実＋最後に読者への問いかけ＋タグ1〜2個・本文にリンクなし。"
    "問いかけで締めること自体は型なので責めない。『締めの型』は問いの形（AかBか／Which〜／Who〜 など）が前後と同じかで見る。"
    "naoshi_an もこの型（最後は問いかけ）で書く。\n"
    "加えて『運営の決まり』に反していないか。曲名・アルバム名を意訳していないか。\n"
    "必ずJSONで返す：{\"verdict\":\"OK\"か\"NG\",\"reasons\":[\"短い理由\"],\"naoshi_an\":\"NGのときだけ、"
    "同じ形（題の行・URL・ハッシュタグはそのまま）で直した全文。事実は出典にあることだけ\"}"
)


def _ai_prompt(text, mae, ato, src_snips, kimari):
    return (
        "【点検する投稿】\n%s\n\n【前の投稿】\n%s\n\n【次の投稿】\n%s\n\n【出典の抜粋】\n%s\n\n【運営の決まり（手直し帳より）】\n%s\n"
    ) % (text, mae or "(なし)", ato or "(なし)", src_snips or "(出典なし)",
         "\n".join("- " + k.get("namae", "") for k in kimari) or "(なし)")


def _snips(text, srcs):
    out = []
    title, body = bunkai(text)
    words = []
    m = re.search(r"[—–-]\s*(.+)$|「([^」]+)」", title or "")
    if m:
        words.append((m.group(1) or m.group(2)).strip())
    for w in re.findall(r"\d{4}|[A-Z][a-zA-Z']{3,}|[\u4e00-\u9fff\u30a0-\u30ff]{2,}", body):
        if w not in words:
            words.append(w)
    for s in srcs:
        t = _src_text(s)
        if not t:
            continue
        got = []
        for w in words[:14]:
            i = t.find(w)
            if i >= 0:
                piece = t[max(0, i - 150): i + 200].replace("\n", " ")
                if not any(piece[:60] in g for g in got):
                    got.append(piece)
        out.append("%s\n  冒頭：%s\n  %s" % (s, t[:700].replace("\n", " "), "\n  ".join(got[:7])))
    return "\n".join(out)[:6000]


def _call_cli(provider, text_prompt):
    """サブスク内のCLI（追加の従量課金なし）。Codex＝ChatGPTの契約、Claude＝sonnet（書いた側とは別の新しい1回）。"""
    if provider == "Codex":
        b = _cli("codex")
        if not b:
            return None, "codex が無い"
        fd, outp = tempfile.mkstemp(prefix="x_nijuu_codex_", suffix=".txt")
        os.close(fd)
        try:
            r = subprocess.run([b, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                                "--output-last-message", outp, "-"],
                               input=AI_SYSTEM + "\n\n" + text_prompt, capture_output=True, text=True,
                               timeout=240, cwd=tempfile.gettempdir())
            c = io.open(outp, encoding="utf-8").read() if os.path.exists(outp) else ""
            if r.returncode != 0 or not c.strip():
                return None, "codex exit=%s %s" % (r.returncode, ((r.stderr or r.stdout) or "")[-160:])
            return {"model": "codex-cli", "usage": {}, "content": c}, ""
        except Exception as e:
            return None, "codex：%s" % str(e)[:100]
        finally:
            try:
                os.remove(outp)          # ★使ったらしまう
            except OSError:
                pass
    b = _cli("claude")
    if not b:
        return None, "claude が無い"
    try:
        r = subprocess.run([b, "-p", "--safe-mode", "--model", "sonnet", "--output-format", "json",
                            "--system-prompt", AI_SYSTEM], input=text_prompt, capture_output=True, text=True,
                           timeout=240, cwd=tempfile.gettempdir())
        env = json.loads(r.stdout)
        if r.returncode != 0 or env.get("is_error"):
            return None, "claude exit=%s %s" % (r.returncode, str(env.get("result"))[:160])
        return {"model": "claude-cli-sonnet", "usage": env.get("usage") or {}, "content": str(env.get("result") or "")}, ""
    except Exception as e:
        return None, "claude：%s" % str(e)[:100]


def _json_of(c):
    try:
        return json.loads(c)
    except Exception:
        m = re.search(r"\{.*\}", c or "", re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _call(provider, text_prompt):
    import gaibu_kenpin as gk
    import urllib.request
    if provider in ("Codex", "Claude"):
        return _call_cli(provider, text_prompt)
    if provider == "Gemini":
        key = gk._find_env_key(("GEMINI_API_KEY",))
        if not key:
            return None, "Geminiの鍵なし"
        body = {"system_instruction": {"parts": [{"text": AI_SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": text_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}}
        errs = []
        for model in gk.GEMINI_MODEL_CANDIDATES:
            try:
                req = urllib.request.Request(gk.GEMINI_URL_TMPL % (model, key), data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"}, method="POST")
                j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
                c = "".join(p.get("text", "") for p in ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts", []))
                return {"model": model, "usage": j.get("usageMetadata") or {}, "content": c}, ""
            except Exception as e:
                errs.append("%s:%s" % (model, str(e)[:60]))
        return None, " / ".join(errs)
    key = gk._find_env_key(("OPENAI_API_KEY",))
    if not key:
        return None, "OpenAIの鍵なし"
    errs = []
    for model in gk.OPENAI_MODEL_CANDIDATES:
        try:
            body = {"model": model, "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": AI_SYSTEM}, {"role": "user", "content": text_prompt}]}
            req = urllib.request.Request(gk.OPENAI_URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
            j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
            return {"model": model, "usage": j.get("usage") or {},
                    "content": (j.get("choices") or [{}])[0].get("message", {}).get("content", "")}, ""
        except Exception as e:
            errs.append("%s:%s" % (model, str(e)[:60]))
    return None, " / ".join(errs)


def betsu_ai(text, mae=None, ato=None, post_id=None, src=None):
    """②別のAI。戻り値: {"verdict": OK/NG/SKIP, "reasons": [...], "naoshi_an": str, "provider": ...}"""
    try:
        import gaibu_kenpin as gk
        ok_cap, why_cap = gk.check_cost_cap()
    except Exception as e:
        ok_cap, why_cap = False, "検品の道具が読めない：%s" % str(e)[:80]
    # ★財布の停止札（2026-10-15〜）や上限のときは、有料APIは叩かず、サブスク内のCLIだけを使う。
    chain = ("Gemini", "OpenAI", "Codex", "Claude") if ok_cap else ("Codex", "Claude")
    prompt = _ai_prompt(text, mae, ato, _snips(text, src_of(text, post_id, src)), _kimari())
    tried = [] if ok_cap else ["有料API：%s" % why_cap[:60]]
    for prov in chain:
        r, err = _call(prov, prompt)
        if not r:
            tried.append("%s：%s" % (prov, err))
            continue
        try:
            p = _json_of(r["content"])
        except Exception:
            p = {"verdict": "NG", "reasons": ["応答がJSONでない：%s" % r["content"][:120]]}
        v = (p.get("verdict") or "NG").upper()
        v = v if v in ("OK", "NG") else "NG"
        try:
            if prov in ("Codex", "Claude"):
                raise StopIteration      # サブスク内＝家計簿の従量欄には書かない
            gk.record_cost(None, "X投稿の2重検品", prov, r["model"], r["usage"], v, note="x_nijuu_kenpin")
            import kakeibo
            kakeibo.kiroku("X投稿の2重検品", prov.lower(), r["model"], "検品1回", kakutei="推定",
                           moto="tools/x_nijuu_kenpin.py")
        except BaseException:
            pass
        return {"verdict": v, "reasons": p.get("reasons") or [], "naoshi_an": p.get("naoshi_an") or "",
                "provider": prov, "model": r["model"]}
    return {"verdict": "SKIP", "reasons": tried}


# ---------------------------------------------------------------- 2つまとめて
def _oboe(k):
    try:
        for l in io.open(KEKKA, encoding="utf-8"):
            r = json.loads(l)
            if r.get("key") == k and r.get("ai", {}).get("verdict") in ("OK", "NG"):
                return r
    except Exception:
        pass
    return None


def kenpin(text, mae=None, ato=None, post_id=None, src=None, ai=True):
    k = _key(text + "|" + (mae or "") + "|" + (ato or ""))
    m = kikai(text, mae, ato, post_id, src)
    c_ok, c_why = clone_check([x for x in (mae, text, ato) if x])
    if not c_ok:
        m["ng"].append("AIクローンメーカーの検品で❌：%s" % c_why)
        m["ok"] = False
    m["clone"] = c_why
    old = _oboe(k) if ai else None
    a = old["ai"] if old else (betsu_ai(text, mae, ato, post_id, src) if ai else {"verdict": "SKIP", "reasons": ["AIは呼ばない指定"]})
    ok = m["ok"] and a.get("verdict") == "OK"
    row = {"at": _now(), "key": k, "post_id": post_id, "head": (text or "")[:60], "zenbun": text, "kikai": m, "ai": a, "ok": ok}
    if not old:
        os.makedirs(D, exist_ok=True)
        io.open(KEKKA, "a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def mon_gql(query, variables):
    """buffer_yoyaku.gql から呼ぶ門。通らなければ Buffer に送らず返す GraphQL エラーの形、通れば None。"""
    if os.environ.get("X_NIJUU_SKIP") == "1":
        return None
    q = query or ""
    if "createPost" not in q and "editPost" not in q:
        return None
    text = (((variables or {}).get("input") or {}).get("text"))
    if not text:
        return None
    pid = ((variables or {}).get("input") or {}).get("id")
    # 同じ全文が直前（6時間以内）に2つとも通っていれば、もう一度AIに見せない
    try:
        lim = (datetime.datetime.now(JST) - datetime.timedelta(hours=6)).isoformat(timespec="seconds")
        for l in io.open(KEKKA, encoding="utf-8"):
            o = json.loads(l)
            if o.get("ok") and o.get("zenbun") == text and o.get("at", "") >= lim:
                return None
    except Exception:
        pass
    r = kenpin(text, post_id=pid)
    if r["ok"]:
        return None
    why = r["kikai"]["ng"] + (["別のAI(%s)：%s" % (r["ai"].get("provider", "-"), "／".join(r["ai"].get("reasons") or []))]
                               if r["ai"].get("verdict") != "OK" else [])
    try:
        io.open(OUTBOX, "a", encoding="utf-8").write(json.dumps({
            "at": _now(), "type": "x_nijuu_tometa", "from": "x_nijuu_kenpin",
            "text": "X投稿を2重検品で止めた（Bufferに入れていない）：%s ｜ %s" % ((text or "")[:30], "／".join(why)[:200])},
            ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"errors": [{"message": "投稿前の2重検品で止めた：" + "／".join(why)}], "x_nijuu": r}


# ---------------------------------------------------------------- 予約済みを見る・直す
def _buffer():
    import buffer_yoyaku as by
    tok = by.token()
    orgs = ((by.gql(tok, by.Q_ORGS).get("data") or {}).get("account") or {}).get("organizations") or []
    chans = []
    for o in orgs:
        for c in (by.gql(tok, by.Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}).get("channels") or []:
            c["_org"] = o["id"]
            chans.append(c)
    ch = by.pick_channel(chans, "oasisjoyrelief", ["eggypop2014"])

    def yoyaku():
        q = by.gql(tok, by.Q_POSTS, {"orgId": ch["_org"], "channelIds": [ch["id"]]})
        return [e["node"] for e in ((q.get("data") or {}).get("posts") or {}).get("edges") or []]
    return by, tok, ch, yoyaku


def yoyaku_zumi(ai=True):
    by, tok, ch, yoyaku = _buffer()
    posts = sorted(yoyaku(), key=lambda p: p.get("dueAt") or "")
    res = []
    for i, p in enumerate(posts):
        mae = posts[i - 1]["text"] if i > 0 else None
        ato = posts[i + 1]["text"] if i + 1 < len(posts) else None
        r = kenpin(p["text"], mae, ato, post_id=p["id"], ai=ai)
        res.append({"id": p["id"], "dueAt": p["dueAt"], "head": p["text"][:50], "ok": r["ok"],
                    "ng": r["kikai"]["ng"], "check": r["kikai"]["check"], "ai": r["ai"]})
    out = {"at": _now(), "yoyaku": len(posts), "ng": sum(1 for r in res if not r["ok"]), "posts": res}
    os.makedirs(os.path.dirname(PUB), exist_ok=True)
    io.open(PUB, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def naosu(path):
    """naoshi.json = {"naoshi":[{"id":..., "text":新しい全文, "why":...}]}。本文だけ差し替える。"""
    job = json.load(io.open(path, encoding="utf-8"))
    by, tok, ch, yoyaku = _buffer()
    before = {p["id"]: p for p in yoyaku()}
    order = sorted(before.values(), key=lambda p: p.get("dueAt") or "")
    new_text = {n["id"]: n["text"] for n in job["naoshi"]}
    seq = [new_text.get(p["id"], p["text"]) for p in order]
    ids = [p["id"] for p in order]
    log = []
    for n in job["naoshi"]:
        p = before.get(n["id"])
        if not p:
            log.append({"id": n["id"], "kekka": "予約に無い（もう出た・消えた）"}); continue
        i = ids.index(n["id"])
        r = kenpin(n["text"], seq[i - 1] if i > 0 else None, seq[i + 1] if i + 1 < len(seq) else None,
                   post_id=n["id"], src=n.get("src"))
        if not r["ok"]:
            log.append({"id": n["id"], "kekka": "直した文が2重検品を通らない（差し替えない）",
                        "ng": r["kikai"]["ng"], "ai": r["ai"]}); continue
        x = by.gql(tok, by.M_EDIT, {"input": {"id": n["id"], "text": n["text"]}})
        post = ((x.get("data") or {}).get("editPost") or {}).get("post")
        log.append({"id": n["id"], "kekka": "差し替えた" if post else "差し替え失敗",
                    "raw": None if post else json.dumps(x, ensure_ascii=False)[:200], "ai": r["ai"].get("provider")})
    after = {p["id"]: p for p in yoyaku()}
    for l in log:
        a, b = after.get(l["id"]), before.get(l["id"])
        if a and b:
            l["jikoku_onaji"] = a["dueAt"] == b["dueAt"]
            l["honbun_icchi"] = a["text"] == new_text.get(l["id"])
    out = {"at": _now(), "job": os.path.basename(path), "log": log,
           "naotta": sum(1 for l in log if l["kekka"] == "差し替えた" and l.get("honbun_icchi") and l.get("jikoku_onaji"))}
    io.open(os.path.join(D, "naoshi_kekka.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ---------------------------------------------------------------- 逆テスト
def self_test():
    bad = []
    t1 = "Ado — Gira Gira\n\nAlso a great one.\n#Ado"
    r = kikai(t1)
    if not any("前の文" in x for x in r["ng"]):
        bad.append("「Also」始まりを落とせない")
    if not any("薄い" in x for x in r["ng"]):
        bad.append("薄い文を落とせない")
    a = "X — Y\n\nA long enough sentence about the song and the band from London here. Rock Lenny or soul Lenny?"
    b = "P — Q\n\nAnother long enough sentence about a different song and its singer here. Al Green or Eric Benet?"
    r = kikai(b.replace("Another", "One"), mae=a)
    if not any("締めの型の連続" in x for x in r["ng"]):
        bad.append("締めの連続を落とせない")
    ok, why = shutten_kenpin("Z — W\n\nReleased in 1996 as the first single from the album by this singer.", src=["https://www.youtube.com/watch?v=x"])
    if ok:
        bad.append("YouTubeだけの出典で断定を通した")
    ok, why = shutten_kenpin("Z — W\n\nA warm song about a quiet evening by the river, sung softly by a choir.", src=[])
    if not ok:
        bad.append("断定の無い文を出典なしで落とした")
    good = "アデル本人いわく「ダークでブルージーなゴスペル・ディスコ」。\nアルバム『21』の1曲目。"
    if MAE_JA.match(good):
        bad.append("ふつうの書き出しを落とした")
    if mon_gql("query { posts }", {}) is not None:
        bad.append("読むだけの問い合わせを止めた")
    print("SELF-TEST", "PASS" if not bad else "FAIL", bad)
    return 0 if not bad else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--text" in a:
        print(json.dumps(kenpin(a[a.index("--text") + 1]), ensure_ascii=False, indent=1)); return
    if "--yoyaku-zumi" in a:
        o = yoyaku_zumi(ai="--no-ai" not in a)
        print("予約%d本／落ちた%d本" % (o["yoyaku"], o["ng"]))
        for p in o["posts"]:
            print(("OK " if p["ok"] else "NG ") + p["dueAt"] + " " + p["head"].replace("\n", " ")[:40])
            for x in p["ng"]:
                print("   ✗", x)
            if p["ai"].get("verdict") != "OK":
                print("   AI", p["ai"].get("verdict"), "／".join(p["ai"].get("reasons") or [])[:300])
        return
    if "--naosu" in a:
        print(json.dumps(naosu(a[a.index("--naosu") + 1]), ensure_ascii=False, indent=1)); return
    print(__doc__)


if __name__ == "__main__":
    main()
