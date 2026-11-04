# -*- coding: utf-8 -*-
"""反查：给定 VA，找出它落在哪个方法（methodPointers 最近前驱）。

    python rev.py <lib64.so> <global-metadata.dat> va [va ...]
"""
import struct
import os
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
from whois import main as _  # noqa  (复用其结构，但这里独立实现)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dis64 import load_map

ARR = 0x146E848
COUNT = 4933
BASE = 26588


def main():
    lib, meta, *vas = sys.argv[1:]
    data, _segs = load_map(lib)
    ptrs = []
    for i in range(COUNT):
        p = struct.unpack_from("<Q", data, ARR + i * 8)[0]
        ptrs.append(p)
    order = sorted(range(COUNT), key=lambda i: ptrs[i])

    from idxmap import method_name
    from meta_v557 import Meta
    m = Meta(meta)

    for v in vas:
        va = int(v, 0)
        best = None
        for i in order:
            if ptrs[i] <= va:
                best = i
            else:
                break
        if best is None:
            print("%08x  <不在任何方法内>" % va)
            continue
        end = min([ptrs[j] for j in order if ptrs[j] > ptrs[best]] or [0xFFFFFFFF])
        print("%08x  -> idx %-5d %-38s %s (+0x%x)"
              % (va, best, method_name(m, BASE + best),
                 "命中函数头" if va == ptrs[best] else "函数内", va - ptrs[best]))


if __name__ == "__main__":
    main()
