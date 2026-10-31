# 宇宙うんこ v3.1（Blender 3.6 LTS の EEVEE）：架空の廃墟（崩れたコンクリートの吹き抜け → 水に沈んだ廃墟の夜）
# 動き・カメラは michi.json（michi_v3.py が計算して、すり抜けゼロを確かめたもの）をそのまま使う。ここでは形と質感と光だけを作る。
# 使い方: Blender -b -P scene_v3.py -- <このフォルダ> <出力フォルダ> <all | 1-100 | 5,60 | none>
# 環境変数: UU_PCT=100  UU_SAMPLES=16  UU_MB=1(動きのぶれ)  UU_SAVE=1(.blendも保存)  UU_LITE=1(体積の霧を軽く)  UU_ENGINE=CYCLES(任意)
import bpy, json, math, os, sys, time, random
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:]
WORK, OUT, FR = argv[0], argv[1], argv[2]
M = json.load(open(os.path.join(WORK, "michi.json")))
FPS, NF, SWITCH, POYON = M["fps"], M["nf"], M["switch"], M["poyon"]
FRM = M["frames"]; BARS = M["bars"]; SC = M["scene"]; H_UNKO = M["h_unko"]
SOZAI = os.path.join(WORK, "sozai")
LITE = os.environ.get("UU_LITE") == "1"
rnd = random.Random(7)
T0 = time.time()
def stage(x): print("STAGE", x, round(time.time() - T0, 1), flush=True)

# 3.6 と 4.x の入力名の違いを吸収
ALIAS = {"Emission Color": "Emission", "Subsurface Weight": "Subsurface", "Coat Weight": "Clearcoat",
         "Coat Roughness": "Clearcoat Roughness", "Specular IOR Level": "Specular", "Transmission Weight": "Transmission"}
ALIAS.update({v: k for k, v in list(ALIAS.items())})
def I(node, key):
    try: return node.inputs[key]
    except KeyError: return node.inputs[ALIAS.get(key, key)]
def O(node, key):
    try: return node.outputs[key]
    except KeyError: return node.outputs[0]
def tryset(obj, **kw):
    for k, v in kw.items():
        try: setattr(obj, k, v)
        except Exception as ex: print("skip", k, ex)

# ---------------- 場の初期化 ----------------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
for e in (("CYCLES",) if os.environ.get("UU_ENGINE") == "CYCLES" else ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")):
    try: sc.render.engine = e; break
    except Exception: pass
if sc.render.engine == "CYCLES":
    tryset(sc.cycles, samples=int(os.environ.get("UU_SAMPLES", "32")), use_denoising=True, device='CPU', max_bounces=4, volume_bounces=0)
print("ENGINE", sc.render.engine, bpy.app.version_string, flush=True)
EV = sc.eevee
tryset(EV, taa_render_samples=int(os.environ.get("UU_SAMPLES", "16")), use_bloom=True, bloom_intensity=0.045,
       bloom_threshold=0.85, bloom_radius=6.5, bloom_knee=0.6, use_gtao=True, gtao_distance=1.2, gtao_factor=1.6,
       use_ssr=True, use_ssr_refraction=True, use_ssr_halfres=True, ssr_quality=0.5, ssr_thickness=0.1,
       use_soft_shadows=True, use_volumetric_shadows=True, use_volumetric_lights=True,
       volumetric_tile_size='16' if not LITE else '16', volumetric_samples=40 if not LITE else 24,
       volumetric_start=0.3, volumetric_end=90.0, volumetric_light_clamp=12.0,
       use_motion_blur=os.environ.get("UU_MB", "1") == "1", motion_blur_shutter=0.25, motion_blur_steps=1,
       shadow_cube_size='1024', shadow_cascade_size='2048', use_shadow_high_bitdepth=True, sss_samples=5)
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.resolution_percentage = int(os.environ.get("UU_PCT", "100"))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = NF
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 93
try: sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
except Exception: pass
sc.view_settings.exposure = 0.35

def newmat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]
def pin(p, key, v):
    try: I(p, key).default_value = v
    except Exception as ex: print("pin", key, ex)
def link(nt, a, b): nt.links.new(a, b)
def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items(): setattr(n, k, v)
    return n
def math_(nt, op, a=None, b=None, va=None, vb=None):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op
    if a is not None: link(nt, a, n.inputs[0])
    elif va is not None: n.inputs[0].default_value = va
    if b is not None: link(nt, b, n.inputs[1])
    elif vb is not None: n.inputs[1].default_value = vb
    return n.outputs[0]
def blend(m, mode='BLEND', shadow='NONE'):
    tryset(m, blend_method=mode, shadow_method=shadow, show_transparent_back=False, use_backface_culling=False)
def load_img(name):
    p = os.path.join(SOZAI, name); return bpy.data.images.load(p, check_existing=True)
def anim_lin(owner):
    ad = getattr(owner, "animation_data", None)
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
def hide_between(o, f_on, f_off):
    """f_on〜f_off の間だけ見える"""
    for f, v in ((1, True), (max(1, f_on - 1), True), (f_on, False), (f_off, False), (f_off + 1, True)):
        if f < 1: continue
        o.hide_render = v; o.keyframe_insert("hide_render", frame=f)
        o.hide_viewport = v; o.keyframe_insert("hide_viewport", frame=f)
def obj_from_mesh(name, verts, faces, mat=None):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    if mat: o.data.materials.append(mat)
    return o
def V(a): return Vector(a)

# =====================================================================
# 宇宙うんこ（v1 のソフトクリーム型のうず＝自前の形。肌は わえ（@cosmicwae）の宇宙画 #12 を箱投影。ちよさんの絵・形は使わない）
# =====================================================================
stage("unko")
cu = bpy.data.curves.new("swirl", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.0; cu.bevel_resolution = 8; cu.use_fill_caps = True
sp = cu.splines.new('NURBS'); NPT = 110; sp.points.add(NPT - 1); sp.use_endpoint_u = True; sp.order_u = 4
for j in range(NPT):
    u = j / (NPT - 1); a_ = 2 * math.pi * 2.6 * u
    R_ = 0.40 * (1 - u) ** 0.85 + 0.012; z = 0.20 + 0.80 * u ** 0.95
    sp.points[j].co = (R_ * math.cos(a_), R_ * math.sin(a_), z, 1); sp.points[j].radius = 0.215 * (1 - u) ** 0.7 + 0.012
so = bpy.data.objects.new("swirl", cu); bpy.context.collection.objects.link(so)
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = so; so.select_set(True); bpy.ops.object.convert(target='MESH'); sw = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.56, location=(0, 0, 0.17)); base = bpy.context.object; base.scale = (1, 1, 0.42)
bpy.ops.object.select_all(action='DESELECT'); sw.select_set(True); base.select_set(True); bpy.context.view_layer.objects.active = sw; bpy.ops.object.join()
unko = bpy.context.object; unko.name = "unko"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for v in unko.data.vertices:          # 底を平らに（板の上にぺたっと座る）
    if v.co.z < 0.0: v.co.z = 0.0
