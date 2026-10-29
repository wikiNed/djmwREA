#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在游戏进程内存段里定位宠物配置表 TapDemonsData_ChongWu_Sheet。

目标
====
存档里 ``ChongWuID`` 1..90 只有极少数能被识别（UI 显示 2/8，详情页全是
「未知型/未知」），说明配置表里有效 ID 不是 1..90 连续。需要从运行内存
反推那 8 行的 ``_ID``。

原理
====
``ChongWu : EERowData`` 是 C# 类，``_ID`` / ``_LevelMax`` / ``_NeedSiLiao``
/ ``_IsKeZhua`` 等字段在 IL2CPP 里是对象内的固定偏移。若表已展开，内存里
会出现 8 个连续排列、字段值呈规律的同型对象。

更稳的锚点是字符串：``_HuaShi`` / ``_XiYouDu`` / ``_JiNeng`` 是 string 字段，
指向托管字符串对象（UTF-16LE 或 UTF-8）。宠物名也可能直接以字符串存在。

本脚本做两件事：
1. 在 dump 出的段里搜 UTF-16LE / UTF-8 的宠物候选名与特有词；
2. 搜索形如 `<int32 ID><int32 0或小值>...` 的 8 连结构（粗筛，仅作提示）。

用法
====
    python scripts/mem_pet_table.py work/memdump
"""
import os
import struct
import sys
from pathlib import Path

# 宠物表里可能出现的专有名词（中文名/属性/化石名等）
CN_WORDS = [
    "可进化", "未知型", "同伴名称", "携带属性", "英雄体力", "英雄攻击",
    "普通", "稀有", "传说", "史诗", "远古",
]

# 结构体字段名（如果运行时保留了反射信息）
EN_WORDS = [
    "ChongWu", "_IsKeZhua", "_NeedSiLiao", "NeedSiLiao", "MaoXianWeiZhi",
    "ChongWuName", "XiYouDu", "JinHua", "ZhanDouLi",
]


def enc(s):
    yield "utf8", s.encode("utf-8")
    yield "utf16le", s.encode("utf-16-le")


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "work/memdump")
    files = sorted(root.glob("*.bin"), key=lambda p: -p.stat().st_size)
    if not files:
        print("没找到 .bin 文件于 %s" % root)
        return 1
    print("段数 %d，总计 %.1f MB" % (len(files), sum(f.stat().st_size for f in files) / 1e6))

    print("\n=== 中文关键词命中 ===")
    for f in files:
        data = f.read_bytes()
        for w in CN_WORDS:
            for e, pat in enc(w):
                i = data.find(pat)
                if i >= 0:
                    n = data.count(pat)
                    print("  %-24s %-8s %-28s count=%-4d first=+0x%x"
                          % (f.name, e, w, n, i))

    print("\n=== 英文/字段名命中 ===")
    for f in files:
        data = f.read_bytes()
        for w in EN_WORDS:
            for e, pat in enc(w):
                i = data.find(pat)
                if i >= 0:
                    print("  %-24s %-8s %-24s count=%-4d first=+0x%x"
                          % (f.name, e, w, data.count(pat), i))
    return 0


if __name__ == "__main__":
    sys.exit(main())
