# 宇宙うんこ v4（Blender 3.6 LTS の EEVEE）：香港の架空の廃墟の街を、クレーンダウンしながら跳ねて下りる
# 動き・カメラ・配置は michi.json（michi_v4.py が計算して、すり抜けゼロを確かめたもの）をそのまま使う。ここでは形・質感・光だけ。
# 使い方: Blender -b -P scene_v4.py -- <このフォルダ> <出力フォルダ> <all | 1-100 | 5,60 | kensa,5 | none>
# 環境変数: UU_PCT=100  UU_SAMPLES=16  UU_MB=1(動きのぶれ)  UU_SAVE=1(.blendも保存)
import bpy, json, math, os, sys, time, random
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:]
WORK, OUT, FR = argv[0], argv[1], argv[2]
M = json.load(open(os.path.join(WORK, "michi.json")))
FPS, NF, FINAL = M["fps"], M["nf"], M["final_fr"]
FRM = M["frames"]; H_UNKO = M["h_unko"]; DWELL = M["dwell"]
ALLEY, FLOOR_H, NFLOOR, TOP = M["alley"], M["floor_h"], M["nfloor"], M["top"]
BAYS = M["bays"]; WIN_W, WIN_H, SILL = M["win"]
SOZAI = os.path.join(WORK, "sozai")
rnd = random.Random(7)
T0 = time.time()
def stage(x): print("STAGE", x, round(time.time() - T0, 1), flush=True)

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
tryset(EV, taa_render_samples=int(os.environ.get("UU_SAMPLES", "16")), use_bloom=True, bloom_intensity=0.06,
       bloom_threshold=0.9, bloom_radius=6.0, bloom_knee=0.5, use_gtao=True, gtao_distance=0.6, gtao_factor=1.0,
       use_ssr=True, use_ssr_refraction=False, use_ssr_halfres=True, ssr_quality=0.5, ssr_thickness=0.2, ssr_max_roughness=0.5,
       use_soft_shadows=False, use_volumetric_shadows=True, use_volumetric_lights=True,
       volumetric_tile_size='16', volumetric_samples=24, volumetric_start=0.5, volumetric_end=120.0, volumetric_light_clamp=4.0,
       use_motion_blur=os.environ.get("UU_MB", "1") == "1", motion_blur_shutter=0.3, motion_blur_steps=1,
       shadow_cube_size='512', shadow_cascade_size='1024', use_shadow_high_bitdepth=False, sss_samples=4)
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.resolution_percentage = int(os.environ.get("UU_PCT", "100"))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = NF
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 93
try: sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
except Exception: pass
sc.view_settings.exposure = 0.25

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
    return bpy.data.images.load(os.path.join(SOZAI, name), check_existing=True)
def anim_lin(owner):
    ad = getattr(owner, "animation_data", None)
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
def V(a): return Vector(a)
_CUBE_V = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
_CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
def mesh_obj(name, verts, faces, mat, smooth=False):
    me_ = bpy.data.meshes.new(name); me_.from_pydata(verts, [], faces); me_.update()
    if smooth:
        for pg in me_.polygons: pg.use_smooth = True
    o = bpy.data.objects.new(name, me_); bpy.context.collection.objects.link(o)
    if mat: me_.materials.append(mat)
    return o
def box(name, lo, hi, mat, coll=True):
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]; s = [max(0.001, hi[i] - lo[i]) for i in range(3)]
    o = mesh_obj(name, _CUBE_V, _CUBE_F, mat); o.location = c; o.scale = s
    return o
