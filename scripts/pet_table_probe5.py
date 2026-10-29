#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""穷举 data.unity3d 里的对象，定位 EasyExcel 数据表。

前几轮探查的教训
================
- pet_table_probe2.py 只看了 MonoBehaviour，命中 0
- pet_table_probe3.py 只扫了 assets/bin/Data/*.resource，那些其实是 FSB5 音频库
- global-metadata.dat 里只有 ``get_IsKeZhua`` 这类属性名，没有行数据

因此本脚本对 data.unity3d 做**全类型统计**：
列出每个 class_id 的对象数与总字节数，并单独打印 TextAsset /
MonoBehaviour 的名字，看 EasyExcel 的表到底以什么形式存在。
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

try:
    import UnityPy
except ImportError:
    print("需要 UnityPy：pip install UnityPy", file=sys.stderr)
    sys.exit(1)


def main():
    asset = paths.unity_data_asset()
    print("data.unity3d: %s (%d bytes)" % (asset, asset.stat().st_size))
    env = UnityPy.load(str(asset))

    stats = collections.Counter()
    sizes = collections.Counter()
    names = collections.defaultdict(list)

    total = 0
    for obj in env.objects:
        total += 1
        cid = obj.type.name
        stats[cid] += 1
        sizes[cid] += obj.byte_size
        if cid in ("TextAsset", "MonoBehaviour"):
            try:
                d = obj.read()
                nm = getattr(d, "m_Name", None) or getattr(d, "name", None)
                if nm:
                    names[cid].append(nm)
            except Exception:
                pass

    print("\n对象总数: %d" % total)
    print("\n=== 按类型统计（前 20）===")
    for cid, n in stats.most_common(20):
        print("  %-22s %6d 个   %10.2f MB" % (cid, n, sizes[cid] / 1e6))

    for cid in ("TextAsset", "MonoBehaviour"):
        lst = names.get(cid, [])
        print("\n=== %s 名称（%d 个）===" % (cid, len(lst)))
        hit = [x for x in lst if "ChongWu" in x or "TapDemons" in x or "Data" in x]
        print("  含 ChongWu/TapDemons/Data 的: %d" % len(hit))
        for x in hit[:60]:
            print("    %s" % x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
