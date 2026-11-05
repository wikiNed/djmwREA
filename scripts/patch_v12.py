# -*- coding: utf-8 -*-
"""v12：宝石升级 90% / 升级消耗 1/10 / 欧气非气恒 50 / 神秘商店库存不减。

全部基于 v11 的 so（work/patched/libil2cpp_64_v11.so）。

1) 成功率下限 90%
   GetLevelUpChengGongLv 收尾（v11 已改成 max(x, 0.75)）：
     0xEB6BD0  fmov s1,#0.75  ->  ldr s1,[pc,#0x936EC]（指向 0xF4A2BC 的 0.9f）
     0xEB6BD4  fmax s0,s0,s1  （保持）
   0.9f = 0x3F666666 不是 VFP 立即数（不能 fmov），全库仅一份在 VA 0xF4A2BC。

2) 升级消耗 1/10
   GetLevelUpSuiPianShu @0xEB681C 有两份相同的收尾副本：
     副本A 0xEB6A34/38/3C/40   副本B 0xEB690C/10/14/18
   原：ucvtf d1,x19 / fmov s2,#1.0 / fcvt s1,d1 / fsub s0,s2,s0(折扣)
   改：ucvtf s0,x19 / movz w8,#0xCCCD / movk w8,#0x3DCC,lsl#16 / fmov s1,w8(=0.1f)
   之后 0xEB6A4C / 0xEB6924 的 fmul s0,s0,s1 就变成 base*0.1。

3) 欧气 / 非气 恒 50
   get_OuQiShuLiang @0xE5F420、get_FeiQiShuLiang @0xE5F428 首条 -> mov w0,#50
   RemoveOuQiShu @0xE5F534、RemoveFeiQiShu @0xE5F630 首条 -> ret

4) 神秘商店库存不减
   SMShopShangPin.RemoveKuCun @0xEB0F3C：
     前两条 stp 改成 mov w0,#1 + ret（永远"扣减成功"，但不改库存）
"""
import struct
import sys

SRC = r"work/patched/libil2cpp_64_v11.so"
OUT = r"work/patched/libil2cpp_64_v12.so"

WORDS = [
    # --- 1) 宝石升级成功率下限 90% ---
    (0xEB6BD0, 0x1E2D1001, 0x1C49B761, "ldr s1,[pc,#0x936ec] -> 0.9f @0xF4A2BC"),

    # --- 2) 升级消耗 1/10（两份副本）---
    (0xEB6A34, 0x9E630261, 0x9E230260, "A: ucvtf s0,x19"),
    (0xEB6A38, 0x1E2E1002, 0x529999A8, "A: movz w8,#0xCCCD"),
    (0xEB6A3C, 0x1E624021, 0x72A7B988, "A: movk w8,#0x3DCC,lsl#16"),
    (0xEB6A40, 0x1E203840, 0x1E270101, "A: fmov s1,w8 (0.1f)"),
    (0xEB690C, 0x9E630261, 0x9E230260, "B: ucvtf s0,x19"),
    (0xEB6910, 0x1E2E1002, 0x529999A8, "B: movz w8,#0xCCCD"),
    (0xEB6914, 0x1E624021, 0x72A7B988, "B: movk w8,#0x3DCC,lsl#16"),
    (0xEB6918, 0x1E203840, 0x1E270101, "B: fmov s1,w8 (0.1f)"),

    # --- 3) 欧气 / 非气 恒 50 ---
    (0xE5F420, 0xB9415000, 0x52800640, "get_OuQiShuLiang -> mov w0,#50"),
    (0xE5F428, 0xB9415400, 0x52800640, "get_FeiQiShuLiang -> mov w0,#50"),
    (0xE5F534, 0xA9BE4FF4, 0xD65F03C0, "RemoveOuQiShu -> ret"),
    (0xE5F630, 0xA9BE4FF4, 0xD65F03C0, "RemoveFeiQiShu -> ret"),

    # --- 4) 神秘商店库存不减 ---
    (0xEB0F3C, 0xA9BE4FF4, 0x52800020, "RemoveKuCun -> mov w0,#1"),
    (0xEB0F40, 0xA9017BFD, 0xD65F03C0, "RemoveKuCun -> ret"),
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