def cyl(name, p0, p1, r, mat, verts=12):
    p0, p1 = V(p0), V(p1); d = p1 - p0; L = d.length
    vs = []; fs = []
    for k in range(verts):
        a = 2 * math.pi * k / verts; vs.append((r * math.cos(a), r * math.sin(a), -L / 2)); vs.append((r * math.cos(a), r * math.sin(a), L / 2))
    for k in range(verts):
        a0, a1 = 2 * k, 2 * ((k + 1) % verts); fs.append((a0, a0 + 1, a1 + 1, a1))
    fs.append(tuple(2 * k for k in range(verts))[::-1]); fs.append(tuple(2 * k + 1 for k in range(verts)))
    o = mesh_obj(name, vs, fs, mat, smooth=verts >= 10); o.location = (p0 + p1) / 2
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return o
def plane(name, center, sx, sy, mat, rot=(0, 0, 0)):
    o = mesh_obj(name, [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [(0, 1, 2, 3)], mat)
    o.location = center; o.scale = (sx, sy, 1); o.rotation_euler = rot
    return o
def noise_tex(nt, scale, detail=3.0, rough=0.5, coord=None, mapping=None):
    tc = coord or node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = scale; I(nz, "Detail").default_value = detail; I(nz, "Roughness").default_value = rough
    if mapping:
        mp = node(nt, "ShaderNodeMapping"); I(mp, "Scale").default_value = mapping; link(nt, tc.outputs["Object"], I(mp, "Vector")); link(nt, mp.outputs[0], I(nz, "Vector"))
    else: link(nt, tc.outputs["Object"], I(nz, "Vector"))
    return nz, tc

# =====================================================================
# 質感
# =====================================================================
stage("materials")
def mat_tile(name, tint=(0.52, 0.50, 0.46), tint2=(0.36, 0.33, 0.30), grime=0.75, tile=9.0):
    """古いタイル張りの外壁：タイルの目地・色むら・縦の雨だれ・黒ずみ"""
    m, nt, p = newmat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    br = node(nt, "ShaderNodeTexBrick"); I(br, "Scale").default_value = tile; br.offset = 0.5; br.squash = 1.0
    I(br, "Mortar Size").default_value = 0.035; I(br, "Mortar Smooth").default_value = 0.3; I(br, "Bias").default_value = 0.0
    I(br, "Color1").default_value = tint + (1,); I(br, "Color2").default_value = tint2 + (1,); I(br, "Mortar").default_value = (0.12, 0.11, 0.10, 1)
    link(nt, tc.outputs["Object"], I(br, "Vector"))
    # 縦に流れる雨だれ（縦に伸ばしたノイズ）
    nz, _ = noise_tex(nt, 3.0, 5.0, 0.6, tc, mapping=(2.5, 2.5, 0.12))
    rp = node(nt, "ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.38; rp.color_ramp.elements[0].color = (1 - grime * 0.8,) * 3 + (1,)
    rp.color_ramp.elements[1].position = 0.62; rp.color_ramp.elements[1].color = (1, 1, 1, 1)
    link(nt, O(nz, "Fac"), I(rp, "Fac"))
    # 大きな色むら（しみ・カビ）
    nz2, _ = noise_tex(nt, 0.35, 3.0, 0.55, tc)
    rp2 = node(nt, "ShaderNodeValToRGB"); rp2.color_ramp.elements[0].position = 0.3; rp2.color_ramp.elements[0].color = (0.45, 0.42, 0.33, 1)
    rp2.color_ramp.elements[1].position = 0.7; rp2.color_ramp.elements[1].color = (1, 1, 1, 1)
    link(nt, O(nz2, "Fac"), I(rp2, "Fac"))
    mx = node(nt, "ShaderNodeMixRGB"); mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
    link(nt, br.outputs["Color"], mx.inputs[1]); link(nt, rp.outputs["Color"], mx.inputs[2])
    mx2 = node(nt, "ShaderNodeMixRGB"); mx2.blend_type = 'MULTIPLY'; mx2.inputs[0].default_value = 1.0
    link(nt, mx.outputs[0], mx2.inputs[1]); link(nt, rp2.outputs["Color"], mx2.inputs[2])
    link(nt, mx2.outputs[0], I(p, "Base Color"))
    # 湿った所はつやが出る（雨だれの所）
    rr = node(nt, "ShaderNodeMapRange"); I(rr, "From Min").default_value = 0.3; I(rr, "From Max").default_value = 0.7
    I(rr, "To Min").default_value = 0.35; I(rr, "To Max").default_value = 0.75
    link(nt, O(nz, "Fac"), I(rr, "Value")); link(nt, rr.outputs[0], I(p, "Roughness"))
    bp = node(nt, "ShaderNodeBump"); I(bp, "Strength").default_value = 0.35; link(nt, br.outputs["Fac"], I(bp, "Height")); link(nt, bp.outputs[0], I(p, "Normal"))
    pin(p, "Specular IOR Level", 0.4)
    return m
def mat_concrete(name, col=(0.42, 0.41, 0.38), wet=0.0):
    m, nt, p = newmat(name)
    nz, tc = noise_tex(nt, 6.0, 6.0, 0.65)
    rp = node(nt, "ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.35; rp.color_ramp.elements[0].color = tuple(c * 0.55 for c in col) + (1,)
    rp.color_ramp.elements[1].position = 0.7; rp.color_ramp.elements[1].color = col + (1,)
    link(nt, O(nz, "Fac"), I(rp, "Fac")); link(nt, rp.outputs["Color"], I(p, "Base Color"))
    nz2, _ = noise_tex(nt, 2.0, 4.0, 0.6, tc, mapping=(2.0, 2.0, 0.15))
    rr = node(nt, "ShaderNodeMapRange"); I(rr, "To Min").default_value = 0.25 if wet else 0.6; I(rr, "To Max").default_value = 0.9
    link(nt, O(nz2, "Fac"), I(rr, "Value")); link(nt, rr.outputs[0], I(p, "Roughness"))
    bp = node(nt, "ShaderNodeBump"); I(bp, "Strength").default_value = 0.25; link(nt, O(nz, "Fac"), I(bp, "Height")); link(nt, bp.outputs[0], I(p, "Normal"))
    return m
def mat_metal(name, col=(0.30, 0.30, 0.31), rust=0.5, rough=0.45):
    """錆びた金属（室外機・配管・看板の箱）"""
    m, nt, p = newmat(name)
    nz, tc = noise_tex(nt, 4.0, 5.0, 0.7)
    rp = node(nt, "ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.5 - rust * 0.25; rp.color_ramp.elements[0].color = col + (1,)
    rp.color_ramp.elements[1].position = 0.5 + rust * 0.1; rp.color_ramp.elements[1].color = (0.30, 0.13, 0.05, 1)
    link(nt, O(nz, "Fac"), I(rp, "Fac")); link(nt, rp.outputs["Color"], I(p, "Base Color"))
    rr = node(nt, "ShaderNodeMapRange"); I(rr, "To Min").default_value = rough; I(rr, "To Max").default_value = min(1.0, rough + 0.45)
    link(nt, O(nz, "Fac"), I(rr, "Value")); link(nt, rr.outputs[0], I(p, "Roughness"))
    pin(p, "Metallic", 0.6)
    bp = node(nt, "ShaderNodeBump"); I(bp, "Strength").default_value = 0.2; link(nt, O(nz, "Fac"), I(bp, "Height")); link(nt, bp.outputs[0], I(p, "Normal"))
    return m
def mat_glass(name):
    m, nt, p = newmat(name); blend(m, 'BLEND')
    pin(p, "Base Color", (0.05, 0.06, 0.08, 1)); pin(p, "Roughness", 0.06); pin(p, "Specular IOR Level", 0.9); pin(p, "Alpha", 0.30)
    nz, _ = noise_tex(nt, 5.0, 4.0, 0.6)
    rr = node(nt, "ShaderNodeMapRange"); I(rr, "To Min").default_value = 0.03; I(rr, "To Max").default_value = 0.35
    link(nt, O(nz, "Fac"), I(rr, "Value")); link(nt, rr.outputs[0], I(p, "Roughness"))
    tryset(m, use_screen_refraction=False)
    return m
def mat_emit(name, col, strength=1.0):
    m, nt, p = newmat(name)
    pin(p, "Base Color", (0, 0, 0, 1)); pin(p, "Emission Color", col + (1,)); pin(p, "Emission Strength", strength); pin(p, "Roughness", 0.8)
    return m, I(p, "Emission Strength")
def mat_room(name, col):
    """部屋の奥の壁：暖色の明かり（強さはコマごとに変える）＋少しの壁紙のむら"""
    m, nt, p = newmat(name)
    nz, _ = noise_tex(nt, 2.0, 3.0, 0.5)
    rp = node(nt, "ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.3; rp.color_ramp.elements[0].color = tuple(c * 0.7 for c in col) + (1,)
    rp.color_ramp.elements[1].position = 0.7; rp.color_ramp.elements[1].color = col + (1,)
    link(nt, O(nz, "Fac"), I(rp, "Fac")); link(nt, rp.outputs["Color"], I(p, "Emission Color")); pin(p, "Base Color", tuple(c * 0.5 for c in col) + (1,))
    pin(p, "Emission Strength", 0.0); pin(p, "Roughness", 0.9)
    return m, I(p, "Emission Strength")
def mat_sil(name="sil"):
    m, nt, p = newmat(name); pin(p, "Base Color", (0.012, 0.010, 0.012, 1)); pin(p, "Roughness", 0.9); pin(p, "Specular IOR Level", 0.2); return m
def mat_neon(name, img):
    m, nt, p = newmat(name); blend(m, 'BLEND')
    tex = node(nt, "ShaderNodeTexImage"); tex.image = load_img(img); tex.extension = 'CLIP'
    link(nt, tex.outputs["Color"], I(p, "Emission Color")); link(nt, tex.outputs["Color"], I(p, "Base Color"))
    pin(p, "Emission Strength", 6.0); pin(p, "Roughness", 0.5)
    return m, I(p, "Emission Strength")
def mat_cloth(name, img):
    m, nt, p = newmat(name)
    tex = node(nt, "ShaderNodeTexImage"); tex.image = load_img(img)
    link(nt, tex.outputs["Color"], I(p, "Base Color")); pin(p, "Roughness", 0.95); pin(p, "Specular IOR Level", 0.1)
    try: link(nt, tex.outputs["Color"], I(p, "Subsurface Color")); pin(p, "Subsurface Weight", 0.1)
    except Exception: pass
    return m
def mat_street(name, pond):
    """濡れたアスファルト：水たまり（ノイズのしきい値）＝鏡のよう／それ以外も湿ってつやあり。着水の波紋は時間で動く"""
    m, nt, p = newmat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 0.55; I(nz, "Detail").default_value = 4; link(nt, tc.outputs["Object"], I(nz, "Vector"))
    fine = node(nt, "ShaderNodeTexNoise"); I(fine, "Scale").default_value = 40; I(fine, "Detail").default_value = 6; link(nt, tc.outputs["Object"], I(fine, "Vector"))
    # 水たまりのマスク：ノイズ > 0.55、着水点のまわりは必ず水たまり
    sep = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tc.outputs["Object"], sep.inputs[0])
    dx = math_(nt, 'SUBTRACT', sep.outputs["X"], vb=pond[0]); dy = math_(nt, 'SUBTRACT', sep.outputs["Y"], vb=pond[1])
    dist = math_(nt, 'SQRT', math_(nt, 'ADD', math_(nt, 'MULTIPLY', dx, dx), math_(nt, 'MULTIPLY', dy, dy)))
    pondmask = math_(nt, 'LESS_THAN', dist, vb=1.35)
    nmask = math_(nt, 'GREATER_THAN', O(nz, "Fac"), vb=0.58)
    mask = math_(nt, 'MAXIMUM', pondmask, nmask)
    # 色：アスファルト（細かいざらつき）、水たまりは暗く
    rp = node(nt, "ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = 0.3; rp.color_ramp.elements[0].color = (0.035, 0.035, 0.038, 1)
    rp.color_ramp.elements[1].position = 0.8; rp.color_ramp.elements[1].color = (0.11, 0.105, 0.10, 1)
    link(nt, O(fine, "Fac"), I(rp, "Fac"))
    mx = node(nt, "ShaderNodeMixRGB"); link(nt, mask, mx.inputs[0]); link(nt, rp.outputs["Color"], mx.inputs[1]); mx.inputs[2].default_value = (0.01, 0.012, 0.016, 1)
    # ひび割れ（ボロノイの縁）と、補修の継ぎはぎ
    vcr = node(nt, "ShaderNodeTexVoronoi"); vcr.feature = 'DISTANCE_TO_EDGE'; I(vcr, "Scale").default_value = 0.9; link(nt, tc.outputs["Object"], I(vcr, "Vector"))
    crack = math_(nt, 'GREATER_THAN', O(vcr, "Distance"), vb=0.012)
    crk = node(nt, "ShaderNodeMixRGB"); crk.blend_type = 'MULTIPLY'; crk.inputs[0].default_value = 0.85
    link(nt, mx.outputs[0], crk.inputs[1]); link(nt, crack, crk.inputs[2])
    link(nt, crk.outputs[0], I(p, "Base Color"))
    rg = node(nt, "ShaderNodeMixRGB"); link(nt, mask, rg.inputs[0]); rg.inputs[1].default_value = (0.42, 0.42, 0.42, 1); rg.inputs[2].default_value = (0.03, 0.03, 0.03, 1)
    link(nt, rg.outputs[0], I(p, "Roughness")); pin(p, "Specular IOR Level", 0.8)
    # 波紋：着水から広がる輪（sin）× 減衰。t はコマで動かす
    tval = node(nt, "ShaderNodeValue"); tval.name = "ripple_t"; tval.outputs[0].default_value = -1.0
    tval.outputs[0].keyframe_insert("default_value", frame=1); tval.outputs[0].default_value = -1.0; tval.outputs[0].keyframe_insert("default_value", frame=FINAL)
    tval.outputs[0].default_value = (NF - FINAL) / FPS; tval.outputs[0].keyframe_insert("default_value", frame=NF)
    tt = tval.outputs[0]
    phase = math_(nt, 'SUBTRACT', math_(nt, 'MULTIPLY', dist, vb=2 * math.pi / 0.28), math_(nt, 'MULTIPLY', tt, vb=2 * math.pi * 3.2))
    ring = math_(nt, 'SINE', phase)
    front = math_(nt, 'LESS_THAN', dist, math_(nt, 'MULTIPLY', tt, vb=1.6))          # 波の先端より内側だけ
    tpos = math_(nt, 'GREATER_THAN', tt, vb=0.0)
    decay = math_(nt, 'EXPONENT', math_(nt, 'MULTIPLY', math_(nt, 'ADD', math_(nt, 'MULTIPLY', tt, vb=0.9), math_(nt, 'MULTIPLY', dist, vb=1.4)), vb=-1.0))
    amp = math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', ring, front), tpos), decay)
    # 小さな雨の揺らぎ＋波紋 → バンプ
    wob = node(nt, "ShaderNodeTexNoise"); I(wob, "Scale").default_value = 9.0; I(wob, "Detail").default_value = 2
    mpw = node(nt, "ShaderNodeMapping"); link(nt, tc.outputs["Object"], I(mpw, "Vector")); link(nt, mpw.outputs[0], I(wob, "Vector"))
    lo_ = I(mpw, "Location"); lo_.default_value = (0, 0, 0); lo_.keyframe_insert("default_value", frame=1); lo_.default_value = (0, 0, 6.0); lo_.keyframe_insert("default_value", frame=NF)
    hgt = math_(nt, 'ADD', math_(nt, 'MULTIPLY', O(wob, "Fac"), vb=0.012), math_(nt, 'MULTIPLY', amp, vb=0.06))
    hgt = math_(nt, 'MULTIPLY', hgt, mask)
    bp = node(nt, "ShaderNodeBump"); I(bp, "Strength").default_value = 0.6; link(nt, hgt, I(bp, "Height")); link(nt, bp.outputs[0], I(p, "Normal"))
    anim_lin(nt)
    return m
M_TILE_L = mat_tile("tile_L", (0.50, 0.47, 0.42), (0.34, 0.31, 0.28), 0.8, 9.0)
M_TILE_R = mat_tile("tile_R", (0.43, 0.46, 0.46), (0.28, 0.31, 0.31), 0.75, 7.0)
M_TILE_S = mat_tile("tile_S", (0.36, 0.34, 0.33), (0.25, 0.23, 0.22), 0.9, 8.0)
M_CONC = mat_concrete("conc"); M_CONC_D = mat_concrete("conc_dark", (0.30, 0.29, 0.27))
M_METAL = mat_metal("metal"); M_METAL_R = mat_metal("metal_rust", (0.25, 0.22, 0.20), 0.85, 0.6); M_PIPE = mat_metal("pipe", (0.22, 0.21, 0.20), 0.7, 0.5)
M_GLASS = mat_glass("glass"); M_SIL = mat_sil()
M_FRAME = mat_metal("frame", (0.35, 0.34, 0.32), 0.3, 0.5)
M_STREET = mat_street("street", M["pond"])
M_CLOTH = [mat_cloth("cloth%d" % k, "cloth%d.png" % k) for k in range(6)]
M_DIM, _ = mat_emit("dim", (1.0, 0.68, 0.38), 0.25)
M_TV, TV_STR = mat_emit("tv", (0.55, 0.7, 1.0), 0.6)
for ff in range(1, NF + 1, 7):   # テレビのちらつき
    TV_STR.default_value = rnd.uniform(0.25, 0.9); TV_STR.keyframe_insert("default_value", frame=ff)
M_SHUTTER = mat_metal("shutter", (0.28, 0.27, 0.26), 0.5, 0.55)
M_SHOP, SHOP_STR = mat_emit("shop", (1.0, 0.62, 0.30), 1.6)

# =====================================================================
# 街：塔（開口のある壁）・部屋・路地・側壁・屋上・遠くの街・地面
# =====================================================================
stage("city")
SOLID = []   # 当たり検査の相手（名前）
def facade(side):
    sgn = side; mat = M_TILE_L if side < 0 else M_TILE_R
    x_in, x_out = sgn * ALLEY, sgn * 7.0
    lo_x, hi_x = min(x_in, x_out), max(x_in, x_out)
    # 本体（窓の帯の部分は開口にするので、本体は y 0.35 より奥。外壁は帯で作る）
    box("tower%s_body" % ("L" if side < 0 else "R"), (lo_x, 0.35, 0), (hi_x, 6.35, TOP), mat)
    # 外壁：柱（窓列の間）と、床ごとの帯（窓の上下）
    edges = sorted([ALLEY] + [b + WIN_W / 2 + 0.0 for b in BAYS] + [b - WIN_W / 2 for b in BAYS] + [7.0])
    # 柱：ALLEY〜bay0 の内側、bay 間、bay2 の外側〜7
    piers = [(ALLEY, BAYS[0] - WIN_W / 2), (BAYS[0] + WIN_W / 2, BAYS[1] - WIN_W / 2), (BAYS[1] + WIN_W / 2, BAYS[2] - WIN_W / 2), (BAYS[2] + WIN_W / 2, 7.0)]
    for k, (a, b) in enumerate(piers):
        xa, xb = sorted((sgn * a, sgn * b))
        box("pier%s%d" % (side, k), (xa, 0.0, 0), (xb, 0.36, TOP), mat)
    for fl in range(NFLOOR):
        z0 = fl * FLOOR_H
        box("band%s%d" % (side, fl), (lo_x, 0.0, z0), (hi_x, 0.36, z0 + SILL), mat)
        box("band%s%db" % (side, fl), (lo_x, 0.0, z0 + SILL + WIN_H), (hi_x, 0.36, z0 + FLOOR_H), mat)
        # 床のスラブの線（少し出っぱる）
        box("slab%s%d" % (side, fl), (lo_x, -0.05, z0 - 0.02), (hi_x, 0.0, z0 + 0.10), M_CONC_D)
    # 屋上のパラペット
    box("parapet%s" % side, (lo_x, -0.1, TOP), (hi_x, 0.5, TOP + 0.9), M_CONC)
    box("roofslab%s" % side, (lo_x, 0.35, TOP), (hi_x, 6.35, TOP + 0.2), M_CONC_D)
    box("parapet%s_back" % side, (lo_x, 5.85, TOP), (hi_x, 6.35, TOP + 0.9), M_CONC)
facade(-1); facade(1)
# 窓（ガラス・枠・窓台）と部屋
ROOM_MATS = {}
def window(side, bay, fl, kind):
    cx = side * BAYS[bay]; z0 = fl * FLOOR_H + SILL; name = "w%s%d_%d" % ("L" if side < 0 else "R", bay, fl)
    if fl == 0: return   # 1階は店（別）
    # 枠
    t = 0.05
    box(name + "_fL", (cx - WIN_W / 2 - t, 0.0, z0 - t), (cx - WIN_W / 2, 0.30, z0 + WIN_H + t), M_FRAME)
    box(name + "_fR", (cx + WIN_W / 2, 0.0, z0 - t), (cx + WIN_W / 2 + t, 0.30, z0 + WIN_H + t), M_FRAME)
    box(name + "_fT", (cx - WIN_W / 2, 0.0, z0 + WIN_H), (cx + WIN_W / 2, 0.30, z0 + WIN_H + t), M_FRAME)
    box(name + "_sill", (cx - WIN_W / 2 - 0.08, -0.05, z0 - 0.06), (cx + WIN_W / 2 + 0.08, 0.30, z0), M_CONC)
    # 中桟
    box(name + "_mul", (cx - 0.02, 0.12, z0), (cx + 0.02, 0.16, z0 + WIN_H), M_FRAME)
    # ガラス
    plane(name + "_g", (cx, 0.14, z0 + WIN_H / 2), WIN_W, WIN_H, M_GLASS, rot=(math.pi / 2, 0, 0))
    # 部屋（奥行き 2.4）：奥の壁・床・天井・横の壁
    d = 2.4; rw = WIN_W + 0.5; rh = WIN_H + 0.7; zr = z0 - 0.35
    if kind in ("lit", "dim", "tv"):
        col = (1.0, 0.62, 0.32) if kind != "tv" else (0.5, 0.6, 0.9)
        m, strength = mat_room(name + "_rm", col if kind == "lit" else (1.0, 0.66, 0.36))
        ROOM_MATS[name] = strength
    else:
        m = M_CONC_D; ROOM_MATS[name] = None
    plane(name + "_back", (cx, 0.36 + d, zr + rh / 2), rw, rh, m, rot=(math.pi / 2, 0, 0))
    plane(name + "_floor", (cx, 0.36 + d / 2, zr), rw, d, M_CONC_D)
    plane(name + "_ceil", (cx, 0.36 + d / 2, zr + rh), rw, d, M_CONC_D)
    plane(name + "_sL", (cx - rw / 2, 0.36 + d / 2, zr + rh / 2), rh, d, M_CONC_D, rot=(0, math.pi / 2, 0))
    plane(name + "_sR", (cx + rw / 2, 0.36 + d / 2, zr + rh / 2), rh, d, M_CONC_D, rot=(0, math.pi / 2, 0))
    if kind == "dim":
        plane(name + "_lamp", (cx + rnd.uniform(-0.3, 0.3), 0.36 + d * 0.6, zr + rh * 0.85), 0.25, 0.25, M_DIM)
        # カーテン（半透明の布）
        plane(name + "_cur", (cx, 0.40, z0 + WIN_H / 2), WIN_W, WIN_H, M_CLOTH[rnd.randint(0, 5)], rot=(math.pi / 2, 0, 0))
    if kind == "tv":
        plane(name + "_tv", (cx + rnd.uniform(-0.2, 0.2), 0.36 + d * 0.5, zr + 0.6), 0.6, 0.4, M_TV, rot=(math.pi / 2, 0, 0))
    return (cx, 0.36, zr)
# 人影（シルエット）：部屋の中、窓と奥の壁の間に立つ
def figure(name, base, scale=1.0, seated=False):
    """頭・胴・腕・脚。返り値 dict（keyframe 用）。base＝足元"""
    parts = {}
    bx, by, bz = base
    e = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(e); e.location = base; e.empty_display_size = 0.1
    def part(n, kind, loc, scl, rot=(0, 0, 0)):
        if kind == "s": bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1, location=(0, 0, 0))
        elif kind == "c": bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1, depth=1, location=(0, 0, 0))
        else: bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        o = bpy.context.object; o.name = name + "_" + n; o.scale = scl; o.location = loc; o.rotation_euler = rot
        o.data.materials.append(M_SIL); o.parent = e; parts[n] = o
        try: bpy.ops.object.shade_smooth()
        except Exception: pass
        return o
    s = scale
    leg = 0.45 * s if not seated else 0.0
    hip = (0.42 if seated else 0.85) * s
    part("torso", "s", (0, 0, hip + 0.28 * s), (0.17 * s, 0.11 * s, 0.30 * s))
    part("head", "s", (0, 0, hip + 0.68 * s), (0.105 * s, 0.11 * s, 0.125 * s))
    part("neck", "c", (0, 0, hip + 0.55 * s), (0.04 * s, 0.04 * s, 0.08 * s))
    for sg, n in ((-1, "armL"), (1, "armR")):
        part(n, "c", (sg * 0.2 * s, 0, hip + 0.32 * s), (0.04 * s, 0.04 * s, 0.28 * s))
    if not seated:
        for sg, n in ((-1, "legL"), (1, "legR")):
            part(n, "c", (sg * 0.08 * s, 0, hip / 2), (0.055 * s, 0.055 * s, hip / 2))
    else:
        for sg, n in ((-1, "legL"), (1, "legR")):
            part(n, "c", (sg * 0.08 * s, -0.18 * s, hip - 0.05 * s), (0.055 * s, 0.055 * s, 0.2 * s), rot=(math.pi / 2, 0, 0))
    parts["_root"] = e
    return parts
def key_loop(parts, fn, f0=1, f1=NF, step=2):
    """fn(t秒) -> {part: (loc or None, rot or None)}"""
    for f in range(f0, f1 + 1, step):
        t = (f - 1) / FPS
        for n, (loc, rot) in fn(t).items():
            o = parts[n]
            if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
            if rot is not None: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)
def person(kind, name, cx, y0, zr, seed):
    r = random.Random(seed); s = 1.0
    depth = y0 + 1.1
    if kind == "piano":
        # ピアノ（箱）＋座る人・両腕が鍵盤の上で上下
        box(name + "_piano", (cx - 0.55, depth + 0.25, zr), (cx + 0.55, depth + 0.75, zr + 1.0), M_SIL)
        box(name + "_lid", (cx - 0.5, depth + 0.3, zr + 1.0), (cx + 0.5, depth + 0.7, zr + 1.35), M_SIL)
        P = figure(name, (cx, depth - 0.15, zr), 0.95, seated=True)
        P["armL"].rotation_euler = (0.9, 0, 0); P["armR"].rotation_euler = (0.9, 0, 0)
        def fn(t):
            a = 0.12 * math.sin(2 * math.pi * 1.6 * t); b = 0.12 * math.sin(2 * math.pi * 1.6 * t + 1.3)
            return {"armL": (None, (0.95 + a, 0, 0.1)), "armR": (None, (0.95 + b, 0, -0.1)), "head": ((0, 0.02 * math.sin(2 * math.pi * 0.5 * t), 0.42 * 0.95 + 0.68 * 0.95 + 0.02 * math.sin(2 * math.pi * 1.6 * t)), None)}
        key_loop(P, fn)
    elif kind == "couple":
        A = figure(name + "a", (cx - 0.13, depth, zr), 0.98); B = figure(name + "b", (cx + 0.13, depth + 0.05, zr), 0.92)
        A["armR"].rotation_euler = (0, -1.0, 0); B["armL"].rotation_euler = (0, 1.0, 0)
        def fn(t):
            sw = 0.04 * math.sin(2 * math.pi * 0.35 * t)
            return {"_root": ((cx - 0.13 + sw, depth, zr), (0, 0, 0.06 * math.sin(2 * math.pi * 0.35 * t)))}
        key_loop(A, fn)
        def fn2(t):
            sw = 0.04 * math.sin(2 * math.pi * 0.35 * t)
            return {"_root": ((cx + 0.13 + sw, depth + 0.05, zr), (0, 0, 0.06 * math.sin(2 * math.pi * 0.35 * t)))}
        key_loop(B, fn2)
    elif kind == "dance":
        P = figure(name, (cx, depth, zr), 1.0)
        def fn(t):
            w = 2 * math.pi * 1.1 * t
            return {"_root": ((cx + 0.12 * math.sin(w / 2), depth, zr + 0.05 * abs(math.sin(w))), (0, 0, 0.35 * math.sin(w / 2))),
                    "armL": (None, (0.4 * math.sin(w), -2.2 + 0.3 * math.sin(w), 0)), "armR": (None, (0.4 * math.cos(w), 2.2 - 0.3 * math.sin(w + 1), 0))}
        key_loop(P, fn)
    elif kind == "workout":
        P = figure(name, (cx, depth, zr), 1.0)
        box(name + "_bar", (cx - 0.5, depth - 0.05, zr + 1.0), (cx + 0.5, depth + 0.05, zr + 1.05), M_SIL)
        bar = bpy.data.objects[name + "_bar"]
        def fn(t):
            w = 2 * math.pi * 0.55 * t; up = 0.5 * (1 + math.sin(w)); zb = zr + 1.15 + 0.55 * up
            bar.location = (cx, depth, zb); bar.keyframe_insert("location", frame=int(t * FPS) + 1)
            return {"armL": ((-0.2, 0, 0.85 + 0.32 + 0.25 * up), (0, 0, 0)), "armR": ((0.2, 0, 0.85 + 0.32 + 0.25 * up), (0, 0, 0)),
                    "_root": ((cx, depth, zr - 0.08 * (1 - up)), None)}
        key_loop(P, fn)
    elif kind == "study":
        box(name + "_desk", (cx - 0.5, depth - 0.1, zr + 0.62), (cx + 0.5, depth + 0.4, zr + 0.68), M_SIL)
        plane(name + "_lamp", (cx + 0.35, depth + 0.3, zr + 0.95), 0.18, 0.1, M_DIM)
        P = figure(name, (cx - 0.1, depth + 0.45, zr), 0.95, seated=True)
        P["armL"].rotation_euler = (1.2, 0, 0); P["armR"].rotation_euler = (1.2, 0, 0)
        def fn(t):
            return {"head": ((0, -0.03 + 0.02 * math.sin(2 * math.pi * 0.3 * t), 0.42 * 0.95 + 0.68 * 0.95), (0.25 + 0.08 * math.sin(2 * math.pi * 0.3 * t), 0, 0)),
                    "armR": (None, (1.2 + 0.1 * math.sin(2 * math.pi * 2.0 * t), 0, -0.2))}
        key_loop(P, fn)
    elif kind == "cat":
        # 窓台に座る猫（頭・耳・胴・しっぽ）
        e = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(e); e.location = (cx + 0.2, y0 + 0.25, zr + 0.35)
        def part(n, kind_, loc, scl, rot=(0, 0, 0)):
            if kind_ == "s": bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1, location=(0, 0, 0))
            elif kind_ == "cone": bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1, depth=1, location=(0, 0, 0))
            else: bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1, depth=1, location=(0, 0, 0))
            o = bpy.context.object; o.name = name + "_" + n; o.scale = scl; o.location = loc; o.rotation_euler = rot; o.data.materials.append(M_SIL); o.parent = e; return o
        part("body", "s", (0, 0, 0.13), (0.13, 0.11, 0.14)); part("head", "s", (0.0, -0.05, 0.33), (0.085, 0.08, 0.075))
        part("earL", "cone", (-0.05, -0.05, 0.41), (0.03, 0.02, 0.06)); part("earR", "cone", (0.05, -0.05, 0.41), (0.03, 0.02, 0.06))
        tail = part("tail", "c", (0.16, 0.03, 0.08), (0.02, 0.02, 0.22), rot=(0, 1.2, 0))
        for f in range(1, NF + 1, 2):
            t = (f - 1) / FPS; tail.rotation_euler = (0.3 * math.sin(2 * math.pi * 0.4 * t), 1.2 + 0.25 * math.sin(2 * math.pi * 0.6 * t), 0); tail.keyframe_insert("rotation_euler", frame=f)
    elif kind == "read":
        box(name + "_chair", (cx - 0.3, depth - 0.1, zr), (cx + 0.3, depth + 0.5, zr + 0.45), M_SIL)
        box(name + "_chairb", (cx - 0.3, depth + 0.4, zr), (cx + 0.3, depth + 0.5, zr + 1.0), M_SIL)
        P = figure(name, (cx, depth + 0.1, zr), 0.95, seated=True)
        P["armL"].rotation_euler = (1.3, 0, 0.3); P["armR"].rotation_euler = (1.3, 0, -0.3)
        box(name + "_book", (cx - 0.16, depth - 0.25, zr + 0.75), (cx + 0.16, depth - 0.22, zr + 0.98), M_SIL)
        def fn(t):
            k = max(0.0, math.sin(2 * math.pi * 0.12 * t)) ** 8
            return {"armR": (None, (1.3 - 0.5 * k, 0, -0.3)), "head": ((0, -0.02, 0.42 * 0.95 + 0.68 * 0.95), (0.3, 0, 0.1 * math.sin(2 * math.pi * 0.2 * t)))}
        key_loop(P, fn)
    elif kind == "guitar":
        P = figure(name, (cx, depth, zr), 1.0, seated=True)
        box(name + "_stool", (cx - 0.18, depth - 0.18, zr), (cx + 0.18, depth + 0.18, zr + 0.42), M_SIL)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1, location=(cx + 0.05, depth - 0.3, zr + 0.6)); g = bpy.context.object; g.name = name + "_gt"; g.scale = (0.22, 0.08, 0.18); g.data.materials.append(M_SIL)
        cyl(name + "_neck", (cx + 0.05, depth - 0.3, zr + 0.6), (cx - 0.5, depth - 0.3, zr + 0.95), 0.02, M_SIL)
        P["armL"].rotation_euler = (0.5, 1.0, 0); P["armR"].rotation_euler = (1.0, -0.4, 0)
        def fn(t):
            return {"armR": (None, (1.0 + 0.25 * math.sin(2 * math.pi * 2.2 * t), -0.4, 0)), "head": ((0, -0.02, 0.42 + 0.68), (0.15 + 0.1 * math.sin(2 * math.pi * 1.1 * t), 0, 0.15))}
        key_loop(P, fn)
    elif kind == "cook":
        P = figure(name, (cx + 0.1, depth - 0.2, zr), 1.0)
        box(name + "_counter", (cx - 0.7, depth - 0.9, zr), (cx + 0.7, depth - 0.6, zr + 0.9), M_SIL)
        P["armL"].rotation_euler = (1.4, 0, 0.3); P["armR"].rotation_euler = (1.4, 0, -0.3)
        def fn(t):
            return {"armR": (None, (1.4 + 0.3 * math.sin(2 * math.pi * 1.5 * t), 0, -0.3)), "_root": ((cx + 0.1 + 0.05 * math.sin(2 * math.pi * 0.3 * t), depth - 0.2, zr), None)}
        key_loop(P, fn)
