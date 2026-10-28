"""反汇编 AESEncryptionAlgorithm 的关键方法，定位 GetKey 的 100 轮迭代实现。

dump.cs 给出的 RVA：
  Encrypt(byte[],string,int)   RVA 0x17826EC   Offset 0x177E6EC
  Decrypt(byte[],string,int)   RVA 0x1782A18   Offset 0x177EA18
  Encrypt(Stream,...)          RVA 0x1782D44
  Decrypt(Stream,...)          RVA 0x178329C
  .ctor()                      RVA 0x1783838

注意：dump.cs 里的 "Offset" 是**文件偏移**，"RVA" 是虚拟地址。
本项目 libil2cpp.so 未加壳的话 RVA == 文件内 VA，需要按 program header 换算到文件偏移。

本脚本：
  1. 建立 VA -> file offset 映射
  2. 反汇编 Encrypt 附近的代码
  3. 搜索 AES 特征常量与 PBKDF2 调用
"""
from paths import SO

import struct

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
data = open(SO, "rb").read()
print("so size", len(data))

# --- program headers ---
e_phoff, = struct.unpack_from("<Q", data, 32)
e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
segs = []
for i in range(e_phnum):
    p = data[e_phoff + i * e_phentsize : e_phoff + (i + 1) * e_phentsize]
    p_type, p_flags = struct.unpack_from("<II", p, 0)
    p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz = struct.unpack_from("<QQQQQ", p, 8)
    if p_type == 1 and p_filesz:
        segs.append((p_vaddr, p_offset, p_filesz))


def va2off(va):
    for vaddr, off, filesz in segs:
        if vaddr <= va < vaddr + filesz:
            return off + (va - vaddr)
    return None


print("segments:", [(hex(a), hex(b), hex(c)) for a, b, c in segs])

TARGETS = {
    "Encrypt_bytes": 0x17826EC,
    "Decrypt_bytes": 0x1782A18,
    "Encrypt_stream": 0x1782D44,
    "Decrypt_stream": 0x178329C,
    "ctor": 0x1783838,
}

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

for name, va in TARGETS.items():
    off = va2off(va)
    print(f"\n=== {name} RVA 0x{va:x} -> file 0x{off:x} ===" if off else f"\n=== {name} NOT MAPPED ===")
    if off is None:
        continue
    code = data[off : off + 400]
    n = 0
    for ins in md.disasm(code, va):
        print(f"  0x{ins.address:x}  {ins.mnemonic:<8} {ins.op_str}")
        n += 1
        if n >= 45:
            break
