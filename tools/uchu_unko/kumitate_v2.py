# 連番 → 文字（隅に小さく）→ 音と合わせて MP4。あわせて「なめらかさ」と「音ズレ」を測って zure.json に書く。
# 使い方: python3 kumitate_v2.py <連番フォルダ> <出力mp4>
import glob, json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
FRD, OUT = sys.argv[1], sys.argv[2]
D = json.load(open(os.path.join(HERE, "hits.json"))); FPS = D["fps"]; NF = D["nf"]
W, H = 720, 1280
FR = sorted(glob.glob(os.path.join(FRD, "f*.jpg")))
nums = [int(os.path.basename(p)[1:5]) for p in FR]
missing = sorted(set(range(1, NF + 1)) - set(nums))
LORA = "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf"; LORAI = "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf"
MIN = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
SHU = (193, 68, 46); KINARI = (237, 230, 214)
def f(p, s): return ImageFont.truetype(p, s)
def spaced(d, xy, text, font, fill, sp):
    x, y = xy
    for ch in text: d.text((x, y), ch, font=font, fill=fill); x += d.textlength(ch, font=font) + sp
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
K = D["kyoku"]
spaced(d, (44, 52), "COSMIC POOP", f(LORA, 12), SHU + (255,), 4.2)
d.text((44, 72), K["title"], font=f(LORA, 25), fill=KINARI + (235,))
d.text((45, 104), K["composer"], font=f(LORAI, 14), fill=KINARI + (170,))
spaced(d, (44, H - 92), "宇宙うんこ", f(MIN, 17), KINARI + (225,), 7)
d.text((45, H - 62), "painting — ただのわえ", font=f(MIN, 11), fill=KINARI + (150,))
# 影（明るい滝の上でも読めるように）
sh = layer.split()[3].point(lambda a: int(a * 0.55))
from PIL import ImageFilter
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(3)))
def frame(i):
    p = os.path.join(FRD, "f%04d.jpg" % i)
    if not os.path.exists(p):   # 抜けたコマは直前を使う（数を記録）
        j = i
        while j > 1 and not os.path.exists(os.path.join(FRD, "f%04d.jpg" % j)): j -= 1
        p = os.path.join(FRD, "f%04d.jpg" % j)
    im = Image.open(p).convert("RGB")
    if im.size != (W, H): im = im.resize((W, H), Image.LANCZOS)
    im.paste(shadow, (1, 1), shadow); im.paste(layer, (0, 0), layer); return im
cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
       "-i", os.path.join(HERE, "oto.wav"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow",
       "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT]
pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(1, NF + 1): pr.stdin.write(frame(i).tobytes())
pr.stdin.close(); pr.wait()
# ---- 測る ----
# 音：wav の立ち上がりを探し、楽譜の当たりの時刻との差（ms）
with wave.open(os.path.join(HERE, "oto.wav")) as w:
    sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, w.getnchannels()).mean(1) / 32768
hop = int(sr * 0.001); env = np.sqrt(np.convolve(x * x, np.ones(hop * 3) / (hop * 3), 'same'))[::hop]
on = []
for h in D["hits"]:
    c = int(h["t"] * 1000); seg = env[max(0, c - 60): c + 60]; dv = np.diff(seg)
    k = int(np.argmax(dv)) + max(0, c - 60); on.append(k - c)
kiroku = json.load(open(os.path.join(FRD, "_kiroku.json")))
vis = [c["lowest_fr"] - c["hit_fr"] for c in kiroku["contact"]]
gap = [abs(c["gap_m"]) for c in kiroku["contact"]]
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate,nb_frames", "-of", "json", OUT], capture_output=True, text=True).stdout
res = {"fps": FPS, "frames_expected": NF, "frames_rendered": len(FR), "frames_missing": len(missing),
       "video_stream": json.loads(probe)["streams"][0],
       "oto_onset_vs_gakufu_ms": {"max_abs": int(max(abs(v) for v in on)), "values": on},
       "eizou_chakuchi_vs_gakufu_frames": {"max_abs": max(abs(v) for v in vis), "values": vis},
       "chakuchi_sukima_m_max": max(gap)}
json.dump(res, open(os.path.join(HERE, "zure.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k not in ("oto_onset_vs_gakufu_ms", "eizou_chakuchi_vs_gakufu_frames")}, ensure_ascii=False),
      "oto_max_ms", res["oto_onset_vs_gakufu_ms"]["max_abs"], "eizou_max_fr", res["eizou_chakuchi_vs_gakufu_frames"]["max_abs"])
# サムネ
frame(min(NF, D["hits"][9]["fr"])).save(OUT.replace(".mp4", "_still.png"))
