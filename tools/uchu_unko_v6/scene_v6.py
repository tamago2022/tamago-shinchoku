# -*- coding: utf-8 -*-
"""宇宙うんこ v6「灯籠の川」Blender 3.6 / Cycles CPU。
使い方: blender -b -P scene_v6.py -- <このフォルダ> <出力> "<コマ指定 0-11 か 0,120,200>"
環境変数: UU_PCT(解像度%) UU_SAMPLES UU_EXPO UU_NOBLUR
"""
import bpy, bmesh, math, os, sys, random, json, time
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
W, OUT, SPEC = argv[0], argv[1], argv[2]
sys.path.insert(0, W)
import plan as P

PCT = int(os.environ.get("UU_PCT", "100")); SAMPLES = int(os.environ.get("UU_SAMPLES", "128"))
EXPO = float(os.environ.get("UU_EXPO", "0.0"))
T0 = time.time()
def log(*a): print("STAGE", round(time.time() - T0, 1), *a, flush=True)

# ---------------- 初期化 ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = P.FPS; sc.frame_start = 0; sc.frame_end = P.NF

def node_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def N(nt, typ, **kw):
    n = nt.nodes.new(typ)
    for k, v in kw.items():
        if k in n.inputs: n.inputs[k].default_value = v
        else: setattr(n, k, v)
    return n

def L(nt, a, b): nt.links.new(a, b)

def principled(nt, **kw):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k, v in kw.items(): p.inputs[k].default_value = v
    return p

def obj_from_bm(name, bm, mat=None, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    if mat: me.materials.append(mat)
    return o

def box_bm(bm, cx, cy, cz, sx, sy, sz):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co.x = cx + v.co.x * sx; v.co.y = cy + v.co.y * sy; v.co.z = cz + v.co.z * sz
    return r

# ---------------- 材質 ----------------
# 水
m_water, nt, out = node_mat("water")
tc = N(nt, "ShaderNodeTexCoord");
mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.6, 3.5, 1.0)
L(nt, tc.outputs["Object"], mp.inputs["Vector"])
nz = N(nt, "ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9.0; nz.inputs["Detail"].default_value = 6; nz.inputs["Roughness"].default_value = 0.55
L(nt, mp.outputs["Vector"], nz.inputs["Vector"])
nz2 = N(nt, "ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 40.0; nz2.inputs["Detail"].default_value = 3
L(nt, mp.outputs["Vector"], nz2.inputs["Vector"])
# 着地の波紋：Σ A·exp(-((r - v·dt)/w)^2)·exp(-dt/τ)·[dt>0]
tval = N(nt, "ShaderNodeValue"); tval.name = "TIME"
ripple_sum = None
xyz = N(nt, "ShaderNodeSeparateXYZ"); L(nt, tc.outputs["Object"], xyz.inputs["Vector"])
RIP = []  # (frame, step_index)
for (lf, x, y, n) in P.LAND: RIP.append(lf)
ripple_nodes = []
for i, lf in enumerate(RIP):
    # 中心は Python で毎コマ更新するため Value ノードにする
    cxv = N(nt, "ShaderNodeValue"); cxv.name = "RCX%d" % i
    cyv = N(nt, "ShaderNodeValue"); cyv.name = "RCY%d" % i
    dx = N(nt, "ShaderNodeMath", operation="SUBTRACT"); L(nt, xyz.outputs["X"], dx.inputs[0]); L(nt, cxv.outputs[0], dx.inputs[1])
    dy = N(nt, "ShaderNodeMath", operation="SUBTRACT"); L(nt, xyz.outputs["Y"], dy.inputs[0]); L(nt, cyv.outputs[0], dy.inputs[1])
    cmb = N(nt, "ShaderNodeCombineXYZ"); L(nt, dx.outputs[0], cmb.inputs["X"]); L(nt, dy.outputs[0], cmb.inputs["Y"])
    ln = N(nt, "ShaderNodeVectorMath", operation="LENGTH"); L(nt, cmb.outputs[0], ln.inputs[0])
    dtv = N(nt, "ShaderNodeValue"); dtv.name = "RDT%d" % i   # 経過秒（負なら波なし）
    # 波の位相 sin(k(r - v dt)) × 包絡 exp(-((r - v dt)/w)^2) × exp(-dt/τ)
    vdt = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, dtv.outputs[0], vdt.inputs[0]); vdt.inputs[1].default_value = 0.42
    rr = N(nt, "ShaderNodeMath", operation="SUBTRACT"); L(nt, ln.outputs[0], rr.inputs[0]); L(nt, vdt.outputs[0], rr.inputs[1])
    ph = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, rr.outputs[0], ph.inputs[0]); ph.inputs[1].default_value = 70.0
    sn = N(nt, "ShaderNodeMath", operation="SINE"); L(nt, ph.outputs[0], sn.inputs[0])
    g1 = N(nt, "ShaderNodeMath", operation="DIVIDE"); L(nt, rr.outputs[0], g1.inputs[0]); g1.inputs[1].default_value = 0.10
    g2 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, g1.outputs[0], g2.inputs[0]); L(nt, g1.outputs[0], g2.inputs[1])
    g3 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, g2.outputs[0], g3.inputs[0]); g3.inputs[1].default_value = -1.0
    g4 = N(nt, "ShaderNodeMath", operation="EXPONENT"); L(nt, g3.outputs[0], g4.inputs[0])
    amp = N(nt, "ShaderNodeValue"); amp.name = "RAMP%d" % i   # exp(-dt/τ)·[dt>0]（Python が入れる）
    m1 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, sn.outputs[0], m1.inputs[0]); L(nt, g4.outputs[0], m1.inputs[1])
    m2 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, m1.outputs[0], m2.inputs[0]); L(nt, amp.outputs[0], m2.inputs[1])
    if ripple_sum is None: ripple_sum = m2
    else:
        a = N(nt, "ShaderNodeMath", operation="ADD"); L(nt, ripple_sum.outputs[0], a.inputs[0]); L(nt, m2.outputs[0], a.inputs[1]); ripple_sum = a
