"""libil2cpp.so 反汇编工具：定位 SaveManager.ctor 并追踪 ES3Settings 构造。"""
from paths import SO

import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM, CS_OP_IMM, CS_OP_REG, CS_OP_MEM
def load_so(path=SO):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF", "not ELF"
    is64 = data[4] == 2
    assert is64, "expect ELF64"
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", data, off)[0]
        if p_type != 1:  # PT_LOAD
            continue
        p_flags = struct.unpack_from("<I", data, off + 4)[0]
        p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from(
            "<QQQQQ", data, off + 8
        )
        segs.append(
            dict(flags=p_flags, off=p_offset, va=p_vaddr, filesz=p_filesz, memsz=p_memsz)
        )
    return data, segs


def va_to_off(segs, va):
    for s in segs:
        if s["va"] <= va < s["va"] + s["filesz"]:
            return s["off"] + (va - s["va"])
    return None


def off_to_va(segs, off):
    for s in segs:
        if s["off"] <= off < s["off"] + s["filesz"]:
            return s["va"] + (off - s["off"])
    return None


def disasm(va, count=120, base=None):
    data, segs = load_so()
    off = va_to_off(segs, va)
    if off is None:
        print(f"VA {va:#x} not in any PT_LOAD segment")
        return
    code = data[off : off + count * 4 + 64]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    for i, ins in enumerate(md.disasm(code, va)):
        if i >= count:
            break
        ops = []
        for op in ins.operands:
            if op.type == CS_OP_IMM:
                ops.append(f"#{op.imm:#x}")
            elif op.type == CS_OP_REG:
                ops.append(ins.reg_name(op.reg))
            elif op.type == CS_OP_MEM:
                b = ins.reg_name(op.mem.base)
                d = ins.reg_name(op.mem.disp) if op.mem.disp else ""
                inner = b
                if op.mem.disp:
                    inner = f"{b}+{op.mem.disp:#x}" if op.mem.disp > 0 else f"{b}-{-op.mem.disp:#x}"
                ops.append(f"[{inner}]")
            else:
                ops.append(str(op.type))
        print(f"{ins.address:#010x}  {ins.mnemonic:<8} {', '.join(ops)}")
        if ins.mnemonic in ("ret", "brk") or (ins.mnemonic == "b" and not ops):
            break


if __name__ == "__main__":
    va = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x17A64D8
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    print(f"=== disasm VA {va:#x} ===")
    disasm(va, n)
