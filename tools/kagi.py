#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1132番：鍵の唯一の読み口。**これ以外の場所から鍵を読むコードを書かない。**

たまごさん（2026-09-24）：
  「やり方統一しよう。そのやり方でやったことないよ。毎回バラバラは嫌ですよ。」

原因は、鍵の読み先が tools/ の中で3か所に散らばっていたこと：
    ~/.tamago/keys/api_keys.env   （20か所がここを見ていた）
    ~/Documents/AI作業/_鍵/keys.env（3か所）
    ~/.env                         （2か所）
どれを正しいと言うかがコードによって違えば、頼む言葉も毎回変わる。だから1本にする。

------------------------------------------------------------------
決めたこと（これが正本。他は読むだけの予備）
------------------------------------------------------------------
    正本 ＝ ~/.tamago/keys/api_keys.env
    形   ＝ KEY=値 を1行ずつ。引用符もexportも要らない（書いてあっても読める）

------------------------------------------------------------------
名前の言い間違いを吸収する（★これが「毎回違う」の実害を止める本体）
------------------------------------------------------------------
    たまごさんに BUFFER_TOKEN= と伝えた便と、
    コードが BUFFER_ACCESS_TOKEN を読んでいた便があった。
    どちらで書いても通るようにする。以後、名前の揺れは ALIAS に足すだけで済む。

------------------------------------------------------------------
使い方
------------------------------------------------------------------
    from kagi import get, need           # tools/ の中から
    tok = get("BUFFER_ACCESS_TOKEN")     # 無ければ None
    tok = need("BUFFER_ACCESS_TOKEN")     # 無ければ分かりやすく落ちる

    python3 tools/kagi.py --list         # 名前と置き場だけ出す（値は出さない）
    python3 tools/kagi.py --migrate      # 予備にしか無い鍵を正本へ写す（元は消さない）