mixh = N(nt, "ShaderNodeMath", operation="MULTIPLY_ADD"); L(nt, nz.outputs["Fac"], mixh.inputs[0]); mixh.inputs[1].default_value = 1.0
L(nt, ripple_sum.outputs[0], mixh.inputs[2])
mixh2 = N(nt, "ShaderNodeMath", operation="MULTIPLY_ADD"); L(nt, nz2.outputs["Fac"], mixh2.inputs[0]); mixh2.inputs[1].default_value = 0.25; L(nt, mixh.outputs[0], mixh2.inputs[2])
bump = N(nt, "ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.22; bump.inputs["Distance"].default_value = 0.02
L(nt, mixh2.outputs[0], bump.inputs["Height"])
pw = principled(nt, **{"Base Color": (0.004, 0.009, 0.012, 1), "Roughness": 0.035, "Specular": 0.5, "IOR": 1.333})
L(nt, bump.outputs["Normal"], pw.inputs["Normal"])
L(nt, pw.outputs[0], out.inputs["Surface"])
WATER_NT = nt

# 和紙（灯籠の紙）：拡散＋透過＋ごく弱い発光、繊維のむら
def mat_paper(name, tint=(1.0, 0.86, 0.66)):
    m, nt, out = node_mat(name)
    tc = N(nt, "ShaderNodeTexCoord")
    nzp = N(nt, "ShaderNodeTexNoise"); nzp.inputs["Scale"].default_value = 60.0; nzp.inputs["Detail"].default_value = 8
    L(nt, tc.outputs["Object"], nzp.inputs["Vector"])
    ramp = N(nt, "ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[0].color = (tint[0] * 0.80, tint[1] * 0.74, tint[2] * 0.60, 1); ramp.color_ramp.elements[1].color = (*tint, 1)
    L(nt, nzp.outputs["Fac"], ramp.inputs["Fac"])
    dif = N(nt, "ShaderNodeBsdfDiffuse"); L(nt, ramp.outputs["Color"], dif.inputs["Color"])
    tr = N(nt, "ShaderNodeBsdfTranslucent"); L(nt, ramp.outputs["Color"], tr.inputs["Color"])
    mx = N(nt, "ShaderNodeMixShader"); mx.inputs["Fac"].default_value = 0.62
    L(nt, dif.outputs[0], mx.inputs[1]); L(nt, tr.outputs[0], mx.inputs[2])
    L(nt, mx.outputs[0], out.inputs["Surface"])
    return m
m_paper = mat_paper("paper", (1.0, 0.66, 0.36))

m_wood, nt, out = node_mat("wood")
tc = N(nt, "ShaderNodeTexCoord"); wv = N(nt, "ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 18; wv.inputs["Distortion"].default_value = 6
L(nt, tc.outputs["Object"], wv.inputs["Vector"])
wr = N(nt, "ShaderNodeValToRGB"); wr.color_ramp.elements[0].color = (0.035, 0.016, 0.008, 1); wr.color_ramp.elements[1].color = (0.11, 0.05, 0.022, 1)
L(nt, wv.outputs["Fac"], wr.inputs["Fac"])
pwd = principled(nt, **{"Roughness": 0.55, "Specular": 0.35}); L(nt, wr.outputs["Color"], pwd.inputs["Base Color"])
L(nt, pwd.outputs[0], out.inputs["Surface"])

# 宇宙うんこの肌：濃紺の地＋星雲＋星粒＋クリアコート（灯籠の光を映す）
m_unko, nt, out = node_mat("unko")
tc = N(nt, "ShaderNodeTexCoord")
nb = N(nt, "ShaderNodeTexNoise"); nb.inputs["Scale"].default_value = 7.0; nb.inputs["Detail"].default_value = 10; nb.inputs["Distortion"].default_value = 1.2
L(nt, tc.outputs["Object"], nb.inputs["Vector"])
neb = N(nt, "ShaderNodeValToRGB"); cr = neb.color_ramp
cr.elements[0].position = 0.36; cr.elements[0].color = (0.004, 0.006, 0.030, 1)
e = cr.elements.new(0.50); e.color = (0.012, 0.025, 0.090, 1)
e = cr.elements.new(0.60); e.color = (0.010, 0.110, 0.170, 1)
cr.elements[-1].position = 0.75; cr.elements[-1].color = (0.36, 0.08, 0.26, 1)
L(nt, nb.outputs["Fac"], neb.inputs["Fac"])
vor = N(nt, "ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 120.0; vor.inputs["Randomness"].default_value = 1.0
L(nt, tc.outputs["Object"], vor.inputs["Vector"])
st = N(nt, "ShaderNodeMath", operation="LESS_THAN"); L(nt, vor.outputs["Distance"], st.inputs[0]); st.inputs[1].default_value = 0.045
vor2 = N(nt, "ShaderNodeTexVoronoi"); vor2.inputs["Scale"].default_value = 28.0
L(nt, tc.outputs["Object"], vor2.inputs["Vector"])
st2 = N(nt, "ShaderNodeMath", operation="LESS_THAN"); L(nt, vor2.outputs["Distance"], st2.inputs[0]); st2.inputs[1].default_value = 0.022
sts = N(nt, "ShaderNodeMath", operation="ADD"); L(nt, st.outputs[0], sts.inputs[0]); L(nt, st2.outputs[0], sts.inputs[1])
stc = N(nt, "ShaderNodeMixRGB", blend_type="MULTIPLY"); stc.inputs["Fac"].default_value = 1.0
L(nt, vor.outputs["Color"], stc.inputs["Color1"]); stc.inputs["Color2"].default_value = (1, 1, 1, 1)
starcol = N(nt, "ShaderNodeMixRGB"); starcol.inputs["Color1"].default_value = (0.75, 0.85, 1.0, 1); starcol.inputs["Color2"].default_value = (1.0, 0.85, 0.7, 1)
L(nt, vor.outputs["Color"], starcol.inputs["Fac"])
glow = N(nt, "ShaderNodeValue"); glow.name = "GLOW"; glow.outputs[0].default_value = 1.0
ems = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, sts.outputs[0], ems.inputs[0]); ems.inputs[1].default_value = 7.0
ems2 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, ems.outputs[0], ems2.inputs[0]); L(nt, glow.outputs[0], ems2.inputs[1])
neb_e = N(nt, "ShaderNodeMixRGB", blend_type="ADD"); neb_e.inputs["Fac"].default_value = 1.0
nebs = N(nt, "ShaderNodeMixRGB", blend_type="MULTIPLY"); nebs.inputs["Fac"].default_value = 1.0; L(nt, neb.outputs["Color"], nebs.inputs["Color1"]); nebs.inputs["Color2"].default_value = (0.9, 0.9, 0.9, 1)
emc = N(nt, "ShaderNodeMixRGB", blend_type="MIX"); L(nt, sts.outputs[0], emc.inputs["Fac"])
L(nt, nebs.outputs["Color"], emc.inputs["Color1"]); L(nt, starcol.outputs["Color"], emc.inputs["Color2"])
emsum = N(nt, "ShaderNodeMath", operation="ADD"); L(nt, ems2.outputs[0], emsum.inputs[0]); emsum.inputs[1].default_value = 0.0
neb_strength = N(nt, "ShaderNodeMath", operation="MULTIPLY_ADD"); L(nt, glow.outputs[0], neb_strength.inputs[0]); neb_strength.inputs[1].default_value = 0.45; L(nt, ems2.outputs[0], neb_strength.inputs[2])
pu = principled(nt, **{"Roughness": 0.22, "Specular": 0.6, "Clearcoat": 1.0, "Clearcoat Roughness": 0.03, "Subsurface": 0.0})
ao = N(nt, "ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.03
aom = N(nt, "ShaderNodeMixRGB", blend_type="MULTIPLY"); aom.inputs["Fac"].default_value = 1.0
L(nt, neb.outputs["Color"], aom.inputs["Color1"]); L(nt, ao.outputs["AO"], aom.inputs["Color2"])
L(nt, aom.outputs["Color"], pu.inputs["Base Color"])
L(nt, emc.outputs["Color"], pu.inputs["Emission"])
L(nt, neb_strength.outputs[0], pu.inputs["Emission Strength"])
bz = N(nt, "ShaderNodeBump"); bz.inputs["Strength"].default_value = 0.08; bz.inputs["Distance"].default_value = 0.004
L(nt, nb.outputs["Fac"], bz.inputs["Height"]); L(nt, bz.outputs["Normal"], pu.inputs["Normal"])
L(nt, pu.outputs[0], out.inputs["Surface"])
UNKO_NT = nt

# 石垣（対岸）
m_stone, nt, out = node_mat("stone")
tc = N(nt, "ShaderNodeTexCoord"); br = N(nt, "ShaderNodeTexBrick")
br.inputs["Scale"].default_value = 4.0; br.inputs["Color1"].default_value = (0.05, 0.055, 0.06, 1); br.inputs["Color2"].default_value = (0.03, 0.033, 0.04, 1); br.inputs["Mortar"].default_value = (0.012, 0.012, 0.014, 1)
L(nt, tc.outputs["Object"], br.inputs["Vector"])
ps = principled(nt, **{"Roughness": 0.8}); L(nt, br.outputs["Color"], ps.inputs["Base Color"]); L(nt, ps.outputs[0], out.inputs["Surface"])

# 家の壁と窓
def mat_house(name, seed):
    m, nt, out = node_mat(name)
    tc = N(nt, "ShaderNodeTexCoord"); sxyz = N(nt, "ShaderNodeSeparateXYZ"); L(nt, tc.outputs["Object"], sxyz.inputs[0])
    def cell(axis_out, size, lo, hi):
        d = N(nt, "ShaderNodeMath", operation="DIVIDE"); L(nt, axis_out, d.inputs[0]); d.inputs[1].default_value = size
        fr = N(nt, "ShaderNodeMath", operation="FRACT"); L(nt, d.outputs[0], fr.inputs[0])
        a = N(nt, "ShaderNodeMath", operation="GREATER_THAN"); L(nt, fr.outputs[0], a.inputs[0]); a.inputs[1].default_value = lo
        b = N(nt, "ShaderNodeMath", operation="LESS_THAN"); L(nt, fr.outputs[0], b.inputs[0]); b.inputs[1].default_value = hi
        m_ = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, a.outputs[0], m_.inputs[0]); L(nt, b.outputs[0], m_.inputs[1])
        fl = N(nt, "ShaderNodeMath", operation="FLOOR"); L(nt, d.outputs[0], fl.inputs[0])
        return m_, fl
    # x と y の和で横方向（家は x に並ぶので x を主に）
    sx_, flx = cell(sxyz.outputs["X"], 0.21 + 0.03 * seed, 0.28, 0.72)
    sz_, flz = cell(sxyz.outputs["Z"], 0.30, 0.32, 0.78)
    win = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, sx_.outputs[0], win.inputs[0]); L(nt, sz_.outputs[0], win.inputs[1])
    cmb = N(nt, "ShaderNodeCombineXYZ"); L(nt, flx.outputs[0], cmb.inputs["X"]); L(nt, flz.outputs[0], cmb.inputs["Y"]); cmb.inputs["Z"].default_value = seed * 7.1
    wn = N(nt, "ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"; L(nt, cmb.outputs[0], wn.inputs["Vector"])
    lit = N(nt, "ShaderNodeMath", operation="GREATER_THAN"); L(nt, wn.outputs["Value"], lit.inputs[0]); lit.inputs[1].default_value = 0.58
    wl = N(nt, "ShaderNodeMath", operation="MULTIPLY"); L(nt, win.outputs[0], wl.inputs[0]); L(nt, lit.outputs[0], wl.inputs[1])
    warm = N(nt, "ShaderNodeMixRGB"); L(nt, wn.outputs["Color"], warm.inputs["Fac"]); warm.inputs["Color1"].default_value = (1.0, 0.50, 0.18, 1); warm.inputs["Color2"].default_value = (1.0, 0.70, 0.36, 1)
    wall = principled(nt, **{"Base Color": (0.035, 0.030, 0.032, 1), "Roughness": 0.8})
    unlit = principled(nt, **{"Base Color": (0.01, 0.012, 0.016, 1), "Roughness": 0.15})
    em = N(nt, "ShaderNodeEmission"); L(nt, warm.outputs["Color"], em.inputs["Color"]); em.inputs["Strength"].default_value = 5.0
    m1 = N(nt, "ShaderNodeMixShader"); L(nt, win.outputs[0], m1.inputs["Fac"]); L(nt, wall.outputs[0], m1.inputs[1]); L(nt, unlit.outputs[0], m1.inputs[2])
    m2 = N(nt, "ShaderNodeMixShader"); L(nt, wl.outputs[0], m2.inputs["Fac"]); L(nt, m1.outputs[0], m2.inputs[1]); L(nt, em.outputs[0], m2.inputs[2])
    L(nt, m2.outputs[0], out.inputs["Surface"])
    return m
m_houses = [mat_house("house%d" % i, i) for i in range(3)]
m_roof, nt, out = node_mat("roof")
pr = principled(nt, **{"Base Color": (0.025, 0.03, 0.045, 1), "Roughness": 0.5, "Specular": 0.4}); L(nt, pr.outputs[0], out.inputs["Surface"])

m_lamp, nt, out = node_mat("lamp")
em = N(nt, "ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.62, 0.28, 1); em.inputs["Strength"].default_value = 30
L(nt, em.outputs[0], out.inputs["Surface"])

m_moon, nt, out = node_mat("moon")
tc = N(nt, "ShaderNodeTexCoord"); mn = N(nt, "ShaderNodeTexNoise"); mn.inputs["Scale"].default_value = 3.0; mn.inputs["Detail"].default_value = 8
L(nt, tc.outputs["Object"], mn.inputs["Vector"])
mr = N(nt, "ShaderNodeValToRGB"); mr.color_ramp.elements[0].position = 0.42; mr.color_ramp.elements[0].color = (0.42, 0.44, 0.48, 1)
mr.color_ramp.elements[1].position = 0.65; mr.color_ramp.elements[1].color = (1.0, 0.98, 0.92, 1)
L(nt, mn.outputs["Fac"], mr.inputs["Fac"])
em = N(nt, "ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.5; L(nt, mr.outputs["Color"], em.inputs["Color"])
L(nt, em.outputs[0], out.inputs["Surface"])
log("materials")

# ---------------- 世界（夜空・星） ----------------
wd = bpy.data.worlds.new("night"); sc.world = wd; wd.use_nodes = True
nt = wd.node_tree; nt.nodes.clear()
wo = N(nt, "ShaderNodeOutputWorld")
tc = N(nt, "ShaderNodeTexCoord")
sxyz = N(nt, "ShaderNodeSeparateXYZ"); L(nt, tc.outputs["Generated"], sxyz.inputs[0])
grad = N(nt, "ShaderNodeValToRGB"); g = grad.color_ramp
g.elements[0].position = 0.0; g.elements[0].color = (0.020, 0.040, 0.060, 1)
g.elements[1].position = 0.45; g.elements[1].color = (0.0035, 0.008, 0.020, 1)
e = g.elements.new(0.06); e.color = (0.030, 0.055, 0.075, 1)
L(nt, sxyz.outputs["Z"], grad.inputs["Fac"])
import numpy as np
SW, SH = 4096, 2048
img = bpy.data.images.new("stars", SW, SH, float_buffer=True)
buf = np.zeros((SH, SW, 4), np.float32); buf[..., 3] = 1
rs_ = np.random.default_rng(9)
ns = 4200
ys_ = rs_.integers(SH // 2 + 12, SH - 2, ns); xs_ = rs_.integers(1, SW - 1, ns)
br_ = (rs_.pareto(2.2, ns) + 0.25) * 0.9
tint = rs_.uniform(0, 1, ns)
for (yy, xx, bb, tt) in zip(ys_, xs_, br_, tint):
    c = np.array([0.85 + 0.15 * tt, 0.9, 1.0 - 0.2 * tt]) * min(bb, 25)
    buf[yy, xx, :3] += c
    if bb > 2.0:
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): buf[yy + dy, xx + dx, :3] += c * 0.25
img.pixels.foreach_set(buf.ravel()); img.pack()
env = N(nt, "ShaderNodeTexEnvironment"); env.image = img; env.interpolation = "Closest"
add = N(nt, "ShaderNodeMixRGB", blend_type="ADD"); add.inputs["Fac"].default_value = 1.0
L(nt, grad.outputs["Color"], add.inputs["Color1"])
smul = N(nt, "ShaderNodeMixRGB", blend_type="MULTIPLY"); smul.inputs["Fac"].default_value = 1.0; smul.inputs["Color2"].default_value = (0.35, 0.35, 0.35, 1)
L(nt, env.outputs["Color"], smul.inputs["Color1"]); L(nt, smul.outputs["Color"], add.inputs["Color2"])
bg = N(nt, "ShaderNodeBackground"); bg.inputs["Strength"].default_value = 1.0
L(nt, add.outputs["Color"], bg.inputs["Color"]); L(nt, bg.outputs[0], wo.inputs["Surface"])

# ---------------- 物 ----------------
# 水面
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
water = obj_from_bm("water", bm, m_water)

# 灯籠の型（台・柱・紙の箱・ふた）— 実体は共有メッシュ
def lantern_mesh():
    bm = bmesh.new()
    box_bm(bm, 0, 0, P.BASE_Z0 + P.BASE_T / 2, P.BASE_W, P.BASE_W, P.BASE_T)          # 台
    s = P.BOX_W / 2
    for (x, y) in [(s, s), (-s, s), (s, -s), (-s, -s)]:
        box_bm(bm, x, y, P.BOX_Z0 + P.BOX_H / 2, 0.014, 0.014, P.BOX_H)                 # 柱
    box_bm(bm, 0, 0, P.BOX_Z0 + P.BOX_H + 0.006, P.BOX_W + 0.02, P.BOX_W + 0.02, 0.012)  # ふたの枠
    me = bpy.data.meshes.new("lantern_wood"); bm.to_mesh(me); bm.free(); me.materials.append(m_wood)
    bm = bmesh.new()
    box_bm(bm, 0, 0, P.BOX_Z0 + P.BOX_H / 2, P.BOX_W - 0.006, P.BOX_W - 0.006, P.BOX_H - 0.002)
    # 横の桟（紙に影を落とす）
    me2 = bpy.data.meshes.new("lantern_paper"); bm.to_mesh(me2); bm.free(); me2.materials.append(m_paper)
    bm = bmesh.new()
    for z in (P.BOX_Z0 + P.BOX_H * 0.36, P.BOX_Z0 + P.BOX_H * 0.70):
        for (x, y, sx, sy) in [(0, s + 0.003, P.BOX_W, 0.008), (0, -s - 0.003, P.BOX_W, 0.008), (s + 0.003, 0, 0.008, P.BOX_W), (-s - 0.003, 0, 0.008, P.BOX_W)]:
            box_bm(bm, x, y, z, sx, sy, 0.008)
    me3 = bpy.data.meshes.new("lantern_bar"); bm.to_mesh(me3); bm.free(); me3.materials.append(m_wood)
    return me, me2, me3
me_wood, me_paper, me_bar = lantern_mesh()

LANT = P.build()
log("lanterns", len(LANT))
rnd = random.Random(3)
LOBJ = []
for l in LANT:
    root = bpy.data.objects.new("L_" + l["id"], None); sc.collection.objects.link(root)
    for me in (me_wood, me_paper, me_bar):
        o = bpy.data.objects.new(me.name + "_" + l["id"], me); sc.collection.objects.link(o); o.parent = root
    lt = bpy.data.lights.new("lt_" + l["id"], "POINT"); lt.shadow_soft_size = 0.05
    lt.color = (1.0, 0.46 + rnd.uniform(-0.04, 0.05), 0.16 + rnd.uniform(-0.03, 0.03))
    base_w = rnd.uniform(1.0, 1.6)
    lt.energy = base_w
    lo = bpy.data.objects.new("lt_" + l["id"], lt); sc.collection.objects.link(lo); lo.parent = root
    lo.location = (0, 0, P.BOX_Z0 + P.BOX_H * 0.38)
    LOBJ.append((l, root, lt, base_w, rnd.uniform(0, 6.28)))

# 宇宙うんこ（ソフトクリーム型のうず：円を螺旋に沿って掃く）
def unko_mesh():
    bm = bmesh.new()
    turns = 2.55; nu = 180; nv = 20
    rings = []
    for i in range(nu + 1):
        u = i / nu
        ang = 2 * math.pi * turns * u
        R = 0.070 * (1 - u) ** 0.9 + 0.003
        z = 0.034 + 0.168 * u
        r = 0.029 * (1 - u) ** 0.6 + 0.009
        if u > 0.93: r *= max(0.05, (1 - u) / 0.07) ** 0.5
        c = Vector((R * math.cos(ang), R * math.sin(ang), z))
        tng = Vector((-math.sin(ang), math.cos(ang), 0.12)).normalized()
        nrm = Vector((math.cos(ang), math.sin(ang), 0)); bnm = tng.cross(nrm).normalized(); nrm = bnm.cross(tng).normalized()
        ring = []
        for j in range(nv):
            a = 2 * math.pi * j / nv
            ring.append(bm.verts.new(c + nrm * (r * math.cos(a)) + bnm * (r * 1.05 * math.sin(a))))
        rings.append(ring)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % nv], rings[i + 1][(j + 1) % nv], rings[i + 1][j]))
    # 底の丸い台座（つぶれた球）
    r2 = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.074)
    for v in r2["verts"]:
        v.co.z = 0.030 + v.co.z * 0.40
        if v.co.z < 0.004: v.co.z = 0.004 + (v.co.z - 0.004) * 0.15
    # 端のふた
    bmesh.ops.contextual_create(bm, geom=rings[0])
    me = bpy.data.meshes.new("unko"); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return me
