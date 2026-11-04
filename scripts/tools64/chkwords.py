# -*- coding: utf-8 -*-
"""核对新补丁字的反汇编，防止像 mul 的 Rm 位那样手算出错。"""
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
words = [
    (0xEB6E00, 0xD2800648),   # mov x8, #50
    (0xEB6E08, 0x9B087C08),   # mul x8, x0, x8
    (0xEB6150, 0x1C1FE0C0),   # ldr s0, #0xef5d68
    (0xEB9484, 0x9B087C01),   # mul x1, x0, x8 （已用）
]
for va, w in words:
    for ins in md.disasm(struct.pack("<I", w), va):
        print("%08x  %08X  %-8s %s" % (va, w, ins.mnemonic, ins.op_str))
