#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.7 libil2cpp.so（ARM32 ELF）段表 / 导出符号 / PLT 桩解析。

为什么要单独写
--------------
`paths.py` 里的 `parse_phdrs` 只支持 ELF64（`ident[4] != 2` 直接抛），
而 v5.5.7 加载的是 **armeabi-v7a 32 位**库。它还有两个 ELF64 那套完全不适用的事实：

1. 用 **SHT_REL**（type=9），addend 就存在目标地址处；不是 SHT_RELA。
2. 有一个 12.9MB 的独立 `il2cpp` 段落着真正的方法体，`.text` 只是外壳。

★ 最大的坑：`.dynsym` 里的 `il2cpp_*` 符号**全是 PLT 桩**
---------------------------------------------------------
2613 条符号里有 236 个 `il2cpp_*`，但它们的 `st_size` 全是 4、`st_shndx` 全是 12
（SHN_UNDEF 的变体 / PLT 段），根本不是函数实现。直接拿 `st_value` 去 hook 或反汇编
只会得到一句 `b <真实实现>` 跳板。

跳板本身是 ARM 的 `b #imm24`（word 高字节 `0xEA`），目标算法：

    target = va + 8 + imm24 * 4        # +8 是 ARM 流水线偏移

解完就得到真实函数体。其中一个特别有价值：

    il2cpp_class_get_static_field_data 的实现就是 `ldr r0, [r0, #0x5c]; bx lr`
    → 由此确认 **Il2CppClass + 0x5c = static_fields 指针**

（这是 docs/27 里三步定位法的第一块基石。）

用法
----
    python elf_v557.py sections                 # 段表
    python elf_v557.py syms                     # 全部 il2cpp_* 符号
    python elf_v557.py syms il2cpp_class        # 只看名字含该子串的
    python elf_v557.py resolve                  # 全部 il2cpp_* PLT 桩 → 真实地址
    python elf_v557.py resolve il2cpp_class_from_name
    python elf_v557.py b 0x001fe698             # 解码单条 ARM b/bx 跳板
    python elf_v557.py check                    # 批量解码校验（找出非跳板的）

    from elf_v557 import Elf32, decode_arm_b
    e = Elf32()
    e.sections["il2cpp"]        # -> dict(name, addr, off, size, ...)
    e.resolve("il2cpp_class_from_name")   # -> int 真实地址
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SHN_UNDEF = 0
SHT_SYMTAB = 2
SHT_DYNSYM = 11
SHT_REL = 9
SHT_RELA = 4

#: v5.5.7 的 libil2cpp.so 里所有导入桩符号共用的 st_shndx。
#: 该段位于 0x119a68，紧挨 .rel.plt（0x119a68 + 8768）。实测 1708 个符号落在这一段。
STUB_SHNDX = 12


def default_so_path() -> Path:
    try:
        from paths import FILES
    except Exception:
        FILES = Path(__file__).resolve().parent.parent / "files"
    return FILES / "old" / "libil2cpp_v557_arm32.so"


def decode_arm_b(va: int, word: int):
    """ARM `b` / `bl` 的绝对目标地址。不是分支指令返回 None。"""
    if (word & 0x0F000000) not in (0x0A000000, 0x0B000000):
        return None
    imm24 = word & 0x00FFFFFF
    if imm24 & 0x00800000:
        imm24 -= 0x01000000
    return (va + 8 + imm24 * 4) & 0xFFFFFFFF


