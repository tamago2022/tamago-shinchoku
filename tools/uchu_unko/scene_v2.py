# 宇宙うんこ v2（Blender 4.1 EEVEE / 4.2 Cycles どちらでも動く）
# グミのように跳ねる宇宙うんこが、滝の段々の鉄琴を叩きながら下り、霧を抜けて夜の雲海へ。
# 使い方: Blender -b -P scene_v2.py -- <v2フォルダ> <出力フォルダ> <all | 1-100 | 5,60> [kata.json]
# 環境変数: UU_ENGINE=EEVEE|CYCLES  UU_PCT=100  UU_SAMPLES=24  UU_STEP=1  UU_SAVE=1(.blendも保存)
import bpy, json, math, random, sys, os, time
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
WORK, OUT, FR = argv[0], argv[1], argv[2]
KATA = json.load(open(argv[3] if len(argv) > 3 else os.path.join(WORK, "kata.json")))
D = json.load(open(os.path.join(WORK, KATA["kyoku"])))
FPS = D["fps"]; NF = D["nf"]; HITS = D["hits"]
PAINT = os.environ.get("UU_PAINT") or os.path.abspath(os.path.join(WORK, KATA["paint"]))
MI = KATA["michi"]; rnd = random.Random(MI["seed"])
ENG = os.environ.get("UU_ENGINE", "EEVEE")

# 版の違い（3.6 と 4.x で入力の名前が違う）を吸収する
ALIAS = {"Emission Color": "Emission", "Subsurface Weight": "Subsurface", "Coat Weight": "Clearcoat",
         "Coat Roughness": "Clearcoat Roughness", "Specular IOR Level": "Specular", "Transmission Weight": "Transmission"}
def I(node, key):
    try: return node.inputs[key]
    except KeyError: return node.inputs[ALIAS.get(key, key)]
T0 = time.time()
def stage(x): print("STAGE", x, round(time.time() - T0, 1), flush=True)

# ---------------- 場の初期化 ----------------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
eng_ok = None
if ENG == "EEVEE":
    for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try: sc.render.engine = e; eng_ok = e; break
        except Exception: pass
else:
    sc.render.engine = "CYCLES"; eng_ok = "CYCLES"
print("ENGINE", eng_ok, bpy.app.version_string, flush=True)
EV = sc.eevee
def tryset(obj, **kw):
    for k, v in kw.items():
        try: setattr(obj, k, v)
        except Exception as ex: print("skip", k, ex)
tryset(EV, taa_render_samples=int(os.environ.get("UU_SAMPLES", "32")), use_bloom=True, bloom_intensity=0.06,
       bloom_threshold=0.9, bloom_radius=6.0, use_gtao=True, gtao_distance=0.6, use_ssr=True,
       use_soft_shadows=True, use_volumetric_shadows=True, volumetric_tile_size='8', volumetric_samples=32,
       volumetric_start=0.5, volumetric_end=60.0, use_motion_blur=os.environ.get('UU_MB','0')=='1', motion_blur_shutter=0.45,
       shadow_cube_size='1024', shadow_cascade_size='2048')
if eng_ok == "CYCLES":
    c = sc.cycles
    tryset(c, samples=int(os.environ.get("UU_SAMPLES", "24")), use_denoising=True, denoiser='OPENIMAGEDENOISE',
           max_bounces=4, diffuse_bounces=1, glossy_bounces=1, transmission_bounces=2, volume_bounces=0,
           caustics_reflective=False, caustics_refractive=False, use_adaptive_sampling=True, adaptive_threshold=0.05,
           device=os.environ.get("UU_DEVICE", "CPU"), volume_step_rate=4.0)
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.4
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.resolution_percentage = int(os.environ.get("UU_PCT", "100"))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = NF
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
try: sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    try: sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
    except Exception: pass

def newmat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]
def pin(p, key, v):
    try: I(p, key).default_value = v
    except Exception as ex: print("pin", key, ex)
def link(nt, a, b): nt.links.new(a, b)
def blend(m, mode='BLEND'):
    tryset(m, blend_method=mode, shadow_method='NONE', show_transparent_back=False, use_backface_culling=False)
def hide_between(o, f_on, f_off):
    """f_on〜f_off の間だけ見える"""
    for f, v in ((1, True), (max(1, f_on - 1), True), (f_on, False), (f_off, False), (f_off + 1, True)):
        if f < 1: continue
        o.hide_render = v; o.keyframe_insert("hide_render", frame=f)
        o.hide_viewport = v; o.keyframe_insert("hide_viewport", frame=f)

stage('michi')
# ---------------- 道（当たりの位置）----------------
# 仮想の一本道で計算 → 舞台Bの区間は SHIFT だけ離れた場所に置く（霧の白で隠して瞬間移動）
SPLIT = KATA["butai"][0]["made"]          # このヒット番号までが舞台A
SHIFT = Vector((0, 0, -400))
P = []; cur = Vector((0, 0, 0)); side = 1
for i, h in enumerate(HITS):
    if i == 0: P.append(cur.copy()); continue
    nb = round((h["fr"] - HITS[i - 1]["fr"]) / D["beat_fr"])
    side = -side
    if i <= SPLIT:
        dz = -(MI["kudari_1"] if nb == 1 else MI["kudari_2"]) * rnd.uniform(0.85, 1.15)
        dx = side * MI["yoko"] * rnd.uniform(0.6, 1.0) * (1.0 if nb == 1 else 1.4)
        dy = rnd.uniform(-0.15, 0.25)
    elif i == SPLIT + 1:      # 霧の中への大落下（仮想座標で連続）
        dz, dx, dy = -7.0, side * 0.6, 0.6
    else:
        dz = MI["nobori_B"] * rnd.uniform(0.6, 1.4) + (0.6 if nb > 1 else 0)
        dx = side * MI["yoko"] * rnd.uniform(0.7, 1.1) * (1.0 if nb == 1 else 1.5)
        dy = rnd.uniform(0.2, 0.6)
    cur = cur + Vector((dx, dy, dz)); P.append(cur.copy())
