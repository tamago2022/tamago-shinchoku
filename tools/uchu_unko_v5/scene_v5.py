# 宇宙うんこ v5（廃墟モール × 沈める寺）：Blender 3.6 EEVEE。michi.json から、モールの形・質感・光・グミ・波紋の色戻し・人影を作って連番を描く。
# 型は v4 の scene_v4.py（from_pydata の箱・ノードの材質・シェイプキー・連番描画）の写し。舞台と材質だけ差し替え。
# 使い方: blender -b -P scene_v5.py -- <フォルダ(michi.json)> <出力> <コマ指定: all | 1-100 | 1,60,300>
import bpy, bmesh, json, math, os, sys, time, random
from mathutils import Vector, Matrix, Euler
T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
W = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
OUT = argv[1] if len(argv) > 1 else os.path.join(W, "frames")
FR = argv[2] if len(argv) > 2 else "1"
os.makedirs(OUT, exist_ok=True)
M = json.load(open(os.path.join(W, "michi.json")))
FPS = M["fps"]; NF = M["nf"]; FRM = M["frames"]; H = M["H"]; NFLOOR = M["nfloor"]; VOID = M["void"]; RING = M["ring"]; ISLAND = M["island"]; CONC = M["conc"]
ROOF = M["roof"]; TRUSS = M["truss"]; RAIL_H = M["rail_h"]; H_UNKO = M["h_unko"]; FINAL = M["final_fr"]
def stage(x): print("STAGE", x, round(time.time() - T0, 1), flush=True)
def I(node, key):
    for s in node.inputs:
        if s.name == key or s.identifier == key: return s
    raise KeyError(key)
def O(node, key):
    for s in node.outputs:
        if s.name == key or s.identifier == key: return s
    raise KeyError(key)
def tryset(obj, **kw):
    for k, v in kw.items():
        try: setattr(obj, k, v)
        except Exception as e: print("skip", k, e)
rnd = random.Random(7)

# ---------------- 場の初期化 ----------------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = e; break
    except Exception: pass
print("ENGINE", sc.render.engine, bpy.app.version_string, flush=True)
EV = sc.eevee
tryset(EV, taa_render_samples=int(os.environ.get("UU_SAMPLES", "16")), use_bloom=True, bloom_intensity=0.05, bloom_threshold=1.0, bloom_radius=6.5, bloom_knee=0.5,
       use_gtao=True, gtao_distance=2.0, gtao_factor=1.3, use_ssr=True, use_ssr_refraction=True, use_ssr_halfres=True, ssr_quality=0.6, ssr_thickness=0.3, ssr_max_roughness=0.6,
       use_soft_shadows=False, use_volumetric_shadows=True, use_volumetric_lights=True, volumetric_tile_size='16', volumetric_samples=32, volumetric_start=0.3, volumetric_end=140.0, volumetric_light_clamp=3.0,
       use_motion_blur=os.environ.get("UU_MB", "1") == "1", motion_blur_shutter=0.35, motion_blur_steps=1,
       shadow_cube_size='512', shadow_cascade_size='1024', use_shadow_high_bitdepth=False, sss_samples=4)
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.resolution_percentage = int(os.environ.get("UU_PCT", "100"))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = NF
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 93
try: sc.view_settings.view_transform = 'Filmic'; sc.view_settings.look = 'Medium High Contrast'
except Exception: pass
sc.view_settings.exposure = -0.45

# ---------------- ノードの道具 ----------------
def newmat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL': nt.nodes.remove(n)
    out = nt.nodes["Material Output"]; return m, nt, out
def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items(): setattr(n, k, v)
    return n
def link(nt, a, b): nt.links.new(a, b)
def val(nt, v): n = node(nt, "ShaderNodeValue"); n.outputs[0].default_value = v; return n.outputs[0]
def math_(nt, op, a, b=None, c=None, clamp=False):
    n = node(nt, "ShaderNodeMath", operation=op); n.use_clamp = bool(clamp)
    if c is not None:
        if hasattr(c, "links"): link(nt, c, n.inputs[2])
        else: n.inputs[2].default_value = c
    if hasattr(a, "default_value") or hasattr(a, "links"): link(nt, a, n.inputs[0])
    else: n.inputs[0].default_value = a
    if b is not None:
        if hasattr(b, "links"): link(nt, b, n.inputs[1])
        else: n.inputs[1].default_value = b
    return n.outputs[0]
def mixrgb(nt, fac, a, b, blend='MIX'):
    n = node(nt, "ShaderNodeMixRGB", blend_type=blend)
    if hasattr(fac, "links"): link(nt, fac, n.inputs[0])
    else: n.inputs[0].default_value = fac
    for s, src in ((n.inputs[1], a), (n.inputs[2], b)):
        if hasattr(src, "links"): link(nt, src, s)
        else: s.default_value = src
    return n.outputs[0]
def noise(nt, scale, detail=4.0, rough=0.55, coord=None, w=0.0):
    n = node(nt, "ShaderNodeTexNoise"); I(n, "Scale").default_value = scale; I(n, "Detail").default_value = detail; I(n, "Roughness").default_value = rough
    try: n.noise_dimensions = '4D'; I(n, "W").default_value = w
    except Exception: pass
    if coord is not None: link(nt, coord, I(n, "Vector"))
    return O(n, "Fac")
def voronoi(nt, scale, coord=None, feature='DISTANCE_TO_EDGE'):
    n = node(nt, "ShaderNodeTexVoronoi", feature=feature); I(n, "Scale").default_value = scale
    if coord is not None: link(nt, coord, I(n, "Vector"))
    return O(n, "Distance")
def ramp(nt, fac, stops):
    n = node(nt, "ShaderNodeValToRGB"); cr = n.color_ramp
    while len(cr.elements) > 1: cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]; cr.elements[0].color = stops[0][1]
    for p, c in stops[1:]: e = cr.elements.new(p); e.color = c
    link(nt, fac, n.inputs[0]); return n.outputs[0]
def geo(nt):
    g = node(nt, "ShaderNodeNewGeometry"); tc = node(nt, "ShaderNodeTexCoord"); return g, tc
def blend(m, mode='BLEND', shadow='HASHED'):
    try: m.blend_method = mode; m.shadow_method = shadow
    except Exception: pass

# ---------------- 波紋のノードグループ：世界座標 → 色の戻り具合（0..1）。4つの枠を毎コマ更新 ----------------
NSLOT = 4
RIP = bpy.data.node_groups.new("RIPPLE", "ShaderNodeTree")
RIP.inputs.new("NodeSocketVector", "P"); RIP.outputs.new("NodeSocketFloat", "mask"); RIP.outputs.new("NodeSocketFloat", "ring")
gi = RIP.nodes.new("NodeGroupInput"); go = RIP.nodes.new("NodeGroupOutput")
SLOT = []
mask_acc = None; ring_acc = None
for s in range(NSLOT):
    cx = RIP.nodes.new("ShaderNodeValue"); cy = RIP.nodes.new("ShaderNodeValue"); cz = RIP.nodes.new("ShaderNodeValue")
    r = RIP.nodes.new("ShaderNodeValue"); hold = RIP.nodes.new("ShaderNodeValue"); rmax = RIP.nodes.new("ShaderNodeValue"); amp = RIP.nodes.new("ShaderNodeValue")
    for n_, nm in ((cx, "cx"), (cy, "cy"), (cz, "cz"), (r, "r"), (hold, "hold"), (rmax, "rmax"), (amp, "amp")): n_.name = "s%d_%s" % (s, nm); n_.label = n_.name
    comb = RIP.nodes.new("ShaderNodeCombineXYZ")
    for k, n_ in enumerate((cx, cy, cz)): RIP.links.new(n_.outputs[0], comb.inputs[k])
    dist = RIP.nodes.new("ShaderNodeVectorMath"); dist.operation = 'DISTANCE'
    RIP.links.new(gi.outputs[0], dist.inputs[0]); RIP.links.new(comb.outputs[0], dist.inputs[1])
    d = dist.outputs["Value"]
    # 輪：exp(-((d - r)/w)^2)、w は r と共に少し太る
    sub_ = RIP.nodes.new("ShaderNodeMath"); sub_.operation = 'SUBTRACT'; RIP.links.new(d, sub_.inputs[0]); RIP.links.new(r.outputs[0], sub_.inputs[1])
    wdt = RIP.nodes.new("ShaderNodeMath"); wdt.operation = 'MULTIPLY_ADD'; RIP.links.new(r.outputs[0], wdt.inputs[0]); wdt.inputs[1].default_value = 0.12; wdt.inputs[2].default_value = 2.2
    dv = RIP.nodes.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; RIP.links.new(sub_.outputs[0], dv.inputs[0]); RIP.links.new(wdt.outputs[0], dv.inputs[1])
    sq = RIP.nodes.new("ShaderNodeMath"); sq.operation = 'MULTIPLY'; RIP.links.new(dv.outputs[0], sq.inputs[0]); RIP.links.new(dv.outputs[0], sq.inputs[1])
    neg = RIP.nodes.new("ShaderNodeMath"); neg.operation = 'MULTIPLY'; RIP.links.new(sq.outputs[0], neg.inputs[0]); neg.inputs[1].default_value = -1.0
    ex = RIP.nodes.new("ShaderNodeMath"); ex.operation = 'EXPONENT'; RIP.links.new(neg.outputs[0], ex.inputs[0])
    # 内側（通り過ぎた所）：1 - (r - d)/hold  （hold は長さ[m]）
    inner = RIP.nodes.new("ShaderNodeMath"); inner.operation = 'SUBTRACT'; RIP.links.new(r.outputs[0], inner.inputs[0]); RIP.links.new(d, inner.inputs[1])
    inn2 = RIP.nodes.new("ShaderNodeMath"); inn2.operation = 'DIVIDE'; RIP.links.new(inner.outputs[0], inn2.inputs[0]); RIP.links.new(hold.outputs[0], inn2.inputs[1])
    inn3 = RIP.nodes.new("ShaderNodeMath"); inn3.operation = 'SUBTRACT'; inn3.inputs[0].default_value = 1.0; RIP.links.new(inn2.outputs[0], inn3.inputs[1]); inn3.use_clamp = True
    gate = RIP.nodes.new("ShaderNodeMath"); gate.operation = 'LESS_THAN'; RIP.links.new(d, gate.inputs[0]); RIP.links.new(r.outputs[0], gate.inputs[1])
    inn4 = RIP.nodes.new("ShaderNodeMath"); inn4.operation = 'MULTIPLY'; RIP.links.new(inn3.outputs[0], inn4.inputs[0]); RIP.links.new(gate.outputs[0], inn4.inputs[1])
    # rmax より外は無し
    g2 = RIP.nodes.new("ShaderNodeMath"); g2.operation = 'LESS_THAN'; RIP.links.new(d, g2.inputs[0]); RIP.links.new(rmax.outputs[0], g2.inputs[1])
    mx = RIP.nodes.new("ShaderNodeMath"); mx.operation = 'MAXIMUM'; RIP.links.new(ex.outputs[0], mx.inputs[0]); RIP.links.new(inn4.outputs[0], mx.inputs[1])
    m2 = RIP.nodes.new("ShaderNodeMath"); m2.operation = 'MULTIPLY'; RIP.links.new(mx.outputs[0], m2.inputs[0]); RIP.links.new(g2.outputs[0], m2.inputs[1])
    m3 = RIP.nodes.new("ShaderNodeMath"); m3.operation = 'MULTIPLY'; RIP.links.new(m2.outputs[0], m3.inputs[0]); RIP.links.new(amp.outputs[0], m3.inputs[1])
    rg = RIP.nodes.new("ShaderNodeMath"); rg.operation = 'MULTIPLY'; RIP.links.new(ex.outputs[0], rg.inputs[0]); RIP.links.new(g2.outputs[0], rg.inputs[1])
    rg2 = RIP.nodes.new("ShaderNodeMath"); rg2.operation = 'MULTIPLY'; RIP.links.new(rg.outputs[0], rg2.inputs[0]); RIP.links.new(amp.outputs[0], rg2.inputs[1])
    if mask_acc is None: mask_acc = m3.outputs[0]; ring_acc = rg2.outputs[0]
    else:
        a1 = RIP.nodes.new("ShaderNodeMath"); a1.operation = 'MAXIMUM'; RIP.links.new(mask_acc, a1.inputs[0]); RIP.links.new(m3.outputs[0], a1.inputs[1]); mask_acc = a1.outputs[0]
        a2 = RIP.nodes.new("ShaderNodeMath"); a2.operation = 'MAXIMUM'; RIP.links.new(ring_acc, a2.inputs[0]); RIP.links.new(rg2.outputs[0], a2.inputs[1]); ring_acc = a2.outputs[0]
    SLOT.append({"cx": cx, "cy": cy, "cz": cz, "r": r, "hold": hold, "rmax": rmax, "amp": amp})