rm = unko.modifiers.new("r", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.012
bpy.ops.object.modifier_apply(modifier="r")
sm = unko.modifiers.new("s", 'SMOOTH'); sm.iterations = 10; sm.factor = 0.55
bpy.ops.object.modifier_apply(modifier="s")
zmin = min(v.co.z for v in unko.data.vertices)
for v in unko.data.vertices: v.co.z -= zmin
hgt = max(v.co.z for v in unko.data.vertices)
S0 = H_UNKO / hgt
for v in unko.data.vertices: v.co *= S0
bpy.ops.object.shade_smooth()
me = unko.data
print("UNKO_MESH verts", len(me.vertices), "width_r", round(max(math.hypot(v.co.x, v.co.y) for v in me.vertices), 3), "h", round(H_UNKO, 3), flush=True)
# グミの質感：宇宙画が中に透けて見える、つやつやで、ぷるんとした塊
def gummy(name, img):
    m, nt, p = newmat(name)
    tc0 = node(nt, "ShaderNodeTexCoord"); mp0 = node(nt, "ShaderNodeMapping"); I(mp0, "Scale").default_value = (1.6, 1.6, 1.6)
    tex = node(nt, "ShaderNodeTexImage"); tex.image = load_img(img); tex.projection = 'BOX'; tex.projection_blend = 0.4; tex.extension = 'REPEAT'
    link(nt, tc0.outputs["Object"], I(mp0, "Vector")); link(nt, mp0.outputs[0], I(tex, "Vector"))
    hsv = node(nt, "ShaderNodeHueSaturation"); I(hsv, "Saturation").default_value = 1.15; I(hsv, "Value").default_value = 1.35
    link(nt, tex.outputs["Color"], I(hsv, "Color"))
    lw = node(nt, "ShaderNodeLayerWeight"); I(lw, "Blend").default_value = 0.18
    bright = node(nt, "ShaderNodeMixRGB"); bright.blend_type = 'SCREEN'; link(nt, lw.outputs["Facing"], bright.inputs[0])
    link(nt, hsv.outputs[0], bright.inputs[1]); bright.inputs[2].default_value = (0.95, 0.78, 1.0, 1)
    link(nt, bright.outputs[0], I(p, "Base Color"))
    try: link(nt, hsv.outputs[0], I(p, "Subsurface Color"))
    except Exception: pass
    pin(p, "Subsurface Weight", 0.16); pin(p, "Subsurface Radius", (1.0, 0.6, 0.85))
    pin(p, "Roughness", 0.1); pin(p, "Coat Weight", 1.0); pin(p, "Coat Roughness", 0.03); pin(p, "Specular IOR Level", 0.7)
    pin(p, "Transmission Weight", 0.07); pin(p, "IOR", 1.42)
    tc = node(nt, "ShaderNodeTexCoord"); vor = node(nt, "ShaderNodeTexVoronoi"); I(vor, "Scale").default_value = 38
    link(nt, tc.outputs["Object"], I(vor, "Vector"))
    st = math_(nt, 'LESS_THAN', O(vor, "Distance"), vb=0.07)
    em = node(nt, "ShaderNodeMixRGB"); em.blend_type = 'ADD'; em.inputs[0].default_value = 1.0
    sc1 = node(nt, "ShaderNodeMixRGB"); sc1.blend_type = 'MULTIPLY'; sc1.inputs[0].default_value = 1.0
    link(nt, hsv.outputs[0], sc1.inputs[1]); sc1.inputs[2].default_value = (0.22, 0.22, 0.22, 1)
    link(nt, sc1.outputs[0], em.inputs[1]); link(nt, st, em.inputs[2])
    link(nt, em.outputs[0], I(p, "Emission Color")); pin(p, "Emission Strength", 1.0)
    tryset(m, use_screen_refraction=True, refraction_depth=0.12, use_sss_translucency=True, blend_method='OPAQUE')
    return m, p
UNKO_MATS = []
m, p = gummy("unko_gummy", "wae_12.jpg"); me.materials.append(m); UNKO_MATS.append(p)
# ぷるぷるの形（シェイプキー）：つぶれ・のび・揺れ（上ほど大きく動く）
unko.shape_key_add(name="Basis")
def key(name, fn):
    kb = unko.shape_key_add(name=name, from_mix=False); kb.slider_min = -1.0; kb.slider_max = 1.5
    for i, v in enumerate(me.vertices): kb.data[i].co = fn(v.co.copy())
    return kb
def tsubure(c):
    h = c.z / H_UNKO
    k = 1.118 * (1 + 0.06 * math.sin(math.pi * min(1, h * 1.6))); return V((c.x * k, c.y * k, c.z * 0.80))
def nobi(c): return V((c.x * 0.945, c.y * 0.945, c.z * 1.12))
def yure(axis):
    def f(c):
        h = c.z / H_UNKO; d = 0.30 * H_UNKO * h * h
        return V((c.x + d, c.y, c.z)) if axis == 0 else V((c.x, c.y + d, c.z))
    return f
KB = {"tsubure": key("tsubure", tsubure), "nobi": key("nobi", nobi), "yureX": key("yureX", yure(0)), "yureY": key("yureY", yure(1))}
unko.location = (0, 0, 0)

# 動き（michi.json のまま）
for f, fr in enumerate(FRM, start=1):
    unko.location = fr["u"]; unko.keyframe_insert("location", frame=f)
    unko.rotation_euler = fr["rot"]; unko.keyframe_insert("rotation_euler", frame=f)
    s = fr["sq"]; yaw = fr["rot"][2]
    KB["tsubure"].value = max(0.0, s) / 0.20; KB["nobi"].value = max(0.0, -s) / 0.12
    lx = (fr["wx"] * math.cos(yaw) + fr["wy"] * math.sin(yaw)) / 0.35
    ly = (-fr["wx"] * math.sin(yaw) + fr["wy"] * math.cos(yaw)) / 0.35
    KB["yureX"].value = max(-1, min(1, lx)); KB["yureY"].value = max(-1, min(1, ly))
    for kb in KB.values(): kb.keyframe_insert("value", frame=f)
anim_lin(unko); anim_lin(me.shape_keys)
# 着地の瞬間だけ、中の星が少し明るく
for p in UNKO_MATS:
    e = I(p, "Emission Strength")
    for b in BARS:
        for ff, vv in ((b["fr"] - 1, 1.0), (b["fr"], 2.6), (b["fr"] + 9, 1.0)):
            e.default_value = vv; e.keyframe_insert("default_value", frame=ff)

# =====================================================================
# 鉄琴の板（角の丸い金属の板・下に2本の横木・低音は大きく朱）
# =====================================================================
stage("bars")
def keycol(midi):
    s = max(0, min(1, (midi - 52) / 36))
    pal = [(0.78, 0.55, 0.22), (0.62, 0.70, 0.52), (0.45, 0.66, 0.68), (0.60, 0.52, 0.78)]
    x = s * (len(pal) - 1); i = min(int(x), len(pal) - 2); u = x - i
    return tuple(pal[i][k] * (1 - u) + pal[i + 1][k] * u for k in range(3))
SHU = (1.0, 0.30, 0.13)
MAT_WOOD, ntw, pw = newmat("yokogi")
nzw = node(ntw, "ShaderNodeTexWave"); I(nzw, "Scale").default_value = 7; I(nzw, "Distortion").default_value = 6
rw = node(ntw, "ShaderNodeValToRGB"); rw.color_ramp.elements[0].color = (0.02, 0.015, 0.012, 1); rw.color_ramp.elements[1].color = (0.06, 0.04, 0.03, 1)
link(ntw, nzw.outputs["Color"], I(rw, "Fac")); link(ntw, rw.outputs["Color"], I(pw, "Base Color")); pin(pw, "Roughness", 0.5)
MAT_HIMO, _, ph_ = newmat("himo"); pin(ph_, "Base Color", (0.55, 0.06, 0.04, 1)); pin(ph_, "Roughness", 0.7); pin(ph_, "Sheen", 0.5)
def bar_mat(i, b):
    m, nt, p = newmat("barM%02d" % i)
    col = SHU if b["bass"] else keycol(b["key"])
    base = (0.78, 0.26, 0.13) if b["bass"] else col
    if b["final"]: base = (0.85, 0.30, 0.15)
    pin(p, "Metallic", 0.45); pin(p, "Coat Weight", 0.8); pin(p, "Coat Roughness", 0.06)
    tco = node(nt, "ShaderNodeTexCoord"); sp_ = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tco.outputs["Object"], sp_.inputs[0])
    holes = None
    for sx in (-1, 1):
        dx = math_(nt, 'SUBTRACT', sp_.outputs["X"], vb=sx * b["L"] * 0.28)
        d2 = math_(nt, 'ADD', math_(nt, 'MULTIPLY', dx, dx), math_(nt, 'MULTIPLY', sp_.outputs["Y"], sp_.outputs["Y"]))
        h_ = math_(nt, 'LESS_THAN', d2, vb=0.022 ** 2)
        holes = h_ if holes is None else math_(nt, 'MAXIMUM', holes, h_)
    mixh = node(nt, "ShaderNodeMixRGB"); link(nt, holes, mixh.inputs[0]); mixh.inputs[1].default_value = base + (1,); mixh.inputs[2].default_value = (0.02, 0.015, 0.01, 1)
    link(nt, mixh.outputs[0], I(p, "Base Color"))
    # ヘアライン（長さ方向の細い筋）で、映り込みにむらを出す
    tc = node(nt, "ShaderNodeTexCoord"); mp = node(nt, "ShaderNodeMapping"); I(mp, "Scale").default_value = (2.0, 90.0, 2.0)
    link(nt, tc.outputs["Object"], I(mp, "Vector")); nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 4; I(nz, "Detail").default_value = 6
    link(nt, mp.outputs[0], I(nz, "Vector"))
    rr = node(nt, "ShaderNodeMapRange"); I(rr, "To Min").default_value = 0.2; I(rr, "To Max").default_value = 0.42
    link(nt, O(nz, "Fac"), I(rr, "Value")); link(nt, rr.outputs[0], I(p, "Roughness"))
    pin(p, "Emission Color", (SHU if (b["bass"] or b["final"]) else (1.0, 0.86, 0.62)) + (1,)); pin(p, "Emission Strength", 0.0)
    return m, p
BAR_OBJS = []
for i, b in enumerate(BARS):
    L, W, T = b["L"], b["W"], b["T"]; p0 = V(b["p"]); yaw = b["yaw"]
    bpy.ops.mesh.primitive_cube_add(size=1, location=p0 - V((0, 0, T / 2)))
    o = bpy.context.object; o.name = "bar%02d" % i; o.scale = (L, W, T); o.rotation_euler = (0, 0, yaw)
    bpy.ops.object.transform_apply(scale=True)
    bv = o.modifiers.new("b", 'BEVEL'); bv.width = 0.034; bv.segments = 6; bv.limit_method = 'NONE'
    m, p = bar_mat(i, b); o.data.materials.append(m)
    bpy.ops.object.shade_smooth(); o.data.use_auto_smooth = True; o.data.auto_smooth_angle = math.radians(40)
    # 支えの横木（板の長さの 22% の位置＝鳴る板の節）
    rails = []
    for s_ in (-1, 1):
        off = V((math.cos(yaw), math.sin(yaw), 0)) * (L * 0.28 * s_)
        bpy.ops.mesh.primitive_cube_add(size=1, location=p0 + off - V((0, 0, T + 0.035)))
        r = bpy.context.object; r.scale = (0.06, W + 0.12, 0.06); r.rotation_euler = (0, 0, yaw); r.data.materials.append(MAT_WOOD)
        bv2 = r.modifiers.new("b", 'BEVEL'); bv2.width = 0.01; bv2.segments = 2
        rails.append(r)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=W + 0.1, vertices=12, location=p0 + off - V((0, 0, T + 0.016)))
        cd_ = bpy.context.object; cd_.rotation_euler = (math.pi / 2, 0, yaw); cd_.data.materials.append(MAT_HIMO); rails.append(cd_)
    # 叩かれて光る・沈む（沈む量はうんこと同じ＝すき間0）
    e = I(p, "Emission Strength"); fh = b["fr"]
    peak = 9.0 if (b["bass"] or b["final"]) else 3.2
    hits_ = [fh] + ([POYON] if b["final"] else [])
    for fh_ in hits_:
        for ff, vv in ((fh_ - 1, 0.0), (fh_, peak), (fh_ + 3, peak * 0.45), (fh_ + 16, peak * 0.06), (fh_ + 34, 0.0)):
            e.default_value = vv; e.keyframe_insert("default_value", frame=ff)
    z0 = o.location.z; rail_z = [r.location.z for r in rails]
    for fs, dz in b["dz"].items():
        f_ = int(fs); o.location.z = z0 + dz; o.keyframe_insert("location", index=2, frame=f_)
        for r, z_ in zip(rails, rail_z): r.location.z = z_ + dz; r.keyframe_insert("location", index=2, frame=f_)
    anim_lin(o)
    BAR_OBJS.append((o, rails, m))
    # 波紋の輪（細く・控えめに）
    bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.008, location=p0 + V((0, 0, 0.006)))
    rg = bpy.context.object; rm_, rnt, rp = newmat("ringM%02d" % i); blend(rm_)
    pin(rp, "Base Color", (0, 0, 0, 1)); pin(rp, "Emission Color", (SHU if b["bass"] else (1.0, 0.9, 0.7)) + (1,)); pin(rp, "Alpha", 1.0)
    rg.data.materials.append(rm_)
    for fh_ in hits_:
        for ff, s_, ee in ((fh_ - 1, 0.001, 0.0), (fh_, 0.5, 6.0), (fh_ + 16, 2.6, 0.0), (fh_ + 17, 0.001, 0.0)):
            rg.scale = (s_, s_, s_); rg.keyframe_insert("scale", frame=ff)
            I(rp, "Emission Strength").default_value = ee; I(rp, "Emission Strength").keyframe_insert("default_value", frame=ff)
    b["ring"] = rg.name

