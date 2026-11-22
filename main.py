#!/usr/bin/env python3
"""The Picture That Tastes of One — make.fun image entry.

Procedural close-up of ONE crispy fried-chicken piece: golden craggy
crust, glossy oil highlights, warm light, dark background, no text.
Pure Python 3.13 stdlib only (struct / zlib / math / random / hashlib).
No external images are read, copied or downloaded; every pixel is drawn
by this program in this session.

Run:  python3 main.py        (from this directory)
Writes: entry.png (local) and /output/entry.png (1024x1024 PNG).
"""
import hashlib
import math
import os
import random
import struct
import zlib

W = H = 1024
SEED = 20261122

# ---------------------------------------------------------------- grids
def make_grid(n, seed):
    """Periodic n x n value-noise grid (values 0..1)."""
    rnd = random.Random(seed)
    return [[rnd.random() for _ in range(n)] for _ in range(n)]


def sample_grid(grid, n, x, y):
    """Bilinear smooth sample of a periodic grid; x, y in [0, 1)."""
    gx = x * n
    gy = y * n
    x0 = int(gx) % n
    y0 = int(gy) % n
    x1 = x0 + 1
    if x1 >= n:
        x1 = 0
    y1 = y0 + 1
    if y1 >= n:
        y1 = 0
    fx = gx - math.floor(gx)
    fy = gy - math.floor(gy)
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)
    row0 = grid[y0]
    row1 = grid[y1]
    a = row0[x0]
    b = row0[x1]
    c = row1[x0]
    d = row1[x1]
    top = a + (b - a) * sx
    bot = c + (d - c) * sx
    return top + (bot - top) * sy


# noise grids: coarse mottling, craggy bumps, fine grain, gloss map
G_MOT = make_grid(24, SEED + 1)      # large golden mottling
G_BUMP = make_grid(64, SEED + 2)     # crispy crag texture (coarse)
G_FINE = make_grid(160, SEED + 3)    # fine grain on top of crags
G_GLOSS = [[0.0] * 128 for _ in range(128)]

# gloss: a few soft warm specular pools (oil shine) baked into a grid
_GLOSS_BLOBS = [
    (0.40, 0.36, 0.11, 1.00),   # upper-left main shine
    (0.62, 0.46, 0.08, 0.90),   # centre-right shine
    (0.50, 0.66, 0.13, 0.75),   # lower shine
    (0.30, 0.58, 0.06, 0.60),   # small left shine
]
for _gy in range(128):
    _cy = (_gy + 0.5) / 128.0
    for _gx in range(128):
        _cx = (_gx + 0.5) / 128.0
        _v = 0.0
        for _bx, _by, _br, _ba in _GLOSS_BLOBS:
            _dx = _cx - _bx
            _dy = _cy - _by
            _v += _ba * math.exp(-(_dx * _dx + _dy * _dy) / (2.0 * _br * _br))
        G_GLOSS[_gy][_gx] = _v if _v < 1.0 else 1.0

# ------------------------------------------------------- chicken outline
CX, CY = 512.0, 530.0          # piece centre (slightly low: fills frame)
BASE_R = 415.0                 # base radius
EDGE_N = 720                   # precomputed outline samples
EDGE = []
for _i in range(EDGE_N):
    _th = 2.0 * math.pi * _i / EDGE_N
    # wobbly organic outline: a thigh-like piece, one fat lobe
    _r = (1.0
          + 0.055 * math.sin(3.0 * _th + 1.7)
          + 0.035 * math.sin(5.0 * _th + 0.4)
          + 0.025 * math.sin(8.0 * _th + 2.9)
          + 0.13 * math.cos(_th - 0.6))   # taper: fat right, leaner left
    # fat lobe bottom-right, slight flatten top
    _r *= 1.0 + 0.10 * math.exp(-((_th - 0.7) ** 2) / 0.35)
    _r *= 1.0 - 0.05 * math.exp(-((_th + 1.35) ** 2) / 0.30)
    EDGE.append(BASE_R * _r)

# second smaller lobe (drumstick end) bottom-left, baked into mask
LX, LY, LR = 300.0, 760.0, 185.0


def edge_radius(theta):
    idx = int((theta + math.pi) / (2.0 * math.pi) * EDGE_N) % EDGE_N
    return EDGE[idx]


