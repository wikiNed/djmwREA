"""精确跟踪 adrp+str，找出谁写 0x35e7408（必须是 adrp 基址 = 0x35e7000 或邻近页）。

因为 .bss 无静态值，只能从代码里找写入点。IL2CPP 一般在
il2cpp_codegen_initialize_runtime_metadata 之后由：
    il2cpp_codegen_initialize_runtime_metadata((uintptr_t*)&GlobalVar);
这种模式访问，或者由 .cctor 里 assignment 写入。
"""
from paths import SO

import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM, CS_OP_IMM, CS_OP_MEM, CS_OP_REG
data = open(SO, "rb").read()

e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
eps = struct.unpack_from("<H", data, 0x36)[0]
epn = struct.unpack_from("<H", data, 0x38)[0]
segs = []
for i in range(epn):
    o = e_phoff + i * eps
    if struct.unpack_from("<I", data, o)[0] != 1:
        continue
    fl = struct.unpack_from("<I", data, o + 4)[0]
    off, va, pa, fs, ms = struct.unpack_from("<QQQQQ", data, o + 8)
    segs.append((fl, off, va, fs, ms))

# 只扫可执行段（flags & 1）
exec_segs = [s for s in segs if s[0] & 1]
print("exec segments:", [(hex(s[2]), hex(s[3])) for s in exec_segs])

TARGETS = {0x35E7408: "ES3Settings 口令槽?", 0x35E3270: "ES3Settings 类指针槽"}

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

for fl, off, bva, fs, ms in exec_segs:
    blob = data[off : off + fs]
    regs = {}
    for ins in md.disasm(blob, bva):
        m = ins.mnemonic
        ops = ins.operands
        if m == "adrp":
            regs[ins.reg_name(ops[0].reg)] = ops[1].imm
            continue
        if m in ("str", "stur") and len(ops) == 2 and ops[1].type == CS_OP_MEM:
            rn = ins.reg_name(ops[1].mem.base)
            disp = ops[1].mem.disp
            if rn in regs:
                addr = regs[rn] + disp
                if addr in TARGETS:
                    print(f"  WRITE {ins.address:#x}  {t}: {m} {ins.reg_name(ops[0].reg)}, [{rn}+{disp:#x}]")
            continue
        if m in ("ldr", "ldur") and len(ops) == 2 and ops[1].type == CS_OP_MEM:
            rn = ins.reg_name(ops[1].mem.base)
            disp = ops[1].mem.disp
            if rn in regs:
                addr = regs[rn] + disp
                if addr in TARGETS:
                    print(f"  read  {ins.address:#x}  {m} {ins.reg_name(ops[0].reg)}, [{rn}+{disp:#x}]")
            continue
        if m == "bl":
            continue
        if m in ("mov", "movz", "movk") and len(ops) == 2 and ops[0].type == CS_OP_REG:
            regs.pop(ins.reg_name(ops[0].reg), None)
print("done")
