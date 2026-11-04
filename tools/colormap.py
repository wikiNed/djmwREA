# -*- coding: utf-8 -*-
"""Coarse color map of full screen: R/B/G dominant chars to see structures."""
import sys
from PIL import Image

im = Image.open(sys.argv[1]).convert('RGB')
px = im.load()
W, H = im.size
cw, ch = 24, 24
out = []
for cy in range(0, H, ch):
    row = ''
    for cx in range(0, W, cw):
        rs = gs = bs = n = 0
        for y in range(cy, min(cy + ch, H), 4):
            for x in range(cx, min(cx + cw, W), 4):
                r, g, b = px[x, y]
                rs += r; gs += g; bs += b; n += 1
        r, g, b = rs / n, gs / n, bs / n
        lum = (r + g + b) / 3
        if lum < 40: ch_ = ' '          # black
        elif lum > 215: ch_ = '@'       # white
        elif b > r + 40 and b > g + 30: ch_ = 'B'  # blue
        elif r > b + 40 and r > g + 30: ch_ = 'R'  # red
        elif g > r + 25 and g > b + 25: ch_ = 'G'  # green
        elif r > 200 and g > 150 and b < 110: ch_ = 'Y'  # yellow/gold
        elif lum < 100: ch_ = '.'
        elif lum < 160: ch_ = '+'
        else: ch_ = '='
        row += ch_
    out.append('%4d %s' % (cy, row))
print('\n'.join(out))
