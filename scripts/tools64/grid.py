# -*- coding: utf-8 -*-
"""把截图压成字符网格，用来看「版式」而不是细节。

    python grid.py <png> [cols] [rows]
字符：. 很暗  d 暗  r 偏红  y 偏黄  g 偏绿  c 偏青  b 偏蓝  m 偏紫  w 亮
"""
import sys

from PIL import Image

BRIGHT = " .:-=+*#%@"


def classify(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 40:
        return "."
    if mx < 80:
        return "d"
    if mx - mn < 25:
        return "w" if mx > 200 else ("+" if mx > 120 else "-")
    if r == mx and g >= b:
        return "y" if g > r * 0.6 else "r"
    if r == mx:
        return "m" if b > g else "r"
    if g == mx:
        return "c" if b > r * 0.8 else "g"
    return "b"


def main():
    path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 44
    im = Image.open(path).convert("RGB").resize((cols, rows))
    for y in range(rows):
        line = ""
        for x in range(cols):
            line += classify(*im.getpixel((x, y)))
        print("%02d %s" % (y, line))


if __name__ == "__main__":
    main()
