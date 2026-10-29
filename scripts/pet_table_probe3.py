#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 APK 内部的 sharedassets*.resource 里找宠物配置表。

背景
====
``pet_table_probe2.py`` 证明 ``TapDemonsData_ChongWu_Sheet`` 只有 MonoScript
（在 data.unity3d 中），没有任何 MonoBehaviour 实例 —— 说明 EasyExcel 生成的
行数据不在主包里，而在 APK 的 ``assets/bin/Data/sharedassets*.resource`` 或
``assets/bin/Data/resources.resource``。

本脚本把 APK 里的这些 .resource 解出来到临时目录，再用 UnityPy 打开，
列出每个包里 MonoScript 指向 TapDemonsData_ChongWu_Sheet 的实例，
并尝试读 typetree 拿行数据的 ID 集合。
"""
import sys
import tempfile
import zipfile
from pathlib import Path

import UnityPy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

TARGET = "TapDemonsData_ChongWu_Sheet"


def main():
    apk = paths.APK
    print("apk: %s" % apk)
    tmp = Path(tempfile.mkdtemp(prefix="rea_res_"))
    print("tmp: %s" % tmp)

    z = zipfile.ZipFile(str(apk))
    entries = [n for n in z.namelist()
               if n.startswith("assets/bin/Data/")
               and (n.endswith(".resource") or n.endswith(".assets"))]
    print("候选条目: %d" % len(entries))

    overall_hits = 0
    for name in entries:
        try:
            raw = z.read(name)
        except Exception as e:
            print("  %s 读取失败: %s" % (name, e))
            continue
        out = tmp / Path(name).name
        out.write_bytes(raw)

        try:
            env = UnityPy.load(str(out))
        except Exception as e:
            print("  %s UnityPy 打开失败: %s" % (name, e))
            continue

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
                break

        if script_ptr is None:
            continue
        print("\n>>> %s 含 %s 的 MonoScript path_id=%s" % (name, TARGET, script_ptr))

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
            overall_hits += 1
            print("    MonoBehaviour path_id=%s" % obj.path_id)
            try:
                tree = obj.read_typetree()
                for k, v in tree.items():
                    sv = repr(v)
                    print("      %s = %s" % (k, sv[:400]))
            except Exception as e:
                print("      typetree 失败: %s" % e)

    print("\n总命中: %d" % overall_hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
