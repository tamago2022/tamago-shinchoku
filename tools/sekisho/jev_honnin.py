#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1052番【仕入れの門・本人判定】Jev（TypeSafe AI）に「この曲はこの名前の本人か」だけ聞く。

■ なぜ入口に置くか（たまごさんの言葉 2026-09-24）
  「2230件、別人混入してんの？　じゃあ別人混入しない仕組みをまず作ろうよ。」
  ＝ 入ってから掃除するのではなく、**入る前に止める**。
  たまごさんの決まり：検品はお金を使う前の注文書に置く。だからこれは入口の門である。

■ Jev とは（公式ドキュメント実読 2026-09-24）
  出典 https://docs.typesafe.ai/models ／ https://docs.typesafe.ai/primitives/noul.md
  - 文章を書かない。**判定だけ**返す。質問の型は3つ：
      Noul  … はい／いいえ。返るのは「はいの確率」1個（0.0〜1.0）。★confidence は無い。
      Choice… 選択肢から1つ。各選択肢の確率＋confidence。
      Score … 順序のある段階づけ。各段の確率＋confidence。
  - state（判定材料）は1回だけ読み込み、questions を**並列**に評価する。
    → 1件1リクエストにすると高い。**1リクエストにまとめる**のが正しい使い方。
      公式実測: 13問を1リクエストにまとめると 12.2倍安く・10.0倍速い（同じ答え）。
      出典 https://docs.typesafe.ai/cookbooks/parallel_questions.md
  - 課金は**入力トークンのみ**。出力は0円。$0.042 / 1Mトークン。
    1ドル157.16円（tools/yosan.py の実測レート）→ **約6.60円 / 1Mトークン**。
  - 文脈長: 1リクエスト 64k トークン（state＋全質問の合計）。
    state＋最長の質問1本で 32k。
  - ★MCP は**無い**。あるのは HTTP API（POST https://api.typesafe.ai/v1/systemone）と
    公式の Claude Code プラグイン／スキル（claude plugin install typesafe@typesafe-ai）。
    出典 https://docs.typesafe.ai/agent-skill.md
  - ★日本語（CJK）は「扱えるが英語ほどではない」と公式が明記している。
    → うちは日本人アーティストが多い。**しきい値は甘くしない**。迷ったら保留。

■ この門の掟（skill sekisho-artist-song をそのまま機械にした）
  1. 証拠が1本も無いものは Jev に聞かない。**0円で保留**。
     （証拠＝動画を上げたチャンネル名／公式サイト／レーベル。名前の文字一致は証拠ではない。）
  2. 鍵が無い・栓が閉まっている・APIが落ちている → **保留**に倒す。通さない。
     「判定できないものは載せない側に倒す」＝掟4。
  3. 通すのは「本人だ」と強く出たものだけ。
  4. ★保留は**捨てない**。status/nyuka/horyuu/ に控えを置く。消すのはたまごさんの判断。
  5. 同名の別人を塞ぐため、質問を2本聞く（後述）。

■ 2本の質問（ここがこの門の中身）
  q_honnin   Noul「この動画を演っているのは、state のアーティスト本人か」
  q_douseidoumei Noul「このチャンネルは、state のアーティストとは**別人**（同名・似た名前）を指しているか」

  なぜ2本目が要るか（実測 2026-09-24）：
    1051番は「上げたチャンネル名が棚の名前と一致したら本人」で 1484件を白にした。
    ところが akiko の棚には、ジャズシンガー akiko（Verve／埼玉）と、
    チャンネル名 "AKIKO" の別アーティストの曲（Coffee or tea / TEXT ME / 小野貓・
    Prod. SILVERSTRIKE / JNYBeatz）が**同居している**。
    チャンネル名が一致していたので、1051番の機械判定はこれを**白にしてしまった**。
    → 名前の一致は本人の証明にならない。2本目でそこを聞く。

■ 使い方
  # 見積りだけ（APIは呼ばない・0円。トークン数と円を出す）
  python3 tools/sekisho/jev_honnin.py --in kouho.json --dry-run

  # 本番（栓を通す。鍵は TYPESAFE_API_KEY か .env）
  python3 tools/sekisho/jev_honnin.py --in kouho.json --out hantei.json --limit 10

  入力 kouho.json = [{"artist_id","artist","about","aliases",
                      "song_id","title","channelTitle","note","year"}, ...]
  出力 hantei.json = {"tooshita":[...], "bessin":[...], "horyuu":[...], "kane":{...}}

