# -*- coding: utf-8 -*-
"""按子串搜方法名（metadata 64/32 通用）。

    python findm.py <global-metadata.dat> <子串> ...
"""
import struct
import os
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idxmap import method_name
from meta_v557 import Meta


def main():
    path = sys.argv[1]
    pats = sys.argv[2:]
    m = Meta(path)
    total = m.table["methodsCount"]
    for i in range(total):
        nm = method_name(m, i)
        for p in pats:
            if p.lower() in nm.lower():
                print("idx %-6d %s" % (i, nm))
                break


if __name__ == "__main__":
    main()
