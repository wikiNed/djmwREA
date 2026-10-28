"""在 libil2cpp.so 里找对指定全局地址的 ldr/adrp 引用，定位给全局赋值的代码。"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"


def load():
    data = open(SO, "rb").read()
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        if struct.unpack_from("<I", data, o)[0] != 1:
            continue
        fl = struct.unpack_from("<I", data, o + 4)[0]
        off, va, pa, fs, ms = struct.unpack_from("<QQQQQ", data, o + 8)
        segs.append((fl, off, va, fs, ms))
    return data, segs


def va2off(segs, va):
    for fl, off, bva, fs, ms in segs:
        if bva <= va < bva + fs:
            return off + (va - bva)
    return None


def scan_refs(target_va, data, segs):
    """ARM64: adrp xN, page; ... add/ldr/str [xN, #imm] -> reconstruct page+imm"""
    # 简单策略：暴力解码整个 text 段，跟踪 adrp 寄存器值
    text_segs = [s for s in segs if s[0] & 0x4 and s[0] & 0x1]  # X|R
    hits = []
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    for fl, off, bva, fs, ms in text_segs:
        code = data[off : off + fs]
        # 用指令字节里的 immhi/immlo 重建 adrp
        n = len(code) // 4
        page = {}
        for i in range(n):
            ins_off = i * 4
            w = struct.unpack_from("<I", code, ins_off)[0]
            cur_va = bva + ins_off
            # adrp: 1xx1 0000 immlo(2) 1... rd(5); mask 0x9F000000 == 0x90000000
            if (w & 0x9F000000) == 0x90000000:
                rd = w & 0x1F
                immlo = (w >> 29) & 0x3
                immhi = (w >> 5) & 0x7FFFF
                imm = (immhi << 2) | immlo
                if imm & (1 << 20):
                    imm -= 1 << 21
                page[rd] = (cur_va & ~0xFFF) + (imm << 12)
                continue
            # ldr xN,[xM,#imm] : 1111 1001 01 imm12 rn rt
            if (w & 0xFFC00000) == 0xF9400000:
                rn = (w >> 5) & 0x1F
                rt = w & 0x1F
                imm12 = (w >> 10) & 0xFFF
                if rn in page:
                    addr = page[rn] + imm12 * 8
                    if addr == target_va:
                        hits.append((cur_va, f"ldr x{rt},[x{rn}+{imm12*8:#x}]"))
                continue
            # str xT,[xN,#imm]
            if (w & 0xFFC00000) == 0xF9000000:
                rn = (w >> 5) & 0x1F
                rt = w & 0x1F
                imm12 = (w >> 10) & 0xFFF
                if rn in page:
                    addr = page[rn] + imm12 * 8
                    if addr == target_va:
                        hits.append((cur_va, f"str x{rt},[x{rpn}]" if False else f"str x{rt},[x{rn}+{imm12*8:#x}]"))
                continue
            # add xN, xM, #imm
            if (w & 0x7F800000) == 0x11000000:
                rn = (w >> 5) & 0x1F
                rd = w & 0x1F
                imm12 = (w >> 10) & 0xFFF
                if rn in page:
                    addr = page[rn] + imm12
                    if addr == target_va:
                        hits.append((cur_va, f"add x{rd},x{rn},#{imm12:#x}"))
                continue
    return hits


if __name__ == "__main__":
    data, segs = load()
    targets = [int(x, 16) for x in sys.argv[1:]]
    for t in targets:
        print(f"\n=== refs to {t:#x} ===")
        hits = scan_refs(t, data, segs)
        for va, desc in hits[:40]:
            print(f"  {va:#x}  {desc}")
        if not hits:
            print("  (none)")
