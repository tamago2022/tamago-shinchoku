#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番の関所（2026-11-22 店主「ページを作ったと言うのに、実装・公開されていない」）。

実測（2026-11-22・queue.json）：11/08以降に「完了(done)」になった19件は全部 okBy=ai-verifier-auto。
そのうち13件は urls が GitHub の確認ページ（tamago2022.github.io/.../share/check/*.html）だけ。
鬼監督（AI検品）も oni_modoshi も「URLが200で中身がある」を見ていたが、
確認ページは作った本人が置くページなので、いつでも200で中身がある＝本番の証拠にならなかった。

★ここから先、完了(done)は「本番URLを叩いて中身を確かめた」ときだけ付く。
  本番URL＝確認ページ以外（joy-relief-station.lovable.app のページ／仕組みなら
  github.com/tamago2022/tamago-shinchoku/blob/main/<ファイル> など、main に入った現物）。
  確認ページ・下書き・localhost・ローカルのパスは何本あっても本番の証拠に数えない。

使う所（3か所・どれも done を付ける直前）：
  auto_launcher.py の AI検品PASS → done
  verify_check_pages.py の機械検品PASS → done
  oni_modoshi.py の kenpin()（確認ページだけの報告は不合格）

返り値 hantei(item) → {"ok": True/False/None, "naze": 理由, "url": 確かめたURL}
  True  … 本番で中身を確かめた → done にしてよい
  False … 本番URLが無い／200でない／中身が空／目印が無い → done にしない（作り直し）
  None  … 外に出られない（サンドボックス等）→ 判定しない。done にもしない（あとで測り直す）

item に "honbanMejirushi": ["文字", ...] があれば、本番の本文にその文字が全部あるかも見る。

  python3 tools/honban_kanmon.py --n 35714      # 1件だけ判定（読むだけ・台帳は変えない）
  python3 tools/honban_kanmon.py --show         # 直近の判定の記録
  python3 tools/honban_kanmon.py --self-test
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DIR = os.path.join(ST, "honban_kanmon")
KIROKU = os.path.join(DIR, "kiroku.jsonl")
PUBLIC = os.path.join(ST, "public", "honban_kanmon.json")

_URL = re.compile(r"https?://[^\s\"'<>）)、。」』\]（\[]+")
# 本番の証拠に数えないURL（作った本人がいつでも置ける場所・見られない場所）
KAKUNIN = re.compile(
    r"(tamago2022\.github\.io/tamago-shinchoku/(share|status|lab|out)/"
    r"|/share/check/|gist\.github|localhost|127\.0\.0\.1|0\.0\.0\.0|^file:"
    r"|raw\.githubusercontent\.com/[^/]+/[^/]+/(?!main/)"   # main 以外の枝
    r"|github\.com/[^/]+/[^/]+/(pull|compare|tree/(?!main)|blob/(?!main))"
    r"|/sessions/|preview--|lovableproject\.com|id-preview)", re.I)
CODE_URL = re.compile(r"github\.com/[^/]+/[^/]+/blob/main/", re.I)
TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
KARA = re.compile(r"(準備中|coming soon|工事中|Not Found|ページがありません|ページが見つかりません|"
                  r"この内容はまだありません|準備しています)", re.I)
NAKAMI_SAITEI = 300
HON_KEYS = ("result", "report", "evidence", "note", "honbanUrl")


def urls_of(item):
    out, seen = [], set()
    for u in item.get("urls") or []:
        if isinstance(u, str):
            seen.add(u)
            out.append(u)
    for k in HON_KEYS:          # ★"what"（元の依頼・過去の差し戻し文）は証拠に数えない
        for u in _URL.findall(str(item.get(k) or "")):
            u = u.rstrip(".,)）」』")
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


FILE_MENTION = re.compile(r"(?<![\w/.-])((?:tools|docs|\.githooks|\.claude)/[\w/.\-]+\.(?:py|mjs|js|sh|json|md|ts)"
                          r"|CLAUDE\.md|AGENTS\.md|README\.md)")
GH = "https://github.com/tamago2022/tamago-shinchoku/blob/main/"
# サイト（ごきげん補給所）の仕事か。そうなら本番ページ（lovable.app）のURLが必須
SITE_WORDS = re.compile(r"曲ページ|アーティストページ|マガジン|特集|棚|ごきげん補給所|名カバー|"
                        r"joy-relief-station|lovable|cover-guide|/feature/|/magazine/")


def main_ni_aru(path, repo=REPO):
    """そのファイルが origin/main に入っているか（push済みか）。入っていなければ本番の証拠にしない。"""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", repo, "cat-file", "-e", "origin/main:%s" % path],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def shikumi_urls(item, aru=None):
    """仕組みの仕事：報告に書かれた tools/… が main に入っていれば、その GitHub のURLを本番の証拠にする。"""
    aru = aru or main_ni_aru
    out = []
    txt = " ".join(str(item.get(k) or "") for k in HON_KEYS)
    for p in dict.fromkeys(FILE_MENTION.findall(txt)):
        if len(out) >= 3:
            break
        if aru(p):
            out.append(GH + p)
    return out


def honban_urls(item):
    return [u for u in urls_of(item) if not KAKUNIN.search(u)]


def tataku(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "honban-kanmon/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read(600000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def soto_ni_derareru(fetch=None):
    fetch = fetch or tataku
    for u in ("https://www.google.com/generate_204", "https://github.com/"):
        code, _ = fetch(u)
        if code is not None:
            return True
    return False


def chimon(body):
    t = TAG.sub(" ", body or "")
    return re.sub(r"\s+", " ", t).strip()


def hantei(item, fetch=None, aru=None):
    fetch = fetch or tataku
    allu = urls_of(item)
    hon = [u for u in allu if not KAKUNIN.search(u)]
    if not any(not CODE_URL.search(u) for u in hon):
        # 本番のページが無い＝仕組みの仕事かもしれない。main に入ったファイルを証拠に足す
        for u in shikumi_urls(item, aru):
            if u not in hon:
                hon.append(u)
    if hon and all(CODE_URL.search(u) for u in hon) and SITE_WORDS.search(
            (item.get("title") or "") + " " + (item.get("what") or "")[:600]):
        return {"ok": False, "url": hon[0],
                "naze": "サイトの仕事なのに本番ページのURLが無い（コードがmainに入っただけでは公開の証拠にならない）"}
    if not hon:
        if allu:
            return {"ok": False, "url": None,
                    "naze": "報告のURLが確認ページ等だけで、本番URLが無い（%d本とも本番の証拠に数えない）" % len(allu)}
        return {"ok": False, "url": None, "naze": "報告に本番URLが1本も無い"}
    if not soto_ni_derareru(fetch):
        return {"ok": None, "url": hon[0], "naze": "外に出られないので判定しない（doneにもしない）"}
    mejirushi = [m for m in (item.get("honbanMejirushi") or []) if isinstance(m, str) and m.strip()]
    nokori = set(mejirushi)
    mita = None
    for u in hon[:3]:
        code, body = fetch(u)
        if code is None:      # 回線の手前で落ちた＝本番の良し悪しは分からない。doneにもしないし戻しもしない
            return {"ok": None, "url": u, "naze": "本番URLに届かない（%s）" % (body or "")[:80]}
        if code != 200:
            return {"ok": False, "url": u, "naze": "本番URLが200で返らない（%s）" % code}
        if not CODE_URL.search(u):
            t = chimon(body)
            if len(t) < NAKAMI_SAITEI:
                return {"ok": False, "url": u, "naze": "本番の本文が%d文字しかない（最低%d）" % (len(t), NAKAMI_SAITEI)}
            m = KARA.search(t[:3000])
            if m:
                return {"ok": False, "url": u, "naze": "本番に「%s」が出ている" % m.group(0)}
        for m in list(nokori):
            if m in (body or ""):
                nokori.discard(m)
        mita = mita or u
    if nokori:
        return {"ok": False, "url": mita, "naze": "本番に目印が無い：%s" % "／".join(sorted(nokori))[:200]}
    return {"ok": True, "url": mita, "naze": "本番で中身を確かめた（%d本）" % min(len(hon), 3)}


def kiroku(item, res, doko):
    try:
        os.makedirs(DIR, exist_ok=True)
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"), "doko": doko, "n": item.get("n"),
               "title": (item.get("title") or "")[:80], "ok": res.get("ok"), "url": res.get("url"),
               "naze": res.get("naze")}
        with io.open(KIROKU, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if os.path.getsize(KIROKU) > 1000000:      # 使ったらしまう：1MBを超えたら直近2000行だけ残す
            keep = _rows(2000)
            with io.open(KIROKU, "w", encoding="utf-8") as f:
                for r in keep:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        _public()
    except Exception:
        pass


def _rows(limit=2000):
    try:
        with io.open(KIROKU, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except Exception:
        return []
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def _public():
    rows = _rows()
    d = {"updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
         "what": "完了(done)は本番URLで中身を確かめたときだけ。tools/honban_kanmon.py",
         "tooshita": sum(1 for r in rows if r.get("ok") is True),
         "modoshita": sum(1 for r in rows if r.get("ok") is False),
         "hakarenai": sum(1 for r in rows if r.get("ok") is None),
         "saikin": rows[-20:][::-1]}
    tmp = PUBLIC + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PUBLIC)


def modosu_bun(res):
    """作り直しの指示文（what に足す）。"""
    return ("\n\n【本番の関所で戻されました・%s】理由：%s。\n"
            "★完了は本番で中身を確かめたときだけ付きます。確認ページ（share/check）は本番の証拠に数えません。\n"
            "サイトの変更なら：push → 公開（deploy_project）→ joy-relief-station.lovable.app の該当URLを result に書く。\n"
            "仕組みの変更なら：main に入れて github.com/tamago2022/tamago-shinchoku/blob/main/<ファイル> を result に書く。\n"
            "本番の本文に必ず出る文字があれば honbanMejirushi に入れる（関所がその文字を探す）。"
            % (time.strftime("%m-%d %H:%M"), res.get("naze")))


def _self_test():
    ok = 0
    ng = []

    def fake(table):
        def f(u):
            if "generate_204" in u or u == "https://github.com/":
                return (204, "") if table.get("_net", True) else (None, "x")
            return table.get(u, (404, ""))
        return f
    page = "<html><body>" + ("ごきげん補給所 Treasure Bruno Mars の曲ページ。" * 20) + "</body></html>"
    cases = [
        ("確認ページだけ→不合格",
         {"urls": ["https://tamago2022.github.io/tamago-shinchoku/share/check/1-a.html"]}, {}, False),
        ("URL無し→不合格", {"result": "やりました"}, {}, False),
        ("本番200で中身あり→合格",
         {"result": "本番 https://joy-relief-station.lovable.app/cover-guide?artist=x&song=y"},
         {"https://joy-relief-station.lovable.app/cover-guide?artist=x&song=y": (200, page)}, True),
        ("本番404→不合格",
         {"urls": ["https://joy-relief-station.lovable.app/magazine/nai.html"]}, {}, False),
        ("本番が殻→不合格",
         {"urls": ["https://joy-relief-station.lovable.app/a"]},
         {"https://joy-relief-station.lovable.app/a": (200, "<div id=root></div>")}, False),
        ("目印が無い→不合格",
         {"urls": ["https://joy-relief-station.lovable.app/b"], "honbanMejirushi": ["存在しない言葉"]},
         {"https://joy-relief-station.lovable.app/b": (200, page)}, False),
        ("目印あり→合格",
         {"urls": ["https://joy-relief-station.lovable.app/b"], "honbanMejirushi": ["Treasure"]},
         {"https://joy-relief-station.lovable.app/b": (200, page)}, True),
        ("main のコード→合格",
         {"result": "https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/honban_kanmon.py"},
         {"https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/honban_kanmon.py": (200, "x")}, True),
        ("枝のコード→不合格",
         {"result": "https://github.com/tamago2022/tamago-shinchoku/blob/work-1/tools/a.py"}, {}, False),
        ("what の中のURLは数えない",
         {"what": "https://joy-relief-station.lovable.app/b", "urls": []},
         {"https://joy-relief-station.lovable.app/b": (200, page)}, False),
        ("外に出られない→判定しない",
         {"urls": ["https://joy-relief-station.lovable.app/b"]}, {"_net": False}, None),
        ("仕組み：確認ページ＋mainに入ったtools→合格",
         {"title": "判定日赤｜止まらない", "urls": ["https://tamago2022.github.io/tamago-shinchoku/share/check/9.html"],
          "result": "tools/okoshi.py を直した"},
         {GH + "tools/okoshi.py": (200, "x"), "_aru": True}, True),
        ("仕組み：mainに入っていない→不合格",
         {"title": "判定日赤｜止まらない", "result": "tools/okoshi.py を直した"},
         {GH + "tools/okoshi.py": (200, "x"), "_aru": False}, False),
        ("サイトの仕事でコードだけ→不合格",
         {"title": "マガジンの曲ページを直す", "result": "tools/magazine/mag_build.py を直した"},
         {GH + "tools/magazine/mag_build.py": (200, "x"), "_aru": True}, False),
    ]
    for name, item, table, want in cases:
        _a = table.get("_aru", False)
        got = hantei(item, fetch=fake(table), aru=lambda p, _a=_a: _a)["ok"]
        if got is want:
            ok += 1
        else:
            ng.append("%s：期待%s 実際%s" % (name, want, got))
    print("honban_kanmon self-test: %d/%d" % (ok, len(cases)))
    for n in ng:
        print("  NG", n)
    return 0 if not ng else 1


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    if "--show" in argv:
        for r in _rows(30):
            print(r.get("ts"), r.get("doko"), r.get("n"), r.get("ok"), r.get("naze"))
        return 0
    if "--n" in argv:
        n = argv[argv.index("--n") + 1]
        q = json.load(io.open(os.path.join(ST, "queue.json"), encoding="utf-8"))
        for it in q.get("items") or []:
            if str(it.get("n")) == str(n):
                print(json.dumps(hantei(it), ensure_ascii=False))
                return 0
        print("見つからない")
        return 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