ROOM_ON = {}      # name -> strength socket（部屋ごとの明かり）
for r in M["rooms"]:
    name = "w%s%d_%d" % ("L" if r["side"] < 0 else "R", r["bay"], r["floor"])
    res = window(r["side"], r["bay"], r["floor"], "lit")
    if res is None: continue
    cx, y0, zr = res
    person(r["person"], name + "_p", cx, y0, zr, seed=hash(name) % 1000)
    ROOM_ON[name] = (ROOM_MATS[name], r["on"], r)
for r in M["others"]:
    window(r["side"], r["bay"], r["floor"], r["mode"])
# 1階：店（右の塔・路地側）と、シャッター
for side in (-1, 1):
    for bay in range(3):
        cx = side * BAYS[bay]; w = WIN_W + 0.35
        if side > 0 and bay == 0:
            # 麺屋：大きな窓・暖色・料理人・湯気（半透明の板）
            plane("shop_g", (cx, 0.14, 0.3 + 1.0), w, 2.0, M_GLASS, rot=(math.pi / 2, 0, 0))
            box("shop_fL", (cx - w / 2 - 0.06, 0.0, 0.2), (cx - w / 2, 0.3, 2.4), M_FRAME); box("shop_fR", (cx + w / 2, 0.0, 0.2), (cx + w / 2 + 0.06, 0.3, 2.4), M_FRAME)
            d = 2.6; rw = w + 0.6
            m, st = mat_room("shop_rm", (1.0, 0.66, 0.36)); st.default_value = 1.3
            plane("shop_back", (cx, 0.36 + d, 1.3), rw, 2.6, m, rot=(math.pi / 2, 0, 0))
            plane("shop_floor", (cx, 0.36 + d / 2, 0.0), rw, d, M_CONC_D); plane("shop_ceil", (cx, 0.36 + d / 2, 2.6), rw, d, M_CONC_D)
            plane("shop_sL", (cx - rw / 2, 0.36 + d / 2, 1.3), 2.6, d, M_CONC_D, rot=(0, math.pi / 2, 0)); plane("shop_sR", (cx + rw / 2, 0.36 + d / 2, 1.3), 2.6, d, M_CONC_D, rot=(0, math.pi / 2, 0))
            for k in range(3): plane("shop_lamp%d" % k, (cx - 0.5 + 0.5 * k, 0.36 + 1.2, 2.3), 0.12, 0.3, M_SHOP)
            person("cook", "shop_p", cx, 0.36, 0.0, seed=5)
            lt = bpy.data.lights.new("shop_lt", 'POINT'); lt.energy = 180; lt.color = (1.0, 0.62, 0.32); lt.shadow_soft_size = 0.5; lt.use_shadow = False
            lo = bpy.data.objects.new("shop_lt", lt); bpy.context.collection.objects.link(lo); lo.location = (cx, 1.3, 2.2)
        else:
            box("shutter%s%d" % (side, bay), (cx - w / 2, 0.08, 0.0), (cx + w / 2, 0.30, 2.3), M_SHUTTER)
            for k in range(14):   # 波板の筋
                z = 0.1 + k * 0.155; box("shut%s%d_%d" % (side, bay, k), (cx - w / 2, 0.05, z), (cx + w / 2, 0.09, z + 0.05), M_SHUTTER)