# ------------------------------------------------------------- rendering
def render():
    img = bytearray(W * H * 3)
    sqrt = math.sqrt
    atan2 = math.atan2
    exp = math.exp
    pi2 = 2.0 * math.pi
    for y in range(H):
        yn = (y + 0.5) / H
        row = y * W * 3
        dy = y - CY
        for x in range(W):
            xn = (x + 0.5) / W
            dx = x - CX
            # elliptical metric: piece wider than tall
            ex = dx / 1.14
            ey = dy / 0.94
            r = sqrt(ex * ex + ey * ey)

            # ---- background: warm dark brown radial + glow behind piece
            dc = r
            glow = exp(-(dc * dc) / (2.0 * 560.0 * 560.0))
            vig = 1.0 - 0.38 * (dc / 724.0) ** 2
            if vig < 0.55:
                vig = 0.55
            br = (12.0 + 96.0 * glow) * vig
            bg = (7.0 + 48.0 * glow) * vig
            bb = (3.0 + 18.0 * glow) * vig

            # ---- chicken mask (main blob + lobe)
            R = edge_radius(atan2(ey, ex))
            d_main = r / R
            ldx = x - LX
            ldy = y - LY
            lr = sqrt(ldx * ldx + ldy * ldy) / LR
            d = d_main if d_main < lr else lr
            if d >= 1.0:
                o = row + x * 3
                img[o] = int(br)
                img[o + 1] = int(bg)
                img[o + 2] = int(bb)
                continue
            # feathered edge
            f = (1.0 - d) * 42.0
            if f > 1.0:
                f = 1.0
            f = f * f * (3.0 - 2.0 * f)

            # ---- crust colour: mottled gold
            m = sample_grid(G_MOT, 24, xn, yn)
            m2 = sample_grid(G_MOT, 24, (xn + 0.37) % 1.0, (yn + 0.61) % 1.0)
            t = 0.5 * m + 0.5 * m2
            # deep -> mid -> bright gold
            if t < 0.5:
                k = t * 2.0
                cr = 150.0 + (214.0 - 150.0) * k
                cg = 78.0 + (136.0 - 78.0) * k
                cb = 18.0 + (36.0 - 18.0) * k
            else:
                k = (t - 0.5) * 2.0
                cr = 214.0 + (242.0 - 214.0) * k
                cg = 136.0 + (184.0 - 136.0) * k
                cb = 36.0 + (72.0 - 36.0) * k

            # ---- crispy bumps: bright ridges, dark craggy crevices
            b = sample_grid(G_BUMP, 64, xn, yn)
            b2 = sample_grid(G_FINE, 160, (xn + 0.13) % 1.0, (yn + 0.29) % 1.0)
            bump = 0.72 * b + 0.28 * b2
            bright = 0.70 + 0.60 * (bump - 0.5)
            cr *= bright
            cg *= bright
            cb *= bright
            if bump < 0.36:                       # crevice -> deep brown
                k = (0.36 - bump) / 0.36 * 0.85
                cr += (66.0 - cr) * k
                cg += (32.0 - cg) * k
                cb += (8.0 - cb) * k
            elif bump > 0.72:                     # crisp ridge highlight
                k = (bump - 0.72) / 0.28 * 0.35
                cr += (255.0 - cr) * k
                cg += (214.0 - cg) * k
                cb += (120.0 - cb) * k

            # ---- warm directional light (top-left) + rim darkening
            if r > 1.0:
                dot = (-0.55 * ex - 0.83 * ey) / r
            else:
                dot = 0.0
            dl = 0.82 + 0.30 * dot
            cr *= dl
            cg *= dl
            cb *= dl
            if d > 0.88:                          # crust rim shadow
                k = (d - 0.88) / 0.12 * 0.38
                cr *= (1.0 - k)
                cg *= (1.0 - k)
                cb *= (1.0 - k)
            if d > 0.90 and dot > 0.25:           # light catching top crust edge
                k = (d - 0.90) / 0.10 * (dot - 0.25) * 0.9
                cr += (255.0 - cr) * k
                cg += (205.0 - cg) * k
                cb += (130.0 - cb) * k

            # ---- oil gloss (warm specular pools)
            g = sample_grid(G_GLOSS, 128, xn, yn)
            if g > 0.02:
                k = g * 0.55
                cr += (255.0 - cr) * k
                cg += (216.0 - cg) * k
                cb += (150.0 - cb) * k

            # ---- crispy speckles (tiny flakes / dark pits)
            h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
            h8 = (h >> 24) & 0xFF
            if h8 < 2:
                cr += (255.0 - cr) * 0.55
                cg += (225.0 - cg) * 0.55
                cb += (150.0 - cb) * 0.55
            elif h8 > 253:
                cr *= 0.62
                cg *= 0.62
                cb *= 0.62

            # ---- blend to background at the feathered edge
            o = row + x * 3
            img[o] = int(cr * f + br * (1.0 - f))
            img[o + 1] = int(cg * f + bg * (1.0 - f))
            img[o + 2] = int(cb * f + bb * (1.0 - f))
    return img


