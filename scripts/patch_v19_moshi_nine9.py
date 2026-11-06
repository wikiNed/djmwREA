# -*- coding: utf-8 -*-
"""v19：魔石数量 1000 -> 99999999（用户 m17617「现在魔石是1000，其他都没问题，把这个改为99999999就行了」）。

### 为什么不能就地改
    v16/v17 为了「魔窟商店买得起」，把 LoadMoShiKuManager 的加载点写死成 1000：

        0x8C7DB8  52807D09  mov w9,#1000
        0x8C7DBC  F9002E69  str x9,[x19,#0x58]   ; 魔石缓存

    99999999 = 0x05F5E0FF 需要 movz + movk **两条**指令才能装进 32 位寄存器，
    而 0x8C7DB8 这一格后面紧接 str（0x8C7DBC），再后面 0x8C7DC0~0x8C7DD0 是
    「取存档对象」的四条指令、0x8C7DD4 起是魔物碎片段 —— 没有可以挪动的空位。

### 采用方案：.rodata 常量池 + LDR 字面量
    0x8C7DB8  58xxxxxx  ldr x9,[pc,#imm]     ; 新常量
    0x8C7DBC  F9002E69  str x9,[x19,#0x58]   ; 原样保留

    常量写在 `0x847BE0` 起的一大片填充区（该处 0x847BC8~0x847BDF 是 jump table 之后
    到下一个函数 0x848BCC 之间，实测 **4076 字节全零**，是 .text 段内的对齐填充，
    没有任何分支引用），距离 0x8C7DB8 约 0x5C1E0 = 377,312 字节，在 `ldr literal`
    的 ±1MB 范围内。

### LDR (literal) 编码
    `LDR Xt,[PC,#imm]` = 0x58000000 | (imm19<<5) | Rt，目标 = PC + imm19*4
即 imm19 = (target - 指令地址) / 4。
"""
import struct

SRC = r"work/patched/libil2cpp_64_v18.so"
OUT = r"work/patched/libil2cpp_64_v19.so"

SLOT = 0x847BE0          # .text 填充区起点（4076 字节全零）
LDR_SITE = 0x8C7DB8
STR_SITE = 0x8C7DBC
VALUE = 99999999         # 0x05F5E0FF

OLD_MOV = 0x52807D09
OLD_STR = 0xF9002E69


def ldr_literal_x(target, pc, rt):
    imm19 = (target - pc) // 4
    assert -0x40000 <= imm19 < 0x40000, "超出 ldr literal 范围"
    return 0x58000000 | ((imm19 & 0x7FFFF) << 5) | rt


def main():
    d = bytearray(open(SRC, "rb").read())

    assert struct.unpack_from("<I", d, LDR_SITE)[0] == OLD_MOV, \
        "0x%X 原值不符" % LDR_SITE
    assert struct.unpack_from("<I", d, STR_SITE)[0] == OLD_STR, \
        "0x%X 原值不符" % STR_SITE
    assert d[SLOT:SLOT + 8] == b"\x00" * 8, "填充区不是全零，换位置"

    # 1) 写常量到填充区
    struct.pack_into("<q", d, SLOT, VALUE)
    print("常量 99999999 写入 0x%X" % SLOT)

    # 2) 把 mov w9,#1000 改成 ldr x9,[pc,#imm]
    word = ldr_literal_x(SLOT, LDR_SITE, 9)
    struct.pack_into("<I", d, LDR_SITE, word)
    print("0x%X  mov w9,#1000 -> ldr x9,[pc,#0x%X]  (%08X)"
          % (LDR_SITE, SLOT - LDR_SITE, word))

    open(OUT, "wb").write(d)
    print("写出", OUT)


if __name__ == "__main__":
    main()
