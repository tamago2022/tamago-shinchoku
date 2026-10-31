# 宇宙うんこ v3（Blender 3.6 LTS の EEVEE）
# 動き・カメラは michi.json（michi_v3.py が計算して、すり抜けゼロを確かめたもの）をそのまま使う。ここでは形と質感と光だけを作る。
# 使い方: Blender -b -P scene_v3.py -- <このフォルダ> <出力フォルダ> <all | 1-100 | 5,60 | none>
# 環境変数: UU_PCT=100  UU_SAMPLES=16  UU_MB=1(動きのぶれ)  UU_SAVE=1(.blendも保存)  UU_LITE=1(体積の霧を軽く)
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
for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = e; break
    except Exception: pass
print("ENGINE", sc.render.engine, bpy.app.version_string, flush=True)
EV = sc.eevee
tryset(EV, taa_render_samples=int(os.environ.get("UU_SAMPLES", "16")), use_bloom=True, bloom_intensity=0.045,
       bloom_threshold=0.85, bloom_radius=6.5, bloom_knee=0.6, use_gtao=True, gtao_distance=0.5, gtao_factor=1.1,
       use_ssr=True, use_ssr_refraction=True, use_ssr_halfres=True, ssr_quality=0.5, ssr_thickness=0.1,
       use_soft_shadows=True, use_volumetric_shadows=True, use_volumetric_lights=True,
       volumetric_tile_size='16' if not LITE else '16', volumetric_samples=40 if not LITE else 24,
       volumetric_start=0.3, volumetric_end=90.0, volumetric_light_clamp=6.0,
       use_motion_blur=os.environ.get("UU_MB", "1") == "1", motion_blur_shutter=0.42, motion_blur_steps=1,
       shadow_cube_size='1024', shadow_cascade_size='2048', use_shadow_high_bitdepth=True, sss_samples=5)
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.resolution_percentage = int(os.environ.get("UU_PCT", "100"))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = NF
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 93
try: sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
except Exception: pass
sc.view_settings.exposure = 0.15

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
# 宇宙うんこ（ちよさんの宇宙うんこの形：太い3段＋右へ巻く先っぽ。肌は、ただのわえさんの宇宙画）
# =====================================================================
stage("unko")
parts = []
for c, r in (((0, 0, 0.215), (0.56, 0.54, 0.235)), ((0.0, 0, 0.495), (0.43, 0.42, 0.19)), ((0.01, 0, 0.735), (0.30, 0.30, 0.16))):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1, location=c); o = bpy.context.object; o.scale = r; parts.append(o)
for c, r in (((0.03, 0, 0.85), 0.155), ((0.085, 0, 0.94), 0.11), ((0.15, 0, 1.005), 0.078), ((0.21, 0, 1.05), 0.05), ((0.255, 0, 1.075), 0.03)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=c); parts.append(bpy.context.object)
bpy.ops.object.select_all(action='DESELECT')
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]; bpy.ops.object.join(); unko = bpy.context.object; unko.name = "unko"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for v in unko.data.vertices:          # 底を平らに（板の上にぺたっと座る）
    if v.co.z < 0.05: v.co.z = 0.05