def draw_crumbs(img):
    """A few golden crumbs scattered on the dark table (drawn in bboxes)."""
    rnd = random.Random(SEED + 9)
    for _ in range(90):
        # cluster near the chicken edge, mostly lower half
        ang = rnd.uniform(0.0, 2.0 * math.pi)
        dist = rnd.uniform(0.0, 90.0)
        cx = int(CX + math.cos(ang) * (BASE_R + dist))
        cy = int(CY + math.sin(ang) * (BASE_R * 0.94 + dist))
        if not (20 <= cx < W - 20 and 20 <= cy < H - 20):
            continue
        # keep off the chicken: outside main outline + lobe
        dx = cx - CX
        dy = cy - CY
        if math.hypot(dx / 1.14, dy / 0.94) < edge_radius(math.atan2(dy / 0.94, dx / 1.14)) + 10:
            continue
        if math.hypot(cx - LX, cy - LY) < LR + 10:
            continue
        s = rnd.choice((1, 2, 2, 3, 3, 4))
        shade = rnd.random()
        r = int(150 + 90 * shade)
        g = int(95 + 70 * shade)
        b = int(25 + 35 * shade)
        for yy in range(cy, min(H, cy + s)):
            for xx in range(cx, min(W, cx + s)):
                o = (yy * W + xx) * 3
                img[o] = r
                img[o + 1] = g
                img[o + 2] = b


# -------------------------------------------------------------- PNG write
def paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def encode_png(img):
    """Adaptive per-row filtering (0/1/2/4 by sum of |signed| bytes)."""
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(img[y * W * 3:(y + 1) * W * 3])
        best = None
        best_score = None
        for ftype in (0, 1, 2, 4):
            if ftype == 0:
                filt = row
            elif ftype == 1:
                buf = bytearray(W * 3)
                for i in range(W * 3):
                    left = row[i - 3] if i >= 3 else 0
                    buf[i] = (row[i] - left) & 0xFF
                filt = bytes(buf)
            elif ftype == 2:
                buf = bytearray(W * 3)
                for i in range(W * 3):
                    buf[i] = (row[i] - prev[i]) & 0xFF
                filt = bytes(buf)
            else:  # Paeth
                buf = bytearray(W * 3)
                for i in range(W * 3):
                    left = row[i - 3] if i >= 3 else 0
                    up = prev[i]
                    upleft = prev[i - 3] if i >= 3 else 0
                    buf[i] = (row[i] - paeth(left, up, upleft)) & 0xFF
                filt = bytes(buf)
            score = sum(v if v < 128 else 256 - v for v in filt)
            if best_score is None or score < best_score:
                best_score = score
                best = bytes([ftype]) + filt
        raw += best
        prev = row
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def blur3(img):
    """One 3x3 box-blur pass (fallback if the PNG is over the size cap)."""
    out = bytearray(img)
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            for c in range(3):
                o = (y * W + x) * 3 + c
                out[o] = (img[o - W * 3 - 3] + img[o - W * 3] + img[o - W * 3 + 3]
                          + img[o - 3] + img[o] + img[o + 3]
                          + img[o + W * 3 - 3] + img[o + W * 3]
                          + img[o + W * 3 + 3]) // 9
    return out


def main():
    img = render()
    draw_crumbs(img)
    png = encode_png(img)
    # size cap: 1 MiB. Blur once/twice to cut high-frequency entropy if needed.
    tries = 0
    while len(png) > 1048576 and tries < 2:
        tries += 1
        img = blur3(img)
        png = encode_png(img)
    with open("entry.png", "wb") as fh:
        fh.write(png)
    try:
        os.makedirs("/output", exist_ok=True)
        with open("/output/entry.png", "wb") as fh:
            fh.write(png)
        out_msg = "/output/entry.png written"
    except OSError as exc:
        out_msg = f"/output write failed ({exc}); local entry.png only"
    print(f"entry.png: {len(png)} bytes, sha256={hashlib.sha256(png).hexdigest()}")
    print(f"size OK (<=1048576): {len(png) <= 1048576}  blur passes: {tries}")
    print(out_msg)
    print(f"PNG header: {png[:8].hex()}  tail: {png[-12:].hex()}")


if __name__ == "__main__":
    main()
