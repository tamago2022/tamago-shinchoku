#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-11-05 たまごさん「たまごさんが聞かないと止まったままになる仕事をゼロに」：宙に浮いた4本を工場の列に積む（1回きり）。
Mac で走らせる（queue_lock が要るため）。同じ印（chuuKey）が既に列にあれば積まない。
  python3 tools/_1105_chuu_tsumu.py
結果：status/itsumo/chuu_tsunda.json（積んだ番号）
"""
import io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import command_ingest
from command_ingest import queue_lock, _load_queue, _save_queue  # noqa

FABLE = "claude-fable-5-1"
KYOUTSUU = (
    "\n■ 守ること（全便共通）\n"
    "・この便は claude-fable-5-1 で走る（fixedModel）。最初に自分のモデル名を確かめ、Fableでなければ作らずに止めて dispatch_outbox.jsonl に1行。使ったモデル名は記録に残す。\n"
    "・お金は0円。有料API（fal・Replicate・ElevenLabs など）は使わない。素材は自由ライセンス（CC0／PD）だけ：Poly Haven・ambientCG（CC0のテクスチャ・写真）、"
    "NASA CGI Moon Kit（https://svs.gsfc.nasa.gov/4720 ・パブリックドメイン）。クレジットは記録に書く。\n"
    "・Macを重くしない：レンダーは GitHub Actions（.github/workflows/uchu-unko-*-render.yml の形）で回す。Mac上で走らせるときは nice -n 19・1本ずつ・試しは低解像度。"
    "中間物（_frames・_chunks・.part）は終わったら消す。\n"
    "・ブラウザ・web_fetch・許可ポップアップの出る道具は使わない。たまごさんに質問しない。\n"
    "・採点：スキル design-critique の5観点（各0〜10）を出し、合計を100点に直して「自己採点NN点」と報告に書く。tamago-tone の基準で「AI臭い」「のっぺり」を減点。\n"
    "・80点以上になったら `python3 tools/claude_nouhin.py put <mp4> --anken 宇宙うんこ --saishin`（GOD FUNKY は --anken 音ハメ文字動画）でドライブ「AI制作物/Claude/<案件>」へ納品し、"
    "報告にドライブのURL（https://drive.google.com/…）を貼る。工場が自動で Dispatch に「完成：名前／Driveリンク」を出す。\n"
    "・80点に届かなければ納品しない。何点で、あと何を直せば80点に届くかを status/<作業フォルダ>/README.md の「次に直すこと」に書き、"
    "同じ便の続きとして列に戻す（報告の頭に【続き】と書く）。\n"
)

BIN = [
    {"key": "uchu_unko_taki_v3", "mei": "宇宙うんこ 滝のv3", "label": "Fable｜宇宙うんこ 滝のv3（のっぺり解消・80点で納品）",
     "what": "【Fable｜宇宙うんこ 滝のv3】\n"
             "元：status/uchu_unko/v2/（README.md・kumitate_v2.py・hashiru.sh・nouhin.sh）と status/uchu_unko/261031_宇宙うんこv3_滝と月.mp4。\n"
             "やること：\n"
             "1) status/uchu_unko/v2/README.md の「次に直すこと」5つを全部直す（霧の白0.5秒／夜のオーロラを近く明るく・雲海の島は小さく暗く／鉄琴を金属の板らしく・1本の道に／滝つぼの泡と水しぶき／低音の当たりは板を大きく・光を朱に）。\n"
             "2) のっぺり解消：写真素材（コンクリート・苔・水しぶき＝Poly Haven／ambientCG の CC0）を質感に貼り、月は NASA CGI Moon Kit の色と高さの地図を使う。\n"
             "3) 作業は status/uchu_unko/v3_taki/ に置く（README.md に手順・素材とライセンス・点数を書く）。\n"},
    {"key": "haikyo_mall_204017", "mei": "宇宙うんこ 廃墟モール×沈める寺", "label": "Fable｜宇宙うんこ 廃墟モール×沈める寺 作り直し（204017・62点→80点）",
     "what": "【Fable｜廃墟モール×沈める寺 作り直し】204017番の続き（たまごさん判定前の自己採点62点）。\n"
             "元：status/fpv_haikyo_mall_1101/README.md と 204017番の記録（status/fable_shiken_1101/kiroku.jsonl）・status/uchu_unko/261101_宇宙うんこv3.1_廃墟.mp4。\n"
             "やること：滝のv3と同じ方法で細かさを出す（写真素材の質感・NASA Moon Kit・霧と光の層・小物の密度）。62点の理由を README から読み、1つずつ潰す。\n"
             "作業は status/fpv_haikyo_mall_1101/ に続けて置く。\n"},
    {"key": "hongkong_crane_204018", "mei": "宇宙うんこ 夜の香港クレーン 直し", "label": "Fable｜宇宙うんこ 夜の香港クレーン 直し（204018・完了確認→続き）",
     "what": "【Fable｜夜の香港クレーン 直し】204018番の続き。前回は「session limit」で止まり、完了したか分からないまま確認待ちに落ちていた。\n"
             "1) まず完了したかを確かめる：status/uchu_unko/261101_宇宙うんこ_夜の香港クレーン_直し.mp4 と tools/uchu_unko_v4・status/uchu_unko/v4 の記録で、"
             "依頼（曲に合わせてカメラとうんこの軌道を設計し直す・ディテール）が全部入っているか。入っていて80点以上なら、採点を書いて納品へ進むだけ。\n"
             "2) 未完なら続きをやる（終わっている工程はやり直さない）。\n"},
    {"key": "god_funky_bansen", "mei": "GOD FUNKY 番宣", "label": "Fable｜GOD FUNKY 番宣 仕上げ（65点→80点・3D正本でロボット差し替え）",
     "what": "【Fable｜GOD FUNKY AI特集番宣 仕上げ】今65点。元の依頼と経緯は 204046番（起こし｜GOD FUNKY AI特集番宣）とその作業フォルダ。\n"
             "1) 3D正本（ドライブ「AI制作物/Claude/月面3D土台」・工場の m3d_ 系の記録＝たまご・ロボの正本3Dモデル）ができているか確かめる。\n"
             "2) できていたら：ラストのロボットと締めのカードを3D正本に差し替える。街（2040年代のネオ東京）の質感を写真素材（CC0）で上げる。音ハメ（GOD FUNKY・Sunoの曲）は崩さない。\n"
             "3) まだできていなければ：街の質感だけ先に上げ、ロボットと締めカードは差し替えずに status/itsumo/machi_3d.json に"
             "{\"n\":この便,\"matsu\":\"3D正本\"} を1行書いて【続き】で列に戻す（3D正本の便 205673 が終わったら続ける）。\n"},
]


def main():
    out = {"at": time.strftime("%F %T"), "tsunda": []}
    with queue_lock():
        q = _load_queue()
        have = {it.get("chuuKey"): it.get("n") for it in q.get("items", []) if it.get("chuuKey")}
    for b in BIN:
        if b["key"] in have:
            out["tsunda"].append({"key": b["key"], "n": have[b["key"]], "st": "既にある"})
            continue
        st, msg = command_ingest.queue_add(b["what"] + KYOUTSUU, priority=1, label=b["label"], origin="user",
                                           model=FABLE, urgent=True)
        out["tsunda"].append({"key": b["key"], "st": st, "msg": str(msg)[:200]})
    # 積んだ項目に印を付ける（番号を拾う）
    with queue_lock():
        q = _load_queue()
        for b, r in zip(BIN, out["tsunda"]):
            for it in reversed(q.get("items", [])):
                if it.get("title") == b["label"] and it.get("status") == "waiting":
                    it.update({"chuuKey": b["key"], "fixedModel": FABLE, "model": FABLE, "kanseiTsuuchi": True,
                               "kanseiMei": b["mei"], "limitMin": 180, "tamagoIsogi": True,
                               "urgentReason": "たまごさん名指し（2026-11-05「聞かないと止まったままの仕事をゼロに」・Fable指定）"})
                    r["n"] = it.get("n")
                    break
        # 古い便は新しい便へ引き継ぎ（確認待ちに残して、たまごさんに見させない）
        for it in q.get("items", []):
            if str(it.get("n")) in ("204017", "204018") and it.get("status") == "awaiting_check":
                it["statusBefore"] = it["status"]
                it["status"] = "cancelled"
                it["restoreWhy"] = "2026-11-05 新しい便（_1105_chuu_tsumu）へ引き継ぎ"
        _save_queue(q)
    os.makedirs(os.path.join(REPO, "status", "itsumo"), exist_ok=True)
    json.dump(out, io.open(os.path.join(REPO, "status", "itsumo", "chuu_tsunda.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
