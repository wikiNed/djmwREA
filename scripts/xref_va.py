#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 .text，找出能算出指定 VA 的 adrp(+add/ldr/str) 组合。

用法:
    python scripts/xref_va.py 0x36fc618
    python scripts/xref_va.py 0x35e7408 0x36e4a90
"""
import sys

import capstone
from capstone import arm64_const as A

from paths import SO, require

TEXT_VA, TEXT_OFF, TEXT_SZ = 0x1436aec, 0x1432aec, 0x30bc90


def scan(targets):
    require(SO, "libil2cpp.so")
    d = open(SO, "rb").read()
    code = d[TEXT_OFF:TEXT_OFF + TEXT_SZ]
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True

    hits = {t: [] for t in targets}
    # reg -> (page_base, insn_addr) ; adrp 结果跨基本块可能失效，
    # 用"同函数内最近一次 adrp"近似（多数编译器保持在寄存器里）。
    prev = {}
    for ins in md.disasm(code, TEXT_VA):
        ops = ins.operands
        if not ops:
            continue
        if ins.mnemonic == "adrp" and len(ops) >= 2 and ops[1].type == A.ARM64_OP_IMM:
            prev[ops[0].reg] = ops[1].imm
            for t in targets:
                if ops[1].imm == (t & ~0xFFF):
                    hits[t].append((ins.address, "adrp", ins.op_str))
            continue
        if len(ops) >= 2 and ops[1].type == A.ARM64_OP_MEM:
            mem = ops[1].mem
            base = prev.get(mem.base)
            if base is None:
                continue
            eff = base + mem.disp
            for t in targets:
                if eff == t:
                    hits[t].append((ins.address, ins.mnemonic, ins.op_str))
    return hits, prev


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    targets = [int(s, 0) for s in argv]
    hits, _ = scan(targets)
    for t in targets:
        print("== refs to 0x%x: %d" % (t, len(hits[t])))
        for addr, mn, ops in hits[t][:40]:
            print("   0x%x: %s %s" % (addr, mn, ops))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
