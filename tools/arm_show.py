#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编指定 RVA 区间的 ARM32 代码（v5.5.7 libil2cpp.so）。

用法::

    python tools/arm_show.py <RVA> [字节数] [标题]
    python tools/arm_show.py 0x424CC0 160 zhiFuHuangJinShu

32 位 ARM 的 ELF32 里 ``file_offset == RVA``（本库的 LOAD 段 vaddr 从 0 开始），
但这里仍按 program header 做一次映射，换成 ARM64 时同样能用。
"""
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM  # noqa: E402

try:                      # capstone 4.x 叫 CS_MODE_ARM，5.x 才拆出 ARM64 模式常量
    from capstone import CS_ARCH_ARM64, CS_MODE_ARM as _M64
    _HAS_ARM64 = True
except Exception:  # noqa: BLE001
    CS_ARCH_ARM64 = None
    _HAS_ARM64 = False

try:
    from scripts import paths  # noqa: E402
    DEFAULT_SO = str(paths.FILES / "old" / "libil2cpp_v557_arm32.so")
except Exception:  # noqa: BLE001
    DEFAULT_SO = os.environ.get("ARM_SO", "")


class Elf:
    """极简 ELF 段映射（只解析 PT_LOAD 与 e_machine）。"""

    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        if d[:4] != b"\x7fELF":
            raise SystemExit("不是 ELF 文件: %s" % path)
        self.is64 = d[4] == 2
        if self.is64:
            self.machine = struct.unpack_from("<H", d, 0x12)[0]
            e_phoff = struct.unpack_from("<Q", d, 0x20)[0]
            e_phnum = struct.unpack_from("<H", d, 0x38)[0]
            self.segs = []
            for i in range(e_phnum):
                p = e_phoff + i * 56
                t, _f, off, vaddr, _pa, fs = struct.unpack_from("<IIQQQQ", d, p)
                if t == 1:
                    self.segs.append((off, vaddr, fs))
        else:
            self.machine = struct.unpack_from("<H", d, 0x12)[0]
            e_phoff = struct.unpack_from("<I", d, 0x1C)[0]
            e_phnum = struct.unpack_from("<H", d, 0x2C)[0]
            self.segs = []
            for i in range(e_phnum):
                p = e_phoff + i * 32
                t, off, vaddr, _pa, fs = struct.unpack_from("<5I", d, p)
                if t == 1:
                    self.segs.append((off, vaddr, fs))

    def r2o(self, rva):
        for off, vaddr, filesz in self.segs:
            if vaddr <= rva < vaddr + filesz:
                return off + (rva - vaddr)
        return None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    rva = int(argv[1], 0)
    nbytes = int(argv[2], 0) if len(argv) > 2 else 128
    title = argv[3] if len(argv) > 3 else ""

    elf = Elf(DEFAULT_SO)
    fo = elf.r2o(rva)
    if fo is None:
        print("!! 0x%x 不在任何 LOAD 段（段表：%s）"
              % (rva, ["%#x+%#x" % (v, f) for _, v, f in elf.segs]))
        return 1

    if elf.machine == 183:      # AArch64
        if not _HAS_ARM64:
            print("!! 这是 AArch64 二进制，但当前 capstone 不支持 ARM64 常量")
            return 1
        md = Cs(CS_ARCH_ARM64, _M64)
    else:                       # ARM
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.skipdata = True

    print("=" * 76)
    print("### %s  RVA=%#x  file_off=%#x  len=%d" % (title, rva, fo, nbytes))
    print("=" * 76)
    code = elf.data[fo:fo + nbytes]
    for ins in md.disasm(code, rva):
        print("  0x%08x  %-12s %s" % (ins.address, ins.mnemonic, ins.op_str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