class Elf32:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_so_path()
        if not self.path.exists():
            raise FileNotFoundError(
                f"找不到 {self.path}\n"
                f"v5.5.7 的 ARM32 库在 files/old/libil2cpp_v557_arm32.so，需要 git lfs pull。")
        self.data = self.path.read_bytes()
        if self.data[:4] != b"\x7fELF" or self.data[4] != 1:
            raise ValueError(f"{self.path} 不是 ELF32")
        # 注意：e_shoff 之后是 <IIHHHH，一共 6 个值，别少写一个 H
        (_type, _mach, _ver, _entry, self.e_phoff, self.e_shoff, _flags,
         _ehsize, self.e_phentsize, self.e_phnum, self.e_shentsize,
         self.e_shnum, self.e_shstrndx) = struct.unpack_from(
            "<HHIIIIIHHHHHH", self.data, 0x10)
        self.sections = self._read_sections()
        self.phdrs = self._read_phdrs()

    # ---- 段表 / 程序头 ----
    def _read_sections(self):
        raw = []
        for i in range(self.e_shnum):
            off = self.e_shoff + i * self.e_shentsize
            vals = struct.unpack_from("<IIIIIIIIII", self.data, off)
            raw.append(dict(zip(
                ("name_off", "type", "flags", "addr", "off", "size",
                 "link", "info", "align", "entsize"), vals)))
        str_off = raw[self.e_shstrndx]["off"]

        def name(i):
            p = str_off + raw[i]["name_off"]
            return self.data[p:self.data.index(b"\x00", p)].decode("utf-8", "replace")

        out = {}
        for i, s in enumerate(raw):
            s["name"] = name(i)
            out[s["name"]] = s
        return out

    def _read_phdrs(self):
        segs = []
        for i in range(self.e_phnum):
            off = self.e_phoff + i * self.e_phentsize
            p_type, p_offset, p_vaddr, _pa, p_filesz, p_memsz, p_flags, _al = \
                struct.unpack_from("<IIIIIIII", self.data, off)
            if p_type == 1:  # PT_LOAD
                segs.append((p_offset, p_vaddr, p_filesz, p_memsz, p_flags))
        return segs

    def va2off(self, va: int) -> int | None:
        for p_offset, p_vaddr, p_filesz, _m, _f in self.phdrs:
            if p_vaddr <= va < p_vaddr + p_filesz:
                return p_offset + (va - p_vaddr)
        return None

    # ---- 符号 ----
    def symbols(self):
        """返回 [(name, st_value, st_size, st_shndx, is_stub)]。

        `is_stub` 的判据是 **st_shndx == 12**，不是 st_size == 4。
        实测 il2cpp_* 共 232 个，全部 shndx=12（`0x119a68` 那个特征段，紧挨 .rel.plt）：
        其中 st_size==4 的 186 个是单指令 `b #imm` 跳板，另外 46 个 size 更大，
        是带实体的跳板块。**两者都是导入桩，st_value 都不是真实实现。**
        """
        ds = self.sections.get(".dynsym")
        dt = self.sections.get(".dynstr")
        if not ds or not dt:
            return []
        out = []
        for i in range(ds["size"] // 16):
            off = ds["off"] + i * 16
            st_name, st_value, st_size, _info, _other, st_shndx = \
                struct.unpack_from("<IIIBBH", self.data, off)
            p = dt["off"] + st_name
            nm = self.data[p:self.data.index(b"\x00", p)].decode("utf-8", "replace")
            if not nm:
                continue
            out.append((nm, st_value, st_size, st_shndx, st_shndx == STUB_SHNDX))
        return out

    def resolve(self, name: str):
        """符号名 → 真实实现地址（自动穿过 `b #imm` 跳板）。找不到返回 None。

        注意「已是真身」这个结论要谨慎：部分符号的 st_value 落在桩段内，
        但那一处的机器码恰好不是 `b` 指令（例如 `ldr r0,[r0,#0x5c]; bx lr`
        这种一行小函数）。此类情况本函数原样返回 st_value —— **它本身就可能
        是真实实现**，不必再找跳转目标。
        """
        for nm, va, _sz, _sh, is_stub in self.symbols():
            if nm != name:
                continue
            if not is_stub:
                return va
            off = self.va2off(va)
            if off is None:
                return va
            word = struct.unpack_from("<I", self.data, off)[0]
            tgt = decode_arm_b(va, word)
            if tgt is None:
                return va
            # 目标处若还是一条 b，继续跟（实测存在 b -> b 的双跳）
            for _ in range(3):
                o2 = self.va2off(tgt)
                if o2 is None:
                    break
                w2 = struct.unpack_from("<I", self.data, o2)[0]
                t2 = decode_arm_b(tgt, w2)
                if t2 is None or t2 == tgt:
                    break
                tgt = t2
            return tgt
        return None

    def disasm(self, va: int, n: int = 16, mode_arm: bool = True):
        """反汇编 n 条。需要 capstone。"""
        import capstone
        off = self.va2off(va)
        if off is None:
            raise ValueError("VA 0x%X 不在任何 PT_LOAD 内" % va)
        md = capstone.Cs(capstone.CS_ARCH_ARM,
                         capstone.CS_MODE_ARM if mode_arm else capstone.CS_MODE_THUMB)
        md.skipdata = True       # ★ 不开会提前停在非法编码处，只解出极少数指令
        out = []
        for insn in md.disasm(self.data[off:off + n * 4], va):
            out.append(insn)
            if len(out) >= n:
                break
        return out


def main(argv):
    e = Elf32()
    cmd = argv[0] if argv else "sections"

    if cmd == "sections":
        print("文件 %s（%d 字节）" % (e.path, len(e.data)))
        print("%-18s %10s %10s %10s %6s" % ("name", "addr", "off", "size", "flags"))
        for n, s in e.sections.items():
            if s["name_off"] == 0:
                continue
            print("%-18s 0x%08x 0x%08x %10d   0x%x"
                  % (n, s["addr"], s["off"], s["size"], s["flags"]))
        print("\nPT_LOAD:")
        for off, va, fsz, msz, fl in e.phdrs:
            print("  va=0x%08x off=0x%08x filesz=0x%08x memsz=0x%08x flags=%d"
                  % (va, off, fsz, msz, fl))
        return 0

    if cmd == "syms":
        needle = argv[1] if len(argv) > 1 else "il2cpp"
        hits = [s for s in e.symbols() if needle in s[0]]
        print("命中 %d 个符号" % len(hits))
        for nm, va, sz, sh, stub in sorted(hits, key=lambda x: x[0]):
            print("  0x%08x size=%-4d shndx=%-3d %s %s"
                  % (va, sz, sh, "桩" if stub else "  ", nm))
        return 0

    if cmd == "resolve":
        needle = argv[1] if len(argv) > 1 else "il2cpp"
        hits = [s for s in e.symbols() if needle in s[0]]
        print("%-44s %-12s %-12s %s" % ("symbol", "st_value", "real", "说明"))
        for nm, va, _sz, _sh, stub in sorted(hits, key=lambda x: x[0]):
            real = e.resolve(nm)
            tag = "已是真身（无跳转）" if (real == va) else "穿过跳板"
            print("%-44s 0x%08x   0x%08x   %s" % (nm, va, real or 0, tag))
        return 0

    if cmd == "b":
        va = int(argv[1], 0)
        off = e.va2off(va)
        word = struct.unpack_from("<I", e.data, off)[0]
        tgt = decode_arm_b(va, word)
        print("va=0x%08x word=0x%08x -> %s"
              % (va, word, ("0x%08x" % tgt) if tgt else "非分支指令"))
        return 0

    if cmd == "check":
        allsyms = [s for s in e.symbols() if s[0].startswith("il2cpp_")]
        stubs = [s for s in allsyms if s[4]]
        one_instr = [s for s in stubs if s[2] == 4]
        real = [s for s in allsyms if not s[4]]
        print("il2cpp_* 符号总数：%d" % len(allsyms))
        print("  导入桩（st_shndx==%d）：%d 个" % (STUB_SHNDX, len(stubs)))
        print("    其中单指令 `b #imm` 跳板：%d 个" % len(one_instr))
        print("    其中带实体的跳板块：      %d 个" % (len(stubs) - len(one_instr)))
        print("  非桩（真正的实现）：        %d 个" % len(real))
        for nm, va, sz, sh, _ in real[:20]:
            print("    0x%08x size=%-4d shndx=%-3d %s" % (va, sz, sh, nm))
        return 0

    if cmd == "dis":
        va = int(argv[1], 0)
        n = int(argv[2]) if len(argv) > 2 else 16
        for insn in e.disasm(va, n):
            print("  0x%08x  %-8s %s" % (insn.address, insn.mnemonic, insn.op_str))
        return 0

    print("未知命令：%s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