unko = bpy.data.objects.new("unko", unko_mesh()); sc.collection.objects.link(unko); unko.data.materials.append(m_unko)
sub = unko.modifiers.new("sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 2

# 対岸：石垣・家並み・街灯
rnd = random.Random(11)
bm = bmesh.new(); box_bm(bm, 0, 10.4, 0.25, 60, 1.2, 0.7); bank = obj_from_bm("bank", bm, m_stone)
bm = bmesh.new(); box_bm(bm, 0, 11.6, 0.55, 60, 1.4, 0.10); obj_from_bm("street", bm, m_roof)
x = -22.0
houses = [bpy.data.meshes.new("h%d" % i) for i in range(3)]
bms = [bmesh.new() for _ in range(3)]; bmr = bmesh.new()
while x < 22:
    w = rnd.uniform(0.6, 1.2); h = rnd.uniform(0.6, 1.4); d = rnd.uniform(0.9, 1.4)
    k = rnd.randrange(3); y = 11.3 + rnd.uniform(0, 0.5)
    box_bm(bms[k], x + w / 2, y + d / 2, 0.6 + h / 2, w * 0.96, d, h)
    # 切妻屋根
    rh = rnd.uniform(0.25, 0.5); z0 = 0.6 + h; x0 = x + w / 2
    vs = [bmr.verts.new(v) for v in [(x0 - w * 0.53, y - 0.05, z0), (x0 + w * 0.53, y - 0.05, z0), (x0 + w * 0.53, y + d + 0.05, z0), (x0 - w * 0.53, y + d + 0.05, z0), (x0, y - 0.05, z0 + rh), (x0, y + d + 0.05, z0 + rh)]]
    bmr.faces.new((vs[0], vs[1], vs[4])); bmr.faces.new((vs[3], vs[5], vs[2])); bmr.faces.new((vs[0], vs[4], vs[5], vs[3])); bmr.faces.new((vs[1], vs[2], vs[5], vs[4]))
    x += w + rnd.uniform(0.02, 0.25)
for k in range(3):
    obj_from_bm("houses%d" % k, bms[k], m_houses[k])
obj_from_bm("roofs", bmr, m_roof)
# 2列目（高い・遠い）
bm2 = bmesh.new(); x = -26
while x < 26:
    w = rnd.uniform(1.0, 2.0); h = rnd.uniform(1.4, 2.6)
    box_bm(bm2, x + w / 2, 14.0 + rnd.uniform(0, 1.0), 0.6 + h / 2, w * 0.95, 1.2, h); x += w + rnd.uniform(0.1, 0.6)
obj_from_bm("houses_far", bm2, m_houses[1])
# 街灯
for i in range(13):
    x = -12 + i * 2.0 + rnd.uniform(-0.3, 0.3)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.07)
    for v in bm.verts: v.co += Vector((x, 10.9, 1.25))
    obj_from_bm("lamp%d" % i, bm, m_lamp)
    bm = bmesh.new(); box_bm(bm, x, 10.9, 0.85, 0.03, 0.03, 0.75); obj_from_bm("pole%d" % i, bm, m_roof)
    lt = bpy.data.lights.new("sl%d" % i, "POINT"); lt.energy = 25; lt.color = (1.0, 0.6, 0.3); lt.shadow_soft_size = 0.1
    lo = bpy.data.objects.new("sl%d" % i, lt); sc.collection.objects.link(lo); lo.location = (x, 10.75, 1.2)
