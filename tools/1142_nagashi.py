#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1142番【流し続ける係】外の口に、仕入れの仕事を1本ずつ絶やさず流す。

━━ なぜ要るか（2026-09-25・たまごさん原文）━━
  「デビンは仕入れ含め止まらず回して」
  「Devinが常に何かを走らせている状態を作る。止まったら自動で次が入る。」

━━ Devinの癖（実測で分かっていること。依頼文に必ず埋める）━━
  ・「指示があるまで待ちます」と書いて止まり finished で死ぬ
    → 依頼文の**先頭**に「返事を書くな。終わりの合図はPRのURLだけ」を置く（後から言っても効かない）
  ・3本同時に投げると30分でACUが尽きて3本とも凍る（2026-09-20 実測）
    → **1本ずつ。**走り切ってから次を投げる
  ・唯一の得意技＝「こちらの前提が正しいか実測で確かめて」（結論を見せずに検証させる）

━━ お金（★勝手に使わない）━━
  Devinは1本 約93円（2026-09-18〜20の15本で $8.85＝1,327円／972番の公式画面差分）。
  財布の栓（tools/yosan.py の devin）が 0円 なら**1本も投げない。**
  そのとき列は止めない：**0円の口（Jules＝GitHub経由・月額の中）へ同じ仕事を回す。**
  → つまり「Devinが動いていない時間」は0にしつつ、無断の課金も0にする。

━━ どこで動くか ━━
  サンドボックス（Cowork/Dispatch）からは api.devin.ai / api.github.com に**回線が出ない**
  （実測：Tunnel connection failed 403）。Macからは出る。
  だから心臓（tools/heartbeat.sh）から1分おきに呼ばれる。列が空なら数ミリ秒で終わる。

━━ 書き出すもの ━━
  status/1142/devin_jissoku.json … Devinの実測（残・走っている本数・課金の状態）
  status/1142/nagashi.json        … 流した本数・返ってきていない本数・弾いた数
  status/gaibu_ai/daicho.jsonl    … 投げた1本ずつ（tools/gaibu_ai.py 経由）
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_DIR = os.path.join(REPO, "status", "1142")
JISSOKU = os.path.join(OUT_DIR, "devin_jissoku.json")
STATE = os.path.join(OUT_DIR, "nagashi.json")
QUEUE = os.path.join(OUT_DIR, "nagashi_queue.json")
LOG = os.path.join(OUT_DIR, "nagashi.log")
ENV_PATH = os.path.join(REPO, ".env")
API = "https://api.devin.ai/v1"

DEVIN_YEN_PER_SESSION = 93.0      # 972番の公式画面差分より（実測）
KIGEN_HOURS = 3                   # 3時間で返ってこなければ赤（daicho.py と同じ）
MAX_PER_DAY = 24                  # 1日に投げる上限（暴走の栓）
MAX_INFLIGHT = 1                  # ★1本ずつ（2026-09-20の事故）

# ★この作法は依頼文の「最初」に置く。後から言っても効かない（devin_1by1.py の実測）。
SAHOU = """★★この仕事の進め方（最初に読んでください）★★
・返事を書かないでください。終わりの合図は、PRのURLか、答えの1行だけです。
・「指示を待ちます」「ご確認ください」と書いてはいけません。依頼主は外出中で、誰も答えられません。
・途中で環境が壊れても、聞かずに自分で直してください。手を5つ試すまで止まらないでください。
・迷ったら、あなたが妥当だと思う方を自分で選んで進めてください。
━━━━━━━━━━━━━━━━━━━━━━━━

"""

