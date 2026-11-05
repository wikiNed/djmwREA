# -*- coding: utf-8 -*-
"""v13：修 v12 里“欧气/非气”和“神秘商店库存”两处没生效的问题。

为什么 v12 没用：
1) 欧气/非气：v12 改的是 get_OuQiShuLiang / get_FeiQiShuLiang，但界面是直接读字段
   ouQiShuLiang //0x150、feiQiShuLiang //0x154（显示成 “8/199”，199 = qiTiShuMax）。
   ⇒ 改成在 LoadOuQiFeiQi 里把两个字段直接写成 50，并让 Add* 不再累加。
2) 神秘商店：v12 只把 RemoveKuCun 改成“恒成功”，但 kuCun 本来就是 0（之前买空了），
   所以全部显示缺货。⇒ 改成 LoadKuCun 每次把 kuCun = kuCunMax。

所有机器码均用 capstone 反解确认：
    52800648  mov w8, #0x32
    B9015008  str w8, [x0, #0x150]
    B9015408  str w8, [x0, #0x154]
    D65F03C0  ret
    B9403008  ldr w8, [x0, #0x30]
    B9002C08  str w8, [x0, #0x2c]
"""
import struct
import sys

SRC = r"work/patched/libil2cpp_64_v12.so"
OUT = r"work/patched/libil2cpp_64_v13.so"

# (offset, 原值, 新值, 说明)
WORDS = [
    # --- 欧气 / 非气：LoadOuQiFeiQi 直接写 50 ---
    (0xE5F430, 0xA9BE4FF4, 0x52800648, "LoadOuQiFeiQi: mov w8,#0x32 (50)"),
    (0xE5F434, 0xA9017BFD, 0xB9015008, "  str w8,[x0,#0x150]  (欧气)"),
    (0xE5F438, 0x910043FD, 0xB9015408, "  str w8,[x0,#0x154]  (非气)"),
    (0xE5F43C, 0xD0003194, 0xD65F03C0, "  ret"),
    # --- 不再累加 ---
    (0xE5F4B4, 0xA9BE4FF4, 0xD65F03C0, "AddOuQiShu -> ret"),
    (0xE5F5B0, 0xA9BE4FF4, 0xD65F03C0, "AddFeiQiShu -> ret"),
    # --- 神秘商店：LoadKuCun 把库存重置为上限 ---
    (0xEB0C74, 0xA9BE4FF4, 0xB9403008, "LoadKuCun: ldr w8,[x0,#0x30]  (kuCunMax)"),
    (0xEB0C78, 0xA9017BFD, 0xB9002C08, "  str w8,[x0,#0x2c]  (kuCun)"),
    (0xEB0C7C, 0x910043FD, 0xD65F03C0, "  ret"),
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
