#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读单条 metadata 字面量，输出限长，避免淹没终端。
用法:
    python scripts/peek_literal.py 12154
    python scripts/peek_literal.py 12154 12155 12160
"""
import struct
import sys

from paths import META, require

LIT_OFF = 0x100      # stringLiteral 表: (length:int32, offset:int32) * 16631  ★length 在前
LIT_SIZE = 0x207b8
DAT_OFF = 0x208b8    # stringLiteralData
DAT_SIZE = 0x7a26c


def load():
    require(META, "global-metadata.dat")
    return open(META, "rb").read()


def literal(m, i):
    """返回第 i 条字面量的原始字节；越界/空串返回 None。

    行格式是 length-first：(int32 length, int32 offset)。
    早先写成 (offset, length) 会读出长度 39 万字节的垃圾 —— 那是本次踩过的坑。
    """
    n = LIT_SIZE // 8
    if not (0 <= i < n):
        return None
    ln, lo = struct.unpack_from("<ii", m, LIT_OFF + i * 8)
    if ln <= 0 or lo < 0 or lo + ln > DAT_SIZE:
        return None
    return m[DAT_OFF + lo: DAT_OFF + lo + ln]


def main(argv):
    if not argv:
        print("usage: peek_literal.py <index> [index ...]")
        return 2
    m = load()
    print("literal rows declared by table =", LIT_SIZE // 8)
    for s in argv:
        i = int(s, 0)
        v = literal(m, i)
        if v is None:
            print("%6d (0x%x) -> <invalid/empty>" % (i, i))
            continue
        txt = v.decode("utf-8", "replace")
        head = txt if len(txt) <= 120 else txt[:120] + "...(+%d chars)" % (len(txt) - 120)
        print("%6d (0x%x) len=%-4d %r" % (i, i, len(v), head))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