cl = RIP.nodes.new("ShaderNodeClamp"); RIP.links.new(mask_acc, cl.inputs[0]); RIP.links.new(cl.outputs[0], go.inputs[0])
cl2 = RIP.nodes.new("ShaderNodeClamp"); RIP.links.new(ring_acc, cl2.inputs[0]); RIP.links.new(cl2.outputs[0], go.inputs[1])
# 枠の値を毎コマ：その時点で生きている波紋（新しい順に4つ）
RIPPLES = M["ripples"]
def alive(f):
    out = []
    for rp in RIPPLES:
        t = (f - rp["fr"]) / FPS
        if t < 0: continue
        r = rp["speed"] * t
        hold_m = rp["speed"] * rp["hold"]
        if r - hold_m > rp["rmax"] + 2: continue    # 全部消えた
        out.append((rp, r, hold_m))
    out.sort(key=lambda x: -x[0]["fr"]); return out[:NSLOT]
for f in range(1, NF + 1):
    al = alive(f)
    for s in range(NSLOT):
        sl = SLOT[s]
        if s < len(al):
            rp, r, hold_m = al[s]; vals = {"cx": rp["p"][0], "cy": rp["p"][1], "cz": rp["p"][2], "r": r, "hold": max(0.5, hold_m), "rmax": rp["rmax"], "amp": min(1.0, 0.45 + 0.7 * rp["vel"])}
        else: vals = {"cx": 0, "cy": 0, "cz": -999, "r": 0, "hold": 1, "rmax": 0, "amp": 0}
        for k, v in vals.items():
            sl[k].outputs[0].default_value = v; sl[k].outputs[0].keyframe_insert("default_value", frame=f)
for fc in RIP.animation_data.action.fcurves:
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
stage("ripple group")
def add_ripple(nt):
    g = node(nt, "ShaderNodeGroup"); g.node_tree = RIP
    tc = node(nt, "ShaderNodeTexCoord"); link(nt, O(tc, "Object"), g.inputs[0])
    # Object 座標ではなく世界座標にするため、object を未指定＝自身の座標。ここでは Geometry の Position を使う
    gm = node(nt, "ShaderNodeNewGeometry"); link(nt, O(gm, "Position"), g.inputs[0])
    return g.outputs[0], g.outputs[1]

# ---------------- 材質 ----------------
def desat(nt, col_socket, mask, keep=0.06):
    """白黒基調：mask=0 で彩度 keep、mask=1 で元の色"""
    hs = node(nt, "ShaderNodeHueSaturation"); link(nt, col_socket, I(hs, "Color"))
    sat = math_(nt, 'MULTIPLY_ADD', mask, 1 - keep);
    # sat = mask*(1-keep)+keep
    sat2 = math_(nt, 'ADD', sat, keep); link(nt, sat2, I(hs, "Saturation"))
    return hs.outputs[0]
def finish(m, nt, out, bsdf): link(nt, bsdf.outputs[0], I(out, "Surface")); return m
def principled(nt): return node(nt, "ShaderNodeBsdfPrincipled")

def mat_concrete(name, col=(0.46, 0.45, 0.43), moss=0.5, wet=0.35, streak=0.8, tile=0.0):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); P = O(tc, "Object"); Pw = O(g, "Position")
    mask, ring = add_ripple(nt)
    base = (col[0], col[1], col[2], 1)
    mottle = noise(nt, 0.35, 5, 0.6, Pw); mot = mixrgb(nt, 0.55, base, (col[0] * 0.40, col[1] * 0.40, col[2] * 0.40, 1), 'MIX')
    mot = mixrgb(nt, mottle, (col[0] * 1.15, col[1] * 1.15, col[2] * 1.12, 1), mot)
    # 雨だれ：縦にのばしたノイズ（上から垂れる）
    mp = node(nt, "ShaderNodeMapping"); link(nt, Pw, I(mp, "Vector")); I(mp, "Scale").default_value = (1.0, 1.0, 0.08)
    st = noise(nt, 2.5, 3, 0.7, O(mp, "Vector")); st = ramp(nt, st, [(0.40, (1, 1, 1, 1)), (0.68, (0.35, 0.35, 0.35, 1))])
    colr = mixrgb(nt, streak, mot, mixrgb(nt, st, (0.12, 0.11, 0.10, 1), mot), 'MIX')
    # ひび：ボロノイの縁
    cr = voronoi(nt, 0.3, Pw); crk = ramp(nt, cr, [(0.0, (0.25, 0.25, 0.25, 1)), (0.004, (0.25, 0.25, 0.25, 1)), (0.009, (1, 1, 1, 1))])
    crmask = ramp(nt, noise(nt, 0.12, 2, 0.5, Pw, 21.0), [(0.5, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))])
    colr = mixrgb(nt, crmask, colr, mixrgb(nt, 0.9, colr, crk, 'MULTIPLY'))
    # 苔：上向きの面 × ノイズ × 低い所
    up = node(nt, "ShaderNodeSeparateXYZ"); link(nt, O(g, "Normal"), up.inputs[0])
    upf = math_(nt, 'MULTIPLY', ramp(nt, up.outputs[2], [(0.3, (0, 0, 0, 1)), (0.9, (1, 1, 1, 1))]), noise(nt, 1.6, 5, 0.65, Pw, 3.0))
    upf = math_(nt, 'MULTIPLY', ramp(nt, upf, [(0.22, (0, 0, 0, 1)), (0.42, (1, 1, 1, 1))]), moss)
    colm = mixrgb(nt, upf, colr, (0.10, 0.16, 0.07, 1))
    # 隅・接する所は暗く（AO）
    ao = node(nt, "ShaderNodeAmbientOcclusion"); I(ao, "Distance").default_value = 1.5; link(nt, colm, I(ao, "Color"))
    colf = mixrgb(nt, 0.7, colm, O(ao, "Color"))
    # 床際の汚れ：各階の床から 0.8m までを暗く（高さの端数）
    zz = node(nt, "ShaderNodeSeparateXYZ"); link(nt, Pw, zz.inputs[0]); fz = math_(nt, 'MODULO', zz.outputs[2], 6.0)
    low = ramp(nt, math_(nt, 'MULTIPLY', fz, 1 / 0.8, clamp=True), [(0.0, (1, 1, 1, 1)), (1.0, (0, 0, 0, 1))])
    colf = mixrgb(nt, math_(nt, 'MULTIPLY', low, 0.55), colf, (0.10, 0.09, 0.08, 1))
    # ほこり（白っぽい粉）
    dust = math_(nt, 'MULTIPLY', ramp(nt, up.outputs[2], [(0.5, (0, 0, 0, 1)), (1.0, (1, 1, 1, 1))]), noise(nt, 0.6, 3, 0.5, Pw, 7.0))
    colf = mixrgb(nt, math_(nt, 'MULTIPLY', dust, 0.35), colf, (0.62, 0.60, 0.56, 1))
    if tile > 0:   # 目地
        br = node(nt, "ShaderNodeTexBrick"); link(nt, Pw, I(br, "Vector")); I(br, "Scale").default_value = tile; I(br, "Mortar Size").default_value = 0.015
        I(br, "Color1").default_value = (1, 1, 1, 1); I(br, "Color2").default_value = (0.94, 0.94, 0.94, 1); I(br, "Mortar").default_value = (0.6, 0.6, 0.6, 1)
        colf = mixrgb(nt, 0.8, colf, O(br, "Color"), 'MULTIPLY')
    link(nt, desat(nt, colf, mask), I(p, "Base Color"))
    # 濡れ：低い所（ノイズ）→ 粗さ 0.03・暗く
    wetm = math_(nt, 'MULTIPLY', ramp(nt, noise(nt, 0.22, 3, 0.5, Pw, 11.0), [(0.52, (0, 0, 0, 1)), (0.6, (1, 1, 1, 1))]), wet)
    wetm = math_(nt, 'MULTIPLY', wetm, ramp(nt, up.outputs[2], [(0.6, (0, 0, 0, 1)), (0.95, (1, 1, 1, 1))]))
    rough = mixrgb(nt, wetm, (0.78, 0.78, 0.78, 1), (0.03, 0.03, 0.03, 1)); rough = mixrgb(nt, math_(nt, 'MULTIPLY', st, 0.3), rough, (0.5, 0.5, 0.5, 1))
    link(nt, rough, I(p, "Roughness")); I(p, "Specular").default_value = 0.45
    bump = node(nt, "ShaderNodeBump"); I(bump, "Strength").default_value = 0.25; link(nt, mottle, I(bump, "Height")); link(nt, bump.outputs[0], I(p, "Normal"))
    # 波紋の輪そのものは、淡く光る
    link(nt, mixrgb(nt, ring, (0, 0, 0, 1), (0.9, 0.8, 0.6, 1)), I(p, "Emission")); I(p, "Emission Strength").default_value = 0.2
    return finish(m, nt, out, p)
