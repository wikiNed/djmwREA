# -*- coding: utf-8 -*-
"""列出 ELF 段/节表，方便判断某地址落在哪个区。"""
import struct
import sys


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        d = f.read()
    is64 = d[4] == 2
    if not is64:
        print("只支持 64 位")
        return
    e_shoff = struct.unpack_from("<Q", d, 0x28)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", d, 0x3A)
    sh = []
    for i in range(e_shnum):
        b = e_shoff + i * e_shentsize
        name, typ, flags, addr, off, size = struct.unpack_from("<IIQQQQ", d, b)
        sh.append((name, typ, flags, addr, off, size))
    strtab = sh[e_shstrndx]
    names = d[strtab[4]: strtab[4] + strtab[5]]
    print("idx  name                 type      flags    addr        off         size")
    for i, (name, typ, flags, addr, off, size) in enumerate(sh):
        nm = names[name:names.find(b"\0", name)].decode("utf-8", "replace")
        print("%-4d %-20s %-9d 0x%08x 0x%08x 0x%08x 0x%08x" % (i, nm, typ, flags, addr, off, size))


if __name__ == "__main__":
    main()
