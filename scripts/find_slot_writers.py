"""静态扫描 libil2cpp.so，找所有写 [x?, #0x408] 且 adrp 指向 0x35e7000 的指令。

背景：保存口令的 ES3Settings 由
    SaveManager..ctor @ 0x17A64D8
        adrp x20, #0x35e7000
        ldr  x2, [x20, #0x408]      <- 取 password（Il2CppString*）
        mov  w1, #1
        bl   ES3Settings..ctor(this, 1, password)
构造；槽 0x35e7000+0x408 位于 .data（file off 0x3639000），文件里全 0。

本脚本不假设 0x17A64D8 是唯一写入者：全文件搜
  (adrp xN, 0x35e7000)  ...  (str xM, [xN, #0x408])
以及
  (ldr xN, [xN, #0x408]) 的所有出现，并列出前后 8 条指令上下文，
以便判断哪些是读、哪些是写。

也可对其它候选偏移复用：改 OFFSETS。
"""
from paths import SO

import struct
import sys
OFFSETS = [0x408, 0x100, 0x108, 0x830]

try:
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM, CS_GRP_JUMP, CS_GRP_CALL
    HAVE_CS = True
except ImportError:
    HAVE_CS = False


def load():
    with open(SO, "rb") as f:
        return f.read()


def decode_adrp(insn, pc):
    """ADRP: bits[31] op, [30:29] immlo, [28:24] 10000, [23:5] immhi, [4:0] Rd"""
    rd = insn & 0x1F
    immlo = (insn >> 29) & 0x3
    immhi = (insn >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= 1 << 21
    page = (pc & ~0xFFF) + (imm << 12)
    return rd, page


def main():
    data = load()
    targets = {}
    for off in OFFSETS:
        targets[off] = []

    if HAVE_CS:
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        # 只需粗扫：先按 4 字节找 adrp 特征位
        n = len(data)
        for i in range(0, n - 4, 4):
            w = struct.unpack_from("<I", data, i)[0]
            if (w & 0x9F000000) != 0x90000000:
                continue
            rd, page = decode_adrp(w, i)
            if page != 0x35E7000:
                continue
            # 往下找 12 条以内是否出现 ldr/str [xN, #off]
            for k in range(1, 13):
                j = i + k * 4
                if j + 4 > n:
                    break
                w2 = struct.unpack_from("<I", data, j)[0]
                # LDR (unsigned offset, 64-bit): 1111 1001 01 imm12 Rn Rt
                if (w2 & 0xFFC00000) == 0xF9400000:
                    rn = (w2 >> 5) & 0x1F
                    rt = w2 & 0x1F
                    imm = ((w2 >> 10) & 0xFFF) * 8
                    if rn == rd and imm in targets:
                        targets[imm].append((i, j, "ldr", rt, rn))
                # STR (unsigned offset, 64-bit): 1111 1001 00 imm12 Rn Rt
                if (w2 & 0xFFC00000) == 0xF9000000:
                    rn = (w2 >> 5) & 0x1F
                    rt = w2 & 0x1F
                    imm = ((w2 >> 10) & 0xFFF) * 8
                    if rn == rd and imm in targets:
                        targets[imm].append((i, j, "str", rt, rn))
    else:
        print("需要 capstone")
        return

    for off, hits in targets.items():
        print(f"\n=== 0x35e7000 + #0x{off:x} 的访问点 ({len(hits)}) ===")
        for adrp_at, at, kind, rt, rn in hits[:40]:
            print(f"  adrp@0x{adrp_at:x}  {kind} x{rt}, [x{rn}, #0x{off:x}] @ 0x{at:x}")


if __name__ == "__main__":
    main()
