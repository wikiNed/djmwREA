# -*- coding: utf-8 -*-
"""裁剪并放大截图，便于 OCR 读小字。

    python crop.py <in.png> <out.png> x0 y0 x1 y1 [scale]
"""
import sys

from PIL import Image


def main():
    src, dst = sys.argv[1], sys.argv[2]
    x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
    scale = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
    im = Image.open(src).crop((x0, y0, x1, y1))
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(dst)
    print("%s  %dx%d" % (dst, im.width, im.height))


if __name__ == "__main__":
    main()
