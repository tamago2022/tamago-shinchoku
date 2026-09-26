#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""971番の相棒：外部から入れたもののコピーを**毎朝ひとりでに直す係**。

たまごさん（2026-09-22・原文）:
  「外部追加分のコピーを全部直す ⇨ これはもう毎日やること」
  「走った回数と、直した件数の両方を数える。走った>0 なのに 直した=0 は赤」
  「できなかったものは理由をそのまま残す。嘘のログを書かない。skip を黙って飲み込まない」

------------------------------------------------------------------
なぜ要るか（実測）
------------------------------------------------------------------
  971番（tools/gaibu_copy_nippou.py）は**数える係**として動いていた。
  09-22 06:07 時点で「手つかず16件」を毎回きちんと出していた。
  だが**直す係が居なかった。**だから数字だけが毎朝更新され、16件は16件のまま座り続けた。
  ここがその「直す係」。数える係とは別ファイルにして、判定だけを数える係から輸入する
  （＝水道水の基準を2箇所に書かない。基準が増えると必ずズレる）。

------------------------------------------------------------------
決め
------------------------------------------------------------------
  ・新しい常駐（launchd便）は増やさない。既にある5分便 machine_status_push.sh に相乗りする。
    → **心臓（auto_launcher）が死んでいても launchd が直接起こす便なので必ず回ってくる。**
  ・中で1日1回ゲートする。朝06:00以降の最初の便で走る。手で回したいときは
    status/.gaibu_copy_naoshi_force を置く（置いた次の便で即走る）。
  ・書き直しは `claude -p`（既にこの工場が使っている口。新しい課金APIを増やさない）。
  ・**材料が無いものは書かない。**題名しか無く、元コピーも無く、URLも無いものは
    「見ていないものを想像で書く」ことになるので**触らず、理由を残して一覧に出す。**
    （たまご憲法11条・関所「出典の取れない断定は書かない」／§11-3「空欄で出す」）
  ・書き直した結果は**もう一度同じ判定にかける。**水道水のままなら書き戻さない。
  ・前の文は必ず残す（status/public/gaibu_copy_naoshi.json の history）。戻せる形にする。
  ・鍵の値はどこにも書き出さない。名前と、通ったか通らないかだけ。

------------------------------------------------------------------
回線についての実測事実
------------------------------------------------------------------
  Cowork/Dispatchのサンドボックスからは Supabase へ出られない（Tunnel 403）。
  たまごさんのMacからは出る。だからここ（5分便＝Mac側）で叩く。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 判定・鍵の探索・取得は「数える係」のものをそのまま使う。**基準を2箇所に書かない。**
import gaibu_copy_nippou as nippou  # noqa: E402

JST = timezone(timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "gaibu_copy_naoshi.json")
GATE = os.path.join(STATUS, ".gaibu_copy_naoshi_last")
FORCE = os.path.join(STATUS, ".gaibu_copy_naoshi_force")
LOCK = os.path.join(STATUS, ".gaibu_copy_naoshi.lock")

# ★1049番（2026-09-24）：手書きの下書き置き場。
#   なぜ要るか（実測）：09-23 06:25 の回で「直せなかった19件」のうち3件の理由が
#   **「題名が英語の原題のまま」**だった。この係は whisper（コピー）しか書き戻さないので、
#   何度書き直しても判定は題名で落ち続ける＝**永久に片づかない列**になっていた。
#   さらに「水道水・テンプレの語」で落ちた分も、機械の書き直しが2回とも同じ水たまりに
#   落ちて座り続けていた。
#   → 人（またはサンドボックス側のセッション）が手で書いた案をここに置けば、
#     この係が**AIを呼ばずに**それを採る。題名も一緒に置けば題名も直す。
#     置いた案も必ず同じ判定（nippou.judge）を通す。通らなければ書き戻さない。
TEGAKI_DIR = os.path.join(STATUS, "copy_tegaki")
TEGAKI_DONE = os.path.join(TEGAKI_DIR, "done")