# 月（左上の空）
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=2.4)
moon = obj_from_bm("moon", bm, m_moon, smooth=True); moon.location = (-20, 52, 23)
moon.visible_shadow = False
# 月明かり（弱い・青白・左奥から）
sun = bpy.data.lights.new("moonlight", "SUN"); sun.energy = 0.06; sun.color = (0.6, 0.75, 1.0); sun.angle = math.radians(1.0)
so = bpy.data.objects.new("moonlight", sun); sc.collection.objects.link(so)
so.rotation_euler = (Vector((20, -52, -23)).to_track_quat("-Z", "Y")).to_euler()
log("objects")

# ---------------- 動き（キーフレームを直接書く） ----------------
def kf(obj_or_id, path, idx, values):
    ad = obj_or_id.animation_data or obj_or_id.animation_data_create()
    if ad.action is None: ad.action = bpy.data.actions.new(obj_or_id.name + "_act")
    fc = ad.action.fcurves.find(path, index=idx) or ad.action.fcurves.new(path, index=idx)
    fc.keyframe_points.add(len(values))
    co = []
    for f, v in values: co += [f, v]
    fc.keyframe_points.foreach_set("co", co)
    for k in fc.keyframe_points: k.interpolation = "LINEAR"
    fc.update()

FR = list(range(0, P.NF + 1))
ON = {l["id"]: P.light_on_frame(l, LANT) for l in LANT}
for (l, root, lt, base_w, ph) in LOBJ:
    xs, ys, zs, rz, rx, en = [], [], [], [], [], []
    for f in FR:
        x, y = P.lantern_xy(l, f); z = P.lantern_z(l, f); t = f / P.FPS
        xs.append((f, x)); ys.append((f, y)); zs.append((f, z))
        rz.append((f, ph + 0.05 * math.sin(0.4 * t + ph)))
        rx.append((f, 0.025 * math.sin(1.1 * t + ph)))
        flick = 1 + 0.06 * math.sin(13 * t + ph) + 0.04 * math.sin(23 * t + 2 * ph)
        flash = 0.0
        for lf in l.get("lands", []):
            dt = (f - lf) / P.FPS
            if dt >= 0: flash += 2.2 * math.exp(-dt / 0.45)
        on = ON[l["id"]]; dt = (f - on) / P.FPS
        lvl = 0.035 if dt < 0 else min(1.0, 0.035 + (dt / 0.35) ** 1.5) * (1 + 0.5 * math.exp(-dt / 0.25) * (dt > 0.2))
        flick *= lvl
        en.append((f, base_w * (flick + flash)))
    kf(root, "location", 0, xs); kf(root, "location", 1, ys); kf(root, "location", 2, zs)
    kf(root, "rotation_euler", 2, rz); kf(root, "rotation_euler", 0, rx)
    kf(lt, "energy", 0, en)