# =====================================================================
# 粒（Geometry Nodes：時間から毎コマ計算＝どのコマから描いても同じ）
# =====================================================================
def spray(name, center, size, count, vmin, vmax, life, rad, mat, seed=0, grav=9.8, shrink=True, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=center); o = bpy.context.object; o.name = name; o.scale = (size[0], size[1], 1)
    o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)   # 速さ・粒の大きさを世界の単位のままにする
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    try:
        ng.inputs.new('NodeSocketGeometry', 'Geometry'); ng.outputs.new('NodeSocketGeometry', 'Geometry')
    except Exception:
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; Lk = ng.links.new
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces'); dist.inputs['Density'].default_value = count / max(0.01, size[0] * size[1]); dist.inputs['Seed'].default_value = seed
    Lk(gi.outputs[0], dist.inputs['Mesh'])
    tm = N.new('GeometryNodeInputSceneTime')
    rph = N.new('FunctionNodeRandomValue'); rph.data_type = 'FLOAT'; rph.inputs[2].default_value = 0; rph.inputs[3].default_value = 1; rph.inputs['Seed'].default_value = seed + 11
    def M_(op, a, b=None, vb=None):
        n = N.new('ShaderNodeMath'); n.operation = op; Lk(a, n.inputs[0])
        if b is not None: Lk(b, n.inputs[1])
        elif vb is not None: n.inputs[1].default_value = vb
        return n.outputs[0]
    age = M_('FRACT', M_('ADD', M_('DIVIDE', tm.outputs['Seconds'], vb=life), rph.outputs[1]))
    tt = M_('MULTIPLY', age, vb=life)
    rv = N.new('FunctionNodeRandomValue'); rv.data_type = 'FLOAT_VECTOR'; rv.inputs[0].default_value = vmin; rv.inputs[1].default_value = vmax; rv.inputs['Seed'].default_value = seed + 23
    vt = N.new('ShaderNodeVectorMath'); vt.operation = 'SCALE'; Lk(rv.outputs[0], vt.inputs[0]); Lk(tt, vt.inputs['Scale'])
    gz = M_('MULTIPLY', M_('MULTIPLY', tt, tt), vb=-0.5 * grav)
    cz = N.new('ShaderNodeCombineXYZ'); Lk(gz, cz.inputs['Z'])
    off = N.new('ShaderNodeVectorMath'); off.operation = 'ADD'; Lk(vt.outputs[0], off.inputs[0]); Lk(cz.outputs[0], off.inputs[1])
    spn = N.new('GeometryNodeSetPosition'); Lk(dist.outputs['Points'], spn.inputs['Geometry']); Lk(off.outputs[0], spn.inputs['Offset'])
    ico = N.new('GeometryNodeMeshIcoSphere'); ico.inputs['Radius'].default_value = rad; ico.inputs['Subdivisions'].default_value = 1
    inst = N.new('GeometryNodeInstanceOnPoints'); Lk(spn.outputs['Geometry'], inst.inputs['Points']); Lk(ico.outputs['Mesh'], inst.inputs['Instance'])
    rs = N.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'; rs.inputs[2].default_value = 0.4; rs.inputs[3].default_value = 1.3; rs.inputs['Seed'].default_value = seed + 37
    scl = M_('MULTIPLY', M_('SUBTRACT', M_('MULTIPLY', age, vb=-1.0), vb=-1.0) if shrink else rs.outputs[1], rs.outputs[1]) if shrink else rs.outputs[1]
    Lk(scl, inst.inputs['Scale'])
    smt = N.new('GeometryNodeSetMaterial'); smt.inputs['Material'].default_value = mat; Lk(inst.outputs['Instances'], smt.inputs['Geometry'])
    Lk(smt.outputs['Geometry'], go.inputs[0])
    md = o.modifiers.new('gn', 'NODES'); md.node_group = ng
    return o

def mat_drop(name, col=(0.92, 0.97, 1.0), em=0.7, alpha=0.85):
    m, nt, p = newmat(name); blend(m)
    pin(p, "Base Color", col + (1,)); pin(p, "Emission Color", col + (1,)); pin(p, "Emission Strength", em)
    pin(p, "Roughness", 0.1); pin(p, "Alpha", alpha); return m

# 板に当たったときの小さな光の粒（6個・板の色）
for i, b in enumerate(BARS):
    p0 = V(b["p"]); m = BAR_OBJS[i][2]
    for k in range(6):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.016, location=p0); d = bpy.context.object; d.data.materials.append(m)
        a2 = rnd.uniform(0, 2 * math.pi); sp_ = rnd.uniform(0.7, 1.5); up = rnd.uniform(1.0, 2.2)
        for fh_ in [b["fr"]] + ([POYON] if b["final"] else []):
            for ff in range(fh_ - 1, fh_ + 20):
                t = (ff - fh_) / FPS
                if t < 0: d.location = p0; d.scale = (0.001,) * 3
                else:
                    d.location = p0 + V((math.cos(a2) * sp_ * t, math.sin(a2) * sp_ * t, up * t - 3 * t * t))
                    s_ = max(0.001, 1 - t / 0.8); d.scale = (s_, s_, s_)
                d.keyframe_insert("location", frame=ff); d.keyframe_insert("scale", frame=ff)

# =====================================================================
# 共通の材料：岩・水・体積の霧
# =====================================================================
def mat_rock(name, moss=0.6, wet=0.0, dark=1.0, glow=None):
    m, nt, p = newmat(name)
    geo = node(nt, "ShaderNodeNewGeometry"); sep = node(nt, "ShaderNodeSeparateXYZ"); link(nt, geo.outputs["Normal"], sep.inputs[0])
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 3.0; I(nz, "Detail").default_value = 10; I(nz, "Roughness").default_value = 0.6
    link(nt, tc.outputs["Object"], I(nz, "Vector"))
    nz2 = node(nt, "ShaderNodeTexNoise"); I(nz2, "Scale").default_value = 18; I(nz2, "Detail").default_value = 6
    link(nt, tc.outputs["Object"], I(nz2, "Vector"))
    # 岩肌（玄武岩の灰〜こげ茶のむら）
    rr = node(nt, "ShaderNodeValToRGB")
    rr.color_ramp.elements[0].position = 0.35; rr.color_ramp.elements[0].color = (0.030 * dark, 0.028 * dark, 0.026 * dark, 1)
    rr.color_ramp.elements[1].position = 0.7; rr.color_ramp.elements[1].color = (0.11 * dark, 0.10 * dark, 0.085 * dark, 1)
    link(nt, O(nz2, "Fac"), I(rr, "Fac"))
    # 苔：上を向いた面に、まだらに
    mz = math_(nt, 'ADD', sep.outputs["Z"], math_(nt, 'MULTIPLY', O(nz, "Fac"), vb=0.9))
    mr = node(nt, "ShaderNodeMapRange"); I(mr, "From Min").default_value = 1.05 - moss * 0.35; I(mr, "From Max").default_value = 1.25 - moss * 0.35
    link(nt, mz, I(mr, "Value"))
    mos = node(nt, "ShaderNodeValToRGB"); mos.color_ramp.elements[0].color = (0.035, 0.07, 0.02, 1); mos.color_ramp.elements[1].color = (0.11, 0.17, 0.04, 1)
    link(nt, O(nz2, "Fac"), I(mos, "Fac"))
    mix = node(nt, "ShaderNodeMixRGB"); link(nt, mr.outputs[0], mix.inputs[0]); link(nt, rr.outputs[0], mix.inputs[1]); link(nt, mos.outputs[0], mix.inputs[2])
    if moss <= 0: mix.inputs[0].default_value = 0; nt.links.remove(mix.inputs[0].links[0])
    link(nt, mix.outputs[0], I(p, "Base Color"))
    # 濡れ：苔のないところはつやっぽく
    rgh = node(nt, "ShaderNodeMapRange"); I(rgh, "To Min").default_value = 0.85 - wet * 0.6; I(rgh, "To Max").default_value = 0.9
    link(nt, mr.outputs[0], I(rgh, "Value")); link(nt, rgh.outputs[0], I(p, "Roughness"))
    bm = node(nt, "ShaderNodeBump"); I(bm, "Strength").default_value = 0.55; I(bm, "Distance").default_value = 0.05
    hh = math_(nt, 'ADD', O(nz, "Fac"), math_(nt, 'MULTIPLY', O(nz2, "Fac"), vb=0.4))
    link(nt, hh, I(bm, "Height")); link(nt, bm.outputs["Normal"], I(p, "Normal"))
    if glow:
        pin(p, "Emission Color", glow + (1,)); link(nt, mr.outputs[0], I(p, "Emission Strength"))
    return m

def rock(name, loc, scale, mat, yaw=0.0, inward=0.18, sub=4, seed=0, safe=False):
    """形を外へは膨らませない岩（へこませるだけ）→ 当たり判定の楕円体からはみ出さない"""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale; o.rotation_euler = (0, 0, yaw)
    if not safe:
        tx = bpy.data.textures.new(name + "t", 'VORONOI'); tx.noise_scale = 0.55; tx.distance_metric = 'DISTANCE'
        dm = o.modifiers.new("d", 'DISPLACE'); dm.texture = tx; dm.strength = inward; dm.mid_level = 1.0; dm.texture_coords = 'LOCAL'
    tx2 = bpy.data.textures.new(name + "c", 'CLOUDS'); tx2.noise_scale = 0.3; tx2.noise_depth = 3
    dm2 = o.modifiers.new("d2", 'DISPLACE'); dm2.texture = tx2; dm2.strength = inward * 0.7; dm2.mid_level = 1.0; dm2.texture_coords = 'LOCAL'
    bpy.ops.object.shade_smooth(); o.data.materials.append(mat); return o

