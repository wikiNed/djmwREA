# -*- coding: utf-8 -*-
"""把 metadata 的 methods 表按「全局方法序号」列出来，用于核对 methodPointers 索引对齐。

用法：
    python idxmap.py <global-metadata.dat> [idx ...]
不给索引时打印表头统计 + 每个类型的方法区间（可 grep 类名）。
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
from meta_v557 import Meta, METHOD_DEF_STRIDE, TYPE_DEF_STRIDE


def method_count(m):
    return m.table.get("methodsCount", 0)


def method_name(m, i):
    off, size = m.abs_off["methods"]
    if i * METHOD_DEF_STRIDE + 4 > size:
        return "<OOB>"
    name_idx = struct.unpack_from("<i", m.data, off + i * METHOD_DEF_STRIDE)[0]
    return m.string_at(name_idx)


def main():
    path = sys.argv[1]
    m = Meta(path)
    print("文件 %s  %d B  magic %08X ver %d  解析自检 %s"
          % (path, len(m.data), m.magic, m.version, m.check()))
    if len(sys.argv) > 2 and sys.argv[2] == "find":
        names = sys.argv[3:]
        for i in range(m.table["methodsCount"]):
            nm = method_name(m, i)
            if nm in names:
                print("idx %-6d %s" % (i, nm))
        return

    idxs = [int(x, 0) for x in sys.argv[2:]]
    if idxs:
        for i in idxs:
            print("idx %-6d %s" % (i, method_name(m, i)))
        return
    print("methodsCount=%d typeCount=%d"
          % (m.table.get("methodsCount", 0), m.table.get("typeDefinitionsCount", 0)))
    t_off, t_size = m.abs_off["typeDefinitions"]
    for t in range(t_size // TYPE_DEF_STRIDE):
        base = t_off + t * TYPE_DEF_STRIDE
        name = m.string_at(struct.unpack_from("<i", m.data, base)[0])
        m_start = struct.unpack_from("<i", m.data, base + 0x24)[0]
        m_cnt = struct.unpack_from("<H", m.data, base + 0x40)[0]
        if m_cnt:
            print("%-45s %d..%d" % (name, m_start, m_start + m_cnt - 1))


if __name__ == "__main__":
    main()