# 跳ね先の台
LEDGE_OBJS = {}
def build_ledge(L):
    i = L["i"]; typ = L["type"]; x, z = L["x"], L["z"]
    objs = []
    if typ == "ac":
        b = L["parts"][0]; o = box("ledge%02d_body" % i, b["lo"], b["hi"], M_METAL); objs.append(o)
        # 前面の格子（薄い帯）と、壁への腕
        for k in range(5):
            zz = b["lo"][2] + 0.08 + k * 0.09; objs.append(box("ledge%02d_gr%d" % (i, k), (b["lo"][0] + 0.05, b["lo"][1] - 0.01, zz), (b["hi"][0] - 0.05, b["lo"][1] + 0.01, zz + 0.03), M_METAL_R))
        for sg in (-1, 1):
            objs.append(cyl("ledge%02d_arm%d" % (i, sg), (x + sg * 0.32, -0.02, b["lo"][2] - 0.05), (x + sg * 0.32, b["lo"][1] + 0.05, b["lo"][2] + 0.02), 0.02, M_PIPE))
        objs.append(cyl("ledge%02d_fan" % i, (x, b["lo"][1] + 0.1, (b["lo"][2] + b["hi"][2]) / 2), (x, b["lo"][1] - 0.005, (b["lo"][2] + b["hi"][2]) / 2), 0.17, M_SIL, 20))
    elif typ == "sign":
        b = L["parts"][0]; o = box("ledge%02d_body" % i, b["lo"], b["hi"], M_METAL_R); objs.append(o)
        tex = rnd.choice([t for t in ["sign_a", "sign_b", "sign_c", "sign_d", "sign_e", "sign_f", "sign_g", "sign_h"] if open(os.path.join(SOZAI, t + ".txt")).read().strip() == "horizontal"])
        m, st = mat_neon("neon_l%02d" % i, tex + ".png")
        face = plane("ledge%02d_face" % i, ((b["lo"][0] + b["hi"][0]) / 2, b["lo"][1] - 0.005, (b["lo"][2] + b["hi"][2]) / 2), b["hi"][0] - b["lo"][0] - 0.06, b["hi"][2] - b["lo"][2] - 0.06, m, rot=(math.pi / 2, 0, 0))
        objs.append(face)
        if rnd.random() < 0.4:   # 切れかけのネオン
            for ff in range(1, NF + 1, 3):
                st.default_value = 6.0 if rnd.random() > 0.15 else 1.0; st.keyframe_insert("default_value", frame=ff)
        for sg in (-1, 1):
            objs.append(cyl("ledge%02d_arm%d" % (i, sg), (x + sg * 0.5, -0.02, b["hi"][2] + 0.35), (x + sg * 0.5, b["hi"][1] - 0.03, b["hi"][2] - 0.02), 0.015, M_PIPE))
        lt = bpy.data.lights.new("ledge%02d_lt" % i, 'POINT'); lt.energy = 25; lt.color = (1.0, 0.5, 0.6); lt.use_shadow = False; lt.shadow_soft_size = 0.4
        lo = bpy.data.objects.new("ledge%02d_lt" % i, lt); bpy.context.collection.objects.link(lo); lo.location = (x, b["lo"][1] - 0.3, (b["lo"][2] + b["hi"][2]) / 2)
    elif typ == "balcony":
        for b in L["parts"]:
            objs.append(box(b["name"], b["lo"], b["hi"], M_CONC))
        # 柵の上の手すり・植木鉢・ほうき
        b = L["parts"][0]
        objs.append(box("ledge%02d_pot" % i, (b["hi"][0] - 0.3, -0.95, z), (b["hi"][0] - 0.1, -0.75, z + 0.22), M_METAL_R))
    elif typ == "awning":
        b = L["parts"][0]; o = box("ledge%02d_body" % i, b["lo"], b["hi"], M_METAL_R); objs.append(o)
        for k in range(6):
            xx = b["lo"][0] + 0.1 + k * (b["hi"][0] - b["lo"][0] - 0.2) / 5
            objs.append(box("ledge%02d_rib%d" % (i, k), (xx - 0.015, b["lo"][1], b["hi"][2]), (xx + 0.015, b["hi"][1], b["hi"][2] + 0.03), M_METAL_R))
        for sg in (-1, 1):
            objs.append(cyl("ledge%02d_arm%d" % (i, sg), (x + sg * 0.5, -0.02, z + 0.45), (x + sg * 0.5, b["lo"][1] + 0.05, z), 0.015, M_PIPE))
    else:   # pole
        b = L["parts"][0]
        objs.append(cyl("ledge%02d_body" % i, (b["lo"][0], -0.55, z - 0.02), (b["hi"][0], -0.55, z - 0.02), 0.022, M_PIPE))
        for sg in (-1, 1):
            objs.append(cyl("ledge%02d_arm%d" % (i, sg), (x + sg * 0.68, -0.02, z - 0.02), (x + sg * 0.68, -0.56, z - 0.02), 0.012, M_PIPE))
        for b2 in L["parts"][1:]:
            objs.append(plane(b2["name"], ((b2["lo"][0] + b2["hi"][0]) / 2, -0.55, (b2["lo"][2] + b2["hi"][2]) / 2), b2["hi"][0] - b2["lo"][0], b2["hi"][2] - b2["lo"][2], M_CLOTH[rnd.randint(0, 5)], rot=(math.pi / 2, 0, 0)))
    # 台が沈む（着地の重みで）
    for o in objs:
        base = o.location.z
        for fk, dz in sorted(L["dz"].items(), key=lambda kv: int(kv[0])):
            o.location.z = base + dz; o.keyframe_insert("location", frame=int(fk))
        anim_lin(o)
    LEDGE_OBJS[i] = objs
