# 宇宙うんこ v2：曲の打ち込み → 「当たり（跳ねる瞬間）」の表 hits.json と、自前合成の音 wav
# 曲はサティ「ジムノペディ第1番」（1888年作曲・パブリックドメイン）。録音は使わず、音も全部ここで作る。
# 型：KYOKU（曲の中身）を差し替えれば別の曲になる。1拍＝ちょうど BEAT_FR コマ にそろえるので、
#     当たりの瞬間は必ず整数コマに乗る（映像と音のズレが原理的に 0 コマ）。
import json, sys, numpy as np, wave
FPS = 24
BEAT_FR = 22                 # 1拍＝22コマ＝0.9167秒（約65.5 BPM・「ゆっくり、悲しげに」）
LEAD_FR = 30                 # 最初の当たりまで（1.25秒）
TAIL = 3.0                   # 最後の当たりのあと余韻
B = BEAT_FR / FPS
def m(n):
    names = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
    return 12*(int(n[-1])+1) + names[n[:-1]]
# ---- 曲（小節, 拍, 音名, 長さ[拍], 強さ）----
def kyoku_gymnopedie():
    ev = []
    BARS = 10
    for b in range(BARS):
        if b == BARS-1:   # 終わり：G の和音で静かに閉じる
            ev += [(b,0,'G2',4,0.8),(b,0,'B3',4,0.4),(b,0,'D4',4,0.4),(b,0,'F#4',4,0.4)]; continue
        if b % 2 == 0: ev += [(b,0,'G2',3,0.85)] + [(b,1,x,2,0.42) for x in ('B3','D4','F#4')]
        else:          ev += [(b,0,'D2',3,0.85)] + [(b,1,x,2,0.42) for x in ('A3','C#4','F#4')]
    mel = [(2,1,'F#5',1),(2,2,'A5',1),(3,0,'G5',1),(3,1,'F#5',1),(3,2,'C#5',1),
           (4,0,'B4',1),(4,1,'C#5',1),(4,2,'D5',1),(5,0,'A4',3),(6,0,'F#4',3),(7,0,'F#4',3),(8,1,'F#5',1),(8,2,'A5',1),(9,0,'G5',4)]
    for bar,beat,n,d in mel: ev.append((bar,beat,n,d,1.0))
    return {"title":"Gymnopédie No.1","composer":"Erik Satie","year":1888,"beats_per_bar":3,"ev":ev}
KYOKU = {"gymnopedie": kyoku_gymnopedie}
name = sys.argv[1] if len(sys.argv) > 1 else "gymnopedie"
K = KYOKU[name]()
BPB = K["beats_per_bar"]
notes = []
for bar,beat,n,d,v in K["ev"]:
    fr = LEAD_FR + (bar*BPB + beat)*BEAT_FR
    notes.append({"fr":fr,"t":fr/FPS,"name":n,"midi":m(n),"dur":d*B,"vel":v,"mel":v>=1.0})
notes.sort(key=lambda e:(e["fr"],e["midi"]))
# 同じ瞬間に始まる音は「1回の当たり」にまとめる（うんこが1回跳ねると、その瞬間の音が全部鳴る）
hits = []
for e in notes:
    if hits and hits[-1]["fr"] == e["fr"]: hits[-1]["notes"].append(e)
    else: hits.append({"fr":e["fr"],"t":e["t"],"notes":[e]})
for h in hits:
    mels = [e for e in h["notes"] if e["mel"]]
    top = max(h["notes"], key=lambda e:e["midi"])
    h["key"] = (mels[0] if mels else top)["midi"]      # 板の音の高さ（色・長さに使う）
    h["kind"] = "mel" if mels else ("bass" if len(h["notes"])==1 or min(e["midi"] for e in h["notes"])<45 and len(h["notes"])>=1 and all(e["midi"]<45 or not e["mel"] for e in h["notes"]) and h["notes"][0]["midi"]<45 else "chord")
    h["names"] = [e["name"] for e in h["notes"]]
END = hits[-1]["t"] + TAIL
NF = int(round(END*FPS))
json.dump({"kyoku":{k:K[k] for k in ("title","composer","year")},"fps":FPS,"beat_fr":BEAT_FR,"nf":NF,"end":END,"hits":hits},
          open("hits.json","w"), ensure_ascii=False, indent=1)

