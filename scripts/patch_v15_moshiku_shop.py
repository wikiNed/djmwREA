# -*- coding: utf-8 -*-
"""v15：魔窟商店购买不消耗 + 魔物碎片恒 1000。

用户需求（2026-11-06，m17421/m17460）：
  1. 魔窟商店物品购买不消耗任何资源（钻石 / 魔石 / 魔物碎片）
  2. 魔物碎片恒为 1000，购买不消耗（当前显示 0）

根因：`MoShiKuShangPinClass.GouMaiShangPin @0x8C8728` 按字段 [x19,#0x38]
（枚举 XiaoHaoLeiXing：zuanShi=0 / moShi=1 / feiQi=2 / ouQi=3 / moWuSuiPian=4）
分成多个购买分支，每个分支都是
    bl IsBuy @0x8C8600  ->  bl RemoveXxx  ->  shangPinKuCun++  ->  bl SetShangPinXinXi @0x8C844C

v14 只 NOP 掉了每个函数的第一处调用，剩下这些：
    RemoveZuanShi      @0xE557F0：0x8C8A00 / 0x8C8B24 / 0x8C8C20
    RemoveMoWuSuiPian  @0x8C60C8：0x8C8E94 / 0x8C8FA0 / 0x8C90AC

资源 getter（原始代码，base_arm64.so 实测）：
    0x8C5610  ldr x0,[x0,#0x50]; ret              get_???
    0x8C5618  ldr x0,[x0,#0x58]; ret              get_MoShiShuLiang        （v14 已改 1000）
    0x8C5620  ldrsw x8,[x0,#0xf8]; mov w9,#100; mul x0,x8,x9; ret
                                                  get_MoShiShuLiangMax     （v14 已改 1000）
    0x8C5630  ldr x0,[x0,#0x60]; ret              get_MoWuSuiPianShuLiang  << 本次改成 1000
    0x8C5638  mov w0,#0x3e8; ret                  get_MoWuSuiPianMax       （原始就是 1000）
"""
import struct

SRC = r"work/patched/libil2cpp_64_v14.so"
OUT = r"work/patched/libil2cpp_64_v15.so"

RET = 0xD65F03C0
NOP = 0xD503201F
MOV_W0_1000 = 0x52807D00          # mov w0, #1000  (0x3E8)

WORDS = [
    # ---- 1) 魔窟商店：补齐所有购买分支的扣费点 ----
    (0x8C8A00, 0x9416337C, NOP, "GouMaiShangPin 分支: bl RemoveZuanShi @0xE557F0 -> nop"),
    (0x8C8B24, 0x94163333, NOP, "GouMaiShangPin 分支: bl RemoveZuanShi @0xE557F0 -> nop"),
    (0x8C8C20, 0x941632F4, NOP, "GouMaiShangPin 分支: bl RemoveZuanShi @0xE557F0 -> nop"),
    (0x8C8E94, 0x97FFF48D, NOP, "GouMaiShangPin 分支: bl RemoveMoWuSuiPian @0x8C60C8 -> nop"),
    (0x8C8FA0, 0x97FFF44A, NOP, "GouMaiShangPin 分支: bl RemoveMoWuSuiPian @0x8C60C8 -> nop"),
    (0x8C90AC, 0x97FFF407, NOP, "GouMaiShangPin 分支: bl RemoveMoWuSuiPian @0x8C60C8 -> nop"),

    # 兜底：即使别的路径直接调这两个函数，也不会真的扣
    (0x8C60C8, 0xF81D0FF5, RET, "MoShiKuManager.RemoveMoWuSuiPian -> ret"),
    # 注：PlayerDataModel.RemoveZuanShi @0xE557F0 在 v8 就已改成 ret（只增不减），这里无需再动

    # ---- 2) 魔物碎片恒 1000 ----
    (0x8C5630, 0xF9403000, MOV_W0_1000,
     "get_MoWuSuiPianShuLiang: ldr x0,[x0,#0x60] -> mov w0,#1000"),
]


def main():
    d = bytearray(open(SRC, "rb").read())
    new = bytearray(d)
    for off, old, want, note in WORDS:
        cur = struct.unpack_from("<I", d, off)[0]
        if cur != old:
            raise SystemExit("MISMATCH @0x%X: got 0x%08X want 0x%08X (%s)"
                             % (off, cur, old, note))
        struct.pack_into("<I", new, off, want)
        print("ok @0x%08x %08x -> %08x  %s" % (off, old, want, note))
    with open(OUT, "wb") as f:
        f.write(new)
    print("写出", OUT)


if __name__ == "__main__":
    main()
