#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IL2CPP global-metadata.dat（v27 / Unity 2020.x）表结构解析。

为什么单独写一个
----------------
v27 的头部**不直接给绝对偏移**，而是给「每段长度」。真实偏移必须从 header
末尾开始用游标逐段累加：

    cursor = 8 + 4 * 字段数          # 8 = magic(4) + version(4)
    for name in FIELDS:              # 顺序严格按头部字段顺序
        abs_off[base] = (cursor, size)
        cursor += size

自检：全部段累加完，游标必须正好等于文件大小。v5.5.7 的 metadata
（3,728,272 字节）末段游标 `0x38e390`，**零偏差** —— 这是判断解析是否正确的最硬标准。

★ 三个容易踩错的步长（实测确定，与网上多数文档不符）

| 表 | 常见写法 | **实测正确值** | 判定方法 |
|---|---|---|---|
| `Il2CppTypeDefinition` | `0x5C` | **`0x58`** | 0x58 能读出 19/20 个合法类型名，0x5C 只有 11/20 且读出 `'d'`/`'ore'`/`'rlib'` 碎片 |
| `Il2CppMethodDefinition` | `0x2C` | **`0x20`** | 0x20 得 20/20，0x2C 只 14/20 |
| `Il2CppFieldDefinition` | `0x10` | **`12`** | 步长 12 得 `value/value/value/value` + token `0x04000001..4`，步长 16 读出乱码 |

判定法统一是「用前 N 条能否读出合法的名字」——**不要用「解析不抛异常」当验证**，
错步长往往也能读出垃圾而不报错。

用法
----
    python meta_v557.py header                  # 全部段：偏移 / 大小 / 结束位置
    python meta_v557.py find GameGUI            # 在 string 表里搜关键词
    python meta_v557.py strings 0x47a00 20      # 从某偏移连续打印字符串

作为模块
--------
    from meta_v557 import Meta
    m = Meta()                       # 默认读 files/old/global-metadata_v557.dat
    m.abs_off["methods"]             # -> (offset, size)
    m.type_by_name("GameGUI")        # -> (index, base_offset)
    m.methods_of("GameGUI")          # -> [(idx, name, token, flags, slot, pcnt), ...]
    m.fields_of("GameGUI")           # -> [(idx, name, type_idx, token), ...]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# v27 头部字段顺序（每一项都是 uint32。名字里带 Offset 的按 (offset, count/size) 成对出现）
FIELDS = [
    "stringLiteralOffset", "stringLiteralCount",
    "stringLiteralDataOffset", "stringLiteralDataCount",
    "stringOffset", "stringCount",
    "eventsOffset", "eventsCount",
    "propertiesOffset", "propertiesCount",
    "methodsOffset", "methodsCount",
    "parameterDefaultValuesOffset", "parameterDefaultValuesCount",
    "fieldDefaultValuesOffset", "fieldDefaultValuesCount",
    "fieldAndParameterDefaultValueDataOffset", "fieldAndParameterDefaultValueDataCount",
    "fieldMarshaledSizesOffset", "fieldMarshaledSizesCount",
    "parametersOffset", "parametersCount",
    "fieldsOffset", "fieldsCount",
    "genericParametersOffset", "genericParametersCount",
    "genericParameterConstraintsOffset", "genericParameterConstraintsCount",
    "genericContainersOffset", "genericContainersCount",
    "nestedTypesOffset", "nestedTypesCount",
    "interfacesOffset", "interfacesCount",
    "vtableMethodsOffset", "vtableMethodsCount",
    "interfaceOffsetsOffset", "interfaceOffsetsCount",
    "typeDefinitionsOffset", "typeDefinitionsCount",
    "imagesOffset", "imagesCount",
    "assembliesOffset", "assembliesCount",
    "fieldRefsOffset", "fieldRefsCount",
    "referencedAssembliesOffset", "referencedAssembliesCount",
    "attributeDataOffset", "attributeDataCount",
    "attributeDataRangeOffset", "attributeDataRangeCount",
    "unresolvedVirtualCallParameterTypesOffset", "unresolvedVirtualCallParameterTypesCount",
    "unresolvedVirtualCallParameterRangesOffset", "unresolvedVirtualCallParameterRangesCount",
    "windowsRuntimeTypeNamesOffset", "windowsRuntimeTypeNamesSize",
    "windowsRuntimeStringsOffset", "windowsRuntimeStringsSize",
    "exportedTypeDefinitionsOffset", "exportedTypeDefinitionsCount",
]

TYPE_DEF_STRIDE = 0x58
METHOD_DEF_STRIDE = 0x20
FIELD_DEF_STRIDE = 12


def default_meta_path() -> Path:
    """优先用仓库 paths.py 的约定，找不到再退回旧版路径。"""
    try:
        from paths import FILES, META
    except Exception:
        FILES = Path(__file__).resolve().parent.parent / "files"
        META = FILES / "global-metadata.dat"
    old = FILES / "old" / "global-metadata_v557.dat"
    return old if old.exists() else META


