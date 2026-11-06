# -*- coding: utf-8 -*-
"""v16：魔物碎片恒 1000（修 v15 失败的原因）+ 商店仍消耗的问题。

用户反馈（m17490 / m17515）：
  - 魔物碎片显示 2 / 3，没到 1000
  - 魔窟商店买完还是会扣

根因（v15 为什么没用）：
  `MoWuSuiPianShuLiang` 有 **两份**：
    1) 存档字段 `Date_MoShiKu.MoWuSuiPian //0x30`（ulong）
    2) 管理器缓存字段 `MoShiKuManager +0x60`  <-- 界面读的是这个
  v15 只把 getter `0x8C5630` 改成 `mov w0,#1000`，但界面不走 getter，直接读 +0x60。
  而 `+0x60` 的写入点是：

    `MoShiKuManager.LoadMoShiKuManager @0x8C7B7C`：
        0x8C7DD4  ldr x9,[x9,#0x30]     ; = 存档的 MoWuSuiPian
        0x8C7DD8  str x9,[x19,#0x60]    ; 写进界面字段  ← 每次加载/开商店都会把存档值灌回来

    `MoShiKuManager.RemoveMoWuSuiPian @0x8C60C8`：
        0x8C6168  ldr x8,[x19,#0x60]
        0x8C616C  sub x8,x8,x20
        0x8C6170  bic x8,x8,x8,asr#63   ; 夹到 >=0
        0x8C6174  str x8,[x19,#0x60]

  所以正确做法是把「加载同步」这一处直接写死 1000 —— 之后再怎么扣，
  只要界面不重开就一直是 1000；重开商店又会灌一次 1000。

  `mov w9,#1000` = 0x52807D09（写 w9 会清零高 32 位，等价于 x9=1000）。

同时魔石 `+0x58` 也是在同一个 Load 里从存档同步的（0x8C7DBC），
一并写死 1000，避免开商店后被存档的 86493929 覆盖。
"""
import struct

SRC = r"work/patched/libil2cpp_64_v15.so"
OUT = r"work/patched/libil2cpp_64_v16.so"

RET = 0xD65F03C0
NOP = 0xD503201F

MOV_W9_1000 = 0x52807D09      # mov w9, #1000  (x9 = 1000)

WORDS = [
    # ---- 魔物碎片：加载同步点写死 1000（替换 ldr x9,[x9,#0x30]）----
    (0x8C7DD4, 0xF9401929, MOV_W9_1000,
     "LoadMoShiKuManager: ldr x9,[x9,#0x30] -> mov w9,#1000（魔物碎片恒 1000）"),

    # ---- 魔石：同一个 Load 里的同步点也写死 1000 ----
    # 0x8C7DB8  ldr x9,[x9,#0x18]  ; 存档的 MoShiShuLiang
    # 0x8C7DBC  str x9,[x19,#0x58]
    (0x8C7DB8, 0xF9400D29, MOV_W9_1000,
     "LoadMoShiKuManager: ldr x9,[x9,#0x18] -> mov w9,#1000（魔石恒 1000）"),

    # ---- RemoveMoWuSuiPian 本体：直接返回，任何路径都不扣 ----
    (0x8C6168, 0xF9403268, 0x52800008,
     "RemoveMoWuSuiPian: ldr x8,[x19,#0x60] -> mov w8,#0"),
    (0x8C616C, 0xCB140108, NOP, "RemoveMoWuSuiPian: sub x8,x8,x20 -> nop"),
    (0x8C6170, 0x8AA8FD08, NOP, "RemoveMoWuSuiPian: bic 夹零 -> nop"),
]


def main():
    d = bytearray(open(SRC, "rb").read())
    new = bytearray(d)
    for off, old, want, note in WORDS:
        cur = struct.unpack_from("<I", d, off)[0]
        if cur != old:
            print("MISMATCH @0x%X: got 0x%08X want 0x%08X  (%s) -- 跳过"
                  % (off, cur, old, note))
            continue
        struct.pack_into("<I", new, off, want)
        print("ok @0x%08x %08x -> %08x  %s" % (off, old, want, note))
    with open(OUT, "wb") as f:
        f.write(new)
    print("写出", OUT)


if __name__ == "__main__":
    main()