# 仕入れの関所（skills: sekisho-artist-song / sekisho-jijitsu-shutten の要点）。
# ★出典URLが無いものは棚に入れない。★名前の一致は証拠にならない。
KANMON = """
【★この仕事の関所（1つでも欠けたら、その曲は出さないでください）】
1. 本人の証拠を1つ以上：公式YouTubeチャンネル（チャンネルIDまで）／VEVO／公式サイト・公式SNSでの案内／
   レーベル公式チャンネルでの本人名義。★**チャンネル名が名前と一致している、は証拠になりません。**
   （akiko の棚にチャンネル名 AKIKO の別人が3曲入った事故がこれです）
2. 断定の事実（◯◯年・オリジナル・原曲・代表曲・カバー・受賞・売上）には**出典URLを必ず付ける。**
   取れないなら、その語を落として書いてください。★推測で埋めない。空欄のままで構いません。
   投稿型（Wikipedia／Discogs／歌詞サイト）は1本だけでは採用しない。独立した2本目と一致したときだけ。
3. 完成の条件（これを満たさないものは1件も出さない）：
   ★再生できる動画が1本以上（動画IDと、実際に埋め込み再生できることを確かめた結果）
   ★サムネイルのURL ★曲名 ★アーティスト名 ★2行のコピー
4. 判定できないものは「出さない」側に倒してください。**無いほうがマシ、間違っているより。**
5. 出せなかったものは、**何が取れなかったのかを1行ずつ**一覧にしてください（何件弾いたかを数字で）。
"""


def _now():
    return datetime.now(JST)


def _iso(dt=None):
    return (dt or _now()).isoformat(timespec="seconds")


def say(msg):
    os.makedirs(OUT_DIR, exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (_now().strftime("%F %T"), msg))