def mat_volume(name, dens, col=(0.85, 0.92, 0.95), aniso=0.4, noise=None, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL': nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    vs = nt.nodes.new("ShaderNodeVolumePrincipled"); I(vs, "Color").default_value = col + (1,); I(vs, "Anisotropy").default_value = aniso
    if noise:
        sc_, spd, lo, hi = noise
        tc = node(nt, "ShaderNodeTexCoord"); mp = node(nt, "ShaderNodeMapping"); link(nt, tc.outputs["Object"], I(mp, "Vector"))
        lo_ = I(mp, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1)
        lo_.default_value = spd; lo_.keyframe_insert("default_value", frame=NF)
        nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = sc_; I(nz, "Detail").default_value = 4
        link(nt, mp.outputs[0], I(nz, "Vector"))
        mr = node(nt, "ShaderNodeMapRange"); I(mr, "From Min").default_value = 0.42; I(mr, "From Max").default_value = 0.7
        I(mr, "To Min").default_value = lo * dens; I(mr, "To Max").default_value = hi * dens
        link(nt, O(nz, "Fac"), I(mr, "Value")); link(nt, mr.outputs[0], I(vs, "Density"))
        anim_lin(nt)
    else:
        I(vs, "Density").default_value = dens
    if emit:
        I(vs, "Emission Color").default_value = emit[0] + (1,); I(vs, "Emission Strength").default_value = emit[1]
    link(nt, vs.outputs[0], I(out, "Volume")); return m

def box(name, center, size, mat):
    if LITE and any(n.type == 'PRINCIPLED_VOLUME' for n in mat.node_tree.nodes) and max(size) > 30: return None
    bpy.ops.mesh.primitive_cube_add(size=1, location=center); o = bpy.context.object; o.name = name
    o.scale = size; o.data.materials.append(mat); return o

def mat_water(name, tint=(0.86, 0.95, 1.0), speed=4.0, bright=1.0, dens=0.6):
    """流れ落ちる水：細い筋が下へ速く流れ、白い泡の帯が混じる"""
    m, nt, p = newmat(name); blend(m, 'BLEND')
    tc = node(nt, "ShaderNodeTexCoord")
    def flow(scale, spd, det=6):
        mp = node(nt, "ShaderNodeMapping"); I(mp, "Scale").default_value = scale
        link(nt, tc.outputs["Object"], I(mp, "Vector"))
        lo_ = I(mp, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1)
        lo_.default_value = (0, 0, spd * NF / FPS * scale[2]); lo_.keyframe_insert("default_value", frame=NF)
        nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 1.0; I(nz, "Detail").default_value = det; I(nz, "Roughness").default_value = 0.55
        link(nt, mp.outputs[0], I(nz, "Vector")); return O(nz, "Fac")
    a = flow((7.0, 7.0, 0.16), speed * 0.8)     # 太い筋
    b = flow((22.0, 22.0, 0.35), speed * 1.25)  # 細い筋（速い）
    c = flow((3.0, 3.0, 0.6), speed * 1.0, 3)   # 泡のかたまり
    anim_lin(nt)
    st = math_(nt, 'MULTIPLY', a, b)
    rs = node(nt, "ShaderNodeMapRange"); I(rs, "From Min").default_value = 0.10; I(rs, "From Max").default_value = 0.40
    link(nt, st, I(rs, "Value"))
    foam = node(nt, "ShaderNodeMapRange"); I(foam, "From Min").default_value = 0.56; I(foam, "From Max").default_value = 0.72; link(nt, c, I(foam, "Value"))
    tot = math_(nt, 'MAXIMUM', rs.outputs[0], foam.outputs[0])
    col = node(nt, "ShaderNodeMixRGB"); I(col, "Color1").default_value = (tint[0] * 0.35, tint[1] * 0.48, tint[2] * 0.5, 1)
    I(col, "Color2").default_value = tint + (1,); link(nt, tot, I(col, "Fac"))
    link(nt, col.outputs[0], I(p, "Base Color")); link(nt, col.outputs[0], I(p, "Emission Color")); pin(p, "Roughness", 0.08)
    al = node(nt, "ShaderNodeMapRange"); I(al, "To Min").default_value = 0.18 * dens; I(al, "To Max").default_value = 0.95 * dens + 0.05
    link(nt, tot, I(al, "Value")); link(nt, al.outputs[0], I(p, "Alpha"))
    link(nt, math_(nt, 'MULTIPLY', tot, vb=bright), I(p, "Emission Strength"))
    return m

def curtain(name, x0, x1, ytop, zt, zb, mat, bend=1.2, nseg=48, lip=0.6):
    verts = []; faces = []; NZ = 40
    for j in range(NZ + 1):
        z = zt + (zb - zt) * j / NZ
        for i in range(nseg + 1):
            u = i / nseg; x = x0 + (x1 - x0) * u
            y = ytop + bend * (2 * u - 1) ** 2 - lip * (1 - j / NZ) ** 6     # 上の縁で手前へ張り出してから落ちる
            verts.append((x, y, z))
    for j in range(NZ):
        for i in range(nseg):
            a = j * (nseg + 1) + i; faces.append((a, a + 1, a + nseg + 2, a + nseg + 1))
    return obj_from_mesh(name, verts, faces, mat)

def leaf_cards(name, base, n, img, size, outward, droop=0.0, seed=0):
    """シダ・葉の板（両面・切り抜き）を、根元から放射状に"""
    r_ = random.Random(seed)
    m = bpy.data.materials.get("leaf_" + img)
    if not m:
        m, nt, p = newmat("leaf_" + img); blend(m, 'CLIP', 'CLIP'); tryset(m, alpha_threshold=0.5)
        tx = node(nt, "ShaderNodeTexImage"); tx.image = load_img(img)
        hsv = node(nt, "ShaderNodeHueSaturation"); I(hsv, "Value").default_value = 1.0; link(nt, tx.outputs["Color"], I(hsv, "Color"))
        link(nt, hsv.outputs[0], I(p, "Base Color")); link(nt, tx.outputs["Alpha"], I(p, "Alpha"))
        pin(p, "Roughness", 0.45); pin(p, "Specular IOR Level", 0.35)
        pin(p, "Subsurface Weight", 0.02); pin(p, "Subsurface Color", (0.3, 0.6, 0.1, 1))
        tryset(m, use_sss_translucency=True)
    verts = []; faces = []; uvs = []
    for k in range(n):
        ang = math.atan2(outward[1], outward[0]) + r_.uniform(-1.0, 1.0)
        tilt = r_.uniform(0.2, 0.9) + droop; s = size * r_.uniform(0.7, 1.2); w = s * 0.5
        d = V((math.cos(ang), math.sin(ang), 0)); side = V((-math.sin(ang), math.cos(ang), 0))
        tip = d * (s * math.cos(tilt)) + V((0, 0, s * math.sin(tilt) * (1 if droop < 0.9 else -1)))
        b0 = len(verts)
        for (u, vv) in ((0, 0), (1, 0), (1, 1), (0, 1)):
            pnt = V(base) + side * ((u - 0.5) * w) + tip * vv
            pnt.z -= 0.25 * s * vv * vv * droop
            verts.append(tuple(pnt)); uvs.append((u, vv))
        faces.append((b0, b0 + 1, b0 + 2, b0 + 3))
    o = obj_from_mesh(name, verts, faces, m)
    uvl_ = o.data.uv_layers.new(name="UV")
    for li, lp in enumerate(o.data.loops): uvl_.data[li].uv = uvs[lp.vertex_index]
    return o

# =====================================================================
# 廃墟の材料：コンクリート（汚れ・苔・錆のしみ・ひび・濡れ）・錆びた鉄筋・割れたガラス・水たまり
# =====================================================================
def mat_concrete(name, moss=0.5, grime=1.0, wet_z=None, tone=1.0, rust=0.5):
    m, nt, p = newmat(name)
    geo = node(nt, "ShaderNodeNewGeometry"); sepn = node(nt, "ShaderNodeSeparateXYZ"); link(nt, geo.outputs["Normal"], sepn.inputs[0])
    sepp = node(nt, "ShaderNodeSeparateXYZ"); link(nt, geo.outputs["Position"], sepp.inputs[0])
    def nz(scale, det=4, rough=0.5, vec=None):
        n = node(nt, "ShaderNodeTexNoise"); I(n, "Scale").default_value = scale; I(n, "Detail").default_value = det; I(n, "Roughness").default_value = rough
        link(nt, vec or geo.outputs["Position"], I(n, "Vector")); return O(n, "Fac")
    big = nz(0.35, 3); grain = nz(22, 8, 0.6); fine = nz(90, 4, 0.5)
    # 縦に流れる汚れ（雨だれ）：縦につぶしたノイズ × 壁（法線が横）
    mp = node(nt, "ShaderNodeMapping"); I(mp, "Scale").default_value = (3.0, 3.0, 0.12); link(nt, geo.outputs["Position"], I(mp, "Vector"))
    streak = nz(1.0, 5, 0.65, mp.outputs[0])
    wallness = math_(nt, 'SUBTRACT', va=1.0, b=math_(nt, 'ABSOLUTE', sepn.outputs["Z"]))
    st_amt = math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', streak, wallness), vb=0.55 * grime)
    # 色：生コン灰（むら）→ 汚れで暗く
    col = node(nt, "ShaderNodeValToRGB"); el = col.color_ramp.elements
    el[0].position = 0.3; el[0].color = (0.085 * tone, 0.082 * tone, 0.078 * tone, 1); el[1].position = 0.75; el[1].color = (0.26 * tone, 0.25 * tone, 0.235 * tone, 1)
    mixbg = math_(nt, 'ADD', math_(nt, 'MULTIPLY', big, vb=0.6), math_(nt, 'MULTIPLY', grain, vb=0.4)); link(nt, mixbg, I(col, "Fac"))
    dark = node(nt, "ShaderNodeMixRGB"); dark.blend_type = 'MULTIPLY'; link(nt, st_amt, dark.inputs[0]); link(nt, col.outputs[0], dark.inputs[1]); dark.inputs[2].default_value = (0.22, 0.21, 0.20, 1)
    # ひび：ボロノイの縁
    vor = node(nt, "ShaderNodeTexVoronoi"); vor.feature = 'DISTANCE_TO_EDGE'; I(vor, "Scale").default_value = 2.6; link(nt, geo.outputs["Position"], I(vor, "Vector"))
    crack = math_(nt, 'LESS_THAN', O(vor, "Distance"), vb=0.006)
    crk = math_(nt, 'MULTIPLY', crack, math_(nt, 'GREATER_THAN', big, vb=0.56))   # ひびは一部の面だけ（細く・まばらに）
    dark2 = node(nt, "ShaderNodeMixRGB"); dark2.blend_type = 'MULTIPLY'; link(nt, crk, dark2.inputs[0]); link(nt, dark.outputs[0], dark2.inputs[1]); dark2.inputs[2].default_value = (0.25, 0.25, 0.25, 1)
    # 錆のしみ（鉄筋から流れる赤茶）
    rv = node(nt, "ShaderNodeTexVoronoi"); I(rv, "Scale").default_value = 0.5; link(nt, mp.outputs[0], I(rv, "Vector"))
    rspot = math_(nt, 'MULTIPLY', math_(nt, 'LESS_THAN', O(rv, "Distance"), vb=0.22 * rust), math_(nt, 'MULTIPLY', streak, wallness))
    rustc = node(nt, "ShaderNodeMixRGB"); link(nt, math_(nt, 'MULTIPLY', rspot, vb=1.6), rustc.inputs[0]); link(nt, dark2.outputs[0], rustc.inputs[1]); rustc.inputs[2].default_value = (0.30, 0.10, 0.04, 1)
    # 苔：上向きの面と、低い所（湿気）に、まだらに
    upness = node(nt, "ShaderNodeMapRange"); I(upness, "From Min").default_value = 0.55; I(upness, "From Max").default_value = 0.95; link(nt, sepn.outputs["Z"], I(upness, "Value"))
    mossn = math_(nt, 'MULTIPLY', math_(nt, 'GREATER_THAN', nz(2.2, 5, 0.6), vb=0.60 - 0.1 * moss), upness.outputs[0])
    if wet_z is not None:
        lowz = node(nt, "ShaderNodeMapRange"); I(lowz, "From Min").default_value = wet_z + 2.5; I(lowz, "From Max").default_value = wet_z + 0.2; link(nt, sepp.outputs["Z"], I(lowz, "Value"))
        mossn = math_(nt, 'MAXIMUM', mossn, math_(nt, 'MULTIPLY', math_(nt, 'GREATER_THAN', nz(3.0, 5, 0.6), vb=0.50), math_(nt, 'MULTIPLY', lowz.outputs[0], vb=0.8 * moss)))
    mossc = node(nt, "ShaderNodeValToRGB"); mossc.color_ramp.elements[0].color = (0.03, 0.06, 0.015, 1); mossc.color_ramp.elements[1].color = (0.10, 0.17, 0.04, 1)
    link(nt, grain, I(mossc, "Fac"))
    fin = node(nt, "ShaderNodeMixRGB"); link(nt, math_(nt, 'MULTIPLY', mossn, vb=moss), fin.inputs[0]); link(nt, rustc.outputs[0], fin.inputs[1]); link(nt, mossc.outputs[0], fin.inputs[2])
    link(nt, fin.outputs[0], I(p, "Base Color"))
    # 粗さ：コンクリは 0.7〜0.85、濡れた所はつや
    rgh = node(nt, "ShaderNodeMapRange"); I(rgh, "To Min").default_value = 0.68; I(rgh, "To Max").default_value = 0.88; link(nt, fine, I(rgh, "Value"))
    rout = rgh.outputs[0]
    if wet_z is not None:
        wetr = node(nt, "ShaderNodeMixRGB"); link(nt, lowz.outputs[0], wetr.inputs[0]); link(nt, rout, wetr.inputs[1]); wetr.inputs[2].default_value = (0.18, 0.18, 0.18, 1); rout = wetr.outputs[0]
    link(nt, rout, I(p, "Roughness")); pin(p, "Specular IOR Level", 0.45)
    bm = node(nt, "ShaderNodeBump"); I(bm, "Strength").default_value = 0.45; I(bm, "Distance").default_value = 0.03
    hh = math_(nt, 'SUBTRACT', math_(nt, 'ADD', math_(nt, 'MULTIPLY', grain, vb=0.5), math_(nt, 'MULTIPLY', fine, vb=0.3)), math_(nt, 'MULTIPLY', crk, vb=0.8))
    link(nt, hh, I(bm, "Height")); link(nt, bm.outputs["Normal"], I(p, "Normal"))
    return m

def mat_rust(name):
    m, nt, p = newmat(name)
    geo = node(nt, "ShaderNodeNewGeometry")
    n1 = node(nt, "ShaderNodeTexNoise"); I(n1, "Scale").default_value = 14; I(n1, "Detail").default_value = 6; link(nt, geo.outputs["Position"], I(n1, "Vector"))
    cr = node(nt, "ShaderNodeValToRGB"); el = cr.color_ramp.elements; el[0].position = 0.35; el[0].color = (0.16, 0.05, 0.02, 1); el[1].position = 0.7; el[1].color = (0.42, 0.18, 0.07, 1)
    link(nt, O(n1, "Fac"), I(cr, "Fac")); link(nt, cr.outputs[0], I(p, "Base Color"))
    rg = node(nt, "ShaderNodeMapRange"); I(rg, "To Min").default_value = 0.55; I(rg, "To Max").default_value = 0.9; link(nt, O(n1, "Fac"), I(rg, "Value")); link(nt, rg.outputs[0], I(p, "Roughness"))
    pin(p, "Metallic", 0.35)
    bm = node(nt, "ShaderNodeBump"); I(bm, "Strength").default_value = 0.6; I(bm, "Distance").default_value = 0.01; link(nt, O(n1, "Fac"), I(bm, "Height")); link(nt, bm.outputs[0], I(p, "Normal"))
    return m

def mat_glass(name):
    m, nt, p = newmat(name); blend(m, 'BLEND', 'HASHED')
    pin(p, "Base Color", (0.85, 0.92, 0.9, 1)); pin(p, "Roughness", 0.06); pin(p, "Transmission Weight", 0.92); pin(p, "IOR", 1.5); pin(p, "Alpha", 0.55)
    tryset(m, use_screen_refraction=True, refraction_depth=0.004)
    return m

def mat_puddle(name, col=(0.010, 0.014, 0.016), ripple=0.08, speed=(0, -3, 1.5)):
    """静かな水面：映り込みが命（粗さ 0.02）・ゆっくり揺れる細かい波"""
    m, nt, p = newmat(name); pin(p, "Base Color", col + (1,)); pin(p, "Roughness", 0.02); pin(p, "Specular IOR Level", 1.0); pin(p, "IOR", 1.33)
    tc = node(nt, "ShaderNodeTexCoord"); mp = node(nt, "ShaderNodeMapping"); link(nt, tc.outputs["Object"], I(mp, "Vector"))
    lo_ = I(mp, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1); lo_.default_value = speed; lo_.keyframe_insert("default_value", frame=NF)
    n1 = node(nt, "ShaderNodeTexNoise"); I(n1, "Scale").default_value = 2.2; I(n1, "Detail").default_value = 5; link(nt, mp.outputs[0], I(n1, "Vector"))
    bm = node(nt, "ShaderNodeBump"); I(bm, "Strength").default_value = ripple; I(bm, "Distance").default_value = 0.1; link(nt, O(n1, "Fac"), I(bm, "Height")); link(nt, bm.outputs[0], I(p, "Normal"))
    anim_lin(nt); return m

def cube(name, loc, size, mat, yaw=0.0, bevel=0.03, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name; o.scale = size
    o.rotation_euler = rot if rot else (0, 0, yaw)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        bv = o.modifiers.new("b", 'BEVEL'); bv.width = bevel; bv.segments = 2; bv.limit_method = 'NONE'
    o.data.materials.append(mat); return o

def rebar(name, p0, p1, mat, r=0.012):
    d = V(p1) - V(p0); L = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, vertices=8, location=(V(p0) + V(p1)) / 2); o = bpy.context.object; o.name = name
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(mat); return o

def ring_mesh(name, cen, r_of, phi0, phi1, z0, z1, nphi, nz, mat, inward=True):
    """円筒の一部の面（φ0→φ1、z0→z1）。r_of(φ, v) で半径を決める（v=0 下〜1 上）"""
    verts = []; faces = []; uvs = []
    for j in range(nz + 1):
        v = j / nz; z = z0 + (z1 - z0) * v
        for i in range(nphi + 1):
            u = i / nphi; ph = phi0 + (phi1 - phi0) * u; r = r_of(ph, v)
            verts.append((cen[0] + r * math.cos(ph), cen[1] + r * math.sin(ph), z)); uvs.append((u, v))
    for j in range(nz):
        for i in range(nphi):
            a_ = j * (nphi + 1) + i
            faces.append((a_, a_ + nphi + 1, a_ + nphi + 2, a_ + 1) if inward else (a_, a_ + 1, a_ + nphi + 2, a_ + nphi + 1))
    o = obj_from_mesh(name, verts, faces, mat)
    uvl_ = o.data.uv_layers.new(name="UV")
    for li, lp in enumerate(o.data.loops): uvl_.data[li].uv = uvs[lp.vertex_index]
    return o

# =====================================================================
# 舞台A：廃墟の吹き抜け（崩れたコンクリートの円形ホール。床は水に沈み、割れた天井から光の筋）
# =====================================================================
def build_haikyo_hall():
    A = SC["A"]; cen = A["center"]; RW = A["R_wall"]; zt = A["ztop"]; pz = A["pool_z"]
    conc = mat_concrete("concA", moss=0.4, grime=1.1, wet_z=pz, tone=1.0, rust=0.6)
    concD = mat_concrete("concA_dark", moss=0.15, grime=1.2, wet_z=pz, tone=0.4, rust=0.3)
    rust = mat_rust("rustA"); glass = mat_glass("glassA")
    ZTOP = zt + 8.6; NSEG = 36; DR = 3.2; TH = 0.36
    # 外の皮（いちばん奥の壁・暗い）
    w_ = ring_mesh("kabe_oku", cen, lambda ph, v: RW + DR + 0.5, 0, 2 * math.pi, pz - 2, ZTOP + 1.5, 180, 40, concD)
    t1 = bpy.data.textures.new("kabe1", 'CLOUDS'); t1.noise_scale = 1.2; t1.noise_depth = 3
    d1 = w_.modifiers.new("d1", 'DISPLACE'); d1.texture = t1; d1.strength = 0.25; d1.mid_level = 0.5; d1.texture_coords = 'GLOBAL'
    # 各階の床（輪の板を36分割。ところどころ崩れ落ちて、鉄筋が出ている）
    floors = []; z = pz + 1.6; k = 0
    while z < ZTOP + 0.1:
        floors.append(z); z += 3.4; k += 1
    gaps = set()
    for fi, zf in enumerate(floors):
        top = fi == len(floors) - 1
        ngap = 14 if top else rnd.randint(2, 5)
        g = set(rnd.sample(range(NSEG), ngap)); gaps |= {(fi, i) for i in g}
        for i in range(NSEG):
            if i in g:
                # 崩れた所：縁に鉄筋
                ph = 2 * math.pi * (i + 0.5) / NSEG
                for j in range(3):
                    rr = RW + 0.2 + j * 0.5; p0 = (cen[0] + rr * math.cos(ph) + rnd.uniform(-0.3, 0.3), cen[1] + rr * math.sin(ph) + rnd.uniform(-0.3, 0.3), zf - 0.1)
                    p1 = (p0[0] + rnd.uniform(-0.5, 0.5), p0[1] + rnd.uniform(-0.5, 0.5), zf - rnd.uniform(0.5, 1.4))
                    rebar("tekkin%02d_%02d_%d" % (fi, i, j), p0, p1, rust)
                continue
            ph = 2 * math.pi * (i + 0.5) / NSEG; rmid = RW + DR / 2
            arc = 2 * math.pi * (RW + DR) / NSEG * 1.04
            o = cube("yuka%02d_%02d" % (fi, i), (cen[0] + rmid * math.cos(ph), cen[1] + rmid * math.sin(ph), zf - TH / 2), (DR, arc, TH), conc, ph, 0.04)
            if rnd.random() < 0.25:   # 縁が欠けて傾く
                o.rotation_euler = (rnd.uniform(-0.04, 0.04), rnd.uniform(-0.03, 0.03), ph)
    # 柱（床と床の間・一部は折れている）
    for i in range(0, NSEG, 3):
        ph = 2 * math.pi * (i + 0.5) / NSEG; rr = RW + 0.35
        for fi in range(len(floors) - 1):
            z0, z1 = floors[fi], floors[fi + 1] - TH
            if rnd.random() < 0.18:
                zb = z0 + rnd.uniform(0.6, 2.0); cube("hashira%02d_%02d" % (fi, i), (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), (z0 + zb) / 2), (0.55, 0.55, zb - z0), conc, ph, 0.03)
                for j in range(4):
                    rebar("hashira_tekkin%02d_%02d_%d" % (fi, i, j), (cen[0] + rr * math.cos(ph) + rnd.uniform(-0.15, 0.15), cen[1] + rr * math.sin(ph) + rnd.uniform(-0.15, 0.15), zb - 0.05),
                          (cen[0] + rr * math.cos(ph) + rnd.uniform(-0.35, 0.35), cen[1] + rr * math.sin(ph) + rnd.uniform(-0.35, 0.35), zb + rnd.uniform(0.4, 1.1)), rust)
            else:
                cube("hashira%02d_%02d" % (fi, i), (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), (z0 + z1) / 2), (0.55, 0.55, z1 - z0), conc, ph, 0.03)
    # 奥の柱（外の皮の手前・濃い影）
    for i in range(1, NSEG, 4):
        ph = 2 * math.pi * (i + 0.5) / NSEG; rr = RW + DR - 0.3
        cube("okuhashira%02d" % i, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), (pz + ZTOP) / 2), (0.7, 0.7, ZTOP - pz), concD, ph, 0.0)
    # 崩れた天井の縁（がれき）と、上に落ちかけた板
    for k in range(30):
        ph = 2 * math.pi * k / 30 + rnd.uniform(-0.1, 0.1); rr = RW + rnd.uniform(0.6, 2.6)
        rock("gareki%02d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), ZTOP + rnd.uniform(0.1, 0.5)), (rnd.uniform(0.6, 1.4), rnd.uniform(0.5, 1.1), rnd.uniform(0.3, 0.7)), conc, ph, 0.25, 3)
    for k in range(5):
        ph = 2 * math.pi * k / 5 + 0.4; rr = RW + 1.0
        cube("ochiita%d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), ZTOP - rnd.uniform(0.6, 2.2)), (2.6, 1.3, 0.3), conc, 0.0, 0.04, rot=(rnd.uniform(0.3, 0.7) * rnd.choice((-1, 1)), rnd.uniform(-0.3, 0.3), ph))
    # 床の上のがれき・割れたガラス（内側の縁に）
    for fi, zf in enumerate(floors[:-1]):
        for k in range(10):
            i = rnd.randrange(NSEG)
            if (fi, i) in gaps: continue
            ph = 2 * math.pi * (i + rnd.uniform(0.1, 0.9)) / NSEG; rr = RW + rnd.uniform(0.3, DR - 0.4)
            if rnd.random() < 0.5:
                rock("kuzu%02d_%02d" % (fi, k), (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), zf + 0.12), (rnd.uniform(0.15, 0.4), rnd.uniform(0.12, 0.3), rnd.uniform(0.08, 0.2)), conc, rnd.uniform(0, 3), 0.2, 2)
            else:
                cube("glass%02d_%02d" % (fi, k), (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), zf + 0.006), (rnd.uniform(0.2, 0.6), rnd.uniform(0.15, 0.4), 0.008), glass, rnd.uniform(0, 3), 0.0)
    # 水：割れた配管から落ちる1本の滝と、壁をつたう細い水
    wA = mat_water("waterA", (0.86, 0.95, 1.0), 4.5, 0.7, 0.62); wA2 = mat_water("waterA2", (0.70, 0.86, 0.92), 3.0, 0.5, 0.4)
    FALLS = [(math.radians(90), math.radians(5)), (math.radians(215), math.radians(1.6)), (math.radians(320), math.radians(1.4))]
    for k, (ph0, wd) in enumerate(FALLS):
        ring_mesh("taki%d" % k, cen, lambda ph, v: RW - 0.15 - 0.25 * v ** 8, ph0 - wd / 2, ph0 + wd / 2, pz - 0.5, ZTOP - 0.6, 6, 50, wA if k == 0 else wA2)
        if k == 0:   # 配管（錆）
            rebar("haikan", (cen[0] + (RW + 2.4) * math.cos(ph0), cen[1] + (RW + 2.4) * math.sin(ph0), ZTOP - 0.4), (cen[0] + (RW - 0.3) * math.cos(ph0), cen[1] + (RW - 0.3) * math.sin(ph0), ZTOP - 0.7), rust, 0.14)
    # 板の下：崩れたコンクリの塊（当たり判定の楕円体と同じ大きさ）
    for b in BARS:
        if b["stage"] != "A": continue
        p0 = V(b["p"]); L, W = b["L"], b["W"]
        rock("ledge%02d" % b["i"], p0 + V((0, 0, -0.40)), (L * 0.40, W * 0.70, 0.22), conc, b["yaw"], 0.10, 4, safe=True)
    # 沈んだ床（水面）：映り込みが命
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=RW + DR + 1.0, fill_type='NGON', location=(cen[0], cen[1], pz)); bpy.context.object.data.materials.append(mat_puddle("poolA"))
    # 水の中から出ているがれき
    for k in range(18):
        ph = rnd.uniform(0, 2 * math.pi); rr = RW - rnd.uniform(0.2, 1.4)
        rock("mizu_gareki%02d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), pz - 0.3), (rnd.uniform(0.5, 1.3), rnd.uniform(0.4, 1.0), rnd.uniform(0.4, 0.9)), conc, ph, 0.3, 3)
    drop = mat_drop("shibuki")
    ph0 = FALLS[0][0]; rr = RW - 0.5
    spray("shibuki0", (cen[0] + rr * math.cos(ph0), cen[1] + rr * math.sin(ph0), pz + 0.05), (1.2, 1.2), 220, (-math.cos(ph0) * 0.5 - 0.5, -math.sin(ph0) * 0.5 - 0.5, 1.6), (-math.cos(ph0) * 2.2 + 0.5, -math.sin(ph0) * 2.2 + 0.5, 4.0), 1.0, 0.022, drop, 3)
    # 埃の粒（光の筋の中で光る）と、うすい霧（光の筋が見える）
    mote = mat_drop("hokori", (1.0, 0.96, 0.88), 1.6, 0.5)
    spray("hokori", (cen[0], cen[1], (zt + pz) / 2 + 2), (RW * 1.7, RW * 1.7), 420, (-0.12, -0.12, -0.06), (0.12, 0.12, 0.08), 7.0, 0.009, mote, 3, 0.0, False)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=RW + 0.5, depth=3.5, location=(cen[0], cen[1], pz + 1.4)); ks = bpy.context.object; ks.name = "kiri_soko"
    ks.data.materials.append(mat_volume("kiriA_soko", 0.7, (0.90, 0.93, 0.95), 0.3, (0.9, (0.6, 0, 0.9), 0.0, 1.0)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=RW + 0.5, depth=ZTOP - pz + 6, location=(cen[0], cen[1], (ZTOP + pz) / 2)); kz = bpy.context.object; kz.name = "kiri_zentai"
    kz.data.materials.append(mat_volume("kiriA", 0.055, (0.95, 0.93, 0.85), 0.8))
    # 光：割れた天井から差す太陽（低め・光の筋）、空の青い回り込み、水面の照り返し
    ld = bpy.data.lights.new("sunA", 'SUN'); ld.energy = 40.0; ld.color = (1.0, 0.86, 0.64); ld.angle = math.radians(1.0)
    lo = bpy.data.objects.new("sunA", ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(-46), math.radians(14), math.radians(150))
    ld2 = bpy.data.lights.new("fillA", 'AREA'); ld2.energy = 420; ld2.size = 14; ld2.color = (0.95, 0.88, 0.76)
    lo2 = bpy.data.objects.new("fillA", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cen[0], cen[1], ZTOP + 4); lo2.rotation_euler = (0, 0, 0)
    ld3 = bpy.data.lights.new("mizu_glow", 'AREA'); ld3.energy = 220; ld3.size = 14; ld3.color = (0.6, 0.8, 0.9)
    lo3 = bpy.data.objects.new("mizu_glow", ld3); bpy.context.collection.objects.link(lo3)
    lo3.location = (cen[0], cen[1], pz + 0.3); lo3.rotation_euler = (math.pi, 0, 0)
    # 植物：床の縁のシダ・天井から垂れるつる・水辺の大きな葉
    for k in range(80):
        fi = rnd.randrange(len(floors) - 1); i = rnd.randrange(NSEG)
        ph = 2 * math.pi * (i + rnd.uniform(0.1, 0.9)) / NSEG; rr = RW + rnd.uniform(0.0, 0.5)
        leaf_cards("shida%02d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), floors[fi] + 0.02), rnd.randint(4, 7), rnd.choice(("shida_a.png", "shida_b.png")), rnd.uniform(0.5, 1.0),
                   (-math.cos(ph), -math.sin(ph), 0), rnd.choice((0.0, 0.0, 0.6)), k)
    for k in range(12):
        ph = rnd.uniform(0, 2 * math.pi); rr = RW - 0.6
        leaf_cards("ha%02d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), pz + 0.05), rnd.randint(3, 5), "ha_ooki.png", rnd.uniform(0.9, 1.5), (-math.cos(ph), -math.sin(ph), 0), 0.0, 100 + k)
    for k in range(26):
        ph = rnd.uniform(0, 2 * math.pi); rr = RW + rnd.uniform(0.1, 1.5)
        leaf_cards("tsuru%02d" % k, (cen[0] + rr * math.cos(ph), cen[1] + rr * math.sin(ph), ZTOP + rnd.uniform(-2.5, 0.2)), 3, "shida_b.png", rnd.uniform(1.2, 2.4), (-math.cos(ph), -math.sin(ph), 0), 1.6, 200 + k)
    return [lo, lo2, lo3]

# =====================================================================
# 舞台B：水に沈んだ廃墟の夜（月・崩れた塔のまわりを上る・遠くに崩れた街のシルエット）
# =====================================================================
def build_haikyo_yoru():
    B = SC["B"]; ct = B["cloud_top"]; cx, cy = B["cx"], B["cy"]
    PE = V(M["pe"]); MOON = V(M["moon"]); LOGO = V(M["logo"])
    WZ = ct - 0.35
    conc = mat_concrete("concB", moss=0.6, grime=1.0, wet_z=WZ, tone=0.8, rust=0.6)
    concF = mat_concrete("concB_far", moss=0.0, grime=0.6, wet_z=None, tone=0.5, rust=0.0)
    # 遠くのビル：窓の格子（へこんだ暗い窓・ところどころ灯りが残る）
    ntF = concF.node_tree; pF = ntF.nodes["Principled BSDF"]
    geoF = node(ntF, "ShaderNodeNewGeometry"); sepF = node(ntF, "ShaderNodeSeparateXYZ"); link(ntF, geoF.outputs["Position"], sepF.inputs[0])
    sepN = node(ntF, "ShaderNodeSeparateXYZ"); link(ntF, geoF.outputs["Normal"], sepN.inputs[0])
    def grid(src, period, fill):
        return math_(ntF, 'LESS_THAN', math_(ntF, 'FRACT', math_(ntF, 'DIVIDE', src, vb=period)), vb=fill)
    horiz = math_(ntF, 'ADD', math_(ntF, 'MULTIPLY', sepF.outputs["X"], math_(ntF, 'ABSOLUTE', sepN.outputs["Y"])), math_(ntF, 'MULTIPLY', sepF.outputs["Y"], math_(ntF, 'ABSOLUTE', sepN.outputs["X"])))
    win = math_(ntF, 'MULTIPLY', math_(ntF, 'MULTIPLY', grid(horiz, 2.6, 0.55), grid(sepF.outputs["Z"], 3.4, 0.5)), math_(ntF, 'SUBTRACT', va=1.0, b=math_(ntF, 'ABSOLUTE', sepN.outputs["Z"])))
    vw = node(ntF, "ShaderNodeTexVoronoi"); I(vw, "Scale").default_value = 0.45; link(ntF, geoF.outputs["Position"], I(vw, "Vector"))
    lit = math_(ntF, 'MULTIPLY', win, math_(ntF, 'LESS_THAN', O(vw, "Distance"), vb=0.16))
    basein = I(pF, "Base Color").links[0].from_socket
    mixw = node(ntF, "ShaderNodeMixRGB"); link(ntF, win, mixw.inputs[0]); link(ntF, basein, mixw.inputs[1]); mixw.inputs[2].default_value = (0.012, 0.014, 0.02, 1)
    link(ntF, mixw.outputs[0], I(pF, "Base Color"))
    pin(pF, "Emission Color", (1.0, 0.72, 0.42, 1)); link(ntF, math_(ntF, 'MULTIPLY', lit, vb=3.0), I(pF, "Emission Strength"))
    rust = mat_rust("rustB")
    # 水面（広く）：月と街の映り込み
    bpy.ops.mesh.primitive_plane_add(size=900, location=(cx, cy + 150, WZ)); wp = bpy.context.object; wp.name = "mizu_men"
    wp.data.materials.append(mat_puddle("mizuB", (0.006, 0.008, 0.014), 0.06, (0, -2, 1)))
    # 水面の上の霧
    box("kiriB", (cx, cy + 150, WZ + 0.5), (900, 900, 1.4), mat_volume("kiriB", 0.16, (0.55, 0.6, 0.9), 0.35, (0.08, (8, 3, 0), 0.0, 1.0)))
    # 落ちてくるときにくぐる霧のかたまり（最初の板の少し上）
    P17 = V(BARS[M["split"] + 1]["p"])
    box("kumo_kuguru", (P17.x, P17.y, P17.z + 4.2), (14, 14, 2.4), mat_volume("kuguru", 1.6, (0.80, 0.82, 0.95), 0.2, (0.6, (0, 0, -3), 0.2, 1.0)))
    # 月
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=17, location=MOON); mo = bpy.context.object
    mm, ntm, pm = newmat("tsuki")
    nzm = node(ntm, "ShaderNodeTexNoise"); I(nzm, "Scale").default_value = 2.2; I(nzm, "Detail").default_value = 6
    rm2 = node(ntm, "ShaderNodeValToRGB"); rm2.color_ramp.elements[0].color = (0.78, 0.74, 0.66, 1); rm2.color_ramp.elements[1].color = (1.0, 0.96, 0.86, 1)
    link(ntm, O(nzm, "Fac"), I(rm2, "Fac")); link(ntm, rm2.outputs[0], I(pm, "Base Color")); link(ntm, rm2.outputs[0], I(pm, "Emission Color"))
    pin(pm, "Emission Strength", 4.5); mo.data.materials.append(mm)
    ld = bpy.data.lights.new("moonB", 'SUN'); ld.energy = 3.6; ld.color = (0.74, 0.80, 1.0); ld.angle = math.radians(1.5)
    lo = bpy.data.objects.new("moonB", ld); bpy.context.collection.objects.link(lo)
    dirm = (MOON - PE).normalized(); lo.rotation_euler = (-dirm).to_track_quat('-Z', 'Y').to_euler()
    ld2 = bpy.data.lights.new("rimB", 'AREA'); ld2.energy = 300; ld2.size = 10; ld2.color = (0.85, 0.6, 1.0)
    lo2 = bpy.data.objects.new("rimB", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cx - 3, cy + 10, ct + 7); lo2.rotation_euler = (math.radians(-110), 0, 0)
    ld3 = bpy.data.lights.new("fillB", 'AREA'); ld3.energy = 140; ld3.size = 12; ld3.color = (0.55, 0.62, 1.0)
    lo3 = bpy.data.objects.new("fillB", ld3); bpy.context.collection.objects.link(lo3)
    lo3.location = (cx, cy - 12, ct + 8); lo3.rotation_euler = (math.radians(65), 0, 0)
    # 板の下：コンクリの塊と、水まで下りる柱
    for b in BARS:
        if b["stage"] != "B": continue
        p0 = V(b["p"]); L, W = b["L"], b["W"]
        rock("shima%02d" % b["i"], p0 + V((0, 0, -0.40)), (L * 0.40, W * 0.70, 0.22), conc, b["yaw"], 0.10, 4, safe=True)
        for j in range(4):   # 塊の下から垂れる鉄筋（当たり判定の根の箱 ±0.15, z -0.5〜-1.0 の中）
            a2 = rnd.uniform(0, 2 * math.pi); r2 = rnd.uniform(0.03, 0.11)
            rebar("shima_tekkin%02d_%d" % (b["i"], j), (p0.x + r2 * math.cos(a2), p0.y + r2 * math.sin(a2), p0.z - 0.5), (p0.x + r2 * math.cos(a2) + rnd.uniform(-0.03, 0.03), p0.y + r2 * math.sin(a2) + rnd.uniform(-0.03, 0.03), p0.z - rnd.uniform(0.75, 0.98)), rust, 0.01)
    # 真ん中の崩れた塔（円筒・上が欠けて鉄筋）
    tc_ = SC["B"]["center"]; t_top = SC["B"]["tou_top"]; t_bot = ct - 3
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1.05, depth=t_top - t_bot, location=(tc_[0], tc_[1], (t_top + t_bot) / 2))
    tou = bpy.context.object; tou.name = "tou"
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=12); bpy.ops.object.mode_set(mode='OBJECT')
    tt = bpy.data.textures.new("tou_t", 'CLOUDS'); tt.noise_scale = 0.5; tt.noise_depth = 3
    dt_ = tou.modifiers.new("d", 'DISPLACE'); dt_.texture = tt; dt_.strength = -0.12; dt_.mid_level = 0.5; dt_.texture_coords = 'GLOBAL'
    bpy.ops.object.shade_smooth(); tou.data.materials.append(conc)
    for j in range(9):
        ph = 2 * math.pi * j / 9; rr = 0.95
        rebar("tou_tekkin%d" % j, (tc_[0] + rr * math.cos(ph), tc_[1] + rr * math.sin(ph), t_top - 0.2), (tc_[0] + (rr + rnd.uniform(-0.3, 0.3)) * math.cos(ph), tc_[1] + (rr + rnd.uniform(-0.3, 0.3)) * math.sin(ph), t_top + rnd.uniform(0.5, 1.3)), rust)
    for j in range(7):
        ph = 2 * math.pi * j / 7 + 0.3
        rock("tou_gareki%d" % j, (tc_[0] + 0.7 * math.cos(ph), tc_[1] + 0.7 * math.sin(ph), t_top + 0.1), (0.35, 0.25, 0.2), conc, ph, 0.2, 2)
    # まわりの沈んだ廃墟（壁・傾いた板・柱）：らせんの外（中心から 9m 以上）
    for k in range(34):
        ph = rnd.uniform(0, 2 * math.pi); rr = rnd.uniform(13.5, 48)
        x, y = cx + rr * math.cos(ph), cy + rr * math.sin(ph)
        kind = rnd.random()
        if kind < 0.45:   # 壁の残り
            h = rnd.uniform(1.5, 7); cube("kabeB%02d" % k, (x, y, WZ - 0.6 + h / 2), (rnd.uniform(3, 9), 0.5, h), conc, rnd.uniform(0, math.pi), 0.05)
        elif kind < 0.75:  # 傾いた板
            cube("itaB%02d" % k, (x, y, WZ + rnd.uniform(-0.4, 0.5)), (rnd.uniform(3, 7), rnd.uniform(2, 4), 0.35), conc, 0.0, 0.04, rot=(rnd.uniform(0.2, 0.6) * rnd.choice((-1, 1)), rnd.uniform(-0.3, 0.3), rnd.uniform(0, math.pi)))
        else:              # 柱
            h = rnd.uniform(2, 9); cube("hashiraB%02d" % k, (x, y, WZ - 0.6 + h / 2), (0.7, 0.7, h), conc, rnd.uniform(0, 3), 0.03)
            for j in range(3):
                rebar("hashiraB_tekkin%02d_%d" % (k, j), (x + rnd.uniform(-0.2, 0.2), y + rnd.uniform(-0.2, 0.2), WZ - 0.6 + h - 0.1), (x + rnd.uniform(-0.5, 0.5), y + rnd.uniform(-0.5, 0.5), WZ - 0.6 + h + rnd.uniform(0.4, 1.2)), rust)
    # 遠くの崩れた街（シルエット・ところどころ灯りが残る）
    lampm = mat_drop("mado_akari", (1.0, 0.75, 0.45), 9.0, 1.0)
    for k in range(70):
        ph = rnd.uniform(math.radians(-10), math.radians(190)); rr = rnd.uniform(110, 330)
        x, y = PE.x + rr * math.cos(ph), PE.y + rr * math.sin(ph)
        w_, d_, h_ = rnd.uniform(10, 30), rnd.uniform(10, 30), rnd.uniform(10, 85)
        kuzure = rnd.random() < 0.3
        if kuzure: h_ *= 0.6
        yw = rnd.uniform(0, 3); cube("machi%02d" % k, (x, y, WZ - 2 + h_ / 2), (w_, d_, h_), concF, yw, 0.0)
        if rnd.random() < 0.5: cube("machi_ue%02d" % k, (x + rnd.uniform(-w_ / 4, w_ / 4), y + rnd.uniform(-d_ / 4, d_ / 4), WZ - 2 + h_ + 2.5), (w_ * 0.35, d_ * 0.35, 5), concF, yw, 0.0)
        if kuzure:   # 上が崩れている
            rock("machi_kuzure%02d" % k, (x, y, WZ - 2 + h_), (w_ * 0.6, d_ * 0.6, h_ * 0.3), concF, 0.0, 0.5, 2)
        for j in range(rnd.randint(0, 3)):
            cube("akari%02d_%d" % (k, j), (x + rnd.uniform(-w_ / 2, w_ / 2), y - d_ / 2 - 0.1, WZ - 2 + rnd.uniform(3, h_ * 0.55)), (1.2, 0.1, 0.8), lampm, 0.0, 0.0)
    # 夜の空気の粒
    mote = mat_drop("yoru_tsubu", (0.8, 0.8, 1.0), 2.0, 0.6)
    spray("yoru_tsubu", (cx, cy, ct + 3), (24, 30), 300, (-0.1, -0.1, -0.02), (0.1, 0.1, 0.12), 7.0, 0.012, mote, 7, 0.0, False)
    return [lo, lo2, lo3]