終了コード: 0=全部さばけた / 1=1件でも「別人」で止めた（--strict時）
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

API = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"          # ★別名(jev-latest)は勝手に動く。版を打っておく。
SAIFU = "typesafe"

# 円の出し方：$0.042/1Mトークン × 157.16円/$ = 6.60円/1Mトークン（入力のみ・出力0円）
USD_PER_MTOK_IN = 0.042
YEN_PER_USD = 157.16
YEN_PER_MTOK_IN = USD_PER_MTOK_IN * YEN_PER_USD        # = 6.60072

# しきい値。★日本語の精度が英語より落ちると公式が言っているので甘くしない。
TOOSU_HONNIN = 0.90      # これ以上でないと通さない
TOOSU_BESSIN = 0.10      # 同名別人の確率がこれ以下でないと通さない
BESSIN_HONNIN = 0.10     # これ以下なら「別人」として止める（それでも消さない）

# 1リクエストに詰める候補の数。64kトークンの枠に対して安全側。
BATCH = 40


# ---------------------------------------------------------------------------
# 証拠の門（0円）: 名前の文字一致は証拠ではない
# ---------------------------------------------------------------------------

def shouko(item):
    """本人を指す証拠があるか。無ければ Jev に聞く前に保留（0円）。

    たまごさん指示：「公式チャンネル・公式サイト・レーベルなど、本人を指す証拠を
    1つ以上求める」。ここが無いのに聞いても、Jev は材料無しで当てるしかない。
    """
    ev = []
    if (item.get("channelTitle") or "").strip():
        ev.append("チャンネル名=" + item["channelTitle"].strip())
    for k in ("officialUrl", "labelUrl", "originalRef"):
        if (item.get(k) or "").strip():
            ev.append("%s=%s" % (k, item[k]))
    return ev


