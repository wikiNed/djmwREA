#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编旧版 v5.5.7 指定 RVA 的 ARM32 代码。"""
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
    p_type, p_offset, p_vaddr, p_paddr, p_filesz = struct.unpack_from("<5I", data, p)
    if p_type == 1:
        segs.append((p_offset, p_vaddr, p_filesz))


def r2o(rva):
    for off, vaddr, filesz in segs:
        if vaddr <= rva < vaddr + filesz:
            return off + (rva - vaddr)
    return None


md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = True
md.skipdata = True


def show(rva, nbytes=0x300, limit=120, title=""):
    fo = r2o(rva)
    print("\n" + "=" * 76)
    print("### %s  RVA=0x%x  file_off=0x%x" % (title, rva, fo))
    print("=" * 76)
    if fo is None:
        print("  映射失败")
        return
    code = data[fo:fo + nbytes]
    cnt = 0
    for ins in md.disasm(code, rva):
        # 标注立即数/地址常量
        extra = ""
        try:
            for op in ins.operands:
                if op.type == 2:  # ARM_OP_IMM
                    v = op.imm
                    if 0x1000 <= v < 0x1200000:
                        extra += "   ; =0x%x" % v
        except Exception:  # noqa: BLE001
            pass
        print("  0x%08x  %-9s %-40s%s"
              % (ins.address, ins.mnemonic, ins.op_str, extra))
        cnt += 1
        if cnt >= limit:
            print("  ...")
            break


if __name__ == "__main__":
    targets = [
        (0x7BD670, "ShuJuDate.BaoCunDate"),
    ]
    for rva, t in targets:
        show(rva, 0x400, 200, t)
