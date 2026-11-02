#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 ELF32 ARM 的 libil2cpp.so 里找「谁调用了某个方法」。

为什么需要这个工具
------------------
静态逆向最耗时的一步是「从一处调用往回找入口」。
手工用 capstone 扫全文件会很慢且容易漏，这个脚本把它变成一条命令。

两种调用形态
------------
1. **托管方法之间**：`bl <目标 RVA>` —— 直接 BL 到目标函数。
2. **IL2CPP 导出 / PLT 桩**：目标在 PLT 里时，调用点是 `bl <PLT 地址>`，
   PLT 桩本身是一条 `ldr pc, [pc, #off]` 跳到 GOT。

用法
----
    python tools/find_calls_arm32.py 0x6A4C90
        搜所有 `bl` 到 0x6A4C90 的指令，输出 file offset 与 RVA

    python tools/find_calls_arm32.py --list-plt Load
        列出名字含 `Load` 的 PLT 符号及其桩地址

    python tools/find_calls_arm32.py --plt LoadScene
        先解出 LoadScene 的 PLT 桩地址，再搜所有调用点

    python tools/find_calls_arm32.py 0x3EDB48 --dump 12
        在调用点附近反汇编 12 条指令（看上下文）

默认库：`files/old/libil2cpp_v557_arm32.so`（v5.5.7，ELF32/ARM）。
用 `--so <path>` 换目标。

