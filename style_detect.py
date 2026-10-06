"""Typography of a page region (bold / italic), classical image analysis on the page scan.
  stroke : stroke thickness relative to letter height (distance transform on the ink skeleton / median glyph height); bold text is thicker
  slant  : the horizontal shear (degrees) that makes the strokes most vertical (sharpest column profile); upright ~0, italic ~10-15
Used to find blocks printed entirely in bold / italic, which the Markdown references write as $\\textbf{..}$ / $\\textit{..}$.
  from style_detect import region_style; region_style(gray_image, (x0, y0, x1, y1)) -> dict(stroke=, slant=, n=) or None
"""
import numpy as np
import cv2
from skimage.morphology import skeletonize


def ink_mask(crop):
    _, m = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = m == 0
    if ink.mean() > 0.5: ink = ~ink          # light text on a dark band
    return ink


def region_style(gray, box, scale=3):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(gray.shape[1], x1), min(gray.shape[0], y1)
    if x1 - x0 < 6 or y1 - y0 < 5: return None
    crop = cv2.resize(gray[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)   # page scans are small: upsample first
    ink = ink_mask(crop)
    if ink.sum() < 30: return None
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    h = [s[3] for s in stats[1:] if s[4] >= 8 and s[3] >= 4]
    if len(h) < 2: return None
    gh = float(np.median(h))
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    sk = skeletonize(ink)
    if sk.sum() < 10: return None
    stroke = 2 * float(np.median(dt[sk])) / gh
    best, ang = -1, 0.0
    H, Wd = ink.shape; inkf = ink.astype(np.float32)
    for a in np.arange(-6, 22, 2.0):
        sh = np.tan(np.radians(a))
        M = np.float32([[1, sh, -sh * H / 2], [0, 1, 0]])
        w = cv2.warpAffine(inkf, M, (Wd, H))
        col = w.sum(axis=0); v = float((col ** 2).sum())
        if v > best: best, ang = v, float(a)
    return {"stroke": stroke, "slant": ang, "n": len(h), "gh": gh}
