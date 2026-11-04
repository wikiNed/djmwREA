# -*- coding: utf-8 -*-
"""在 64 位 lib 里找常量 / 找可用代码洞（长串 0x00 或 0xCC）。

    python hunt64.py <so> <hexconst> [start_va] [end_va]
    python hunt64.py <so> --cave [start_va] [end_va]
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dis64 import load_map, va_to_off


def main():
    path = sys.argv[1]
    data, segs = load_map(path)
    mode = sys.argv[2]
    start = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x2ff880
    end = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x1200000
    lo, hi = va_to_off(segs, start), va_to_off(segs, end)

    if mode == "--cave":
        best = []
        i = lo
        while i < hi:
            if data[i] == 0:
                j = i
                while j < hi and data[j] == 0:
                    j += 1
                if j - i >= 16:
                    best.append((i, j - i))
                i = j
            else:
                i += 1
        # 按“离 0xeb6150 近 + 长度够”排序
        for off, ln in best:
            va = start + (off - lo)
            print("%08x  %d bytes" % (va, ln))
        print("// %d 个洞" % len(best))
        return

    val = int(mode, 16)
    pat = struct.pack("<I", val)
    hits = []
    i = data.find(pat, lo, hi)
    while i != -1:
        hits.append(start + (i - lo))
        i = data.find(pat, i + 1, hi)
    for va in hits:
        print("%08x" % va)
    print("// %d 处 0x%08X" % (len(hits), val))


if __name__ == "__main__":
    main()
