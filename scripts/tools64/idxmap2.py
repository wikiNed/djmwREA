# -*- coding: utf-8 -*-
"""核对 methodPointers 索引：给出锚点类的方法与全局序号。"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
from idxmap import method_name
from meta_v557 import Meta, TYPE_DEF_STRIDE


def type_span(m, name):
    t_off, t_size = m.abs_off["typeDefinitions"]
    for t in range(t_size // TYPE_DEF_STRIDE):
        base = t_off + t * TYPE_DEF_STRIDE
        if m.string_at(struct.unpack_from("<i", m.data, base)[0]) == name:
            st = struct.unpack_from("<i", m.data, base + 0x24)[0]
            cnt = struct.unpack_from("<H", m.data, base + 0x40)[0]
            return st, cnt
    return None, None


def main():
    path = sys.argv[1]
    m = Meta(path)
    print("== %s" % path)
    # 锚点：32 位 methodPtr 652/669/673
    anchors = {"GetFenJieSuiPianShu": 652, "AddBaoShiSuiPian": 669, "FenSuiBaoShi": 673}
    found = {}
    for i in range(m.table["methodsCount"]):
        nm = method_name(m, i)
        if nm in anchors and nm not in found:
            found[nm] = i
    offs = {k: found[k] - v for k, v in anchors.items() if k in found}
    print("锚点全局序号 %s" % found)
    print("推算模块基址 %s" % offs)
    base = min(offs.values()) if offs else 26588
    for cls in sys.argv[2:]:
        st, cnt = type_span(m, cls)
        if st is None:
            print("%-20s <类未找到>" % cls)
            continue
        for k in range(cnt):
            g = st + k
            print("%-20s global %-6d methodPtr %-6d %s"
                  % (cls, g, g - base, method_name(m, g)))


if __name__ == "__main__":
    main()
