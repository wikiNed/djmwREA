# -*- coding: utf-8 -*-
"""ARM64 反汇编小工具（ELF PT_LOAD 映射：虚拟地址 -> 文件偏移）。

    python dis64.py <so> <va> [n]        从 va 起反汇编 n 条
    python dis64.py <so> <va> --func     从 va 起直到 ret/下一函数前，最多 200 条
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM


def load_map(path):
    data = open(path, "rb").read()
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segs = []
    for i in range(e_phnum):
        b = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", data, b)[0]
        if p_type != 1:
            continue
        p_offset = struct.unpack_from("<Q", data, b + 8)[0]
        p_vaddr = struct.unpack_from("<Q", data, b + 0x10)[0]
        p_filesz = struct.unpack_from("<Q", data, b + 0x20)[0]
        segs.append((p_vaddr, p_filesz, p_offset))
    return data, segs


def va_to_off(segs, va):
    for vaddr, filesz, off in segs:
        if vaddr <= va < vaddr + filesz:
            return off + (va - vaddr)
    return None


def main():
    path, va = sys.argv[1], int(sys.argv[2], 0)
    arg = sys.argv[3] if len(sys.argv) > 3 else "40"
    data, segs = load_map(path)
    off = va_to_off(segs, va)
    if off is None:
        print("va 未映射: 0x%x" % va)
        return
    func = arg == "--func"
    n = 200 if func else int(arg, 0)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = False
    code = data[off: off + n * 4]
    done = 0
    for ins in md.disasm(code, va):
        print("%08x  %-8s  %s" % (ins.address, ins.bytes.hex(), ins.op_str and
                                 (ins.mnemonic + " " + ins.op_str) or ins.mnemonic))
        done += 1
        if func and ins.mnemonic in ("ret",):
            break
        if done >= n:
            break
    print("// %d 条" % done)


if __name__ == "__main__":
    main()
