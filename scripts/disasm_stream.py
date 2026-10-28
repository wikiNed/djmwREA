"""在 Encrypt_stream(0x1782D44) 整个函数体里找 Aes 相关调用与 key 派生循环。

策略：
  1. 从 0x1782D44 反汇编到 ret（heuristic：直到地址超过下一个方法 0x178329C）
  2. 收集所有 bl 目标并打印（便于对照 il2cpp 元数据里的常见方法）
  3. 找循环结构（向后跳的分支）——  100 轮迭代会有 b.n 回到前面的循环
  4. 找立即数 0x64 (=100)
"""
import struct

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
data = open(SO, "rb").read()
e_phoff, = struct.unpack_from("<Q", data, 32)
e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
segs = []
for i in range(e_phnum):
    p = data[e_phoff + i * e_phentsize : e_phoff + (i + 1) * e_phentsize]
    p_type, _ = struct.unpack_from("<II", p, 0)
    p_offset, p_vaddr, _pp, p_filesz, _pm = struct.unpack_from("<QQQQQ", p, 8)
    if p_type == 1 and p_filesz:
        segs.append((p_vaddr, p_offset, p_filesz))


def va2off(va):
    for vaddr, off, filesz in segs:
        if vaddr <= va < vaddr + filesz:
            return off + (va - vaddr)
    return None


md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

START, END = 0x1782D44, 0x178329C
off = va2off(START)
code = data[off : va2off(END)]

print(f"=== Encrypt_stream 0x{START:x}..0x{END:x} ({END - START} bytes) ===")
back_branches = []
bl_targets = {}
const100 = []
n = 0
for ins in md.disasm(code, START):
    n += 1
    if ins.mnemonic in ("b", "b.ne", "b.eq", "b.lt", "b.gt", "b.le", "b.ge", "b.ls", "b.hi", "cbz", "cbnz", "tbz", "tbnz", "b.ne", "b.cond"):
        pass
    if ins.mnemonic.startswith("b.") or ins.mnemonic in ("b", "cbz", "cbnz", "tbz", "tbnz"):
        parts = ins.op_str.split(",")
        tgt = parts[-1].strip()
        if tgt.startswith("#0x"):
            t = int(tgt[3:], 16)
            if t < ins.address:
                back_branches.append((ins.address, t, ins.mnemonic))
    if ins.mnemonic == "bl":
        tgt = ins.op_str.strip()
        if tgt.startswith("#0x"):
            t = int(tgt[3:], 16)
            bl_targets[t] = bl_targets.get(t, 0) + 1
    if "#0x64" in ins.op_str or "0x64]" in ins.op_str:
        const100.append((ins.address, ins.mnemonic, ins.op_str))

print(f"instructions: {n}")
print(f"\n=== 向后分支（潜在循环）: {len(back_branches)} ===")
for a, t, m in back_branches[:30]:
    print(f"  0x{a:x} {m} -> 0x{t:x}")

print(f"\n=== bl 目标去重: {len(bl_targets)} ===")
for t, c in sorted(bl_targets.items(), key=lambda x: -x[1])[:40]:
    print(f"  0x{t:x}  x{c}")

print(f"\n=== 含 0x64(100) 的指令: {len(const100)} ===")
for a, m, o in const100[:20]:
    print(f"  0x{a:x}  {m} {o}")