# 空：舞台Aは割れた天井から見える曇り空（明るい）、舞台Bは夜の藍＋星。入れ替えはキーで
stage("world")
w = sc.world or bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree
bg = wn.nodes.get("Background")
tcw = node(wn, "ShaderNodeTexCoord"); sepw = node(wn, "ShaderNodeSeparateXYZ"); link(wn, tcw.outputs["Generated"], sepw.inputs[0])
zmap = node(wn, "ShaderNodeMath"); zmap.operation = 'MULTIPLY_ADD'; zmap.inputs[1].default_value = 0.5; zmap.inputs[2].default_value = 0.5
link(wn, sepw.outputs["Z"], zmap.inputs[0])
rampA = node(wn, "ShaderNodeValToRGB")
rampA.color_ramp.elements[0].position = 0.40; rampA.color_ramp.elements[0].color = (0.035, 0.038, 0.042, 1)
rampA.color_ramp.elements[1].position = 0.85; rampA.color_ramp.elements[1].color = (0.75, 0.74, 0.70, 1)
link(wn, zmap.outputs[0], I(rampA, "Fac"))
vor = node(wn, "ShaderNodeTexVoronoi"); I(vor, "Scale").default_value = 220
stp = math_(wn, 'LESS_THAN', O(vor, "Distance"), vb=0.05)
link(wn, tcw.outputs["Generated"], I(vor, "Vector"))
vor2 = node(wn, "ShaderNodeTexVoronoi"); I(vor2, "Scale").default_value = 70; link(wn, tcw.outputs["Generated"], I(vor2, "Vector"))
stp2 = math_(wn, 'LESS_THAN', O(vor2, "Distance"), vb=0.035)
stars = math_(wn, 'ADD', math_(wn, 'MULTIPLY', stp, vb=2.5), math_(wn, 'MULTIPLY', stp2, vb=6.0))
rampB = node(wn, "ShaderNodeValToRGB")
rampB.color_ramp.elements[0].position = 0.45; rampB.color_ramp.elements[0].color = (0.045, 0.040, 0.10, 1)
rampB.color_ramp.elements[1].position = 0.9; rampB.color_ramp.elements[1].color = (0.004, 0.005, 0.022, 1)
link(wn, zmap.outputs[0], I(rampB, "Fac"))
addst = node(wn, "ShaderNodeMixRGB"); addst.blend_type = 'ADD'; addst.inputs[0].default_value = 1.0
link(wn, rampB.outputs["Color"], addst.inputs[1]); link(wn, stars, addst.inputs[2])
mixw = node(wn, "ShaderNodeMixRGB"); link(wn, rampA.outputs["Color"], mixw.inputs[1]); link(wn, addst.outputs["Color"], mixw.inputs[2])
link(wn, mixw.outputs["Color"], I(bg, "Color")); I(bg, "Strength").default_value = 1.0
for ff, vv in ((SWITCH - 1, 0.0), (SWITCH, 1.0)):
    mixw.inputs[0].default_value = vv; mixw.inputs[0].keyframe_insert("default_value", frame=ff)

