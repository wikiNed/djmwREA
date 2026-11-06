# -*- coding: utf-8 -*-
"""v14：魔窟（MoShiKu）三项改动。

用户需求（2026-11-06）：
  1. 进魔窟体力不消化（界面现在是 6/7）
  2. 魔窟商店物品购买不消化（钻石 / 魔石 / 魔物碎片）
  3. 魔窟金币（魔石 MoShiShuLiang）恒为 1000，购买不消耗（现在是 200）

定位依据（`work/dump64/dump.cs` + dis64）：
  - `MoShiKuManager.RemoveTiLi(int) @0x8C7278`：`ldr w8,[x0,#0x44]; sub w8,w8,w1; bic …`
    「体力已用」存在 `[0x44]`，`get_TiLi @0x8C5450` = `TiLiMax - [x0,#0x44]`。
  - `MoShiKuManager.MaoXian() @0x8C7AB8` 里面反而 `bl AddTiLi(1)`（= 把已用减 1，白送体力），
    这条路不扣体力。
  - `MoShiKuShangPinClass.GouMaiShangPin @0x8C8728` 内扣减点：
      `0x8C8874  bl RemoveZuanShi    @0xE557F0`（钻石）
      `0x8C88B8  bl AddMoShiShuLiang @0x8BC414`
      `0x8C8D88  bl RemoveMoWuSuiPian @0x8C60C8`（魔物碎片）
    货币枚举 `XiaoHaoLeiXing{zuanShi=0, moShi=1, feiQi=2, ouQi=3, moWuSuiPian=4}`。
  - 魔石（金币）读口：`get_MoShiShuLiang @0x8C5618` = `mov w0,#1000; ret`（原本就是常量 1000！），
    另有一个 `@0x8C5620` 是 `get_MoShiShuLiangMax` = `[x0,#0xf8] * 100`。
  - 扣减：`RemoveMoShiShuLiang(long) @0x8C4588`、`RemoveMoWuSuiPian(long) @0x8C60C8`、
    `PlayerDataModel.RemoveZuanShi(int) @0xE557F0`。
"""
import struct
import sys

SRC = r"work/patched/libil2cpp_64_v13.so"
OUT = r"work/patched/libil2cpp_64_v14.so"

RET = 0xD65F03C0
NOP = 0xD503201F

WORDS = [
    # ---- 1) 魔窟体力不消耗 ----
    # RemoveTiLi(n)：入口直接返回，[x0+0x44] 的“已用体力”永远不变
    (0x8C7278, 0xA9BE4FF4, RET, "MoShiKuManager.RemoveTiLi -> ret（进洞/买体力都不再扣）"),
    # MaoXian 里那句 bl AddTiLi(1)（目标是 0x8C71E8），NOP 掉
    (0x8C7AF8, 0x97FFFDBC, NOP, "MaoXian: bl AddTiLi @0x8C71E8 -> nop"),

    # ---- 2) 魔窟商店购买不消耗资源 ----
    (0x8C8874, 0x941633DF, NOP, "GouMaiShangPin: bl RemoveZuanShi @0xE557F0 -> nop（钻石不扣）"),
    (0x8C8D88, 0x97FFF4D0, NOP, "GouMaiShangPin: bl RemoveMoWuSuiPian @0x8C60C8 -> nop（魔物碎片不扣）"),
    (0x8BC414, 0xA9BE4FF4, RET, "AddMoShiShuLiang -> ret（魔石不再增加）"),
    (0x8C4588, 0xF81D0FF5, RET, "RemoveMoShiShuLiang -> ret（魔石不再减少）"),

    # ---- 3) 魔石（魔窟金币）恒 1000 ----
    # get_MoShiShuLiang @0x8C5618 原本就是 `ldr x0,[x0,#0x60]; ret`（读字段），
    # 把它改成常量 1000；上限同样钉成 1000，避免 UI 反推出奇怪的比值。
    (0x8C5618, 0xF9402C00, 0x52807D00, "get_MoShiShuLiang: ldr x0 -> mov w0,#1000"),
    (0x8C5620, 0xB980F808, 0x52807D00, "get_MoShiShuLiangMax: ldrsw -> mov w0,#1000"),
    (0x8C5624, 0x52800C89, RET, "get_MoShiShuLiangMax: mov w9,#100 -> ret"),
]


def main():
    d = bytearray(open(SRC, "rb").read())
    ok = True
    for off, old, new, desc in WORDS:
        cur = struct.unpack_from("<I", d, off)[0]
        if cur != old:
            print("MISMATCH @%#x 期望 %08x 实际 %08x  (%s)" % (off, old, cur, desc))
            ok = False
            continue
        struct.pack_into("<I", d, off, new)
        print("ok @%#x %08x -> %08x  %s" % (off, old, new, desc))
    if not ok:
        print("\n有 MISMATCH，未写出。请按实际字节修正后重跑。")
        sys.exit(1)
    open(OUT, "wb").write(d)
    print("写出", OUT, len(d))


if __name__ == "__main__":
    main()