SWITCH = (HITS[SPLIT]["fr"] + HITS[SPLIT + 1]["fr"]) // 2 + 4     # 白くなりきった瞬間に舞台を入れ替える
def actual(v, f): return v + SHIFT if f >= SWITCH else v
PA = [P[i] for i in range(SPLIT + 1)]
PB = [P[i] + SHIFT for i in range(SPLIT + 1, len(P))]

# ---------------- うんこの軌道（放物線・当たりの瞬間＝整数コマ）----------------
G = 9.8
UNKO_H = 0.56
def pos_virtual(f):
    """仮想座標でのうんこの底の位置と速度"""
    f0 = HITS[0]["fr"]
    if f <= f0:   # 空から落ちてくる
        t = (f - f0) / FPS
        return P[0] + Vector((0, 0, 0.5 * G * t * t)), Vector((0, 0, G * t)), None
    for i in range(len(HITS) - 1):
        a, b = HITS[i]["fr"], HITS[i + 1]["fr"]
        if a <= f <= b:
            T = (b - a) / FPS; t = (f - a) / FPS
            d = P[i + 1] - P[i]
            vz0 = (d.z + 0.5 * G * T * T) / T
            p = P[i] + Vector((d.x * t / T, d.y * t / T, vz0 * t - 0.5 * G * t * t))
            v = Vector((d.x / T, d.y / T, vz0 - G * t))
            return p, v, (f - a) / FPS
    # 最後：星へ飛んでいく
    a = HITS[-1]["fr"]; t = (f - a) / FPS
    p = P[-1] + Vector((0.4 * t, 1.2 * t, 6.5 * t - 0.5 * 2.0 * t * t))
    return p, Vector((0.4, 1.2, 6.5 - 2.0 * t)), t

# ---------------- 宇宙うんこ（ソフトクリーム型・わえさんの宇宙画）----------------
cu = bpy.data.curves.new("swirl", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.0; cu.bevel_resolution = 6; cu.use_fill_caps = True
sp = cu.splines.new('NURBS'); NPT = 90; sp.points.add(NPT - 1); sp.use_endpoint_u = True; sp.order_u = 4
for j in range(NPT):
    u = j / (NPT - 1); a_ = 2 * math.pi * 2.7 * u
    R_ = 0.52 * (1 - u) ** 0.85 + 0.015; z = 0.20 + 0.82 * u ** 0.95
    sp.points[j].co = (R_ * math.cos(a_), R_ * math.sin(a_), z, 1); sp.points[j].radius = 0.25 * (1 - u) ** 0.7 + 0.012
so = bpy.data.objects.new("swirl", cu); bpy.context.collection.objects.link(so)
bpy.context.view_layer.objects.active = so; so.select_set(True); bpy.ops.object.convert(target='MESH'); sw = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.62, location=(0, 0, 0.16)); base = bpy.context.object; base.scale = (1, 1, 0.38)
bpy.ops.object.select_all(action='DESELECT'); sw.select_set(True); base.select_set(True); bpy.context.view_layer.objects.active = sw; bpy.ops.object.join()
unko = bpy.context.object; unko.name = "unko"
rm = unko.modifiers.new("r", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.02
sm = unko.modifiers.new("s", 'SMOOTH'); sm.iterations = 3; sm.factor = 0.5
bpy.ops.object.modifier_apply(modifier="r"); bpy.ops.object.modifier_apply(modifier="s"); bpy.ops.object.shade_smooth()
# 原点を底の中心に
zmin = min(v.co.z for v in unko.data.vertices)
for v in unko.data.vertices: v.co.z -= zmin
hgt = max(v.co.z for v in unko.data.vertices)
S0 = UNKO_H / hgt
um, nt, p = newmat("unkoM")
pin(p, "Roughness", 0.18); pin(p, "Coat Weight", 0.6); pin(p, "Coat Roughness", 0.05)
pin(p, "Subsurface Weight", 0.35); pin(p, "Subsurface Radius", (0.3, 0.15, 0.25)); pin(p, "Subsurface Scale", 0.08)
pin(p, "Specular IOR Level", 0.6)
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); I(mp, "Scale").default_value = (0.9, 0.9, 0.9)
im = nt.nodes.new("ShaderNodeTexImage"); im.image = bpy.data.images.load(PAINT); im.projection = 'BOX'; im.projection_blend = 0.35
link(nt, tc.outputs["Object"], I(mp, "Vector")); link(nt, mp.outputs["Vector"], I(im, "Vector"))
hsv = nt.nodes.new("ShaderNodeHueSaturation"); I(hsv, "Value").default_value = 1.35; I(hsv, "Saturation").default_value = 1.1
link(nt, im.outputs["Color"], I(hsv, "Color"))
link(nt, hsv.outputs["Color"], I(p, "Base Color")); link(nt, im.outputs["Color"], I(p, "Emission Color")); pin(p, "Emission Strength", 0.35)
try: link(nt, hsv.outputs["Color"], I(p, "Subsurface Color"))
except Exception: pass
unko.data.materials.clear(); unko.data.materials.append(um)

# 当たりのつぶれ（グミのぷるん）
def squash(tsince, vz):
    st = min(0.14, abs(vz) * 0.012)              # 飛んでいる間は速さに応じて少し縦にのびる
    if tsince is None or tsince < 0: zs = 1 + st
    else:
        k = math.exp(-tsince / 0.11) * math.cos(2 * math.pi * tsince / 0.17)   # 当たりでつぶれて、ぷるんと戻る
        zs = 1 - 0.36 * k + st * (1 - math.exp(-tsince / 0.08))
    return 1 / math.sqrt(max(zs, 0.4)), zs