ux, uy, uz, usx, usz, urz = [], [], [], [], [], []
for f in FR:
    (x, y, z), (sx, sz), spin = P.unko_at(f, LANT)
    ux.append((f, x)); uy.append((f, y)); uz.append((f, z)); usx.append((f, sx)); usz.append((f, sz)); urz.append((f, 0.6 + spin))
kf(unko, "location", 0, ux); kf(unko, "location", 1, uy); kf(unko, "location", 2, uz)
kf(unko, "scale", 0, [(f, v * P.US) for f, v in usx]); kf(unko, "scale", 1, [(f, v * P.US) for f, v in usx]); kf(unko, "scale", 2, [(f, v * P.US) for f, v in usz]); kf(unko, "rotation_euler", 2, urz)

# 着地のたびに、うんこから小さな星のかけらが立ちのぼる
m_spark, nt, out = node_mat("spark")
em = N(nt, "ShaderNodeEmission"); em.inputs["Strength"].default_value = 14.0
oi = N(nt, "ShaderNodeObjectInfo"); rmp = N(nt, "ShaderNodeValToRGB")
rmp.color_ramp.elements[0].color = (0.65, 0.85, 1.0, 1); rmp.color_ramp.elements[1].color = (1.0, 0.78, 0.5, 1)
L(nt, oi.outputs["Random"], rmp.inputs["Fac"]); L(nt, rmp.outputs["Color"], em.inputs["Color"]); L(nt, em.outputs[0], out.inputs["Surface"])
bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.0065)
me_sp = bpy.data.meshes.new("spark"); bm.to_mesh(me_sp); bm.free(); me_sp.materials.append(m_spark)
rs = random.Random(21)
for i, (lf, _, _, _) in enumerate(P.LAND):
    (bx, by, bz), _, _ = P.unko_at(lf, LANT)
    cnt = 16 if i == len(P.LAND) - 1 else 10
    for k in range(cnt):
        o = bpy.data.objects.new("sp%d_%d" % (i, k), me_sp); sc.collection.objects.link(o)
        o.visible_shadow = False
        a = rs.uniform(0, 6.28); hv = rs.uniform(0.04, 0.16); vz = rs.uniform(0.22, 0.48); life = rs.uniform(1.4, 2.6)
        x0 = bx + 0.05 * math.cos(a); y0 = by + 0.05 * math.sin(a); z0 = bz + rs.uniform(0.10, 0.22)
        sz0 = rs.uniform(0.6, 1.4)
        xs, ys, zs, ss = [], [], [], []
        for f in FR:
            dt = (f - lf) / P.FPS
            if dt < 0 or dt > life:
                xs.append((f, x0)); ys.append((f, y0)); zs.append((f, z0)); ss.append((f, 0.0)); continue
            dmp = (1 - math.exp(-dt / 0.6)) * 0.6
            x = x0 + hv * math.cos(a) * dmp + 0.03 * math.sin(3 * dt + k)
            y = y0 + hv * math.sin(a) * dmp + 0.03 * math.cos(2.4 * dt + k)
            z = z0 + vz * dmp + 0.10 * dt
            sc_ = sz0 * min(1, dt / 0.08) * max(0, 1 - dt / life) ** 0.7 * (0.8 + 0.2 * math.sin(20 * dt + k))
            xs.append((f, x)); ys.append((f, y)); zs.append((f, z)); ss.append((f, sc_))
        kf(o, "location", 0, xs); kf(o, "location", 1, ys); kf(o, "location", 2, zs)
        for ax in range(3): kf(o, "scale", ax, ss)

