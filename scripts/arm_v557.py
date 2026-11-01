#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编 v557 ARM32 .so 里一段 RVA 区间。

用法：
    python arm_v557.py <rva_hex> [指令条数]
    python arm_v557.py 0x7c1e38 60
"""
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM  # noqa: E402

SO = r"E:\DSH\game\djmwREA\files\old\libil2cpp_v557_arm32.so"


def load():
    data = open(SO, "rb").read()
    e_phoff = struct.unpack_from("<I", data, 0x1C)[0]
    e_phnum = struct.unpack_from("<H", data, 0x2C)[0]
    segs = []
    for i in range(e_phnum):
        p = e_phoff + i * 32
        t, o, v, _pa, fs = struct.unpack_from("<5I", data, p)
        if t == 1:
            segs.append((o, v, fs))
    return data, segs


def r2o(segs, rva):
    for off, vaddr, filesz in segs:
        if vaddr <= rva < vaddr + filesz:
            return off + (rva - vaddr)
    raise ValueError("RVA 0x%x 不在任何 PT_LOAD 内" % rva)


def main(argv):
    rva = int(argv[0], 16 if argv[0].startswith("0x") else 10)
    n = int(argv[1]) if len(argv) > 1 else 60
    data, segs = load()
    off = r2o(segs, rva)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    code = data[off:off + n * 4]
    print("RVA=0x%08x  file_off=0x%08x" % (rva, off))
    print("=" * 70)
    for ins in md.disasm(code, rva):
        print("  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