yaw = 0.0
TRACK = []
for f in range(1, NF + 1):
    pv, v, ts = pos_virtual(f)
    pa = actual(pv, f)
    xs, zs = squash(ts, v.z)
    if f > HITS[-1]["fr"]:
        k = min(1, (f - HITS[-1]["fr"]) / (1.6 * FPS)); sc_ = S0 * (1 - 0.85 * k)
    else: sc_ = S0
    yaw += 0.035 + 0.02 * math.sin(f * 0.05)
    hv = Vector((v.x, v.y, 0))
    tilt = max(-0.35, min(0.35, -0.05 * v.z * 0)) if True else 0
    unko.location = pa; unko.keyframe_insert("location", frame=f)
    unko.rotation_euler = (0.12 * math.sin(f * 0.11) * (1 if ts and ts > 0.1 else 0.3), 0.10 * math.cos(f * 0.09), yaw)
    unko.keyframe_insert("rotation_euler", frame=f)
    unko.scale = (sc_ * xs, sc_ * xs, sc_ * zs); unko.keyframe_insert("scale", frame=f)
    TRACK.append({"f": f, "virt": list(pv), "z_bottom": pa.z})
for fc in unko.animation_data.action.fcurves:
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
# うんこのしずく光（当たりの瞬間だけ少し光る）
em = I(p, "Emission Strength")
for h in HITS:
    for ff, vv in ((h["fr"] - 1, 0.35), (h["fr"], 1.6), (h["fr"] + 8, 0.35)):
        em.default_value = vv; em.keyframe_insert("default_value", frame=ff)
em.default_value = 6.0; em.keyframe_insert("default_value", frame=NF)   # 最後は星になって光る

stage('unko')
# ---------------- 鉄琴の板 ----------------
def keycol(midi):
    # 低い音＝深い朱、高い音＝すみれ〜水色（レイ・ハラカミの柔らかい色に寄せる）
    s = max(0, min(1, (midi - 38) / 45))
    pal = [(0.85, 0.30, 0.18), (0.95, 0.62, 0.30), (0.95, 0.85, 0.55), (0.55, 0.85, 0.75), (0.45, 0.62, 0.95), (0.72, 0.52, 0.95)]
    x = s * (len(pal) - 1); i = min(int(x), len(pal) - 2); u = x - i
    return tuple(pal[i][k] * (1 - u) + pal[i + 1][k] * u for k in range(3))
BAR_T = 0.07
def make_bar(i, h, loc, butai):
    midi = h["key"]; col = keycol(midi)
    L = 1.35 - 0.55 * max(0, min(1, (midi - 40) / 45)); W = 0.34 if len(h["notes"]) < 3 else 0.46
    nxt = P[i + 1] - P[i] if i + 1 < len(P) else P[i] - P[i - 1]
    ang = math.atan2(nxt.y, nxt.x) + math.pi / 2     # 進む向きに対して横向き
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc - Vector((0, 0, BAR_T / 2)))
    o = bpy.context.object; o.name = "bar%02d" % i
    o.scale = (L, W, BAR_T); o.rotation_euler = (0, 0, ang)
    bv = o.modifiers.new("b", 'BEVEL'); bv.width = 0.025; bv.segments = 4
    m, nt_, pp = newmat("barM%02d" % i)
    pin(pp, "Base Color", col + (1,)); pin(pp, "Metallic", 0.55); pin(pp, "Roughness", 0.28)
    pin(pp, "Emission Color", col + (1,)); pin(pp, "Emission Strength", 0.0)
    o.data.materials.append(m)
    # 支え（2本の小さな柱）と下の台
    for sgn in (-1, 1):
        off = Vector((math.cos(ang), math.sin(ang), 0)) * (L * 0.33 * sgn)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.16, location=loc + off - Vector((0, 0, BAR_T + 0.08)))
        cy = bpy.context.object; cy.data.materials.append(MAT_POST)
    # 光る・沈む・ぷるっと揺れる
    fh = h["fr"]; e = I(pp, "Emission Strength")
    for ff, vv in ((fh - 1, 0.0), (fh, 7.0), (fh + 3, 3.0), (fh + 16, 0.25), (fh + 40, 0.0)):
        e.default_value = vv; e.keyframe_insert("default_value", frame=ff)
    z0 = o.location.z
    for ff, dz in ((fh - 1, 0), (fh + 1, -0.05), (fh + 4, 0.012), (fh + 8, -0.004), (fh + 12, 0)):
        o.location.z = z0 + dz; o.keyframe_insert("location", index=2, frame=ff)
    # 波紋の輪
    bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.012, location=loc + Vector((0, 0, 0.01)))
    rg = bpy.context.object; rm_, rnt, rp = newmat("ringM%02d" % i)
    pin(rp, "Base Color", (0, 0, 0, 1)); pin(rp, "Emission Color", col + (1,)); pin(rp, "Emission Strength", 0.0)
    rg.data.materials.append(rm_)
    for ff, s_, ee in ((fh - 1, 0.0, 0.0), (fh, 0.4, 8.0), (fh + 18, 3.2, 0.0), (fh + 19, 0.0, 0.0)):
        rg.scale = (s_, s_, s_); rg.keyframe_insert("scale", frame=ff)
        I(rp, "Emission Strength").default_value = ee; I(rp, "Emission Strength").keyframe_insert("default_value", frame=ff)
    # 小さな光の粒（6個）
    for k in range(int(os.environ.get('UU_TSUBU', '4'))):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.018, location=loc)
        d = bpy.context.object; d.data.materials.append(m)
        a2 = rnd.uniform(0, 2 * math.pi); sp_ = rnd.uniform(0.8, 1.6); up = rnd.uniform(1.2, 2.4)
        for ff in range(fh - 1, fh + 20):
            t = (ff - fh) / FPS
            if t < 0: d.location = loc; d.scale = (0, 0, 0)
            else:
                d.location = loc + Vector((math.cos(a2) * sp_ * t, math.sin(a2) * sp_ * t, up * t - 0.5 * 6 * t * t))
                s_ = max(0, 1 - t / 0.8); d.scale = (s_, s_, s_)
            d.keyframe_insert("location", frame=ff); d.keyframe_insert("scale", frame=ff)
    return o, ang, L

