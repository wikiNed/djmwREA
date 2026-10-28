"""定位 .so 中所有对某静态字段槽的引用。

用途：SaveManager..ctor 用 [0x35e7000+0x408] 作为 encryptionPassword，
要找出谁在初始化这个槽（il2cpp_codegen_initialize 里的字符串字面量装载）。
"""
import struct
import sys

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
PAGE = 0x35E7000
OFFS = 0x408


def load_segs(data):
    e_phoff, = struct.unpack_from("<Q", data, 32)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
    segs = []
    for i in range(e_phnum):
        p = data[e_phoff + i * e_phentsize: e_phoff + (i + 1) * e_phentsize]
        t, fl = struct.unpack_from("<II", p, 0)
        off, va, pa, fs, ms = struct.unpack_from("<QQQQQ", p, 8)
        if t == 1 and fs:
            segs.append((va, off, fs))
    return segs


def adrp_target(w, pc):
    immlo = (w >> 29) & 3
    immhi = (w >> 5) & 0x7FFFF
    imm = ((immhi << 2) | immlo) << 12
    if imm & (1 << 32):
        imm -= (1 << 33)
    return (pc & ~0xFFF) + imm


def main():
    data = open(SO, "rb").read()
    segs = load_segs(data)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    hits = []
    for va, off, fs in segs:
        blob = data[off:off + fs]
        for i in range(0, len(blob) - 12, 4):
            w, = struct.unpack_from("<I", blob, i)
            if (w & 0x9F000000) != 0x90000000:
                continue
            pc = va + i
            if adrp_target(w, pc) != PAGE:
                continue
            rd = w & 0x1F
            nxt, = struct.unpack_from("<I", blob, i + 4)
            # ldr Rt, [Rn, #imm12]
            if (nxt & 0xFFC00000) == 0xF9400000:
                rn = (nxt >> 5) & 0x1F
                off12 = ((nxt >> 10) & 0xFFF) * 8
                if rn == rd and off12 == OFFS:
                    hits.append((pc, nxt & 0x1F))
                    continue
            # add Rd, Rn, #imm12
            if (nxt & 0xFF800000) == 0x91000000:
                rn = (nxt >> 5) & 0x1F
                imm12 = (nxt >> 10) & 0xFFF
                if rn == rd and imm12 == OFFS:
                    hits.append((pc, None))
    print(f"命中 {len(hits)} 处")
    for pc, rt in hits:
        print(f"  0x{pc:x}  (rt=x{rt})" if rt is not None else f"  0x{pc:x}  (add)")


if __name__ == "__main__":
    main()
