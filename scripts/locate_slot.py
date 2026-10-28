"""定位 0x35e7408 / 0x35e3270 在 metadata usage 表中的编号。

IL2CPP metadata usage 编译期会生成一个 Il2CppMetadataUsage 数组，
放在 .data.rel.ro（这里第一个 LOAD 段 flags=4 是 R，实际 usage 在 RW 段）。
每个 usage 8 字节：(uint32 encodedSourceIndex, uint32 encodedType)。
另外 il2cpp_codegen_string_literal 的用法：
    ldr x0, [metadata_usage_slot]
    bl  il2cpp_codegen_string_literal   -> 返回 Il2CppString*
"""
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
    print(f"LOAD flags={fl} off={off:#x} va={va:#x} filesz={fs:#x} memsz={ms:#x}")


def find_section(va):
    for fl, off, bva, fs, ms in segs:
        if bva <= va < bva + fs:
            return fl, off + (va - bva), fs
    return None


for target in (0x35E7408, 0x35E3270, 0x35E3370, 0x35E7300, 0x35E7310):
    r = find_section(target)
    print(f"\ntarget {target:#x}: ", end="")
    if not r:
        print("NOT in file")
        continue
    fl, fo, fs = r
    print(f"segflags={fl} fileoff={fo:#x}")
    # 打印该位置附近 ±64 字节
    lo = max(0, fo - 32)
    blob = data[lo : fo + 32]
    print("  hex:", blob.hex())
    # 判断与段起点的相对位置
    for f2, o2, b2, s2, m2 in segs:
        if b2 <= target < b2 + s2:
            print(f"  rel to seg va {target - b2:#x}")
