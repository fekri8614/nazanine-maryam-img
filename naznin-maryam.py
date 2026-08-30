import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageOps, ImageEnhance
import random, math

random.seed(77)
np.random.seed(77)

W = H = 3000
img = Image.new("RGB", (W, H), (0,0,0))

# ---------- helpers ----------
def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, v))

# ---------- 1. SKY GRADIENT ----------
# multi-stop vertical gradient: violet top -> ash-blue -> muted rose/gold near horizon
stops = [
    (0.00, (32, 34, 56)),    # deep violet-indigo top
    (0.22, (46, 46, 68)),
    (0.42, (74, 63, 78)),    # muted mauve
    (0.60, (128, 95, 88)),   # dusky rose
    (0.74, (183, 132, 95)),  # faded gold-orange
    (0.86, (219, 168, 118)), # warm horizon glow
    (1.00, (206, 150, 108)), # settling back slightly, horizon haze
]

sky = np.zeros((H, W, 3), dtype=np.float32)
ys = np.linspace(0, 1, H)
for y_idx, t in enumerate(ys):
    # find bracketing stops
    for i in range(len(stops)-1):
        t0, c0 = stops[i]
        t1, c1 = stops[i+1]
        if t0 <= t <= t1:
            local_t = (t - t0) / (t1 - t0 + 1e-9)
            # ease
            local_t = local_t*local_t*(3-2*local_t)
            col = lerp_color(c0, c1, local_t)
            sky[y_idx, :, :] = col
            break

sky_img = Image.fromarray(sky.astype(np.uint8), "RGB")

# horizontal warm glow bias toward lower-right (sun already set slightly right of center)
glow = Image.new("L", (W, H), 0)
gdraw = ImageDraw.Draw(glow)
sun_x, sun_y = int(W*0.62), int(H*0.735)
max_r = int(W*0.95)
for r in range(max_r, 0, -6):
    alpha = int(70 * (1 - r/max_r) ** 2.2)
    bbox = [sun_x-r, sun_y-r*0.55, sun_x+r, sun_y+r*0.55]
    gdraw.ellipse(bbox, fill=alpha)
glow = glow.filter(ImageFilter.GaussianBlur(140))
glow_color = Image.new("RGB", (W,H), (232, 176, 121))
sky_img = Image.composite(glow_color, sky_img, glow.point(lambda p: int(p*0.55)))

img.paste(sky_img, (0,0))

# fine sky noise for painterly texture
sky_noise = (np.random.randn(H, W) * 3.2)
sky_noise_img = Image.fromarray(np.clip(128+sky_noise,0,255).astype(np.uint8))
sky_tex = ImageChops.overlay(img, Image.merge("RGB",(sky_noise_img,sky_noise_img,sky_noise_img)))
img = Image.blend(img, sky_tex, 0.12)

draw = ImageDraw.Draw(img, "RGBA")

