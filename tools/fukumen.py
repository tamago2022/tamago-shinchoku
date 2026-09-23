#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1029番【覆面調査員】たまごさんの代わりに、本番のごきげん補給所をひたすら触る係。

■ たまごさんの言葉（そのまま）
  「覆面テストだったり実機テストだったり、架空のお客さん役でひたすら触ってくれる人がほしい。
    俺は3万ページ全部は見られないわけじゃん。潜伏してひたすら触ってくれる人がいれば、
    どこを直してどうすればもっと体験が良くなるか分かるんじゃないの？」

■ ★この道具の一番大事な考え方：たまごさんの3つの症状は「感想」ではなく「数字」である
  1.「入力してるときに落ちる」
     → 1文字ずつ打ちながら (a)入力欄が作り直された回数 (b)フォーカスが外れた回数
       (c)打った字が消えた回数 (d)画面の要素が差し替わった回数 (e)console error を数える。
       ★「落ちる」の正体はたいてい「1文字打つたびに画面ごと作り直している」こと。
  2.「読んでる途中で画面がすぐ切り替わっちゃう」
     → CLS（Cumulative Layout Shift）。Web Vitalsの標準指標で、PerformanceObserver の
       'layout-shift' でそのまま取れる。0.1以下が良・0.25超が悪。どの要素がずれたかまで取る。
  3.「URL貼っても落ちる」「重い」
     → LCP / INP / 長いタスク(50ms超)の数 / リクエスト数・転送バイト数。

  ★この3つは1円もかからず、AIを1回も呼ばずに測れる。AIの感想は1つも使っていない。

■ 架空のお客さん（ペルソナ）4人
  ① 初めて来た人（1280px）… トップ→棚→曲ページを読む。読んでいる間に画面がずれないか。
  ② スマホの人（375px）  … 同じことを375pxで。たまごさんが何度も指摘している幅。
  ③ 案内人に話しかける人  … 卵コンシェルジュに本物のお客さんの言い方で30問投げる。
  ④ URLを貼る人          … 案内所のURL欄にYouTubeのURLを1文字ずつ貼って登録しようとする。

■ 走らせ方（Mac上。サンドボックスからは外に出られないので必ずMac側で）
  python3 tools/fukumen.py                 # 全部（15分ほど）
  python3 tools/fukumen.py --quick         # 短縮（トップ＋棚1つ＋曲3枚＋案内人8問）
  python3 tools/fukumen.py --only concierge

■ 出るもの
  status/fukumen/<日付>/result.json … その日の全数字（比較用の正本）
  status/fukumen/latest.json        … 最新への近道
  share/check/assets/1029-fukumen/  … 証拠のスクリーンショット（ずれる前／ずれた後）
  ここでは報告HTMLは作らない。作るのは tools/fukumen_report.py（役割を1つにする）。
