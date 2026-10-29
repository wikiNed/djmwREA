# -*- coding: utf-8 -*-
"""扫描 .text，找所有 `bl <target>` 调用指定地址的位置。

用来回答「谁在用 JiNengStr 调 Enum.Parse」这类问题：
扫 Enum.Parse 的两个重载（0x292AE48 两参 / 0x292AEB0 三参），
再看调用者里有没有读 [x,#0x10]（JiNengStr 字段）的。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import capstone
from capstone import arm64_const as A
from rela_resolve import Elf

SO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "libil2cpp.so")
TEXT_VA = 0x1436AEC
TEXT_SIZE = 0x30BC90

TARGETS = {}
if len(sys.argv) > 1:
    for a in sys.argv[1:]:
        TARGETS[int(a, 16)] = a


def main():
    e = Elf(SO)
    with open(SO, "rb") as f:
        off = e.va2off(TEXT_VA)
        f.seek(off)
        data = f.read(TEXT_SIZE)

    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True

    hits = {}
    n = 0
    for ins in md.disasm(data, TEXT_VA):
        n += 1
        if ins.id != A.ARM64_INS_BL:
            continue
        ops = ins.operands
        if not ops or ops[0].type != A.ARM64_OP_IMM:
            continue
        tgt = ops[0].imm
        if tgt in TARGETS:
            hits.setdefault(tgt, []).append(ins.address)

    print("扫描 %d 条指令" % n)
    for tgt, name in sorted(TARGETS.items()):
        addrs = hits.get(tgt, [])
        print("\n%s <- %d 处调用" % (name, len(addrs)))
        for a in addrs[:40]:
            print("  0x%X" % a)
        if len(addrs) > 40:
            print("  … 共 %d 处" % len(addrs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