# ---- 音：レイ・ハラカミ風（丸いFMの電子ピアノ＋入りの小さなピッチの揺れ＋こもったテープディレイ）----
SR = 48000; N = int(END*SR); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(3)
def onepole(x, fc):
    a = np.exp(-2*np.pi*fc/SR); y = np.empty_like(x); s = 0.0
    # 速度のためにブロック無しの単純実装（音は短いので十分）
    for i in range(len(x)): s = (1-a)*x[i] + a*s; y[i] = s
    return y
def voice(midi, dur, vel):
    f = 440*2**((midi-69)/12)
    n = int(min(5.0, dur+2.2)*SR); t = np.arange(n)/SR
    bend = 2**((-0.22*np.exp(-t/0.05) + 0.06*np.sin(2*np.pi*4.3*t)*np.minimum(1,t/0.6)*0.5)/12)  # 入りで少し下から滑り込む
    ph = 2*np.pi*np.cumsum(f*bend)/SR
    idx = (1.5 + 1.0*vel)*np.exp(-t/0.35) + 0.25                   # 当たりで少しだけ明るく、すぐ丸くなる
    mod = np.sin(ph*1.0 + 0.3)                                     # 1:1 で柔らかい倍音
    car = np.sin(ph + idx*mod)
    tine = 0.10*np.sin(ph*7.0)*np.exp(-t/0.03)                     # ごく小さな「コン」
    hi = 1.0 if midi < 48 else 0.0
    sub = hi*0.6*np.sin(ph*0.5 if midi>=36 else ph)*np.exp(-t/1.6)
    dec = np.exp(-t/(1.1 + 1.0*(72-min(midi,72))/36))
    rel = np.clip((dur+0.35 - t)/0.6 + 1, 0, 1)                    # 音価のあとゆっくり消える
    att = np.minimum(1, t/0.006)
    return (car*0.8 + tine + sub)*dec*rel*att*vel
for k,h in enumerate(hits):
    for e in h["notes"]:
        v = voice(e["midi"], e["dur"], e["vel"])
        g = (0.55 if e["midi"] < 48 else (0.30 if not e["mel"] else 0.42))
        pan = 0.5 + (0.18 if k%2 else -0.18)*(1 if e["mel"] else 0.4)
        i = int(round(e["t"]*SR)); j = min(N, i+len(v))
        L[i:j] += v[:j-i]*g*(1-pan)*1.4; R[i:j] += v[:j-i]*g*pan*1.4
# ローパスで丸く
from numpy.fft import rfft, irfft
def lp(x, fc):
    X = rfft(x); fr = np.fft.rfftfreq(len(x), 1/SR); X *= 1/np.sqrt(1+(fr/fc)**4); return irfft(X, len(x))
L = lp(L, 3200); R = lp(R, 3200)
# テープディレイ（付点8分・こもった返り・左右に振る）
d = int(0.75*B*SR); fb = 0.38
dl = np.zeros(N); dr = np.zeros(N)
srcL, srcR = L.copy(), R.copy()
for rep in range(1, 6):
    sh = d*rep; g = fb**rep
    if sh >= N: break
    a = lp(np.concatenate([np.zeros(sh), (srcR if rep%2 else srcL)[:N-sh]]), 2200/rep**0.5)*g
    b_ = lp(np.concatenate([np.zeros(sh), (srcL if rep%2 else srcR)[:N-sh]]), 2200/rep**0.5)*g
    dl += a; dr += b_
# 部屋の響き（短い拡散）
ir_n = int(2.4*SR); ir = rng.standard_normal(ir_n)*np.exp(-np.arange(ir_n)/SR/0.7); ir = lp(ir, 4000); ir /= np.abs(ir).sum()/5
def conv(x): return irfft(rfft(x, 2*N)*rfft(ir, 2*N))[:N]
outL = L + 0.45*dl + 0.22*conv(L+R)
outR = R + 0.45*dr + 0.22*conv(L+R)*0.97
# ほんの少しのテープ飽和とノイズ床
out = np.stack([outL, outR], 1); out /= np.abs(out).max()
out = np.tanh(out*1.3)/np.tanh(1.3)
out += rng.standard_normal(out.shape)*0.0012
fade = int(2.0*SR); out[-fade:] *= np.linspace(1,0,fade)[:,None]
out *= 0.89/np.abs(out).max()
with wave.open("oto.wav","wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out*32767).astype('<i2').tobytes())
print(len(hits), "hits", len(notes), "notes", "end", round(END,2), "NF", NF)
