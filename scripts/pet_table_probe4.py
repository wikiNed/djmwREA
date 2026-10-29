#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 APK / 资源包里精确定位宠物配置表（EasyExcel 序列化的行数据）。

背景（2026-10-29）
=================
- ``TapDemonsData_ChongWu_Sheet`` 的 MonoScript 在 data.unity3d 里（path_id=1561），
  但**没有任何 MonoBehaviour 实例**指向它。
- APK 的 ``assets/bin/Data/*.resource`` 里也搜不到（pet_table_probe3.py 总命中 0）。
- 存档里 ``ChongWuID`` 1..90 只有 2 个（1 和 10）能被游戏认出，UI 显示 2/8，
  说明表里只有 8 行。

推断
====
EasyExcel 的表要么
  (a) 打进某个 AssetBundle（不在 Data/ 下），或
  (b) 作为 Resources 里的 TextAsset 用二进制/加密格式存放，或
  (c) 走 StreamingAssets。

本脚本：
1. 列出 APK 里所有非 so/dex 的条目，按大小排序，找出可疑的数据包；
2. 对每个候选，扫描里面是否出现 EasyExcel 的表头特征字符串
   （字段名 ``_IsKeZhua`` / ``_NeedSiLiao`` / ``_XiYouDu`` 等）；
3. 报告命中位置，便于进一步解析。
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

# ChongWu 表里一组足够独特的字段名，UTF-8 编码后做字节匹配
NEEDLES = [
    b"_IsKeZhua",
    b"_NeedSiLiao",
    b"_XiYouDu",
    b"_BossDuoBiDown",
    b"TapDemonsData_ChongWu",
]


def main():
    apk = paths.APK
    print("apk: %s (%d bytes)" % (apk, apk.stat().st_size))
    z = zipfile.ZipFile(str(apk))

    infos = sorted(z.infolist(), key=lambda i: -i.file_size)
    print("\n条目总数: %d" % len(infos))
    print("\n按大小前 25（跳过 so/dex/arsc）:")
    shown = 0
    for i in infos:
        if i.filename.endswith((".so", ".dex", ".arsc")):
            continue
        print("  %10d  %s" % (i.file_size, i.filename))
        shown += 1
        if shown >= 25:
            break

    print("\n=== 扫描表头特征 ===")
    hits = 0
    for i in infos:
        if i.file_size < 512 or i.file_size > 60 * 1024 * 1024:
            continue
        try:
            raw = z.read(i.filename)
        except Exception:
            continue
        found = [n.decode() for n in NEEDLES if n in raw]
        if found:
            hits += 1
            print("\n命中 %s (%d bytes)" % (i.filename, len(raw)))
            print("  匹配: %s" % found)
            for n in NEEDLES:
                pos = raw.find(n)
                if pos >= 0:
                    print("    %-22s offset=0x%X" % (n.decode(), pos))
    print("\n命中条目数: %d" % hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
