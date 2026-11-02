#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新增逆向工具链的自检 —— 保证 meta_* / elf_v557 在干净机器上也能跑。

这些脚本的价值全在「解析对不对」，所以断言必须钉在**已知正确的具体值**上，
而不是「不抛异常」。每条断言都注明它在验证什么。

    python tools/test_meta_tools.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from meta_v557 import Meta, TYPE_DEF_STRIDE, METHOD_DEF_STRIDE, FIELD_DEF_STRIDE
from meta_literal import decode_sentinel, encode_sentinel, literal_at
from meta_fields import field_offset
from elf_v557 import Elf32, decode_arm_b, STUB_SHNDX

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print("  %-46s PASS %s" % (name, detail))
    else:
        _failed += 1
        print("  %-46s FAIL %s" % (name, detail))


def test_header():
    print("[1] metadata v27 段表")
    m = Meta()
    check("magic 是 0xfab11baf", m.magic == 0xFAB11BAF, "0x%08x" % m.magic)
    check("version == 27", m.version == 27, str(m.version))
    # 最强断言：末段游标必须精确等于文件大小，任何步长/顺序错误都会破
    check("末段游标 == 文件大小", m.check(),
          "0x%x vs %d" % (m.cursor, len(m.data)))
    check("stringLiteral 在 0x100", m.abs_off["stringLiteral"][0] == 0x100,
          "0x%x" % m.abs_off["stringLiteral"][0])
    check("typeDefinitions 在 0x2fcd90", m.abs_off["typeDefinitions"][0] == 0x2FCD90,
          "0x%x" % m.abs_off["typeDefinitions"][0])
    check("methods 段有 31519 条", m.abs_off["methods"][1] // METHOD_DEF_STRIDE == 31519,
          str(m.abs_off["methods"][1] // METHOD_DEF_STRIDE))


def test_types():
    print("[2] 类型 / 方法 / 字段")
    m = Meta()

    ti, _ = m.type_by_name("GameGUI")
    check("GameGUI 类型序号 4355", ti == 4355, str(ti))

    ms = m.methods_of("GameGUI")
    check("GameGUI 有 64 个方法", len(ms) == 64, str(len(ms)))
    hit = [x for x in ms if x[1] == "OpenChongWuUI"]
    # token 是稳定的：0x060005a9。用 token 断言能同时验证 methods 步长与起始索引
    check("OpenChongWuUI token == 0x060005a9",
          bool(hit) and hit[0][2] == 0x060005A9,
          "0x%08x" % hit[0][2] if hit else "未找到")
    check("OpenChongWuUI 无参数", bool(hit) and hit[0][5] == 0,
          str(hit[0][5]) if hit else "-")

    zs = m.methods_of("ZuoBi")
    check("ZuoBi 有 3 个方法", len(zs) == 3, str(len(zs)))

    fs = m.fields_of("GameGUI")
    check("GameGUI 有 63 个字段", len(fs) == 63, str(len(fs)))
    chong = [x for x in fs if x[1] == "ChongWuUIGO"]
    check("ChongWuUIGO 是第 22 个字段", bool(chong) and chong[0][0] == 22,
          str(chong[0][0]) if chong else "-")


def test_literal():
    print("[3] stringLiteral 表")
    m = Meta()
    table = m.literal_table()
    # 70448 / 8 = 8806 条，一条都不能丢
    check("表长 8806", len(table) == 8806, str(len(table)))
    check("SaveFile.es3 在 [3386]", table[3386] == "SaveFile.es3", repr(table[3386]))
    check("PJSQJ678 在 [3089]", table[3089] == "PJSQJ678", repr(table[3089]))
    check("heiMingDan 端点可搜到",
          any(s and "heiMingDan.asp" in s for s in table))

    # 哨兵编解码往返
    v = encode_sentinel(12153)
    check("encode(12153) == 0xA0005EF3", v == 0xA0005EF3, "0x%08x" % v)
    check("decode(0xA0005EF3) == 12153", decode_sentinel(0xA0005EF3) == 12153)
    check("decode 拒绝非哨兵 0x1234", decode_sentinel(0x1234) is None)


def test_field_offset():
    print("[4] 字段偏移公式")
    check("idx 22 在 32 位下 = 0x60", field_offset(22) == 0x60, hex(field_offset(22)))
    check("idx 22 在 64 位下 = 0xC0", field_offset(22, True) == 0xC0,
          hex(field_offset(22, True)))
    check("idx 0 在 32 位下 = 0x08", field_offset(0) == 0x08, hex(field_offset(0)))


def test_elf():
    print("[5] ELF32 符号解析")
    e = Elf32()
    syms = {s[0]: s for s in e.symbols()}

    # st_shndx==12 才是桩的判据，不是 st_size==4
    il2 = [s for s in e.symbols() if s[0].startswith("il2cpp_")]
    check("il2cpp_* 共 232 个", len(il2) == 232, str(len(il2)))
    check("il2cpp_* 全部 st_shndx==12",
          all(s[3] == STUB_SHNDX for s in il2),
          str({s[3] for s in il2}))

    # PLT 桩穿过跳板后的真实地址
    real = e.resolve("il2cpp_class_from_name")
    check("class_from_name 解到 0x0022bc94", real == 0x0022BC94,
          "0x%08x" % (real or 0))

    # 这条不是跳板，而是一行小函数，反汇编必须是 ldr r0,[r0,#0x5c]; bx lr
    off = e.va2off(syms["il2cpp_class_get_static_field_data"][1])
    raw = e.data[off:off + 8]
    check("static_field_data 是 ldr r0,[r0,#0x5c]",
          raw[:4] == bytes.fromhex("5c0090e5"),
          raw[:4].hex())
    check("紧随 bx lr", raw[4:8] == bytes.fromhex("1eff2fe1"), raw[4:8].hex())

    # ARM b 指令解码：+8 流水线偏移
    check("decode_arm_b 0x1fe698 → 0x22bc90",
          decode_arm_b(0x001FE698, 0xEA00B57C) == 0x0022BC90,
          hex(decode_arm_b(0x001FE698, 0xEA00B57C) or 0))
    check("非分支指令返回 None",
          decode_arm_b(0x1000, 0xE1A00000) is None)


def test_find_calls():
    print("[6] ARM32 调用点搜索（find_calls_arm32）")
    import find_calls_arm32 as F

    so = F.DEFAULT_SO
    if not so.exists():
        check("v557 .so 存在", False, str(so))
        return
    data, secs = F.load_elf(so)

    # SceneManager.LoadScene(string) 的 RVA 来自 dump.cs
    hits = F.find_bl_to(data, secs, 0x6A4C90)
    check("LoadScene(string) 有 10 处调用", len(hits) == 10, str(len(hits)))
    # 封号链路里唯一的那处
    rvas = {r for _o, r in hits}
    check("其中包含 0x3EDB48（GetBaoName）", 0x3EDB48 in rvas)

    # PLT 桩表：LoadScene 必须能在 .rel.plt 里找到
    stubs = F.plt_stubs(data, secs, F.dynsyms(data, secs))
    check("PLT 能解出 .rel.plt 表项",
          len(stubs) > 0, "%d 个符号" % len(stubs))


def test_scene_classes():
    print("[7] Unity 场景类分布（unity_scene_classes）")
    import unity_scene_classes as U

    bundle = U.DEFAULT_BUNDLE
    if not bundle.exists():
        print("  (跳过：%s 不存在)" % bundle)
        return

    import UnityPy
    env = UnityPy.load(str(bundle))
    scripts = U.script_class_map(env)
    # m_Name 在偏移 0 才对；按偏移 8 解会大面积失败
    check("能解出 >1200 个 MonoScript 类名",
          len(scripts) > 1200, "%d 个" % len(scripts))
    check("MonoScript pid 697 是 ZuoBi",
          scripts.get(697) == "ZuoBi", str(scripts.get(697)))

    rows = U.monobehaviour_class(env, scripts)
    lv11 = [c for s, c in rows if s == "level11"]
    check("level11 有 6 个 MonoBehaviour", len(lv11) == 6, str(len(lv11)))
    check("level11 里恰好 1 个 ZuoBi", lv11.count("ZuoBi") == 1)

    lv7 = [c for s, c in rows if s == "level7"]
    check("level7（Level_ChongWu）里有 ChongWuManager",
          "ChongWuManager" in lv7)


def main():
    print("=" * 60)
    test_header()
    test_types()
    test_literal()
    test_field_offset()
    test_elf()
    test_find_calls()
    test_scene_classes()
    print("=" * 60)
    print("结果: %d passed, %d failed" % (_passed, _failed))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