rim = bpy.data.lights.new("rim", "AREA"); rim.size = 0.25; rim.energy = 11.0; rim.color = (0.70, 0.82, 1.0)
rimo = bpy.data.objects.new("rim", rim); sc.collection.objects.link(rimo)
# カメラ
cam_d = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.sensor_fit = "AUTO"; cam_d.sensor_width = 36
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = float(os.environ.get("UU_FSTOP", "1.8")); cam_d.dof.aperture_blades = 7
cam_d.clip_start = 0.02; cam_d.clip_end = 200
CAMS = P.camera_track(LANT)
cl = [[], [], []]; cr = [[], [], []]; fl = []; fd = []
for f in FR:
    c = CAMS[f]; loc = Vector(c["loc"]); look = Vector(c["look"])
    q = (look - loc).to_track_quat("-Z", "Y"); e = q.to_euler()
    for i in range(3): cl[i].append((f, loc[i])); cr[i].append((f, e[i]))
    fl.append((f, c["lens"]))
    (x, y, z), _, _ = P.unko_at(f, LANT)
    fd.append((f, (Vector((x, y, z + 0.09)) - loc).length))
for i in range(3): kf(cam, "location", i, cl[i]); kf(cam, "rotation_euler", i, cr[i])
rl_ = [[], [], []]; rr_ = [[], [], []]
for f in FR:
    (x, y, z), _, _ = P.unko_at(f, LANT); u = Vector((x, y, z + 0.13))
    c = Vector(CAMS[f]["loc"]); d = (u - c); d.z = 0; d.normalize()
    pos = u + d * 0.55 + Vector((0, 0, 0.32))
    e = (u - pos).to_track_quat("-Z", "Y").to_euler()
    for i in range(3): rl_[i].append((f, pos[i])); rr_[i].append((f, e[i]))