# ---------- 2. DISTANT MOUNTAINS (soft, layered, misty) ----------
def mountain_layer(base_y, amplitude, roughness, color, alpha, blur, seed):
    rnd = random.Random(seed)
    pts = [(0, base_y)]
    n = 26
    for i in range(1, n):
        x = W * i / (n-1)
        y = base_y + math.sin(i*0.7+seed) * amplitude * 0.5 + rnd.uniform(-amplitude, amplitude*0.6)
        pts.append((x, y))
    pts.append((W, base_y))
    pts.append((W, H))
    pts.append((0, H))
    layer = Image.new("RGBA", (W,H), (0,0,0,0))
    ld = ImageDraw.Draw(layer)
    ld.polygon(pts, fill=color+(alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return layer

horizon_y = int(H*0.66)

m1 = mountain_layer(horizon_y-95, 46, 0.5, (168,146,144), 100, 48, 1)
m2 = mountain_layer(horizon_y-50, 60, 0.6, (132,112,114), 145, 34, 2)
m3 = mountain_layer(horizon_y-10, 72, 0.7, (88,76,84), 190, 20, 3)

for m in (m1, m2, m3):
    img = Image.alpha_composite(img.convert("RGBA"), m).convert("RGB")

# soft atmospheric mist — a smooth vertical gradient band (no hard rectangle edges)
mist_grad = Image.new("L", (W,H), 0)
mg = ImageDraw.Draw(mist_grad)
for yy in range(H):
    d = abs(yy - (horizon_y-20))
    a = int(55 * math.exp(-(d*d)/(2*130*130)))
    if a > 0:
        mg.line([(0,yy),(W,yy)], fill=a)
mist_grad = mist_grad.filter(ImageFilter.GaussianBlur(50))
mist_col = Image.new("RGB",(W,H),(214,194,182))
img = Image.composite(mist_col, img, mist_grad)

draw = ImageDraw.Draw(img, "RGBA")

# ---------- 3. MIDGROUND FIELD BASE ----------
field_top = horizon_y + 10
field_color_top = (98, 92, 70)
field_color_bottom = (48, 42, 34)
field = np.zeros((H-field_top, W, 3), dtype=np.float32)
fys = np.linspace(0,1,H-field_top)
for i,t in enumerate(fys):
    field[i,:,:] = lerp_color(field_color_top, field_color_bottom, t**0.8)
field_img = Image.fromarray(field.astype(np.uint8))
img.paste(field_img, (0, field_top))

draw = ImageDraw.Draw(img, "RGBA")

# subtle ground haze right above field line to merge mountains/field
haze2 = Image.new("RGBA",(W,H),(0,0,0,0))
h2d = ImageDraw.Draw(haze2)
h2d.rectangle([0, field_top-40, W, field_top+120], fill=(196,170,150,50))
haze2 = haze2.filter(ImageFilter.GaussianBlur(55))
img = Image.alpha_composite(img.convert("RGBA"), haze2).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

# ---------- 4. THE LONE TREE ----------
tree_x = int(W*0.345)
tree_base_y = int(H*0.745)
tree_top_y = int(H*0.485)

def draw_branch(draw, x0, y0, angle, length, width, depth, color, layer, tips=None):
    if depth == 0 or length < 6:
        if tips is not None:
            tips.append((x0, y0, depth))
        return
    x1 = x0 + math.cos(angle) * length
    y1 = y0 - math.sin(angle) * length
    layer_draw = ImageDraw.Draw(layer, "RGBA")
    steps = max(2, int(length/14))
    for s in range(steps):
        t0 = s/steps
        t1 = (s+1)/steps
        wob = math.sin(t0*7+x0*0.01)*width*0.15
        xa = lerp(x0,x1,t0)+wob
        ya = lerp(y0,y1,t0)
        xb = lerp(x0,x1,t1)+wob
        yb = lerp(y0,y1,t1)
        wgt = max(1.2, width*(1-t0*0.5))
        layer_draw.line([xa,ya,xb,yb], fill=color, width=int(wgt))
    n_branches = 2 if depth > 1 else random.choice([0,1,2])
    if n_branches == 0 and tips is not None:
        tips.append((x1, y1, depth))
    for _ in range(n_branches):
        spread = random.uniform(0.35, 0.85)
        sign = random.choice([-1,1])
        new_angle = angle + sign*spread*random.uniform(0.5,1.0)
        new_len = length * random.uniform(0.55, 0.72)
        new_w = width * 0.62
        draw_branch(draw, x1, y1, new_angle, new_len, new_w, depth-1, color, layer, tips)
    if tips is not None and depth <= 2:
        tips.append((x1, y1, depth))

tree_layer = Image.new("RGBA", (W,H), (0,0,0,0))
trunk_color = (34,28,26,255)
branch_tips = []
random.seed(11)
draw_branch(draw, tree_x, tree_base_y, math.radians(94), 300, 36, 7, trunk_color, tree_layer, branch_tips)
# a couple extra low, gnarled side branches for weathered asymmetry
random.seed(23)
draw_branch(draw, tree_x-4, tree_base_y-70, math.radians(28), 175, 18, 5, trunk_color, tree_layer, branch_tips)
random.seed(41)
draw_branch(draw, tree_x+4, tree_base_y-45, math.radians(158), 150, 16, 5, trunk_color, tree_layer, branch_tips)

tree_layer = tree_layer.filter(ImageFilter.GaussianBlur(0.6))
img = Image.alpha_composite(img.convert("RGBA"), tree_layer).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

# rim light on tree — thin warm edge catching the last sun from the right
rim = Image.new("RGBA",(W,H),(0,0,0,0))
rim_layer = Image.new("RGBA", (W,H), (0,0,0,0))
random.seed(11)
draw_branch(rim, tree_x+4, tree_base_y, math.radians(94), 300, 36, 7, (222,168,110,90), rim_layer)
rim_layer = rim_layer.filter(ImageFilter.GaussianBlur(3))
img = Image.alpha_composite(img.convert("RGBA"), rim_layer).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

# soft cast shadow of tree on the field, long, faint (light from lower right)
shadow = Image.new("RGBA",(W,H),(0,0,0,0))
sd = ImageDraw.Draw(shadow)
sd.polygon([
    (tree_x-30, tree_base_y),
    (tree_x-260, tree_base_y+270),
    (tree_x-170, tree_base_y+290),
    (tree_x+15, tree_base_y+15),
], fill=(20,16,14,55))
shadow = shadow.filter(ImageFilter.GaussianBlur(30))
img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

print("stage1 done")
img.save("/home/claude/nazanin/stage1.png")

# ---------- 6. SPARSE WEATHERED FOLIAGE ----------
# The tree is old and bowed but alive — a thin, sparse scatter of dry leaf
# clusters at the outer branch tips, autumnal and muted, never a full canopy.
random.seed(5)
foliage_layer = Image.new("RGBA", (W,H), (0,0,0,0))
fol_draw = ImageDraw.Draw(foliage_layer, "RGBA")

# use the real branch endpoints collected while drawing the tree, so foliage
# clusters sit exactly where branches actually end (favor the outer, thinner tips)
outer_tips = [(x,y) for (x,y,d) in branch_tips if d <= 2]
if len(outer_tips) < 6:
    outer_tips = [(x,y) for (x,y,d) in branch_tips]
branch_tips = outer_tips
leaf_colors = [(74,64,44), (92,76,48), (62,54,38), (100,80,50), (68,58,42), (56,48,34)]
for (bx,by) in branch_tips:
    n = random.randint(7, 13)
    spread = random.uniform(20, 34)
    for _ in range(n):
        lx = bx + random.uniform(-spread, spread)
        ly = by + random.uniform(-spread*0.7, spread*0.7)
        rx = random.uniform(2.5, 7) * random.uniform(0.6,1.3)
        ry = random.uniform(2.5, 7) * random.uniform(0.6,1.3)
        col = random.choice(leaf_colors)
        a = random.randint(60, 125)
        fol_draw.ellipse([lx-rx, ly-ry, lx+rx, ly+ry], fill=col+(a,))
foliage_layer = foliage_layer.filter(ImageFilter.GaussianBlur(1.1))
img = Image.alpha_composite(img.convert("RGBA"), foliage_layer).convert("RGB")

# a few warm rim-lit leaves catching the last light, upper-right side of canopy
rim_leaf = Image.new("RGBA", (W,H), (0,0,0,0))
rld = ImageDraw.Draw(rim_leaf, "RGBA")
for (bx,by) in branch_tips[:7]:
    for _ in range(random.randint(2,4)):
        lx = bx + random.uniform(-18, 30)
        ly = by + random.uniform(-18, 16)
        r = random.uniform(2, 4.5)
        rld.ellipse([lx-r,ly-r,lx+r,ly+r], fill=(178,140,92,75))
rim_leaf = rim_leaf.filter(ImageFilter.GaussianBlur(1.6))
img = Image.alpha_composite(img.convert("RGBA"), rim_leaf).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

print("stage2 foliage done")
img.save("/home/claude/nazanin/stage2.png")

# ---------- 7. REDO FABRIC — thinner, wind-torn ribbon, tucked lower & smaller ----------
# (paint over the old fabric with field-color patch first is unnecessary since we
# draw a fresh, smaller, more convincing scrap on a lower side branch)
fabric_x, fabric_y = tree_x-176, tree_base_y-190
fab_layer = Image.new("RGBA", (W,H), (0,0,0,0))
fabd = ImageDraw.Draw(fab_layer, "RGBA")
# a thin wind-curved ribbon made of short overlapping segments tapering to a torn point
segs = 10
bx0, by0 = fabric_x, fabric_y
angle = math.radians(-25)
cur_w = 21
path_top = []
path_bot = []
for i in range(segs):
    t = i/(segs-1)
    curve = math.sin(t*3.1)*10
    x = bx0 + i*6 + curve
    y = by0 + i*9 - math.sin(t*2.2)*6
    w = cur_w * (1-t*0.75)
    path_top.append((x, y-w/2))
    path_bot.append((x, y+w/2))
poly = path_top + path_bot[::-1]
fabd.polygon(poly, fill=(224,214,196,235))
fab_layer = fab_layer.filter(ImageFilter.GaussianBlur(1.0))
img = Image.alpha_composite(img.convert("RGBA"), fab_layer).convert("RGB")
# faint fold shading + warm edge light
fold2 = Image.new("RGBA",(W,H),(0,0,0,0))
f2d = ImageDraw.Draw(fold2, "RGBA")
f2d.line([bx0+4,by0+2,bx0+40,by0+40], fill=(140,124,104,80), width=2)
f2d.line([bx0+2,by0-2,bx0+34,by0+24], fill=(226,192,150,70), width=2)
fold2 = fold2.filter(ImageFilter.GaussianBlur(1.4))
img = Image.alpha_composite(img.convert("RGBA"), fold2).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

print("stage3 fabric redone")
img.save("/home/claude/nazanin/stage3.png")

# ---------- 8. WILD GRASS FIELD ----------
# Layered blades: a soft, low midground layer first, then a taller, slightly
# blurred foreground layer to create depth-of-field, all bending the same
# direction in the evening wind.
random.seed(99)

def grass_layer(y_band_top, y_band_bottom, n_blades, h_min, h_max, w_min, w_max,
                 colors, alpha_range, bend, blur_amt, sway_seed,
                 clear_x=None, clear_radius=0, clear_scale=0.35, clump=True):
    layer = Image.new("RGBA", (W,H), (0,0,0,0))
    gd = ImageDraw.Draw(layer, "RGBA")
    rnd = random.Random(sway_seed)

    if clump:
        n_clusters = max(6, n_blades // 55)
        centers = [rnd.uniform(-60, W+60) for _ in range(n_clusters)]
    else:
        centers = None

    for i in range(n_blades):
        if clump:
            cx = rnd.choice(centers)
            bx = cx + rnd.gauss(0, 95)
        else:
            bx = rnd.uniform(-40, W+40)
        by = rnd.uniform(y_band_top, y_band_bottom)
        h_scale = 1.0
        if clear_x is not None:
            d = abs(bx - clear_x)
            if d < clear_radius:
                h_scale = clear_scale + (1-clear_scale) * (d/clear_radius)
        bh = rnd.uniform(h_min, h_max) * h_scale
        bw = rnd.uniform(w_min, w_max)
        col = rnd.choice(colors)
        a = rnd.randint(*alpha_range)
        lean = bend + rnd.uniform(-0.14, 0.14)
        tip_x = bx + bh*lean
        tip_y = by - bh
        mid_x = bx + bh*lean*0.55
        mid_y = by - bh*0.55
        gd.line([bx,by, mid_x+ rnd.uniform(-4,4), mid_y, tip_x, tip_y],
                 fill=col+(a,), width=max(1,int(bw)), joint="curve")
    if blur_amt:
        layer = layer.filter(ImageFilter.GaussianBlur(blur_amt))
    return layer

field_bottom = H
# distant/mid grass — shorter, muted, sparse with visible gaps, parts around the tree
mid_colors = [(84,78,52),(102,92,58),(66,60,40),(118,104,64)]
g_mid = grass_layer(field_top+10, field_top+220, 950, 26, 80, 2, 4,
                     mid_colors, (40,95), 0.30, 1.6, 201,
                     clear_x=tree_x, clear_radius=230, clear_scale=0.3)
img = Image.alpha_composite(img.convert("RGBA"), g_mid).convert("RGB")

# closer grass band — clumped, with a clearing around the trunk
close_colors = [(96,86,54),(70,62,40),(126,110,66),(58,52,34)]
g_close = grass_layer(field_top+160, field_top+440, 1300, 70, 190, 3, 6,
                       close_colors, (80,150), 0.34, 0.6, 202,
                       clear_x=tree_x, clear_radius=260, clear_scale=0.3)
img = Image.alpha_composite(img.convert("RGBA"), g_close).convert("RGB")

# tiny sparse wildflowers among mid grass — desaturated pale lavender/cream, not sweet
random.seed(303)
flower_layer = Image.new("RGBA",(W,H),(0,0,0,0))
flwd = ImageDraw.Draw(flower_layer, "RGBA")
flower_colors = [(196,178,168),(176,158,150),(150,138,132)]
for _ in range(70):
    fx = random.uniform(0, W)
    fy = random.uniform(field_top+120, field_top+420)
    r = random.uniform(2.2, 4.2)
    col = random.choice(flower_colors)
    a = random.randint(90,170)
    flwd.ellipse([fx-r,fy-r,fx+r,fy+r], fill=col+(a,))
flower_layer = flower_layer.filter(ImageFilter.GaussianBlur(0.6))
img = Image.alpha_composite(img.convert("RGBA"), flower_layer).convert("RGB")

# foreground grass — tall, soft-focus, framing only the lower edge of the frame,
# thinned near the tree's x-position so the trunk and canopy stay legible
fg_colors = [(52,46,30),(38,34,22),(70,62,40),(30,27,18)]
g_fg = grass_layer(H-260, H+140, 560, 180, 430, 6, 13,
                    fg_colors, (120,200), 0.30, 3.4, 404,
                    clear_x=tree_x, clear_radius=340, clear_scale=0.4)
img = Image.alpha_composite(img.convert("RGBA"), g_fg).convert("RGB")

# a touch of warm rim-light on foreground grass tips (catching last horizon glow)
rim_grass = grass_layer(H-230, H+120, 140, 180, 380, 4, 7,
                         [(196,150,96),(214,168,110)], (25,60), 0.30, 2.6, 505,
                         clear_x=tree_x, clear_radius=340, clear_scale=0.4)
img = Image.alpha_composite(img.convert("RGBA"), rim_grass).convert("RGB")
draw = ImageDraw.Draw(img, "RGBA")

print("stage4 grass done")
img.save("/home/claude/nazanin/stage4.png")

# ---------- 9. FINAL ATMOSPHERE, GRAIN, GRADE, VIGNETTE ----------
# gentle overall haze to unify depth
haze3 = Image.new("RGBA",(W,H),(214,196,178, 0))
haze3.putalpha(0)
haze_grad = Image.new("L",(W,H),0)
hg = ImageDraw.Draw(haze_grad)
for i in range(H):
    t = i/H
    a = int(26 * math.exp(-((t-0.60)**2)/(2*0.09**2)))
    hg.line([(0,i),(W,i)], fill=a)
haze_grad = haze_grad.filter(ImageFilter.GaussianBlur(30))
haze_col = Image.new("RGB",(W,H),(210,178,150))
img = Image.composite(haze_col, img, haze_grad)

# gentle color grade: lift shadows slightly toward blue-violet, warm highlights
img = ImageEnhance.Color(img).enhance(0.72)   # desaturate toward earthy
img = ImageEnhance.Contrast(img).enhance(1.05)
img = ImageEnhance.Brightness(img).enhance(1.0)

arr = np.array(img).astype(np.float32)
lum = arr.mean(axis=2, keepdims=True)/255.0
shadow_tint = np.array([12, 10, 26], dtype=np.float32)
highlight_tint = np.array([14, 6, -8], dtype=np.float32)
arr = arr + shadow_tint*(1-lum)*0.5 + highlight_tint*lum*0.5
arr = np.clip(arr, 0, 255)
img = Image.fromarray(arr.astype(np.uint8))

# film grain
grain = np.random.randn(H, W) * 9.5
grain_img = np.stack([grain]*3, axis=-1)
arr = np.array(img).astype(np.float32) + grain_img
arr = np.clip(arr, 0, 255)
img = Image.fromarray(arr.astype(np.uint8))
img = img.filter(ImageFilter.GaussianBlur(0.4))

# soft vignette
vig = Image.new("L", (W,H), 0)
vd = ImageDraw.Draw(vig)
vd.ellipse([-W*0.28, -H*0.28, W*1.28, H*1.28], fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(260))
vig_arr = np.array(vig).astype(np.float32)/255.0
img_arr = np.array(img).astype(np.float32)
darken = (1 - vig_arr)[...,None] * 46
img_arr = np.clip(img_arr - darken, 0, 255)
img = Image.fromarray(img_arr.astype(np.uint8))

# very subtle overall softness (analog lens feel) while keeping a sharp core via unsharp mask on a blurred duplicate
soft = img.filter(ImageFilter.GaussianBlur(1.6))
img = Image.blend(img, soft, 0.18)

img.save("/home/claude/nazanin/final.png", quality=97)
print("final saved")
