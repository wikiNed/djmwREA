# -*- coding: utf-8 -*-
"""v10：把派遣时长固定为 3 秒。

公式（ZhaoMuManager.SetWuZiAndText）：
    paiQianTime = max(perBattle * get_PaiQianTime(5或20) * ciShu, 60.0)
把这段替换成固定的 3.0，写回 [x19+0xB8]。
"""
import struct
import sys

SRC = r"work/patched/libil2cpp_64_v9.so"
OUT = r"work/patched/libil2cpp_64_v10.so"

WORDS = [
    # (offset, 原值, 新值, 说明)
    (0xE41408, 0xBD405A61, 0x52880008, "movz w8,#0x4000  (3.0f 的高半字)"),
    (0xE4140C, 0x90000CE8, 0x72A80808, "movk w8,#0x4040,lsl#16"),
    (0xE41410, 0xBD4D8D02, 0x1E270100, "fmov s0,w8   -> s0 = 3.0"),
    (0xE41414, 0x1E200900, 0xD503201F, "nop (原 fmul)"),
    (0xE41418, 0x5E21D821, 0xD503201F, "nop (原 scvtf)"),
    (0xE4141C, 0x1E210800, 0xD503201F, "nop (原 fmul ciShu)"),
    (0xE41420, 0x1E224800, 0xD503201F, "nop (原 fmax 60.0)"),
]


def main():
    d = bytearray(open(SRC, "rb").read())
    for off, old, new, desc in WORDS:
        cur = struct.unpack_from("<I", d, off)[0]
        if cur != old:
            print("MISMATCH @%#x 期望 %08x 实际 %08x (%s)" % (off, old, cur, desc))
            sys.exit(1)
        struct.pack_into("<I", d, off, new)
        print("ok @%#x %08x -> %08x  %s" % (off, old, new, desc))
    open(OUT, "wb").write(d)
    print("写出", OUT, len(d))


if __name__ == "__main__":
    main()