★値は返り値としてしか外に出さない。print・ログ・例外文に1文字も書かない。
"""
import io
import os
import stat
import sys

HOME = os.path.expanduser("~")

# 正本。ここが唯一の「置き場」。
SEIHON = os.path.join(HOME, ".tamago", "keys", "api_keys.env")

# 予備（読むだけ。過去の便が置いた場所。消さない）。上から順に、最初に見つけたものを使う。
YOBI = [
    os.path.join(HOME, "Documents", "AI作業", "_鍵", "keys.env"),
    os.path.join(HOME, "Documents", "AI作業", "_鍵", ".env"),
    os.path.join(HOME, ".env"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    os.path.join(HOME, "Desktop", "joy-relief-station", ".env.local"),
    os.path.join(HOME, "Desktop", "joy-relief-station", ".env"),
]
# ~/.zshrc は入れない（1132番の実測で中身は PATH と BUN_INSTALL だけ。鍵は無い）。

# 鍵ではないもの。正本へ写さない（PATH を正本に書き込む事故を形で止める）。
KAGI_DEWA_NAI = {"PATH", "BUN_INSTALL", "LANG", "LC_ALL", "EDITOR", "SHELL",
                 "HOME", "TERM", "NODE_ENV", "PYTHONPATH"}

# 他のツールが「見る場所の一覧」として使うもの。★自分でリストを書かない。ここを import する。
ALL_FILES = [SEIHON] + YOBI

# 名前の揺れ。左＝コードが呼ぶ名前 / 右＝同じ意味で書かれうる名前。
ALIAS = {
    "BUFFER_ACCESS_TOKEN": ["BUFFER_TOKEN", "BUFFER_KEY", "BUFFER_API_TOKEN"],
    "OPENAI_API_KEY": ["OPENAI_KEY", "CHATGPT_API_KEY"],
    "XAI_API_KEY": ["XAI_API_KEY2", "GROK_API_KEY"],
    "YOUTUBE_DATA_API_KEY": ["YOUTUBE_API_KEY", "YT_API_KEY"],
    "GEMINI_API_KEY": ["GOOGLE_AI_API_KEY"],
    "GITHUB_TOKEN": ["GH_TOKEN"],
    "DEVIN_API_KEY": ["DEVIN_TOKEN"],
    "FAL_KEY": ["FAL_API_KEY"],
    "GUMROAD_ACCESS_TOKEN": ["GUMROAD_TOKEN"],
}


def _parse(path):
    """KEY=値 を読む。export・引用符・コメントを許す。壊れた行は黙って飛ばす。"""
    out = {}
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                if ln.startswith("export "):
                    ln = ln[7:].strip()
                if "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                k = k.strip()
                if not k or not k.replace("_", "").isalnum():
                    continue
                v = v.strip().strip('"').strip("'")
                if v:
                    out[k] = v
    except Exception:
        pass
    return out


def _names(name):
    """探す名前の順番。正式名 → 別名 → 逆引き（別名で呼ばれたら正式名も見る）。"""
    seen, order = set(), []
    for n in [name] + ALIAS.get(name, []):
        if n not in seen:
            seen.add(n)
            order.append(n)
    for seishiki, aliases in ALIAS.items():
        if name in aliases and seishiki not in seen:
            seen.add(seishiki)
            order.append(seishiki)
    return order


def where(name):
    """どこにあるかだけを返す（値は返さない）。無ければ None。"""
    for path in [SEIHON] + YOBI:
        d = _parse(path)
        for n in _names(name):
            if d.get(n):
                return path, n
    return None


def get(name, default=None):
    """鍵の値。正本 → 予備 → 環境変数 の順に探す。無ければ default。"""
    for path in [SEIHON] + YOBI:
        d = _parse(path)
        for n in _names(name):
            v = d.get(n)
            if v:
                return v
    for n in _names(name):
        v = os.environ.get(n)
        if v:
            return v
    return default


def need(name):
    """無いと進めないとき。★値は例外文に出さない。"""
    v = get(name)
    if not v:
        raise SystemExit(
            "鍵【%s】がありません。置き場はここだけです：\n"
            "  %s\n"
            "  この1行を足してください： %s=（値）\n"
            "  （%s でも読めます）"
            % (name, SEIHON.replace(HOME, "~"), name,
               " / ".join(ALIAS.get(name, [])) or "別名なし"))
    return v


def put(name, value):
    """正本に書く。既にあれば差し替え。★.tmp は固定名にしない（既知の地雷）。"""
    os.makedirs(os.path.dirname(SEIHON), exist_ok=True)
    lines = []
    if os.path.exists(SEIHON):
        lines = io.open(SEIHON, encoding="utf-8").read().splitlines()
    out, done = [], False
    for ln in lines:
        if ln.strip().startswith(name + "="):
            out.append("%s=%s" % (name, value))
            done = True
        else:
            out.append(ln)
    if not done:
        out.append("%s=%s" % (name, value))
    tmp = "%s.%d.tmp" % (SEIHON, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, SEIHON)


def _list():
    if not os.path.isdir(os.path.dirname(SEIHON)):
        print("鍵の置き場(~/.tamago/keys)が見えません＝ここはサンドボックスです。判定を書きません。")
        return 3
    honban = sorted(_parse(SEIHON).keys())
    print("■ 正本 %s（%d本）" % (SEIHON.replace(HOME, "~"), len(honban)))
    for k in honban:
        print("    - %s" % k)
    for path in YOBI:
        d = _parse(path)
        if not d:
            continue
        nokori = sorted(k for k in d if k not in honban and k not in KAGI_DEWA_NAI)
        print("■ 予備 %s（%d本 / 正本に無いもの %d本）"
              % (path.replace(HOME, "~"), len(d), len(nokori)))
        for k in nokori:
            print("    ※ %s ← 正本に無い（--migrate で写せる）" % k)
    return 0


def _migrate():
    """予備にしか無い鍵を正本へ写す。★元ファイルは消さない（戻せるように）。"""
    if not os.path.isdir(os.path.dirname(SEIHON)):
        print("鍵の置き場が見えないので何もしません")
        return 3
    honban = _parse(SEIHON)
    utsushita = []
    for path in YOBI:
        for k, v in sorted(_parse(path).items()):
            if k in honban or k in KAGI_DEWA_NAI:
                continue
            put(k, v)
            honban[k] = v
            utsushita.append((k, path.replace(HOME, "~")))
    if not utsushita:
        print("写すものはありませんでした（全部すでに正本にあります）")
    for k, src in utsushita:
        print("写した: %s ← %s（元は消していません）" % (k, src))
    return 0


if __name__ == "__main__":
    if "--migrate" in sys.argv:
        sys.exit(_migrate())
    if "--where" in sys.argv:
        i = sys.argv.index("--where")
        nm = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        w = where(nm)
        print("%s: %s に %s として入っています" % (nm, w[0].replace(HOME, "~"), w[1])
              if w else "%s: どこにもありません" % nm)
        sys.exit(0 if w else 2)
    sys.exit(_list())
