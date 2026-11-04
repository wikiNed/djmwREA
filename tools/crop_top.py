#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁剪 _cur.png 顶部资源条并放大，供 tools/ocr.ps1 识别。

用法: python tools/crop_top.py [x0 y0 x1 y1]
默认裁 (620,10)-(1080,130)，4x 放大 -> work/live/_top.png
"""
import sys
from PIL import Image

SRC = r"E:\DSH\game\djmwREA\work\live\_cur.png"
DST = r"E:\DSH\game\djmwREA\work\live\_top.png"

box = (620, 10, 1080, 130)
if len(sys.argv) == 5:
    box = tuple(int(v) for v in sys.argv[1:5])

img = Image.open(SRC).crop(box)
img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
img.save(DST)
print("saved", DST, img.size)