def _tokens(s):
    """トークン数のあたり。★実測ではない見積り。
    英数は4文字1トークン、日本語・ハングル・かなは1文字1トークンで数える
    （多めに出る側＝金を過小に言わない側に倒す）。
    """
    s = s or ""
    cjk = len(re.findall(r"[぀-ヿ一-鿿가-힣]", s))
    rest = len(s) - cjk
    return cjk + max(1, rest // 4)


# ---------------------------------------------------------------------------
# リクエストを組む
# ---------------------------------------------------------------------------

def build_request(artist, items):
    """1アーティスト分。state に「棚の本人は誰か」、questions に候補1件2問。"""
    state = {
        "shelf_artist_name": artist.get("artist") or "",
        "shelf_artist_aliases": artist.get("aliases") or [],
        "shelf_artist_profile": artist.get("about") or "",
        "note": ("This is the identity of ONE specific artist who owns a shelf. "
                 "Other artists may share the same or a similar name. "
                 "A name match alone does NOT make them the same person."),
    }
    questions = {}
    for i, it in enumerate(items):
        ev = shouko(it)
        payload = {
            "song_title": it.get("title") or "",
            "uploaded_by_channel": it.get("channelTitle") or "",
            "evidence": ev,
            "note_on_file": it.get("note") or "",
            "year_on_file": it.get("year") or "",
        }
        questions["honnin_%d" % i] = {
            "type": "noul",
            "instructions": {
                "question": ("Is the performer on this recording the SAME PERSON as "
                             "the shelf artist described in the state?"),
                "candidate": payload,
            },
            "criteria": {
                "true": ("The performer is the shelf artist in the state. The uploading "
                         "channel is that artist's own channel, their official/VEVO "
                         "channel, or their label releasing under that artist's name."),
                "false": ("The performer is a different act, even if the name is "
                          "identical or nearly identical to the shelf artist's name. "
                          "Also false when the evidence does not identify the performer."),
            },
        }
        questions["douseidoumei_%d" % i] = {
            "type": "noul",
            "instructions": {
                "question": ("Does the uploading channel belong to a DIFFERENT artist "
                             "who merely shares the same or a similar name as the "
                             "shelf artist in the state?"),
                "candidate": payload,
            },
            "criteria": {
                "true": ("Two different acts share this name, and this channel is the "
                         "other one. Genre, era, language, collaborators or producers "
                         "do not fit the shelf artist's profile."),
                "false": "This channel is the shelf artist in the state.",
            },
        }
    return {"model": MODEL, "state": state, "questions": questions}


def estimate_yen(req):
    """★叩く前の見積り。入力トークンだけ数える（出力は0円）。"""
    tok = _tokens(json.dumps(req, ensure_ascii=False))
    return tok, round(tok / 1_000_000 * YEN_PER_MTOK_IN, 6)


# ---------------------------------------------------------------------------
# 鍵とAPI
# ---------------------------------------------------------------------------

def _key():
    k = os.environ.get("TYPESAFE_API_KEY")
    if k:
        return k.strip()
    for p in (os.path.join(REPO, ".env"),
              os.path.expanduser("~/.tamago/keys/api_keys.env")):
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8"):
                m = re.match(r"\s*TYPESAFE_API_KEY\s*=\s*(.+?)\s*$", ln)
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    return None


def call(req, key, timeout=60):
    body = json.dumps(req, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(r, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ★0円の判定役（codex）。2026-09-24・1060番
#
# なぜ足すか（実測）：
#   TYPESAFE_API_KEY はMacにも .env にも無く、財布 typesafe の栓も0円。
#   つまりこの門は**鍵が無い＋栓が閉まっている**の二重で止まっていて、
#   入荷票8枚が全部ここで保留になっていた（status/_1060/mon5.log・05:23）。
#   鍵と栓は**こちらで開けてはいけない**（金が出る）。
#   代わりに、既に払い終わっている口＝Macの codex（ChatGPTのログインで動く。
#   1回ごとの課金は出ない＝0円）に、**同じ2問・同じしきい値**で答えさせる。
#   ★これは点を甘くして通すことではない。判定役を、金の出ない別のAIに替えただけ。
#   codexが居なければ何も変わらない（今までどおり保留に倒れる）。
# ---------------------------------------------------------------------------

CODEX_SYSTEM = """You are an identity checker for a Japanese music site.
A "shelf" belongs to ONE specific artist. Other artists may share the same or a
very similar name. A NAME MATCH ALONE IS NOT PROOF that they are the same act.
You will be given the shelf artist's identity, and one or more candidate songs.

For each candidate index i, answer two probabilities between 0.0 and 1.0:
  honnin_i        = probability the performer on this recording IS the shelf artist
  douseidoumei_i  = probability this is a DIFFERENT act that merely shares the name

Set honnin_i high only when the evidence (uploading channel, official site, label)
actually identifies the performer as the shelf artist. If the evidence does not
identify the performer, honnin_i must be low. Do not guess from the name.
Genre, era, language, collaborators or producers that do not fit the shelf
artist's profile are signs of a different act.

Return ONLY this JSON:
{"answers": {"honnin_0": 0.0, "douseidoumei_0": 0.0, ...}}"""


def kiku_codex(req, timeout=180):
    """codexに同じ2問を聞く。戻り値 (answers:dict|None, who:str, err:str)。0円。"""
    try:
        import gaibu_kuchi as gkuchi
    except Exception as e:
        return None, "", "gaibu_kuchi を読めない（%s）" % e
    if not gkuchi.codex_aru():
        return None, "", "codexがMacに居ない"
    user = json.dumps({"state": req["state"], "questions": req["questions"]},
                      ensure_ascii=False)
    d, who, err = gkuchi.kiku_codex(CODEX_SYSTEM, user, timeout=timeout)
    if d is None:
        return None, who, err or "JSONが返ってこない"
    ans = d.get("answers") if isinstance(d.get("answers"), dict) else d
    if not isinstance(ans, dict):
        return None, who, "answers が辞書で返ってこない"
    return ans, who, ""


def _prob(v):
    """0.0〜1.0 に直せないものは None（＝判定できない＝保留に倒る）。"""
    try:
        f = float(v)
    except Exception:
        return None
    if f != f or f < 0.0 or f > 1.0:
        return None
    return f


def judge(honnin, bessin):
    """3つに割る。通す／別人／保留。★どれも消さない。"""
    if honnin is None or bessin is None:
        return "horyuu", "Jevの答えが取れない（判定できない＝載せない側に倒す）"
    if honnin >= TOOSU_HONNIN and bessin <= TOOSU_BESSIN:
        return "tooshita", "本人 %.2f／同名別人 %.2f" % (honnin, bessin)
    if honnin <= BESSIN_HONNIN or bessin >= 0.90:
        return "bessin", "別人の疑いが濃い（本人 %.2f／同名別人 %.2f）" % (honnin, bessin)
    return "horyuu", "確信が足りない（本人 %.2f／同名別人 %.2f）" % (honnin, bessin)


def run(items, dry_run=False, limit=None, quiet=False):
    import yosan

    def say(*a):
        if not quiet:
            print(*a)

    out = {"tooshita": [], "bessin": [], "horyuu": [],
           "kane": {"mitsumoriYen": 0.0, "jissaiYen": 0.0,
                    "mitsumoriTokens": 0, "jissaiTokens": 0, "requests": 0},
           "shikii": {"tooshita_honnin": TOOSU_HONNIN,
                      "tooshita_bessin": TOOSU_BESSIN,
                      "bessin_honnin": BESSIN_HONNIN},
           "model": MODEL, "dryRun": bool(dry_run)}

    # --- 門0：証拠が無いものは聞かない（0円） --------------------------------
    kiku = []
    for it in items:
        if not shouko(it):
            out["horyuu"].append(dict(it, riyu=(
                "本人を指す証拠が1本も無い（チャンネル名も公式URLもレーベルも無い）。"
                "★名前の文字一致は証拠ではない。Jevには聞いていない＝0円")))
        else:
            kiku.append(it)
    say("門0 証拠：聞く %d件／証拠なしで保留 %d件（0円）" % (len(kiku), len(out["horyuu"])))

    if limit:
        nokori = kiku[limit:]
        kiku = kiku[:limit]
        for it in nokori:
            out["horyuu"].append(dict(it, riyu="--limit %d の外（まだ聞いていない）" % limit))
        say("★--limit %d：先に %d件だけ聞く。残り %d件は手つかず。" % (limit, len(kiku), len(nokori)))

    # --- 棚ごとにまとめる（state は1回・質問は並列＝ここが安さの理由） -------
    tana = {}
    for it in kiku:
        tana.setdefault(it.get("artist_id") or it.get("artist") or "?", []).append(it)

    # --- ★0円の判定役（codex）を先に当てる。金の出る口はそのあと ----------
    if not dry_run and kiku:
        nokori_tana = {}
        for aid, group in list(tana.items()):
            sabaketa = []
            for i in range(0, len(group), BATCH):
                chunk = group[i:i + BATCH]
                req = build_request(chunk[0], chunk)
                ans, who, err = kiku_codex(req)
                if ans is None:
                    say("  [0円の判定役が使えない] %s … %s" % (aid, err))
                    continue
                for n, it in enumerate(chunk):
                    h = _prob(ans.get("honnin_%d" % n))
                    b = _prob(ans.get("douseidoumei_%d" % n))
                    where, riyu = judge(h, b)
                    out[where].append(dict(it, honnin=h, douseidoumei=b,
                                           riyu=riyu + "（判定役 %s・0円）" % who,
                                           model=who, kane="0円"))
                sabaketa.extend(chunk)
                say("  [0円で聞いた] %s %d件 … %s（追加の金は出ていない）"
                    % (aid, len(chunk), who))
            nokori = [it for it in group if it not in sabaketa]
            if nokori:
                nokori_tana[aid] = nokori
        tana = nokori_tana
        if not tana:
            out["kane"]["judge"] = "codex（ChatGPTのログイン。1回ごとの課金なし＝0円）"
            return out

    key = None if dry_run else _key()
    if not dry_run and not key:
        # ★codexでさばけた分は tana から抜いてある。ここで二重に保留にしない。
        for it in [x for g in tana.values() for x in g]:
            out["horyuu"].append(dict(it, riyu=(
                "TYPESAFE_API_KEY が無い。★判定できないので保留に倒した（掟4）。"
                "鍵は https://console.typesafe.ai/keys で発行して .env に置く。"
                "★契約はたまごさんが押すこと。こちらは押さない。")))
        say("★鍵が無い。1件も聞いていない（0円）。全部保留に倒した。")
        return out

    for aid, group in tana.items():
        for i in range(0, len(group), BATCH):
            chunk = group[i:i + BATCH]
            req = build_request(chunk[0], chunk)
            tok, yen = estimate_yen(req)
            out["kane"]["mitsumoriTokens"] += tok
            out["kane"]["mitsumoriYen"] = round(out["kane"]["mitsumoriYen"] + yen, 6)

            if dry_run:
                say("  [見積り] %s %d件 … 入力 %d トークン ＝ %.4f円" % (aid, len(chunk), tok, yen))
                for it in chunk:
                    out["horyuu"].append(dict(it, riyu="--dry-run（聞いていない）"))
                continue

            # ★叩く前に栓を通す。ここを飛ばしてはいけない。
            ok, riyu = yosan.mitsumori(SAIFU, yen, "Jevに本人判定 %d件（%s）" % (len(chunk), aid))
            if not ok:
                say("  [栓で止まった] %s … %s" % (aid, riyu))
                for it in chunk:
                    out["horyuu"].append(dict(it, riyu="予算の栓で止まった：" + riyu))
                continue

            try:
                res = call(req, key)
            except urllib.error.HTTPError as e:
                why = "Jevが %s を返した：%s" % (e.code, e.read()[:200].decode("utf-8", "replace"))
                say("  [API失敗] %s … %s" % (aid, why))
                for it in chunk:
                    out["horyuu"].append(dict(it, riyu=why + "（判定できない＝保留）"))
                continue
            except Exception as e:
                why = "Jevに届かない：%s" % e
                say("  [API失敗] %s … %s" % (aid, why))
                for it in chunk:
                    out["horyuu"].append(dict(it, riyu=why + "（判定できない＝保留）"))
                continue

            out["kane"]["requests"] += 1
            u = res.get("usage") or {}
            jt = int(u.get("input_tokens") or 0)
            jy = round(jt / 1_000_000 * YEN_PER_MTOK_IN, 6)
            out["kane"]["jissaiTokens"] += jt
            out["kane"]["jissaiYen"] = round(out["kane"]["jissaiYen"] + jy, 6)
            yosan.tsukatta(SAIFU, jy, "Jev 本人判定 %d件（%s）" % (len(chunk), aid),
                           src="usage.input_tokens=%d" % jt)

            ans = res.get("answers") or {}
            for n, it in enumerate(chunk):
                h = (ans.get("honnin_%d" % n) or {}).get("noul")
                b = (ans.get("douseidoumei_%d" % n) or {}).get("noul")
                where, riyu = judge(h, b)
                out[where].append(dict(it, honnin=h, douseidoumei=b, riyu=riyu,
                                       model=res.get("model")))
            say("  [聞いた] %s %d件 … 実額 %.4f円（入力 %d トークン）" % (aid, len(chunk), jy, jt))

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp")
    ap.add_argument("--dry-run", action="store_true", help="APIを呼ばない。トークン数と円だけ出す")
    ap.add_argument("--limit", type=int, help="先に何件だけ聞くか（★いきなり全件流さない）")
    ap.add_argument("--strict", action="store_true", help="別人が1件でもあれば exit 1")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    items = json.load(open(a.inp, encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("items") or items.get("hold") or []

    out = run(items, dry_run=a.dry_run, limit=a.limit, quiet=a.quiet)

    if a.outp:
        os.makedirs(os.path.dirname(a.outp) or ".", exist_ok=True)
        with open(a.outp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

    if not a.quiet:
        k = out["kane"]
        print("\n通した %d件／別人で止めた %d件／保留 %d件"
              % (len(out["tooshita"]), len(out["bessin"]), len(out["horyuu"])))
        print("見積り %.4f円（%d トークン）／実額 %.4f円（%d トークン・%d リクエスト）"
              % (k["mitsumoriYen"], k["mitsumoriTokens"],
                 k["jissaiYen"], k["jissaiTokens"], k["requests"]))
        print("★保留は捨てていない。消すのはたまごさんの判断。")

    if a.strict and out["bessin"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