def mat_metal(name, col=(0.55, 0.55, 0.56), rust=0.5, rough=0.4):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    base = (col[0], col[1], col[2], 1)
    rs = ramp(nt, noise(nt, 2.2, 5, 0.7, Pw, 5.0), [(0.42, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))]); rs = math_(nt, 'MULTIPLY', rs, rust)
    c = mixrgb(nt, rs, base, (0.30, 0.14, 0.07, 1)); c = mixrgb(nt, math_(nt, 'MULTIPLY', noise(nt, 9.0, 3, 0.5, Pw), 0.3), c, (0.2, 0.2, 0.2, 1))
    link(nt, desat(nt, c, mask, 0.15), I(p, "Base Color")); link(nt, math_(nt, 'SUBTRACT', 1.0, math_(nt, 'MULTIPLY', rs, 0.9)), I(p, "Metallic"))
    link(nt, mixrgb(nt, rs, (rough, rough, rough, 1), (0.85, 0.85, 0.85, 1)), I(p, "Roughness"))
    bump = node(nt, "ShaderNodeBump"); I(bump, "Strength").default_value = 0.3; link(nt, rs, I(bump, "Height")); link(nt, bump.outputs[0], I(p, "Normal"))
    link(nt, mixrgb(nt, ring, (0, 0, 0, 1), (0.9, 0.8, 0.6, 1)), I(p, "Emission")); I(p, "Emission Strength").default_value = 0.3
    return finish(m, nt, out, p)
def mat_glass(name, broken=0.0, tint=(0.85, 0.9, 0.9)):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position")
    I(p, "Base Color").default_value = (tint[0], tint[1], tint[2], 1); I(p, "Transmission").default_value = 1.0; I(p, "Roughness").default_value = 0.08; I(p, "IOR").default_value = 1.45
    grime = ramp(nt, noise(nt, 1.5, 4, 0.6, Pw, 2.0), [(0.4, (0, 0, 0, 1)), (0.75, (1, 1, 1, 1))])
    link(nt, mixrgb(nt, grime, (0.05, 0.05, 0.05, 1), (0.55, 0.55, 0.55, 1)), I(p, "Roughness"))
    if broken > 0:
        vo = voronoi(nt, 1.3, Pw); crack = ramp(nt, vo, [(0.0, (0, 0, 0, 1)), (0.012, (0, 0, 0, 1)), (0.03, (1, 1, 1, 1))])
        miss = ramp(nt, noise(nt, 0.9, 2, 0.5, Pw, 4.0), [(0.5 - broken * 0.25, (1, 1, 1, 1)), (0.52, (0, 0, 0, 1))])
        link(nt, math_(nt, 'MULTIPLY', crack, miss), I(p, "Alpha"))
        link(nt, mixrgb(nt, crack, (0.9, 0.9, 0.9, 1), (0.0, 0.0, 0.0, 1)), I(p, "Emission")); I(p, "Emission Strength").default_value = 0.6
    blend(m, 'BLEND', 'HASHED'); tryset(m, use_screen_refraction=True, show_transparent_back=False)
    return finish(m, nt, out, p)
def mat_shutter(name, col=(0.40, 0.40, 0.38)):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    wv = node(nt, "ShaderNodeTexWave"); link(nt, Pw, I(wv, "Vector")); I(wv, "Scale").default_value = 7.0; wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    rs = ramp(nt, noise(nt, 1.8, 5, 0.7, Pw, 9.0), [(0.4, (0, 0, 0, 1)), (0.6, (1, 1, 1, 1))])
    mp = node(nt, "ShaderNodeMapping"); link(nt, Pw, I(mp, "Vector")); I(mp, "Scale").default_value = (1.0, 1.0, 0.1)
    st = ramp(nt, noise(nt, 3.0, 3, 0.7, O(mp, "Vector")), [(0.45, (1, 1, 1, 1)), (0.7, (0.4, 0.4, 0.4, 1))])
    c = mixrgb(nt, rs, (col[0], col[1], col[2], 1), (0.28, 0.13, 0.07, 1)); c = mixrgb(nt, 0.8, c, st, 'MULTIPLY')
    link(nt, desat(nt, c, mask, 0.1), I(p, "Base Color")); link(nt, math_(nt, 'SUBTRACT', 0.9, math_(nt, 'MULTIPLY', rs, 0.9)), I(p, "Metallic"))
    link(nt, mixrgb(nt, rs, (0.45, 0.45, 0.45, 1), (0.9, 0.9, 0.9, 1)), I(p, "Roughness"))
    bump = node(nt, "ShaderNodeBump"); I(bump, "Strength").default_value = 0.5; link(nt, O(wv, "Fac"), I(bump, "Height")); link(nt, bump.outputs[0], I(p, "Normal"))
    return finish(m, nt, out, p)
SIGN_COLS = [(0.95, 0.15, 0.25), (0.1, 0.8, 0.95), (1.0, 0.75, 0.1), (0.5, 0.2, 0.95), (0.1, 0.9, 0.5), (1.0, 0.4, 0.1)]
def mat_sign(name, col, strength=6.0):
    """看板・LED の帯：波紋が来た所だけ色つきで灯る。普段は死んだ暗いパネル（ひび・ほこり）"""
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    I(p, "Base Color").default_value = (0.08, 0.08, 0.09, 1); I(p, "Roughness").default_value = 0.35
    dead = ramp(nt, noise(nt, 3.0, 4, 0.6, Pw, 1.0), [(0.3, (0.0, 0.0, 0.0, 1)), (0.7, (0.25, 0.25, 0.25, 1))])
    link(nt, mixrgb(nt, mask, dead, (col[0], col[1], col[2], 1)), I(p, "Emission"))
    flick = math_(nt, 'MULTIPLY_ADD', noise(nt, 40.0, 1, 0.5, Pw, 0.0), 0.5, 0.6)
    wv = node(nt, "ShaderNodeTexWave"); link(nt, Pw, I(wv, "Vector")); I(wv, "Scale").default_value = 60.0; wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    scan = math_(nt, 'MULTIPLY_ADD', O(wv, "Fac"), 0.5, 0.5)
    broken = ramp(nt, noise(nt, 2.5, 3, 0.6, Pw, 5.0), [(0.38, (0, 0, 0, 1)), (0.5, (1, 1, 1, 1))])
    link(nt, math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', mask, strength * 0.25), flick), math_(nt, 'MULTIPLY', scan, broken)), I(p, "Emission Strength"))
    return finish(m, nt, out, p)
def mat_emit(name, col, strength=1.0):
    m, nt, out = newmat(name); e = node(nt, "ShaderNodeEmission"); I(e, "Color").default_value = (col[0], col[1], col[2], 1); I(e, "Strength").default_value = strength
    return finish(m, nt, out, e)
def mat_ghost(name):
    """顔のない光の残像の人：波紋の中だけ見える。縦にぼけた光"""
    m, nt, out = newmat(name); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    e = node(nt, "ShaderNodeEmission"); I(e, "Color").default_value = (1.0, 0.85, 0.6, 1)
    fres = node(nt, "ShaderNodeLayerWeight"); I(fres, "Blend").default_value = 0.6
    a = math_(nt, 'MULTIPLY', O(fres, "Facing"), mask); a = math_(nt, 'MULTIPLY', a, 0.85)
    link(nt, math_(nt, 'MULTIPLY', a, 4.0), I(e, "Strength"))
    tr = node(nt, "ShaderNodeBsdfTransparent"); mx = node(nt, "ShaderNodeMixShader"); link(nt, a, mx.inputs[0]); link(nt, tr.outputs[0], mx.inputs[1]); link(nt, e.outputs[0], mx.inputs[2])
    blend(m, 'BLEND', 'NONE'); return finish(m, nt, out, mx)
def mat_water(name):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position")
    I(p, "Base Color").default_value = (0.05, 0.06, 0.06, 1); I(p, "Roughness").default_value = 0.02; I(p, "Specular").default_value = 0.6
    mp = node(nt, "ShaderNodeMapping"); link(nt, Pw, I(mp, "Vector")); I(mp, "Scale").default_value = (3, 3, 3)
    bump = node(nt, "ShaderNodeBump"); I(bump, "Strength").default_value = 0.08; link(nt, noise(nt, 4.0, 2, 0.5, O(mp, "Vector")), I(bump, "Height")); link(nt, bump.outputs[0], I(p, "Normal"))
    link(nt, ramp(nt, noise(nt, 0.5, 3, 0.6, Pw, 23.0), [(0.44, (0, 0, 0, 1)), (0.5, (1, 1, 1, 1))]), I(p, "Alpha")); blend(m, 'CLIP', 'CLIP')
    return finish(m, nt, out, p)
def mat_spray(name):
    m, nt, out = newmat(name); e = node(nt, "ShaderNodeEmission"); I(e, "Color").default_value = (0.8, 0.9, 1.0, 1); I(e, "Strength").default_value = 0.6
    g, tc = geo(nt); Pw = O(g, "Position"); n_ = noise(nt, 6.0, 3, 0.6, Pw)
    tr = node(nt, "ShaderNodeBsdfTransparent"); mx = node(nt, "ShaderNodeMixShader"); link(nt, math_(nt, 'MULTIPLY', n_, 0.22), mx.inputs[0]); link(nt, tr.outputs[0], mx.inputs[1]); link(nt, e.outputs[0], mx.inputs[2])
    blend(m, 'BLEND', 'NONE'); return finish(m, nt, out, mx)

def mat_plant(name):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    c = mixrgb(nt, noise(nt, 3.0, 3, 0.6, Pw, 13.0), (0.05, 0.11, 0.03, 1), (0.14, 0.26, 0.07, 1))
    link(nt, desat(nt, c, mask, 0.12), I(p, "Base Color")); I(p, "Roughness").default_value = 0.75; I(p, "Specular").default_value = 0.3
    I(p, "Subsurface").default_value = 0.12; I(p, "Subsurface Color").default_value = (0.2, 0.5, 0.1, 1)
    return finish(m, nt, out, p)
def mat_cloth(name, col):
    m, nt, out = newmat(name); p = principled(nt); g, tc = geo(nt); Pw = O(g, "Position"); mask, ring = add_ripple(nt)
    c = mixrgb(nt, math_(nt, 'MULTIPLY', noise(nt, 1.2, 4, 0.6, Pw, 17.0), 0.6), (col[0], col[1], col[2], 1), (0.25, 0.23, 0.2, 1))
    link(nt, desat(nt, c, mask, 0.08), I(p, "Base Color")); I(p, "Roughness").default_value = 0.9; I(p, "Specular").default_value = 0.1
    holes = ramp(nt, noise(nt, 2.5, 3, 0.7, Pw, 19.0), [(0.36, (0, 0, 0, 1)), (0.42, (1, 1, 1, 1))]); link(nt, holes, I(p, "Alpha"))
    blend(m, 'CLIP', 'CLIP'); return finish(m, nt, out, p)
MAT = {
    "plant": mat_plant("plant"), "cloth0": mat_cloth("cloth0", (0.7, 0.15, 0.2)), "cloth1": mat_cloth("cloth1", (0.15, 0.3, 0.7)), "cloth2": mat_cloth("cloth2", (0.8, 0.6, 0.15)),
    "floor": mat_concrete("floor", (0.34, 0.33, 0.31), moss=0.6, wet=0.5, streak=0.5, tile=0.8),
    "wall": mat_concrete("wall", (0.36, 0.35, 0.33), moss=0.3, wet=0.0, streak=0.9),
    "panel": mat_concrete("panel", (0.46, 0.46, 0.45), moss=0.15, wet=0.0, streak=0.7),      # 未来モールの白いリブ・床の縁
    "step": mat_concrete("step", (0.26, 0.26, 0.26), moss=0.9, wet=0.3, streak=0.3),
    "metal": mat_metal("metal", (0.40, 0.40, 0.42), rust=0.55, rough=0.35),
    "metal_dark": mat_metal("metal_dark", (0.16, 0.16, 0.17), rust=0.7, rough=0.5),
    "rim": mat_concrete("rim", (0.36, 0.35, 0.33), moss=0.75, wet=0.5, streak=0.6),
    "glass": mat_glass("glass", 0.0), "glass_broken": mat_glass("glass_broken", 0.6), "roof_glass": mat_glass("roof_glass", 0.35, (0.8, 0.85, 0.9)),
    "shutter": mat_shutter("shutter"), "water": mat_water("water"), "ghost": mat_ghost("ghost"), "spray": mat_spray("spray"),
}
SIGNM = [mat_sign("sign%d" % k, c) for k, c in enumerate(SIGN_COLS)]
LEDM = mat_sign("led", (0.3, 0.7, 1.0), 4.0)
stage("materials")

# ---------------- 形：箱を材質ごとにまとめて1つのメッシュに ----------------
MESH_ACC = {}
def acc_box(matkey, lo, hi, rot=None, name=None):
    """lo..hi の箱。rot=(ax,ay,az, cx,cy,cz) で回す"""
    v = [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]), (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]
    if rot is not None:
        R = Euler(rot[:3]).to_matrix(); c = Vector(rot[3:6]); v = [tuple(R @ (Vector(p) - c) + c) for p in v]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    a = MESH_ACC.setdefault(matkey, {"v": [], "f": []}); n = len(a["v"]); a["v"] += v; a["f"] += [tuple(i + n for i in q) for q in f]
