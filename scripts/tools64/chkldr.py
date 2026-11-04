# -*- coding: utf-8 -*-
"""验证 ldr s0, [pc, #imm] 的编码/解码（我们用它在 0xEB6150 取 3/7 常量）。"""
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PC = 0xEB6150
TARGET = 0xEF5D68
imm19 = (TARGET - PC) // 4
word = 0x1C000000 | ((imm19 & 0x7FFFF) << 5)
print("imm19 = 0x%X   word = 0x%08X" % (imm19, word))
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
for ins in md.disasm(struct.pack("<I", word), PC):
    print("%08x  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
print("原始指令 0x1E2703E0:")
for ins in md.disasm(struct.pack("<I", 0x1E2703E0), PC):
    print("%08x  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