rm = unko.modifiers.new("r", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.011
bpy.ops.object.modifier_apply(modifier="r")
sm = unko.modifiers.new("s", 'SMOOTH'); sm.iterations = 6; sm.factor = 0.6
bpy.ops.object.modifier_apply(modifier="s")
zmin = min(v.co.z for v in unko.data.vertices)
for v in unko.data.vertices: v.co.z -= zmin
hgt = max(v.co.z for v in unko.data.vertices)
S0 = H_UNKO / hgt
for v in unko.data.vertices: v.co *= S0
bpy.ops.object.shade_smooth()
# 段の境目（くびれ）を、半径の一番細いところで決める
bins = {}
for v in unko.data.vertices:
    k = int(v.co.z / H_UNKO * 100); r = math.hypot(v.co.x, v.co.y); bins[k] = max(bins.get(k, 0), r)
def kubire(a, b):
    ks = [k for k in range(a, b) if k in bins]; return min(ks, key=lambda k: bins[k]) / 100 * H_UNKO
Z1 = kubire(int(0.30 / 1.08 * 100), int(0.46 / 1.08 * 100)); Z2 = kubire(int(0.55 / 1.08 * 100), int(0.72 / 1.08 * 100))
print("kubire", round(Z1, 3), round(Z2, 3), flush=True)
DAN = [(0.0, Z1), (Z1, Z2), (Z2, H_UNKO)]
me = unko.data
for poly in me.polygons:
    z = poly.center.z; poly.material_index = 0 if z < Z1 else (1 if z < Z2 else 2)
uvl = me.uv_layers.new(name="UV")
for poly in me.polygons:
    lo, hi = DAN[poly.material_index]
    us = []
    for li in poly.loop_indices:
        co = me.vertices[me.loops[li].vertex_index].co
        us.append(math.atan2(co.y, co.x) / (2 * math.pi) + 0.5)
    if max(us) - min(us) > 0.5: us = [u + 1 if u < 0.5 else u for u in us]
    for li, u in zip(poly.loop_indices, us):
        co = me.vertices[me.loops[li].vertex_index].co
        uvl.data[li].uv = (u, max(0.02, min(0.98, (co.z - lo) / (hi - lo))))
# グミの質感：宇宙画が中に透けて見える、つやつやで、ぷるんとした塊
def gummy(name, img):
    m, nt, p = newmat(name)
    tex = node(nt, "ShaderNodeTexImage"); tex.image = load_img(img); tex.extension = 'REPEAT'
    uvn = node(nt, "ShaderNodeUVMap"); uvn.uv_map = "UV"; link(nt, uvn.outputs[0], I(tex, "Vector"))
    hsv = node(nt, "ShaderNodeHueSaturation"); I(hsv, "Saturation").default_value = 1.12; I(hsv, "Value").default_value = 1.25
    link(nt, tex.outputs["Color"], I(hsv, "Color"))
    # ふちが明るく透ける（グミの縁）
    lw = node(nt, "ShaderNodeLayerWeight"); I(lw, "Blend").default_value = 0.35
    bright = node(nt, "ShaderNodeMixRGB"); bright.blend_type = 'SCREEN'; link(nt, lw.outputs["Facing"], bright.inputs[0])
    link(nt, hsv.outputs[0], bright.inputs[1]); bright.inputs[2].default_value = (0.95, 0.78, 1.0, 1)
    link(nt, bright.outputs[0], I(p, "Base Color"))
    try: link(nt, hsv.outputs[0], I(p, "Subsurface Color"))
    except Exception: pass
    pin(p, "Subsurface Weight", 0.12); pin(p, "Subsurface Radius", (1.0, 0.6, 0.85))
    pin(p, "Roughness", 0.13); pin(p, "Coat Weight", 1.0); pin(p, "Coat Roughness", 0.03); pin(p, "Specular IOR Level", 0.7)
    pin(p, "Transmission Weight", 0.07); pin(p, "IOR", 1.42)
    # 中の小さな星（ちらちら光る）
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
for k in range(3):
    m, p = gummy("unko_dan%d" % k, "hada_dan%d.jpg" % k); me.materials.append(m); UNKO_MATS.append(p)
# ぷるぷるの形（シェイプキー）：つぶれ・のび・揺れ（上ほど大きく動く）
unko.shape_key_add(name="Basis")
def key(name, fn):
    kb = unko.shape_key_add(name=name, from_mix=False); kb.slider_min = -1.0; kb.slider_max = 1.5
    for i, v in enumerate(me.vertices): kb.data[i].co = fn(v.co.copy())
    return kb
def tsubure(c):
    h = c.z / H_UNKO; bul = 1 + 0.10 * math.sin(math.pi * min(1, h * 1.6))
    k = 1.27 * bul; return V((c.x * k, c.y * k, c.z * 0.62))
def nobi(c): return V((c.x * 0.9, c.y * 0.9, c.z * 1.22))
def yure(axis):
    def f(c):
        h = c.z / H_UNKO; d = 0.42 * H_UNKO * h * h
        return V((c.x + d, c.y, c.z)) if axis == 0 else V((c.x, c.y + d, c.z))
    return f
KB = {"tsubure": key("tsubure", tsubure), "nobi": key("nobi", nobi), "yureX": key("yureX", yure(0)), "yureY": key("yureY", yure(1))}
unko.location = (0, 0, 0)

# 動き（michi.json のまま）
for f, fr in enumerate(FRM, start=1):
    unko.location = fr["u"]; unko.keyframe_insert("location", frame=f)
    unko.rotation_euler = fr["rot"]; unko.keyframe_insert("rotation_euler", frame=f)
    s = fr["sq"]; yaw = fr["rot"][2]
    KB["tsubure"].value = max(0.0, s) / 0.38; KB["nobi"].value = max(0.0, -s) / 0.22
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
def bar_mat(i, b):
    m, nt, p = newmat("barM%02d" % i)
    col = SHU if b["bass"] else keycol(b["key"])
    base = (0.78, 0.26, 0.13) if b["bass"] else col
    if b["final"]: base = (0.85, 0.30, 0.15)
    pin(p, "Base Color", base + (1,)); pin(p, "Metallic", 1.0)
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
    bv = o.modifiers.new("b", 'BEVEL'); bv.width = 0.028; bv.segments = 5; bv.limit_method = 'NONE'
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
    # 叩かれて光る・沈む（沈む量はうんこと同じ＝すき間0）
    e = I(p, "Emission Strength"); fh = b["fr"]
    peak = 9.0 if (b["bass"] or b["final"]) else 3.2
    hits_ = [fh] + ([POYON] if b["final"] else [])
    for fh_ in hits_:
        for ff, vv in ((fh_ - 1, 0.0), (fh_, peak), (fh_ + 3, peak * 0.45), (fh_ + 16, peak * 0.06), (fh_ + 34, 0.0)):
            e.default_value = vv; e.keyframe_insert("default_value", frame=ff)
    z0 = o.location.z
    for fs, dz in b["dz"].items():
        f_ = int(fs); o.location.z = z0 + dz; o.keyframe_insert("location", index=2, frame=f_)
        for r in rails: r.location.z = (p0.z - T - 0.035) + dz; r.keyframe_insert("location", index=2, frame=f_)
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
# 舞台A：森の滝（段々の岩に置かれた鉄琴を、滝の前で下っていく）
# =====================================================================
def build_mori_no_taki():
    A = SC["A"]; cx = A["cx"]; zt, zb = A["ztop"], A["zbot"]; ymax = A["ymax"]; ymin = A["ymin"]
    wl, wr = A["wall_x"]; cy_ = A["curtain_y"]; pz = A["pool_z"]
    rockA = mat_rock("rockA", moss=0.75, wet=0.7); rockW = mat_rock("rockW", moss=0.25, wet=1.0, dark=0.8)
    # 滝（奥の大きな滝・その奥のうすい層・右の細い滝）
    wA = mat_water("waterA", (0.88, 0.96, 1.0), 4.5, 1.15, 0.75)
    curtain("takiA_main", wl - 0.5, wr + 0.5, cy_, zt + 3, pz - 0.5, wA, 1.2)
    wA2 = mat_water("waterA2", (0.70, 0.86, 0.92), 3.0, 0.6, 0.45)
    curtain("takiA_back", wl - 2.5, wr + 2.5, cy_ + 0.8, zt + 3, pz - 0.5, wA2, 0.8)
    curtain("takiA_side", wr + 0.6, wr + 1.6, cy_ - 1.2, zt - 1, pz - 0.5, wA, 0.15, 10, 0.3)
    # 滝の上の縁（白く盛り上がって落ち始める水）
    lip = mat_water("lipA", (1.0, 1.0, 1.0), 1.5, 1.3, 0.9)
    curtain("taki_fuchi", wl - 0.5, wr + 0.5, cy_ - 0.75, zt + 3.3, zt + 2.2, lip, 1.2, 48, 0.2)
    # 谷の壁（左右と手前）：すき間のない岩の壁。カメラの通り道から 0.8m 以上はなす（凹凸は ±0.6m）
    fy = A["front_y"]
    def wall(name, o, ua, va, su, sv, nrm, mat, nu=140, nv=170):
        verts = []; faces = []
        for j in range(nv + 1):
            for i in range(nu + 1):
                pnt = V(o) + V(ua) * (su * (i / nu - 0.5)) + V(va) * (sv * (j / nv - 0.5)); verts.append(tuple(pnt))
        for j in range(nv):
            for i in range(nu):
                a_ = j * (nu + 1) + i; faces.append((a_, a_ + 1, a_ + nu + 2, a_ + nu + 1))
        w_ = obj_from_mesh(name, verts, faces, mat)
        vg = w_.vertex_groups.new(name="all"); vg.add(list(range(len(verts))), 1.0, 'REPLACE')
        t1 = bpy.data.textures.new(name + "1", 'CLOUDS'); t1.noise_scale = 2.2; t1.noise_depth = 4
        d1 = w_.modifiers.new("d1", 'DISPLACE'); d1.texture = t1; d1.strength = 1.1; d1.mid_level = 0.5; d1.texture_coords = 'GLOBAL'; d1.direction = 'CUSTOM_NORMAL' if False else 'NORMAL'
        t2 = bpy.data.textures.new(name + "2", 'VORONOI'); t2.noise_scale = 0.9
        d2 = w_.modifiers.new("d2", 'DISPLACE'); d2.texture = t2; d2.strength = 0.25; d2.mid_level = 0.5; d2.texture_coords = 'GLOBAL'
        bpy.context.view_layer.objects.active = w_; w_.select_set(True); bpy.ops.object.shade_smooth()
        # 面の向き（谷の内側を向く）
        if (V(ua).cross(V(va))).dot(V(nrm)) < 0:
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.flip_normals(); bpy.ops.object.mode_set(mode='OBJECT')
        return w_
    zc, zh = (zt + 8 + pz - 2) / 2, (zt + 8) - (pz - 2)
    yc, yl = (fy + cy_ + 4) / 2, (cy_ + 4) - fy
    wall("kabe_L", (wl - 0.7, yc, zc), (0, 1, 0), (0, 0, 1), yl, zh, (1, 0, 0), rockA)
    wall("kabe_R", (wr + 0.7, yc, zc), (0, 1, 0), (0, 0, 1), yl, zh, (-1, 0, 0), rockA)
    wall("kabe_mae", ((wl + wr) / 2, fy - 0.7, zc), (1, 0, 0), (0, 0, 1), wr - wl + 4, zh, (0, 1, 0), rockA, 60, 170)
    box("cliff_back", (cx, cy_ + 3.5, (zt + pz) / 2), (30, 1.5, zt - pz + 14), rockW)
    # 上の縁から張り出す岩（空との境目の形）
    for k in range(18):
        sgn = rnd.choice((-1, 1)); xw = wl - 1.6 if sgn < 0 else wr + 1.6
        rock("fuchi%02d" % k, (xw, rnd.uniform(fy, cy_ + 1), zt + 8 + rnd.uniform(-1, 1)), (rnd.uniform(1.5, 2.6), rnd.uniform(1.5, 2.5), rnd.uniform(1.0, 1.8)), rockA, rnd.uniform(0, 6.28), 0.45, 4)
    # 左右と手前の壁を流れ落ちる細い滝（どちらを向いても滝が見える）
    wS = mat_water("waterS", (0.86, 0.95, 1.0), 4.0, 0.9, 0.7)
    for k, (xx, yy, wd) in enumerate(((wl - 0.15, ymin + 2.0, 2.2), (wl - 0.15, ymin + 11.0, 1.4), (wr + 0.15, ymin + 5.5, 2.6), (wr + 0.15, ymin + 14.0, 1.6))):
        verts = []; faces = []; NZ = 40; NS = 12
        for j in range(NZ + 1):
            z = zt + 7.5 + (pz - zt - 7.5) * j / NZ
            for i in range(NS + 1):
                u = i / NS; verts.append((xx + (0.25 if xx < cx else -0.25) * (1 - j / NZ) ** 8, yy + (u - 0.5) * wd, z))
        for j in range(NZ):
            for i in range(NS):
                a_ = j * (NS + 1) + i; faces.append((a_, a_ + 1, a_ + NS + 2, a_ + NS + 1))
        obj_from_mesh("taki_yoko%d" % k, verts, faces, wS)
    for k, (xx, wd) in enumerate((((wl + wr) / 2 - 2.2, 1.8), ((wl + wr) / 2 + 2.6, 2.4))):
        curtain("taki_mae%d" % k, xx - wd / 2, xx + wd / 2, fy - 0.15, zt + 7.5, pz - 0.5, wS, -0.05, 10, -0.25)
    # 滝つぼ（水面・泡・しぶき・霧）
    mw, ntw_, pw_ = newmat("pool"); pin(pw_, "Base Color", (0.015, 0.06, 0.055, 1)); pin(pw_, "Roughness", 0.04)
    tcw = node(ntw_, "ShaderNodeTexCoord"); mpw = node(ntw_, "ShaderNodeMapping"); link(ntw_, tcw.outputs["Object"], I(mpw, "Vector"))
    lw_ = I(mpw, "Location"); lw_.default_value = (0, 0, 0); lw_.keyframe_insert("default_value", frame=1); lw_.default_value = (0, -6, 2); lw_.keyframe_insert("default_value", frame=NF)
    nzw_ = node(ntw_, "ShaderNodeTexNoise"); I(nzw_, "Scale").default_value = 3.5; link(ntw_, mpw.outputs[0], I(nzw_, "Vector"))
    bmw = node(ntw_, "ShaderNodeBump"); I(bmw, "Strength").default_value = 0.25; link(ntw_, O(nzw_, "Fac"), I(bmw, "Height")); link(ntw_, bmw.outputs[0], I(pw_, "Normal"))
    anim_lin(ntw_)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(cx, cy_ - 10, pz)); bpy.context.object.data.materials.append(mw)
    foam = mat_water("awa", (1.0, 1.0, 1.0), 0.6, 1.0, 0.85)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy_ - 1.6, pz + 0.03)); fo = bpy.context.object; fo.scale = (wr - wl + 2, 3.2, 1)
    fo.data.materials.append(foam)
    drop = mat_drop("shibuki")
    spray("shibuki_a", (cx, cy_ - 0.7, pz + 0.05), (wr - wl + 1, 0.8), 900, (-0.6, -2.6, 2.0), (0.6, -0.6, 5.2), 1.1, 0.028, drop, 1)
    spray("shibuki_b", (cx, cy_ - 1.2, pz + 0.05), (wr - wl + 1, 1.2), 500, (-1.0, -3.2, 1.0), (1.0, -1.2, 3.0), 0.9, 0.05, drop, 2)
    # 板の岩に流れ落ちる水が当たる細かな粒（滝の前の空中を漂う）
    mote = mat_drop("kiri_tsubu", (1.0, 0.95, 0.85), 1.4, 0.55)
    spray("tadayou", (cx, (ymin + cy_) / 2, (zt + pz) / 2), (wr - wl + 2, cy_ - ymin + 3), 260, (-0.15, -0.1, -0.05), (0.15, 0.1, 0.15), 6.0, 0.012, mote, 3, 0.0, False)
    box("kiri_soko", (cx, cy_ - 2.5, pz + 1.6), (wr - wl + 8, 9, 4.0), mat_volume("kiriA_soko", 1.2, (0.92, 0.96, 0.97), 0.3, (0.9, (0.6, 0, 0.9), 0.0, 1.0)))
    box("kiri_zentai", (cx, (ymin + cy_) / 2, (zt + pz) / 2), (wr - wl + 14, cy_ - ymin + 16, zt - pz + 12),
        mat_volume("kiriA", 0.022, (0.85, 0.95, 0.88), 0.65))
    # 光：上の奥から差し込む金色の光（霧に光の筋）、手前から青みの柔らかい光
    ld = bpy.data.lights.new("sunA", 'SUN'); ld.energy = 5.0; ld.color = (1.0, 0.86, 0.62); ld.angle = math.radians(2.5)
    lo = bpy.data.objects.new("sunA", ld); bpy.context.collection.objects.link(lo)
    lo.rotation_euler = (math.radians(-38), math.radians(22), math.radians(165))
    ld2 = bpy.data.lights.new("fillA", 'AREA'); ld2.energy = 260; ld2.size = 8; ld2.color = (0.70, 0.86, 1.0)
    lo2 = bpy.data.objects.new("fillA", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cx - 2, ymin - 9, (zt + pz) / 2 + 4); lo2.rotation_euler = (math.radians(70), 0, math.radians(-8))
    ld3 = bpy.data.lights.new("takiA_glow", 'AREA'); ld3.energy = 400; ld3.size = 10; ld3.color = (0.85, 0.95, 1.0)
    lo3 = bpy.data.objects.new("takiA_glow", ld3); bpy.context.collection.objects.link(lo3)
    lo3.location = (cx, cy_ - 1.0, (zt + pz) / 2); lo3.rotation_euler = (math.radians(90), 0, math.radians(180))
    # 植物：崖のシダ・垂れる葉・水辺の大きな葉（道の中には置かない）
    for k in range(80):
        sgn = rnd.choice((-1, 1)); xw = wl if sgn < 0 else wr
        base = (xw + sgn * rnd.uniform(0.15, 0.45), rnd.uniform(A["front_y"] + 0.5, cy_ - 0.3), rnd.uniform(pz + 0.5, zt + 6))
        leaf_cards("shida%02d" % k, base, rnd.randint(4, 7), rnd.choice(("shida_a.png", "shida_b.png")), rnd.uniform(0.6, 1.2),
                   (-sgn, rnd.uniform(-0.3, 0.3), 0), rnd.choice((0.0, 0.0, 0.6, 1.2)), k)
    for k in range(14):
        sgn = rnd.choice((-1, 1)); xw = wl if sgn < 0 else wr
        base = (xw + sgn * rnd.uniform(0.0, 0.4), rnd.uniform(A["front_y"] + 1, cy_ - 2.5), pz + 0.05)
        leaf_cards("ha%02d" % k, base, rnd.randint(3, 5), "ha_ooki.png", rnd.uniform(0.9, 1.6), (-sgn, -0.4, 0), 0.0, 100 + k)
    for k in range(18):   # 上から垂れるつる（シダを下向きに）
        x = rnd.uniform(wl - 0.3, wr + 0.3); base = (x, cy_ - rnd.uniform(0.9, 2.0), zt + rnd.uniform(1.5, 3.5))
        if wl + 0.8 < x < wr - 0.8 and base[1] < A["ymax"] + 1.2: continue
        leaf_cards("tsuru%02d" % k, base, 3, "shida_b.png", rnd.uniform(1.2, 2.0), (0, -1, 0), 1.6, 200 + k)
    return [lo, lo2, lo3]