MAT_POST, _, pp_ = newmat("post"); pin(pp_, "Base Color", (0.75, 0.7, 0.6, 1)); pin(pp_, "Metallic", 0.8); pin(pp_, "Roughness", 0.3)

# ---------------- 舞台A：森の滝（アマゾンの秘境の滝のような） ----------------
def noise_rock(name, loc, scale, mat, seed):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale
    tx = bpy.data.textures.new(name + "t", 'VORONOI'); tx.noise_scale = 0.6
    dm = o.modifiers.new("d", 'DISPLACE'); dm.texture = tx; dm.strength = 0.35; dm.texture_coords = 'LOCAL'
    tx2 = bpy.data.textures.new(name + "c", 'CLOUDS'); tx2.noise_scale = 0.35
    dm2 = o.modifiers.new("d2", 'DISPLACE'); dm2.texture = tx2; dm2.strength = 0.25
    o.rotation_euler = (rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), rnd.uniform(0, 6.28))
    bpy.ops.object.shade_smooth(); o.data.materials.append(mat); return o

def mat_rock(name, moss=True):
    m, nt_, pp = newmat(name)
    geo = nt_.nodes.new("ShaderNodeNewGeometry"); sepz = nt_.nodes.new("ShaderNodeSeparateXYZ")
    link(nt_, geo.outputs["Normal"], sepz.inputs[0])
    nz = nt_.nodes.new("ShaderNodeTexNoise"); I(nz, "Scale").default_value = 6
    mix = nt_.nodes.new("ShaderNodeMath"); mix.operation = 'ADD'
    link(nt_, sepz.outputs["Z"], mix.inputs[0]); link(nt_, nz.outputs["Fac"], mix.inputs[1])
    ramp = nt_.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.75; ramp.color_ramp.elements[0].color = (0.045, 0.042, 0.038, 1)
    ramp.color_ramp.elements[1].position = 1.15 if moss else 1.6; ramp.color_ramp.elements[1].color = (0.055, 0.13, 0.035, 1)
    link(nt_, mix.outputs[0], I(ramp, "Fac")); link(nt_, ramp.outputs["Color"], I(pp, "Base Color"))
    pin(pp, "Roughness", 0.75)
    bm = nt_.nodes.new("ShaderNodeBump"); I(bm, "Strength").default_value = 0.4
    link(nt_, nz.outputs["Fac"], I(bm, "Height")); link(nt_, bm.outputs["Normal"], I(pp, "Normal"))
    return m

def mat_water(name, tint=(0.85, 0.95, 1.0), speed=1.0, bright=1.4, dens=0.5):
    m, nt_, pp = newmat(name); blend(m, 'BLEND')
    tc_ = nt_.nodes.new("ShaderNodeTexCoord")
    def flow(scale, spd):
        mp_ = nt_.nodes.new("ShaderNodeMapping"); I(mp_, "Scale").default_value = scale
        link(nt_, tc_.outputs["Object"], I(mp_, "Vector"))
        loc_in = I(mp_, "Location")
        loc_in.default_value = (0, 0, 0); loc_in.keyframe_insert("default_value", frame=1)
        loc_in.default_value = (0, 0, spd * NF / FPS); loc_in.keyframe_insert("default_value", frame=NF)
        nz = nt_.nodes.new("ShaderNodeTexNoise"); I(nz, "Scale").default_value = 1.0; I(nz, "Detail").default_value = 4
        I(nz, "Roughness").default_value = 0.45
        link(nt_, mp_.outputs["Vector"], I(nz, "Vector")); return nz
    a = flow((5.0, 5.0, 0.22), 0.9 * speed)      # 太い筋（ゆっくり）
    b = flow((11.0, 11.0, 0.5), 2.2 * speed)     # 細い筋（速い）
    for fc in m.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    mx = nt_.nodes.new("ShaderNodeMath"); mx.operation = 'MULTIPLY'
    link(nt_, a.outputs["Fac"], mx.inputs[0]); link(nt_, b.outputs["Fac"], mx.inputs[1])
    ramp = nt_.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.12; ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.42; ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    link(nt_, mx.outputs[0], I(ramp, "Fac"))
    mth = nt_.nodes.new("ShaderNodeMath"); mth.operation = 'MULTIPLY_ADD'
    mth.inputs[1].default_value = 0.55; mth.inputs[2].default_value = 0.35 * dens + 0.1
    link(nt_, ramp.outputs["Color"], mth.inputs[0])
    col = nt_.nodes.new("ShaderNodeMixRGB"); I(col, "Color1").default_value = (tint[0] * 0.45, tint[1] * 0.55, tint[2] * 0.6, 1)
    I(col, "Color2").default_value = tint + (1,); link(nt_, ramp.outputs["Color"], I(col, "Fac"))
    link(nt_, col.outputs[0], I(pp, "Base Color")); link(nt_, col.outputs[0], I(pp, "Emission Color")); pin(pp, "Roughness", 0.15)
    link(nt_, mth.outputs[0], I(pp, "Alpha"))
    em2 = nt_.nodes.new("ShaderNodeMath"); em2.operation = 'MULTIPLY'; em2.inputs[1].default_value = bright * 0.6
    link(nt_, ramp.outputs["Color"], em2.inputs[0]); link(nt_, em2.outputs[0], I(pp, "Emission Strength"))
    return m