"""
import argparse
import json
import os
import re
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://joy-relief-station.lovable.app"
# ★撮ったものは全部ここ（gitに乗らない場所）。公開するのは報告に使う数枚だけで、
#   それは tools/fukumen_report.py が軽いJPEGにして share/check/assets/ へ移す。
#   毎日6MBのPNGをgitへ積むと、数週間でこのリポジトリが開けなくなる。
SHOTDIR = os.path.join(ROOT, "status", "fukumen", "shots")
OUTDIR = os.path.join(ROOT, "status", "fukumen")

# ── 測る目盛り（Web Vitals の公式しきい値。ここの数字は勝手に動かさない）──
CLS_GOOD, CLS_BAD = 0.10, 0.25
LCP_GOOD, LCP_BAD = 2500, 4000
INP_GOOD, INP_BAD = 200, 500

# ── ページの中に仕込む観測器（ページのスクリプトより先に走らせる）──────────
INIT_JS = r"""
(() => {
  const F = { cls:0, shifts:[], lcp:0, longtasks:[], inp:0, ready:true };
  window.__fk = F;
  const desc = (el) => {
    try {
      if (!el || !el.tagName) return '(不明)';
      let s = el.tagName.toLowerCase();
      if (el.id) s += '#' + el.id;
      const cn = (typeof el.className === 'string') ? el.className.trim() : '';
      if (cn) s += '.' + cn.split(/\s+/).slice(0, 2).join('.');
      const t = (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 30);
      if (t) s += ' 「' + t + '」';
      return s;
    } catch (e) { return '(不明)'; }
  };
  const rect = (r) => r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null;
  const obs = (type, fn, extra) => {
    try {
      const o = new PerformanceObserver(fn);
      o.observe(Object.assign({ type: type, buffered: true }, extra || {}));
    } catch (e) { }
  };
  obs('layout-shift', (l) => {
    for (const e of l.getEntries()) {
      if (e.hadRecentInput) continue;          // 人が触った直後のズレは数えない（公式の定義）
      F.cls += e.value;
      F.shifts.push({
        t: Math.round(e.startTime), v: +e.value.toFixed(4),
        srcs: (e.sources || []).slice(0, 3).map(s => ({
          el: desc(s.node), from: rect(s.previousRect), to: rect(s.currentRect)
        }))
      });
    }
  });
  obs('largest-contentful-paint', (l) => {
    const es = l.getEntries(); const last = es[es.length - 1];
    if (last) F.lcp = Math.round(last.startTime);
  });
  obs('longtask', (l) => { for (const e of l.getEntries()) F.longtasks.push(Math.round(e.duration)); });
  obs('event', (l) => { for (const e of l.getEntries()) { const d = Math.round(e.duration); if (d > F.inp) F.inp = d; } },
      { durationThreshold: 16 });

  // ── 入力中の見張り。1文字ごとに「入力欄が生きているか」を確かめるために使う ──
  window.__fkWatch = (sel) => {
    const el = document.querySelector(sel);
    const T = { node: el, swaps: 0, blurs: 0, found: !!el };
    window.__fkT = T;
    try {
      const mo = new MutationObserver((ms) => {
        for (const m of ms) {
          if (m.type !== 'childList') continue;
          for (const n of m.removedNodes) if (n.nodeType === 1) T.swaps++;
        }
      });
      mo.observe(document.body, { childList: true, subtree: true });
      T.stop = () => mo.disconnect();
    } catch (e) { }
    document.addEventListener('focusout', () => { T.blurs++; }, true);
    return !!el;
  };
  window.__fkProbe = (sel) => {
    const T = window.__fkT || {};
    const el = document.querySelector(sel);
    return {
      alive: !!el,
      focused: !!el && document.activeElement === el,
      val: el ? String(el.value || '') : null,
      // ★打ち始めの箱がDOMから外れた＝1文字ごとに入力欄ごと作り直している証拠
      rebuilt: !!(T.node && !document.contains(T.node)),
      swaps: T.swaps || 0,
      blurs: T.blurs || 0
    };
  };
})();
"""

# ── 案内人に投げる質問（本物のお客さんの言い方。おじさん、わかってるね を測る）──
QUESTIONS = [
    "泣ける曲ある？", "ドライブで聴くやつ", "90年代っぽいの", "知らない国の音楽が聴きたい",
    "シティポップってなに？", "King Gnu好きなんだけど", "最近入ったやつある？", "作業中に流すやつ",
    "子どもと聴けるの", "元気が出るやつ", "雨の日に合うの", "夜中にひとりで聴くやつ",
    "なんか笑えるやつない？", "ユーミン", "昭和の歌謡曲", "結婚式で流せるの",
    "疲れたときに聴くやつ", "朝起きたときに聴くやつ", "カラオケで歌いやすいの", "掃除がはかどるやつ",
    "親に聴かせたい", "ちょっと泣きたい気分", "тихо", "おすすめある？",
    "ブランデー戦記", "料理しながら聴くやつ", "海が見たくなる曲", "冬の曲",
    "誰も知らないような曲", "ギターがかっこいいやつ", "犬が出てくるやつ", "40代がグッとくるやつ",
]

SHELVES = ["/shelf/music/night", "/shelf/music/covers", "/shelf/food/kattemi-yokatta"]


def log(msg):
    sys.stdout.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stdout.flush()


def slug(url, w):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", url.replace(BASE, "")).strip("-") or "top"
    return "%s-%dpx" % (s[:60], w)


def judge(cls, lcp, inp):
    bad = []
    if cls > CLS_BAD:
        bad.append("cls")
    if lcp > LCP_BAD:
        bad.append("lcp")
    if inp > INP_BAD:
        bad.append("inp")
    return bad


class Shopper(object):
    """1人のお客さん。ブラウザの箱を1つだけ持ち、閉じるまで使い回す（タブを増やさない）。"""

    def __init__(self, pw, width, height, mobile=False, shots=True):
        self.width, self.height, self.shots = width, height, shots
        self.browser = pw.chromium.launch(args=["--disable-dev-shm-usage"])
        kw = {"viewport": {"width": width, "height": height},
              "locale": "ja-JP", "timezone_id": "Asia/Tokyo"}
        if mobile:
            kw["is_mobile"] = True
            kw["has_touch"] = True
            kw["device_scale_factor"] = 2
            kw["user_agent"] = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        self.ctx = self.browser.new_context(**kw)
        self.ctx.add_init_script(INIT_JS)
        self.page = self.ctx.new_page()
        # ★ここが無いと止まる（2026-09-23 実測）：本番は1ページの読み込みに20秒以上かかることがあり、
        #   既定のまま page.evaluate を呼ぶと「新しい文書が出来上がるまで待ち続けて永久に戻らない」。
        #   実際に案内人3問目で4分以上固まった。以後、文字を読むのは inner_text（時間切れのある道具）だけを使う。
        self.page.set_default_timeout(20000)
        self.page.set_default_navigation_timeout(45000)
        self.errors = []
        self.bytes = 0
        self.reqs = 0
        self.page.on("console", self._console)
        self.page.on("pageerror", lambda e: self.errors.append("pageerror: " + str(e)[:200]))
        self.page.on("response", self._response)

    def _console(self, m):
        if m.type in ("error",):
            self.errors.append("console: " + (m.text or "")[:200])

    def _response(self, r):
        self.reqs += 1
        try:
            n = r.headers.get("content-length")
            if n:
                self.bytes += int(n)
        except Exception:
            pass

    def close(self):
        try:
            self.ctx.close()
            self.browser.close()
        except Exception:
            pass

    def probe(self, selector):
        """入力欄の今の様子を見る。
        ★page.evaluate は使わない（時間切れの仕組みが無く、重いページで永久に戻らない。
          2026-09-23に実測で1回はまり、20分ぶんの計測が全部消えた）。
          locator.evaluate は timeout を持っているので、必ずこちらを使う。"""
        try:
            return self.page.locator(selector).first.evaluate(
                "el => ({alive:true, focused: document.activeElement===el,"
                " val:String(el.value||''),"
                " rebuilt: !!(window.__fkT && window.__fkT.node && !document.contains(window.__fkT.node)),"
                " swaps:(window.__fkT||{}).swaps||0, blurs:(window.__fkT||{}).blurs||0})",
                timeout=8000)
        except Exception:
            return {"alive": False, "focused": False, "val": None,
                    "rebuilt": True, "swaps": 0, "blurs": 0, "timeout": True}

    # ── 1ページを「お客さんが読むつもりで」開いて、読んでいる間の数字を取る ──
    def read_page(self, path, settle_ms=8000, label=""):
        url = path if path.startswith("http") else BASE + path
        rec = {"url": url, "width": self.width, "label": label}
        e0, b0, r0 = len(self.errors), self.bytes, self.reqs
        t0 = time.time()
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as ex:
            rec["error"] = "開けませんでした: %s" % str(ex)[:160]
            return rec
        rec["domcontentloaded_ms"] = int((time.time() - t0) * 1000)
        sp = os.path.join(SHOTDIR, slug(url, self.width) + "-before.png")
        self.page.wait_for_timeout(700)
        if self.shots:
            try:
                self.page.screenshot(path=sp)
                rec["shot_before"] = os.path.relpath(sp, ROOT)
            except Exception:
                pass
        # ★ここが「読んでる途中」。触らずにただ待つ。この間のズレが たまごさんの言う症状。
        try:
            cls_at_before = float(self.page.locator("body").first.evaluate(
                "() => (window.__fk||{}).cls || 0", timeout=10000))
        except Exception:
            cls_at_before = 0.0
        self.page.wait_for_timeout(settle_ms)
        try:
            # 読み込みが終わる前に evaluate を呼ぶと永久に戻らないことがある（実測）。先に待つ。
            self.page.wait_for_load_state("load", timeout=20000)
        except Exception:
            pass
        try:
            fk = self.page.locator("body").first.evaluate(
                "() => { const f = window.__fk || {};"
                " return {cls:f.cls||0, shifts:(f.shifts||[]).slice(0,40),"
                " lcp:f.lcp||0, longtasks:f.longtasks||[], inp:f.inp||0}; }", timeout=15000)
        except Exception as ex:
            rec["error"] = "測れませんでした: %s" % str(ex)[:160]
            return rec
        sa = os.path.join(SHOTDIR, slug(url, self.width) + "-after.png")
        # ★証拠は2枚あって初めて証拠になる。ズレが出たページは必ずもう1枚撮る
        #   （読み込みが遅いページでは「読み始め」の1枚目がすでにズレた後になることがあるため、
        #     差分だけを見て撮る・撮らないを決めない）。
        if self.shots and (fk["cls"] > CLS_GOOD or (fk["cls"] - cls_at_before) > 0.02):
            try:
                self.page.screenshot(path=sa)
                rec["shot_after"] = os.path.relpath(sa, ROOT)
            except Exception:
                pass
        lt = [x for x in fk["longtasks"] if x > 50]
        rec.update({
            "cls": round(fk["cls"], 4),
            "cls_while_reading": round(fk["cls"] - cls_at_before, 4),   # 読み始めた後にずれた分
            "shifts": fk["shifts"][:12],
            "lcp_ms": fk["lcp"],
            "inp_ms": fk["inp"],
            "longtasks_over50": len(lt),
            "longtask_total_ms": sum(lt),
            "console_errors": self.errors[e0:],
            "requests": self.reqs - r0,
            "kb": round((self.bytes - b0) / 1024.0, 1),
            "title": (self.page.title() or "")[:80],
        })
        rec["verdict"] = judge(rec["cls"], rec["lcp_ms"], rec["inp_ms"])
        return rec

    # ── 入力欄に1文字ずつ打って「落ちる」を数える ─────────────────────
    def typing_test(self, path, selector, text, label, per_char_ms=110):
        url = path if path.startswith("http") else BASE + path
        rec = {"url": url, "selector": selector, "label": label, "text": text, "width": self.width}
        e0 = len(self.errors)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.page.wait_for_timeout(2500)
        except Exception as ex:
            rec["error"] = "開けませんでした: %s" % str(ex)[:160]
            return rec
        try:
            self.page.wait_for_selector(selector, timeout=15000)
        except Exception:
            rec["error"] = "入力欄が見つかりません: %s" % selector
            return rec
        if not self.page.evaluate("sel => window.__fkWatch(sel)", selector):
            rec["error"] = "見張りを付けられませんでした"
            return rec
        try:
            self.page.click(selector)
        except Exception as ex:
            rec["error"] = "入力欄を押せません: %s" % str(ex)[:120]
            return rec
        rebuilt = focus_lost = value_lost = timeouts = 0
        worst_val = None
        per_char = []
        for i, ch in enumerate(text):
            try:
                self.page.keyboard.type(ch)
            except Exception:
                pass
            self.page.wait_for_timeout(per_char_ms)
            st = self.probe(selector)
            want = text[:i + 1]
            got = st.get("val")
            if st.get("timeout"):
                timeouts += 1
            if st.get("rebuilt"):
                rebuilt += 1
            if not st.get("focused"):
                focus_lost += 1
            if got is None or len(got) < len(want):
                value_lost += 1
                if worst_val is None:
                    worst_val = {"打った": want, "残っていた": got}
            per_char.append({"i": i + 1, "focused": bool(st.get("focused")),
                             "len": (len(got) if got is not None else -1),
                             "rebuilt": bool(st.get("rebuilt"))})
        fin = self.probe(selector)
        try:
            fk = self.page.locator("body").first.evaluate(
                "() => ({cls:(window.__fk||{}).cls||0, inp:(window.__fk||{}).inp||0})", timeout=8000)
        except Exception:
            fk = {"cls": 0, "inp": 0}
        rec.update({
            "chars": len(text),
            "入力欄が作り直された回数": rebuilt,
            "フォーカスが外れた回数": focus_lost,
            "打った字が消えた回数": value_lost,
            "画面の要素が差し替わった回数": int(fin.get("swaps") or 0),
            "focusoutイベント回数": int(fin.get("blurs") or 0),
            "最後に残っていた文字": (fin.get("val") or ""),
            "全部残ったか": (fin.get("val") or "") == text,
            "消えた例": worst_val,
            "返事が来なかった回数": timeouts,
            "console_errors": self.errors[e0:],
            "cls": round(float(fk.get("cls") or 0), 4),
            "inp_ms": int(fk.get("inp") or 0),
            "per_char": per_char,
        })
        if self.shots:
            sp = os.path.join(SHOTDIR, "typing-" + slug(url, self.width) + ".png")
            try:
                self.page.screenshot(path=sp)
                rec["shot_after"] = os.path.relpath(sp, ROOT)
            except Exception:
                pass
        return rec


# ── 案内人（卵コンシェルジュ）に30問投げる ─────────────────────────
CONCIERGE_SEL = 'input[placeholder*="気分でも"]'
URL_SEL = 'input[placeholder*="https://"]'


def body_lines(page):
    """★page.evaluate は使わない（時間切れが無く、重いページで永久に戻らないため）。"""
    try:
        t = page.inner_text("body", timeout=15000)
    except Exception:
        return []
    return [x.strip() for x in t.split("\n") if x.strip()]


# 「しゃべり」と「出てきたカードの題名」を分ける目安。
# カードの題名は短くて句読点が無い。人が読む“案内人のセリフ”は文になっている。
def is_speech(line):
    return len(line) >= 10 and any(c in line for c in "。、！？!?…")


# ── 「おじさん、わかってるね」を機械で測る ────────────────────────
# 本番の案内人は、出した札に必ず「知らない◯◯の世界だけど」と分野名を書く。
# そこを読めば、お客さんが聞いた分野と、実際に出した分野が合っているかを数えられる。
# 実測（2026-09-23）：「泣ける曲ある？」→ 猫の爪切り（笑い）、
#   「シティポップってなに？」→ 氷点下71℃の村（旅）、「ドライブで聴くやつ」→ 町中華（食べ物）。
FIELD_RE = re.compile(r"知らない(音楽|食べ物|かわいい|笑い|旅|踊り|喜び)の世界")
ASK_FIELD = [
    ("音楽", ("曲", "音楽", "聴く", "聴き", "歌", "バンド", "ポップ", "ロック", "ギター",
              "カラオケ", "歌謡", "流すやつ", "流せる")),
    ("食べ物", ("食べ", "料理", "ごはん", "レシピ", "腹")),
    ("笑い", ("笑え", "笑い", "お笑い", "面白")),
    ("旅", ("旅", "海が見たく", "景色")),
    ("踊り", ("踊", "ダンス")),
]


def asked_field(q):
    for name, words in ASK_FIELD:
        for w in words:
            if w in q:
                return name
    return None


def ask_concierge(sh, questions, revive=None):
    """revive: ブラウザが落ちた時に新しいお客さんを連れてくる関数（無ければ諦める）。
    ★2026-09-23の実測：13問目でタブごと落ち、以後18問が一度も投げられなかった。
      落ちたこと自体は記録し、そのうえで立て直して残りを必ず全部聞く。"""
    """1問ずつ投げて、画面に新しく出た言葉を『返事』として取る。
    ★測るのは「返ってきたか」ではなく「たまごさんが『わかってるね』と言うか」に効く4つ：
      空 ／ 何も出てこない ／ 使い回し（前と同じセリフ） ／ 喋りすぎ（セリフが2行超）。
    ★喋りすぎは“セリフだけ”で数える（出てきたカードの題名は数に入れない）。"""
    out = []
    seen = {}
    for q in questions:
        rec = {"q": q}
        e0 = len(sh.errors)
        t0 = time.time()
        try:
            sh.page.goto(BASE + "/cover-guide", wait_until="domcontentloaded", timeout=45000)
            sh.page.wait_for_timeout(2200)
            sh.page.wait_for_selector(CONCIERGE_SEL, timeout=15000)
            before = set(body_lines(sh.page))
            sh.page.fill(CONCIERGE_SEL, q, timeout=15000)
            sh.page.keyboard.press("Enter")
            sh.page.wait_for_timeout(3500)
            after = body_lines(sh.page)
        except Exception as ex:
            msg = "%s: %s" % (type(ex).__name__, str(ex)[:140])
            rec["error"] = msg
            rec["ng"] = ["落ちて投げられない" if "crash" in msg.lower() else "開けない・投げられない"]
            rec["seconds"] = round(time.time() - t0, 1)
            out.append(rec)
            log("  案内人 %-18s %s" % (q[:18], msg[:50]))
            if "crash" in msg.lower() and revive:
                try:
                    sh.close()
                except Exception:
                    pass
                sh = revive()
                log("  （タブが落ちたので新しいお客さんに交代）")
            continue
        new = [l for l in after if l not in before]
        speech = [l for l in new if is_speech(l)]
        cards = [l for l in new if not is_speech(l)]
        ans = "\n".join(new).strip()
        sp = "\n".join(speech).strip()
        want = asked_field(q)
        got = sorted(set(FIELD_RE.findall(ans)))
        rec.update({
            "seconds": round(time.time() - t0, 1),
            "セリフ": sp[:400], "セリフ行数": len(speech), "セリフ文字数": len(sp),
            "出てきたもの": len(cards), "画面に増えた全文": ans[:600],
            "聞いた分野": want, "出てきた分野": got,
            "console_errors": sh.errors[e0:],
        })
        ng = []
        if len(ans) < 4:
            ng.append("空（何も返っていない）")
        else:
            if want and got and want not in got:
                ng.append("的外れ（%sを聞いたのに%sが出た）" % (want, "・".join(got)))
            if not cards:
                ng.append("何も出てこない（棚が1枚も出ない）")
            key = sp[:80]
            if key and key in seen:
                ng.append("使い回し（「%s」と同じセリフ）" % seen[key])
            elif key:
                seen[key] = q
            if len(speech) > 2 or len(sp) > 120:
                ng.append("喋りすぎ（セリフ%d行・%d文字。1行＋短い一言まで）" % (len(speech), len(sp)))
        rec["ng"] = ng
        rec["ok"] = not ng
        out.append(rec)
        log("  案内人 %-18s %s" % (q[:18], "／".join(ng)[:44] if ng else "OK"))
    return out


def discover_songs(sh, want=10):
    try:
        sh.page.goto(BASE + "/cover-guide", wait_until="domcontentloaded", timeout=45000)
        sh.page.wait_for_timeout(2500)
        hrefs = sh.page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.getAttribute('href'))")
    except Exception:
        return []
    songs = []
    for h in hrefs or []:
        if h and "cover-guide?" in h and "song=" in h and h not in songs:
            songs.append(h if h.startswith("/") else "/" + h)
    return songs[:want]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--settle", type=int, default=8000)
    ap.add_argument("--merge", action="store_true",
                    help="今日の結果に上書きせず、走らせた部分だけ差し替える（--only と一緒に使う）")
    a = ap.parse_args()
    only = set(x.strip() for x in a.only.split(",") if x.strip())

    def want(name):
        return (not only) or (name in only)

    os.makedirs(SHOTDIR, exist_ok=True)
    day = time.strftime("%Y-%m-%d")
    outdir = os.path.join(OUTDIR, day)
    os.makedirs(outdir, exist_ok=True)

    from playwright.sync_api import sync_playwright
    # ★このMac自体が混んでいると LCP/INP/長いタスク は簡単に倍になる。
    #   数字を読む人が誤解しないよう、走らせた時の混み具合を必ず一緒に残す。
    try:
        la = [round(x, 1) for x in os.getloadavg()]
    except Exception:
        la = None
    result = {"日付": day, "開始": time.strftime("%F %T"), "本番": BASE,
              "このMacの混み具合(開始時のload average)": la,
              "ものさし": {"CLS": "0.1以下が良・0.25超が悪", "LCP": "2.5秒以下が良・4秒超が悪",
                          "INP": "200ms以下が良・500ms超が悪"},
              "pages": [], "typing": [], "concierge": [], "errors": []}
    shots = not a.no_shots
    songs = []

    if a.merge:
        # ★一部だけ走らせ直した時に、走らせていない部分を消さない。
        # どの人が走ればその欄が埋まるか、の対応表だけを見る。
        owners = {"pages": ("first", "mobile"), "typing": ("mobile", "url"),
                  "concierge": ("concierge",)}
        try:
            with open(os.path.join(outdir, "result.json")) as f:
                old = json.load(f)
            for k, who in owners.items():
                if not any(want(x) for x in who):
                    result[k] = old.get(k, [])
        except Exception:
            pass

    def save(final=False):
        """★1人終わるごとに必ず書く。最後にまとめて書くと、途中で1回詰まっただけで
        その日の計測が丸ごと消える（2026-09-23に20分ぶん失って学んだ）。"""
        try:
            with open(os.path.join(outdir, "result.json"), "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
            with open(os.path.join(OUTDIR, "latest.json"), "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
    with sync_playwright() as pw:
        # ① 初めて来た人（1280px）
        if want("first"):
            sh = Shopper(pw, 1280, 900, shots=shots)
            try:
                log("① 初めて来た人（1280px）")
                result["pages"].append(sh.read_page("/", a.settle, "トップ"))
                songs = discover_songs(sh, 3 if a.quick else 10)
                shelves = SHELVES[:1] if a.quick else SHELVES
                for s in shelves:
                    result["pages"].append(sh.read_page(s, a.settle, "棚"))
                for s in songs:
                    result["pages"].append(sh.read_page(s, a.settle, "曲ページ"))
            except Exception:
                result["errors"].append("first: " + traceback.format_exc()[-400:])
            finally:
                sh.close()
                save()

        # ② スマホの人（375px）
        if want("mobile"):
            sh = Shopper(pw, 375, 812, mobile=True, shots=shots)
            try:
                log("② スマホの人（375px）")
                result["pages"].append(sh.read_page("/", a.settle, "トップ"))
                if not songs:
                    songs = discover_songs(sh, 3 if a.quick else 10)
                for s in (SHELVES[:1] if a.quick else SHELVES):
                    result["pages"].append(sh.read_page(s, a.settle, "棚"))
                for s in songs[:3 if a.quick else 5]:
                    result["pages"].append(sh.read_page(s, a.settle, "曲ページ"))
                result["typing"].append(sh.typing_test(
                    "/cover-guide", CONCIERGE_SEL, "雨の日にひとりで", "案内人に話しかける欄（スマホ375px）"))
            except Exception:
                result["errors"].append("mobile: " + traceback.format_exc()[-400:])
            finally:
                sh.close()
                save()

        # ③ URLを貼る人（1280px）— たまごさんが「落ちる」と言っている経路
        if want("url"):
            sh = Shopper(pw, 1280, 900, shots=shots)
            try:
                log("③ URLを貼る人")
                result["typing"].append(sh.typing_test(
                    "/cover-guide", URL_SEL, "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "案内所のURL欄にYouTubeのURLを打つ", per_char_ms=70))
                result["typing"].append(sh.typing_test(
                    "/cover-guide", CONCIERGE_SEL, "ドライブで聴くやつ", "案内人に話しかける欄（1280px）"))
                result["typing"].append(sh.typing_test(
                    "/", 'textarea[placeholder*="気になった点"]', "ここが分かりにくかったです",
                    "トップの感想欄"))
            except Exception:
                result["errors"].append("url: " + traceback.format_exc()[-400:])
            finally:
                sh.close()
                save()

        # ④ 案内人に話しかける人
        if want("concierge"):
            sh = Shopper(pw, 1280, 900, shots=False)
            try:
                log("④ 案内人に30問")
                qs = QUESTIONS[:8] if a.quick else QUESTIONS
                result["concierge"] = ask_concierge(
                    sh, qs, revive=lambda: Shopper(pw, 1280, 900, shots=False))
            except Exception:
                result["errors"].append("concierge: " + traceback.format_exc()[-400:])
            finally:
                sh.close()
                save()

    result["終了"] = time.strftime("%F %T")
    try:
        result["このMacの混み具合(終了時のload average)"] = [round(x, 1) for x in os.getloadavg()]
    except Exception:
        pass
    ok_pages = [p for p in result["pages"] if "cls" in p]
    result["まとめ"] = {
        "見たページ数": len(result["pages"]),
        "測れたページ数": len(ok_pages),
        "CLSが悪い(0.25超)ページ数": len([p for p in ok_pages if p["cls"] > CLS_BAD]),
        "CLSが良い(0.1以下)ページ数": len([p for p in ok_pages if p["cls"] <= CLS_GOOD]),
        "LCPが4秒超のページ数": len([p for p in ok_pages if p["lcp_ms"] > LCP_BAD]),
        "console errorが出たページ数": len([p for p in ok_pages if p.get("console_errors")]),
        "入力で作り直しが起きた欄の数": len([t for t in result["typing"] if t.get("入力欄が作り直された回数")]),
        "案内人の不合格数": len([c for c in result["concierge"] if c.get("ng")]),
        "案内人の設問数": len(result["concierge"]),
    }
    path = os.path.join(outdir, "result.json")
    with open(path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUTDIR, "latest.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log("書きました: %s" % os.path.relpath(path, ROOT))
    log(json.dumps(result["まとめ"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
