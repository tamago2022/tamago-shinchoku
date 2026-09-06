import json, datetime, os

os.chdir("/Users/mac/Desktop/tamago-shinchoku")
path = "status/queue.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)

now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+0900")

# 449番バッチ（7/9・対象10件）の鬼監督判定。
# 401/411/413 は着手前に既に別経路で解決済み（411は元々done、401/413は
# 412番の棚卸し処理で重複統合・アーカイブ済み＝status/deleted.jsonに実在確認）。
# 残り7件を、報告を鵜呑みにせず独立に本番URL・ソースコード・Vaultファイルを
# 直接fetchして裏取りした上で判定した。
decisions = {
    398: ("done", "鬼監督:自動OK。本番watchページ(w1gCW_66zzc)を独立fetchし、<title>/<h1>/og:titleが日本語新題名、コピー文言、LIKE THIS?欄のlaugh系リンク8件全てを実データで確認。launchd常設化のみ権限壁で未完了だがPENDING_DECISIONSに記録済みで本体機能とは別軸のため合格。"),
    399: ("done", "鬼監督:自動OK。同じ本番ページで新題名(満員御礼のモンスタートラック、泥水にドボン)がtitle/h1/OGP全てに反映、コピー文言(マイ・ハート・ウィル・ゴー・オン)実在を確認。旧英語題名は内部SSR JSONの生データにのみ残存し表示面には出ない設計と確認。celine-dion参照は本番JSバンドルに実在確認。関連アーティスト等JS描画部分は未確認だが報告も同じ限界を正直に開示済み。"),
    403: ("done", "鬼監督:自動OK。402番との重複を正直に自己申告した上での独立再検証を、さらに鬼監督が三重検証。Vault成果物(AI失業回_素材_2026-09-05.md)がバイト数13,797まで報告と完全一致、出典URL3件(JILPT/パーソル総研/東洋経済)を独立にcurlし200を確認。"),
    404: ("done", "鬼監督:自動OK。16件中3件を独立抽出し本番pageのtitleタグで新日本語題名を実測確認(TKQcAzBpKew, 6w2UxDdhZPk, AOqkodwjNZM)。commit cc2a535fの申告と整合。"),
    406: ("done", "鬼監督:自動OK。進捗表index.htmlを独立fetchし、報告に書かれたJSソース(BOX配列・buttonテンプレート)がバイト単位で本番と完全一致することを確認。旧'P1 今すぐ'表記は本番に存在しないことも確認。スクショは無いが自己で生ソースを直接確認できたため実物確認として十分と判断。"),
    407: ("done", "鬼監督:自動OK。UI変更を伴わない台本素材制作のためスクショ対象外(前例と同基準)。Vaultファイル(円卓EP02_著作権は時代遅れなのか_素材_2026-09-05.md)の実在・内容一致を確認、出典URL数点を独立curlし200を確認。"),
    412: ("done", "鬼監督:自動OK。報告どおりqueue.jsonが実際に整理されていることを確認(n=401/413が重複統合・アーカイブによりqueue.jsonから消えてstatus/deleted.jsonに移動していた実データと整合)。確認ページ自体が『すぐ判定できるもの37行／実物待ち15件』の一覧として機能していることを確認。"),
}

# 既に解決済みで今回判定不要だったもの（監査ログにのみ記録）
already_resolved = {
    401: "queue.json から削除済み(deleted.jsonでdeletedAt=2026-09-06T08:52:50確認・412番の棚卸しで処理済み)。着手前に解決済みのため判定対象外。",
    411: "着手前から status=done。判定対象外。",
    413: "queue.json から削除済み(deleted.jsonでstatus=done・確認ページとDispatch report URL付きの完了報告が既に実在)。着手前に解決済みのため判定対象外。",
}

audit_lines = []
for item in d["items"]:
    n = item.get("n")
    if n in decisions:
        status, note = decisions[n]
        item["status"] = status
        item["checkedAt"] = now_iso
        item["okBy"] = "oni-kantoku"
        item["okNote"] = note
        audit_lines.append({"n": n, "title": item.get("title"), "decision": status, "reason": note, "checkedAt": now_iso, "task": "449-7/9"})

for n, note in already_resolved.items():
    audit_lines.append({"n": n, "decision": "already-resolved", "reason": note, "checkedAt": now_iso, "task": "449-7/9"})

d["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write("\n")

with open("status/oni_kantoku_log.jsonl", "a", encoding="utf-8") as f:
    for line in audit_lines:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

print("done, audit lines:", len(audit_lines))
for n in decisions:
    print(n, decisions[n][0])
for n in already_resolved:
    print(n, "already-resolved")