def acc_tris(matkey, verts, faces):
    a = MESH_ACC.setdefault(matkey, {"v": [], "f": []}); n = len(a["v"]); a["v"] += [tuple(p) for p in verts]; a["f"] += [tuple(i + n for i in q) for q in faces]
def acc_cyl(matkey, p0, p1, r, nseg=10):
    p0 = Vector(p0); p1 = Vector(p1); d = p1 - p0; L_ = d.length
    if L_ < 1e-6: return
    z = d.normalized(); x = z.cross(Vector((0, 0, 1))) if abs(z.z) < 0.99 else z.cross(Vector((1, 0, 0))); x.normalize(); y = z.cross(x)
    vs = []; fs = []
    for k in range(nseg):
        a = 2 * math.pi * k / nseg; o = x * (r * math.cos(a)) + y * (r * math.sin(a)); vs.append(tuple(p0 + o)); vs.append(tuple(p1 + o))
    for k in range(nseg):
        a0 = 2 * k; b0 = 2 * ((k + 1) % nseg); fs.append((a0, b0, b0 + 1, a0 + 1))
    fs.append(tuple(2 * k for k in range(nseg))[::-1]); fs.append(tuple(2 * k + 1 for k in range(nseg)))
    acc_tris(matkey, vs, fs)
def flush_meshes(prefix="static_"):
    objs = {}
    for key, a in MESH_ACC.items():
        if not a["v"]: continue
        me = bpy.data.meshes.new(prefix + key); me.from_pydata(a["v"], [], a["f"]); me.update(); me.validate()
        mk = key.split("#")[0]
        me.materials.append(MAT[mk] if mk in MAT else (SIGNM[int(mk[4:])] if mk.startswith("sign") else LEDM))
        o = bpy.data.objects.new(prefix + key, me); sc.collection.objects.link(o); objs[key] = o
    MESH_ACC.clear(); return objs
BOXES = M["boxes"]; BOXN = {b["name"]: b for b in BOXES}
KIND2MAT = {"floor": "floor", "wall": "wall", "truss": "metal_dark", "step": "step", "rail": "metal", "rim": "rim", "spire": "metal", "column": "panel", "table": "metal_dark", "ceiling_ring": None, "glass": None}
for b in BOXES:
    k = b["kind"]; lo, hi = b["lo"], b["hi"]
    if k in ("glass", "ceiling_ring"): continue
    if k == "rail" and not b["name"].startswith(("E1", "E2", "E3", "E4")):
        # 手すり：ガラスの板（下 0.95）＋金属の笠木＋子柱
        horizontal = (hi[0] - lo[0]) > (hi[1] - lo[1])
        if horizontal:
            acc_box("glass", (lo[0], (lo[1] + hi[1]) / 2 - 0.012, lo[2] + 0.1), (hi[0], (lo[1] + hi[1]) / 2 + 0.012, lo[2] + 0.95))
            acc_box("metal", (lo[0], (lo[1] + hi[1]) / 2 - 0.04, hi[2] - 0.06), (hi[0], (lo[1] + hi[1]) / 2 + 0.04, hi[2]))
            x = lo[0]
            while x < hi[0]:
                acc_box("metal", (x, (lo[1] + hi[1]) / 2 - 0.03, lo[2]), (x + 0.06, (lo[1] + hi[1]) / 2 + 0.03, hi[2] - 0.05)); x += 1.5
        else:
            acc_box("glass", ((lo[0] + hi[0]) / 2 - 0.012, lo[1], lo[2] + 0.1), ((lo[0] + hi[0]) / 2 + 0.012, hi[1], lo[2] + 0.95))
            acc_box("metal", ((lo[0] + hi[0]) / 2 - 0.04, lo[1], hi[2] - 0.06), ((lo[0] + hi[0]) / 2 + 0.04, hi[1], hi[2]))
            y = lo[1]
            while y < hi[1]:
                acc_box("metal", ((lo[0] + hi[0]) / 2 - 0.03, y, lo[2]), ((lo[0] + hi[0]) / 2 + 0.03, y + 0.06, hi[2] - 0.05)); y += 1.5
        continue
    if k == "rail":   # エスカレーターの側板＋手すりベルト
        acc_box("metal_dark", (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2] - 0.08)); acc_box("metal", (lo[0], lo[1] - 0.03, hi[2] - 0.08), (hi[0], hi[1] + 0.03, hi[2]))
        continue
    if k == "step":
        acc_box("step", lo, hi); acc_box("metal_dark", (lo[0], lo[1], hi[2] - 0.02), (hi[0], hi[1], hi[2]))   # 段の縁の金属
        continue
    if k == "floor" and b["name"].startswith(("ring", "island", "E")):
        acc_box("floor", lo, hi)
        # 床の縁（吹き抜け側）に未来モールの白い帯＋LED の帯
        continue
    if k == "table":
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        acc_box("metal_dark", (cx - 0.55, cy - 0.55, hi[2] - 0.04), (cx + 0.55, cy + 0.55, hi[2])); acc_cyl("metal_dark", (cx, cy, lo[2]), (cx, cy, hi[2] - 0.04), 0.05)
        for j in range(4):   # 椅子（倒れているのも）
            a = j * math.pi / 2 + 0.3; sx, sy = cx + math.cos(a) * 0.95, cy + math.sin(a) * 0.95; tipped = (rnd.random() < 0.3)
            rot = (1.3, 0, a, sx, sy, lo[2] + 0.2) if tipped else (0, 0, a, sx, sy, lo[2])
            acc_box("metal_dark", (sx - 0.22, sy - 0.22, lo[2] + 0.42), (sx + 0.22, sy + 0.22, lo[2] + 0.46), rot); acc_box("metal_dark", (sx - 0.22, sy + 0.18, lo[2] + 0.46), (sx + 0.22, sy + 0.22, lo[2] + 0.9), rot)
            for dx_, dy_ in ((-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2), (0.2, 0.2)): acc_cyl("metal_dark", (sx + dx_, sy + dy_, lo[2]), (sx + dx_, sy + dy_, lo[2] + 0.42), 0.015, 6) if not tipped else None
        continue
    mk = KIND2MAT.get(k, "wall")
    if mk: acc_box(mk, lo, hi)
# 吹き抜けの縁の帯（白いリブ＋LED 帯）：各階、床の下側の縁に沿って
for f in range(1, NFLOOR):
    z = f * H
    for (x0, y0, x1, y1) in ((VOID[0], VOID[2], VOID[1], VOID[2]), (VOID[0], VOID[3], VOID[1], VOID[3]), (VOID[0], VOID[2], VOID[0], VOID[3]), (VOID[1], VOID[2], VOID[1], VOID[3])):
        hor = (x1 - x0) > 0
        if hor: acc_box("panel", (x0, y0 - 0.25, z - 0.9), (x1, y0 + 0.25, z - 0.45)); acc_box("led", (x0, y0 - 0.27, z - 0.7), (x1, y0 + 0.27, z - 0.64))
        else: acc_box("panel", (x0 - 0.25, y0, z - 0.9), (x0 + 0.25, y1, z - 0.45)); acc_box("led", (x0 - 0.27, y0, z - 0.7), (x0 + 0.27, y1, z - 0.64))
    for (x0, y0, x1, y1) in ((ISLAND[0], ISLAND[2], ISLAND[1], ISLAND[2]), (ISLAND[0], ISLAND[3], ISLAND[1], ISLAND[3]), (ISLAND[0], ISLAND[2], ISLAND[0], ISLAND[3]), (ISLAND[1], ISLAND[2], ISLAND[1], ISLAND[3])):
        hor = (x1 - x0) > 0
        if hor: acc_box("panel", (x0, y0 - 0.2, z - 0.8), (x1, y0 + 0.2, z - 0.45)); acc_box("led", (x0, y0 - 0.22, z - 0.66), (x1, y0 + 0.22, z - 0.6))
        else: acc_box("panel", (x0 - 0.2, y0, z - 0.8), (x0 + 0.2, y1, z - 0.45)); acc_box("led", (x0 - 0.22, y0, z - 0.66), (x0 + 0.22, y1, z - 0.6))