for i in range(3): kf(rimo, "location", i, rl_[i]); kf(rimo, "rotation_euler", i, rr_[i])
kf(cam_d, "lens", 0, fl); kf(cam_d, "dof.focus_distance", 0, fd)
# 回転の連続性（オイラーの飛び）を直す
for fc in list(cam.animation_data.action.fcurves) + list(rimo.animation_data.action.fcurves):
    if fc.data_path == "rotation_euler":
        pts = fc.keyframe_points; prev = None
        for k in pts:
            if prev is not None:
                while k.co[1] - prev > math.pi: k.co[1] -= 2 * math.pi
                while k.co[1] - prev < -math.pi: k.co[1] += 2 * math.pi
            prev = k.co[1]
        fc.update()

def per_frame(f):
    """シェーダーの値（波紋の中心・経過・強さ、うんこの光）をコマごとに入れる"""
    t = f / P.FPS
    steps = sorted([l for l in LANT if "step" in l], key=lambda l: l["step"])
    for i, (lf, _, _, _) in enumerate(P.LAND):
        x, y = P.lantern_xy(steps[i], lf)
        dt = (f - lf) / P.FPS
        WATER_NT.nodes["RCX%d" % i].outputs[0].default_value = x
        WATER_NT.nodes["RCY%d" % i].outputs[0].default_value = y
        WATER_NT.nodes["RDT%d" % i].outputs[0].default_value = max(dt, 0) + 0.18
        WATER_NT.nodes["RAMP%d" % i].outputs[0].default_value = (0.9 * math.exp(-dt / 1.3)) if dt >= 0 else 0.0
    g = 1.0
    for (lf, _, _, _) in P.LAND:
        dt = (f - lf) / P.FPS
        if dt >= 0: g += 1.6 * math.exp(-dt / 0.30)
    UNKO_NT.nodes["GLOW"].outputs[0].default_value = g