def curtain(name, x0, x1, ytop, zt, zb, mat, bend=1.2, nseg=40):
    me = bpy.data.meshes.new(name); verts = []; faces = []; NZ = 30
    for j in range(NZ + 1):
        z = zt + (zb - zt) * j / NZ
        for i in range(nseg + 1):
            u = i / nseg; x = x0 + (x1 - x0) * u
            y = ytop + bend * (2 * u - 1) ** 2 - 0.4 * (1 - j / NZ) ** 3
            verts.append((x, y, z))
    for j in range(NZ):
        for i in range(nseg):
            a = j * (nseg + 1) + i; faces.append((a, a + 1, a + nseg + 2, a + nseg + 1))
    me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o); o.data.materials.append(mat)
    return o

def mat_volume(name, dens, col=(0.85, 0.92, 0.95), aniso=0.4):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt_ = m.node_tree
    for n in list(nt_.nodes):
        if n.type != 'OUTPUT_MATERIAL': nt_.nodes.remove(n)
    out = [n for n in nt_.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    vs = nt_.nodes.new("ShaderNodeVolumePrincipled"); I(vs, "Density").default_value = dens
    I(vs, "Color").default_value = col + (1,); I(vs, "Anisotropy").default_value = aniso
    link(nt_, vs.outputs[0], I(out, "Volume")); return m

LITE = os.environ.get("UU_LITE") == "1"     # Cycles用の軽い版：体積の霧をやめ、奥行きの霧は合成で足す
def box(name, center, size, mat):
    if LITE and any(n.type == 'PRINCIPLED_VOLUME' for n in mat.node_tree.nodes): return None
    bpy.ops.mesh.primitive_cube_add(size=1, location=center); o = bpy.context.object; o.name = name
    o.scale = size; o.data.materials.append(mat); return o

ALL_A, ALL_B = [], []
def track_new(lst):
    before = set(bpy.data.objects.keys())
    return before

def build_mori_no_taki():
    xs = [p_.x for p_ in PA]; zs = [p_.z for p_ in PA]; ys = [p_.y for p_ in PA]
    zt, zb = max(zs) + 6, min(zs) - 6
    cx = sum(xs) / len(xs); ymax = max(ys)
    rock = mat_rock("rockA"); rock2 = mat_rock("rockA2", moss=False)
    # 大きな滝（奥）と細い滝（左右）
    wA = mat_water("waterA", (0.86, 0.95, 1.0), 1.0, 1.6, 0.6)
    curtain("takiA_main", cx - 4.6, cx + 4.6, ymax + 3.0, zt + 2, zb - 2, wA, 1.3)
    wA2 = mat_water("waterA2", (0.7, 0.88, 0.95), 1.3, 0.9, 0.35)
    curtain("takiA_back", cx - 6.0, cx + 6.0, ymax + 3.6, zt + 2, zb - 2, wA2, 1.0)
    curtain("takiA_side", cx + 6.6, cx + 7.6, ymax + 1.6, zt - 1, zb - 2, wA, 0.2, 10)
    # 崖（左右と奥）
    for k in range(10):
        z = zt - (zt - zb) * k / 9
        for sgn in (-1, 1):
            noise_rock("cliff%d%d" % (k, sgn), (cx + sgn * rnd.uniform(5.6, 6.6), ymax + rnd.uniform(1.5, 4.0), z),
                       (rnd.uniform(1.6, 2.6), rnd.uniform(1.6, 2.4), rnd.uniform(1.8, 2.6)), rock, k)
    box("cliff_back", (cx, ymax + 5.2, (zt + zb) / 2), (18, 1, zt - zb + 8), rock2)
    # 板の下の岩（段々）
    for i, pp_ in enumerate(PA):
        noise_rock("ledge%02d" % i, pp_ + Vector((0, 0.2, -0.62)), (0.62, 0.42, 0.22), rock, i)
    # 滝つぼと霧
    mw, ntw, pw = newmat("pool"); pin(pw, "Base Color", (0.02, 0.10, 0.09, 1)); pin(pw, "Roughness", 0.05)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(cx, ymax, zb + 1.2)); bpy.context.object.data.materials.append(mw)
    box("kiri_soko", (cx, ymax + 1, zb + 2.6), (16, 14, 4.4), mat_volume("kiriA_soko", 0.55, (0.9, 0.95, 0.95)))
    box("kiri_zentai", (cx, ymax, (zt + zb) / 2), (26, 26, zt - zb + 10), mat_volume("kiriA", 0.010, (0.8, 0.95, 0.85), 0.6))
    # 光：上の奥から差す（光の筋）、手前の柔らかい補助
    ld = bpy.data.lights.new("sunA", 'SUN'); ld.energy = 6.0; ld.color = (1.0, 0.88, 0.68); ld.angle = math.radians(3)
    lo = bpy.data.objects.new("sunA", ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(-35), math.radians(18), math.radians(160))
    ld2 = bpy.data.lights.new("fillA", 'AREA'); ld2.energy = 170; ld2.size = 6; ld2.color = (0.75, 0.9, 1.0)
    lo2 = bpy.data.objects.new("fillA", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cx - 1, min(ys) - 7, (zt + zb) / 2 + 3); lo2.rotation_euler = (math.radians(70), 0, 0)
    # ツタ（垂れる細い葉の帯）
    mv, ntv, pv_ = newmat("tsuta"); pin(pv_, "Base Color", (0.08, 0.25, 0.05, 1)); pin(pv_, "Roughness", 0.6)
    for k in range(18):
        x = cx + rnd.choice((-1, 1)) * rnd.uniform(4.2, 5.4); z = zt - rnd.uniform(0, (zt - zb) * 0.8)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=rnd.uniform(2, 5), location=(x, ymax + rnd.uniform(0.2, 1.8), z))
        bpy.context.object.data.materials.append(mv)
    return sunlamps(lo, lo2)

def sunlamps(*l): return list(l)

