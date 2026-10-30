#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pydisasm：自己解析 dalvik code_item 并反汇编，绕开 androguard 的 offset 混淆问题。

为什么自己写
============
`androguard disassemble -o <off>` 期待的是**指令字节**的偏移，而
`CodeItem.get_off()` 给的是 **code_item 结构体**的偏移。两者差 16 字节：

    code_item:
        u2 registers_size
        u2 ins_size
        u2 outs_size
        u2 tries_size
        u4 debug_info_off
        u4 insns_size      <- 到这里 16 字节
        u2 insns[insns_size]

直接用 code_item 偏移去 disassemble 会得到 `move v0, v0` 这类噪声，
甚至报 `opcode 0xe6 is unused`。

用法:
    python tools/dex_disasm.py <dex> <class-descriptor> [方法名...]
    python tools/dex_disasm.py <dex> --list 'Lcom/antiaddiction/sdk/UserService;'
"""
import argparse
import struct
import sys


class Dex:
    """够用的最小 dex 解析器：只解 class_data / code_item / 指令。"""

    def __init__(self, data):
        self.data = data
        hdr = struct.unpack_from("<8sIIIIIIII", data, 0)
        (self.magic, self.checksum, self.signature, self.file_size,
         self.header_size, self.endian_tag, self.link_size, self.link_off,
         self.map_off) = hdr
        (self.string_ids_size, self.string_ids_off,
         self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off,
         self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off,
         self.class_defs_size, self.class_defs_off) = struct.unpack_from(
             "<12I", data, 0x38)
        self._build_strings()

    def _build_strings(self):
        d = self.data
        self.strings = []
        for i in range(self.string_ids_size):
            off = struct.unpack_from("<I", d, self.string_ids_off + 4 * i)[0]
            # uleb128 长度 + MUTF-8
            pos = off
            n, pos = self._uleb(pos)
            raw = d[pos:pos + n * 3]
            self.strings.append(self._mutf8(raw, n))

    def _uleb(self, pos):
        d, result, shift = self.data, 0, 0
        while True:
            b = d[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result, pos
            shift += 7

    @staticmethod
    def _mutf8(raw, n):
        out, i, cnt = [], 0, 0
        while cnt < n and i < len(raw):
            b = raw[i]
            if b < 0x80:
                out.append(chr(b))
                i += 1
                cnt += 1
            elif b & 0xE0 == 0xC0:
                out.append(chr(((b & 0x1F) << 6) | (raw[i + 1] & 0x3F)))
                i += 2
                cnt += 1
            elif b & 0xF0 == 0xE0:
                out.append(chr(((b & 0x0F) << 12) | ((raw[i + 1] & 0x3F) << 6)
                               | (raw[i + 2] & 0x3F)))
                i += 3
                cnt += 1
            else:
                i += 1
        return "".join(out)

    def type_name(self, idx):
        sidx = struct.unpack_from("<I", self.data,
                                  self.type_ids_off + 4 * idx)[0]
        return self.strings[sidx]

    def method_ref(self, idx):
        """返回 (class, name, desc)。"""
        d = self.data
        cls_idx, proto_idx, name_idx = struct.unpack_from(
            "<HHI", d, self.method_ids_off + 8 * idx)
        cls = self.type_name(cls_idx)
        name = self.strings[name_idx]
        proto_off = self.proto_ids_off + 12 * proto_idx
        ret_idx = struct.unpack_from("<I", d, proto_off + 4)[0]
        params_off = struct.unpack_from("<I", d, proto_off + 8)[0]
        ret = self.type_name(ret_idx)
        params = ""
        if params_off:
            n = struct.unpack_from("<I", d, params_off)[0]
            params = "".join(self.type_name(struct.unpack_from(
                "<H", d, params_off + 4 + 2 * i)[0]) for i in range(n))
        return cls, name, "(%s)%s" % (params, ret)

    def field_ref(self, idx):
        d = self.data
        cls_idx, type_idx, name_idx = struct.unpack_from(
            "<HHI", d, self.field_ids_off + 8 * idx)
        return (self.type_name(cls_idx), self.strings[name_idx],
                self.type_name(type_idx))

    def find_class(self, descriptor):
        for i in range(self.class_defs_size):
            off = self.class_defs_off + 32 * i
            cls_idx = struct.unpack_from("<I", self.data, off)[0]
            if self.type_name(cls_idx) == descriptor:
                return struct.unpack_from("<I", self.data, off + 24)[0]
        return None

    def iter_methods(self, class_data_off):
        """class_data_item: uleb×8 头 + 编码列表。"""
        d = self.data
        p = class_data_off
        sf, p = self._uleb(p)
        inf, p = self._uleb(p)
        dm, p = self._uleb(p)
        vm, p = self._uleb(p)
        for _ in range(sf):
            _, p = self._uleb(p)
            _, p = self._uleb(p)
        for _ in range(inf):
            _, p = self._uleb(p)
            _, p = self._uleb(p)
        # 直接方法 = static/private/constructor
        idx = 0
        for _ in range(dm):
            diff, p = self._uleb(p)
            acc, p = self._uleb(p)
            code_off, p = self._uleb(p)
            idx += diff
            yield idx, acc, code_off
        # 虚方法
        idx = 0
        for _ in range(vm):
            diff, p = self._uleb(p)
            acc, p = self._uleb(p)
            code_off, p = self._uleb(p)
            idx += diff
            yield idx, acc, code_off

    def code_bytes(self, code_off):
        """从 code_item 偏移取出真正的指令字节。"""
        if not code_off:
            return None
        d = self.data
        regs, ins, outs, tries, dbg, n = struct.unpack_from(
            "<HHHHII", d, code_off)
        start = code_off + 16
        return d[start:start + n * 2], regs, ins, n


# --------------------------------------------------------------- 反汇编

#: opcode -> (助记符, 格式)。只覆盖会出现在我们目标方法里的那些；
#: 其余按「未知 opcode + 原始字」打印，视觉上一眼能看出来。
OPS = {
    0x00: ("nop", "10x"),
    0x01: ("move", "12x"), 0x02: ("move/from16", "22x"),
    0x03: ("move/16", "32x"),
    0x04: ("move-wide", "12x"), 0x05: ("move-wide/from16", "22x"),
    0x06: ("move-wide/16", "32x"),
    0x07: ("move-object", "12x"), 0x08: ("move-object/from16", "22x"),
    0x09: ("move-object/16", "32x"),
    0x0A: ("move-result", "11x"), 0x0B: ("move-result-wide", "11x"),
    0x0C: ("move-result-object", "11x"),
    0x0D: ("move-exception", "11x"),
    0x0E: ("return-void", "10x"),
    0x0F: ("return", "11x"), 0x10: ("return-wide", "11x"),
    0x11: ("return-object", "11x"),
    0x12: ("const/4", "11n"), 0x13: ("const/16", "21s"),
    0x14: ("const", "31i"), 0x15: ("const/high16", "21h"),
    0x16: ("const-wide/16", "21s"), 0x17: ("const-wide/32", "31i"),
    0x18: ("const-wide", "51l"), 0x19: ("const-wide/high16", "21h"),
    0x1A: ("const-string", "21c"), 0x1B: ("const-string/jumbo", "31c"),
    0x1C: ("const-class", "21c"),
    0x1D: ("monitor-enter", "11x"), 0x1E: ("monitor-exit", "11x"),
    0x1F: ("check-cast", "21c"),
    0x20: ("instance-of", "22c"), 0x21: ("array-length", "12x"),
    0x22: ("new-instance", "21c"), 0x23: ("new-array", "22c"),
    0x24: ("filled-new-array", "35c"),
    0x25: ("filled-new-array/range", "3rc"),
    0x26: ("fill-array-data", "31t"), 0x27: ("throw", "11x"),
    0x28: ("goto", "10t"), 0x29: ("goto/16", "20t"),
    0x2A: ("goto/32", "30t"),
    0x2B: ("packed-switch", "31t"), 0x2C: ("sparse-switch", "31t"),
    0x2D: ("cmpl-float", "23x"), 0x2E: ("cmpg-float", "23x"),
    0x2F: ("cmpl-double", "23x"), 0x30: ("cmpg-double", "23x"),
    0x31: ("cmp-long", "23x"),
    0x32: ("if-eq", "22t"), 0x33: ("if-ne", "22t"),
    0x34: ("if-lt", "22t"), 0x35: ("if-ge", "22t"),
    0x36: ("if-gt", "22t"), 0x37: ("if-le", "22t"),
    0x38: ("if-eqz", "21t"), 0x39: ("if-nez", "21t"),
    0x3A: ("if-ltz", "21t"), 0x3B: ("if-gez", "21t"),
    0x3C: ("if-gtz", "21t"), 0x3D: ("if-lez", "21t"),
    0x44: ("aget", "23x"), 0x45: ("aget-wide", "23x"),
    0x46: ("aget-object", "23x"), 0x47: ("aget-boolean", "23x"),
    0x48: ("aget-byte", "23x"), 0x49: ("aget-char", "23x"),
    0x4A: ("aget-short", "23x"),
    0x4B: ("aput", "23x"), 0x4C: ("aput-wide", "23x"),
    0x4D: ("aput-object", "23x"), 0x4E: ("aput-boolean", "23x"),
    0x4F: ("aput-byte", "23x"), 0x50: ("aput-char", "23x"),
    0x51: ("aput-short", "23x"),
    0x52: ("iget", "22c"), 0x53: ("iget-wide", "22c"),
    0x54: ("iget-object", "22c"), 0x55: ("iget-boolean", "22c"),
    0x56: ("iget-byte", "22c"), 0x57: ("iget-char", "22c"),
    0x58: ("iget-short", "22c"),
    0x59: ("iput", "22c"), 0x5A: ("iput-wide", "22c"),
    0x5B: ("iput-object", "22c"), 0x5C: ("iput-boolean", "22c"),
    0x5D: ("iput-byte", "22c"), 0x5E: ("iput-char", "22c"),
    0x5F: ("iput-short", "22c"),
    0x60: ("sget", "21c"), 0x61: ("sget-wide", "21c"),
    0x62: ("sget-object", "21c"), 0x63: ("sget-boolean", "21c"),
    0x64: ("sget-byte", "21c"), 0x65: ("sget-char", "21c"),
    0x66: ("sget-short", "21c"),
    0x67: ("sput", "21c"), 0x68: ("sput-wide", "21c"),
    0x69: ("sput-object", "21c"), 0x6A: ("sput-boolean", "21c"),
    0x6B: ("sput-byte", "21c"), 0x6C: ("sput-char", "21c"),
    0x6D: ("sput-short", "21c"),
    0x6E: ("invoke-virtual", "35c"), 0x6F: ("invoke-super", "35c"),
    0x70: ("invoke-direct", "35c"), 0x71: ("invoke-static", "35c"),
    0x72: ("invoke-interface", "35c"),
    0x74: ("invoke-virtual/range", "3rc"),
    0x75: ("invoke-super/range", "3rc"),
    0x76: ("invoke-direct/range", "3rc"),
    0x77: ("invoke-static/range", "3rc"),
    0x78: ("invoke-interface/range", "3rc"),
}
for _i in range(13):
    OPS[0x90 + _i] = ("add-int" if _i == 0 else "rsub-int", "23x")
BIN = ["add-int", "sub-int", "mul-int", "div-int", "rem-int", "and-int",
       "or-int", "xor-int", "shl-int", "shr-int", "ushr-int"]
for _i, _n in enumerate(BIN):
    OPS[0x90 + _i] = (_n, "23x")
    OPS[0xB0 + _i] = (_n + "/2addr", "12x")
    OPS[0xD0 + _i] = (_n + "/lit16", "22s")
    OPS[0xD8 + _i] = (_n + "/lit8", "22b")
for _i in range(5):
    OPS[0x95 + _i] = (["add-int", "sub-int", "mul-int", "div-int",
                       "rem-int"][_i] + "/lit16", "22s") if False else \
        OPS.get(0x95 + _i, ("op_%02x" % (0x95 + _i), "?"))
OPS[0x95] = ("mul-int/lit16", "22s")
OPS[0x96] = ("div-int/lit16", "22s")
OPS[0x97] = ("rem-int/lit16", "22s")
OPS[0x98] = ("and-int/lit16", "22s")
OPS[0x99] = ("or-int/lit16", "22s")
OPS[0x9A] = ("xor-int/lit16", "22s")
OPS[0x9B] = ("add-int/lit8", "22b")
OPS[0x9C] = ("rsub-int/lit8", "22b")
OPS[0x9D] = ("mul-int/lit8", "22b")
OPS[0x9E] = ("div-int/lit8", "22b")
OPS[0x9F] = ("rem-int/lit8", "22b")
OPS[0xA0] = ("and-int/lit8", "22b")
OPS[0xA1] = ("or-int/lit8", "22b")
OPS[0xA2] = ("xor-int/lit8", "22b")
OPS[0xA3] = ("shl-int/lit8", "22b")
OPS[0xA4] = ("shr-int/lit8", "22b")
OPS[0xA5] = ("ushr-int/lit8", "22b")


def _sx(v, bits):
    m = 1 << (bits - 1)
    return (v ^ m) - m


def decode(dex, code, base_addr=0):
    """把指令字节解成 (offset, mnemonic, operands) 列表。"""
    out = []
    p, n = 0, len(code) // 2
    reg = 0
    while p < n:
        unit = struct.unpack_from("<H", code, p * 2)[0]
        op = unit & 0xFF
        name, fmt = OPS.get(op, ("op_%02x" % op, "10x"))
        addr = (base_addr + p) * 2
        a = unit >> 8
        arg = ""
        try:
            if fmt == "10x":
                p += 1
            elif fmt == "12x":
                arg = "v%d, v%d" % (a & 0xF, a >> 4)
                p += 1
            elif fmt == "11n":
                arg = "v%d, #%d" % (a & 0xF, _sx(a >> 4, 4))
                p += 1
            elif fmt == "11x":
                arg = "v%d" % a
                p += 1
            elif fmt == "10t":
                arg = "-> %+d" % _sx(a, 8)
                p += 1
            elif fmt == "20t":
                off = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "-> %+d" % off
                p += 2
            elif fmt == "22x":
                arg = "v%d, v%d" % (a, struct.unpack_from("<H", code, (p + 1) * 2)[0])
                p += 2
            elif fmt == "21s":
                v = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "v%d, #%d" % (a, v)
                p += 2
            elif fmt == "21h":
                v = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "v%d, #%d" % (a, v << 16)
                p += 2
            elif fmt == "21t":
                v = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "v%d, -> %+d" % (a, v)
                p += 2
            elif fmt == "21c":
                idx = struct.unpack_from("<H", code, (p + 1) * 2)[0]
                p += 2
                if name.startswith("const-string"):
                    arg = "v%d, %r" % (a, dex.strings[idx]
                                       if idx < len(dex.strings) else "?")
                elif name == "const-class":
                    arg = "v%d, %s" % (a, dex.type_name(idx))
                elif name.startswith(("sget", "sput")):
                    f = dex.field_ref(idx)
                    arg = "v%d, %s->%s:%s" % (a, f[0], f[1], f[2])
                else:
                    arg = "v%d, @0x%x" % (a, idx)
            elif fmt == "31i":
                v = struct.unpack_from("<i", code, (p + 1) * 2)[0]
                arg = "v%d, #%d" % (a, v)
                p += 3
            elif fmt == "22t":
                v = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "v%d, v%d, -> %+d" % (a & 0xF, a >> 4, v)
                p += 2
            elif fmt == "22s":
                v = struct.unpack_from("<h", code, (p + 1) * 2)[0]
                arg = "v%d, v%d, #%d" % (a & 0xF, a >> 4, v)
                p += 2
            elif fmt == "22b":
                b = struct.unpack_from("<b", code, (p + 1) * 2)[0]
                arg = "v%d, v%d, #%d" % (a, a >> 8 if False else (struct.unpack_from('<H', code, (p+1)*2)[0] >> 8), b)
                p += 2
            elif fmt == "22c":
                idx = struct.unpack_from("<H", code, (p + 1) * 2)[0]
                f = dex.field_ref(idx)
                arg = "v%d, v%d, %s->%s:%s" % (a & 0xF, a >> 4, f[0], f[1], f[2])
                p += 2
            elif fmt == "23x":
                v = struct.unpack_from("<H", code, (p + 1) * 2)[0]
                arg = "v%d, v%d, v%d" % (a, v & 0xFF, v >> 8)
                p += 2
            elif fmt == "12x_lit8":
                p += 1
            elif fmt == "22b_lit8":
                b = struct.unpack_from("<b", code, (p + 1) * 2)[0]
                arg = "v%d, v%d, #%d" % (a, a, b)
                p += 2
            elif fmt == "35c":
                idx = struct.unpack_from("<H", code, (p + 1) * 2 + 2)[0]
                cnt = a >> 4
                g = (a & 0xF, a >> 8)
                p += 3
                c, mname, mdesc = dex.method_ref(idx)
                arg = "%s->%s%s" % (c, mname, mdesc)
            elif fmt == "3rc":
                idx = struct.unpack_from("<H", code, (p + 1) * 2 + 2)[0]
                p += 3
                c, mname, mdesc = dex.method_ref(idx)
                arg = "%s->%s%s" % (c, mname, mdesc)
            else:
                p += 1
        except Exception:  # noqa: BLE001
            p += 1
        out.append((addr, name, arg))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dex")
    ap.add_argument("cls", help="类描述符，如 Lcom/antiaddiction/sdk/UserService;")
    ap.add_argument("methods", nargs="*", help="方法名（不给则列全部）")
    a = ap.parse_args()

    dex = Dex(open(a.dex, "rb").read())
    cdo = dex.find_class(a.cls)
    if cdo is None:
        raise SystemExit("找不到类 %s" % a.cls)
    for idx, acc, code_off in dex.iter_methods(cdo):
        c, name, desc = dex.method_ref(idx)
        if a.methods and name not in a.methods:
            continue
        print("\n===== %s->%s%s  code_off=%d =====" % (c, name, desc, code_off))
        if not code_off:
            print("  (abstract/native)")
            continue
        got = dex.code_bytes(code_off)
        if got is None:
            continue
        code, regs, ins, n = got
        print("  regs=%d ins=%d insns=%d" % (regs, ins, n))
        for addr, mnm, arg in decode(dex, code):
            print("  %04x  %-18s %s" % (addr, mnm, arg))


if __name__ == "__main__":
    main()