stage("butai")
known = set(bpy.data.objects.keys())
lightsA = build_haikyo_hall()
objsA = set(bpy.data.objects.keys()) - known; known |= objsA
stage("butaiA")
lightsB = build_haikyo_yoru()
objsB = set(bpy.data.objects.keys()) - known
stage("butaiB")
for n in objsA: hide_between(bpy.data.objects[n], 1, SWITCH - 1)
for n in objsB: hide_between(bpy.data.objects[n], SWITCH, NF + 5)
# 板・横木・波紋・粒も、見えない方の舞台では消す（光が混ざらないように）
for i, b in enumerate(BARS):
    o, rails, m = BAR_OBJS[i]
    for ob in [o] + rails + [bpy.data.objects[b["ring"]]]:
        if b["stage"] == "A": hide_between(ob, 1, SWITCH - 1)
        else: hide_between(ob, SWITCH, NF + 5)
kg = bpy.data.objects.get("kumo_kuguru")      # くぐる雲は、くぐり終えたら消す
if kg:
    fB = BARS[M["split"] + 1]["fr"]
    kg.hide_render = True; kg.keyframe_insert("hide_render", frame=fB - 6)
    kg.hide_viewport = True; kg.keyframe_insert("hide_viewport", frame=fB - 6)

# =====================================================================
# 間接光（v3.1）：舞台Aの吹き抜けに EEVEE の Irradiance Volume を置いて焼く（跳ね返りの光＝のっぺり対策。失敗しても描画は続ける）
# =====================================================================
stage("bake")
if os.environ.get("UU_BAKE", "1") == "1" and not LITE:
    try:
        A_ = SC["A"]; cenA = A_["center"]; RWA = A_["R_wall"]; ztA = A_["ztop"] + 8.6; pzA = A_["pool_z"]
        bpy.ops.object.lightprobe_add(type='GRID', location=(cenA[0], cenA[1], (ztA + pzA) / 2))
        pr = bpy.context.object; pr.name = "irrA"; pr.scale = (RWA + 3.0, RWA + 3.0, (ztA - pzA) / 2 + 1.0)
        tryset(pr.data, grid_resolution_x=8, grid_resolution_y=8, grid_resolution_z=12, intensity=1.0, clip_start=0.2, clip_end=80.0, falloff=0.3)
        tryset(EV, gi_diffuse_bounces=2, gi_cubemap_resolution='256', gi_visibility_resolution='16', gi_irradiance_smoothing=0.25, gi_auto_bake=False)
        sc.frame_set(1); tb = time.time()
        bpy.ops.scene.light_cache_bake()
        print("BAKE ok", round(time.time() - tb, 1), flush=True)
    except Exception as ex:
        print("BAKE fail", ex, flush=True)