# 未来モールの曲がったリブ（吹き抜けの壁面：各階の間を斜めに走る白い帯）
for f in range(1, NFLOOR):
    z = f * H
    for k in range(-2, 3):
        x = k * 8.0
        acc_box("panel", (x - 0.18, VOID[2] - 0.55, z - H + 0.6), (x + 0.18, VOID[2] - 0.25, z - 0.9), (0, 0, 0, x, VOID[2] - 0.4, z - H / 2))
        acc_box("panel", (x - 0.18, VOID[3] + 0.25, z - H + 0.6), (x + 0.18, VOID[3] + 0.55, z - 0.9))
# 天窓：桁の間にガラスの板（欠けている所あり）＋細い桟
for xi in range(-20, 20, 4):
    for yi in range(-10, 10, 4):
        if rnd.random() < 0.22: continue      # 落ちて無い板
        acc_box("roof_glass", (xi + 0.05, yi + 0.05, ROOF), (xi + 3.95, yi + 3.95, ROOF + 0.04))
    acc_box("metal_dark", (xi - 0.04, VOID[2], ROOF - 0.12), (xi + 0.04, VOID[3], ROOF + 0.06))
for yi in range(-10, 11, 4): acc_box("metal_dark", (VOID[0], yi - 0.04, ROOF - 0.12), (VOID[1], yi + 0.04, ROOF + 0.06))
# 天窓の外の屋根（吹き抜け以外）：閉じた天井
acc_box("wall", (RING[0], RING[2], ROOF - 0.5), (RING[1], VOID[2], ROOF)); acc_box("wall", (RING[0], VOID[3], ROOF - 0.5), (RING[1], RING[3], ROOF))
acc_box("wall", (RING[0], VOID[2], ROOF - 0.5), (VOID[0], VOID[3], ROOF)); acc_box("wall", (VOID[1], VOID[2], ROOF - 0.5), (RING[1], VOID[3], ROOF))
# 店：奥行き 4m の空洞＋顔（シャッター／ガラス）＋看板
SHOPS = M["shops"]
for i, s in enumerate(SHOPS):
    lo, hi = s["lo"], s["hi"]; face = s["face"]; kind = s["kind"]; z0 = lo[2]; z1 = hi[2]
    # 店内（暗い箱：床・天井・奥壁・側壁）
    acc_box("wall", (lo[0], lo[1], z0 - 0.02), (hi[0], hi[1], z0 + 0.0))
    if face in ("n", "s"):
        yface = hi[1] if face == "n" else lo[1]; yback = lo[1] if face == "n" else hi[1]
        acc_box("wall", (lo[0], min(yback, yback + (0.3 if face == "n" else -0.3)), z0), (hi[0], max(yback, yback + (0.3 if face == "n" else -0.3)), z1))
        acc_box("wall", (lo[0] - 0.15, lo[1], z0), (lo[0] + 0.15, hi[1], z1)); acc_box("wall", (hi[0] - 0.15, lo[1], z0), (hi[0] + 0.15, hi[1], z1))
        acc_box("wall", (lo[0], lo[1], z1 - 0.3), (hi[0], hi[1], z1 + 0.3))
        fl = (lo[0] + 0.3, yface - 0.05, z0); fh = (hi[0] - 0.3, yface + 0.05, z1 - 1.0)
        sl = (lo[0] + 0.5, yface - 0.08, z1 - 0.95); sh_ = (hi[0] - 0.5, yface + 0.12, z1 - 0.25)
    else:
        xface = hi[0] if face == "e" else lo[0]; xback = lo[0] if face == "e" else hi[0]
        acc_box("wall", (min(xback, xback + (0.3 if face == "e" else -0.3)), lo[1], z0), (max(xback, xback + (0.3 if face == "e" else -0.3)), hi[1], z1))
        acc_box("wall", (lo[0], lo[1] - 0.15, z0), (hi[0], lo[1] + 0.15, z1)); acc_box("wall", (lo[0], hi[1] - 0.15, z0), (hi[0], hi[1] + 0.15, z1))
        acc_box("wall", (lo[0], lo[1], z1 - 0.3), (hi[0], hi[1], z1 + 0.3))
        fl = (xface - 0.05, lo[1] + 0.3, z0); fh = (xface + 0.05, hi[1] - 0.3, z1 - 1.0)
        sl = (xface - 0.08, lo[1] + 0.5, z1 - 0.95); sh_ = (xface + 0.12, hi[1] - 0.5, z1 - 0.25)
    if kind == "shutter": acc_box("shutter", fl, fh)
    elif kind == "shutter_half": acc_box("shutter", (fl[0], fl[1], fl[2] + 1.6), fh)
    elif kind == "window": acc_box("glass", fl, fh)
    else: acc_box("glass_broken", fl, fh)
    # 店内の名残（棚・カウンター・マネキンの台）
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    for j in range(3):
        ox = rnd.uniform(-2.2, 2.2); oy = rnd.uniform(-1.5, 1.5); hgt = rnd.uniform(0.8, 2.2)
        acc_box("metal_dark", (cx + ox - 0.4, cy + oy - 0.3, z0), (cx + ox + 0.4, cy + oy + 0.3, z0 + hgt))
    acc_box("metal_dark", (sl[0] - 0.08, sl[1] - 0.08, sl[2] - 0.08), (sh_[0] + 0.08, sh_[1] + 0.08, sh_[2] + 0.08)); acc_box("sign%d" % (i % 6), sl, sh_)
    # 看板の脱落（たまに斜め）
    if i % 5 == 2:
        acc_box("metal_dark", (sl[0], sl[1], sl[2] - 0.3), (sh_[0], sh_[1], sl[2] - 0.2), (0.0, 0.0, 0.0, (sl[0] + sh_[0]) / 2, (sl[1] + sh_[1]) / 2, sl[2]))
# 案内板（各階の島と大通り）：傾いた板＋死んだ画面
for f in range(1, NFLOOR):
    z = f * H; x, y = (3.0 if f % 2 else -3.0), 4.5
    acc_box("metal_dark", (x - 0.05, y - 0.05, z), (x + 0.05, y + 0.05, z + 2.3)); acc_box("sign1", (x - 0.7, y - 0.03, z + 1.2), (x + 0.7, y + 0.03, z + 2.3), (0.12, 0, 0.3, x, y, z + 1.8))
for yk in (-45.0, -30.0):
    acc_box("metal_dark", (-4.9, yk - 0.05, 0), (-4.8, yk + 0.05, 2.3)); acc_box("sign2", (-5.5, yk - 0.03, 1.2), (-4.2, yk + 0.03, 2.3), (0.1, 0, -0.2, -4.85, yk, 1.8))
# ホログラムのキオスク（島に 2 本の光る柱）・ガラスのエレベーターの筒（島の角）
for f in range(1, NFLOOR):
    z = f * H
    acc_cyl("metal_dark", (-3.5, -3.5, z), (-3.5, -3.5, z + 1.1), 0.35, 12); acc_cyl("sign4", (-3.5, -3.5, z + 1.1), (-3.5, -3.5, z + 2.6), 0.12, 10)
acc_cyl("glass", (ISLAND[1] + 1.6, ISLAND[3] + 1.6, 0.0), (ISLAND[1] + 1.6, ISLAND[3] + 1.6, ROOF - 1.0), 1.5, 24)
acc_cyl("metal_dark", (ISLAND[1] + 1.6, ISLAND[3] + 1.6, 0.0), (ISLAND[1] + 1.6, ISLAND[3] + 1.6, ROOF - 1.0), 0.12, 8)
acc_box("metal_dark", (ISLAND[1] + 0.4, ISLAND[3] + 0.4, 2.5 * H), (ISLAND[1] + 2.8, ISLAND[3] + 2.8, 2.5 * H + 2.8))   # 途中で止まったカゴ
# 落ちた天井パネル・がれき・割れガラス（天窓の下の地上、各階の縁）
for k in range(70):
    x = rnd.uniform(VOID[0] + 1, VOID[1] - 1); y = rnd.uniform(VOID[2] + 1, VOID[3] - 1)
    if math.hypot(x, y) < 6.0: continue
    s_ = rnd.uniform(0.5, 1.6); a = rnd.uniform(0, math.pi); t_ = rnd.uniform(0, 0.6)
    acc_box("panel", (x - s_, y - s_ * 0.7, 0.0), (x + s_, y + s_ * 0.7, 0.04), (t_, 0, a, x, y, 0.0))
for k in range(220):   # 小さながれき
    x = rnd.uniform(RING[0] + 1, RING[1] - 1); y = rnd.uniform(RING[2] + 1, RING[3] - 1); z = rnd.choice([0, 0, 0, 1, 2, 3, 4]) * H
    if z > 0 and (VOID[0] < x < VOID[1] and VOID[2] < y < VOID[3]) and not (ISLAND[0] < x < ISLAND[1] and ISLAND[2] < y < ISLAND[3]): continue
    s_ = rnd.uniform(0.08, 0.4); acc_box(rnd.choice(["wall", "panel", "metal_dark"]), (x - s_, y - s_ * 0.6, z), (x + s_, y + s_ * 0.6, z + s_ * 0.5), (rnd.uniform(0, 0.4), 0, rnd.uniform(0, 3), x, y, z))
for k in range(150):   # 割れガラスの破片（きらっと光る）
    x = rnd.uniform(VOID[0], VOID[1]); y = rnd.uniform(VOID[2], VOID[3]); s_ = rnd.uniform(0.05, 0.25)
    acc_box("glass", (x - s_, y - s_ * 0.5, 0.0), (x + s_, y + s_ * 0.5, 0.01), (0, 0, rnd.uniform(0, 3), x, y, 0))
# 大通りの落ちた天井パネル（斜めに垂れ下がる）＋配線
for k in range(14):
    y = CONC[2] + 3 + k * 2.6; x = rnd.uniform(-4, 4); s_ = rnd.uniform(0.6, 1.2)
    acc_box("panel", (x - s_, y - 0.5, H - 0.4), (x + s_, y + 0.5, H - 0.36), (rnd.uniform(0.3, 1.2), rnd.uniform(-0.2, 0.2), 0, x, y, H - 0.4))