for L in M["ledges"]: build_ledge(L)
# 飾り：室外機・竿と布
for k, d in enumerate(M["deco"]):
    b = d["box"]
    if d["type"] == "ac":
        box(b["name"], b["lo"], b["hi"], M_METAL)
        for j in range(5):
            zz = b["lo"][2] + 0.06 + j * 0.09; box(b["name"] + "_g%d" % j, (b["lo"][0] + 0.05, b["lo"][1] - 0.01, zz), (b["hi"][0] - 0.05, b["lo"][1] + 0.01, zz + 0.03), M_METAL_R)
    else:
        xm = (b["lo"][0] + b["hi"][0]) / 2; zt = b["hi"][2]
        cyl(b["name"], (b["lo"][0], -0.55, zt - 0.02), (b["hi"][0], -0.55, zt - 0.02), 0.018, M_PIPE)
        for j in range(d["n"]):
            xx = b["lo"][0] + 0.25 + j * (b["hi"][0] - b["lo"][0] - 0.5) / max(1, d["n"] - 1)
            plane(b["name"] + "_c%d" % j, (xx, -0.55, zt - 0.45), 0.3, 0.7, M_CLOTH[rnd.randint(0, 5)], rot=(math.pi / 2, 0, 0))
# 配管（縦）
for k, pp in enumerate(M["pipes"]):
    cyl("pipe%d" % k, (pp["x"], -pp["r"] - 0.01, pp["z0"]), (pp["x"], -pp["r"] - 0.01, pp["z1"]), pp["r"], M_PIPE)
    for j in range(int(pp["z1"] // 3.5)):
        box("pipe%d_b%d" % (k, j), (pp["x"] - pp["r"] - 0.03, -pp["r"] * 2 - 0.03, 3.5 * j + 1.0), (pp["x"] + pp["r"] + 0.03, 0.0, 3.5 * j + 1.06), M_METAL_R)
# 側壁（手前・左右）と、通りへ張り出す看板
for sgn, nm in ((-1, "L"), (1, "R")):
    box("side_%s" % nm, (min(sgn * 6.5, sgn * 7.5), -14.0, 0), (max(sgn * 6.5, sgn * 7.5), 0.0, TOP + 2), M_TILE_S)
    for fl in range(NFLOOR):
        for yy in (-2.5, -5.5, -8.5, -11.5):
            z0 = fl * FLOOR_H + SILL
            r = rnd.random()
            m = M_DIM if r < 0.12 else (M_TV if r < 0.17 else M_GLASS)
            plane("sw_%s%d_%d" % (nm, fl, int(-yy)), (sgn * 6.49, yy, z0 + WIN_H / 2), WIN_H, 0.9, m, rot=(0, math.pi / 2, 0))
for k, s in enumerate(M["signs"]):
    sgn = s["side"]; x0 = s["x0"]; w = s["w"]; y = s["y"]; z = s["z"]; h = s["h"]
    if open(os.path.join(SOZAI, s["tex"] + ".txt")).read().strip() == "vertical": w, h = 0.55, 2.1
    lo = (min(x0, x0 - sgn * w), y - s["d"] / 2, z); hi = (max(x0, x0 - sgn * w), y + s["d"] / 2, z + h)
    box("sign%d" % k, lo, hi, M_METAL_R)
    m, st = mat_neon("neon_s%d" % k, s["tex"] + ".png")
    if not s["on"]: st.default_value = 0.4
    elif rnd.random() < 0.3:
        for ff in range(1, NF + 1, 4): st.default_value = 6.0 if rnd.random() > 0.2 else 0.8; st.keyframe_insert("default_value", frame=ff)
    for sy in (-1, 1):
        plane("sign%d_f%d" % (k, sy), ((lo[0] + hi[0]) / 2, y + sy * (s["d"] / 2 + 0.005), z + h / 2), w - 0.05, h - 0.05, m, rot=(math.pi / 2, 0, 0))
    cyl("sign%d_arm" % k, (x0, y, z + h + 0.4), (x0 - sgn * w * 0.9, y, z + h), 0.015, M_PIPE)
    if s["on"]:
        lt = bpy.data.lights.new("sign%d_lt" % k, 'POINT'); lt.energy = 60; lt.color = (1.0, 0.6, 0.7); lt.use_shadow = False; lt.shadow_soft_size = 0.5
        lo_ = bpy.data.objects.new("sign%d_lt" % k, lt); bpy.context.collection.objects.link(lo_); lo_.location = ((lo[0] + hi[0]) / 2, y, z + h / 2)
# 路地：向かい合う壁の窓（薄明かり）・ケーブル・奥の床
for sgn, nm in ((-1, "L"), (1, "R")):
    for fl in range(NFLOOR):
        for yy in (1.6, 3.4, 5.2):
            z0 = fl * FLOOR_H + SILL; r = rnd.random()
            m = M_DIM if r < 0.18 else (M_TV if r < 0.23 else M_GLASS)
            plane("aw_%s%d_%d" % (nm, fl, int(yy * 10)), (sgn * (ALLEY - 0.01), yy, z0 + WIN_H / 2), WIN_H, 0.8, m, rot=(0, math.pi / 2, 0))
for k, c in enumerate(M["cables"]):
    # たるんだケーブル（曲線を折れ線で）
    pts = []
    for j in range(13):
        u = j / 12; x = -ALLEY + 2 * ALLEY * u; pts.append((x, c["y"], c["z"] - c["sag"] * 4 * u * (1 - u)))
    for j in range(12): cyl("cable%d_%d" % (k, j), pts[j], pts[j + 1], 0.012, M_SIL, 6)
# 遠くの街（路地の奥）：窓の点々＋霞
M_FAR, _ = mat_emit("far", (1, 1, 1), 1.0)
ntf = M_FAR.node_tree; pf = ntf.nodes["Principled BSDF"]
texf = node(ntf, "ShaderNodeTexImage"); texf.image = load_img("far_windows.png"); texf.extension = 'REPEAT'
tcf = node(ntf, "ShaderNodeTexCoord"); mpf = node(ntf, "ShaderNodeMapping"); I(mpf, "Scale").default_value = (1.2, 1.2, 1.2)
link(ntf, tcf.outputs["Object"], I(mpf, "Vector")); link(ntf, mpf.outputs[0], I(texf, "Vector")); link(ntf, texf.outputs["Color"], I(pf, "Emission Color"))
pin(pf, "Emission Strength", 0.9); pin(pf, "Base Color", (0.06, 0.07, 0.10, 1))
for k, f_ in enumerate(M["far"]):
    box("far%d" % k, (f_["x"] - f_["w"] / 2, f_["y"], 0), (f_["x"] + f_["w"] / 2, f_["y"] + f_["d"], f_["h"]), M_FAR)
# 港の水（塔の裏・月を映す）
mw_, ntw, pw = newmat("water")
pin(pw, "Base Color", (0.003, 0.005, 0.010, 1)); pin(pw, "Roughness", 0.03); pin(pw, "Specular IOR Level", 0.6); pin(pw, "Metallic", 0.0)
nzw = node(ntw, "ShaderNodeTexNoise"); I(nzw, "Scale").default_value = 2.5; I(nzw, "Detail").default_value = 6
mpw2 = node(ntw, "ShaderNodeMapping"); tcw2 = node(ntw, "ShaderNodeTexCoord"); link(ntw, tcw2.outputs["Object"], I(mpw2, "Vector")); link(ntw, mpw2.outputs[0], I(nzw, "Vector"))
low_ = I(mpw2, "Location"); low_.default_value = (0, 0, 0); low_.keyframe_insert("default_value", frame=1); low_.default_value = (0, 3.0, 1.5); low_.keyframe_insert("default_value", frame=NF)
bpw = node(ntw, "ShaderNodeBump"); I(bpw, "Strength").default_value = 0.35; link(ntw, O(nzw, "Fac"), I(bpw, "Height")); link(ntw, bpw.outputs[0], I(pw, "Normal"))
anim_lin(ntw)
plane("water", (0, 300, -0.15), 800, 600, mw_)
box("quay", (-8, 6.35, -0.2), (8, 7.0, 0.05), M_CONC_D)
for k in range(9): cyl("quay_post%d" % k, (-7.5 + 1.9 * k, 6.9, 0.0), (-7.5 + 1.9 * k, 6.9, 0.95), 0.03, M_PIPE, 6)
for k in range(8): cyl("quay_rail%d" % k, (-7.5 + 1.9 * k, 6.9, 0.93), (-5.6 + 1.9 * k, 6.9, 0.93), 0.02, M_PIPE, 6)
# 地面（通り＋すき間の床）
plane("ground", (0, -3.75, 0), 30, 20.5, M_STREET)
# 通りのゴミ袋・段ボール（手前の下の方）
for k in range(7):
    x = rnd.choice([-1, 1]) * rnd.uniform(2.9, 3.4); y = rnd.uniform(-6, -1.5)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1, location=(x, y, 0.22)); o = bpy.context.object; o.name = "bag%d" % k; o.scale = (0.3, 0.28, 0.22); o.data.materials.append(M_SIL)
# 屋上：給水タンク・アンテナ（路地の真上は空けておく）
for sgn in (-1, 1):
    cyl("tank%d" % sgn, (sgn * 4.0, 3.0, TOP + 0.2), (sgn * 4.0, 3.0, TOP + 1.8), 0.7, M_METAL_R, 16)
    for k in range(3):
        cyl("ant%d_%d" % (sgn, k), (sgn * (2.0 + k * 0.9), 1.5 + k, TOP + 0.2), (sgn * (2.0 + k * 0.9), 1.5 + k, TOP + 2.2 + k * 0.6), 0.02, M_PIPE, 6)
stage("city_done")

# =====================================================================
# 宇宙うんこ（自前の形：ソフトクリーム型のうずまき。たまご工場 v1/v2 の作り方）＋銀河の質感（手描き絵は使わない）
# =====================================================================
stage("unko")
cu = bpy.data.curves.new("swirl", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.0; cu.bevel_resolution = 8; cu.use_fill_caps = True
sp = cu.splines.new('NURBS'); NPT = 110; sp.points.add(NPT - 1); sp.use_endpoint_u = True; sp.order_u = 4
for j in range(NPT):
    u = j / (NPT - 1); a_ = 2 * math.pi * 2.6 * u
    R_ = 0.50 * (1 - u) ** 0.8 + 0.012; z = 0.22 + 0.84 * u ** 0.92
    sp.points[j].co = (R_ * math.cos(a_), R_ * math.sin(a_), z, 1); sp.points[j].radius = 0.26 * (1 - u) ** 0.65 + 0.01
so = bpy.data.objects.new("swirl", cu); bpy.context.collection.objects.link(so)
bpy.ops.object.select_all(action='DESELECT'); so.select_set(True); bpy.context.view_layer.objects.active = so; bpy.ops.object.convert(target='MESH'); sw = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.64, location=(0, 0, 0.20)); base = bpy.context.object; base.scale = (1, 1, 0.42)
bpy.ops.object.select_all(action='DESELECT'); sw.select_set(True); base.select_set(True); bpy.context.view_layer.objects.active = sw; bpy.ops.object.join()
unko = bpy.context.object; unko.name = "unko"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
rm = unko.modifiers.new("r", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.014; bpy.ops.object.modifier_apply(modifier="r")
sm = unko.modifiers.new("s", 'SMOOTH'); sm.iterations = 10; sm.factor = 0.55; bpy.ops.object.modifier_apply(modifier="s")
for v in unko.data.vertices:
    if v.co.z < 0.02: v.co.z = 0.02
zmin = min(v.co.z for v in unko.data.vertices)
for v in unko.data.vertices: v.co.z -= zmin
hgt = max(v.co.z for v in unko.data.vertices); S0 = H_UNKO / hgt
for v in unko.data.vertices: v.co *= S0
bpy.ops.object.shade_smooth()
me = unko.data
print("UNKO_MESH verts", len(me.vertices), "h", round(max(v.co.z for v in me.vertices), 3), "r", round(max(math.hypot(v.co.x, v.co.y) for v in me.vertices), 3), flush=True)
# 銀河の肌：濃い紺〜紫の地に、星雲（マゼンタ・水色）、小さな星、つや
um, unt, up = newmat("unko_galaxy")
tcu = node(unt, "ShaderNodeTexCoord")
nzA = node(unt, "ShaderNodeTexNoise"); I(nzA, "Scale").default_value = 3.2; I(nzA, "Detail").default_value = 7; I(nzA, "Roughness").default_value = 0.62; link(unt, tcu.outputs["Object"], I(nzA, "Vector"))
nzB = node(unt, "ShaderNodeTexNoise"); I(nzB, "Scale").default_value = 7.0; I(nzB, "Detail").default_value = 5; link(unt, tcu.outputs["Object"], I(nzB, "Vector"))
rpA = node(unt, "ShaderNodeValToRGB"); cr = rpA.color_ramp
cr.elements[0].position = 0.30; cr.elements[0].color = (0.02, 0.01, 0.08, 1)
cr.elements[1].position = 0.60; cr.elements[1].color = (0.75, 0.12, 0.70, 1)
e2 = cr.elements.new(0.76); e2.color = (0.20, 0.75, 1.0, 1)
e3 = cr.elements.new(0.46); e3.color = (0.12, 0.05, 0.32, 1)
link(unt, O(nzA, "Fac"), I(rpA, "Fac"))
vor = node(unt, "ShaderNodeTexVoronoi"); I(vor, "Scale").default_value = 75; link(unt, tcu.outputs["Object"], I(vor, "Vector"))
stars = math_(unt, 'LESS_THAN', O(vor, "Distance"), vb=0.085)
starsB = math_(unt, 'MULTIPLY', math_(unt, 'LESS_THAN', O(nzB, "Fac"), vb=0.42), stars)
mixc = node(unt, "ShaderNodeMixRGB"); mixc.blend_type = 'ADD'; mixc.inputs[0].default_value = 1.0
link(unt, rpA.outputs["Color"], mixc.inputs[1]); link(unt, stars, mixc.inputs[2])
link(unt, mixc.outputs[0], I(up, "Base Color"))
lw = node(unt, "ShaderNodeLayerWeight"); I(lw, "Blend").default_value = 0.25
rim = node(unt, "ShaderNodeMixRGB"); rim.blend_type = 'ADD'; link(unt, lw.outputs["Facing"], rim.inputs[0])
rim.inputs[1].default_value = (0, 0, 0, 1); rim.inputs[2].default_value = (0.35, 0.25, 0.6, 1)
emc = node(unt, "ShaderNodeMixRGB"); emc.blend_type = 'ADD'; emc.inputs[0].default_value = 1.0
link(unt, rim.outputs[0], emc.inputs[1]); link(unt, stars, emc.inputs[2])
link(unt, emc.outputs[0], I(up, "Emission Color")); pin(up, "Emission Strength", 0.9)
pin(up, "Roughness", 0.16); pin(up, "Coat Weight", 1.0); pin(up, "Coat Roughness", 0.04); pin(up, "Specular IOR Level", 0.7)
pin(up, "Subsurface Weight", 0.12); pin(up, "Subsurface Radius", (0.6, 0.3, 0.9))
try: I(up, "Subsurface Color").default_value = (0.5, 0.2, 0.7, 1)
except Exception: pass
bpu = node(unt, "ShaderNodeBump"); I(bpu, "Strength").default_value = 0.08; link(unt, O(nzB, "Fac"), I(bpu, "Height")); link(unt, bpu.outputs[0], I(up, "Normal"))
tryset(um, use_sss_translucency=True)
me.materials.append(um)
UNKO_EM = I(up, "Emission Strength")
# ぷるぷる（シェイプキー）
unko.shape_key_add(name="Basis")
def key(name, fn):
    kb = unko.shape_key_add(name=name, from_mix=False); kb.slider_min = -1.0; kb.slider_max = 1.5
    for i, v in enumerate(me.vertices): kb.data[i].co = fn(v.co.copy())
    return kb
def tsubure(c):
    h = c.z / H_UNKO; k = 1.12 * (1 + 0.05 * math.sin(math.pi * min(1, h * 1.6))); return V((c.x * k, c.y * k, c.z * 0.80))
def nobi(c): return V((c.x * 0.94, c.y * 0.94, c.z * 1.12))
def yure(axis):
    def f(c):
        h = c.z / H_UNKO; d = 0.30 * H_UNKO * h * h
        return V((c.x + d, c.y, c.z)) if axis == 0 else V((c.x, c.y + d, c.z))
    return f
KB = {"tsubure": key("tsubure", tsubure), "nobi": key("nobi", nobi), "yureX": key("yureX", yure(0)), "yureY": key("yureY", yure(1))}
unko.location = (0, 0, 0)
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
for fl in M["flashes"]:
    for ff, vv in ((fl["fr"] - 1, 0.9), (fl["fr"], 3.0), (fl["fr"] + 10, 0.9)):
        UNKO_EM.default_value = vv; UNKO_EM.keyframe_insert("default_value", frame=ff)

# =====================================================================
# 当たりの光：閃光（色は音の高さ）・広がる輪・飛び散る粒・部屋が灯る
# =====================================================================
stage("flash")
import colorsys
def hue_col(h, s=0.55, v=1.0): return colorsys.hsv_to_rgb(h, s, v)
RING_MATS = []
def ring_mat(col):
    m, nt, p = newmat("ring"); blend(m, 'BLEND')
    tc = node(nt, "ShaderNodeTexCoord"); sep = node(nt, "ShaderNodeSeparateXYZ"); link(nt, tc.outputs["Generated"], sep.inputs[0])
    dx = math_(nt, 'SUBTRACT', sep.outputs["X"], vb=0.5); dy = math_(nt, 'SUBTRACT', sep.outputs["Y"], vb=0.5)
    r = math_(nt, 'MULTIPLY', math_(nt, 'SQRT', math_(nt, 'ADD', math_(nt, 'MULTIPLY', dx, dx), math_(nt, 'MULTIPLY', dy, dy))), vb=2.0)
    band = math_(nt, 'EXPONENT', math_(nt, 'MULTIPLY', math_(nt, 'POWER', math_(nt, 'SUBTRACT', r, vb=0.82), vb=2.0), vb=-90.0))
    # 粒で消える：ノイズでちぎれる
    nz = node(nt, "ShaderNodeTexNoise"); I(nz, "Scale").default_value = 14; link(nt, tc.outputs["Generated"], I(nz, "Vector"))
    frag = math_(nt, 'GREATER_THAN', O(nz, "Fac"), vb=0.0)
    al = math_(nt, 'MULTIPLY', band, frag)
    fade = node(nt, "ShaderNodeValue"); fade.name = "fade"; fade.outputs[0].default_value = 0.0
    thr = node(nt, "ShaderNodeValue"); thr.name = "thr"; thr.outputs[0].default_value = 0.0
    # しきい値が上がるほど、ノイズで欠けていく（ふわっと粒になって消える）
    frag2 = math_(nt, 'GREATER_THAN', O(nz, "Fac"), thr.outputs[0])
    al2 = math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', band, frag2), fade.outputs[0])
    link(nt, al2, I(p, "Alpha")); pin(p, "Base Color", (0, 0, 0, 1)); pin(p, "Emission Color", col + (1,)); pin(p, "Emission Strength", 1.6)
    return m, fade.outputs[0], thr.outputs[0]
M_SPARK, _ = mat_emit("spark", (1.0, 0.9, 0.7), 8.0); blend(M_SPARK, 'BLEND')
for k, fl in enumerate(M["flashes"]):
    f0 = fl["fr"]; col = hue_col(fl["hue"]) if fl["kind"] != "final" else (0.7, 0.85, 1.0)
    # 閃光
    lt = bpy.data.lights.new("flash%02d" % k, 'POINT'); lt.color = col; lt.shadow_soft_size = 0.35; lt.use_shadow = True; lt.energy = 0.0
    lo = bpy.data.objects.new("flash%02d" % k, lt); bpy.context.collection.objects.link(lo); lo.location = fl["p"]
    peak = 1400 if fl["kind"] in ("mel", "final") else (900 if fl["kind"] == "bass" else 650)
    for ff, vv in ((f0 - 1, 0.0), (f0, peak), (f0 + 2, peak * 0.7), (f0 + 10, peak * 0.12), (f0 + 26, 0.0)):
        lt.energy = vv; lt.keyframe_insert("energy", frame=ff)
    anim_lin(lt)
    for ff, vv in ((1, True), (f0 - 2, True), (f0 - 1, False), (f0 + 26, False), (f0 + 27, True)):   # 光っていない間は消す（影の計算を減らす）
        lo.hide_render = vv; lo.keyframe_insert("hide_render", frame=ff); lo.hide_viewport = vv; lo.keyframe_insert("hide_viewport", frame=ff)
    # 広がる輪（壁と平行の面。中心は着地点）
    m, fade, thr = ring_mat(col)
    rg = plane("ring%02d" % k, (fl["p"][0], -0.13, fl["p"][2] - 0.2), 1, 1, m, rot=(math.pi / 2, 0, 0)) if fl["kind"] != "final" else plane("ring%02d" % k, (fl["p"][0], fl["p"][1], 0.01), 1, 1, m)
    for ff, s_, fd, th in ((f0 - 1, 0.05, 0.0, 0.0), (f0, 0.2, 0.9, 0.0), (f0 + 8, 1.2, 0.6, 0.3), (f0 + 20, 2.0, 0.0, 0.75), (f0 + 21, 0.05, 0.0, 1.0)):
        rg.scale = (s_, s_, 1); rg.keyframe_insert("scale", frame=ff)
        fade.default_value = fd; fade.keyframe_insert("default_value", frame=ff)
        thr.default_value = th; thr.keyframe_insert("default_value", frame=ff)
    anim_lin(rg); anim_lin(m.node_tree)
    if fl["kind"] != "final":
        for ff, vv in ((1, True), (f0 - 2, True), (f0 - 1, False), (f0 + 21, False), (f0 + 22, True)):
            rg.hide_render = vv; rg.keyframe_insert("hide_render", frame=ff); rg.hide_viewport = vv; rg.keyframe_insert("hide_viewport", frame=ff)
    # 飛び散る粒（8個）：放物線で飛んで、小さくなって消える
    for j in range(8):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.014, location=fl["p"]); d = bpy.context.object; d.name = "spark%02d_%d" % (k, j); d.data.materials.append(M_SPARK)
        a2 = rnd.uniform(0, 2 * math.pi); spd = rnd.uniform(0.6, 1.6); upv = rnd.uniform(1.0, 2.4)
        p0 = V((fl["p"][0], fl["p"][1] - 0.1, fl["p"][2] - 0.25))
        for ff in range(f0 - 1, f0 + 22):
            t = (ff - f0) / FPS
            if t < 0: d.location = p0; d.scale = (0.001,) * 3
            else:
                d.location = p0 + V((math.cos(a2) * spd * t, -abs(math.sin(a2)) * spd * t * 0.6, upv * t - 4.0 * t * t))
                s_ = max(0.001, 1 - t / 0.85); d.scale = (s_, s_, s_)
            d.keyframe_insert("location", frame=ff); d.keyframe_insert("scale", frame=ff)
        for ff, vv in ((1, True), (f0 - 2, True), (f0 - 1, False), (f0 + 21, False), (f0 + 22, True)):
            d.hide_render = vv; d.keyframe_insert("hide_render", frame=ff); d.hide_viewport = vv; d.keyframe_insert("hide_viewport", frame=ff)
# 部屋が灯る：当たりで一気に明るく → 余韻で薄明かりのまま残る（＝浮かび上がった人は見え続ける）
for name, (strength, ons, r) in ROOM_ON.items():
    if strength is None: continue
    ev = [(1, 0.0)]
    cur = 0.0
    for f0 in sorted(ons):
        ev += [(f0 - 1, cur), (f0 + 2, 1.6), (f0 + 12, 1.1), (f0 + 40, 0.55), (f0 + 90, 0.38)]
        cur = 0.38
    ev.append((NF, cur))
    for ff, vv in ev:
        strength.default_value = vv; strength.keyframe_insert("default_value", frame=ff)
# 着水のしぶき（最後）
def spray(name, center, size, count, vmin, vmax, life, rad, mat, seed=0, grav=9.8):
    bpy.ops.mesh.primitive_plane_add(size=1, location=center); o = bpy.context.object; o.name = name; o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    try:
        ng.inputs.new('NodeSocketGeometry', 'Geometry'); ng.outputs.new('NodeSocketGeometry', 'Geometry')
    except Exception:
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry'); ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; Lk = ng.links.new
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces'); dist.inputs['Density'].default_value = count / max(0.01, size[0] * size[1]); dist.inputs['Seed'].default_value = seed
    Lk(gi.outputs[0], dist.inputs['Mesh'])
    tm = N.new('GeometryNodeInputSceneTime')
    def M_(op, a, b=None, vb=None):
        n = N.new('ShaderNodeMath'); n.operation = op; Lk(a, n.inputs[0])
        if b is not None: Lk(b, n.inputs[1])
        elif vb is not None: n.inputs[1].default_value = vb
        return n.outputs[0]
    tt = M_('MAXIMUM', M_('SUBTRACT', tm.outputs['Seconds'], vb=FINAL / FPS), vb=0.0)
    rv = N.new('FunctionNodeRandomValue'); rv.data_type = 'FLOAT_VECTOR'; rv.inputs[0].default_value = vmin; rv.inputs[1].default_value = vmax; rv.inputs['Seed'].default_value = seed + 23
    vt = N.new('ShaderNodeVectorMath'); vt.operation = 'SCALE'; Lk(rv.outputs[0], vt.inputs[0]); Lk(tt, vt.inputs['Scale'])
    gz = M_('MULTIPLY', M_('MULTIPLY', tt, tt), vb=-0.5 * grav)
    cz = N.new('ShaderNodeCombineXYZ'); Lk(gz, cz.inputs['Z'])
    off = N.new('ShaderNodeVectorMath'); off.operation = 'ADD'; Lk(vt.outputs[0], off.inputs[0]); Lk(cz.outputs[0], off.inputs[1])
    spn = N.new('GeometryNodeSetPosition'); Lk(dist.outputs['Points'], spn.inputs['Geometry']); Lk(off.outputs[0], spn.inputs['Offset'])
    ico = N.new('GeometryNodeMeshIcoSphere'); ico.inputs['Radius'].default_value = rad; ico.inputs['Subdivisions'].default_value = 1
    inst = N.new('GeometryNodeInstanceOnPoints'); Lk(spn.outputs['Geometry'], inst.inputs['Points']); Lk(ico.outputs['Mesh'], inst.inputs['Instance'])
    scl = M_('MAXIMUM', M_('SUBTRACT', M_('MULTIPLY', tt, vb=-1.0 / life), vb=-1.0), vb=0.0)
    Lk(scl, inst.inputs['Scale'])
    smt = N.new('GeometryNodeSetMaterial'); smt.inputs['Material'].default_value = mat; Lk(inst.outputs['Instances'], smt.inputs['Geometry'])
    Lk(smt.outputs['Geometry'], go.inputs[0])
    md = o.modifiers.new('gn', 'NODES'); md.node_group = ng
    return o
M_DROP, _ = mat_emit("drop", (0.85, 0.92, 1.0), 1.2); blend(M_DROP, 'BLEND')
ndrop = M_DROP.node_tree.nodes["Principled BSDF"]; pin(ndrop, "Alpha", 0.8); pin(ndrop, "Roughness", 0.1)
sp_ = spray("splash", (M["pond"][0], M["pond"][1], 0.03), (0.5, 0.5), 60, (-1.2, -1.2, 1.6), (1.2, 1.2, 3.2), 0.9, 0.02, M_DROP, seed=3)
for ff, vv in ((1, True), (FINAL - 1, True), (FINAL, False), (FINAL + 24, False), (FINAL + 25, True)):
    sp_.hide_render = vv; sp_.keyframe_insert("hide_render", frame=ff); sp_.hide_viewport = vv; sp_.keyframe_insert("hide_viewport", frame=ff)

# =====================================================================
# 空気：月（世界の背景）・月明かりの太陽・霧・漂う埃
# =====================================================================
stage("world")
w = sc.world or bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree
bg = wn.nodes.get("Background"); outw = [n for n in wn.nodes if n.type == 'OUTPUT_WORLD'][0]
tcw = node(wn, "ShaderNodeTexCoord"); sepw = node(wn, "ShaderNodeSeparateXYZ"); link(wn, tcw.outputs["Generated"], sepw.inputs[0])
el, az = math.radians(M["moon"][0]), math.radians(M["moon"][1])
md = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
# 月：方向との内積 → 円盤（やわらかい縁）＋大きなハロ
dotn = node(wn, "ShaderNodeVectorMath"); dotn.operation = 'DOT_PRODUCT'; link(wn, tcw.outputs["Generated"], dotn.inputs[0]); dotn.inputs[1].default_value = md
ang = math_(wn, 'ARCCOSINE', math_(wn, 'MINIMUM', O(dotn, "Value"), vb=1.0))
R_MOON = math.radians(4.8)
disc = node(wn, "ShaderNodeMapRange"); I(disc, "From Min").default_value = R_MOON - math.radians(0.2); I(disc, "From Max").default_value = R_MOON + math.radians(0.2)
I(disc, "To Min").default_value = 1.0; I(disc, "To Max").default_value = 0.0; link(wn, ang, I(disc, "Value"))
# 月の模様（海）
nzm = node(wn, "ShaderNodeTexNoise"); I(nzm, "Scale").default_value = 9.0; I(nzm, "Detail").default_value = 6; link(wn, tcw.outputs["Generated"], I(nzm, "Vector"))
mare = node(wn, "ShaderNodeMapRange"); I(mare, "From Min").default_value = 0.42; I(mare, "From Max").default_value = 0.6; I(mare, "To Min").default_value = 0.55; I(mare, "To Max").default_value = 1.0
link(wn, O(nzm, "Fac"), I(mare, "Value"))
moon = math_(wn, 'MULTIPLY', math_(wn, 'MULTIPLY', disc.outputs[0], mare.outputs[0]), vb=7.0)
halo = math_(wn, 'MULTIPLY', math_(wn, 'EXPONENT', math_(wn, 'MULTIPLY', math_(wn, 'POWER', math_(wn, 'DIVIDE', ang, vb=math.radians(16.0)), vb=1.6), vb=-1.0)), vb=0.35)
# 空：下ほど街明かりで少し明るい紺、上は黒に近い
zmap = node(wn, "ShaderNodeMath"); zmap.operation = 'MULTIPLY_ADD'; zmap.inputs[1].default_value = 0.5; zmap.inputs[2].default_value = 0.5; link(wn, sepw.outputs["Z"], zmap.inputs[0])
rampB = node(wn, "ShaderNodeValToRGB"); rampB.color_ramp.elements[0].position = 0.45; rampB.color_ramp.elements[0].color = (0.035, 0.03, 0.06, 1)
rampB.color_ramp.elements[1].position = 0.85; rampB.color_ramp.elements[1].color = (0.003, 0.004, 0.012, 1); link(wn, zmap.outputs[0], I(rampB, "Fac"))
vorw = node(wn, "ShaderNodeTexVoronoi"); I(vorw, "Scale").default_value = 160; link(wn, tcw.outputs["Generated"], I(vorw, "Vector"))
starsw = math_(wn, 'MULTIPLY', math_(wn, 'LESS_THAN', O(vorw, "Distance"), vb=0.03), vb=1.5)
mcol = node(wn, "ShaderNodeMixRGB"); mcol.blend_type = 'ADD'; mcol.inputs[0].default_value = 1.0
tot = math_(wn, 'ADD', math_(wn, 'ADD', moon, halo), starsw)
moonc = node(wn, "ShaderNodeMixRGB"); moonc.blend_type = 'MULTIPLY'; moonc.inputs[0].default_value = 1.0; moonc.inputs[2].default_value = (1.0, 0.93, 0.78, 1)
link(wn, tot, moonc.inputs[1])
link(wn, rampB.outputs["Color"], mcol.inputs[1]); link(wn, moonc.outputs[0], mcol.inputs[2])
link(wn, mcol.outputs["Color"], I(bg, "Color")); I(bg, "Strength").default_value = 1.0
# 霧（世界の体積）：薄く、街の底ほど濃い
vol = node(wn, "ShaderNodeVolumePrincipled"); I(vol, "Color").default_value = (0.55, 0.62, 0.75, 1); I(vol, "Anisotropy").default_value = 0.45
I(vol, "Density").default_value = 0.005
link(wn, vol.outputs[0], I(outw, "Volume"))
# 月明かり（太陽ランプ・青白い・路地を抜けて差す）
sun_d = bpy.data.lights.new("moon_sun", 'SUN'); sun_d.energy = 1.3; sun_d.color = (0.75, 0.82, 1.0); sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("moon_sun", sun_d); bpy.context.collection.objects.link(sun)
sun.rotation_euler = (-V(md)).to_track_quat('-Z', 'Y').to_euler()
# 街全体の薄い環境光（ネオンの照り返し）
amb_d = bpy.data.lights.new("amb", 'SUN'); amb_d.energy = 0.10; amb_d.color = (1.0, 0.75, 0.6); amb_d.angle = math.radians(40); amb_d.use_shadow = False
amb = bpy.data.objects.new("amb", amb_d); bpy.context.collection.objects.link(amb); amb.rotation_euler = (math.radians(60), 0, math.radians(180))
# 街明かりの照り返し（カメラ側の斜め上から・青灰色・影あり＝台の影が壁に落ちる）
key_d = bpy.data.lights.new("city_key", 'SUN'); key_d.energy = 0.45; key_d.color = (0.72, 0.78, 0.95); key_d.angle = math.radians(6)
keyo = bpy.data.objects.new("city_key", key_d); bpy.context.collection.objects.link(keyo)
kd = V((math.sin(math.radians(-35)) * math.cos(math.radians(28)), math.cos(math.radians(-35)) * math.cos(math.radians(28)), -math.sin(math.radians(28))))   # 光の進む向き（カメラ側から壁へ）
keyo.rotation_euler = kd.to_track_quat('-Z', 'Y').to_euler()
# 漂う埃（小さな光る粒・ゆっくり）
M_DUST, _ = mat_emit("dust", (1.0, 0.95, 0.85), 2.0); blend(M_DUST, 'BLEND'); pin(M_DUST.node_tree.nodes["Principled BSDF"], "Alpha", 0.6)
for k in range(140):
    x = rnd.uniform(-3.3, 3.3); y = rnd.uniform(-6.5, -0.3); z = rnd.uniform(0.2, TOP + 6)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rnd.uniform(0.006, 0.012), location=(x, y, z)); d = bpy.context.object; d.name = "dust%d" % k; d.data.materials.append(M_DUST)
    for ff in (1, NF):
        t = (ff - 1) / FPS; d.location = (x + 0.25 * math.sin(k + t * 0.3), y + 0.15 * math.cos(k * 0.7 + t * 0.25), z - 0.12 * t + 0.1 * math.sin(k + t * 0.5)); d.keyframe_insert("location", frame=ff)
    anim_lin(d)