def build_kumo_no_yoru():
    xs = [p_.x for p_ in PB]; zs = [p_.z for p_ in PB]; ys = [p_.y for p_ in PB]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys); zlo = min(zs)
    # 雲海（ふわっと盛り上がる面）
    me_cl = bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=160, size=90, location=(cx, cy + 20, zlo - 3.2))
    cl = bpy.context.object
    tx = bpy.data.textures.new("kumo", 'CLOUDS'); tx.noise_scale = 3.5; tx.noise_depth = 3
    dm = cl.modifiers.new("d", 'DISPLACE'); dm.texture = tx; dm.strength = 2.2
    bpy.ops.object.shade_smooth()
    mc, ntc, pc = newmat("kumoM"); pin(pc, "Base Color", (0.55, 0.62, 0.85, 1)); pin(pc, "Roughness", 1.0)
    pin(pc, "Subsurface Weight", 0.4); pin(pc, "Emission Color", (0.25, 0.22, 0.45, 1)); pin(pc, "Emission Strength", 0.25)
    cl.data.materials.append(mc)
    box("kiriB", (cx, cy + 20, zlo - 1.6), (90, 90, 2.6), mat_volume("kiriB", 0.08, (0.6, 0.65, 0.95), 0.3))
    # 雲を抜けてくる層（落ちてくるときにくぐる）
    box("kumo_kuguru", (PB[0].x, PB[0].y, PB[0].z + 4.0), (10, 10, 1.6), mat_volume("kuguru", 0.9, (0.85, 0.85, 1.0)))
    # 月
    bpy.ops.mesh.primitive_uv_sphere_add(radius=5, location=(cx + 9, cy + 70, zlo + 20)); mo = bpy.context.object
    mm, ntm, pm = newmat("tsuki"); pin(pm, "Base Color", (1, 0.95, 0.85, 1)); pin(pm, "Emission Color", (1, 0.93, 0.8, 1)); pin(pm, "Emission Strength", 6)
    mo.data.materials.append(mm)
    ld = bpy.data.lights.new("moonB", 'SUN'); ld.energy = 2.2; ld.color = (0.72, 0.78, 1.0); ld.angle = math.radians(1)
    lo = bpy.data.objects.new("moonB", ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(-60), math.radians(-12), math.radians(170))
    ld2 = bpy.data.lights.new("rimB", 'AREA'); ld2.energy = 300; ld2.size = 8; ld2.color = (0.85, 0.55, 1.0)
    lo2 = bpy.data.objects.new("rimB", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cx - 3, cy + 8, zlo + 5); lo2.rotation_euler = (math.radians(-110), 0, 0)
    # 星の滝（空から雲海へ落ちる、すみれ色の光の滝）
    wB = mat_water("hoshinotaki", (0.75, 0.6, 1.0), 0.8, 2.6, 0.4)
    curtain("hoshi_taki", cx + 6, cx + 11, cy + 26, zlo + 30, zlo - 4, wB, 0.8, 20)
    curtain("hoshi_taki2", cx - 16, cx - 12, cy + 34, zlo + 34, zlo - 4, wB, 0.6, 16)
    # オーロラ（ゆるく曲がった光のカーテン。下は緑、上はすみれ、縦の筋がゆらぐ）
    for k, (x0, x1, yy, z0, z1, bend) in enumerate(((cx - 40, cx + 30, cy + 60, zlo + 6, zlo + 30, 14), (cx - 10, cx + 45, cy + 75, zlo + 10, zlo + 38, 10))):
        ma, nta, pa_ = newmat("aurora%d" % k); blend(ma)
        tc_ = nta.nodes.new("ShaderNodeTexCoord"); sep = nta.nodes.new("ShaderNodeSeparateXYZ")
        link(nta, tc_.outputs["Generated"], sep.inputs[0])
        bump = nta.nodes.new("ShaderNodeValToRGB"); el = bump.color_ramp.elements
        el[0].position = 0.0; el[0].color = (0, 0, 0, 1); el[1].position = 1.0; el[1].color = (0, 0, 0, 1)
        e2 = el.new(0.22); e2.color = (1, 1, 1, 1); e3 = el.new(0.55); e3.color = (0.35, 0.35, 0.35, 1)
        link(nta, sep.outputs["Z"], I(bump, "Fac"))
        mp_ = nta.nodes.new("ShaderNodeMapping"); I(mp_, "Scale").default_value = (28, 1, 0.6)
        link(nta, tc_.outputs["Generated"], I(mp_, "Vector"))
        lo_ = I(mp_, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1)
        lo_.default_value = (1.5, 0, 0); lo_.keyframe_insert("default_value", frame=NF)
        nz = nta.nodes.new("ShaderNodeTexNoise"); I(nz, "Scale").default_value = 1.0; I(nz, "Detail").default_value = 3
        link(nta, mp_.outputs["Vector"], I(nz, "Vector"))
        mul = nta.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'
        link(nta, bump.outputs["Color"], mul.inputs[0]); link(nta, nz.outputs["Fac"], mul.inputs[1])
        mul2 = nta.nodes.new("ShaderNodeMath"); mul2.operation = 'MULTIPLY'; mul2.inputs[1].default_value = 0.9
        link(nta, mul.outputs[0], mul2.inputs[0]); link(nta, mul2.outputs[0], I(pa_, "Alpha"))
        cr = nta.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.2, 1.0, 0.6, 1); cr.color_ramp.elements[1].color = (0.65, 0.35, 1.0, 1)
        cr.color_ramp.elements[0].position = 0.15; cr.color_ramp.elements[1].position = 0.7
        link(nta, sep.outputs["Z"], I(cr, "Fac"))
        pin(pa_, "Base Color", (0, 0, 0, 1)); link(nta, cr.outputs["Color"], I(pa_, "Emission Color")); pin(pa_, "Emission Strength", 2.2)
        curtain("aurora%d" % k, x0, x1, yy, z1, z0, ma, bend, 60)
    # 板の下の小さな光の島
    mi, nti, pi_ = newmat("shima"); pin(pi_, "Base Color", (0.06, 0.05, 0.10, 1)); pin(pi_, "Emission Color", (0.45, 0.32, 0.9, 1)); pin(pi_, "Emission Strength", 0.12)
    for i, pp_ in enumerate(PB):
        noise_rock("shima%02d" % i, pp_ + Vector((0, 0.1, -0.55)), (0.5, 0.36, 0.2), mi, 50 + i)
    return [lo, lo2]

