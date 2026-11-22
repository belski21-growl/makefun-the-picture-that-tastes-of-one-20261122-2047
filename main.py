#!/usr/bin/env python3
"""make.fun entry: The picture that tastes of one ingredient.

One close-up piece of golden crispy fried chicken (a drumstick), drawn
procedurally from scratch with Python 3.13 stdlib only. No image is
loaded, copied or downloaded; every pixel is computed here.

Writes /output/entry.png (and entry.png next to this script), 1024x1024.
Deterministic: fixed seed.
"""
import hashlib
import math
import os
import random
import struct
import zlib

W = H = 1024
SEED = 20261122

# ---------------------------------------------------------------- noise ----
_rng = random.Random(SEED)
_GN = 192  # noise grid size
_grid = [[_rng.random() for _ in range(_GN + 1)] for _ in range(_GN + 1)]
_grid2 = [[_rng.random() for _ in range(_GN + 1)] for _ in range(_GN + 1)]


def _vnoise(grid, x, y):
    """Bilinear value noise; x, y in grid units, wraps."""
    xi = int(math.floor(x))
    yi = int(math.floor(y))
    xf = x - xi
    yf = y - yi
    x0 = xi % _GN
    x1 = (xi + 1) % _GN
    y0 = yi % _GN
    y1 = (yi + 1) % _GN
    a = grid[y0][x0]
    b = grid[y0][x1]
    c = grid[y1][x0]
    d = grid[y1][x1]
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def _hash2(ix, iy, s):
    """Deterministic pseudo-random in [0, 1) from integer cell coords."""
    h = (ix * 374761393 + iy * 668265263 + s * 974634211) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF) / 16777216.0


def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------- scene data --
# Drumstick axis: bulb (meaty end) upper-left, bone tip lower-right.
_COSA = 0.788010754  # cos(38 deg)
_SINA = 0.615661475  # sin(38 deg)
_CX, _CY = 480.0, 460.0  # bulb centre

# Soft background bokeh dots (x, y, radius, brightness).
_BOKEH = [
    (150.0, 170.0, 46.0, 0.55), (880.0, 130.0, 60.0, 0.45),
    (920.0, 880.0, 52.0, 0.40), (120.0, 860.0, 58.0, 0.42),
    (700.0, 90.0, 30.0, 0.35), (90.0, 480.0, 34.0, 0.30),
    (950.0, 480.0, 28.0, 0.30), (520.0, 950.0, 40.0, 0.32),
]
# Golden crumbs scattered on the dark table (x, y, r, shade 0..1).
_CRUMBS = [(820.0, 905.0, 9.0, 0.9), (862.0, 880.0, 6.0, 0.7),
           (150.0, 930.0, 7.0, 0.8), (905.0, 830.0, 5.0, 0.6),
           (95.0, 700.0, 6.0, 0.7), (700.0, 965.0, 8.0, 0.75)]
# Herb leaves (small green accent, lower-left of the meat).
# Each leaf: centre, half-length, half-width, angle (deg).
_LEAVES = [
    (332.0, 722.0, 58.0, 16.0, -28.0),
    (378.0, 756.0, 50.0, 14.0, 12.0),
    (300.0, 762.0, 44.0, 13.0, -62.0),
]


def _leaf_mask(x, y):
    """Return (leaf index, normalised along-leaf coord) or (-1, 0)."""
    for i, (lx, ly, a, b, ang) in enumerate(_LEAVES):
        th = math.radians(ang)
        ca, sa = math.cos(th), math.sin(th)
        dx, dy = x - lx, y - ly
        px = dx * ca + dy * sa
        py = -dx * sa + dy * ca
        if (px / a) * (px / a) + (py / b) * (py / b) < 1.0:
            return i, px / a
    return -1, 0.0


