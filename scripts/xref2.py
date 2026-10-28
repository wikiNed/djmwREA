"""扫描对给定 VA 的全部 adrp+add/ldr/str 引用（含 store）。"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM, CS_OP_IMM, CS_OP_REG, CS_OP_MEM

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"


def load():
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
    return data, segs


def main(targets):
    data, segs = load()
    text = [s for s in segs if s[0] & 1]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    results = {t: [] for t in targets}
    regs = {}
    cur_func = 0

    for fl, off, bva, fs, ms in text:
        blob = data[off : off + fs]
        for ins in md.disasm(blob, bva):
            m = ins.mnemonic
            ops = ins.operands
            if m == "adrp":
                rd = ins.reg_name(ops[0].reg)
                regs[rd] = ops[1].imm
                continue
            if m == "add" and len(ops) == 3 and ops[2].type == CS_OP_IMM:
                rn = ins.reg_name(ops[1].reg)
                if rn in regs:
                    results.setdefault(regs[rn] + ops[2].imm, []).append(
                        (ins.address, f"add {ins.reg_name(ops[0].reg)}, {rn}, #{ops[2].imm:#x}")
                    )
                continue
            if m in ("ldr", "str", "ldrb", "strb", "ldrh", "strh") and len(ops) == 2:
                if ops[1].type == CS_OP_MEM:
                    rn = ins.reg_name(ops[1].mem.base)
                    disp = ops[1].mem.disp
                    if rn in regs:
                        addr = regs[rn] + disp
                        results.setdefault(addr, []).append(
                            (ins.address, f"{m} {ins.reg_name(ops[0].reg)}, [{rn}+{disp:#x}]")
                        )
                continue
            if m == "bl":
                continue
    return results


if __name__ == "__main__":
    targets = [int(x, 16) for x in sys.argv[1:]]
    res = main(targets)
    for t in targets:
        print(f"\n=== refs to {t:#x} ===")
        hits = res.get(t, [])
        stores = [h for h in hits if h[1].startswith("st")]
        print(f"  total {len(hits)}, stores {len(stores)}")
        for va, d in stores[:20]:
            print(f"  STORE {va:#x}  {d}")
        for va, d in hits[:20]:
            print(f"        {va:#x}  {d}")
