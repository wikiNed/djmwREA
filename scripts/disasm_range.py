"""反汇编指定 RVA 区间的 ARM64 代码（capstone），自动解析 bl 目标并标注 dump.cs 方法名。"""

from paths import DUMP, SO

import re
import sys

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
# RVA -> 文件偏移：arm64 的 .text 段 RVA==file offset（dump.cs 里 Offset 字段已验证）
# 但从 dump 看 Offset 与 RVA 差 0x4000（.text 前有 0x4000 header）。
FILE_DELTA = -0x4000  # dump.cs 里 RVA 0x18A7034 对应 Offset 0x18A3034，差 0x4000


def build_rva_map():
    """解析 dump.cs: RVA -> 方法签名"""
    m = {}
    with open(DUMP, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, ln in enumerate(lines):
        got = re.search(r"// RVA: 0x([0-9A-Fa-f]+)", ln)
        if got:
            rva = int(got.group(1), 16)
            sig = lines[i + 1].strip() if i + 1 < len(lines) else ""
            m[rva] = sig[:120]
    return m


def main():
    start = int(sys.argv[1], 16) if not sys.argv[1].startswith("0x") else int(sys.argv[1], 16)
    size = int(sys.argv[2], 16) if not sys.argv[2].startswith("0x") else int(sys.argv[2], 16)
    rvamap = build_rva_map()
    inv = {}
    for r, s in rvamap.items():
        inv.setdefault(r, s)

    with open(SO, "rb") as f:
        f.seek(start + FILE_DELTA)
        code = f.read(size)

    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = False
    for ins in md.disasm(code, start):
        note = ""
        if ins.mnemonic in ("bl", "b") and ins.op_str.startswith("#"):
            tgt = int(ins.op_str[1:], 16)
            if tgt in rvamap:
                note = "   ; -> " + rvamap[tgt]
        print(f"0x{ins.address:X}:  {ins.mnemonic:8s} {ins.op_str}{note}")


if __name__ == "__main__":
    main()