def render():
    buf = bytearray(W * H * 3)
    grid = _grid
    grid2 = _grid2
    for y in range(H):
        row = y * W * 3
        dy0 = y - _CY
        for x in range(W):
            dx0 = x - _CX
            # Rotate into drumstick frame: u along axis to bone, v across.
            u = dx0 * _COSA + dy0 * _SINA
            v = -dx0 * _SINA + dy0 * _COSA
            # --- meat mask: bulb ellipse + tapered shaft capsule ---
            bu = (u + 62.0) / 330.0
            bv = v / 300.0
            d_bulb = (bu * bu + bv * bv - 1.0) * 300.0
            # shaft: centreline v=0, u in [130, 360], half-width 165 -> 82
            uc = 130.0 if u < 130.0 else (360.0 if u > 360.0 else u)
            wdt = 165.0 - (uc - 130.0) * 0.361
            du = u - uc
            if u < 130.0 or u > 360.0:
                d_shaft = math.sqrt(du * du + v * v) - wdt
            else:
                d_shaft = abs(v) - wdt
            d_meat = d_bulb if d_bulb < d_shaft else d_shaft
            # --- bone mask: capsule u in [364, 478], half-width 30 + knobs ---
            bu2 = 364.0 if u < 364.0 else (478.0 if u > 478.0 else u)
            du2 = u - bu2
            d_bone = math.sqrt(du2 * du2 + v * v) - 30.0
            kx = 486.0
            for ky in (-22.0, 22.0):
                ddx = u - kx
                ddy = v - ky
                dk = math.sqrt(ddx * ddx + ddy * ddy) - 26.0
                if dk < d_bone:
                    d_bone = dk
            o = row + x * 3
            if d_meat > 2.0 and d_bone > 2.0:
                # ---------------- background: warm dark glow + vignette --
                gx = x - 512.0
                gy = y - 500.0
                gr = math.sqrt(gx * gx + gy * gy)
                glow = math.exp(-(gr * gr) / (2.0 * 430.0 * 430.0))
                r = _lerp(14.0, 96.0, glow)
                g = _lerp(8.0, 56.0, glow)
                b = _lerp(4.0, 26.0, glow)
                # soft bokeh
                for (bx, by, br, bi) in _BOKEH:
                    ddx = x - bx
                    ddy = y - by
                    dd = ddx * ddx + ddy * ddy
                    if dd < br * br * 4.0:
                        fall = math.exp(-dd / (2.0 * br * br)) * bi
                        r += 70.0 * fall
                        g += 44.0 * fall
                        b += 18.0 * fall
                # crumbs
                for (cx, cy, cr, sh) in _CRUMBS:
                    ddx = x - cx
                    ddy = y - cy
                    if ddx * ddx + ddy * ddy < cr * cr:
                        r = _lerp(r, 214.0, sh)
                        g = _lerp(g, 150.0, sh)
                        b = _lerp(b, 70.0, sh)
                # faint steam wisps rising above the meat
                if 320.0 < x < 680.0 and y < 360.0:
                    w1 = math.sin(x * 0.021 + y * 0.030) * 0.5 + 0.5
                    w2 = math.sin(x * 0.043 - y * 0.052 + 1.7) * 0.5 + 0.5
                    sa = (0.06 + 0.13 * w1 * w2) * _clamp01((360.0 - y) / 240.0)
                    sa *= _clamp01((x - 320.0) / 60.0) * _clamp01((680.0 - x) / 60.0)
                    r = _lerp(r, 235.0, sa)
                    g = _lerp(g, 225.0, sa)
                    b = _lerp(b, 205.0, sa)
                # soft drop shadow under the chicken (lower-right side)
                sx = (x - 590.0) / 400.0
                sy = (y - 700.0) / 190.0
                se = sx * sx + sy * sy
                if se < 1.0:
                    sh = 0.55 * (1.0 - se)
                    r *= (1.0 - sh)
                    g *= (1.0 - sh)
                    b *= (1.0 - sh)
                buf[o] = int(r) if r < 255.0 else 255
                buf[o + 1] = int(g) if g < 255.0 else 255
                buf[o + 2] = int(b) if b < 255.0 else 255
                continue
            # ---------------- inside chicken ------------------------------
            if d_bone <= d_meat and d_bone <= 2.0:
                # bone: warm ivory, shaded, browned near the meat joint
                joint = _clamp01((420.0 - u) / 60.0)
                base_r = _lerp(226.0, 168.0, joint)
                base_g = _lerp(206.0, 138.0, joint)
                base_b = _lerp(168.0, 96.0, joint)
                sh = _clamp01(0.5 + v / 90.0)
                r = base_r * (0.72 + 0.38 * sh)
                g = base_g * (0.72 + 0.38 * sh)
                b = base_b * (0.72 + 0.38 * sh)
                # glossy bone highlight along the top edge
                if v < -12.0:
                    hl = _clamp01((-12.0 - v) / 26.0) * 0.35
                    r = _lerp(r, 255.0, hl)
                    g = _lerp(g, 250.0, hl)
                    b = _lerp(b, 235.0, hl)
                t = _clamp01(0.5 - d_bone / 3.0)
                r = 0.0 if r < 0.0 else (255.0 if r > 255.0 else r)
                g = 0.0 if g < 0.0 else (255.0 if g > 255.0 else g)
                b = 0.0 if b < 0.0 else (255.0 if b > 255.0 else b)
                if t >= 1.0:
                    buf[o] = int(r)
                    buf[o + 1] = int(g)
                    buf[o + 2] = int(b)
                else:
                    gx = x - 512.0
                    gy = y - 500.0
                    gr = math.sqrt(gx * gx + gy * gy)
                    glow = math.exp(-(gr * gr) / (2.0 * 430.0 * 430.0))
                    br = _lerp(14.0, 96.0, glow)
                    bg = _lerp(8.0, 56.0, glow)
                    bb = _lerp(4.0, 26.0, glow)
                    buf[o] = int(_lerp(br, r, t))
                    buf[o + 1] = int(_lerp(bg, g, t))
                    buf[o + 2] = int(_lerp(bb, b, t))
                continue
            # --- crispy meat ---
            n1 = _vnoise(grid, x * 0.011, y * 0.011)          # mottling
            n2 = _vnoise(grid2, x * 0.085, y * 0.085)         # fine crisp
            n3 = _vnoise(grid, x * 0.11 + 31.0, y * 0.11)     # micro grain
            # warm key light from upper-left
            lx = (x - 360.0) / 640.0
            ly = (y - 300.0) / 640.0
            light = math.exp(-(lx * lx + ly * ly) * 1.1)
            tone = 0.30 + 0.42 * n1 + 0.28 * light
            # deep crust -> mid gold -> pale crisp highlight
            if tone < 0.5:
                tt = tone / 0.5
                r = _lerp(138.0, 203.0, tt)
                g = _lerp(80.0, 134.0, tt)
                b = _lerp(28.0, 54.0, tt)
            else:
                tt = (tone - 0.5) / 0.5
                r = _lerp(203.0, 242.0, tt)
                g = _lerp(134.0, 186.0, tt)
                b = _lerp(54.0, 102.0, tt)
            # fine grain darkens crevices, lightens peaks
            grain = (n3 - 0.5) * 46.0
            r += grain
            g += grain * 0.8
            b += grain * 0.5
            # crack flecks where mid noise crosses 0.5 (kept faint + fine)
            ridge = abs(n2 - 0.5)
            if ridge < 0.035:
                k = (0.035 - ridge) / 0.035
                r *= (1.0 - 0.20 * k)
                g *= (1.0 - 0.20 * k)
                b *= (1.0 - 0.18 * k)
            # crust pits + pale flakes from cell hash (coarser flakes)
            hh = _hash2(x >> 3, y >> 3, 5)
            if hh > 0.92:
                r *= 0.55
                g *= 0.52
                b *= 0.50
            elif hh > 0.885:
                r = _lerp(r, 252.0, 0.45)
                g = _lerp(g, 208.0, 0.45)
                b = _lerp(b, 130.0, 0.45)
            # oil gloss: soft specular pools on the bulb
            for (sx, sy, sr, si) in ((400.0, 350.0, 110.0, 1.0),
                                     (580.0, 540.0, 80.0, 0.7),
                                     (310.0, 540.0, 70.0, 0.55)):
                ddx = x - sx
                ddy = y - sy
                dd = ddx * ddx + ddy * ddy
                if dd < sr * sr * 4.0:
                    gl = math.exp(-dd / (2.0 * sr * sr)) * si
                    r = _lerp(r, 255.0, gl * 0.55)
                    g = _lerp(g, 214.0, gl * 0.55)
                    b = _lerp(b, 130.0, gl * 0.55)
            # warm rim light on the lower-right edge of the meat
            if d_meat > -26.0:
                rim = (d_meat + 26.0) / 26.0
                rw = rim * rim * _clamp01((u - 60.0) / 240.0 + (v / 260.0))
                r = _lerp(r, 255.0, rw * 0.35)
                g = _lerp(g, 150.0, rw * 0.35)
                b = _lerp(b, 60.0, rw * 0.25)
            # herb leaves overlapping the lower edge of the meat
            li, lp = _leaf_mask(x, y)
            if li >= 0:
                vein = 1.0 - abs(lp) * 0.4
                r = 66.0 * vein + 16.0
                g = 150.0 * vein + 22.0
                b = 58.0 * vein + 12.0
                if abs(lp) < 0.08:
                    r, g, b = 165.0, 195.0, 105.0
            # edge anti-alias against the background
            t = _clamp01(0.5 - d_meat / 3.0)
            if t < 1.0:
                gx = x - 512.0
                gy = y - 500.0
                gr = math.sqrt(gx * gx + gy * gy)
                glow = math.exp(-(gr * gr) / (2.0 * 430.0 * 430.0))
                br = _lerp(14.0, 96.0, glow)
                bg = _lerp(8.0, 56.0, glow)
                bb = _lerp(4.0, 26.0, glow)
                r = _lerp(br, r, t)
                g = _lerp(bg, g, t)
                b = _lerp(bb, b, t)
            buf[o] = int(r) if 0.0 < r < 255.0 else (0 if r <= 0.0 else 255)
            buf[o + 1] = int(g) if 0.0 < g < 255.0 else (0 if g <= 0.0 else 255)
            buf[o + 2] = int(b) if 0.0 < b < 255.0 else (0 if b <= 0.0 else 255)
    return bytes(buf)


def write_png(path, rgb):
    """Write 1024x1024 RGB bytes as a PNG with Sub-filtered scanlines."""
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(1)  # filter: Sub
        start = y * stride
        line = rgb[start:start + stride]
        for i in range(stride):
            left = line[i - 3] if i >= 3 else 0
            raw.append((line[i] - left) & 0xFF)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    rgb = render()
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(here, "entry.png")
    size = write_png(local, rgb)
    outdir = "/output"
    if os.path.isdir(outdir):
        write_png(os.path.join(outdir, "entry.png"), rgb)
        print("wrote /output/entry.png")
    print("wrote %s (%d bytes)" % (local, size))
    print("sha256:", hashlib.sha256(open(local, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
