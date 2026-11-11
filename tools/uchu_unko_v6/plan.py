# -*- coding: utf-8 -*-
"""宇宙うんこ v6「灯籠の川」— 10秒1場面の道・跳ね・カメラ・当たり判定（bpy を使わない。Blender からも sandbox からも読む）
単位はメートル。24fps・240コマ（10秒）。川は +x へ流れる。カメラは手前（-y）から奥を見て、左へ回り込む。
"""
import math, random

FPS = 24
NF = 240                 # 場面のコマ数（10秒）
DRIFT = (0.045, 0.006)   # 灯籠の流れ（m/s）

# 灯籠の寸法
BASE_W = 0.30; BASE_T = 0.035; BASE_Z0 = -0.012      # 木の台（水に少し沈む）
BOX_W = 0.24; BOX_Z0 = BASE_Z0 + BASE_T; BOX_H = 0.27  # 紙の箱
LID_Z = BOX_Z0 + BOX_H + 0.012                         # ふたの上面（うんこが座る高さ）

# うんこ（当たり判定は底からの高さと半径の球3つ）
US = 1.3   # うんこの大きさの倍率
UNKO_SPH = [(0.055 * US, 0.085 * US), (0.115 * US, 0.068 * US), (0.170 * US, 0.042 * US)]
UNKO_H = 0.215 * US

# 着地（コマ番号, その時の灯籠の中心 x, y, 音の高さ）
LAND = [
    (30,  -0.62, 0.30, 0),
    (64,  -0.20, 0.78, 2),
    (96,   0.28, 0.50, 4),
    (124,  0.58, 1.02, 3),
    (152,  1.00, 0.70, 5),
    (196,  1.30, 1.22, 7),
]
SIT = 9   # 着地してから跳び立つまでのコマ

def t_of(f): return f / FPS

def bob(f, land_frames):
    """着地された灯籠の沈み込み（m）。"""
    z = 0.0
    for lf in land_frames:
        dt = t_of(f - lf)
        if dt >= 0:
            z += -0.040 * math.exp(-dt / 0.55) * math.sin(2 * math.pi * dt / 0.75)
    return z

def lantern_xy(l, f):
    t = t_of(f)
    x = l["x0"] + DRIFT[0] * t + 0.012 * math.sin(0.7 * t + l["ph"])
    y = l["y0"] + DRIFT[1] * t + 0.010 * math.sin(0.5 * t + 1.7 * l["ph"])
    return x, y

def lantern_z(l, f):
    t = t_of(f)
    return 0.006 * math.sin(1.3 * t + l["ph"]) + bob(f, l.get("lands", []))

def build_lanterns(seed=7):
    rnd = random.Random(seed)
    L = []
    # 跳ね台の灯籠（着地の時刻にその場所へ来るように逆算）
    for i, (lf, x, y, n) in enumerate(LAND):
        l = {"id": "step%d" % i, "ph": rnd.uniform(0, 6.28), "lands": [lf], "step": i}
        t = t_of(lf)
        l["x0"] = x - DRIFT[0] * t - 0.012 * math.sin(0.7 * t + l["ph"])
        l["y0"] = y - DRIFT[1] * t - 0.010 * math.sin(0.5 * t + 1.7 * l["ph"])
        L.append(l)
    # まわりの灯籠（手前のぼけ・奥の列）
    tries = 0
    while len(L) < 64 and tries < 20000:
        tries += 1
        x0 = rnd.uniform(-4.5, 4.5); y0 = rnd.uniform(-0.9, 5.2)
        l = {"id": "f%d" % len(L), "x0": x0, "y0": y0, "ph": rnd.uniform(0, 6.28), "lands": []}
        ok = True
        for o in L:
            if math.hypot(o["x0"] - x0, o["y0"] - y0) < 0.46: ok = False; break
        if not ok: continue
        # 跳ねの道から離す（全コマで判定するのは check で。ここは大まかに）
        if path_clear(l) and camera_clear(l):
            L.append(l)
    return L