class Meta:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_meta_path()
        if not self.path.exists():
            raise FileNotFoundError(
                f"找不到 metadata：{self.path}\n"
                f"v5.5.7 的 metadata 在 files/old/global-metadata_v557.dat，需要 git lfs pull。"
            )
        self.data = self.path.read_bytes()
        self.magic, self.version = struct.unpack_from("<Ii", self.data, 0)
        self.table, self.cursor, self.abs_off = self._parse_header()

    # ---- 头部 ----
    def _parse_header(self):
        n = len(FIELDS)
        vals = struct.unpack_from("<%dI" % n, self.data, 8)
        table = dict(zip(FIELDS, vals))
        cursor = 8 + 4 * n
        abs_off = {}
        for name in FIELDS:
            if not name.endswith("Offset"):
                continue
            base = name[: -len("Offset")]
            size = 0
            for k in (base + "Count", base + "Size"):
                if k in table:
                    size = table[k]
                    break
            abs_off[base] = (cursor, size)
            cursor += size
        return table, cursor, abs_off

    def check(self) -> bool:
        """末段游标是否精确等于文件大小 —— 解析是否正确的硬标准。"""
        return self.cursor == len(self.data)

    # ---- 字符串 ----
    def string_at(self, idx: int) -> str:
        """按 string 表里的 byte index 取字符串（index 是相对 string 段起点的偏移）。"""
        off, size = self.abs_off["string"]
        p = off + idx
        if off <= p < off + size:
            e = self.data.find(b"\x00", p)
            return self.data[p:e].decode("utf-8", "replace")
        return "<OOB:%d>" % idx

    def literal_table(self):
        """stringLiteral 表：每条 8 字节，**格式是 (length, offset)**，不是 (offset, length)。

        offset 相对 stringLiteralData 段。实测 70448/8 = 8806 条，其中约 7091 条可解。
        """
        sl_off, sl_size = self.abs_off["stringLiteral"]
        sld_off, sld_size = self.abs_off["stringLiteralData"]
        out = []
        for i in range(sl_size // 8):
            ln, lo = struct.unpack_from("<ii", self.data, sl_off + i * 8)
            if ln < 0 or lo < 0 or lo + ln > sld_size or ln > 4096:
                out.append(None)
                continue
            out.append(self.data[sld_off + lo: sld_off + lo + ln].decode("utf-8", "replace"))
        return out

    # ---- 类型 / 方法 / 字段 ----
    def type_by_name(self, name: str):
        """返回 (type_index, base_offset)，找不到返回 (None, None)。"""
        t_off, t_size = self.abs_off["typeDefinitions"]
        for i in range(t_size // TYPE_DEF_STRIDE):
            base = t_off + i * TYPE_DEF_STRIDE
            if self.string_at(struct.unpack_from("<i", self.data, base)[0]) == name:
                return i, base
        return None, None

    def methods_of(self, name: str):
        """列出类的全部方法：(idx, name, token, flags, slot, param_count)。"""
        ti, base = self.type_by_name(name)
        if ti is None:
            return []
        m_start = struct.unpack_from("<i", self.data, base + 0x24)[0]
        m_count = struct.unpack_from("<H", self.data, base + 0x40)[0]
        m_off, m_size = self.abs_off["methods"]
        out = []
        for k in range(m_count):
            mb = m_off + (m_start + k) * METHOD_DEF_STRIDE
            if mb + METHOD_DEF_STRIDE > m_off + m_size:
                out.append((k, "<OOB>", 0, 0, 0, 0))
                break
            name_idx, decl, ret, pstart, gen, token, flags, iflags, slot, pcnt = \
                struct.unpack_from("<5iIHHHH", self.data, mb)
            out.append((k, self.string_at(name_idx), token, flags, slot, pcnt))
        return out

    def fields_of(self, name: str):
        """列出类的字段：(idx, name, type_index, token)。

        Il2CppFieldDefinition 只有 12 字节：nameIndex(int32) + typeIndex(int32) + token(uint32)。
        """
        ti, base = self.type_by_name(name)
        if ti is None:
            return []
        f_start = struct.unpack_from("<i", self.data, base + 0x20)[0]
        f_count = struct.unpack_from("<H", self.data, base + 0x44)[0]
        f_off, f_size = self.abs_off["fields"]
        out = []
        for j in range(f_count):
            fb = f_off + (f_start + j) * FIELD_DEF_STRIDE
            if fb + FIELD_DEF_STRIDE > f_off + f_size:
                break
            name_idx, type_idx, tok = struct.unpack_from("<iiI", self.data, fb)
            out.append((j, self.string_at(name_idx), type_idx, tok))
        return out


def main(argv):
    m = Meta()
    cmd = argv[0] if argv else "header"

    if cmd == "header":
        print("文件 %s（%d 字节）" % (m.path, len(m.data)))
        print("magic=0x%08x version=%d" % (m.magic, m.version))
        print("%-40s %10s %10s  %10s" % ("name", "offset", "size", "end"))
        for k, (off, size) in m.abs_off.items():
            if size == 0:
                continue
            print("%-40s 0x%08x %10d  0x%08x" % (k, off, size, off + size))
        print("\n末段游标 = 0x%x (%d)  vs 文件 %d  ->  %s"
              % (m.cursor, m.cursor, len(m.data),
                 "✓ 零偏差" if m.check() else "✗ 不一致（解析有误）"))
        return 0 if m.check() else 1

    if cmd == "find":
        kw = argv[1].lower()
        off, size = m.abs_off["string"]
        p = off
        hits = 0
        while p < off + size:
            e = m.data.find(b"\x00", p)
            if e < 0:
                break
            s = m.data[p:e].decode("utf-8", "replace")
            if kw in s.lower():
                print("str 0x%06x  %s" % (p, s))
                hits += 1
            p = e + 1
        print("命中 %d" % hits)
        return 0

    if cmd == "strings":
        start = int(argv[1], 0)
        cnt = int(argv[2]) if len(argv) > 2 else 10
        off, size = m.abs_off["string"]
        p = start
        for _ in range(cnt):
            e = m.data.find(b"\x00", p)
            if e < 0 or e >= off + size:
                break
            print("0x%06x  %s" % (p, m.data[p:e].decode("utf-8", "replace")))
            p = e + 1
        return 0

    print("未知命令：%s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
