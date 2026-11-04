# -*- coding: utf-8 -*-
"""把 32 位 v5.5.7 的补丁点「翻译」到手机上的 64 位 libil2cpp.so。

原理：两个 build 共用同一份方法顺序（metadata 里 Assembly-CSharp 的方法索引一致），
Il2CppCodeGenModule.methodPointers 数组按同一索引存放每个方法的入口地址。
所以：
    32 位方法入口（来自 32 位 so 的 methodPointers） -> 索引 i
    64 位 methodPointers[i]                          -> 同名方法的 64 位入口
再在 64 位函数体里按常量/指令形状找对应的指令点。

用法：
    python port64.py map 0x7AE780          # 32 位地址 -> 64 位方法入口 + 函数内偏移
    python port64.py dis 0x7AE780 [n]      # 反汇编 64 位对应函数（从头）
    python port64.py win 0x7AE780 0x20 20  # 反汇编 64 位函数的指定窗口
    python port64.py const 0x7AE780 3F000000   # 在 64 位函数体内找常量（按小端存储给出）
    python port64.py find 0xE8EBC0         # 32 位 bl 的目标方法，在 64 位函数里找同名 bl
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM, CS_ARCH_ARM64, CS_MODE_ARM

SO32 = r'E:\DSH\game\djmwREA\files\old\libil2cpp_v557_arm32.so'
SO64 = r'E:\DSH\game\work\phone64\libil2cpp_64.so'
A32_ARR, A32_CNT = 0x1204878, 4931
A64_ARR, A64_CNT = 0x146e848, 4933

MD64 = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
MD32 = Cs(CS_ARCH_ARM, CS_MODE_ARM)


def load():
    d32 = open(SO32, 'rb').read()
    d64 = open(SO64, 'rb').read()
    v32 = list(struct.unpack_from('<%dI' % A32_CNT, d32, A32_ARR))
    v64 = list(struct.unpack_from('<%dQ' % A64_CNT, d64, A64_ARR))
    return d32, d64, v32, v64


def index_of(v32, addr):
    best = None
    for i, a in enumerate(v32):
        a &= ~1
        if a <= addr and (best is None or a > (v32[best] & ~1)):
            best = i
    return best


def rev(v64):
    m = {}
    for i, a in enumerate(v64):
        m.setdefault(a, i)
    return m


def func_end(v64, idx):
    start = v64[idx]
    nxt = min((v64[j] for j in range(len(v64)) if v64[j] > start), default=start + 0x8000)
    return start, min(nxt, start + 0x8000)


def dis64(d64, va, n=200):
    out = []
    for ins in MD64.disasm(d64[va:va + 4 * n], va):
        out.append((ins.address, struct.unpack('<I', ins.bytes)[0], ins.mnemonic, ins.op_str))
    return out


def names():
    try:
        import meta_v557
        m = meta_v557.Meta(meta_v557.default_meta_path())
        return m.method_names()
    except Exception as e:  # noqa
        print('# 取方法名失败: %r' % (e,))
        return []


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd = argv[1]
    d32, d64, v32, v64 = load()
    addr = int(argv[2], 16)
    idx = index_of(v32, addr)
    f32 = v32[idx] & ~1
    f64 = v64[idx]
    start, end = func_end(v64, idx)
    print('32bit %#x -> 方法 idx=%d（入口 %#x，+%#x）' % (addr, idx, f32, addr - f32))
    print('64bit 入口 %#x 范围 %#x..%#x' % (f64, start, end))
    nm = names()

    def name_of(i):
        return nm[i] if 0 <= i < len(nm) else '?'

    if cmd == 'map':
        return 0

    if cmd in ('dis', 'win'):
        if cmd == 'dis':
            off, n = 0, (int(argv[3]) if len(argv) > 3 else 60)
        else:
            off, n = int(argv[3], 16), (int(argv[4]) if len(argv) > 4 else 30)
        for a, w, m, o in dis64(d64, f64 + off, n):
            print('   %#x  %08x  %-9s %s' % (a, w, m, o))
        return 0

    if cmd == 'const':
        pats = [bytes.fromhex(x)[::-1] for x in argv[3:]]
        for p in pats:
            i = d64.find(p, start, end)
            hits = []
            while i >= 0:
                hits.append(i)
                i = d64.find(p, i + 1, end)
            print('常量 %s 命中 %d：%s' % (p[::-1].hex(), len(hits), [hex(h) for h in hits]))
        return 0

    if cmd == 'find':
        # 32 位这条指令是不是 bl / b？目标是谁？
        w = struct.unpack_from('<I', d32, addr - 0)[0]
        ins = list(MD32.disasm(struct.pack('<I', w), addr))
        if not ins:
            print('32bit 指令解码失败')
            return 1
        i0 = ins[0]
        print('32bit: %#x %s %s' % (addr, i0.mnemonic, i0.op_str))
        tgt = None
        if i0.mnemonic in ('bl', 'b', 'blx') and i0.op_str.startswith('#'):
            tgt = int(i0.op_str[1:], 16)
        if tgt is None:
            print('不是直接跳转指令')
            return 1
        ti = index_of(v32, tgt)
        print('目标 %#x = idx %d %s' % (tgt, ti, name_of(ti)))
        # 64 位函数里找「跳到同一 idx 方法」的 bl
        r64 = rev(v64)
        for a, wd, m, o in dis64(d64, start, (end - start) // 4):
            if m in ('bl', 'b') and o.startswith('#'):
                t = int(o[1:], 16)
                j = r64.get(t)
                if j == ti:
                    print('   64bit 匹配: %#x  %08x  %-9s %s   (idx %d %s)' % (a, wd, m, o, j, name_of(j)))
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
