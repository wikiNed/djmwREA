"""分析 0x35e7408 的用途：和 0x35e3270（类指针）对照。

IL2CPP 生成的典型模式：
  - 类/方法指针：adrp x0, page; ldr x0,[x0+off]; bl il2cpp_codegen_initialize_runtime_metadata
  - 字符串字面量：adrp x0, page; ldr x0,[x0+off]; bl il2cpp_codegen_string_literal
所以紧跟其后的 bl 目标能告诉我们这个槽的类型。
"""

from pathlib import Path

from paths import SO
import struct

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


def va2off(va):
    for fl, off, bva, fs, ms in segs:
        if bva <= va < bva + fs:
            return off + (va - bva)
    return None


# 已知的辅助函数
KNOWN = {
    0x1653D94: "il2cpp_codegen_initialize_runtime_metadata (thunk->0x168907c)",
    0x1653B4C: "il2cpp_codegen_class_lock / acquire",
    0x1653AF8: "write_barrier",
    0x1653C80: "il2cpp_codegen_runtime_class_init",
}

# 反汇编 ctor，找出每个 bl 的目标与前一条 ldr 的槽地址
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM, CS_OP_IMM, CS_OP_MEM, CS_OP_REG

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

start = 0x17A64D8
off = va2off(start)
code = data[off : off + 0x100]
print("=== SaveManager..ctor 逐指令 + 槽追踪 ===")
regs = {}
for ins in md.disasm(code, start):
    m = ins.mnemonic
    ops = ins.operands
    extra = ""
    if m == "adrp":
        regs[ins.reg_name(ops[0].reg)] = ops[1].imm
        extra = f"   ; {ins.reg_name(ops[0].reg)} = {ops[1].imm:#x}"
    elif m in ("ldr",) and len(ops) == 2 and ops[1].type == CS_OP_MEM:
        rn = ins.reg_name(ops[1].mem.base)
        d = ops[1].mem.disp
        if rn in regs:
            extra = f"   ; SLOT {regs[rn] + d:#x}"
    elif m == "bl":
        tgt = ops[0].imm
        extra = f"   ; -> {'KNOWN[' + KNOWN[tgt] + ']' if tgt in KNOWN else hex(tgt)}"
    print(f"{ins.address:#010x}  {m:<8} {ins.op_str}{extra}")
    if m == "ret":
        break
