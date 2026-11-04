# -*- coding: utf-8 -*-
"""按虚拟地址读 64 位 lib 里的 4/8 字节值。

    python peek.py <so> <va> [n]      # 每 4 字节一组，顺带给出 float 解释
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dis64 import load_map, va_to_off


def main():
    path, va = sys.argv[1], int(sys.argv[2], 0)
    n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 4
    data, segs = load_map(path)
    off = va_to_off(segs, va)
    if off is None:
        print("va 未映射")
        return
    for i in range(n):
        b = data[off + i * 4: off + i * 4 + 4]
        w = struct.unpack("<I", b)[0]
        f = struct.unpack("<f", b)[0]
        d = struct.unpack("<d", data[off + i * 8: off + i * 8 + 8])[0] if i == 0 else 0
        print("%08x  %08X  float %-14g  fileoff 0x%x" % (va + i * 4, w, f, off + i * 4))
    b8 = data[off: off + 8]
    print("qword @%08x = 0x%016X  (double %g)" % (va, struct.unpack("<Q", b8)[0],
                                                   struct.unpack("<d", b8)[0]))


if __name__ == "__main__":
    main()
