# -*- coding: utf-8 -*-
"""v11：宝石升级成功率下限 75%。

ShenQiBaoShiDateModel.GetLevelUpChengGongLv @0xEB6A6C 的结尾：

    fadd s0, s8, s0        ; 基础 + 加成
    fmov s1, #1.0
    fmin s0, s0, s1        ; 上限 1.0
    ret

改成：

    fmov s1, #0.75
    fmax s0, s0, s1        ; 下限 0.75（高于 0.75 的保持原值）

编码均已用 capstone 反解确认：
    1e2d1001  fmov s1, #0.75000000
    1e214800  fmax s0, s0, s1
"""
import struct
import sys

SRC = r"work/patched/libil2cpp_64_v10.so"
OUT = r"work/patched/libil2cpp_64_v11.so"

WORDS = [
    (0xEB6BD0, 0x1E2E1001, 0x1E2D1001, "fmov s1,#1.0 -> fmov s1,#0.75"),
    (0xEB6BD4, 0x1E215800, 0x1E214800, "fmin s0,s0,s1 -> fmax s0,s0,s1"),
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
