#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IL2CPP stringLiteral 表解析 —— 找出代码里硬编码的字符串常量。

这个表是什么
------------
代码里 `ldstr "xxx"` 这类常量不直接内联在指令里，而是走「用法索引 → 哨兵 → 表项」
三条链路。运行时 .data 段里存的是哨兵：

    sentinel = 0xA0000000 | ((literal_index << 1) | 1)

（32 位每项 4 字节，64 位每项 8 字节但高 32 位恒 0。）
拿到哨兵值就能反解出 index，再查本表拿到真正的字符串。

★ 表项格式是 **(length, offset)** 两个 int32，不是 (offset, length)。
这是最容易搞反的地方 —— 反了以后 length 会变成巨大或负数，读出来全是垃圾。

    length = 字符串字节数（不含结尾 NUL）
    offset = 相对 stringLiteralData 段起点的偏移

实测 v5.5.7：70448/8 = 8806 条，可解 8806 条（空洞 0 条）。
注意 v27 的头两条是「空串 + 单 NUL + 双 NUL」这类填充项（len=0/1/2），不是脏数据。

⚠ 关于「哨兵 index」与「表项下标」是否同一个东西
--------------------------------------------------
在 v5.9.2（64 位）上，`0x35e7408 → addend 0x36FC618 → 0xA0005EF3 → index 12153`
这条链解出的第 12153 条表项**确实是** `hqgames@2013`，即 index 与表项下标一致。

但在 **v5.5.7 上不要直接套这个等式**：实测 `SaveFile.es3` 位于表项 **[3386]**
（`len=12 off=0x17a85`），而 `0xA00039CD → 7398` 对应的是一条游戏文案，
两者不是同一个字符串。也就是说 v5.5.7 的哨兵取值与表项下标之间存在额外偏移，
**尚未解出**。在 v5.5.7 上请以 `find` 按内容搜的结果为准，不要用 `sentinel` 反推出的
index 直接当表项下标。

用法
----
    python meta_literal.py stat                    # 总条数 / 可解数
    python meta_literal.py get 3386                # 按索引取
    python meta_literal.py find SaveFile           # 按内容搜
    python meta_literal.py sentinel 0xa0005ef3     # 哨兵值 → 字符串
    python meta_literal.py dump 3300 30            # 连续打印一段

    from meta_literal import decode_sentinel, literal_at
    decode_sentinel(0xA0005EF3)   # -> 12153
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_v557 import Meta

SENTINEL_BASE = 0xA0000000


def decode_sentinel(value: int) -> int | None:
    """哨兵值 → literal index。不合法（高 20 位不是 0xA00 或末位不是 1）返回 None。

    注意 (value >> 20) == 0xA00 这个判据在 JS 里必须写成 (value >>> 20)，
    否则超过 0x7FFFFFFF 的值会做有符号转换而永假。
    """
    if (value >> 20) != 0xA00 or (value & 1) != 1:
        return None
    return (value >> 1) & 0x7FFFFFF


def encode_sentinel(index: int) -> int:
    """literal index → 哨兵值。

    ⚠ 注意方向：本函数假设「哨兵 index == 表项下标」，这在 v5.9.2 上成立，
    在 v5.5.7 上**未知**（见模块 docstring 的警告）。仅用于展示与 64 位对照。
    """
    return SENTINEL_BASE | ((index << 1) | 1)


def literal_at(index: int, meta: Meta | None = None) -> str | None:
    m = meta or Meta()
    table = m.literal_table()
    if 0 <= index < len(table):
        return table[index]
    return None


def main(argv):
    m = Meta()
    cmd = argv[0] if argv else "stat"

    if cmd == "stat":
        table = m.literal_table()
        ok = sum(1 for x in table if x is not None)
        print("stringLiteral 段 %d 字节 → %d 条（每条 8 字节）" % (
            m.abs_off["stringLiteral"][1], len(table)))
        print("可解 %d 条，空洞 %d 条" % (ok, len(table) - ok))
        return 0

    if cmd == "get":
        idx = int(argv[1], 0)
        v = literal_at(idx, m)
        print("[%d] = %r" % (idx, v))
        return 0 if v is not None else 1

    if cmd == "sentinel":
        val = int(argv[1], 0)
        idx = decode_sentinel(val)
        if idx is None:
            print("0x%08X 不是合法哨兵" % val)
            return 1
        print("0x%08X → index %d → %r" % (val, idx, literal_at(idx, m)))
        return 0

    if cmd == "find":
        kw = argv[1]
        table = m.literal_table()
        hit = 0
        for i, s in enumerate(table):
            if s is not None and kw in s:
                print("[%5d] 0x%08x  %r" % (i, encode_sentinel(i), s))
                hit += 1
        print("命中 %d" % hit)
        return 0

    if cmd == "dump":
        start = int(argv[1], 0)
        cnt = int(argv[2]) if len(argv) > 2 else 10
        table = m.literal_table()
        for i in range(start, min(start + cnt, len(table))):
            print("[%5d] 0x%08x  %r" % (i, encode_sentinel(i), table[i]))
        return 0

    print("未知命令：%s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
