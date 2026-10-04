#!/usr/bin/env python3
"""締め切り見張り：GitHub Milestone(期日つき)を正本に、毎日1回
 ①「今日／あと1日／過ぎた」のMilestoneの代表Issueへコメント（同じ日・同じ状態は1回だけ）
 ②全Milestoneから share/calendar.ics を作り、tamago-shinchoku(main)へ更新
gh(curl相当のAPI)だけ使う。AIのクレジットは使わない。
使い方: python3 tools/deadline_watch.py [--dry]
Milestoneの description に「代表Issue: #821」と書くと、そのIssueにコメントが付く。
"""
import json, re, subprocess, sys, datetime as dt, os

GH = os.path.expanduser("~/.local/bin/gh")
REPOS = ["tamago2022/joy-relief-station"]
JST = dt.timezone(dt.timedelta(hours=9))
DRY = "--dry" in sys.argv


def gh(*a, inp=None):
    r = subprocess.run([GH, *a], capture_output=True, text=True, input=inp)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def api(path, *a, inp=None):
    return json.loads(gh("api", path, *a, inp=inp) or "null")


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    b, out = line.encode(), []
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode()); b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


def outbox(text):
    """工場の dispatch_outbox（Dispatchが拾う）へ1行"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "status", "dispatch_outbox.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": dt.datetime.now(JST).isoformat(), "from": "deadline_watch", "text": text}, ensure_ascii=False) + "\n")


def alarms(what):
    """5日前・3日前・前日の通知"""
    out = []
    for d in (5, 3, 1):
        out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER:-P{d}D", f"DESCRIPTION:{what}あと{d}日", "END:VALARM"]
    return out


def main():
    now = dt.datetime.now(JST)
    today = now.date()
    test = None
    if "--now" in sys.argv:  # 動作確認用: --now 2026-10-07
        test = sys.argv[sys.argv.index("--now") + 1]
        today = dt.date.fromisoformat(test)
    events = []
    for repo in REPOS:
        for ms in api(f"repos/{repo}/milestones?state=all&per_page=100"):
            due = ms.get("due_on")
            if not due:
                continue
            # GitHubは期日を日付だけで持つ(00:00Z)。その日の23:59 JSTを締め切りとする
            d0 = dt.date.fromisoformat(due[:10])
            due_jst = dt.datetime(d0.year, d0.month, d0.day, 23, 59, tzinfo=JST)
            o, c = ms["open_issues"], ms["closed_issues"]
            m = re.search(r"代表Issue:\s*#(\d+)", ms.get("description") or "")
            events.append(dict(repo=repo, id=ms["id"], num=ms["number"], title=ms["title"],
                               due=due_jst, o=o, c=c, start=ms["created_at"][:10], url=ms["html_url"], state=ms["state"]))
            if ms["state"] != "open" or not m or o == 0:
                continue
            days = (due_jst.date() - today).days
            label = {0: "今日", 1: "あと1日"}.get(days) or ("過ぎた" if days < 0 else None)
            if not label:
                continue
            issue = m.group(1)
            marker = f"<!--deadline:{repo}:{ms['number']}:{today}:{label}-->"
            body = (f"{marker}\n{'（動作確認の試し投稿）' if test else ''}締め切り{label}（{due_jst:%m/%d %H:%M}）：{ms['title']}\n"
                    f"完了{c}/{c+o}、残り{o}件。\n@codex 確認を。Gensparkも確認を（このIssueを読んでいます）。\n"
                    f"一覧: {ms['html_url']}")
            existing = api(f"repos/{repo}/issues/{issue}/comments?per_page=100&sort=created&direction=desc")
            if any(marker in (x.get("body") or "") for x in existing):
                print(f"skip(既に投稿済み) {repo}#{issue} {label}")
                continue
            print(f"comment {repo}#{issue} {label}: 完了{c}/{c+o}")
            if not DRY:
                r = api(f"repos/{repo}/issues/{issue}/comments", "-F", "body=@-", inp=body)
                print("URL", r["html_url"])
                outbox(f"【締め切り{label}】{ms['title']}：完了{c}/{c+o}、残り{o}件（{due_jst:%m/%d}）。#{issue}に@codex・Gensparkへ確認コメント済み {r['html_url']}")

    # ---- xAI(Grok Voice)の使用量を台帳へ（Lovable voice_usage_log をSELECTのみ。失敗しても続ける）----
    if not DRY and not test:
        try:
            subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "xai_voice_tally.py")], timeout=120)
        except Exception as ex:
            print("xai集計 失敗:", ex)

    # ---- サブスク予告（5日前・3日前・前日→進捗表＋dispatch_outbox）----
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import subsc_shirase
        if not DRY and not test:
            subsc_shirase.run()
    except Exception as ex:
        print("subsc_shirase 失敗:", ex)

    # ---- ics ----
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//tamago//deadline-watch//JA",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:たまごAI専用カレンダー",
         "X-WR-TIMEZONE:Asia/Tokyo", "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
    for e in sorted(events, key=lambda e: e["due"]):
        total = e["o"] + e["c"]
        o_, c_ = e["o"], e["c"]
        done = "【完了】" if e["state"] == "closed" or e["o"] == 0 else ""
        start = e["due"] - dt.timedelta(hours=1)
        L += ["BEGIN:VEVENT",
              f"UID:milestone-{e['id']}@tamago2022.github.io",
              f"DTSTAMP:{stamp}",
              f"DTSTART;TZID=Asia/Tokyo:{start:%Y%m%dT%H%M%S}",
              f"DTEND;TZID=Asia/Tokyo:{e['due']:%Y%m%dT%H%M%S}",
              "SUMMARY:" + esc(done + "締切 " + e["title"] + " 残り" + str(o_) + "件"),
              "DESCRIPTION:" + esc("着手 " + e["start"] + "／期日 " + f"{e['due']:%Y-%m-%d}" + f"／完了{c_}/{total}、残り{o_}件"),
              f"URL:{e['url']}",
              ] + alarms("締め切り") + [
              "END:VEVENT"]
        sd = e["start"].replace("-", "")
        sd2 = (dt.date.fromisoformat(e["start"]) + dt.timedelta(days=1)).strftime("%Y%m%d")
        L += ["BEGIN:VEVENT", f"UID:milestone-start-{e['id']}@tamago2022.github.io", f"DTSTAMP:{stamp}",
              f"DTSTART;VALUE=DATE:{sd}", f"DTEND;VALUE=DATE:{sd2}",
              "SUMMARY:" + esc("着手 " + e["title"]), "URL:" + e["url"], "END:VEVENT"]
    # サブスクの更新日（status/subsc.json・日付が確かなものだけ）
    try:
        led = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "status", "subsc.json"), encoding="utf-8"))
    except Exception:
        led = {"items": []}
    for it in led.get("items", []):
        try:
            d0 = dt.date.fromisoformat((it.get("tsugi") or "")[:10])
        except ValueError:
            continue
        owari = it.get("kurikaeshi") == "owari"
        kane = f"${it['usd']}" if it.get("usd") else ""
        if it.get("yen"):
            kane += f"（約{it['yen']:,}円・目安）"
        name = it["name"].split("（")[0] + ("" if it.get("kakunin") else "（日付は未確認）")
        L += ["BEGIN:VEVENT", f"UID:subsc-{it['id']}-{d0}@tamago2022.github.io", f"DTSTAMP:{stamp}",
              f"DTSTART;VALUE=DATE:{d0:%Y%m%d}", f"DTEND;VALUE=DATE:{d0 + dt.timedelta(days=1):%Y%m%d}",
              "SUMMARY:" + esc(("サブスク終了 " if owari else "サブスク更新 ") + name + (" " + kane if kane else "")),
              "DESCRIPTION:" + esc(("更新しない。" if owari else "") + "円は目安・実際のカード請求額とは異なる"),
              ] + alarms("サブスク") + ["END:VEVENT"]
    L.append("END:VCALENDAR")
    # Googleカレンダーに入れる必要のある予定（正本は台帳・Milestone。Dispatchはこれを見て【AI】付きで入れる）
    cal = []
    for e in events:
        if e["state"] == "open":
            cal.append(dict(uid=f"milestone-{e['id']}", title="【AI】締切 " + e["title"], start=e["start"],
                            date=f"{e['due']:%Y-%m-%d}", note=f"残り{e['o']}件／{e['url']}", alarmDays=[5, 3, 1]))
    for it in led.get("items", []):
        try:
            d0 = dt.date.fromisoformat((it.get("tsugi") or "")[:10])
        except ValueError:
            continue
        ow = it.get("kurikaeshi") == "owari"
        cal.append(dict(uid=f"subsc-{it['id']}-{d0}", title=("【AI】サブスク終了 " if ow else "【AI】サブスク更新 ") + it["name"].split("（")[0],
                        date=str(d0), note=(f"${it['usd']}" if it.get("usd") else "") + ("（円は目安）" if it.get("yen") else "") + ("" if it.get("kakunin") else "／日付未確認"),
                        alarmDays=[5, 3, 1]))
    cal.sort(key=lambda x: x["date"])
    if not DRY:
        outp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "status", "calendar_todo.json")
        json.dump(dict(generatedAt=dt.datetime.now(JST).isoformat(), calendar="eggypop2010@gmail.com", items=cal),
                  open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ics = "\r\n".join(fold(x) for x in L) + "\r\n"

    # 公開：tools/pages_publish.sh が status/public/ をそのまま配信枝へ写す（書き手1本の原則を守る）
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "status", "public", "calendar.ics")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    old = open(out, encoding="utf-8", newline="").read() if os.path.exists(out) else ""
    strip = lambda t: re.sub(r"DTSTAMP:\S+", "", t)
    if strip(old) == strip(ics):
        print("ics 変化なし")
    elif DRY:
        print("ics 更新(dry)")
    else:
        open(out, "w", encoding="utf-8", newline="").write(ics)
        print("ics 更新", out)


if __name__ == "__main__":
    main()