def _read(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------- Devinの実測
def devin_key():
    k = os.environ.get("DEVIN_API_KEY")
    if k:
        return k
    if os.path.exists(ENV_PATH):
        with io.open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("DEVIN_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return None


def call(path, data=None, timeout=25):
    key = devin_key()
    if not key:
        return 0, {"error": "DEVIN_API_KEYが.envにありません"}
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + key)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": repr(e)}


LIVE = ("working", "running", "in_progress", "resumed")


def jissoku():
    """Devinが生きているかを実測する。★取れないものは「取れない」と書く。推測しない。"""
    out = {"at": _iso(), "kuchi": {}, "hashiru": None, "nokori_acu": None,
           "kagi": bool(devin_key())}
    code, d = call("/sessions?limit=100")
    out["kuchi"]["/v1/sessions"] = code
    if code == 200:
        ss = d.get("sessions") or []
        live = [s for s in ss
                if (s.get("status_enum") or s.get("status") or "") in LIVE]
        out["hashiru"] = len(live)
        out["session_sou"] = len(ss)
        out["hashiru_ichiran"] = [{"sid": s.get("session_id"),
                                   "title": (s.get("title") or "")[:60],
                                   "status": s.get("status_enum") or s.get("status")}
                                  for s in live]
    else:
        out["hashiru_torenai_riyuu"] = "HTTP %s %s" % (code, str(d)[:180])

    # 残ACU：公式に口があるなら読む。無ければ「取れない＋どの口が閉じているか」を書く。
    for p in ("/enterprise/consumption", "/usage", "/billing/usage", "/acu"):
        c, r = call(p, timeout=15)
        out["kuchi"][p] = c
        if c == 200 and isinstance(r, dict):
            out["nokori_acu"] = r
            break
    if out["nokori_acu"] is None:
        out["nokori_acu_torenai_riyuu"] = (
            "残ACUを返す口が開いていません（上の kuchi の数字が実測）。"
            "残高は app.devin.ai の画面にしか出ません＝APIでは取れない。")

    # お金の栓（yosan.py）の今の状態も一緒に出す。
    try:
        import yosan
        st = yosan.settei()
        limit = float((st.get("limits") or {}).get("devin") or 0)
        used = float((yosan.tsukatta_gokei("devin") or (0, 0))[0])
        out["saifu"] = {"jougen_yen": limit, "tsukatta_yen": used,
                        "nokori_yen": max(0.0, limit - used),
                        "1pon_yen": DEVIN_YEN_PER_SESSION,
                        "aiteru": (limit - used) >= DEVIN_YEN_PER_SESSION}
    except Exception as e:
        out["saifu"] = {"error": repr(e), "aiteru": False}
    _write(JISSOKU, out)
    return out


# ---------------------------------------------------------------- 仕事の作り方
def raw_names():
    d = os.path.join(REPO, "status", "shiire_raw")
    try:
        return sorted(os.path.splitext(p)[0] for p in os.listdir(d) if p.endswith(".json"))
    except Exception:
        return []


def make_job(state):
    """列が空なら自分で仕事を作る（仕入れ→裏取り→間違い探しの順）。"""
    q = _read(QUEUE, {"items": []})
    items = [it for it in (q.get("items") or []) if not it.get("done")]
    if items:
        it = items[0]
        it["done"] = True
        _write(QUEUE, q)
        return it
    # 自動で作る：まだ仕上げていない仕入れの素材を1件、完成条件まで詰めさせる。
    tsukatta = set(state.get("tsukatta_raw") or [])
    for nm in raw_names():
        if nm in tsukatta:
            continue
        state.setdefault("tsukatta_raw", []).append(nm)
        return {
            "name": "仕入れの仕上げ：%s" % nm,
            "kind": "shiire",
            "prompt": ("""リポジトリ https://github.com/tamago2022/tamago-shinchoku の
status/shiire_raw/%s.json を読んでください。ここには同定の素材（MusicBrainz等）だけが入っています。

【お題】このアーティストについて、**棚に出せる形の曲を最大3曲**まとめてください。
★まず「この素材が指しているのが本当に同一人物か」を、あなたの側で実測して確かめてください。
　こちらの前提が間違っている可能性を先に潰してください（結論はこちらからは言いません）。
%s
【出し方】
status/shiire_raw/%s.done.json に、次の形で書いて Pull Request を1本出してください。
{"artist":"","artistEvidence":[{"what":"公式チャンネル","url":"","channelId":""}],
 "songs":[{"title":"","videoId":"","thumb":"","copy":"","facts":[{"claim":"","src":["URL"]}]}],
 "hajiita":[{"title":"","riyuu":"何が取れなかったか"}]}
★hajiita（出せなかったもの）を必ず書いてください。0件のときも "hajiita": [] と書いてください。
""" % (nm, KANMON, nm)),
        }
    return {
        "name": "間違い探し：棚の中の別人混入",
        "kind": "machigai",
        "prompt": ("""リポジトリ https://github.com/tamago2022/tamago-shinchoku を調べてください。

【お題】棚のデータの中で「名前の字面が一致しただけで別人の曲が入っている」箇所を探してください。
★こちらの前提（もう全部直っている）が正しいかを、あなたの側で実測して確かめてください。
【やること】曲データを走査し、アーティスト名とチャンネル名／動画の出どころが
一致していない疑いのある行を全部出す。1行ごとに「なぜ疑わしいか」と「確かめたURL」を付ける。
★直すのは、証拠のURLが取れたものだけ。取れないものは「保留」として一覧に出す。
【報告】走査した件数／疑わしい件数／直した件数／保留の件数を数字で。Pull Requestを1本。
"""),
    }


# ---------------------------------------------------------------- 投げる／見る
def throw_devin(job):
    code, res = call("/sessions", {"prompt": SAHOU + job["prompt"], "idempotent": False})
    if code != 200:
        return None, "HTTP %s %s" % (code, str(res)[:180])
    return {"kuchi": "devin", "sid": res.get("session_id"),
            "url": res.get("url") or ("https://app.devin.ai/sessions/%s" % res.get("session_id"))}, None


def throw_jules(job):
    """0円の口。GitHubのIssueに jules の札を貼る（公式の呼び方）。"""
    try:
        import shigoto_furu
        r = shigoto_furu.furu("gemini", SAHOU + job["prompt"], title="【Julesに頼む】%s" % job["name"][:40])
    except Exception as e:
        return None, repr(e)
    if not r or not r.get("ok"):
        return None, str(r)[:180]
    num = r.get("number")
    return {"kuchi": "jules", "issue": num,
            "url": "https://github.com/tamago2022/joy-relief-station/issues/%s" % num}, None


def look_devin(cur):
    code, d = call("/session/" + str(cur.get("sid")), timeout=25)
    if code != 200:
        return False, None, "HTTP %s" % code
    st = d.get("status_enum")
    msgs = d.get("messages") or []
    last = str((msgs[-1].get("message") if msgs else "") or "")[:200]
    pr = d.get("pull_request")
    if st in ("finished", "blocked", "expired"):
        url = (pr or {}).get("url") if isinstance(pr, dict) else pr
        return True, (url or cur.get("url")), "%s / %s" % (st, last)
    return False, None, "%s / msgs=%d" % (st, len(msgs))


def look_jules(cur):
    """Issueのコメントを見る（工場側のkeijibanの口を借りる。gh経由・0円）。"""
    try:
        import gaibu_kuchi as gk
        jid = gk.enqueue_job("keijiban", {"action": "read",
                                          "repo": "tamago2022/joy-relief-station",
                                          "number": cur.get("issue")})
        r = gk.wait_job(jid, wait_sec=60, poll=5) or {}
    except Exception as e:
        return False, None, repr(e)[:160]
    if not r.get("ok"):
        return False, None, str(r)[:160]
    cms = r.get("comments") or []
    for c in cms:
        body = str(c.get("body") or "")
        if "http" in body and ("/pull/" in body or "Ready for" in body or "PR" in body):
            url = cur.get("url")
            for w in body.replace("(", " ").replace(")", " ").split():
                if w.startswith("http") and "/pull/" in w:
                    url = w.rstrip(".,)")
                    break
            return True, url, body[:200]
    return False, None, "コメント%d件" % len(cms)


# ---------------------------------------------------------------- 本体
LOCK = os.path.join(OUT_DIR, ".nagashi.lock")
LOCK_STALE = 300   # 5分。★実測（09:40の便）で、この係が外から強制終了されて鍵だけ残る事が
#   あったので短くする。鍵が残っても5分で次の便が必ず引き継ぐ。


def _lock():
    """★二重起動しない。1分おきに呼ばれるので、投げるのに240秒かかる間に
    次の便が入って**同じ仕事を2回投げる**のを止める（心臓が2本になった時と同じ事故）。"""
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        if os.path.exists(LOCK) and (time.time() - os.path.getmtime(LOCK)) < LOCK_STALE:
            return False
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write("%d %s\n" % (os.getpid(), _iso()))
        return True
    except Exception:
        return True


def _unlock():
    try:
        os.remove(LOCK)
    except Exception:
        pass


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # ★どんな理由で固まっても自分で抜ける（心臓の run_with_timeout と同じ考え方。
    #   ここは投げっぱなし(&)で呼ばれるので、上限を自分で持っていないと永久に居座る）。
    try:
        import signal

        def _jikangire(*_a):
            _unlock()
            raise SystemExit("240秒を超えたので自分で終わります（鍵は外しました）")
        signal.signal(signal.SIGALRM, _jikangire)
        signal.alarm(240)
    except Exception:
        pass
    if not _lock():
        print("前の便がまだ走っているので、今回は何もしません（二重投げの防止）")
        return 0
    try:
        return _main()
    finally:
        _unlock()


def _main():
    import gaibu_ai

    js = jissoku()
    st = _read(STATE, {"note": "1142番【流し続ける係】。1本ずつ・止まったら次を投げる。",
                       "inflight": None, "nageta": 0, "kaetta": 0, "rireki": [],
                       "tsukatta_raw": [], "hi": ""})
    today = _now().strftime("%F")
    if st.get("hi") != today:
        st["hi"] = today
        st["kyou_nageta"] = 0
    st["at"] = _iso()
    st["devin_hashiru"] = js.get("hashiru")
    st["devin_saifu"] = js.get("saifu")

    # ★Devinが0本になっている時間を毎日測る（目標0分）。1分おきに呼ばれる前提で数える。
    if st.get("zero_hi") != today:
        st["zero_hi"] = today
        st["devin_zero_fun_kyou"] = 0
        st["mita_fun_kyou"] = 0
    if js.get("hashiru") is not None:
        st["mita_fun_kyou"] = st.get("mita_fun_kyou", 0) + 1
        if js.get("hashiru") == 0:
            st["devin_zero_fun_kyou"] = st.get("devin_zero_fun_kyou", 0) + 1

    # ① 今の1本を見る
    cur = st.get("inflight")
    if cur:
        owari, url, memo = (look_devin(cur) if cur.get("kuchi") == "devin" else look_jules(cur))
        if owari:
            try:
                gaibu_ai.kaeri(cur.get("daicho_id"), url=url, memo=memo)
            except Exception as e:
                say("台帳に返りを書けませんでした: %r" % e)
            st["kaetta"] = st.get("kaetta", 0) + 1
            st["rireki"] = (st.get("rireki") or [])[-30:] + [
                {"name": cur.get("name"), "kuchi": cur.get("kuchi"),
                 "url": url, "owattaAt": _iso()}]
            st["inflight"] = None
            say("1本おわり：%s（%s）→ %s" % (cur.get("name"), cur.get("kuchi"), url))
            cur = None
        else:
            st["ima"] = memo

    # ② 空いていたら次を投げる（★止めない）
    if not cur and (st.get("kyou_nageta", 0) < MAX_PER_DAY):
        job = make_job(st)
        saifu = js.get("saifu") or {}
        kuchi, res, err = None, None, None
        if saifu.get("aiteru"):
            try:
                import yosan
                ok, why = yosan.mitsumori("devin", DEVIN_YEN_PER_SESSION,
                                          "Devinに1本投げる（1142番の流し続ける係）")
            except Exception as e:
                ok, why = False, repr(e)
            if ok:
                res, err = throw_devin(job)
                kuchi = "devin"
            else:
                st["devin_tomete_iru_riyuu"] = why
        else:
            st["devin_tomete_iru_riyuu"] = (
                "財布の栓（yosan devin）が %s円。1本 %s円なので投げません。"
                "★開けるなら: python3 tools/yosan.py --set devin %d"
                % ((saifu.get("jougen_yen")), DEVIN_YEN_PER_SESSION,
                   int(DEVIN_YEN_PER_SESSION) + 1))
        if res is None:
            # Devinが使えないあいだも列は止めない → 0円の口へ同じ仕事を回す
            res, err2 = throw_jules(job)
            kuchi = "jules"
            err = err or err2
        if res:
            kigen = _iso(_now() + timedelta(hours=KIGEN_HOURS))
            row = gaibu_ai.nage(kuchi, job["name"], kigen,
                                kane=("実測 約%d円/本（Devin従量）" % DEVIN_YEN_PER_SESSION
                                      if kuchi == "devin" else "0円（GitHub経由・月額の中）"),
                                memo="1142番の流し続ける係が自動で投げた")
            res.update({"name": job["name"], "daicho_id": row["id"],
                        "nageta_at": _iso(), "kigen": kigen})
            st["inflight"] = res
            st["nageta"] = st.get("nageta", 0) + 1
            st["kyou_nageta"] = st.get("kyou_nageta", 0) + 1
            say("投げました：%s → %s（%s）" % (job["name"], res.get("url"), kuchi))
        else:
            st["nagerarenakatta"] = err
            say("投げられませんでした：%s" % err)

    # ③ 返ってきていないもの＝赤
    rows = gaibu_ai.load()
    ima = _now()
    aka = []
    for r in rows:
        if r.get("kaeri") == "yes":
            continue
        try:
            kg = datetime.fromisoformat(str(r.get("kigen")))
            if kg.tzinfo is None:
                kg = kg.replace(tzinfo=JST)
        except Exception:
            continue
        if kg < ima:
            aka.append({"id": r.get("id"), "ai": r.get("ai"), "what": r.get("what"),
                        "kigen": r.get("kigen")})
    st["nageta_kedo_kaette_konai"] = len(aka)
    st["aka_ichiran"] = aka[-20:]
    st["daicho_nageta_gokei"] = len(rows)
    st["daicho_kaetta_gokei"] = len([r for r in rows if r.get("kaeri") == "yes"])
    st["hashitte_iru_no_ni_torete_inai"] = (
        st["daicho_nageta_gokei"] > 0 and st["daicho_kaetta_gokei"] == 0)

    # ④ 門が弾いた数（0が続いたら門が死んでいる＝赤）
    hj = 0
    p = os.path.join(REPO, "status", "1142_kanmon.jsonl")
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if str(d.get("at", "")).startswith(today) and d.get("tsuuka") is False:
                    hj += 1
    try:
        hold = len(os.listdir(os.path.join(REPO, "status", "nyuka", "hold")))
    except Exception:
        hold = 0
    st["hajiita_kyou"] = hj
    st["horyuu_gokei"] = hold
    st["mon_shinderu"] = (hj == 0)
    _write(STATE, st)
    print(json.dumps({k: st.get(k) for k in
                      ("devin_hashiru", "kyou_nageta", "nageta_kedo_kaette_konai",
                       "hajiita_kyou", "devin_tomete_iru_riyuu")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
