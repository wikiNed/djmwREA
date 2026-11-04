#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描指定 RVA 范围内的所有 bl 指令，反查每个目标的 dump.cs 签名。

用法: python work/_scan_bl.py <start_rva> <nbytes> [dump.cs 路径]
"""
import re
import struct
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\tools")
import arm_show  # noqa: E402

DUMP = r"E:\DSH\game\djmwREA\work\old\dump557\dump.cs"

_sig_cache = None


def load_sigs():
    global _sig_cache
    if _sig_cache is not None:
        return _sig_cache
    lines = open(DUMP, encoding="utf-8", errors="replace").read().splitlines()
    d = {}
    for i, l in enumerate(lines):
        m = re.search(r"// RVA: 0x([0-9A-Fa-f]+)", l)
        if m:
            rva = int(m.group(1), 16)
            sig = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if sig and rva not in d:
                d[rva] = (sig, i + 2)
    _sig_cache = d
    return d


def main():
    start = int(sys.argv[1], 0)
    n = int(sys.argv[2], 0)
    elf = arm_show.Elf(arm_show.DEFAULT_SO)
    off0 = elf.r2o(start)
    data = elf.data[off0:off0 + n]

    sigs = load_sigs()
    out = []
    for off in range(0, len(data) - 4, 4):
        w = struct.unpack_from("<I", data, off)[0]
        # ARM 模式 BL: cond=1110 (0xEB), 偏移 24 位有符号 *4
        if (w >> 24) & 0xFF == 0xEB:
            imm = w & 0x00FFFFFF
            if imm & 0x00800000:
                imm -= 0x01000000
            target = (start + off + 8) + imm * 4
            target &= 0xFFFFFFFF
            sig = sigs.get(target)
            out.append((start + off, target, sig))

    print("扫描 0x%X 起 %d 字节，共 %d 个 bl" % (start, n, len(out)))
    print()
    for site, tgt, sig in out:
        if sig:
            print("  0x%06X -> 0x%06X  %s" % (site, tgt, sig[0][:88]))
        else:
            print("  0x%06X -> 0x%06X  (—)" % (site, tgt))


if __name__ == "__main__":
    main()
