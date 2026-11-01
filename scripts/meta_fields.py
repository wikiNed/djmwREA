#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按类型名查 IL2CPP 字段布局 —— 反汇编前必备。

为什么要这个脚本
----------------
要 hook 或读一个托管对象，先得知道字段在对象里的偏移。规则很固定但容易算错：

    32 位：offset = 0x08 + index * 4
    64 位：offset = 0x10 + index * 8

`0x08` / `0x10` 的前置部分是对象头（`klass` 指针 + `monitor`）：
    32 位 +0x00 = klass, +0x04 = monitor
    64 位 +0x00 = klass, +0x08 = monitor

⚠ 常见误判：`+0x08` 在 32 位下**第一个字段就在这儿**，不是 `m_CachedPtr`。
只有 UnityEngine.Object 的子类才有 `m_CachedPtr`，且它在 `+0x10`（32 位）。
用「+0x08 == 0 所以对象已销毁」下结论是错的 —— 那只说明第一个字段是 null。

用法
----
    python meta_fields.py GameGUI                 # 列字段 + 32/64 位偏移
    python meta_fields.py GameGUI ChongWu         # 只列名字含子串的
    python meta_fields.py --class-of-var 22       # 反查：字段索引 → 名字

    from meta_fields import field_offset, fields_of
    field_offset(22)        # -> {'i32': 0x60, 'i64': 0xC0}
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_v557 import Meta

#: 对象头大小：klass(ptr) + monitor(ptr)
OBJ_HEADER_32 = 0x08
OBJ_HEADER_64 = 0x10


def field_offset(index: int, is64: bool = False) -> int:
    """字段索引 → 对象内绝对偏移。"""
    return (OBJ_HEADER_64 + index * 8) if is64 else (OBJ_HEADER_32 + index * 4)


def fields_of(cls: str, meta: Meta | None = None):
    """返回 [(index, name, type_index, token, off32, off64), ...]。"""
    m = meta or Meta()
    out = []
    for j, name, type_idx, tok in m.fields_of(cls):
        out.append((j, name, type_idx, tok, field_offset(j), field_offset(j, True)))
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return 1

    m = Meta()

    if argv[0] == "--class-of-var":
        # 有些 dump 里只有字段序号，用这个反查序号对应哪一行
        want = {int(x) for x in argv[1:]}
        t_off, t_size = m.abs_off["typeDefinitions"]
        from meta_v557 import TYPE_DEF_STRIDE
        for i in range(t_size // TYPE_DEF_STRIDE):
            base = t_off + i * TYPE_DEF_STRIDE
            name = m.string_at(int.from_bytes(m.data[base:base + 4], "little", signed=True))
            f_start = int.from_bytes(m.data[base + 0x20:base + 0x24], "little", signed=True)
            f_count = int.from_bytes(m.data[base + 0x44:base + 0x46], "little")
            if any(f_start <= j < f_start + f_count for j in want):
                rel = [j - f_start for j in sorted(want) if f_start <= j < f_start + f_count]
                print("%-40s fieldStart=%d count=%d  相对索引=%s"
                      % (name, f_start, f_count, rel))
        return 0

    cls = argv[0]
    needle = argv[1] if len(argv) > 1 else None
    rows = fields_of(cls, m)
    if not rows:
        print("找不到类型或它没有字段：%s" % cls)
        return 1

    ti, _base = m.type_by_name(cls)
    print("类型 %s  (type_index=%d, 字段数=%d)" % (cls, ti, len(rows)))
    print("  %-4s %-30s %-6s %-12s %-8s %-8s" % ("idx", "name", "type", "token", "off32", "off64"))
    for j, name, type_idx, tok, o32, o64 in rows:
        if needle and needle.lower() not in name.lower():
            continue
        print("  %-4d %-30s %-6d 0x%08x   0x%02x     0x%02x"
              % (j, name, type_idx, tok, o32, o64))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