# 世界（空）：舞台Aは霧の緑金、舞台Bは夜の藍＋星。切り替えはキーで
w = sc.world or bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree
bg = wn.nodes.get("Background")
tcw = wn.nodes.new("ShaderNodeTexCoord"); sepw = wn.nodes.new("ShaderNodeSeparateXYZ"); link(wn, tcw.outputs["Generated"], sepw.inputs[0])
zmap = wn.nodes.new("ShaderNodeMath"); zmap.operation = 'MULTIPLY_ADD'; zmap.inputs[1].default_value = 0.5; zmap.inputs[2].default_value = 0.5
link(wn, sepw.outputs["Z"], zmap.inputs[0])
rampA = wn.nodes.new("ShaderNodeValToRGB")
rampA.color_ramp.elements[0].position = 0.45; rampA.color_ramp.elements[0].color = (0.10, 0.20, 0.13, 1)
rampA.color_ramp.elements[1].position = 0.85; rampA.color_ramp.elements[1].color = (0.75, 0.82, 0.62, 1)
link(wn, zmap.outputs[0], I(rampA, "Fac"))
vor = wn.nodes.new("ShaderNodeTexVoronoi"); I(vor, "Scale").default_value = 160
try: vor.feature = 'F1'
except Exception: pass
stp = wn.nodes.new("ShaderNodeMath"); stp.operation = 'LESS_THAN'; stp.inputs[1].default_value = 0.06
link(wn, tcw.outputs["Generated"], I(vor, "Vector")); link(wn, vor.outputs["Distance"], stp.inputs[0])
rampB = wn.nodes.new("ShaderNodeValToRGB")
rampB.color_ramp.elements[0].position = 0.45; rampB.color_ramp.elements[0].color = (0.04, 0.03, 0.09, 1)
rampB.color_ramp.elements[1].position = 0.9; rampB.color_ramp.elements[1].color = (0.005, 0.008, 0.03, 1)
link(wn, zmap.outputs[0], I(rampB, "Fac"))
addst = wn.nodes.new("ShaderNodeMixRGB"); addst.blend_type = 'ADD'; addst.inputs[0].default_value = 1.0
starc = wn.nodes.new("ShaderNodeMath"); starc.operation = 'MULTIPLY'; starc.inputs[1].default_value = 3.0
link(wn, stp.outputs[0], starc.inputs[0])
link(wn, rampB.outputs["Color"], addst.inputs[1]); link(wn, starc.outputs[0], addst.inputs[2])
mixw = wn.nodes.new("ShaderNodeMixRGB"); link(wn, rampA.outputs["Color"], mixw.inputs[1]); link(wn, addst.outputs["Color"], mixw.inputs[2])
link(wn, mixw.outputs["Color"], I(bg, "Color")); I(bg, "Strength").default_value = 1.0
for ff, vv in ((SWITCH - 1, 0.0), (SWITCH, 1.0)):
    mixw.inputs[0].default_value = vv; mixw.inputs[0].keyframe_insert("default_value", frame=ff)

stage('world')
BUTAI = {"mori_no_taki": build_mori_no_taki, "kumo_no_yoru": build_kumo_no_yoru}
before = set(bpy.data.objects.keys())
lightsA = BUTAI[KATA["butai"][0]["kata"]]()
objsA = set(bpy.data.objects.keys()) - before
before = set(bpy.data.objects.keys())
lightsB = BUTAI[KATA["butai"][1]["kata"]]()
objsB = set(bpy.data.objects.keys()) - before
stage('butai')
# 板を作る
before = set(bpy.data.objects.keys())
for i, h in enumerate(HITS):
    loc = P[i] if i <= SPLIT else P[i] + SHIFT
    make_bar(i, h, loc, "A" if i <= SPLIT else "B")
# 見えない方の舞台は消しておく（光と霧が重ならないように）
for n in objsA: hide_between(bpy.data.objects[n], 1, SWITCH - 1)
for n in objsB: hide_between(bpy.data.objects[n], SWITCH, NF + 5)
kg = bpy.data.objects.get("kumo_kuguru")     # 雲をくぐる層は、くぐり終えたら消す（あとで道が上ってきても暗くならない）
if kg:
    kg.hide_render = True; kg.keyframe_insert("hide_render", frame=HITS[SPLIT + 1]["fr"] + 6)
    kg.hide_viewport = True; kg.keyframe_insert("hide_viewport", frame=HITS[SPLIT + 1]["fr"] + 6)

stage('bars')
# ---------------- カメラ（追いかけ・回り込み・引き）----------------
def smooth_track():
    raw = [pos_virtual(f)[0] for f in range(1, NF + 1)]
    out = []
    for i in range(len(raw)):
        acc = Vector((0, 0, 0)); ws = 0
        for k in range(-18, 19):
            j = min(len(raw) - 1, max(0, i + k)); wgt = math.exp(-(k / 9.0) ** 2); acc += raw[j] * wgt; ws += wgt
        out.append(acc / ws)
    return out