# =====================================================================
# 動かないものは材質ごとに1つにまとめる（描画の呼び出しを減らす。当たり検査は static_* をまとめて見る）
# =====================================================================
stage("merge")
groups = {}
for o in list(bpy.data.objects):
    if o.type != 'MESH' or o.animation_data is not None or o.parent is not None: continue
    if o.name in ("unko", "ground") or o.name.startswith(("ring", "spark", "splash", "dust", "ledge")): continue
    key_ = o.data.materials[0].name if o.data.materials else "none"
    groups.setdefault(key_, []).append(o)
for key_, objs in groups.items():
    if len(objs) < 2: continue
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join()
    bpy.context.object.name = "static_" + key_
print("MERGED", len(groups), "groups ->", len([o for o in bpy.data.objects if o.type == 'MESH']), "meshes", flush=True)

# =====================================================================
# カメラ（michi.json の位置・見る先・レンズ）
# =====================================================================
stage("camera")
cam_d = bpy.data.cameras.new("C"); cam_d.clip_start = 0.05; cam_d.clip_end = 400; cam_d.sensor_fit = 'AUTO'
cam = bpy.data.objects.new("Cam", cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
cam.rotation_mode = 'QUATERNION'; prevq = None
for f, fr in enumerate(FRM, start=1):
    c = V(fr["cam"]); l = V(fr["look"]); fwd = (l - c).normalized()
    q = fwd.to_track_quat('-Z', 'Y'); q = q @ Quaternion((0, 0, 1), fr["roll"])
    if prevq is not None and prevq.dot(q) < 0: q.negate()
    prevq = q
    cam.location = c; cam.keyframe_insert("location", frame=f)
    cam.rotation_quaternion = q; cam.keyframe_insert("rotation_quaternion", frame=f)
    cam_d.lens = fr["lens"]; cam_d.keyframe_insert("lens", frame=f)
anim_lin(cam); anim_lin(cam_d)
# レンズの前の雨粒（薄い・少し）は入れない（忙しくなる）。
if os.environ.get("UU_SAVE"): bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "_scene.blend"))
stage("ready")
os.makedirs(OUT, exist_ok=True)
if FR == "none": print("DONE build-only", flush=True); sys.exit(0)

