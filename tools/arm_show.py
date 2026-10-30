#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编指定 RVA 区间的 ARM32 代码。"""
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM  # noqa: E402

SO = r"E:\DSH\game\djmwREA\files\old\libil2cpp_v557_arm32.so"
data = open(SO, "rb").read()

e_phoff = struct.unpack_from("<I", data, 0x1C)[0]
e_phnum = struct.unpack_from("<H", data, 0x2C)[0]
segs = []
for i in range(e_phnum):
    p = e_phoff + i * 32
    t, o, v, _pa, fs = struct.unpack_from("<5I", data, p)
    if t == 1:
        segs.append((o, v, fs))


def r2o(rva):
    for off, vaddr, filesz in segs:
        if vaddr <= rva < vaddr + filesz:
            return off + (rva - vaddr)
    return None


def show(rva, nbytes, title=""):
    fo = r2o(rva)
    if fo is None:
        print("!! 0x%x 不在任何 LOAD 段" % rva)
        return
    print("\n" + "=" * 76)
    print("### %s  RVA=0x%x  file_off=0x%x" % (title, rva, fo))
    print("=" * 76)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.skipdata = True
    code = data[fo:fo + nbytes]
    n = 0
    for ins in md.disasm(code, rva):
        line = "  0x%08x  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str)
        print(line)
        n += 1
        if n > 400:
            print("  ... 截断")
            break


if __name__ == "__main__":
    targets = [
        (0x7C0D98, 0x180, "ShuJuDate.Encrypt"),
        (0x7C0CC8, 0x120, "ShuJuDate.ZhuanHuanString"),
        (0x5A5214, 0x100, "unknown_0x5A5214"),
        (0x7BE230, 0x100, "unknown_0x7BE230"),
    ]
    for rva, n, t in targets:
        show(rva, n, t)
