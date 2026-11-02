#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反汇编 v5.5.7（ARM32）libil2cpp.so 里一段 RVA 区间。

用法：
    python scripts/arm_v557.py <rva_hex> [指令条数] [--raw]

    与相邻工具的分工
    ----------------
    - `scripts/arm_v557.py`（本文件）：ARM32，用于**旧版 v5.5.7**。
      32 位下 `file_offset == RVA`，但仍走 program header 映射，不硬编码等价。
    - `tools/arm_show.py`：同样的 ARM32 反汇编，接口更简单（`show(rva, nbytes, title)`）。
    - `tools/arm_disasm.py`：ARM32 反汇编的底层实现。
    - v5.9.2 是 **ARM64**，用 `tools/disasm_range.py` 或 `scripts/armdis.py`。

    踩坑备忘
    --------
    - `--raw` 会把指令字节一起打出来，用来肉眼确认 capstone 没跑偏。
    - 打印大段反汇编会淹没上下文，务必给条数。
"""
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

#: 旧版 v5.5.7 的宿主库（ELF32 / ARM）
SO = paths.FILES / "old" / "libil2cpp_v557_arm32.so"


def load(path=None):
    """解析 ELF32 program headers，返回 (文件字节, [(p_offset, p_vaddr, p_filesz)])。"""
    p = Path(path or SO)
    if not p.exists():
        raise SystemExit(
            "找不到 %s\n请先 git lfs pull，或用 --so 指定路径。" % p)
    data = p.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1:
        raise SystemExit("%s 不是 ELF32" % p)
    e_phoff = struct.unpack_from("<I", data, 0x1C)[0]
    e_phnum = struct.unpack_from("<H", data, 0x2C)[0]
    segs = []
    for i in range(e_phnum):
        base = e_phoff + i * 32
        p_type, p_offset, p_vaddr, _pa, p_filesz = \
            struct.unpack_from("<5I", data, base)
        if p_type == 1:                      # PT_LOAD
            segs.append((p_offset, p_vaddr, p_filesz))
    return data, segs


def r2o(segs, rva):
    """RVA -> 文件偏移。ARM32 下多数情况两者相等，但仍按段表算。"""
    for off, vaddr, filesz in segs:
        if vaddr <= rva < vaddr + filesz:
            return off + (rva - vaddr)
    raise ValueError("RVA 0x%x 不在任何 PT_LOAD 段内" % rva)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    so = SO
    if "--so" in argv:
        i = argv.index("--so")
        so = argv[i + 1]
        del argv[i:i + 2]

    raw_mode = "--raw" in argv
    argv = [a for a in argv if a != "--raw"]

    rva = int(argv[0], 16 if argv[0].lower().startswith("0x") else 10)
    n = int(argv[1]) if len(argv) > 1 else 60

    data, segs = load(so)
    off = r2o(segs, rva)
    code = data[off:off + n * 4]

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    print("RVA 0x%X -> 文件 0x%X，%d 条指令" % (rva, off, n))
    for ins in md.disasm(code, rva):
        if raw_mode:
            blk = code[ins.address - rva:ins.address - rva + ins.size]
            print("  %08X  %-20s %-10s %s" % (
                ins.address, blk.hex(), ins.mnemonic, ins.op_str))
        else:
            print("  %08X  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