# 垂れるケーブルとつる（天窓の桁・落ちた天井から）
for k in range(60):
    x = rnd.uniform(VOID[0] + 2, VOID[1] - 2); y = rnd.choice([-10, -6, -2, 2, 6, 10]) + rnd.uniform(-0.3, 0.3); z0 = TRUSS - 0.3; L_ = rnd.uniform(2, 14)
    p1 = (x + rnd.uniform(-0.8, 0.8), y + rnd.uniform(-0.8, 0.8), z0 - L_)
    acc_cyl("metal_dark" if rnd.random() < 0.6 else "step", (x, y, z0), p1, rnd.uniform(0.015, 0.04), 6)
for k in range(30):   # 各階の縁から垂れるつる
    f = rnd.randint(1, NFLOOR - 1); z0 = f * H - 0.45; x = rnd.uniform(VOID[0], VOID[1]); y = rnd.choice([VOID[2], VOID[3]])
    acc_cyl("step", (x, y, z0), (x + rnd.uniform(-0.5, 0.5), y, z0 - rnd.uniform(1, 5)), 0.03, 6)
for k in range(24):   # 大通り
    y = rnd.uniform(CONC[2] + 2, CONC[3] - 2); x = rnd.uniform(-5, 5)
    acc_cyl("metal_dark", (x, y, H - 0.4), (x + rnd.uniform(-0.5, 0.5), y + rnd.uniform(-0.5, 0.5), H - 0.4 - rnd.uniform(0.8, 3.0)), 0.02, 6)
# 水たまり（地上の低い所・池の底）
acc_box("water", (-5.0, -5.0, M["basin_z"] + 0.02), (5.0, 5.0, M["basin_z"] + 0.1))
for k in range(12):
    x = rnd.uniform(VOID[0] + 2, VOID[1] - 2); y = rnd.uniform(VOID[2] + 1, VOID[3] - 1); s_ = rnd.uniform(1.0, 3.5)
    if math.hypot(x, y) < 6.5: continue
    acc_box("water", (x - s_, y - s_ * 0.6, 0.0), (x + s_, y + s_ * 0.6, 0.012))
for k in range(8):
    y = rnd.uniform(CONC[2] + 2, CONC[3] - 2); x = rnd.uniform(-4, 4); s_ = rnd.uniform(0.8, 2.5)
    acc_box("water", (x - s_, y - s_ * 0.6, 0.0), (x + s_, y + s_ * 0.6, 0.012))

ESC_INFO = M["esc_info"]; STEPD = M["step"]
# 植物（葉の塊）：天窓から垂れるつる・床の草・各階の縁・プランター
def leaf_clump(center, r, n, mat="plant"):
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi); b = rnd.uniform(-1, 1); rr = r * rnd.uniform(0.3, 1.0)
        c = (center[0] + rr * math.cos(a) * math.sqrt(1 - b * b), center[1] + rr * math.sin(a) * math.sqrt(1 - b * b), center[2] + rr * b)
        sz = rnd.uniform(0.08, 0.22); ang = rnd.uniform(0, 2 * math.pi); t_ = rnd.uniform(0, math.pi)
        v0 = (c[0], c[1], c[2]); v1 = (c[0] + sz * math.cos(ang), c[1] + sz * math.sin(ang), c[2] + sz * 0.3 * math.cos(t_)); v2 = (c[0] + sz * math.cos(ang + 1.2), c[1] + sz * math.sin(ang + 1.2), c[2] - sz * 0.4 * math.sin(t_))
        acc_tris(mat, [v0, v1, v2], [(0, 1, 2)])
for k in range(90):   # 天窓の桁から垂れるつる（葉つき）
    x = rnd.uniform(VOID[0] + 1, VOID[1] - 1); y = rnd.choice([-6, -2, 2, 6]) + rnd.uniform(-0.2, 0.2); L_ = rnd.uniform(3, 16); z0 = TRUSS - 0.2
    xe = x + rnd.uniform(-1.0, 1.0); ye = y + rnd.uniform(-1.0, 1.0)
    acc_cyl("step", (x, y, z0), (xe, ye, z0 - L_), rnd.uniform(0.02, 0.05), 6)
    for j in range(int(L_ / 0.7)):
        u = (j + 0.5) / (L_ / 0.7); leaf_clump((x + (xe - x) * u, y + (ye - y) * u, z0 - L_ * u), 0.35, 7)
for f in range(1, NFLOOR):   # 各階の縁からこぼれる草とつる
    z = f * H
    for k in range(40):
        x = rnd.uniform(VOID[0], VOID[1]); y = rnd.choice([VOID[2], VOID[3]])
        leaf_clump((x, y + (0.3 if y > 0 else -0.3), z + 0.15), 0.45, 10)
        if rnd.random() < 0.5: 
            L_ = rnd.uniform(1, 5); acc_cyl("step", (x, y, z - 0.45), (x + rnd.uniform(-0.4, 0.4), y, z - 0.45 - L_), 0.03, 6)
            for j in range(int(L_ / 0.6)): leaf_clump((x, y, z - 0.45 - L_ * (j + 0.5) / (L_ / 0.6)), 0.3, 6)
    for k in range(16):
        x = rnd.uniform(ISLAND[0], ISLAND[1]); y = rnd.choice([ISLAND[2], ISLAND[3]]); leaf_clump((x, y, z + 0.15), 0.4, 9)
for k in range(260):   # 床の草むら（吹き抜けの地上・大通り・各階の通路）
    z = rnd.choice([0, 0, 0, 0, 1, 2, 3, 4]) * H
    if z == 0:
        if rnd.random() < 0.35: x = rnd.uniform(-5, 5); y = rnd.uniform(CONC[2], CONC[3])
        else:
            x = rnd.uniform(VOID[0], VOID[1]); y = rnd.uniform(VOID[2], VOID[3])
            if math.hypot(x, y) < 5.6: continue
    else:
        x = rnd.uniform(RING[0] + 1, RING[1] - 1); y = rnd.uniform(RING[2] + 1, RING[3] - 1)
        if VOID[0] < x < VOID[1] and VOID[2] < y < VOID[3]: continue
    for j in range(rnd.randint(4, 9)):
        a = rnd.uniform(0, 2 * math.pi); h_ = rnd.uniform(0.15, 0.5); w_ = 0.03
        bx, by = x + rnd.uniform(-0.3, 0.3), y + rnd.uniform(-0.3, 0.3)
        acc_tris("plant", [(bx - w_ * math.sin(a), by + w_ * math.cos(a), z), (bx + w_ * math.sin(a), by - w_ * math.cos(a), z), (bx + 0.25 * h_ * math.cos(a), by + 0.25 * h_ * math.sin(a), z + h_)], [(0, 1, 2)])
# エスカレーターの段の苔の盛り上がり（葉ではなく低い塊）
for name, f0, xb, xt, yy in M["escs"]:
    for tw in (0, 1):
        e = ESC_INFO[name + ("b" if tw else "")]
        for k in range(STEPD["n"]):
            if rnd.random() < 0.45: continue
            x = e["xb"] + e["sgn"] * (k + 0.5) * STEPD["run"] + rnd.uniform(-0.2, 0.2); y = e["y"] + rnd.uniform(-0.45, 0.45); z = f0 * H + (k + 1) * STEPD["rise"]
            leaf_clump((x, y, z + 0.04), 0.14, 5)
# プランター・ベンチ・ごみ箱・垂れ幕（各階の通路）
for f in range(0, NFLOOR):
    z = f * H
    spots = [(rnd.uniform(VOID[0] + 2, VOID[1] - 2), rnd.choice([VOID[2] - 3.0, VOID[3] + 3.0])) for _ in range(8)] + [(rnd.choice([VOID[0] - 3.0, VOID[1] + 3.0]), rnd.uniform(VOID[2] + 1, VOID[3] - 1)) for _ in range(5)]
    if f == 0: spots += [(rnd.uniform(-4.5, 4.5), rnd.uniform(CONC[2] + 2, CONC[3] - 2)) for _ in range(7)]
    for i, (x, y) in enumerate(spots):
        kind = i % 4
        if kind == 0:     # プランター（土＋植物）
            acc_box("panel", (x - 0.8, y - 0.4, z), (x + 0.8, y + 0.4, z + 0.55)); acc_box("step", (x - 0.72, y - 0.32, z + 0.4), (x + 0.72, y + 0.32, z + 0.52))
            leaf_clump((x, y, z + 0.8), 0.7, 26); leaf_clump((x + 0.5, y, z + 0.6), 0.4, 10)
        elif kind == 1:   # ベンチ
            acc_box("metal_dark", (x - 0.9, y - 0.25, z + 0.42), (x + 0.9, y + 0.25, z + 0.48)); acc_box("metal_dark", (x - 0.9, y + 0.2, z + 0.48), (x + 0.9, y + 0.25, z + 0.9))
            for dx_ in (-0.8, 0.8): acc_box("metal_dark", (x + dx_ - 0.03, y - 0.22, z), (x + dx_ + 0.03, y + 0.22, z + 0.42))
        elif kind == 2:   # ごみ箱（倒れているのも）
            tipped = rnd.random() < 0.4
            if tipped: acc_box("metal_dark", (x - 0.25, y - 0.25, z), (x + 0.25, y + 0.25, z + 0.85), (1.5, 0.0, rnd.uniform(0, 3), x, y, z + 0.25))
            else: acc_cyl("metal_dark", (x, y, z), (x, y, z + 0.85), 0.27, 12)
        else:             # 垂れ幕（破れた布）
            w_, h_ = 0.9, rnd.uniform(1.8, 3.0); acc_box("cloth%d" % (i % 3), (x - w_ / 2, y - 0.01, z + 2.2), (x + w_ / 2, y + 0.01, z + 2.2 + h_), (rnd.uniform(-0.15, 0.15), 0.0, rnd.uniform(-0.3, 0.3), x, y, z + 2.2 + h_))
# 吹き抜けの縁の手すりから垂れる幕
for f in range(1, NFLOOR):
    z = f * H
    for k in range(5):
        x = rnd.uniform(VOID[0] + 2, VOID[1] - 2); y = rnd.choice([VOID[2], VOID[3]]); h_ = rnd.uniform(2.0, 4.5)
        acc_box("cloth%d" % (k % 3), (x - 0.6, y - 0.02, z + 1.0 - h_), (x + 0.6, y + 0.02, z + 1.0), (0.0, rnd.uniform(-0.1, 0.1), 0.0, x, y, z + 1.0))
STATIC = flush_meshes("static_")
for o in STATIC.values():
    for p in o.data.polygons: p.use_smooth = False
stage("static meshes %d" % len(STATIC))