# =====================================================================
# カメラ（michi.json の位置・見る先・傾き・レンズ）
# =====================================================================
stage("camera")
cam_d = bpy.data.cameras.new("C"); cam_d.clip_start = 0.04; cam_d.clip_end = 1500; cam_d.sensor_fit = 'AUTO'
cam = bpy.data.objects.new("Cam", cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.rotation_mode = 'QUATERNION'
prevq = None
for f, fr in enumerate(FRM, start=1):
    c = V(fr["cam"]); l = V(fr["look"])
    fwd = (l - c).normalized()
    q = fwd.to_track_quat('-Z', 'Y')
    q = q @ Quaternion((0, 0, 1), fr["roll"])
    if prevq is not None and prevq.dot(q) < 0: q.negate()
    prevq = q
    cam.location = c; cam.keyframe_insert("location", frame=f)
    cam.rotation_quaternion = q; cam.keyframe_insert("rotation_quaternion", frame=f)
    cam_d.lens = fr["lens"]; cam_d.keyframe_insert("lens", frame=f)
anim_lin(cam); anim_lin(cam_d)
# 霧の白（カメラの前の板）：舞台の入れ替えを 0.5 秒で隠す
mf, ntf, pf = newmat("shiro"); blend(mf)
pin(pf, "Base Color", (1, 1, 1, 1)); pin(pf, "Emission Color", (0.93, 0.96, 1.0, 1)); pin(pf, "Emission Strength", 1.5)
bpy.ops.mesh.primitive_plane_add(size=1); card = bpy.context.object; card.data.materials.append(mf)
card.parent = cam; card.location = (0, 0, -0.06); card.scale = (0.5, 0.5, 1)
al = I(pf, "Alpha")
for ff, vv in ((1, 0.0), (SWITCH - 7, 0.0), (SWITCH - 1, 1.0), (SWITCH, 1.0), (SWITCH + 6, 0.0), (NF, 0.0)):
    al.default_value = vv; al.keyframe_insert("default_value", frame=ff)

if os.environ.get("UU_SAVE"): bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "_scene.blend"))
stage("ready")
os.makedirs(OUT, exist_ok=True)
if FR == "none": print("DONE build-only", flush=True); sys.exit(0)

