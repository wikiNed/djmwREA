#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 data.unity3d 里翻出宠物配置表，找出合法 ChongWuID 范围。

背景（2026-10-29 实测）
======================
存档 ``seg6.SuoYouChongWuDate`` 里放了 90 条 ``ChongWuID`` 0..89 的记录，
但游戏「我的同伴」列表只显示 1 只。怀疑真实可用 ID 并非 0..89 连续，
配置表 ``TapDemonsData_ChongWu_Sheet`` 的 ``ChongWu._ID`` 是 ``[EEKeyField]``，
且带 ``_IsKeZhua`` / ``_IsSuCai`` / ``_IsZhanDou`` / ``_IsXianLiang`` 标志位，
列表很可能只渲染 ``IsZhanDou == 1`` 的行。

本脚本用 UnityPy 打开 data.unity3d，列出名字含 ChongWu 的 TextAsset，
并把内容里出现的整数候选打出来，供人工比对。
"""
import io
import sys
from pathlib import Path

import UnityPy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths


def main():
    p = paths.unity_data_asset()
    print("unity3d: %s (%d bytes)" % (p, p.stat().st_size))
    env = UnityPy.load(str(p))

    found = 0
    for obj in env.objects:
        try:
            d = obj.read()
        except Exception:
            continue
        name = getattr(d, "m_Name", None)
        if not name or "ChongWu" not in str(name):
            continue
        found += 1
        print("\n=== %s  type=%s  path_id=%s ===" % (name, obj.type.name, obj.path_id))
        script = getattr(d, "m_Script", None)
        if isinstance(script, str):
            text = script
        elif isinstance(script, (bytes, bytearray)):
            text = bytes(script).decode("utf-8", "replace")
        else:
            data = getattr(d, "m_Script", None) or getattr(d, "script", None)
            text = repr(data)[:2000]
        print("  len = %d" % len(text))
        print("  head: %s" % text[:500].replace("\n", "\\n"))

    if not found:
        print("\n没找到名字含 ChongWu 的 TextAsset。")
        # 退一步：把所有 TextAsset 名字打出来，供人工挑
        print("\n全部 TextAsset 名字：")
        names = []
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            try:
                names.append(getattr(obj.read(), "m_Name", "?"))
            except Exception:
                pass
        for n in sorted(set(names)):
            print("  ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