# ---------------- 噴水の噴き上げ（波紋の時だけ） ----------------
sp_me = bpy.data.meshes.new("spray"); vs = []; fs = []
for j in range(9):
    a = 2 * math.pi * j / 9 + 0.4; vs0 = len(vs)
    for k in range(8):
        t = k / 7; r = 0.04 + 0.10 * t; xo = math.cos(a) * (0.4 + 2.4 * t); yo = math.sin(a) * (0.4 + 2.4 * t); z = 1.2 + 5.0 * math.sin(math.pi * t) ** 0.8 * (1 - t * 0.5)
        for q in range(4):
            b = 2 * math.pi * q / 4; vs.append((xo + math.cos(b) * r, yo + math.sin(b) * r, z))
    for k in range(7):
        for q in range(4): fs.append((vs0 + k * 4 + q, vs0 + k * 4 + (q + 1) % 4, vs0 + (k + 1) * 4 + (q + 1) % 4, vs0 + (k + 1) * 4 + q))
sp_me.from_pydata(vs, [], fs); sp_me.update(); sp_me.materials.append(MAT["spray"])
spray = bpy.data.objects.new("spray", sp_me); sc.collection.objects.link(spray); spray.location = (0, 0, M["basin_z"])
spray.scale = (0, 0, 0); spray.keyframe_insert("scale", frame=1)
for ev in M["events"]:
    if ev["what"] != "fountain": continue
    f0 = ev["fr"]; d = ev["dur"]
    for ff, s_ in ((f0 - 1, 0.0), (f0 + 6, 1.0), (f0 + d - 8, 1.0), (f0 + d, 0.0)):
        spray.scale = (s_, s_, s_); spray.keyframe_insert("scale", frame=ff)
# エスカレーターの「一瞬動く」：段の縁の金属の帯は静的なので、手すりベルト側に流れる筋を出す代わりに、段の上に薄い光の帯を流す
ESC_INFO = M["esc_info"]; STEPD = M["step"]
for name, f0, xb, xt, yy in M["escs"]:
    for tw in (0, 1):
        e = ESC_INFO[name + ("b" if tw else "")]
        me = bpy.data.meshes.new("escflow_" + name + str(tw)); vs = []; fs = []
        for k in range(STEPD["n"]):
            x0 = e["xb"] + e["sgn"] * k * STEPD["run"]; x1 = e["xb"] + e["sgn"] * (k + 1) * STEPD["run"]; z = f0 * H + (k + 1) * STEPD["rise"] + 0.005
            n = len(vs); vs += [(min(x0, x1), e["y"] - STEPD["w"] / 2, z), (max(x0, x1), e["y"] - STEPD["w"] / 2, z), (max(x0, x1), e["y"] + STEPD["w"] / 2, z), (min(x0, x1), e["y"] + STEPD["w"] / 2, z)]
            fs.append((n, n + 1, n + 2, n + 3))
        me.from_pydata(vs, [], fs); me.update()
        m_, nt, out = newmat("escflow_" + name + str(tw)); em = node(nt, "ShaderNodeEmission"); I(em, "Color").default_value = (0.6, 0.85, 1.0, 1)
        g, tc = geo(nt); mp = node(nt, "ShaderNodeMapping"); link(nt, O(g, "Position"), I(mp, "Vector")); I(mp, "Scale").default_value = (3.0, 0.0, 0.0)
        wv = node(nt, "ShaderNodeTexWave"); link(nt, O(mp, "Vector"), I(wv, "Vector")); I(wv, "Scale").default_value = 1.0; wv.wave_type = 'BANDS'; wv.bands_direction = 'X'
        on = val(nt, 0.0); link(nt, math_(nt, 'MULTIPLY', math_(nt, 'MULTIPLY', O(wv, "Fac"), on), 2.5), I(em, "Strength"))
        tr = node(nt, "ShaderNodeBsdfTransparent"); mx = node(nt, "ShaderNodeMixShader"); link(nt, math_(nt, 'MULTIPLY', O(wv, "Fac"), on), mx.inputs[0]); link(nt, tr.outputs[0], mx.inputs[1]); link(nt, em.outputs[0], mx.inputs[2])
        blend(m_, 'BLEND', 'NONE'); finish(m_, nt, out, mx); me.materials.append(m_)
        o = bpy.data.objects.new("escflow_" + name + str(tw), me); sc.collection.objects.link(o)
        on.default_value = 0.0; on.keyframe_insert("default_value", frame=1)
        I(mp, "Location").default_value = (0, 0, 0); I(mp, "Location").keyframe_insert("default_value", frame=1)
        for ev in M["events"]:
            if ev["what"] != "escalator" or ev["name"] != name: continue
            f_ = ev["fr"]; d = ev["dur"]
            for ff, s_ in ((f_ - 1, 0.0), (f_ + 4, 1.0), (f_ + d - 6, 1.0), (f_ + d, 0.0)):
                on.default_value = s_; on.keyframe_insert("default_value", frame=ff)
            I(mp, "Location").default_value = (0, 0, 0); I(mp, "Location").keyframe_insert("default_value", frame=f_)
            I(mp, "Location").default_value = (e["sgn"] * 3.0 * d / FPS * 0.6, 0, 0); I(mp, "Location").keyframe_insert("default_value", frame=f_ + d)
stage("events")

# ---------------- 人影（顔のない光の残像）：波紋の中だけ見える ----------------
for i, pp in enumerate(M["people"]):
    me = bpy.data.meshes.new("ghost%d" % i); bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=8, radius=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * 0.22, v.co.y * 0.16, v.co.z * pp["h"] * 0.5 + pp["h"] * 0.5))
    bm.to_mesh(me); bm.free(); me.materials.append(MAT["ghost"])
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new("ghost%d" % i, me); sc.collection.objects.link(o)
    p0 = Vector(pp["p0"]); p1 = Vector(pp["p1"]); L_ = (p1 - p0).length; per = max(1.0, L_ / pp["speed"])
    for f in range(1, NF + 1, 3):
        t = (f / FPS + pp["phase"] * per) % (2 * per); u = t / per if t < per else 2 - t / per
        q = p0.lerp(p1, u); o.location = (q.x, q.y, q.z + 0.03 * math.sin(f * 0.6)); o.keyframe_insert("location", frame=f)
        o.rotation_euler = (0, 0, math.atan2((p1 - p0).y, (p1 - p0).x)); o.keyframe_insert("rotation_euler", frame=f)
stage("ghosts")

# ---------------- グミ（宇宙うんこ）：自作のソフトクリーム型＋銀河の肌 ----------------
def unko_mesh():
    nz = 36; nth = 40; vs = []; fs = []
    for i in range(nz + 1):
        h = i / nz; z = h * H_UNKO
        R = 0.235 * (1 - h) ** 0.75 + 0.02; R *= (1 + 0.05 * math.sin(h * 9))
        for j in range(nth):
            th = 2 * math.pi * j / nth; r = R * (1 + 0.16 * math.cos(3 * th - h * 9.5) * (0.4 + 0.6 * h) * (1 if h > 0.08 else h / 0.08))
            vs.append((r * math.cos(th), r * math.sin(th), z * (1 - 0.12 * (1 - h) * (1 - h))))
    for i in range(nz):
        for j in range(nth): a = i * nth + j; b = i * nth + (j + 1) % nth; fs.append((a, b, b + nth, a + nth))
    c0 = len(vs); vs.append((0, 0, 0.0)); fs += [(c0, (j + 1) % nth, j) for j in range(nth)]
    c1 = len(vs); vs.append((0, 0, H_UNKO * 1.02)); fs += [(c1, nz * nth + j, nz * nth + (j + 1) % nth) for j in range(nth)]
    me = bpy.data.meshes.new("unko"); me.from_pydata(vs, [], fs); me.update()
    for p in me.polygons: p.use_smooth = True
    return me
me = unko_mesh(); unko = bpy.data.objects.new("unko", me); sc.collection.objects.link(unko)
um, unt, uout = newmat("unko_galaxy"); up = principled(unt); g, tc = geo(unt); P = O(tc, "Object")
nebA = noise(unt, 7.0, 6, 0.7, P, 0.0); nebB = noise(unt, 11.0, 5, 0.6, P, 2.0)
c = mixrgb(unt, ramp(unt, nebA, [(0.45, (0, 0, 0, 1)), (0.72, (1, 1, 1, 1))]), (0.02, 0.015, 0.08, 1), (0.55, 0.10, 0.40, 1))
c = mixrgb(unt, ramp(unt, nebB, [(0.55, (0, 0, 0, 1)), (0.75, (1, 1, 1, 1))]), c, (0.10, 0.55, 0.80, 1))
stars = ramp(unt, voronoi(unt, 90.0, P, 'F1'), [(0.0, (1, 1, 1, 1)), (0.04, (1, 1, 1, 1)), (0.09, (0, 0, 0, 1))])
link(unt, c, I(up, "Base Color")); I(up, "Roughness").default_value = 0.22; I(up, "Clearcoat").default_value = 0.8; I(up, "Clearcoat Roughness").default_value = 0.05
I(up, "Subsurface").default_value = 0.04; I(up, "Subsurface Color").default_value = (0.3, 0.1, 0.5, 1)
link(unt, mixrgb(unt, stars, (0.06, 0.02, 0.14, 1), (1.0, 0.95, 0.9, 1)), I(up, "Emission")); I(up, "Emission Strength").default_value = 0.5
bpu = node(unt, "ShaderNodeBump"); I(bpu, "Strength").default_value = 0.06; link(unt, nebB, I(bpu, "Height")); link(unt, bpu.outputs[0], I(up, "Normal"))
finish(um, unt, uout, up); me.materials.append(um); UNKO_EM = I(up, "Emission Strength")
unko.shape_key_add(name="Basis")
def key(name, fn):
    kb = unko.shape_key_add(name=name, from_mix=False); kb.slider_min = -1.0; kb.slider_max = 1.5
    for i, v in enumerate(me.vertices): kb.data[i].co = fn(v.co.copy())
    return kb
def tsubure(c):
    h = c.z / H_UNKO; k = 1.12 * (1 + 0.05 * math.sin(math.pi * min(1, h * 1.6))); return Vector((c.x * k, c.y * k, c.z * 0.80))
def nobi(c): return Vector((c.x * 0.94, c.y * 0.94, c.z * 1.12))
def yure(axis):
    def f(c):
        h = c.z / H_UNKO; d = 0.30 * H_UNKO * h * h
        return Vector((c.x + d, c.y, c.z)) if axis == 0 else Vector((c.x, c.y + d, c.z))
    return f