def kensa():
    """Blender の中で、本物の形どうしで当たりを確かめる（うんこの変形後のメッシュ × 板・横木・紐・岩・塔）。
    1コマを4つに割って、三角形どうしが交わる組があるかを BVH で調べる。着地して板の上にいる間の、その板だけは「接している」ので除く。"""
    import bmesh
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    names = [o.name for o in bpy.data.objects if o.type == 'MESH' and (o.name.startswith(("bar", "ledge", "shima", "tou")) or o.name.startswith("Cube") or o.name.startswith("Cylinder") or o.name.startswith("Cone"))]
    names = [n for n in names if n != "unko"]
    def bvh_of(o):
        ev = o.evaluated_get(dg); me_ = ev.to_mesh(); bm = bmesh.new(); bm.from_mesh(me_); bm.transform(ev.matrix_world)
        t = BVHTree.FromBMesh(bm); c = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts)); r = max(((v.co - c).length for v in bm.verts), default=0)
        bm.free(); ev.to_mesh_clear(); return t, c, r
    own = {}
    for b in BARS: own[b["i"]] = {"bar%02d" % b["i"]}
    bad = []; n_check = 0; t0 = time.time()
    for f in range(1, NF + 1):
        for sub in (0.0, 0.25, 0.5, 0.75):
            sc.frame_set(f, subframe=sub); dg = bpy.context.evaluated_depsgraph_get()
            fr = FRM[f - 1]; vis = [n for n in names if not bpy.data.objects[n].hide_render]
            tu, cu, ru = bvh_of(unko)
            for n in vis:
                o = bpy.data.objects[n]
                if (o.matrix_world.translation - cu).length > ru + 6: continue
                to, co, ro = bvh_of(o)
                if (co - cu).length > ru + ro: continue
                n_check += 1
                if n.startswith("bar") and int(n[3:5]) in (fr.get("bi"), (fr.get("bi") or 0) + 1) and n == ("bar%02d" % int(n[3:5])):
                    # 乗っている板・次に乗る板：三角が触れているだけ（＝着地）は当たり前。板の上面より下に沈んでいたら、めり込み
                    # 板の上面と向き・大きさは michi.json（置いた位置の正本）から
                    bb = BARS[int(n[3:5])]; top = bb["p"][2] + bb["dz"].get(str(f), bb["dz"].get(str(f + 1), 0.0) if False else 0.0)
                    ks = sorted(int(k) for k in bb["dz"])
                    if ks and ks[0] <= f <= ks[-1]:
                        a0 = bb["dz"].get(str(f), 0.0); a1 = bb["dz"].get(str(f + 1), a0); top = bb["p"][2] + a0 + (a1 - a0) * sub
                    cy_, sy_ = math.cos(bb["yaw"]), math.sin(bb["yaw"]); hx = bb["L"] / 2; hy = bb["W"] / 2
                    ev = unko.evaluated_get(dg); me_ = ev.to_mesh(); mw = ev.matrix_world
                    pen = -9.0
                    for v in me_.vertices:
                        w = mw @ v.co; dx, dy = w.x - bb["p"][0], w.y - bb["p"][1]
                        lx, ly = dx * cy_ + dy * sy_, -dx * sy_ + dy * cy_
                        if abs(lx) < hx - 0.03 and abs(ly) < hy - 0.03 and w.z > top - 0.3: pen = max(pen, top - w.z)
                    ev.to_mesh_clear()
                    if pen > 0.005: bad.append({"f": f, "sub": sub, "obj": n, "st": fr["st"], "shizumi_m": round(pen, 4)})
                    continue
                if tu.overlap(to):
                    bad.append({"f": f, "sub": sub, "obj": n, "st": fr["st"]})
        if f % 100 == 0: print("KENSA", f, len(bad), round(time.time() - t0), flush=True)
    res = {"koma": NF, "kizami": 4, "shirabeta_kumi": n_check, "meri_komi": len(bad), "rei": bad[:30]}
    json.dump(res, open(os.path.join(OUT, "kensa.json"), "w"), ensure_ascii=False, indent=1)
    print("KENSA_DONE", json.dumps({k: v for k, v in res.items() if k != "rei"}), flush=True)

STEP = int(os.environ.get("UU_STEP", "1"))
if FR == "all": frames = range(1, NF + 1, STEP)
elif "-" in FR and "," not in FR: a_, b_ = FR.split("-"); frames = range(int(a_), int(b_) + 1, STEP)
else:
    items = FR.split(",")
    if "kensa" in items:
        os.makedirs(OUT, exist_ok=True); kensa(); items = [x for x in items if x != "kensa"]
        open(os.path.join(OUT, "f0000.jpg"), "w").close()
    frames = [int(x) for x in items if x]
for f in frames:
    path = os.path.join(OUT, "f%04d.jpg" % f)
    if os.path.exists(path): continue
    t0 = time.time(); sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print("FRAME", f, round(time.time() - t0, 1), flush=True)
print("DONE", NF, flush=True)
