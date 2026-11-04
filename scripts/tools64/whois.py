# -*- coding: utf-8 -*-
"""反查：methodPointers 索引 -> 名字/所属类。

    python whois.py <global-metadata.dat> <base_global> idx [idx ...]
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
from idxmap import method_name
from meta_v557 import Meta, TYPE_DEF_STRIDE


def main():
    path = sys.argv[1]
    base = int(sys.argv[2])
    m = Meta(path)
    idxs = [int(x) for x in sys.argv[3:]]

    types = []
    t_off, t_size = m.abs_off["typeDefinitions"]
    for t in range(t_size // TYPE_DEF_STRIDE):
        b = t_off + t * TYPE_DEF_STRIDE
        name = m.string_at(struct.unpack_from("<i", m.data, b)[0])
        st = struct.unpack_from("<i", m.data, b + 0x24)[0]
        cnt = struct.unpack_from("<H", m.data, b + 0x40)[0]
        types.append((st, cnt, name))
    types.sort()

    for i in idxs:
        g = base + i
        owner = None
        for st, cnt, name in types:
            if st <= g < st + cnt:
                owner = (name, g - st)
                break
        print("methodPtr %-5d global %-6d %-24s %s.%s"
              % (i, g, method_name(m, g),
                 owner[0] if owner else "?",
                 method_name(m, g)))


if __name__ == "__main__":
    main()