# =====================================================================
# 舞台B：雲の上の夜（月・オーロラ・星の滝・遠くの山の中腹にロゴの壁画）
# =====================================================================
def build_kumo_no_yoru():
    B = SC["B"]; ct = B["cloud_top"]; cx, cy = B["cx"], B["cy"]
    PE = V(M["pe"]); MOON = V(M["moon"]); MOUNT = V(M["mount"]); LOGO = V(M["logo"])
    # 雲海（もこもこの面：上の面が ct-0.2 を越えない）
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=360, y_subdivisions=360, size=260, location=(cx, cy + 60, ct - 2.4))
    cl = bpy.context.object
    tx = bpy.data.textures.new("kumo", 'CLOUDS'); tx.noise_scale = 9.0; tx.noise_depth = 3
    dm = cl.modifiers.new("d", 'DISPLACE'); dm.texture = tx; dm.strength = 1.6; dm.mid_level = 0.0; dm.texture_coords = 'GLOBAL'
    tx2 = bpy.data.textures.new("kumo2", 'CLOUDS'); tx2.noise_scale = 2.5; tx2.noise_depth = 2
    dm2 = cl.modifiers.new("d2", 'DISPLACE'); dm2.texture = tx2; dm2.strength = 0.6; dm2.mid_level = 0.0; dm2.texture_coords = 'GLOBAL'
    bpy.ops.object.shade_smooth()
    mc, ntc, pc = newmat("kumoM"); pin(pc, "Base Color", (0.42, 0.47, 0.70, 1)); pin(pc, "Roughness", 1.0)
    pin(pc, "Subsurface Weight", 0.5); pin(pc, "Subsurface Color", (0.55, 0.55, 0.95, 1)); pin(pc, "Subsurface Radius", (3, 3, 4))
    pin(pc, "Emission Color", (0.16, 0.15, 0.32, 1)); pin(pc, "Emission Strength", 0.3)
    cl.data.materials.append(mc)
    box("kiriB", (cx, cy + 60, ct - 0.6), (260, 260, 1.6), mat_volume("kiriB", 0.12, (0.62, 0.66, 0.95), 0.35, (0.08, (8, 3, 0), 0.0, 1.0)))
    # 落ちてくるときにくぐる雲（最初の板の少し上）
    P17 = V(BARS[M["split"] + 1]["p"])
    kg = box("kumo_kuguru", (P17.x, P17.y, P17.z + 4.2), (14, 14, 2.4), mat_volume("kuguru", 1.6, (0.88, 0.88, 1.0), 0.2, (0.6, (0, 0, -3), 0.2, 1.0)))
    # 月（大きく・やわらかく・表面にうすい模様）
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=17, location=MOON); mo = bpy.context.object
    mm, ntm, pm = newmat("tsuki")
    nzm = node(ntm, "ShaderNodeTexNoise"); I(nzm, "Scale").default_value = 2.2; I(nzm, "Detail").default_value = 6
    rm2 = node(ntm, "ShaderNodeValToRGB"); rm2.color_ramp.elements[0].color = (0.78, 0.74, 0.66, 1); rm2.color_ramp.elements[1].color = (1.0, 0.96, 0.86, 1)
    link(ntm, O(nzm, "Fac"), I(rm2, "Fac")); link(ntm, rm2.outputs[0], I(pm, "Base Color")); link(ntm, rm2.outputs[0], I(pm, "Emission Color"))
    pin(pm, "Emission Strength", 4.5); mo.data.materials.append(mm)
    # 月のまわりのにじみ
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=40, location=MOON); halo = bpy.context.object
    hm = bpy.data.materials.new("tsuki_kasa"); hm.use_nodes = True; hnt = hm.node_tree
    for n in list(hnt.nodes):
        if n.type != 'OUTPUT_MATERIAL': hnt.nodes.remove(n)
    hout = [n for n in hnt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    lwh = node(hnt, "ShaderNodeLayerWeight"); I(lwh, "Blend").default_value = 0.5
    pw2 = math_(hnt, 'POWER', O(lwh, "Facing"), vb=3.0); inv = math_(hnt, 'SUBTRACT', va=1.0, b=pw2)
    emh = node(hnt, "ShaderNodeEmission"); I(emh, "Color").default_value = (0.75, 0.72, 1.0, 1)
    link(hnt, math_(hnt, 'MULTIPLY', inv, vb=0.8), I(emh, "Strength"))
    trh = node(hnt, "ShaderNodeBsdfTransparent"); adh = node(hnt, "ShaderNodeAddShader")
    link(hnt, emh.outputs[0], adh.inputs[0]); link(hnt, trh.outputs[0], adh.inputs[1]); link(hnt, adh.outputs[0], I(hout, "Surface"))
    blend(hm); halo.data.materials.append(hm)
    ld = bpy.data.lights.new("moonB", 'SUN'); ld.energy = 2.4; ld.color = (0.74, 0.80, 1.0); ld.angle = math.radians(1.5)
    lo = bpy.data.objects.new("moonB", ld); bpy.context.collection.objects.link(lo)
    dirm = (MOON - PE).normalized(); lo.rotation_euler = (-dirm).to_track_quat('-Z', 'Y').to_euler()
    ld2 = bpy.data.lights.new("rimB", 'AREA'); ld2.energy = 380; ld2.size = 10; ld2.color = (0.85, 0.55, 1.0)
    lo2 = bpy.data.objects.new("rimB", ld2); bpy.context.collection.objects.link(lo2)
    lo2.location = (cx - 3, cy + 10, ct + 7); lo2.rotation_euler = (math.radians(-110), 0, 0)
    ld3 = bpy.data.lights.new("fillB", 'AREA'); ld3.energy = 160; ld3.size = 12; ld3.color = (0.55, 0.62, 1.0)
    lo3 = bpy.data.objects.new("fillB", ld3); bpy.context.collection.objects.link(lo3)
    lo3.location = (cx, cy - 12, ct + 8); lo3.rotation_euler = (math.radians(65), 0, 0)
    # 星の滝（空から雲海へ落ちる、すみれ色の光の滝）
    wB = mat_water("hoshinotaki", (0.78, 0.64, 1.0), 2.0, 3.2, 0.5)
    curtain("hoshi_taki", cx + 10, cx + 16, cy + 34, ct + 46, ct - 2, wB, 0.8, 20, 0.0)
    curtain("hoshi_taki2", cx - 22, cx - 17, cy + 44, ct + 52, ct - 2, wB, 0.6, 16, 0.0)
    # オーロラ（近く・明るく：下は緑、上はすみれ、縦の筋がゆっくり流れる）
    for k, (x0, x1, yy, z0, z1, bend, st_) in enumerate(((cx - 45, cx + 35, cy + 42, ct + 3, ct + 34, 16, 5.5), (cx - 15, cx + 55, cy + 58, ct + 8, ct + 44, 12, 4.5))):
        ma, nta, pa_ = newmat("aurora%d" % k); blend(ma)
        tc_ = node(nta, "ShaderNodeTexCoord"); sep = node(nta, "ShaderNodeSeparateXYZ"); link(nta, tc_.outputs["Generated"], sep.inputs[0])
        bump = node(nta, "ShaderNodeValToRGB"); el = bump.color_ramp.elements
        el[0].position = 0.0; el[0].color = (0, 0, 0, 1); el[1].position = 1.0; el[1].color = (0, 0, 0, 1)
        e2 = el.new(0.15); e2.color = (1, 1, 1, 1); e3 = el.new(0.5); e3.color = (0.45, 0.45, 0.45, 1)
        link(nta, sep.outputs["Z"], I(bump, "Fac"))
        mp_ = node(nta, "ShaderNodeMapping"); I(mp_, "Scale").default_value = (30, 1, 0.5)
        link(nta, tc_.outputs["Generated"], I(mp_, "Vector"))
        lo_ = I(mp_, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1)
        lo_.default_value = (2.4, 0, 0.3); lo_.keyframe_insert("default_value", frame=NF)
        nz = node(nta, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 1.0; I(nz, "Detail").default_value = 3
        link(nta, mp_.outputs[0], I(nz, "Vector")); anim_lin(nta)
        cn = node(nta, "ShaderNodeMapRange"); I(cn, "From Min").default_value = 0.35; I(cn, "From Max").default_value = 0.75
        link(nta, O(nz, "Fac"), I(cn, "Value"))
        al = math_(nta, 'MULTIPLY', bump.outputs["Color"], cn.outputs[0])
        link(nta, math_(nta, 'MULTIPLY', al, vb=0.95), I(pa_, "Alpha"))
        cr = node(nta, "ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.25, 1.0, 0.62, 1); cr.color_ramp.elements[1].color = (0.70, 0.38, 1.0, 1)
        cr.color_ramp.elements[0].position = 0.12; cr.color_ramp.elements[1].position = 0.65
        link(nta, sep.outputs["Z"], I(cr, "Fac"))
        pin(pa_, "Base Color", (0, 0, 0, 1)); link(nta, cr.outputs["Color"], I(pa_, "Emission Color")); pin(pa_, "Emission Strength", st_)
        curtain("aurora%d" % k, x0, x1, yy, z1, z0, ma, bend, 80, 0.0)
    # 板の下の浮き島（小さく・暗く・苔がうすく光る）
    shima = mat_rock("shima", moss=0.5, wet=0.3, dark=0.6, glow=(0.28, 0.2, 0.6))
    for b in BARS:
        if b["stage"] != "B": continue
        p0 = V(b["p"]); L, W = b["L"], b["W"]
        rock("shima%02d" % b["i"], p0 + V((0, 0, -0.40)), (L * 0.40, W * 0.70, 0.22), shima, b["yaw"], 0.10, 4, safe=True)
        bpy.ops.mesh.primitive_cone_add(radius1=0.16, radius2=0.01, depth=1.0, location=p0 + V((0, 0, -0.95)))
        o = bpy.context.object; o.rotation_euler = (math.pi, 0, 0); o.data.materials.append(shima)
    # 遠くの山並み（シルエット）と、ロゴの山
    mtn = mat_rock("yama", moss=0.45, wet=0.0, dark=1.6)
    def yama(name, c, rad, hgt, seed, sub=6, rough=0.12):
        bpy.ops.mesh.primitive_cone_add(vertices=160, radius1=rad, radius2=rad * 0.05, depth=hgt, location=(c[0], c[1], c[2] + hgt / 2))
        o = bpy.context.object; o.name = name
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=sub); bpy.ops.object.mode_set(mode='OBJECT')
        t_ = bpy.data.textures.new(name + "t", 'CLOUDS'); t_.noise_scale = hgt * 0.22; t_.noise_depth = 4
        d_ = o.modifiers.new("d", 'DISPLACE'); d_.texture = t_; d_.strength = hgt * rough; d_.mid_level = 0.5; d_.texture_coords = 'LOCAL'
        bpy.ops.object.shade_smooth(); o.data.materials.append(mtn); return o
    for k, (dx, dy, r_, h_) in enumerate(((-90, 210, 70, 55), (95, 230, 80, 62), (-30, 300, 90, 70), (160, 180, 60, 40), (-160, 170, 60, 38))):
        yama("toi_yama%d" % k, (PE.x + dx, PE.y + dy, ct - 6), r_, h_, k)
    ym = yama("logo_yama", (MOUNT.x, MOUNT.y, ct - 6), 75, 70, 9, 7, 0.05)
    bpy.context.view_layer.update()
    # 壁画：山の斜面に沿わせた網（カメラの終わりの位置から斜面へ光線を当てて、斜面の 0.35m 手前に置く）
    dg = bpy.context.evaluated_depsgraph_get(); ym_eval = ym.evaluated_get(dg)
    camE = V(FRM[-1]["cam"]); fwd = (LOGO - camE).normalized()
    right = fwd.cross(V((0, 0, 1))).normalized(); up = right.cross(fwd).normalized()
    WL, HL = 40.0, 40.0 * 2600 / 2048; NX, NY = 64, 80
    verts = []; uvs = []; faces = []
    inv = ym_eval.matrix_world.inverted()
    for j in range(NY + 1):
        for i in range(NX + 1):
            u, v = i / NX, j / NY
            pt = LOGO + right * ((u - 0.5) * WL) + up * ((v - 0.5) * HL)
            d_ = (pt - camE).normalized()
            ok, loc, nrm, idx = ym_eval.ray_cast(inv @ camE, (inv.to_3x3() @ d_).normalized())
            hit = ym_eval.matrix_world @ loc if ok else pt
            verts.append(tuple(hit - d_ * 0.35)); uvs.append((u, v))
    for j in range(NY):
        for i in range(NX):
            a = j * (NX + 1) + i; faces.append((a, a + 1, a + NX + 2, a + NX + 1))
    mlogo, ntl, pl = newmat("hekiga"); blend(mlogo, 'BLEND')
    txl = node(ntl, "ShaderNodeTexImage"); txl.image = load_img("hekiga_logo.png"); txl.extension = 'CLIP'
    link(ntl, txl.outputs["Color"], I(pl, "Base Color")); link(ntl, txl.outputs["Color"], I(pl, "Emission Color"))
    link(ntl, txl.outputs["Alpha"], I(pl, "Alpha")); pin(pl, "Roughness", 0.9)
    el_ = I(pl, "Emission Strength")
    f_rise0 = M["rise"][0]
    for ff, vv in ((1, 0.25), (f_rise0 + 30, 0.25), (f_rise0 + 70, 1.15), (NF, 1.3)):   # 見えてくるときに、ふわっと灯る
        el_.default_value = vv; el_.keyframe_insert("default_value", frame=ff)
    lg = obj_from_mesh("hekiga", verts, faces, mlogo)
    uvl_ = lg.data.uv_layers.new(name="UV")
    for li, lp in enumerate(lg.data.loops): uvl_.data[li].uv = uvs[lp.vertex_index]
    # 山の上の小さな灯り（ロゴのまわりにぽつぽつ）
    lamp = mat_drop("hotaru", (1.0, 0.8, 0.5), 6.0, 1.0)
    spray("hotaru", tuple(LOGO + V((0, 0, 0)) - fwd * 1.0), (WL * 1.3, HL * 1.1), 70, (-0.05, -0.05, -0.05), (0.05, 0.05, 0.08), 8.0, 0.12, lamp, 5, 0.0, False,
          rot=(math.pi / 2, 0, math.atan2(fwd.y, fwd.x) + math.pi / 2))
    # 夜の空気の粒
    mote = mat_drop("yoru_tsubu", (0.8, 0.8, 1.0), 2.0, 0.6)
    spray("yoru_tsubu", (cx, cy, ct + 3), (24, 30), 300, (-0.1, -0.1, -0.02), (0.1, 0.1, 0.12), 7.0, 0.012, mote, 7, 0.0, False)
    return [lo, lo2, lo3]

# 空：舞台Aは霧の翡翠と金、舞台Bは夜の藍＋星。入れ替えはキーで
stage("world")
w = sc.world or bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree
bg = wn.nodes.get("Background")
tcw = node(wn, "ShaderNodeTexCoord"); sepw = node(wn, "ShaderNodeSeparateXYZ"); link(wn, tcw.outputs["Generated"], sepw.inputs[0])
zmap = node(wn, "ShaderNodeMath"); zmap.operation = 'MULTIPLY_ADD'; zmap.inputs[1].default_value = 0.5; zmap.inputs[2].default_value = 0.5
link(wn, sepw.outputs["Z"], zmap.inputs[0])
rampA = node(wn, "ShaderNodeValToRGB")
rampA.color_ramp.elements[0].position = 0.40; rampA.color_ramp.elements[0].color = (0.06, 0.13, 0.09, 1)
rampA.color_ramp.elements[1].position = 0.85; rampA.color_ramp.elements[1].color = (0.80, 0.84, 0.66, 1)
link(wn, zmap.outputs[0], I(rampA, "Fac"))
vor = node(wn, "ShaderNodeTexVoronoi"); I(vor, "Scale").default_value = 220
stp = math_(wn, 'LESS_THAN', O(vor, "Distance"), vb=0.05)
link(wn, tcw.outputs["Generated"], I(vor, "Vector"))
vor2 = node(wn, "ShaderNodeTexVoronoi"); I(vor2, "Scale").default_value = 70; link(wn, tcw.outputs["Generated"], I(vor2, "Vector"))
stp2 = math_(wn, 'LESS_THAN', O(vor2, "Distance"), vb=0.035)
stars = math_(wn, 'ADD', math_(wn, 'MULTIPLY', stp, vb=2.5), math_(wn, 'MULTIPLY', stp2, vb=6.0))
rampB = node(wn, "ShaderNodeValToRGB")
rampB.color_ramp.elements[0].position = 0.45; rampB.color_ramp.elements[0].color = (0.05, 0.04, 0.11, 1)
rampB.color_ramp.elements[1].position = 0.9; rampB.color_ramp.elements[1].color = (0.004, 0.006, 0.025, 1)
link(wn, zmap.outputs[0], I(rampB, "Fac"))
addst = node(wn, "ShaderNodeMixRGB"); addst.blend_type = 'ADD'; addst.inputs[0].default_value = 1.0
link(wn, rampB.outputs["Color"], addst.inputs[1]); link(wn, stars, addst.inputs[2])
mixw = node(wn, "ShaderNodeMixRGB"); link(wn, rampA.outputs["Color"], mixw.inputs[1]); link(wn, addst.outputs["Color"], mixw.inputs[2])
link(wn, mixw.outputs["Color"], I(bg, "Color")); I(bg, "Strength").default_value = 1.0
for ff, vv in ((SWITCH - 1, 0.0), (SWITCH, 1.0)):
    mixw.inputs[0].default_value = vv; mixw.inputs[0].keyframe_insert("default_value", frame=ff)

stage("butai")
known = set(bpy.data.objects.keys())
lightsA = build_mori_no_taki()
objsA = set(bpy.data.objects.keys()) - known; known |= objsA
stage("butaiA")
lightsB = build_kumo_no_yoru()
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
