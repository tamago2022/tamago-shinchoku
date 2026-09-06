#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
409番『卵劇場EP01・15秒を松竹梅で作って比べる』の実行本体。

このスクリプトは「有料のfal.ai API呼び出し」を実際に行います（合計上限300円のガード付き）。
このスクリプト自体は準備済みですが、このMac上のClaude Codeセッションの安全機構（auto mode classifier）が、
人間が対話的に許可ボタンを押していない無人セッションからの「有料API実行」をブロックする仕様のため、
tamago-orchestrator（409番セッション）自身はこのスクリプトを実行できませんでした。

★実行方法（たまごさん本人 or 対話的に許可できるセッションで）：
    python3 "/Users/mac/Desktop/tamago-shinchoku/share/check/assets/409-matsutakeume/run_matsutakeume.py"

実行すると、Bashの許可ダイアログが1回（最初のfal API呼び出し時）出るはずなので「許可」を押してください。
以降は自動で進み、梅→竹(実測1本)→竹(残り)→松(実測1本)→松(残り) の順で、
合計300円に達した時点で自動停止し、そこまでの結果を書き出します。

出力先：
  - このフォルダ（output/ サブフォルダ）に ume_15s.mp4 / take_15s.mp4 / matsu_15s.mp4
  - このフォルダに cost_matsutakeume.md（実施した生成・実費・累計・できたこと/できなかったこと）
  - 可能なら Google Drive（/Users/mac/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/卵劇場EP01_完成/）にもコピー