MORNING_HOUR = 6          # 朝6時以降の最初の便で走る
LOCK_STALE_SEC = 60 * 60  # 60分以上握ったままのロックは詰まりとみなす
DEADLINE_SEC = 20 * 60    # 1回の持ち時間。超えたら残りは次の回へ（Macを占有し続けない）
MAX_PER_RUN = 25          # 1回で直す上限（Macを占有しないため。残りは翌朝に回る）
#   ふだん入ってくるのは1日3〜4件なので、この数字が効くのは溜まりを片づける日だけ。
#   控えの口は1件2〜3秒なので、25件でも1〜2分。claude -p が生きている日は
#   黙りを2回見た時点でその回は控えに任せるので、150秒×25を焼くことはない。
CLAUDE_TIMEOUT = 150
HISTORY_KEEP = 200

CLAUDE = os.environ.get("CLAUDE_BIN") or (
    os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

# ---- 1158番：claude は必ず関所を通す（2026-09-26）----
# 同時起動の競合で refreshToken が空を書き戻され鍵ごと消える事故を、
# 起動口で物理的に止める。上限は status/dojisu_jougen.json の「同時上限」。
# 関所は引数をそのまま素通しするので、呼ぶ側のコードは1文字も変わらない。
_KANMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1158_kanmon.py")
if os.path.exists(_KANMON):
    os.environ.setdefault("KANMON_CLAUDE_BIN", CLAUDE)
    CLAUDE = _KANMON



import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import claude_auth as _claude_auth


def claude_env():
    """正本は tools/claude_auth.py（2026-09-25に1か所へ集約）。

    ここに実体を置くと、4か所のコピーが直すたびにずれる。呼ぶだけにする。
    """
    return _claude_auth.claude_env()


# ---------------------------------------------------------------- 書き直しの注文書
# bonjovi-ojisan-kobun（コピーの型）と sekisho-jijitsu-shutten（出典の関所）を、
# スキルを読めない環境でも効く形に落としたもの。**新しい基準を発明しない。**
PROMPT = """あなたは「ごきげん補給所」のコピーを書く編集者です。
下の1件について、カードに載せる一言（whisper）を書き直してください。

【型：ボンジョビおじさん構文】
コピーがつまらなくなる原因は決まっています。**紹介文を書いてしまうから。**
この棚が欲しいのは紹介ではなく、**ただの行為が小さな事件に変わる瞬間**です。

　電車に乗るだけ　→　全員ボンジョビ部に入部
　公園で歌うだけ　→　町内会ロックフェス
　車でバラードを聴くだけ　→　ふたりだけの教会
　ラジオを聴くだけ　→　夜の逃げ道が鳴る

良い文の手ざわり（この温度・この長さ・この終わり方）：
　狭い車の中が、ふたりだけの教会になる。
　小さなラジオから、夜の逃げ道が鳴っている。
　濡れた街に、ロックンロールのエンジンがかかる。
　強がってる人の背中を、そっと知ってくれてる歌。

この4つに共通していることを守ってください：
　・読み手に一度も命令していない。「〜しよう」「〜してみて」「〜しませんか」が無い。
　・「！」が1つも無い。
　・言い切りで終わる。誘うのは、行きたくさせることであって、呼びかけることではない。
　・題名をそのまま置き直していない。

【長さ】1文、長くて2文。全部で25〜60文字。短いほど強い。

【絶対の禁止】これを1つでもやったら不合格です。
・「収められています」「が映し出され」「する様子」などの説明テンプレ。
・「必見」「お見逃しなく」「間違いなし」「体感しよう」「話題」「反響」「絶賛」など、
　煽る語・観測していない他人の反応。
・「！」「!」を使うこと。
・「〜しよう」「〜してみて」「〜しませんか」「〜に参加」など、読み手への呼びかけ・命令。
・**材料に書かれていないことを足すこと。**国名・地名・年号・人物名・関係・受賞・数字・
　匂い・音・天気を、材料に無いのに書いたら、その時点で失格です。
　（実例：題名が「初レモン赤ちゃん」だけなのに「街全体がフレッシュな香りで満たされる」と
　　書いたものがありました。これは嘘です。書いてはいけません。）
・たまごさん個人を主語にしない。

【材料】ここに書いてあることだけが、あなたが知っている全部です。
題名：%(title)s
いま載っている一言：%(copy)s
出どころ：%(url)s

【出し方】
書き直した一言だけを1行で出す。前置き・説明・かぎかっこ・箇条書きを付けない。
材料が薄すぎて、何かを足さないと1行も書けない場合は、無理に書かず
NO_MATERIAL とだけ出す。**薄いまま無理に書くより、NO_MATERIAL の方が正解です。**"""


LOG = os.path.join(STATUS, "gaibu_copy_naoshi.log")


def log(msg):
    """自分で足跡を残す。**呼ぶ側のログ任せにしない。**
    実測（2026-09-22 06:36）：シェル側のログだけに頼っていたら、1回目が何も残さずに
    消えていて、走ったのか落ちたのかすら分からなかった。"""
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def take_lock():
    """二重起動を防ぐ。詰まったロックは時間で剥がす（門前払いを続けない）。"""
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        age = time.time() - os.path.getmtime(LOCK)
        alive = False
        if pid:
            try:
                os.kill(pid, 0)
                alive = True
            except Exception:
                alive = False
        if alive and age < LOCK_STALE_SEC:
            return False
        try:
            os.remove(LOCK)
        except Exception:
            pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    return True


def drop_lock():
    try:
        os.remove(LOCK)
    except Exception:
        pass


def clean(s):
    """CLIの返事を1行の一言に整える。"""
    s = (s or "").strip()
    # 前置きが付いてきたら最後の非空行を採る（CLIはたまに「はい、こちらです：」を足す）
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return ""
    s = lines[-1] if len(lines) > 1 and len(lines[-1]) >= 12 else lines[0]
    s = s.strip().strip("「」\"'`").strip()
    s = re.sub(r"^[-*・\d\.\s]+", "", s)
    return s.strip()


CLAUDE_DOWN = [None]   # この回で claude が寝ていると分かったら、以降は待たずに控えへ回す
CLAUDE_SILENT = [0]    # 黙ったまま返らなかった回数


def ask_claude(title, copy, url, diag):
    """claude -p に書き直させる。通らなければ (None, 理由) を返す。嘘のログを書かない。"""
    if CLAUDE_DOWN[0]:
        return None, CLAUDE_DOWN[0]
    # 2026-09-25：切れていると分かっているのに叩かない。
    # 叩くと1件あたり150秒だまって返らず、そのうえ「失敗」が25件ぶん積み上がる。
    # 工場が既に立てている札（status/no_launch.flag）を先に見て、待ちに戻す。
    _ng = _claude_auth.login_ng()
    if _ng:
        CLAUDE_DOWN[0] = "claudeの認証が切れている（%s・叩かずに待ちへ戻しました）" % _ng
        return None, CLAUDE_DOWN[0]
    prompt = PROMPT % {"title": title or "（題名なし）",
                       "copy": copy or "（まだ無い）",
                       "url": url or "（無い）"}
    cmd = [CLAUDE, "-p", "--model", "claude-sonnet-5", "--output-format", "json", prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT,
                           cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL,
                           env=claude_env())
    except subprocess.TimeoutExpired:
        # 実測（2026-09-22 06:53〜）：認証が切れていると `claude -p` は
        # エラーを返さずただ黙る＝1件ごとに150秒を捨てる。2回黙ったらこの回は控えに任せる。
        CLAUDE_SILENT[0] += 1
        if CLAUDE_SILENT[0] >= 2:
            CLAUDE_DOWN[0] = "claude -p が黙ったまま返らない（%d回連続）" % CLAUDE_SILENT[0]
        return None, "claude -p が %d秒で返らなかった" % CLAUDE_TIMEOUT
    except FileNotFoundError:
        return None, "claude コマンドが見つからない（%s）" % CLAUDE
    except Exception as e:
        return None, "claude -p が起動できない（%s）" % type(e).__name__
    out = (r.stdout or "") + (r.stderr or "")
    if "Failed to authenticate" in out or "OAuth session expired" in out:
        # 1件で分かったことを25件ぶん繰り返さない（150秒×25＝1時間を無駄に焼かない）
        CLAUDE_DOWN[0] = "claudeの認証が切れている（OAuth session expired）"
        return None, CLAUDE_DOWN[0]
    if "usage limit" in out.lower() or "rate limit" in out.lower():
        CLAUDE_DOWN[0] = "claudeの利用上限に当たった"
        return None, CLAUDE_DOWN[0]
    try:
        j = json.loads(r.stdout or "{}")
        text = j.get("result") or ""
        if j.get("total_cost_usd") is not None:
            diag.append("cost_usd=%s" % j.get("total_cost_usd"))
    except Exception:
        text = r.stdout or ""
    text = clean(text)
    if not text:
        return None, "claude -p が空を返した（rc=%s）" % r.returncode
    if "NO_MATERIAL" in text:
        return None, "材料が題名だけで、足さずには書けない（動画を見ないと書けない）"
    return text, None


# ---------------------------------------------------------------- 書き手の控え
# 実測（2026-09-22 06:47・1回目の本番）：`claude -p` が
#   「OAuth session expired」で12件とも落ちた。＝**書き手が1人だと、その1人が寝た日は
#   仕組み全体が0件になる。**たまごさんに「ログインし直して」と頼む間も止めないために、
#   工場が既に持っている外部の口（tools/gaibu_kuchi.py）へ降りる。
# お金：1件あたり 入力約500トークン＋出力約80トークン。25件で gpt-4o-mini なら
#   合計 約0.005ドル＝**1円未満**。使った実額は gaibu_kuchi 側の台帳に毎回載る。
FALLBACK_VENDORS = ("openai", "gemini", "grok")
# 実測（2026-09-22 07:00・1回目）：既定の先頭 gpt-4o-mini に書かせたら12件中ほぼ全部が
#   「〜しよう！」の呼びかけになり、1件は材料に無い匂いまで足した（嘘）。**安い方から
#   順に試す既定のままでは、この棚の文は書けない。**賢い方を先頭に指名する。
#   値段差：1件あたり0.013円→約0.06円。25件で1.5円。ここは値段より文の質を採る。
FALLBACK_MODELS = {"openai": ["gpt-5-mini", "gpt-4o", "gpt-4o-mini"]}


def ask_fallback(title, copy, url, diag):
    """claude -p が使えない日の控えの書き手。通らなければ (None, 理由) を返す。"""
    try:
        import gaibu_kuchi as kuchi
    except Exception as e:
        return None, "控えの口が読み込めない（%s）" % type(e).__name__
    prompt = PROMPT % {"title": title or "（題名なし）",
                       "copy": copy or "（まだ無い）",
                       "url": url or "（無い）"}
    tried = []
    for v in FALLBACK_VENDORS:
        try:
            if not kuchi.find_key(v):
                tried.append("%s=鍵なし" % v)
                continue
            r = kuchi.ask(v, [{"role": "user", "content": prompt}], timeout=60,
                          models=FALLBACK_MODELS.get(v))
        except Exception as e:
            tried.append("%s=%s" % (v, type(e).__name__))
            continue
        if r.get("ok") and r.get("text"):
            diag.append("控えの口 %s／%s／%s円" % (v, r.get("model"), r.get("costYen")))
            t = clean(r["text"])
            if t and "NO_MATERIAL" not in t:
                return t, None
            if "NO_MATERIAL" in (t or ""):
                return None, "材料が題名だけで、足さずには書けない（動画を見ないと書けない）"
            tried.append("%s=空" % v)
        else:
            tried.append("%s=%s" % (v, (r.get("error") or "不明")[:60]))
    return None, "控えの口も通らなかった（%s）" % "／".join(tried)


def write_probe(url, key, row_id, current, diag):
    """**書ける鍵かどうかを、書き直す前に1回だけ確かめる。**

    実測で一番こわいのは「コピーは全部作ったのに、書き戻しが RLS で弾かれて0件」。
    今の値をそのまま入れ直すだけなので、中身は1文字も変わらない。
    """
    try:
        _rep, st = patch_copy(url, key, row_id, current)
        diag.append("書き戻しの下見：HTTP %s（書ける）" % st)
        return True, None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:160]
        except Exception:
            pass
        return False, "書き戻しが HTTP %d で弾かれる（鍵が読み取り専用の可能性）%s" % (e.code, body)
    except Exception as e:
        return False, "書き戻しの下見が通らない（%s）" % type(e).__name__


