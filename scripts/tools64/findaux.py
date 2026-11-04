# -*- coding: utf-8 -*-
"""按子串列出方法：名字 / methodPtr 索引 / 64 位入口地址。

    python findaux.py <global-metadata.dat> <lib64.so> <substr> [substr ...]
"""
import struct
import os
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idxmap import method_name
from meta_v557 import Meta
from dis64 import load_map

ARR = 0x146E848
COUNT = 4933
BASE = 26588


def main():
    meta, lib = sys.argv[1], sys.argv[2]
    subs = sys.argv[3:]
    m = Meta(meta)
    data, _ = load_map(lib)
    ptrs = [struct.unpack_from("<Q", data, ARR + i * 8)[0] for i in range(COUNT)]
    for i in range(min(m.table["methodsCount"], COUNT + BASE)):
        nm = method_name(m, i)
        if not nm or not any(s.lower() in nm.lower() for s in subs):
            continue
        idx = i - BASE
        addr = ptrs[idx] if 0 <= idx < COUNT else 0
        print("idx %-5s %08x  %s" % (idx if 0 <= idx < COUNT else "-", addr, nm))


if __name__ == "__main__":
    main()
