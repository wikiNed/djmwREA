#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按类型名查 IL2CPP 方法表 —— meta_v557.Meta 的薄 CLI 包装。

这个脚本存在的意义：不必记住 typeDefinitions / methods 的偏移与步长，
直接给类名就能列出它的全部方法（含 token / flags / 参数个数），
用来在反汇编前先确认「这个方法存在、参数几个、是不是 public」。

    python meta_types.py GameGUI              # 列全部方法
    python meta_types.py GameGUI OpenChongWu  # 只列名字含该子串的
    python meta_types.py --all 0x060005        # 按 token 前缀反查

★ 步长记忆口诀（与网上多数文档不符，实测为准）：
    Il2CppTypeDefinition   0x58   （不是 0x5C）
    Il2CppMethodDefinition 0x20   （不是 0x2C）
    Il2CppFieldDefinition  12     （不是 0x10）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_v557 import Meta

#: flags 里我们真正关心的几位
PUBLIC = 0x0006
STATIC = 0x0010
VIRTUAL = 0x0040
ABSTRACT = 0x0400


def describe(flags: int) -> str:
    bits = []
    if flags & PUBLIC:
        bits.append("public")
    else:
        bits.append("private")
    if flags & STATIC:
        bits.append("static")
    if flags & VIRTUAL:
        bits.append("virtual")
    if flags & ABSTRACT:
        bits.append("abstract")
    return " ".join(bits)


def main(argv):
    if not argv:
        print(__doc__)
        return 1

    m = Meta()

    if argv[0] == "--all":
        prefix = argv[1] if len(argv) > 1 else "0x"
        t_off, t_size = m.abs_off["typeDefinitions"]
        from meta_v557 import TYPE_DEF_STRIDE
        hit = 0
        for i in range(t_size // TYPE_DEF_STRIDE):
            base = t_off + i * TYPE_DEF_STRIDE
            cls = m.string_at(int.from_bytes(m.data[base:base + 4], "little", signed=True))
            for k, name, tok, fl, slot, pcnt in m.methods_of(cls):
                if ("0x%08x" % tok).startswith(prefix):
                    print("%-32s [%2d] %-34s tok=0x%08x %s pcnt=%d"
                          % (cls, k, name, tok, describe(fl), pcnt))
                    hit += 1
        print("命中 %d" % hit)
        return 0

    cls = argv[0]
    needle = argv[1] if len(argv) > 1 else None
    ms = m.methods_of(cls)
    if not ms:
        print("找不到类型：%s" % cls)
        return 1

    ti, _base = m.type_by_name(cls)
    print("类型 %s  (type_index=%d, 方法数=%d)" % (cls, ti, len(ms)))
    for k, name, tok, fl, slot, pcnt in ms:
        if needle and needle.lower() not in name.lower():
            continue
        print("  [%2d] %-34s tok=0x%08x slot=%-6d pcnt=%d  %s"
              % (k, name, tok, slot, pcnt, describe(fl)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