def patch_copy(url, key, row_id, text):
    """admin_stock の whisper だけを1件ずつ書き戻す。丸ごと一括更新はしない。"""
    q = urllib.parse.urlencode({"id": "eq." + str(row_id)})
    body = json.dumps({"whisper": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url + "/rest/v1/admin_stock?" + q, data=body, method="PATCH",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8") or "[]"), r.status


def patch_title(url, key, row_id, text):
    """admin_stock の title だけを1件ずつ書き戻す。丸ごと一括更新はしない。
    ★題名を触るのはここだけ。手書きの下書きに title が入っていたときしか呼ばない。"""
    q = urllib.parse.urlencode({"id": "eq." + str(row_id)})
    body = json.dumps({"title": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url + "/rest/v1/admin_stock?" + q, data=body, method="PATCH",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8") or "[]"), r.status


def load_tegaki():
    """手書きの下書きを読む。{id: {"whisper":..., "title":..., "by":..., "path":...}}

    ★読むだけ。ここでは消さない（書き戻しが通ってから retire_tegaki で片づける）。
    """
    out = {}
    if not os.path.isdir(TEGAKI_DIR):
        return out
    for fn in sorted(os.listdir(TEGAKI_DIR)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(TEGAKI_DIR, fn)
        try:
            with io.open(p, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        rid = str(d.get("id") or "").strip()
        if not rid:
            continue
        d["path"] = p
        out[rid] = d
    return out


def retire_tegaki(d):
    """使い終わった下書きを done/ へ移す。**消さない**（戻せる形で残す）。"""
    try:
        os.makedirs(TEGAKI_DONE, exist_ok=True)
        src = d.get("path")
        if src and os.path.exists(src):
            os.replace(src, os.path.join(TEGAKI_DONE, os.path.basename(src)))
    except Exception:
        pass


def find_write_key(diag):
    """**書ける鍵**を探す。数える係は「読めればいい」ので最初に見つかった鍵で止まるが、
    こちらは書き戻すので、置き場を全部見てから一番強い鍵を採る。

    実測：数える係が拾っていたのは SUPABASE_PUBLISHABLE_KEY（読み取り用）。
    RLS が効いていれば PATCH は 401/403 で弾かれる。弾かれたらその番号を
    そのまま一覧に残す（嘘のログを書かない）。値はここから一歩も外へ出さない。
    """
    url, key, keyname, where = nippou.find_supabase(diag)
    if not url:
        return None, None, None, where
    best = (key, keyname, where, 5)

    # ★1041番：たまごさんが画面から貼った service_role の鍵は、公開リポジトリの外
    #   （~/.tamago/supabase_service_role・権限600・git管理外）に置く。
    #   在れば一番強い鍵として採る。値はここから一歩も外へ出さない。
    _kp = os.path.expanduser("~/.tamago/supabase_service_role")
    if os.path.exists(_kp):
        try:
            _v = io.open(_kp, encoding="utf-8").read().strip()
        except Exception:
            _v = ""
        if _v:
            diag.append("~/.tamago/supabase_service_role あり（貼られた鍵を使う）")
            best = (_v, "SUPABASE_SERVICE_ROLE_KEY", "~/.tamago/supabase_service_role", -1)

    rank = {"SERVICE_ROLE": 0, "SERVICE": 1, "SECRET": 2, "PUBLISHABLE": 4, "ANON": 4}
    for rel in nippou.ENV_RELS:
        p = os.path.join(nippou.JRS, rel)
        if not os.path.exists(p):
            continue
        env = nippou.read_env_names(p)
        for k, v in env.items():
            ku = k.upper()
            if "SUPABASE" not in ku or not v:
                continue
            r = next((sc for pref, sc in rank.items() if pref in ku), 5)
            if r < best[3]:
                best = (v, k, rel, r)
    diag.append("書き戻しに使う鍵：%s（%s）" % (best[1], best[2]))
    return url, best[0], best[1], best[2]


def pick_targets(url, key, diag, since_days):
    """昨日ぶん＋溜まっているぶんから、手つかずのものを新しい順に拾う。人は選ばない。"""
    now = datetime.now(JST)
    since = (now - timedelta(days=since_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = nippou.fetch_stock(url, key, since.isoformat())
    targets = []
    for r in rows:
        if not isinstance(r, dict) or r.get("deleted_at"):
            continue
        title = nippou.pick(r, ["title", "name", "song_title"])
        copy = nippou.pick(r, ["whisper", "copy", "lead"])
        link = nippou.pick(r, ["url", "source_url", "link", "youtube_url", "ref"])
        kind = nippou.pick(r, ["kind"])
        if link and not link.startswith("http"):
            link = ("https://youtu.be/" + link) if kind == "youtube" else ""
        why = nippou.judge(title, copy)
        if not why:
            continue
        created = nippou.pick(r, ["created_at", "createdAt", "inserted_at"])
        targets.append({"id": r.get("id"), "date": (created or "")[:10],
                        "title": title, "copy": copy, "url": link,
                        "kind": kind, "why": why})
    targets.sort(key=lambda t: t["date"], reverse=True)
    diag.append("手つかず %d件を拾った（直近%d日）" % (len(targets), since_days))
    return targets


def run(since_days=14):
    now = datetime.now(JST)
    prev = load(OUT_JSON, {}) or {}
    out = {
        "generatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "ranAt": now.isoformat(),
        "runs": int((prev.get("runs") or 0)) + 1,       # 走った回数（累計）
        "fixedTotal": int((prev.get("fixedTotal") or 0)),
        "targets": 0, "fixed": 0, "skipped": 0,
        "changes": [],     # 今回の前後
        "skips": [],       # できなかったものと、その理由（そのまま残す）
        "red": [],
        "diag": [],
        "history": (prev.get("history") or [])[:HISTORY_KEEP],
        # ★1049番：手書きの下書きから直した分。題名を直したものは別に数える。
        "titleFixed": 0,
        "titleChanges": [],
        "byHand": 0,
        "tegakiWaiting": 0,
    }
    diag = out["diag"]
    tegaki = load_tegaki()
    out["tegakiWaiting"] = len(tegaki)
    if tegaki:
        diag.append("手書きの下書きが %d件 置いてある（AIを呼ばずにこちらを採る）" % len(tegaki))

    url, key, keyname, where = find_write_key(diag)
    if not url:
        out["red"].append("正本（admin_stock）に手が届かない：" + where)
        return out
    out["sourceNote"] = "admin_stock（鍵：%s・%s）" % (keyname, where)

    try:
        targets = pick_targets(url, key, diag, since_days)
    except urllib.error.HTTPError as e:
        out["red"].append("admin_stock が HTTP %d（鍵は在るが通らない）" % e.code)
        return out
    except Exception as e:
        out["red"].append("admin_stock に繋がらない（%s）" % type(e).__name__)
        return out

    out["targets"] = len(targets)
    log("対象 %d件（今回は最大%d件まで直す）" % (len(targets), MAX_PER_RUN))

    # 書き直す前に、書き戻せる鍵かどうかを1回だけ確かめる（中身は変えない下見）。
    # ここで弾かれるなら、コピーを25本作っても1本も載らない。先に赤にする。
    if targets:
        p = targets[0]
        ok, why = write_probe(url, key, p["id"], p["copy"], diag)
        out["canWrite"] = ok
        if not ok:
            out["red"].append("書き戻せない：" + why)
            log("書き戻しの下見で弾かれた：" + why)
            out["skipped"] = 0
            out["remaining"] = len(targets)
            out["redCount"] = len(out["red"])
            return out

    t0 = time.time()
    for i, t in enumerate(targets[:MAX_PER_RUN], 1):
        if time.time() - t0 > DEADLINE_SEC:
            # Macを何十分も占有しない。**残ったことを隠さない。**次の回が続きから拾う。
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "この回の持ち時間（%d分）を使い切った。次の回で続きをやる"
                                           % (DEADLINE_SEC // 60)})
            log("持ち時間切れ。%d件目以降は次の回へ" % i)
            break
        log("  %d/%d %s" % (i, min(len(targets), MAX_PER_RUN), (t["title"] or "")[:40]))

        # ── 手書きの下書きがあれば、AIを呼ばずにそれを採る（1049番） ──────────
        #    題名も入っていれば題名から先に直す。題名が英語のままだと、
        #    コピーを何回書き直しても判定は題名で落ちる＝永久に片づかないため。
        hand = tegaki.get(str(t["id"]))
        judge_title = t["title"]
        if hand:
            new_title = str(hand.get("title") or "").strip()
            if new_title and new_title != (t["title"] or ""):
                try:
                    _rep, st_t = patch_title(url, key, t["id"], new_title)
                    out["titleFixed"] = out.get("titleFixed", 0) + 1
                    out["titleChanges"].append(
                        {"id": t["id"], "was": t["title"], "now": new_title,
                         "at": now.strftime("%Y-%m-%d %H:%M"), "http": st_t,
                         "by": hand.get("by") or "手書き"})
                    judge_title = new_title
                except Exception as e:
                    out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                         "was": t["copy"], "why": t["why"],
                                         "reason": "題名を書き戻せなかった（%s）" % type(e).__name__,
                                         "draft": new_title})
                    continue
            text, why_ng = str(hand.get("whisper") or "").strip(), None
            if not text:
                why_ng = "手書きの下書きに whisper が入っていない"
        else:
            text, why_ng = ask_claude(t["title"], t["copy"], t["url"], diag)
        if not text:
            # 書き手が1人だとその1人が寝た日に0件になる。控えの口へ降りる。
            text2, why2 = ask_fallback(t["title"], t["copy"], t["url"], diag)
            if text2:
                text, why_ng = text2, None
            else:
                why_ng = "%s／控え：%s" % (why_ng, why2)
        if not text:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"], "reason": why_ng})
            continue
        # 書き直したものを**同じ判定にもう一度かける。**水道水のままなら書き戻さない。
        # ★手書きの下書きも素通りさせない。同じ関所を通す。
        again = nippou.judge(judge_title, text)
        if again and hand:
            # 手書きが落ちたら、AIで上書きしない。落ちた理由をそのまま残す（黙って捨てない）。
            out["skips"].append({"id": t["id"], "date": t["date"], "title": judge_title,
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "手書きの下書きが判定で落ちた（%s）：%s" % (again, text),
                                 "draft": text})
            continue
        if again:
            # 1回だけ、どこが引っかかったかを伝えて書き直させる（黙って捨てない）
            t2 = dict(t)
            t2["copy"] = (t["copy"] or "") + "\n（直前に書いた案「%s」は %s で不合格でした。" \
                                             "同じ手は使わないでください）" % (text, again)
            text2, _ = ask_fallback(t["title"], t2["copy"], t["url"], diag)
            if text2 and not nippou.judge(t["title"], text2):
                text, again = text2, None
        if again:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き直したがまだ水道水（%s）：%s" % (again, text)})
            continue
        try:
            _rep, st = patch_copy(url, key, t["id"], text)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き戻しが HTTP %d（%s）" % (e.code, body),
                                 "draft": text})
            continue
        except Exception as e:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き戻せない（%s）" % type(e).__name__,
                                 "draft": text})
            continue
        ch = {"id": t["id"], "date": t["date"], "title": judge_title,
              "was": t["copy"], "now": text, "why": t["why"],
              "url": t["url"], "at": now.strftime("%Y-%m-%d %H:%M"), "http": st,
              "by": (hand.get("by") or "手書き") if hand else "機械"}
        out["changes"].append(ch)
        out["fixed"] += 1
        if hand:
            out["byHand"] += 1
            retire_tegaki(hand)

    # ★置いたのに一度も呼ばれなかった手書きを、黙って飲み込まない（1049番）。
    #   直近 since_days 日から外れた行は pick_targets に出てこないので、
    #   下書きだけが置き場で永久に待つ事故が起きる。数えて理由ごと出す。
    picked = {str(t["id"]) for t in targets}
    orphan = [k for k in tegaki if k not in picked]
    if orphan:
        out["tegakiOrphan"] = orphan
        out["red"].append(
            "手書きの下書きが%d件、正本の手つかず一覧に出てこない"
            "（直近%d日から外れた／既に直っている／idが違う のどれか）" % (len(orphan), since_days))

    out["skipped"] = len(out["skips"])
    out["fixedTotal"] += out["fixed"]
    out["history"] = (out["changes"] + out["history"])[:HISTORY_KEEP]
    out["remaining"] = max(0, out["targets"] - out["fixed"])

    # 赤の決まり（たまごさん 2026-09-22 指定）
    # 「走った>0 なのに 直した=0」＝動いているのに何も取れていない。一番たちの悪い壊れ方。
    if out["targets"] > 0 and out["fixed"] == 0:
        out["red"].append("走ったのに1件も直っていない（対象%d件・理由は下の一覧）" % out["targets"])
    if out["skips"]:
        out["red"].append("直せなかったものが%d件（理由つきで下に出している）" % len(out["skips"]))
    out["redCount"] = len(out["red"])
    return out


def main():
    argv = sys.argv[1:]
    force = ("--force" in argv) or os.environ.get("NAOSHI_FORCE") == "1"
    if os.path.exists(FORCE):
        force = True
        try:
            os.remove(FORCE)
        except Exception:
            pass
    now = datetime.now(JST)
    if not force:
        # 1日1回。朝6時以降の最初の便で走る。
        if now.hour < MORNING_HOUR:
            return
        if os.path.exists(GATE):
            try:
                last = io.open(GATE, encoding="utf-8").read().strip()[:10]
            except Exception:
                last = ""
            if last == now.strftime("%Y-%m-%d"):
                return
    if not take_lock():
        log("前の回がまだ走っているので見送り")
        return
    log("開始（force=%s）" % force)
    try:
        try:
            out = run()
        except Exception as e:
            # 落ちたことを**隠さない。**次の回が同じところで落ちるかどうかも分かる形で残す。
            import traceback
            log("落ちた：%s %s" % (type(e).__name__, e))
            log(traceback.format_exc()[-800:])
            prev = load(OUT_JSON, {}) or {}
            out = {"generatedAt": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
                   "runs": int(prev.get("runs") or 0) + 1,
                   "fixedTotal": int(prev.get("fixedTotal") or 0),
                   "targets": 0, "fixed": 0, "skipped": 0,
                   "changes": [], "skips": [],
                   "history": (prev.get("history") or [])[:HISTORY_KEEP],
                   "red": ["直す係が途中で落ちた（%s: %s）" % (type(e).__name__, e)],
                   "redCount": 1, "diag": []}
        save(OUT_JSON, out)
        log("終わり：対象%s 直した%s 直せず%s" % (out.get("targets"), out.get("fixed"),
                                             out.get("skipped")))
        try:
            with io.open(GATE, "w", encoding="utf-8") as f:
                f.write(now.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            pass  # 印が書けなくても直した事実は残す（止まらない）
        # 直した直後に「数える係」を回し直して、1枚の数字をその場で合わせる。
        try:
            with io.open(os.path.join(STATUS, ".gaibu_copy_nippou_force"),
                         "w", encoding="utf-8") as f:
                f.write(now.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            pass
    finally:
        drop_lock()


if __name__ == "__main__":
    main()