# ---- うんこの道 ----
def unko_at(f, lanterns):
    """コマ f のうんこの底の中心 (x,y,z)、伸び縮み (sx, sz)、回転（z, rad）"""
    steps = [l for l in lanterns if "step" in l]
    steps.sort(key=lambda l: l["step"])
    # 最初の落下
    lf0 = LAND[0][0]
    if f <= lf0:
        l = steps[0]; x1, y1 = lantern_xy(l, lf0); z1 = LID_Z + lantern_z(l, lf0)
        s = f / lf0
        x = x1 - 0.35 * (1 - s); y = y1 + 0.25 * (1 - s)
        z = z1 + 2.6 * (1 - s * s)
        st = 1.0 + 0.25 * s
        return (x, y, z), (1 / math.sqrt(st), st), 0.9 * (1 - s)
    for i in range(len(LAND)):
        lf = LAND[i][0]
        nxt = LAND[i + 1][0] if i + 1 < len(LAND) else None
        to = lf + SIT
        if nxt is None or f <= to:
            if f < lf: continue
            l = steps[i]; x, y = lantern_xy(l, f); z = LID_Z + lantern_z(l, f)
            dt = t_of(f - lf)
            sq = 0.30 * math.exp(-dt / 0.16) * math.cos(2 * math.pi * dt / 0.42)  # 着地のつぶれ
            if nxt is not None:
                pre = max(0.0, (f - (to - 4)) / 4.0)  # 跳ぶ前に沈む
                sq += 0.12 * pre
            if nxt is None:
                sq += 0.0
            sz = 1 - sq; sx = 1 / math.sqrt(max(sz, 0.3))
            return (x, y, z), (sx, sz), 0.0
        if to < f < nxt:
            la = steps[i]; lb = steps[i + 1]
            xa, ya = lantern_xy(la, to); za = LID_Z + lantern_z(la, to)
            xb, yb = lantern_xy(lb, nxt); zb = LID_Z + lantern_z(lb, nxt)
            s = (f - to) / (nxt - to)
            H = 0.30 + 0.05 * (i % 3)
            x = xa + (xb - xa) * s; y = ya + (yb - ya) * s
            z = za + (zb - za) * s + 4 * H * s * (1 - s)
            st = 1 + 0.18 * (1 - 2 * s) if s < 0.5 else 1 - 0.10 * (2 * s - 1) + 0.0
            st = max(st, 0.9)
            spin = 2 * math.pi * s * (1 if i % 2 == 0 else -1) * 0.5
            return (x, y, z), (1 / math.sqrt(st), st), spin
    return unko_at(NF, lanterns)

# ---- カメラ ----
def smooth(vals, k):
    out = []
    for i in range(len(vals)):
        a = max(0, i - k); b = min(len(vals), i + k + 1)
        out.append(sum(vals[a:b]) / (b - a))
    return out

def ease(s): return s * s * (3 - 2 * s)

def camera_track(lanterns):
    """各コマのカメラ位置・注視点・焦点距離。うんこを中心に左へ約55°回り込み、最後に上がって川を見せる。"""
    ux, uy, uz = [], [], []
    for f in range(NF + 1):
        (x, y, z), _, _ = unko_at(f, lanterns)
        ux.append(x); uy.append(y); uz.append(z)
    ux = smooth(ux, 18); uy = smooth(uy, 18); uz = smooth(uz, 22)
    cams = []
    for f in range(NF + 1):
        s = f / NF
        th = math.radians(-98 + 52 * ease(s))
        R = 1.55 + 0.25 * ease(s) + 0.9 * ease(max(0, (f - 186) / 54.0))
        cx, cy = ux[f] * 0.75 + 0.15, uy[f] * 0.6 + 0.25
        rise = ease(max(0, (f - 180) / 60.0))
        h = 0.26 + 0.10 * ease(s) + 0.85 * rise
        px = cx + R * math.cos(th); py = cy + R * math.sin(th)
        tz = min(uz[f], 0.9) * 0.55 + 0.22 - 0.05 * rise
        tx = ux[f] * 0.8 + cx * 0.2; ty = uy[f] * 0.8 + cy * 0.2
        cams.append({"loc": (px, py, h), "look": (tx, ty, tz), "lens": 30.0 - 3.0 * rise})
    return cams

def camera_clear(l):
    return True  # check() で全コマ確かめる（作る時には使わない）

def path_clear(l, margin=0.10):
    """候補の灯籠が、うんこの道（跳ね台どうしを結ぶ線）から十分離れているか（大まか）。"""
    for i in range(len(LAND) - 1):
        _, xa, ya, _ = LAND[i]; _, xb, yb, _ = LAND[i + 1]
        # 灯籠は流れるので、その区間の時刻での位置で比べる
        tm = t_of((LAND[i][0] + LAND[i + 1][0]) / 2)
        x = l["x0"] + DRIFT[0] * tm; y = l["y0"] + DRIFT[1] * tm
        dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
        u = max(0, min(1, ((x - xa) * dx + (y - ya) * dy) / L2))
        d = math.hypot(x - (xa + u * dx), y - (ya + u * dy))
        if d < 0.30 + margin: return False
    # 最初の落下の筋
    x = l["x0"] + DRIFT[0] * 1.0; y = l["y0"]
    if math.hypot(x - LAND[0][1], y - LAND[0][2]) < 0.6: return False
    return True

