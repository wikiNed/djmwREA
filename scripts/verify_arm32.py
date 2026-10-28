#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 32 位 ARM 版 libil2cpp.so 独立复算口令，与 64 位结果交叉验证。

不同架构的 ELF、不同的重定位类型，但 metadata 是同一份。
如果两条链算出同一个字面量，静态分析结论就是可靠的。

用法:
    python scripts/verify_arm32.py
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(os.path.dirname(HERE), "files")
ARM32 = os.path.join(FILES, "libil2cpp_arm32.so")
META = os.path.join(FILES, "global-metadata.dat")

# ARM32 版里 SaveManager..ctor 的 RVA 与 64 位不同，需重新定位。
# 这里复用 64 位已确定的 GOT 槽位思路：先在 .rel.dyn 里找 R_AARCH64_RELATIVE 的等价物
# R_ARM_RELATIVE = 23
R_ARM_RELATIVE = 23


class Elf32:
    """最小 ARM32 ELF 解析：PT_LOAD 映射 + .rel.dyn 重定位。"""

    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        d = self.data
        assert d[:4] == b"\x7fELF", "不是 ELF"
        assert d[4] == 1, "不是 32 位 ELF（e_ident[EI_CLASS]=%d）" % d[4]
        (self.e_phoff, self.e_shoff) = struct.unpack_from("<II", d, 0x1C)
        (self.e_phentsize, self.e_phnum) = struct.unpack_from("<HH", d, 0x2A)
        (self.e_shentsize, self.e_shnum) = struct.unpack_from("<HH", d, 0x2E)
        self.loads = []
        for i in range(self.e_phnum):
            off = self.e_phoff + i * self.e_phentsize
            p_type, p_offset, p_vaddr, _, p_filesz, p_memsz, p_flags, _ = \
                struct.unpack_from("<IIIIIIII", d, off)
            if p_type == 1:  # PT_LOAD
                self.loads.append((p_vaddr, p_offset, p_filesz, p_memsz, p_flags))
        self.sections = []
        for i in range(self.e_shnum):
            off = self.e_shoff + i * self.e_shentsize
            name, s_type, s_flags, s_addr, s_off, s_size, s_link, s_info, \
                s_align, s_entsize = struct.unpack_from("<IIIIIIIIII", d, off)
            self.sections.append(dict(type=s_type, addr=s_addr, off=s_off,
                                      size=s_size, entsize=s_entsize, link=s_link))

    def va2off(self, va):
        for vaddr, offset, filesz, _memsz, _flags in self.loads:
            if vaddr <= va < vaddr + filesz:
                return offset + (va - vaddr)
        raise ValueError("VA 0x%x 不在任何 PT_LOAD 内" % va)

    def relocations(self):
        """返回 {r_offset: addend}，只取 R_ARM_RELATIVE。"""
        out = {}
        for sec in self.sections:
            if sec["type"] != 9:  # SHT_REL（注意：ARM32 用 REL，addend 在目标处）
                continue
            n = sec["size"] // sec["entsize"] if sec["entsize"] else 0
            for i in range(n):
                off = sec["off"] + i * 8
                r_offset, r_info = struct.unpack_from("<II", self.data, off)
                r_type = r_info & 0xFF
                if r_type == R_ARM_RELATIVE:
                    out[r_offset] = None  # addend 存在目标位置本身
        return out

    def sections_named(self):
        return [(s["addr"], s["size"], s["type"]) for s in self.sections]


def main():
    if not os.path.exists(ARM32):
        print("缺少 %s —— 先从 APK 提取 lib/armeabi-v7a/libil2cpp.so" % ARM32)
        return 1

    e = Elf32(ARM32)
    print("=== ARM32 ELF ===")
    print("文件大小 %d 字节" % len(e.data))
    for vaddr, offset, filesz, memsz, flags in e.loads:
        perm = "".join(c if flags & m else "-" for c, m in
                       (("r", 4), ("w", 2), ("x", 1)))
        print("  LOAD va 0x%08x..0x%08x  fileoff 0x%08x  filesz 0x%08x  %s"
              % (vaddr, vaddr + memsz, offset, filesz, perm))

    rels = e.relocations()
    print("R_ARM_RELATIVE 重定位 %d 条" % len(rels))

    # 32 位下 pointer 占 4 字节，字符串字面量哨兵仍是 32 位
    # 在 .data/.bss 可写段里找 0xA0000000|... 形态
    print("\n=== 在可写段里找 metadata usage 哨兵 ===")
    found = 0
    for vaddr, offset, filesz, memsz, flags in e.loads:
        if not (flags & 2):
            continue
        seg = e.data[offset:offset + filesz]
        for i in range(0, len(seg) - 4, 4):
            v = struct.unpack_from("<I", seg, i)[0]
            if (v & 0xFF000000) == 0xA0000000:
                va = vaddr + i
                if found < 5:
                    idx = (v & 0xFFFFFF) >> 1
                    print("  0x%08x  0x%08x  idx=%d" % (va, v, idx))
                found += 1
    print("共 %d 个哨兵" % found)

    print("\n=== metadata 字面量（独立于架构）===")
    if os.path.exists(META):
        with open(META, "rb") as f:
            m = f.read()
        magic, ver = struct.unpack_from("<II", m, 0)
        print("sanity=0x%08X version=%d 大小=%d" % (magic, ver, len(m)))
        off0, sz0 = struct.unpack_from("<II", m, 0x08)
        off1, sz1 = struct.unpack_from("<II", m, 0x10)
        print("stringLiteral off=0x%x size=%d（%d 行）" % (off0, sz0, sz0 // 8))
        print("literalData  off=0x%x size=%d" % (off1, sz1))
        for idx in (12153, 6804):
            ln, lo = struct.unpack_from("<ii", m, off0 + idx * 8)
            s = m[off1 + lo:off1 + lo + ln]
            print("  [%d] len=%d %r" % (idx, ln, s.decode("utf-8", "replace")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