原理
----
ARM32 下 `file_offset == RVA`（v5.5.7 已实测），`bl` 编码为 `0xEBxxxxxx`：
高 8 位 = cond(AL=0xE) + 1011，低 24 位是相对偏移，目标 = `pc + 8 + (imm << 2)`，
`pc` 取**当前指令地址 + 8**（ARM 流水线）。
"""
import argparse
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import paths  # noqa: E402

DEFAULT_SO = paths.FILES / "old" / "libil2cpp_v557_arm32.so"


# --------------------------------------------------------------- ELF32 解析

def load_elf(path):
    """返回 (data, sections)，section = dict(nm, typ, addr, off, size, entsize)。"""
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1:
        raise SystemExit("%s 不是 ELF32" % path)
    e_shoff = struct.unpack_from("<I", data, 0x20)[0]
    e_shentsize = struct.unpack_from("<H", data, 0x2E)[0]
    e_shnum = struct.unpack_from("<H", data, 0x30)[0]
    e_shstrndx = struct.unpack_from("<H", data, 0x32)[0]

    secs = []
    for i in range(e_shnum):
        p = e_shoff + i * e_shentsize
        name, typ, _flags, addr, off, size, _link, _info, _align, entsize = \
            struct.unpack_from("<10I", data, p)
        secs.append(dict(name=name, typ=typ, addr=addr, off=off,
                         size=size, entsize=entsize))

    shstr = secs[e_shstrndx]
    for s in secs:
        raw = data[shstr["off"] + s["name"]:]
        s["nm"] = raw[:raw.index(b"\x00")].decode("utf-8", "replace")
    return data, secs


def dynsyms(data, secs):
    """返回 [(name, value, shndx)]，按 .dynsym 顺序（下标就是符号索引）。"""
    sym = next(s for s in secs if s["nm"] == ".dynsym")
    dstr = next(s for s in secs if s["nm"] == ".dynstr")
    base = dstr["off"]
    out = []
    for i in range(sym["size"] // 16):
        name, value, _size, _info, _other, shndx = \
            struct.unpack_from("<IIIBBH", data, sym["off"] + i * 16)
        raw = data[base + name:]
        out.append((raw[:raw.index(b"\x00")].decode("utf-8", "replace"),
                    value, shndx))
    return out


def plt_stubs(data, secs, syms):
    """.rel.plt 第 i 项对应 .plt 的第 (i+1) 个桩（跳过 PLT0），每桩 12 字节。"""
    relplt = next((s for s in secs if s["nm"] == ".rel.plt"), None)
    plt = next((s for s in secs if s["nm"] == ".plt"), None)
    if not relplt or not plt:
        return {}
    out = {}
    for i in range(relplt["size"] // 8):
        _off, info = struct.unpack_from("<II", data, relplt["off"] + i * 8)
        symi = info >> 8
        if symi >= len(syms):
            continue
        nm = syms[symi][0]
        addr = plt["off"] + 12 * (i + 1)
        out.setdefault(nm, []).append(addr)
    return out


def fileoff_to_rva(secs, off):
    for s in secs:
        if s["size"] and s["off"] <= off < s["off"] + s["size"]:
            return off - s["off"] + s["addr"]
    return None


# --------------------------------------------------------------- 搜索

def find_bl_to(data, secs, target):
    """在所有 PROGBITS 段里搜 `bl #target`，返回 [(file_off, rva)]。"""
    hits = []
    for s in secs:
        if s["typ"] != 1 or not s["size"]:
            continue
        base, end = s["off"], s["off"] + s["size"]
        i = base
        while i + 4 <= end:
            w = struct.unpack_from("<I", data, i)[0]
            if (w & 0xFF000000) == 0xEB000000:
                imm = w & 0xFFFFFF
                if imm & 0x800000:
                    imm -= 0x1000000
                if (i + 8) + (imm << 2) == target:
                    hits.append((i, fileoff_to_rva(secs, i)))
            i += 4
    return hits


def disasm_at(data, secs, rva, count):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    off = fileoff_to_rva(secs, rva)
    # 反查：RVA 就是 file offset（ARM32）时直接用
    if off is None:
        off = rva
    code = data[off:off + count * 4]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for ins in md.disasm(code, rva):
        print("        %08X  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="ARM32 libil2cpp.so 调用点搜索", add_help=True)
    ap.add_argument("target", nargs="?",
                    help="目标 RVA（如 0x6A4C90）")
    ap.add_argument("--so", default=str(DEFAULT_SO), help="目标 .so")
    ap.add_argument("--plt", metavar="SYM", help="按 PLT 符号名搜索")
    ap.add_argument("--list-plt", metavar="KW", nargs="?", const="",
                    help="列出匹配的 PLT 符号")
    ap.add_argument("--dump", type=int, default=0,
                    help="在每个调用点附近反汇编 N 条指令")
    a = ap.parse_args(argv)

    if not Path(a.so).exists():
        raise SystemExit(
            "找不到 %s\n请先 git lfs pull，或用 --so 指定。" % a.so)
    data, secs = load_elf(a.so)
    syms = dynsyms(data, secs)

    if a.list_plt is not None:
        stubs = plt_stubs(data, secs, syms)
        kw = a.list_plt.lower()
        n = 0
        for nm in sorted(stubs):
            if kw in nm.lower():
                print("  %-44s plt_file=0x%06X" % (nm, stubs[nm][0]))
                n += 1
        print("共 %d 个" % n)
        return 0

    if a.plt:
        stubs = plt_stubs(data, secs, syms)
        hit = [nm for nm in stubs if nm == a.plt or nm.startswith(a.plt)]
        if not hit:
            print("没有匹配 `%s` 的 PLT 符号（用 --list-plt 看看有哪些）" % a.plt)
            return 1
        for nm in sorted(hit):
            p = stubs[nm][0]
            print("PLT %s -> file 0x%06X" % (nm, p))
            for off, rva in find_bl_to(data, secs, p):
                print("   被调用 @ file 0x%06X  rva 0x%X" % (off, rva))
                if a.dump:
                    disasm_at(data, secs, rva, a.dump)
        return 0

    if not a.target:
        ap.print_help()
        return 1

    tgt = int(a.target, 0)
    hits = find_bl_to(data, secs, tgt)
    print("搜索 bl -> 0x%X：命中 %d 处" % (tgt, len(hits)))
    for off, rva in hits:
        print("   file 0x%06X  rva 0x%X" % (off, rva))
        if a.dump:
            disasm_at(data, secs, rva, a.dump)
    return 0 if hits else 2


if __name__ == "__main__":
    sys.exit(main())
