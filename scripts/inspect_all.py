#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""三份演示存档的横向体检：宠物拥有数 / 宝石碎片 / 已兑礼包码"""

from paths import SAVES
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import savedit as S
for p in ("01", "02", "03"):
    path = os.path.join(D, "playerDate_%s.json" % p)
    if not os.path.exists(path):
        print("--%s: 文件不存在" % p)
        continue
    segs = S.load(open(path, "rb").read())

    def seg(n):
        for x in segs:
            if x.get("DateID") == n:
                return x
        return {}

    s6, s9, s13 = seg(6), seg(9), seg(13)
    lst = s6.get("SuoYouChongWuDate") or []
    own = [i for i in lst if i.get("ChongWuLevel", 0) > 0]
    libao = s13.get("LiBaoIDs") or []
    lv = sorted(set(i.get("ChongWuLevel") for i in lst))

    print("--%s  段数=%d" % (p, len(segs)))
    print("   宠物槽 %d / 已拥有 %d / 未拥有 %d" % (len(lst), len(own), len(lst) - len(own)))
    print("   等级分布: %s" % (lv[:12],))
    print("   BaoShiSuiPian = %s" % s9.get("BaoShiSuiPian"))
    print("   LiBaoIDs 已兑 %d 个: %s" % (len(libao), libao[:15]))
    print()
