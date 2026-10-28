#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 RVA 通过 RELA 重定位解析成"链接器填进去的值"。

未 load 的 .so 里 GOT/.data.rel.ro 槽位 raw 全是 0；
真实初值写在 .rela.dyn 的 addend 里（R_AARCH64_RELATIVE=1027）。

用法:
    python scripts/rela_resolve.py 0x35e7408 0x35e7400 0x35e7410
    python scripts/rela_resolve.py --dump 0x36e4a90 64
"""
import struct
import sys

from paths import SO, require

RELATIVE = 1027


class Elf:
    def __init__(self, path):
        require(path, "libil2cpp.so")
        self.d = open(path, "rb").read()
        phoff, = struct.unpack_from("<Q", self.d, 0x20)
        phentsize, = struct.unpack_from("<H", self.d, 0x36)
        phnum, = struct.unpack_from("<H", self.d, 0x38)
        self.loads = []
        for i in range(phnum):
            typ, flags, off, vaddr, _pa, filesz, memsz, _al = struct.unpack_from(
                "<IIQQQQQQ", self.d, phoff + i * phentsize)
            if typ == 1:
                self.loads.append((vaddr, vaddr + filesz, off, memsz))
        self._rela = None

    def va2off(self, va):
        for vstart, vend, off, _memsz in self.loads:
            if vstart <= va < vend:
                return off + (va - vstart)
        raise ValueError("va 0x%x not mapped" % va)

    def read(self, va, n):
        o = self.va2off(va)
        return self.d[o:o + n]

    def _load_rela(self):
        if self._rela is not None:
            return self._rela
        e_shoff, = struct.unpack_from("<Q", self.d, 0x28)
        e_shentsize, = struct.unpack_from("<H", self.d, 0x3a)
        e_shnum, = struct.unpack_from("<H", self.d, 0x3c)
        tbl = {}
        for i in range(e_shnum):
            b = e_shoff + i * e_shentsize
            _nm, typ, _fl, _addr, off, size, _lk, _inf, _al, _ent = struct.unpack_from(
                "<IIQQQQIIQQ", self.d, b)
            if typ != 4:            # SHT_RELA
                continue
            for k in range(size // 24):
                ro, ri, add = struct.unpack_from("<QQq", self.d, off + k * 24)
                tbl[ro] = (ri & 0xFFFFFFFF, add)
        self._rela = tbl
        return tbl

    def resolve(self, va):
        """返回 (type, value)：value 是加载后该 8 字节的值。"""
        t = self._load_rela()
        if va in t:
            typ, add = t[va]
            return typ, add
        raw, = struct.unpack("<Q", self.read(va, 8))
        return 0, raw


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    e = Elf(SO)
    if argv[0] == "--dump":
        va = int(argv[1], 0)
        n = int(argv[2]) if len(argv) > 2 else 16
        for i in range(n):
            a = va + i * 8
            typ, val = e.resolve(a)
            print("0x%08x  type=%-4d value=0x%016x" % (a, typ, val & 0xFFFFFFFFFFFFFFFF))
        return 0
    for s in argv:
        va = int(s, 0)
        typ, val = e.resolve(va)
        print("0x%08x  type=%-4d value=0x%016x" % (va, typ, val & 0xFFFFFFFFFFFFFFFF))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