KB = {"tsubure": key("tsubure", tsubure), "nobi": key("nobi", nobi), "yureX": key("yureX", yure(0)), "yureY": key("yureY", yure(1))}
for f, fr in enumerate(FRM, start=1):
    unko.location = fr["u"]; unko.keyframe_insert("location", frame=f)
    d = Vector(FRM[min(NF, f + 1) - 1]["u"]) - Vector(FRM[max(1, f - 1) - 1]["u"]); lean = 0.0
    if d.length > 0.02: lean = max(-0.35, min(0.35, 0.5 * math.hypot(d.x, d.y) / max(0.02, d.length) * (1 if d.z < 0 else 0.5)))
    unko.rotation_euler = (0.0, lean, fr["yaw"]); unko.keyframe_insert("rotation_euler", frame=f)
    s = fr["sq"]; yaw = fr["yaw"]
    KB["tsubure"].value = max(0.0, s) / 0.20; KB["nobi"].value = max(0.0, -s) / 0.12
    lx = (fr["wx"] * math.cos(yaw) + fr["wy"] * math.sin(yaw)) / 0.35; ly = (-fr["wx"] * math.sin(yaw) + fr["wy"] * math.cos(yaw)) / 0.35
    KB["yureX"].value = max(-1, min(1, lx)); KB["yureY"].value = max(-1, min(1, ly))
    for kb in KB.values(): kb.keyframe_insert("value", frame=f)
def anim_lin(owner):
    if owner.animation_data and owner.animation_data.action:
        for fc in owner.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
anim_lin(unko); anim_lin(me.shape_keys)
for ld in M["landings"]:
    for ff, vv in ((ld["fr"] - 1, 0.5), (ld["fr"], 1.6 + 1.5 * ld["vel"]), (ld["fr"] + 12, 0.5)):
        UNKO_EM.default_value = vv; UNKO_EM.keyframe_insert("default_value", frame=ff)
# グミの着地の閃光（小さな点光源が一瞬）
lamp = bpy.data.lights.new("flash", 'POINT'); lamp.energy = 0; lamp.color = (1.0, 0.85, 0.6); lamp.shadow_soft_size = 0.5
try: lamp.use_contact_shadow = True
except Exception: pass
fl = bpy.data.objects.new("flash", lamp); sc.collection.objects.link(fl); fl.parent = unko; fl.location = (0, 0, 0.35)
lamp.energy = 0; lamp.keyframe_insert("energy", frame=1)
for ld in M["landings"]:
    e = 60 + 500 * ld["vel"] * (2.0 if ld["kind"] in ("slam", "peak", "big") else 1.0)
    for ff, vv in ((ld["fr"] - 1, 0.0), (ld["fr"], e), (ld["fr"] + 9, 0.0)): lamp.energy = vv; lamp.keyframe_insert("energy", frame=ff)
stage("unko")

# ---------------- 光：天窓からの太陽（光の筋）・曇った空の光・霧 ----------------
sun = bpy.data.lights.new("sun", 'SUN'); sun.energy = 3.6; sun.color = (1.0, 0.85, 0.66); sun.angle = math.radians(1.5)
try: sun.use_contact_shadow = True; sun.shadow_cascade_max_distance = 120; sun.shadow_cascade_count = 4
except Exception: pass
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(52), 0.0, math.radians(-30))
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True; wn = wd.node_tree
bg = wn.nodes["Background"]; bg.inputs[0].default_value = (0.45, 0.55, 0.70, 1); bg.inputs[1].default_value = 0.10
vol = wn.nodes.new("ShaderNodeVolumeScatter"); vol.inputs["Density"].default_value = 0.010; vol.inputs["Anisotropy"].default_value = 0.55
wn.links.new(vol.outputs[0], wn.nodes["World Output"].inputs["Volume"])
# 大通りの弱い非常灯（緑がかった冷たい光）と、吹き抜けの冷たい補助光
for k, y in enumerate((-46.0, -34.0, -22.0)):
    l = bpy.data.lights.new("exit%d" % k, 'POINT'); l.energy = 60; l.color = (0.6, 1.0, 0.75); l.shadow_soft_size = 0.3
    o = bpy.data.objects.new("exit%d" % k, l); sc.collection.objects.link(o); o.location = (4.5 if k % 2 else -4.5, y, H - 0.9)
for k, (x, y, z) in enumerate(((0, 0, 28.0), (-14, 0, 20.0), (14, 0, 12.0))):
    l = bpy.data.lights.new("fill%d" % k, 'POINT'); l.energy = 500; l.color = (0.7, 0.8, 1.0); l.shadow_soft_size = 4.0
    o = bpy.data.objects.new("fill%d" % k, l); sc.collection.objects.link(o); o.location = (x, y, z)
# ほこりの粒（光の筋の中に浮く小さな球）
dm = bpy.data.meshes.new("dust"); vs = []; fs = []
for k in range(1400):
    x = rnd.uniform(VOID[0], VOID[1]); y = rnd.uniform(VOID[2], VOID[3]); z = rnd.uniform(0.3, ROOF - 1); r = rnd.uniform(0.006, 0.02)
    n = len(vs); vs += [(x - r, y, z), (x + r, y, z), (x, y, z + r * 1.6)]; fs.append((n, n + 1, n + 2))
for k in range(300):
    x = rnd.uniform(-5, 5); y = rnd.uniform(CONC[2], CONC[3]); z = rnd.uniform(0.3, H - 0.5); r = rnd.uniform(0.006, 0.015)
    n = len(vs); vs += [(x - r, y, z), (x + r, y, z), (x, y, z + r * 1.6)]; fs.append((n, n + 1, n + 2))
dm.from_pydata(vs, [], fs); dm.update(); dm.materials.append(mat_emit("dust", (1.0, 0.95, 0.85), 0.7))
do = bpy.data.objects.new("dust", dm); sc.collection.objects.link(do)
do.location = (0, 0, 0); do.keyframe_insert("location", frame=1); do.location = (0.3, 0.1, -0.6); do.keyframe_insert("location", frame=NF)
stage("lights")

# ---------------- カメラ：michi.json のとおり（見る先・ロール・ピント） ----------------
cam = bpy.data.cameras.new("cam"); cam.lens = M["lens"]; cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 36.0; cam.clip_end = 300
cam.dof.use_dof = True; cam.dof.aperture_fstop = 3.5; cam.dof.aperture_blades = 7
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co
cam.dof.focus_object = unko
for f, fr in enumerate(FRM, start=1):
    c = Vector(fr["cam"]); l = Vector(fr["look"]); d = (l - c).normalized()
    q = d.to_track_quat('-Z', 'Y'); rot = q.to_matrix() @ Matrix.Rotation(math.radians(fr["roll"]), 3, 'Z')
    co.location = c; co.rotation_euler = rot.to_euler(); co.keyframe_insert("location", frame=f); co.keyframe_insert("rotation_euler", frame=f)
anim_lin(co)
# レンズの癖：ほんの少しのゆがみ・色のにじみ・ビネット・グロー（合成ノード）
sc.use_nodes = True; cn = sc.node_tree
for n in list(cn.nodes): cn.nodes.remove(n)
rl = cn.nodes.new("CompositorNodeRLayers"); ld = cn.nodes.new("CompositorNodeLensdist"); ld.inputs["Distort"].default_value = 0.03; ld.inputs["Dispersion"].default_value = 0.012; ld.use_fit = True
gl = cn.nodes.new("CompositorNodeGlare"); gl.glare_type = 'FOG_GLOW'; gl.threshold = 0.9; gl.size = 7; gl.mix = -0.3
el = cn.nodes.new("CompositorNodeEllipseMask"); el.width = 1.25; el.height = 1.35
bl = cn.nodes.new("CompositorNodeBlur"); bl.size_x = 200; bl.size_y = 200; bl.filter_type = 'FAST_GAUSS'; bl.use_relative = False
mm = cn.nodes.new("CompositorNodeMath"); mm.operation = 'MULTIPLY_ADD'; mm.inputs[1].default_value = 0.55; mm.inputs[2].default_value = 0.45
mix = cn.nodes.new("CompositorNodeMixRGB"); mix.blend_type = 'MULTIPLY'
cb = cn.nodes.new("CompositorNodeColorBalance"); cb.correction_method = 'LIFT_GAMMA_GAIN'; cb.lift = (0.98, 0.99, 1.02); cb.gain = (1.03, 1.0, 0.96)
comp = cn.nodes.new("CompositorNodeComposite")
cn.links.new(rl.outputs["Image"], gl.inputs[0]); cn.links.new(gl.outputs[0], ld.inputs[0]); cn.links.new(ld.outputs[0], mix.inputs[1])
cn.links.new(el.outputs[0], bl.inputs[0]); cn.links.new(bl.outputs[0], mm.inputs[0]); cn.links.new(mm.outputs[0], mix.inputs[2]); cn.links.new(mix.outputs[0], cb.inputs["Image"]); cn.links.new(cb.outputs[0], comp.inputs[0])
stage("camera")

# ---------------- 深度画像（FLUX 深度制御の入力用）：UU_DEPTH=1 のとき、指定コマの深度を 0..1 に正規化した PNG で出す ----------------
if os.environ.get("UU_DEPTH") == "1":
    vl = sc.view_layers[0]; vl.use_pass_z = True
    for n in list(cn.nodes): cn.nodes.remove(n)
    rl = cn.nodes.new("CompositorNodeRLayers"); mr = cn.nodes.new("CompositorNodeMapRange"); mr.use_clamp = True
    mr.inputs["From Min"].default_value = 0.5; mr.inputs["From Max"].default_value = float(os.environ.get("UU_DEPTH_MAX", "60")); mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
    comp = cn.nodes.new("CompositorNodeComposite"); cn.links.new(rl.outputs["Depth"], mr.inputs[0]); cn.links.new(mr.outputs[0], comp.inputs[0])
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'BW'; sc.render.image_settings.color_depth = '8'
    try: sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    except Exception: pass
    sc.view_settings.exposure = 0.0; EV.taa_render_samples = 1; tryset(EV, use_bloom=False, use_motion_blur=False)
if os.environ.get("UU_SAVE"): bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "scene_v5.blend"))

# ---------------- 描画 ----------------
STEP = int(os.environ.get("UU_STEP", "1"))
if FR == "all": frames = range(1, NF + 1, STEP)
elif "-" in FR and "," not in FR: a_, b_ = FR.split("-"); frames = range(int(a_), int(b_) + 1, STEP)
else:
    frames = []
    for x in FR.split(","):
        if not x: continue
        if "-" in x: a_, b_ = x.split("-"); frames += list(range(int(a_), int(b_) + 1))
        else: frames.append(int(x))
for f in frames:
    path = os.path.join(OUT, ("d%04d.png" if os.environ.get("UU_DEPTH") == "1" else "f%04d.jpg") % f)
    if os.path.exists(path): continue
    t0 = time.time(); sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print("FRAME", f, round(time.time() - t0, 1), flush=True)
print("DONE", NF, flush=True)