# ---- 点検 ----
def box_sphere_gap(cx, cy, cz, r, lx, ly, z0, z1, half):
    dx = max(abs(cx - lx) - half, 0); dy = max(abs(cy - ly) - half, 0)
    dz = max(z0 - cz, 0, cz - z1)
    return math.sqrt(dx * dx + dy * dy + dz * dz) - r

def check(lanterns, sub=4):
    rep = {"unko_lantern_min_gap": 9, "unko_hit": [], "cam_lantern_min": 9, "cam_hit": [],
           "lantern_pair_min": 9, "cam_z_min": 9, "unko_below_lid": []}
    cams = camera_track(lanterns)
    half = BASE_W / 2 * 1.02
    for k in range(NF * sub + 1):
        f = k / sub
        fi = int(round(f))
        (x, y, z), (sx, sz), _ = unko_at(f, lanterns)
        for l in lanterns:
            lx, ly = lantern_xy(l, f); lz = lantern_z(l, f)
            # 乗っている／乗る瞬間の台は「ふたより下に入らない」を別に見る
            on = False
            if "step" in l:
                i = l["step"]; lf = LAND[i][0]
                to = lf + SIT; nxt = LAND[i + 1][0] if i + 1 < len(LAND) else 10 ** 9
                if lf - 0.5 <= f <= to + 0.5 or (i + 1 == len(LAND) and f >= lf - 0.5):
                    on = True
                    if z < LID_Z + lz - 1e-6: rep["unko_below_lid"].append(round(f, 2))
            if on: continue
            for (hz, r) in UNKO_SPH:
                g = box_sphere_gap(x, y, z + hz * sz, r * sx, lx, ly, BASE_Z0 + lz, LID_Z + lz, half)
                # 跳ぶ直前・直後の自分の台との近さは除外（台の上から出入りする）
                if "step" in l:
                    i = l["step"]
                    lf = LAND[i][0]
                    if abs(f - lf) < 3 or abs(f - (lf + SIT)) < 3: continue
                if g < rep["unko_lantern_min_gap"]: rep["unko_lantern_min_gap"] = g
                if g < 0: rep["unko_hit"].append((round(f, 2), l["id"]))
    for f in range(NF + 1):
        c = cams[f]["loc"]
        rep["cam_z_min"] = min(rep["cam_z_min"], c[2])
        for l in lanterns:
            lx, ly = lantern_xy(l, f)
            d = math.hypot(c[0] - lx, c[1] - ly)
            if c[2] < LID_Z + 0.25:
                rep["cam_lantern_min"] = min(rep["cam_lantern_min"], d)
                if d < 0.45: rep["cam_hit"].append((f, l["id"]))
    for i in range(len(lanterns)):
        for j in range(i + 1, len(lanterns)):
            for f in (0, 120, 240):
                a = lantern_xy(lanterns[i], f); b = lantern_xy(lanterns[j], f)
                rep["lantern_pair_min"] = min(rep["lantern_pair_min"], math.hypot(a[0] - b[0], a[1] - b[1]))
    rep["unko_hit"] = rep["unko_hit"][:20]; rep["cam_hit"] = rep["cam_hit"][:20]
    rep["unko_below_lid"] = rep["unko_below_lid"][:20]
    return rep

def build():
    """カメラにぶつかる灯籠を除いて、確定の灯籠一覧を返す。"""
    L = build_lanterns()
    cams = camera_track(L)
    keep = []
    for l in L:
        bad = False
        if "step" not in l:
            for f in range(0, NF + 1, 2):
                c = cams[f]["loc"]; lx, ly = lantern_xy(l, f)
                if math.hypot(c[0] - lx, c[1] - ly) < 0.95: bad = True; break
        if not bad: keep.append(l)
    return keep

if __name__ == "__main__":
    import json, sys
    L = build()
    r = check(L)
    print(len(L), "lanterns")
    print(json.dumps(r, ensure_ascii=False, indent=1))
