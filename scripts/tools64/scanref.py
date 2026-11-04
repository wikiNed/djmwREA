# -*- coding: utf-8 -*-
"""扫描 ARM64 代码里对某个 .rodata 地址的 adrp+ldr 引用点。

    python scanref.py <so> <target_va> [start_va] [end_va]
"""
import os
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dis64 import load_map, va_to_off


def main():
    path = sys.argv[1]
    target = int(sys.argv[2], 0)
    start = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x2ff880
    end = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x1000000
    data, segs = load_map(path)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    pending = {}
    hits = []
    off = va_to_off(segs, start)
    chunk = data[off: va_to_off(segs, end)]
    for ins in md.disasm(chunk, start):
        if ins.mnemonic == "adrp":
            reg = ins.operands[0].reg
            imm = ins.operands[1].imm
            pending[reg] = imm
            continue
        if ins.mnemonic.startswith("ldr") and ins.operands:
            mem = ins.operands[1]
            if mem.type == 3:  # ARM64_OP_MEM
                base = mem.mem.base
                disp = mem.mem.disp
                if base in pending and pending[base] + disp == target:
                    hits.append((ins.address, ins.mnemonic + " " + ins.op_str))
        # adrp 结果被后续指令复用前一般不会太长，简单起见只清空被写的目的寄存器
        if ins.operands and ins.operands[0].type == 1:
            pending.pop(ins.operands[0].reg, None)
    for a, t in hits:
        print("%08x  %s" % (a, t))
    print("// %d 处引用 0x%x" % (len(hits), target))


if __name__ == "__main__":
    main()