def kensa():
    """Blender の中で、本物の形どうしで当たりを確かめる（うんこの変形後のメッシュ × 台・飾り・看板・壁・配管）。
    1コマを4つに割って、三角形どうしが交わる組があるかを BVH で調べる。自分の台に乗っている間（着地〜出発）は、台の上面より下に沈んでいないかで見る。"""
    import bmesh
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    pre = ("ledge", "deco", "sign", "pipe", "pier", "band", "slab", "tower", "side_", "shutter", "cable", "parapet", "ground", "bag", "swf", "w", "static_")
    names = [o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(pre) and o.name != "unko" and not o.name.startswith(("ring", "spark", "splash", "dust"))]
    def bvh_of(o):
        ev = o.evaluated_get(dg); me_ = ev.to_mesh(); bm = bmesh.new(); bm.from_mesh(me_); bm.transform(ev.matrix_world)
        t = BVHTree.FromBMesh(bm); c = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts)); r = max(((v.co - c).length for v in bm.verts), default=0)
        bm.free(); ev.to_mesh_clear(); return t, c, r
    own = {}
    for L in M["ledges"]: own[L["i"]] = L
    bad = []; n_check = 0; t0 = time.time()
    bs = {}; cache = {}
    for n in names:
        o = bpy.data.objects[n]; pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        c = sum(pts, Vector()) / 8; bs[n] = (c, max((p - c).length for p in pts) + 0.1)
        if o.animation_data is None: cache[n] = bvh_of(o)
    for f in range(1, NF + 1):
        fr = FRM[f - 1]
        for sub in (0.0, 0.25, 0.5, 0.75):
            sc.frame_set(f, subframe=sub); dg = bpy.context.evaluated_depsgraph_get()
            tu, cu_, ru = bvh_of(unko)
            near = [n for n in names if (bs[n][0] - cu_).length < ru + bs[n][1] and not bpy.data.objects[n].hide_render]
            for n in near:
                o = bpy.data.objects[n]
                to, co, ro = cache[n] if n in cache else bvh_of(o)
                n_check += 1
                mine = None
                for L in M["ledges"]:
                    if n == "ledge%02d_body" % L["i"] and (L["fr"] - 3 <= f <= L["fr"] + DWELL + 3): mine = L
                if n == "ground" and f >= FINAL: mine = {"z": M["pond"][2] - 0.06}
                if mine is not None:
                    # 乗っている台：上面より 1cm 以上沈んでいたら、めり込み
                    if "dz" in mine:
                        a0 = mine["dz"].get(str(f), 0.0); a1 = mine["dz"].get(str(f + 1), a0 if str(f) in mine["dz"] else 0.0)
                        ks_ = sorted(int(k) for k in mine["dz"])
                        if not (ks_[0] <= f <= ks_[-1]): a0 = a1 = 0.0
                        top = mine["z"] + a0 + (a1 - a0) * sub
                    else: top = mine["z"]
                    ev = unko.evaluated_get(dg); me_ = ev.to_mesh(); mw = ev.matrix_world
                    pen = max((top - (mw @ v.co).z) for v in me_.vertices); ev.to_mesh_clear()
                    if pen > 0.012: bad.append({"f": f, "sub": sub, "obj": n, "st": fr["st"], "shizumi_m": round(pen, 4)})
                    continue
                if tu.overlap(to): bad.append({"f": f, "sub": sub, "obj": n, "st": fr["st"]})
        if f % 100 == 0: print("KENSA", f, len(bad), round(time.time() - t0), flush=True)
    res = {"koma": NF, "kizami": 4, "shirabeta_kumi": n_check, "meri_komi": len(bad), "rei": bad[:40]}
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
