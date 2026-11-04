# -*- coding: utf-8 -*-
"""扫描代码里对某个结构偏移的 ldr/str（word）访问，并打印前后指令。

    python scanoff.py <so> 0x34 [start] [end] [before] [after]
"""
import os
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dis64 import load_map, va_to_off


def main():
    path = sys.argv[1]
    disp = int(sys.argv[2], 0)
    start = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x4af1e0
    end = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0xef5600
    before = int(sys.argv[5], 0) if len(sys.argv) > 5 else 4
    after = int(sys.argv[6], 0) if len(sys.argv) > 6 else 2
    data, segs = load_map(path)
    off = va_to_off(segs, start)
    chunk = data[off: va_to_off(segs, end)]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    insns = list(md.disasm(chunk, start))
    for i, ins in enumerate(insns):
        if ins.mnemonic not in ("ldr", "str"):
            continue
        if len(ins.operands) < 2 or ins.operands[1].type != 3:
            continue
        m = ins.operands[1].mem
        if m.disp != disp:
            continue
        lo = max(0, i - before)
        hi = min(len(insns), i + after + 1)
        print("---")
        for j in range(lo, hi):
            t = insns[j]
            mark = ">>" if j == i else "  "
            print("%s %08x  %s %s" % (mark, t.address, t.mnemonic, t.op_str))


if __name__ == "__main__":
    main()
