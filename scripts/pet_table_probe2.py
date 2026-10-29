#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 data.unity3d 里找 EERowDataCollection 形式的配置表数据。

背景
====
``pet_table_probe.py`` 只翻到一堆 MonoScript（脚本元数据，m_Script 为 None），
说明配置表不是 TextAsset，而是挂在 MonoBehaviour 上的序列化数据。
``ChongWu : EERowData`` 的实现类 ``TapDemonsData_ChongWu_Sheet`` 继承自
``EERowDataCollection``，需要找到它对应的 MonoBehaviour 实例并读字段。

本脚本：
1. 找出 TapDemonsData_ChongWu_Sheet 的 MonoScript，取其 m_ClassName / 脚本引用；
2. 遍历所有 MonoBehaviour，按 m_Script 指向该脚本的实例；
3. 用 UnityPy 的 typetree 读出其中的行数据键。

若 typetree 不可用（IL2CPP 常见），退化为打印原始字节里的整数扫描结果。
"""
import struct
import sys
from pathlib import Path

import UnityPy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

TARGET = "TapDemonsData_ChongWu_Sheet"


def main():
    p = paths.unity_data_asset()
    env = UnityPy.load(str(p))

    script_ptr = None
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            d = obj.read()
        except Exception:
            continue
        if getattr(d, "m_Name", None) == TARGET:
            script_ptr = obj.path_id
            print("找到 MonoScript %s  path_id=%s" % (TARGET, script_ptr))
            print("  m_ClassName = %r" % getattr(d, "m_ClassName", None))
            print("  m_Namespace = %r" % getattr(d, "m_Namespace", None))
            print("  m_AssemblyName = %r" % getattr(d, "m_AssemblyName", None))
            break

    if script_ptr is None:
        print("没找到 %s 的 MonoScript" % TARGET)
        return 1

    print("\n遍历 MonoBehaviour 实例...")
    n = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            d = obj.read()
        except Exception:
            continue
        s = getattr(d, "m_Script", None)
        sid = getattr(s, "path_id", None) if s is not None else None
        if sid != script_ptr:
            continue
        n += 1
        print("\n=== MonoBehaviour path_id=%s ===" % obj.path_id)
        try:
            tree = obj.read_typetree()
            print("  typetree keys:", list(tree.keys())[:40])
            for k, v in tree.items():
                sv = repr(v)
                print("   %s = %s" % (k, sv[:300]))
        except Exception as e:
            print("  typetree 失败: %s" % e)
            raw = obj.get_raw_data()
            print("  raw len = %d" % len(raw))
            # 扫描连续的 int32，打印前 200 个非零值
            vals = []
            for off in range(0, min(len(raw), 4000) - 4, 4):
                v = struct.unpack_from("<i", raw, off)[0]
                if 0 < v < 1000:
                    vals.append(v)
            print("  前 200 个 (0,1000) 范围内整数:", vals[:200])
    print("\n命中 MonoBehaviour 数: %d" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