"""
import sys, os, json, time, mimetypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fal_helper as fh

FLAT_PACK = "/Users/mac/Desktop/EP01_娘がAIと暮らしはじめた_Claude制作パック_FLAT"
OUT_DIR = os.path.join(HERE, "output")
os.makedirs(OUT_DIR, exist_ok=True)

DRIVE_DIR = "/Users/mac/Library/CloudStorage/GoogleDrive-eggypop2010@gmail.com/マイドライブ/卵劇場EP01_完成"

USD_TO_JPY = 157.0
BUDGET_JPY = 300.0

# 2026-09-06 419番: COST_LOGはプロセス起動のたびに空になる。
# 前回プロセス（梅の3ショット+竹sh09実測=123.3円）は既に実費が発生済みで
# output/内のファイルとしてもSKIP-DUPで残っているため、その分を最初から
# 積んでおかないと「合計300円で必ず止まる」が壊れて二重に予算を使ってしまう。
PRIOR_SPEND_JPY = 123.3
COST_LOG = [{"label": "前回実行分(引き継ぎ)", "usd": PRIOR_SPEND_JPY / USD_TO_JPY, "jpy": PRIOR_SPEND_JPY,
             "note": "梅3ショット+竹sh09実測（前プロセスで実費発生済み・output/に成果物あり）", "t": "prior"}]


def jpy(usd):
    return usd * USD_TO_JPY


def total_jpy():
    return sum(x["jpy"] for x in COST_LOG)


def record(label, usd, note=""):
    entry = {"label": label, "usd": usd, "jpy": jpy(usd), "note": note, "t": time.strftime("%H:%M:%S")}
    COST_LOG.append(entry)
    print(f"[COST] {label}: ${usd:.4f} = {entry['jpy']:.1f}円  累計={total_jpy():.1f}円  {note}")


def would_exceed(usd):
    return total_jpy() + jpy(usd) > BUDGET_JPY


# ---------- ① 画像の切り出し（無料・ローカル処理） ----------

def crop_shots():
    img_dir = os.path.join(HERE, "img")
    os.makedirs(img_dir, exist_ok=True)
    paths = {
        "sh09": os.path.join(img_dir, "sh09_source.png"),
        "sh10": os.path.join(img_dir, "sh10_source.png"),
        "sh11": os.path.join(img_dir, "sh11_source.png"),
    }
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in paths.values()):
        # 2026-09-06 419番: 元の制作パックフォルダ(FLAT_PACK)が本セッション時点で
        # 見当たらなくなっていた（移動/整理された可能性）。前回プロセスが既に
        # 切り出し済みのこの3枚をそのまま再利用する（無料処理・二重生成不要）。
        print("[SKIP-DUP] 画像切り出しは前回分を再利用（元FLAT_PACKが見当たらないため）")
        return paths

    from PIL import Image
    src1 = Image.open(os.path.join(FLAT_PACK, "21_SHOTS_06_10.png"))
    sh09 = src1.crop((30, 505, 560, 780))
    sh09.save(paths["sh09"])
    sh10 = src1.crop((828, 505, 1360, 780))
    sh10.save(paths["sh10"])
    src2 = Image.open(os.path.join(FLAT_PACK, "22_SHOTS_11_15.png"))
    sh11 = src2.crop((15, 172, 565, 425))
    sh11.save(paths["sh11"])
    return paths


# ---------- ② 静止画から「固定カメラの5秒動画」を作る（Kling LipSyncのvideo_url入力用・無料） ----------

def make_hold_video(png_path, mp4_path, seconds, fps=24, size=(960, 540)):
    import cv2, numpy as np
    from PIL import Image
    img = Image.open(png_path).convert("RGB").resize(size)
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    vw = cv2.VideoWriter(mp4_path, cv2.CAP_AVFOUNDATION, fourcc, fps, size)
    if not vw.isOpened():
        raise RuntimeError(f"VideoWriter が開けませんでした: {mp4_path}")
    for _ in range(int(seconds * fps)):
        vw.write(frame)
    vw.release()
    time.sleep(1)
    return mp4_path


# ---------- ③ 梅：TTS（ElevenLabs）→ Kling LipSync ----------

TTS_LINES = [
    # 2026-09-06 419番: "Antoni" は fal-ai/elevenlabs/tts/eleven-v3 で
    # HTTP 422 "Voice not found: Antoni" になることを実測で確認（旧世代voice名が廃止済み）。
    # "Rachel"(デフォルト)/"Adam" は実際に呼び出して有効なことを小額テストで確認済みなので採用。
    ("sh09_amore", "アモーレ", "Rachel", "人生は愛だ！ ロマンスだ！"),
    ("sh10_yamori", "家守", "Adam", "お前は四回結婚してるだろ。"),
    ("sh10_amore", "アモーレ", "Rachel", "四回も愛した。"),
    ("sh11_yamori", "家守", "Adam", "三回離婚してる！"),
    ("sh11_amore", "アモーレ", "Rachel", "三回、正直だった。"),
]


def _existing_tts(key):
    for ext in (".mp3", ".wav", ".m4a"):
        p = os.path.join(OUT_DIR, f"tts_{key}{ext}")
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def run_tts_all():
    results = {}
    for key, char, voice, text in TTS_LINES:
        existing = _existing_tts(key)
        if existing:
            print(f"[SKIP-DUP] TTS:{key} は既に生成済み（二重課金回避）: {existing}")
            results[key] = existing
            continue
        nchars = len(text)
        est_usd = (nchars / 1000.0) * 0.10
        if would_exceed(est_usd):
            print(f"[STOP] TTS:{key} で予算超過見込み。停止。")
            break
        out = fh.run_sync("fal-ai/elevenlabs/tts/eleven-v3", {"text": text, "voice": voice}, timeout=60)
        record(f"TTS:{key}", est_usd, f"{char}/{voice} \"{text}\" ({nchars}文字)")
        url = fh.find_url(out)
        if not url:
            print(f"[WARN] {key} の音声URLが見つからない。生レスポンス: {json.dumps(out)[:400]}")
            continue
        dest = os.path.join(OUT_DIR, f"tts_{key}{os.path.splitext(url)[1] or '.mp3'}")
        fh.download(url, dest)
        results[key] = dest
        print(f"  -> {dest}")
    return results


def concat_bytes(paths, dest):
    """mp3等を単純バイト連結する簡易つなぎ（ffmpeg非搭載環境向けの妥協策）。"""
    with open(dest, "wb") as out:
        for p in paths:
            with open(p, "rb") as f:
                out.write(f.read())
    return dest


def run_ume(tts_paths):
    """梅：Kling LipSyncのみ。カメラ固定・口と顔が動く。3カットで約33円想定。"""
    print("\n=== 【梅】Kling LipSync ===")
    shots = crop_shots()
    plan = [
        ("sh09", [tts_paths.get("sh09_amore")], 5.5),
        ("sh10", [tts_paths.get("sh10_yamori"), tts_paths.get("sh10_amore")], 6.5),
        ("sh11", [tts_paths.get("sh11_yamori"), tts_paths.get("sh11_amore")], 5.5),
    ]
    clip_paths = []
    for shot_key, audio_parts, seconds in plan:
        existing_ume = os.path.join(OUT_DIR, f"{shot_key}_ume.mp4")
        if os.path.exists(existing_ume) and os.path.getsize(existing_ume) > 0:
            print(f"[SKIP-DUP] {shot_key}: 既にKling LipSync完成済み（二重課金回避）: {existing_ume}")
            clip_paths.append(existing_ume)
            continue
        audio_parts = [p for p in audio_parts if p]
        if not audio_parts:
            print(f"[SKIP] {shot_key}: 音声が無いのでスキップ")
            continue
        audio_combo = os.path.join(OUT_DIR, f"{shot_key}_audio_combo{os.path.splitext(audio_parts[0])[1]}")
        concat_bytes(audio_parts, audio_combo)

        hold_mp4 = os.path.join(OUT_DIR, f"{shot_key}_hold.mp4")
        make_hold_video(shots[shot_key], hold_mp4, seconds)

        est_usd = 0.014 * (5 if seconds <= 5 else 5 * (int(seconds // 5) + 1))  # 5秒切り上げ課金
        if would_exceed(est_usd):
            print(f"[STOP] Kling:{shot_key} で予算超過見込み。停止。")
            break

        video_url = fh.upload_file(hold_mp4, "video/mp4")
        audio_url = fh.upload_file(audio_combo, mimetypes.guess_type(audio_combo)[0] or "audio/mpeg")

        try:
            out = fh.run_sync(
                "fal-ai/kling-video/lipsync/audio-to-video",
                {"video_url": video_url, "audio_url": audio_url},
                timeout=300,
            )
        except Exception as e:
            print(f"[ERROR] Kling:{shot_key} 失敗: {e}")
            print("        (video_url入力のフォーマット・尺制限などをfalのエラーメッセージで確認してください)")
            continue

        record(f"Kling:{shot_key}", est_usd, f"梅・{seconds:.1f}秒ホールド動画+音声")
        out_url = fh.find_url(out)
        if out_url:
            dest = os.path.join(OUT_DIR, f"{shot_key}_ume.mp4")
            fh.download(out_url, dest)
            clip_paths.append(dest)
            print(f"  -> {dest}")
        else:
            print(f"[WARN] {shot_key} の出力URLが見つからない: {json.dumps(out)[:400]}")

    final = os.path.join(OUT_DIR, "ume_15s.mp4")
    if clip_paths:
        concat_bytes(clip_paths, final)
        print(f"[DONE] 梅版（単純結合）: {final}")
    return final if clip_paths else None


# ---------- ④ 竹：Seedance 2.0 mini（sh09で実測済み・sh10/sh11も同様に追加して15秒フルへ） ----------

TAKE_PROMPTS = {
    "sh09": "A puppet-like animated man in a red velvet coat gestures dramatically, mouth moving as if shouting joyfully, camera fixed, subtle natural motion.",
    "sh10": "A puppet-like animated man in a red velvet coat argues with a woman, both gesturing emotionally, camera fixed, subtle natural motion.",
    "sh11": "A puppet-like animated woman speaks calmly and honestly, gentle hand gesture, camera fixed, subtle natural motion.",
}


def run_take(shots):
    print("\n=== 【竹】bytedance/seedance-2.0/mini/image-to-video（3ショット・15秒フル） ===")
    clip_paths = []
    for shot_key in ("sh09", "sh10", "sh11"):
        existing = os.path.join(OUT_DIR, f"{shot_key}_take.mp4")
        if os.path.exists(existing) and os.path.getsize(existing) > 0:
            print(f"[SKIP-DUP] {shot_key}: 既にSeedance2.0生成済み（二重課金回避）: {existing}")
            clip_paths.append(existing)
            continue

        # 480p・5秒 = 最安構成での実測単価をsh09実測（56.6円/5秒）から採用
        est_usd = 0.3605
        if would_exceed(est_usd):
            print(f"[STOP] 竹:{shot_key} で予算超過見込み。ここで竹は打ち切り。")
            break

        image_url = fh.upload_file(shots[shot_key], "image/png")
        prompt = TAKE_PROMPTS[shot_key]
        try:
            out = fh.run_sync(
                "bytedance/seedance-2.0/mini/image-to-video",
                {"prompt": prompt, "image_url": image_url, "resolution": "480p", "duration": "5"},
                timeout=420,
            )
        except Exception as e:
            print(f"[ERROR] 竹:{shot_key} 生成に失敗: {e}")
            continue

        # 注意：実際の請求額はfalダッシュボードでのみ確定する。ここではsh09実測値を単価として概算する。
        record(f"Seedance2.0:{shot_key}", est_usd, "480p・5秒（sh09実測単価を採用。本当の請求額はfalダッシュボードで要確認）")
        out_url = fh.find_url(out)
        if out_url:
            dest = os.path.join(OUT_DIR, f"{shot_key}_take.mp4")
            fh.download(out_url, dest)
            clip_paths.append(dest)
            print(f"  -> {dest}")
        else:
            print(f"[WARN] 竹:{shot_key} の出力URLが見つからない: {json.dumps(out)[:400]}")

    final = os.path.join(OUT_DIR, "take_15s.mp4")
    if clip_paths:
        concat_bytes(clip_paths, final)
        print(f"[DONE] 竹版（単純結合・{len(clip_paths)}ショット）: {final}")
    return final if clip_paths else None


# ---------- ⑤ 松：Seedance 2.5 reference-to-video（1本ずつ実測しながら予算内で追加） ----------

MATSU_PROMPTS = {
    "sh09": "Cinematic camera slowly pushes in on a puppet-like animated man in a red velvet coat, shouting joyfully with dramatic hand gestures, warm moonlit night background.",
    "sh10": "Cinematic camera slowly pushes in on a puppet-like animated man arguing emotionally with a woman, warm moonlit night background.",
    "sh11": "Cinematic camera slowly pushes in on a puppet-like animated woman speaking calmly and honestly, warm moonlit night background.",
}


def run_matsu(shots):
    print("\n=== 【松】bytedance/seedance-2.5/reference-to-video（1本ずつ実測しながら予算内で追加） ===")
    clip_paths = []
    # 720p・5秒での最悪見積り（公式早見表: 720p 約0.28〜0.47ドル/秒）→ 5秒で約1.4〜2.35ドル ≈ 220〜370円
    # 予算300円の大半〜全部を1本で使い切る可能性が高いため、480pでの実測を優先する。
    est_usd_worst_case = 0.13 * 5 + 0.1  # 480p下限側で見積り

    for shot_key in ("sh09", "sh10", "sh11"):
        existing = os.path.join(OUT_DIR, f"{shot_key}_matsu.mp4")
        if os.path.exists(existing) and os.path.getsize(existing) > 0:
            print(f"[SKIP-DUP] {shot_key}: 既にSeedance2.5生成済み（二重課金回避）: {existing}")
            clip_paths.append(existing)
            continue

        if would_exceed(est_usd_worst_case):
            print(f"[STOP] 松:{shot_key} で予算超過見込み。ここで松は打ち切り。")
            break

        image_url = fh.upload_file(shots[shot_key], "image/png")
        prompt = MATSU_PROMPTS[shot_key]
        try:
            out = fh.run_sync(
                "bytedance/seedance-2.5/reference-to-video",
                {"prompt": prompt, "image_urls": [image_url], "resolution": "480p", "duration": "5"},
                timeout=420,
            )
        except Exception as e:
            print(f"[ERROR] 松:{shot_key} 生成に失敗: {e}")
            print("        (2026-09-06 419番: 1回目は reference_image_url で HTTP422")
            print("         'At least one reference image or video is required' → image_urls(配列)に修正済み。")
            print("         それでも失敗する場合は fal.ai/models/bytedance/seedance-2.5/reference-to-video/api を再確認)")
            continue

        record(f"Seedance2.5:{shot_key}(実測)", est_usd_worst_case, "480p・5秒（本当の請求額はfalダッシュボードで要確認）")
        out_url = fh.find_url(out)
        if out_url:
            dest = os.path.join(OUT_DIR, f"{shot_key}_matsu.mp4")
            fh.download(out_url, dest)
            clip_paths.append(dest)
            print(f"  -> {dest}")
        else:
            print(f"[WARN] 松:{shot_key} の出力URLが見つからない: {json.dumps(out)[:400]}")

    final = os.path.join(OUT_DIR, "matsu_15s.mp4")
    if clip_paths:
        concat_bytes(clip_paths, final)
        print(f"[DONE] 松版（単純結合・{len(clip_paths)}ショット）: {final}")
    return final if clip_paths else None


def write_cost_report(ume_ok, take_ok, matsu_ok):
    path = os.path.join(OUT_DIR, "cost_matsutakeume.md")
    lines = []
    lines.append("# 409番 卵劇場EP01・松竹梅コスト報告\n")
    lines.append(f"実行時刻: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("## 生成ログ\n")
    for e in COST_LOG:
        lines.append(f"- {e['t']} {e['label']}: ${e['usd']:.4f} = {e['jpy']:.1f}円  {e['note']}\n")
    lines.append(f"\n## 累計: 約{total_jpy():.1f}円（上限300円）\n")
    lines.append("\n## 結果\n")
    lines.append(f"- 梅（Kling LipSync）: {'完成 ' + ume_ok if ume_ok else '未完成/失敗'}\n")
    lines.append(f"- 竹（Seedance 2.0 mini, 実測1本）: {'完成 ' + take_ok if take_ok else '未完成/失敗 または予算超過で未実行'}\n")
    lines.append(f"- 松（Seedance 2.5 reference-to-video, 実測1本）: {'完成 ' + matsu_ok if matsu_ok else '未完成/失敗 または予算超過で未実行'}\n")
    lines.append("\n※実際の請求額はfal.aiダッシュボードでのみ確定します。上記は早見表の単価からの概算です。\n")
    with open(path, "w") as f:
        f.writelines(lines)
    print(f"\n[REPORT] {path}")
    return path


def _finalize(ume, take, matsu):
    """途中で例外が起きても、そこまでの成果を必ず書き出す（外部状態への保存・冪等原則）。"""
    report = write_cost_report(ume, take, matsu)
    try:
        os.makedirs(DRIVE_DIR, exist_ok=True)
        import shutil
        for name, path in [("ume_15s.mp4", ume), ("take_15s.mp4", take), ("matsu_15s.mp4", matsu)]:
            if path and os.path.exists(path):
                shutil.copy(path, os.path.join(DRIVE_DIR, name))
        shutil.copy(report, os.path.join(DRIVE_DIR, "cost_matsutakeume.md"))
        print(f"[DRIVE] コピー完了: {DRIVE_DIR}")
    except Exception as e:
        print(f"[DRIVE] コピー失敗（Google Drive未マウント等の可能性）: {e}")
    print(f"\n累計 {total_jpy():.1f}円 / 上限{BUDGET_JPY}円")


def main():
    print(f"予算上限: {BUDGET_JPY}円")
    shots = crop_shots()

    ume = None
    take = None
    matsu = None
    try:
        tts_paths = run_tts_all()
        ume = run_ume(tts_paths)
        # 2026-09-06 419番: 松(Seedance2.5)は単価が竹(Seedance2.0)より高く、
        # 竹を先に使い切ると松の実測すら1本もできなくなる。
        # 「Seedanceの実単価を実測する」目的を優先し、松を先に1本以上試す。
        if total_jpy() < BUDGET_JPY:
            matsu = run_matsu(shots)
        if total_jpy() < BUDGET_JPY:
            take = run_take(shots)
    finally:
        _finalize(ume, take, matsu)

    print("完了。確認ページ用に output/ フォルダの中身を使ってください。")


if __name__ == "__main__":
    main()
