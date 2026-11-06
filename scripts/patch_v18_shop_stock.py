# -*- coding: utf-8 -*-
"""v18：魔窟商店购买不再消耗库存次数（kuCun 不增长）。

用户反馈（m17555）：「魔物碎片保持1000不减了，但是魔窟商店的商品购买还是消耗次数」。

分析：
  `IsBuy @0x8C8600` 只是余额比较（读 Date_MoShiKu+0x58/+0x60 与价格 [x19,#0x3c] 比），
  不扣任何东西。真正被“消耗”的是商品自己的库存计数：

      MoShiKuShangPinClass.GouMaiShangPin
        shangPinKuCunMax  //0x44
        shangPinKuCun     //0x48   <- 每次买成功 +1，涨到 Max 就售罄

  八个购买分支完全是同一段模式（地址不同、指令字节完全相同）：

      0x..AA1303E0  mov x0, x19
      0x..11000508  add w8, w8, #1
      0x..B9004A68  str w8, [x19, #0x48]

  把 `add w8,w8,#1` 换成 NOP 后，w8 仍是 `ldr w8,[x19,#0x48]` 读到的原值，
  再原样写回 —— 库存恒定，永远买得到。

八处 add 的地址：
  0x8C8934  0x8C8A0C  0x8C8B30  0x8C8C2C
  0x8C8D94  0x8C8EA0  0x8C8FAC  0x8C90B8
"""
import struct

SRC = r"work/patched/libil2cpp_64_v17.so"
OUT = r"work/patched/libil2cpp_64_v18.so"

NOP = 0xD503201F
ADD_W8_1 = 0x11000508       # add w8, w8, #1

ADDRS = [
    0x8C8934, 0x8C8A0C, 0x8C8B30, 0x8C8C2C,
    0x8C8D94, 0x8C8EA0, 0x8C8FAC, 0x8C90B8,
]


def main():
    d = bytearray(open(SRC, "rb").read())
    new = bytearray(d)
    for off in ADDRS:
        cur = struct.unpack_from("<I", d, off)[0]
        if cur != ADD_W8_1:
            print("MISMATCH @0x%X got 0x%08X -- 跳过" % (off, cur))
            continue
        struct.pack_into("<I", new, off, NOP)
        print("ok @0x%08x add w8,w8,#1 -> nop  (魔窟商店库存不减)")
    with open(OUT, "wb") as f:
        f.write(new)
    print("写出", OUT)


if __name__ == "__main__":
    main()
