# -*- coding: utf-8 -*-
"""截图粗分类：作弊惩罚屏是纯暗红底，世界地图/登录页颜色分布完全不同。

    python shotstat.py <png> [png...]
"""
import sys

from PIL import Image


def stat(path):
    im = Image.open(path).convert("RGB")
    im = im.resize((160, 350))
    px = list(im.getdata())
    n = len(px)
    red = sum(1 for r, g, b in px if r > 70 and r > g * 2 and r > b * 2)
    white = sum(1 for r, g, b in px if r > 200 and g > 200 and b > 200)
    dark = sum(1 for r, g, b in px if r < 40 and g < 40 and b < 40)
    avg = tuple(sum(c[i] for c in px) // n for i in range(3))
    # 顶部/底部条带（UI 常见）
    top = im.crop((0, 0, 160, 40)).resize((1, 1)).getpixel((0, 0))
    return dict(red=red * 100.0 / n, white=white * 100.0 / n,
                dark=dark * 100.0 / n, avg=avg, top=top)


for p in sys.argv[1:]:
    s = stat(p)
    print("%-40s red %5.1f%%  white %5.1f%%  dark %5.1f%%  avg %s  top %s"
          % (p.split("\\")[-1], s["red"], s["white"], s["dark"], s["avg"], s["top"]))