TG = smooth_track()
fA, fT, fB, fE = HITS[0]["fr"], HITS[SPLIT]["fr"], HITS[SPLIT + 1]["fr"], HITS[-1]["fr"]
# (コマ, 距離, 方位[度], 仰角[度], レンズ)
SHOTS = [
    (1, 11.0, -18, 12, 26),              # 引き：滝の全景、空からうんこが降ってくる
    (fA + 30, 6.0, -12, 10, 30),         # 寄る
    (fA + 110, 4.2, 8, 8, 32),           # 追いかけ
    (fA + 200, 4.0, 42, 12, 32),         # 回り込み（斜め横から、滝を背に）
    (fT - 30, 4.4, 30, 22, 30),          # 戻りながら上へ
    (fT, 5.0, 10, 38, 28),               # 見下ろし：落ちる先
    (SWITCH - 1, 3.4, 0, 55, 26),        # 霧へ一緒に落ちる
    (SWITCH, 3.4, -30, 50, 26),
    (fB + 10, 4.2, -25, 8, 30),          # 雲を抜けて：低い位置から月を背に
    (fB + 110, 4.0, 20, 6, 32),
    (fE - 20, 4.6, 55, 10, 30),          # 回り込み
    (fE + 10, 6.0, 30, 12, 28),
    (NF, 15.0, 10, 18, 24),              # 大きく引く：星へ
]
def smoothstep(x): return x * x * (3 - 2 * x)
def shot(f):
    for a, b in zip(SHOTS, SHOTS[1:]):
        if a[0] <= f <= b[0]:
            u = smoothstep((f - a[0]) / max(1, b[0] - a[0]))
            if a[0] == SWITCH - 1: u = 1.0 if f >= SWITCH else 0.0
            return [a[k] + (b[k] - a[k]) * u for k in range(1, 5)]
    return SHOTS[-1][1:]
cam_d = bpy.data.cameras.new("C"); cam_d.clip_end = 400
cam = bpy.data.objects.new("Cam", cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new("Tgt", None); bpy.context.collection.objects.link(tgt)
tr = cam.constraints.new('TRACK_TO'); tr.target = tgt; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
CAMLOG = []
for f in range(1, NF + 1):
    dist, az, el, lens = shot(f)
    t = TG[f - 1].copy()
    if f <= fA + 30:   # 最初は滝の全景の中心を見る
        u = smoothstep(min(1, f / (fA + 30))); t = (P[0] + Vector((0, 1.5, -2.5))) * (1 - u) + t * u
    if f > fE: t = t + Vector((0, 0, 0.0))
    t_act = actual(t + Vector((0, 0, UNKO_H * 0.5)), f)
    a, e = math.radians(az), math.radians(el)
    c = t_act + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.location = c; cam.keyframe_insert("location", frame=f)
    tgt.location = t_act; tgt.keyframe_insert("location", frame=f)
    cam_d.lens = lens; cam_d.keyframe_insert("lens", frame=f)
    CAMLOG.append(f)
for ob in (cam, tgt):
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
# 霧の白（カメラの前の板）：舞台の入れ替えを隠す
mf, ntf, pf = newmat("shiro"); blend(mf)
pin(pf, "Base Color", (1, 1, 1, 1)); pin(pf, "Emission Color", (0.92, 0.95, 1.0, 1)); pin(pf, "Emission Strength", 1.6)
bpy.ops.mesh.primitive_plane_add(size=1); card = bpy.context.object; card.data.materials.append(mf)
card.parent = cam; card.location = (0, 0, -0.3); card.scale = (2, 2, 1)
al = I(pf, "Alpha")
for ff, vv in ((1, 0.0), (SWITCH - 12, 0.0), (SWITCH - 2, 1.0), (SWITCH + 3, 1.0), (SWITCH + 16, 0.0), (NF, 0.0)):
    al.default_value = vv; al.keyframe_insert("default_value", frame=ff)

# ---------------- 記録（音ズレの点検用）----------------
rec = {"switch": SWITCH, "nf": NF, "fps": FPS, "contact": []}
for i, h in enumerate(HITS):
    loc = P[i] if i <= SPLIT else P[i] + SHIFT
    zs_ = [(f, actual(pos_virtual(f)[0], f).z - loc.z) for f in range(max(1, h["fr"] - 3), min(NF, h["fr"] + 3) + 1)]
    lowest = min(zs_, key=lambda x: x[1])
    rec["contact"].append({"i": i, "hit_fr": h["fr"], "lowest_fr": lowest[0], "gap_m": round(lowest[1], 5)})
os.makedirs(OUT, exist_ok=True)
json.dump(rec, open(os.path.join(OUT, "_kiroku.json"), "w"), indent=1)
if os.environ.get("UU_SAVE"): bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "_scene.blend"))

if LITE:
    sc.view_layers[0].use_pass_mist = True
    w.mist_settings.start = 3; w.mist_settings.depth = 45; w.mist_settings.falloff = 'QUADRATIC'
    sc.use_nodes = True; cn = sc.node_tree
    rl = cn.nodes.get("Render Layers"); comp = cn.nodes.get("Composite")
    mx = cn.nodes.new("CompositorNodeMixRGB"); fogm = cn.nodes.new("CompositorNodeMath"); fogm.operation = 'MULTIPLY'
    fogm.inputs[1].default_value = 0.75
    cn.links.new(rl.outputs["Mist"], fogm.inputs[0]); cn.links.new(fogm.outputs[0], mx.inputs[0])
    cn.links.new(rl.outputs["Image"], mx.inputs[1]); cn.links.new(mx.outputs[0], comp.inputs["Image"])
    fc_ = mx.inputs[2]
    for ff, col in ((SWITCH - 1, (0.75, 0.85, 0.78, 1)), (SWITCH, (0.10, 0.10, 0.22, 1))):
        fc_.default_value = col; fc_.keyframe_insert("default_value", frame=ff)
stage('ready')
# ---------------- 描画 ----------------
STEP = int(os.environ.get("UU_STEP", "1"))
if FR == "all": frames = range(1, NF + 1, STEP)
elif "-" in FR: a_, b_ = FR.split("-"); frames = range(int(a_), int(b_) + 1, STEP)
else: frames = [int(x) for x in FR.split(",")]
for f in frames:
    path = os.path.join(OUT, "f%04d.jpg" % f)
    if os.path.exists(path): continue
    t0 = time.time(); sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print("FRAME", f, round(time.time() - t0, 1), flush=True)
print("DONE", NF, flush=True)
