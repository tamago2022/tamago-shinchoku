#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""題名の直し係（daimei_naoshi）：外部から入れたカードの題名を、毎日少しずつ「何の動画か」に直す。

たまごさん（2026-10-14・要旨）:
  「冷やすではなく癒やす」ではサムネを見ても何の動画か分からず、クリックされない。
  すぐでなくてよい。1か月後にばっちりできていれば合格。

■ 決め
  ・判定は tools/daimei_kanmon.py の judge() が正本。ここで基準を発明しない。
  ・1日20件まで（クレジット控えめ）。新しく入ったカードから先に直す（取り込みで差し戻された分が先頭）。
  ・書き手は gaibu_copy_naoshi の口（claude -p → 控えの codex）。型だけ差し替える。
  ・書いた題名ももう一度関所に通す。落ちたら書き戻さず、理由を残す。同じカードで3回落ちたら諦めて人の列へ。
  ・手書きの下書き（status/daimei/tegaki/<stock id>.json {"title":…, "whisper":…}）があればAIを呼ばずに採る。
  ・書き戻しは「いまの題名がまだ前の題名のときだけ」（人が画面で直した後なら上書きしない）。
  ・前の題名・コピーは必ず status/public/daimei_naoshi.json の history に残す。--modoshi <id> で戻せる。
  ・DBへは 2210番と同じ Lovable 公式MCP の query_database（鍵不要・0円）。cover-guide（名カバー）は触らない。

使い方:
  python3 tools/daimei_naoshi.py --daily        # 5分便から。30分に1回だけ動く（1日20件まで）
  python3 tools/daimei_naoshi.py --force        # 今すぐ（1日20件の枠は守る）
  python3 tools/daimei_naoshi.py --only <id>    # その1件だけ（枠の外）
  python3 tools/daimei_naoshi.py --dry          # 書き戻さずに、直す候補だけ出す
  python3 tools/daimei_naoshi.py --modoshi <id> # 前の題名・コピーに戻す
"""
from __future__ import annotations

import importlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import daimei_kanmon as kanmon  # noqa: E402

JST = timezone(timedelta(hours=9))
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "daimei_naoshi.json")
MACHI = os.path.join(ST, "daimei", "machi.jsonl")      # 取り込みの関所で差し戻された分
TEGAKI = os.path.join(ST, "daimei", "tegaki")
GATE = os.path.join(ST, ".daimei_naoshi_last")
FORCE = os.path.join(ST, ".daimei_naoshi_force")
LOCK = os.path.join(ST, ".daimei_naoshi.lock")
LOG = os.path.join(ST, "daimei_naoshi.log")
CAP_PER_DAY = 20
GIVE_UP = 3
DEADLINE_SEC = 15 * 60
HISTORY_KEEP = 2000

PROMPT = """あなたは「ごきげん補給所」の棚に並べるカードの、1行目（題名）と2行目（コピー）を書く編集者です。
カードはサムネと一緒に小さく並びます。見た人が「これは何の動画か」を一目で分かることが最優先です。

【1行目＝題名：何の動画か】
・主題の名詞（料理名・食材・曲名・人・場所・動物など）＋していること。12〜22文字（スマホのカードは23文字目から切れる）。主題の名詞は前半に置く。
・例：「さつまいもで作る、ひんやりビスケットサンド」「白菜と肉を重ねるだけの、花みたいな鍋」
・投稿文の比喩・決め台詞・キャッチ（「AでなくB」など）を題名に使わない。投稿文の言い回しをそのまま写さない。
・絵文字・記号・ハッシュタグ・「！」を使わない。

【2行目＝コピー：気の利いた言い回しはこちら】
・ただの行為が小さな事件に変わる1文（ボンジョビおじさん構文）。25〜50文字。
・読み手への命令・呼びかけ・「！」・「話題」「必見」などの煽りを使わない。題名をそのまま言い直さない。

【絶対】材料に書かれていないことを足さない。材料に無い食材・数字・年号・人名・地名を書いたら失格。

【材料】ここに書いてあることだけが、あなたが知っている全部です。
いまの題名：%(title)s
投稿本文・原題・チャンネル：%(copy)s
出どころ：%(url)s