# ---------------- 描画設定 ----------------
r = sc.render
r.engine = "CYCLES"; sc.cycles.device = "CPU"
r.resolution_x = 720; r.resolution_y = 1280; r.resolution_percentage = PCT
sc.cycles.samples = SAMPLES; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.025
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 3; sc.cycles.transmission_bounces = 6; sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False; sc.cycles.blur_glossy = 1.0
sc.cycles.sample_clamp_indirect = 6.0
try: sc.cycles.use_light_tree = True
except Exception: pass
r.use_motion_blur = os.environ.get("UU_NOBLUR", "0") != "1"; r.motion_blur_shutter = 0.30
sc.view_settings.view_transform = "Filmic"; sc.view_settings.look = "Medium High Contrast"; sc.view_settings.exposure = EXPO
r.image_settings.file_format = "JPEG"; r.image_settings.quality = 93
r.film_transparent = False
# グレア（光のにじみ）をコンポジットで
sc.use_nodes = True; ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers"); co = ct.nodes.new("CompositorNodeComposite")
gl = ct.nodes.new("CompositorNodeGlare"); gl.glare_type = "FOG_GLOW"; gl.quality = "HIGH"; gl.threshold = 0.9; gl.size = 8; gl.mix = -0.72
bpy.context.view_layer.use_pass_mist = True
sc.world.mist_settings.start = 2.5; sc.world.mist_settings.depth = 14.0; sc.world.mist_settings.falloff = "QUADRATIC"
mm = ct.nodes.new("CompositorNodeMath"); mm.operation = "MULTIPLY"; mm.inputs[1].default_value = float(os.environ.get("UU_HAZE", "0.14"))
ct.links.new(rl.outputs["Mist"], mm.inputs[0])
mx = ct.nodes.new("CompositorNodeMixRGB"); mx.blend_type = "SCREEN"; mx.inputs[2].default_value = (0.03, 0.06, 0.09, 1)
ct.links.new(mm.outputs[0], mx.inputs[0]); ct.links.new(rl.outputs["Image"], mx.inputs[1])
ct.links.new(mx.outputs["Image"], gl.inputs["Image"]); ct.links.new(gl.outputs["Image"], co.inputs["Image"])

def parse(spec):
    fs = []
    for part in spec.split(","):
        part = part.strip()
        if not part: continue
        if "-" in part:
            a, b = part.split("-"); fs += list(range(int(a), int(b) + 1))
        else: fs.append(int(part))
    return fs

os.makedirs(OUT, exist_ok=True)
log("ready")
for f in parse(SPEC):
    fp = os.path.join(OUT, "f%04d.jpg" % f)
    if os.path.exists(fp): continue
    sc.frame_set(f); per_frame(f)
    r.filepath = fp
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print("FRAME", f, round(time.time() - t1, 1), flush=True)
print("DONE", flush=True)