【出し方】
「題名｜コピー」の形で1行だけ出す（全角の縦棒「｜」で区切る）。前置き・かぎかっこ・説明を付けない。
材料が薄くて何の動画か言えない場合は NO_MATERIAL とだけ出す。"""


def now():
    return datetime.now(JST)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (now().strftime("%F %T"), msg))
    except OSError:
        pass


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def db():
    return importlib.import_module("2210_tanaire").DB()


def lit(s):
    return importlib.import_module("2210_tanaire").lit(s)


def material_of(r):
    """事実の材料：投稿本文（Xの埋め込み）／原題（note）／いまの題名（YouTubeは原題のことが多い）。"""
    parts = []
    post = kanmon.post_text_of(r)
    if post:
        parts.append(re.sub(r"https?://\S+", "", post))
    if r.get("kind") == "youtube" and r.get("title"):
        parts.append("原題：%s" % r["title"])
    return re.sub(r"[ \t]+", " ", " / ".join(p.strip() for p in parts if p.strip()))[:1200]


RE_YEAR = re.compile(r"(1[89]\d\d|20\d\d)")
RE_LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


def fact_ng(text, material):
    m = (material or "").lower()
    for y in RE_YEAR.findall(text or ""):
        if y not in (material or ""):
            return "材料に無い年号「%s」" % y
    for w in RE_LATIN.findall(text or ""):
        if w.lower() not in m:
            return "材料に無い固有名「%s」" % w
    return None


def copy_ng(copy, source):
    """2行目（whisper）が直す対象か。投稿の写し・飾りつき・水道水なら理由を返す。"""
    c = str(copy or "").strip()
    try:
        nippou = importlib.import_module("gaibu_copy_nippou")
        w = nippou.judge_copy(c)
        if w:
            return w
    except Exception:
        if not c:
            return "コピーが空"
    if kanmon.RE_KAZARI.search(c):
        return "コピーに投稿の飾り（絵文字・罫線）が残っている"
    if c.startswith("「") and source:
        nc, ns = kanmon._norm(c), kanmon._norm(source)
        if len(nc) >= 8 and nc[:8] in ns:
            return "コピーが投稿文の写し"
    return None


def ask(r, material, extra=""):
    """書き手に1行「題名｜コピー」を頼む。(title, copy, why)。"""
    naoshi = importlib.import_module("gaibu_copy_naoshi")
    saved = naoshi.PROMPT
    diag = []
    try:
        naoshi.PROMPT = PROMPT
        args = (r.get("title") or "（無い）", (material or "（無い）") + extra, r.get("ref") or "（無い）", diag)
        text, why = naoshi.ask_claude(*args)
        if not text:
            text, why2 = naoshi.ask_fallback(*args)
            why = "%s／控え：%s" % (why, why2) if not text else None
    finally:
        naoshi.PROMPT = saved
    if not text:
        return None, None, why or "書き手が書けなかった"
    text = text.strip().strip("「」")
    if "｜" not in text and "|" in text:
        text = text.replace("|", "｜")
    if "｜" not in text:
        return None, None, "「題名｜コピー」の形で返ってこなかった：%s" % text[:60]
    t, c = [x.strip().strip("「」") for x in text.split("｜", 1)]
    return t, c, None


def fetch_rows(d, only=None):
    where = "kind in ('x','youtube','link') and deleted_at is null"
    if only:
        where += " and id::text = %s" % lit(only)
    return d.q("select id::text as id, kind, ref, title, whisper, note, created_at::text as created_at "
               "from admin_stock where %s order by created_at desc limit 5000" % where) or []


def write_back(d, r, title, copy):
    sets = ["title = %s" % lit(title), "updated_at = now()"]
    if copy is not None:
        sets.append("whisper = %s" % lit(copy))
    rows = d.q("update admin_stock set %s where id::text = %s and title is not distinct from %s returning id::text as id"
               % (", ".join(sets), lit(r["id"]), lit(r.get("title"))))
    return bool(rows)


def run(only=None, dry=False):
    st = load(OUT, {}) or {}
    today = now().strftime("%Y-%m-%d")
    per_day = st.get("perDay") or {}
    done_today = int(per_day.get(today) or 0)
    fails = st.get("fails") or {}
    hist = st.get("history") or []
    res = {"ranAt": now().strftime("%F %T"), "fixed": [], "skips": [], "red": []}

    d = db()
    rows = fetch_rows(d, only)
    machi_ids = [x.get("stockId") for x in _read_jsonl(MACHI)]
    targets = []
    for r in rows:
        why = kanmon.judge(r.get("title"), kanmon.post_text_of(r), r.get("kind"))
        if not why and not only:
            continue
        if not only and fails.get(r["id"], 0) >= GIVE_UP:
            continue
        r["_why"] = why
        targets.append(r)
    # 取り込みで差し戻された分を先頭へ（新しいものから）
    targets.sort(key=lambda r: (r["id"] not in machi_ids, ""), reverse=False)
    res["remaining"] = len(targets)
    room = len(targets) if only else max(0, CAP_PER_DAY - done_today)
    res["room"] = room
    if dry:
        res["candidates"] = [{"id": r["id"], "title": r.get("title"), "why": r["_why"]} for r in targets[:room]]
        return res

    t0 = time.time()
    for r in targets[:room]:
        if time.time() - t0 > DEADLINE_SEC:
            res["skips"].append({"id": r["id"], "why": "持ち時間切れ（次の回で続き）"})
            break
        material = material_of(r)
        hand = load(os.path.join(TEGAKI, r["id"] + ".json"), None)
        if hand:
            new_t, new_c, why = str(hand.get("title") or "").strip(), str(hand.get("whisper") or "").strip() or None, None
            by = hand.get("by") or "手書き"
        else:
            if not material and not r.get("title"):
                res["skips"].append({"id": r["id"], "title": r.get("title"), "why": "材料が無い（投稿本文も原題も無い）"})
                fails[r["id"]] = GIVE_UP
                continue
            new_t, new_c, why = ask(r, material)
            by = "機械"
            if new_t:
                ng = kanmon.judge(new_t, material, r.get("kind")) or ([fact_ng(new_t, material)] if fact_ng(new_t, material) else [])
                if ng:
                    new_t2, new_c2, _ = ask(r, material, "\n（直前の題名案「%s」は %s で不合格。同じ手を使わないこと）"
                                            % (new_t, "・".join(ng)))
                    if new_t2:
                        new_t, new_c = new_t2, new_c2
        if not new_t:
            fails[r["id"]] = fails.get(r["id"], 0) + 1
            res["skips"].append({"id": r["id"], "title": r.get("title"), "why": why})
            log("書けなかった %s：%s（%s）" % (r["id"], (r.get("title") or "")[:30], str(why)[:120]))
            continue
        ng = kanmon.judge(new_t, material, r.get("kind"))
        f = None if hand else fact_ng(new_t, material)
        if ng or f:
            fails[r["id"]] = fails.get(r["id"], 0) + 1
            res["skips"].append({"id": r["id"], "title": r.get("title"), "draft": new_t,
                                 "why": "書いた題名が関所で落ちた：%s" % "・".join(ng + ([f] if f else []))})
            continue
        # 2行目は「いまのコピーが写し・飾り・水道水」のときだけ替える
        put_c = None
        if new_c and copy_ng(r.get("whisper"), kanmon.post_text_of(r)) and not copy_ng(new_c, "") \
                and (hand or not fact_ng(new_c, material)):
            put_c = new_c
        try:
            ok = write_back(d, r, new_t, put_c)
        except Exception as e:  # noqa: BLE001
            res["skips"].append({"id": r["id"], "title": r.get("title"), "why": "書き戻しで転んだ：%s" % str(e)[:120]})
            continue
        if not ok:
            res["skips"].append({"id": r["id"], "title": r.get("title"), "why": "書き戻す前に題名が変わっていた（人の直しを優先）"})
            continue
        ch = {"id": r["id"], "kind": r.get("kind"), "ref": r.get("ref"), "at": now().strftime("%F %T"), "by": by,
              "was": r.get("title"), "now": new_t, "wasCopy": r.get("whisper"),
              "nowCopy": put_c if put_c is not None else r.get("whisper"), "why": r["_why"]}
        hist.insert(0, ch)
        res["fixed"].append(ch)
        if not only:
            done_today += 1
        if hand:
            try:
                os.makedirs(os.path.join(TEGAKI, "done"), exist_ok=True)
                os.replace(os.path.join(TEGAKI, r["id"] + ".json"), os.path.join(TEGAKI, "done", r["id"] + ".json"))
            except OSError:
                pass
        log("直した %s：%s → %s" % (r["id"], (r.get("title") or "")[:30], new_t))

    # 書く直前に読み直して混ぜる（1件だけの手直しが並行して走っても、前後の控えを消さない）
    cur = load(OUT, {}) or {}
    seen = {(h.get("id"), h.get("at")) for h in hist}
    hist = hist + [h for h in (cur.get("history") or []) if (h.get("id"), h.get("at")) not in seen]
    hist.sort(key=lambda h: h.get("at") or "", reverse=True)
    for k, v in (cur.get("fails") or {}).items():
        fails[k] = max(fails.get(k, 0), v)
    per_day[today] = max(done_today, int((cur.get("perDay") or {}).get(today) or 0))
    st.update({"generatedAt": res["ranAt"], "perDay": dict(sorted(per_day.items())[-45:]),
               "fails": fails, "history": hist[:HISTORY_KEEP],
               "fixedTotal": int(st.get("fixedTotal") or 0) + len(res["fixed"]),
               "remaining": max(0, res["remaining"] - len(res["fixed"])),
               "last": {k: res[k] for k in ("ranAt", "fixed", "skips", "red", "room")}})
    if targets[:room] and not res["fixed"]:
        res["red"].append("走ったのに1件も直っていない（理由は skips）")
    save(OUT, st)
    return res


def modoshi(sid):
    st = load(OUT, {}) or {}
    for h in st.get("history") or []:
        if h.get("id") == sid:
            d = db()
            d.q("update admin_stock set title = %s, whisper = %s, updated_at = now() where id::text = %s and title = %s"
                % (lit(h["was"]), lit(h.get("wasCopy")), lit(sid), lit(h["now"])))
            return {"ok": True, "back": h["was"]}
    return {"ok": False, "why": "控えに無い"}


def _read_jsonl(p):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except OSError:
        pass
    return out


def sashimodoshi(stock_id, title, why, source=""):
    """取り込みの関所から呼ぶ口：差し戻した1件を列に積み、次の5分便で直させる。"""
    try:
        os.makedirs(os.path.dirname(MACHI), exist_ok=True)
        with io.open(MACHI, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now().strftime("%F %T"), "stockId": stock_id, "title": title,
                                "why": why}, ensure_ascii=False) + "\n")
        io.open(FORCE, "w").write(now().strftime("%F %T"))
    except OSError:
        pass


def main():
    a = sys.argv[1:]
    if "--modoshi" in a:
        print(json.dumps(modoshi(a[a.index("--modoshi") + 1]), ensure_ascii=False))
        return 0
    only = a[a.index("--only") + 1] if "--only" in a else None
    if "--daily" in a and not only:
        forced = os.path.exists(FORCE)
        if forced:
            try:
                os.remove(FORCE)
            except OSError:
                pass
        else:
            try:
                if time.time() - os.path.getmtime(GATE) < 30 * 60:
                    return 0
            except OSError:
                pass
        io.open(GATE, "w").write(now().strftime("%F %T"))
        # ★5分便（launchd）が終わると子も道連れで消える（実測 2026-10-14 04:54：pid 51237 が何も残さず消えた）。
        #   自分のセッションを持って切り離す（tools/git_souji.py 等と同じ形）。
        try:
            if os.fork() > 0:
                return 0
            os.setsid()
            if os.fork() > 0:
                os._exit(0)
        except OSError:
            pass
    import signal
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(143)))
    if only:
        # 1件だけ（手直し）はロックの外。同じカードの取り違えは write_back の「前の題名のままなら」で防ぐ
        res = run(only=only, dry="--dry" in a)
    else:
        try:
            if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 40 * 60:
                alive = True
                try:
                    os.kill(int(io.open(LOCK).read().strip() or 0), 0)
                except (OSError, ValueError):
                    alive = False      # 握ったまま死んだロックは剥がす
                if alive:
                    print("別の回が走っています（ロック）")
                    return 0
            io.open(LOCK, "w").write(str(os.getpid()))
        except OSError:
            pass
        try:
            res = run(only=only, dry="--dry" in a)
        finally:
            try:
                os.remove(LOCK)
            except OSError:
                pass
    print(json.dumps({k: res.get(k) for k in ("ranAt", "room", "remaining", "fixed", "skips", "red", "candidates")},
                     ensure_ascii=False, indent=1)[:20000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
