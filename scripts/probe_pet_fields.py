#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位宠物"已解锁"的真实字段：打印段6每个槽位的全部键，并统计各键的取值分布。"""
import sys, os, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import savedit as S

D = r"E:\DSH\game\.rea-study\saves"
segs = S.load(open(os.path.join(D, "playerDate_03.json"), "rb").read())
s6 = [x for x in segs if x.get("DateID") == 6][0]
lst = s6["SuoYouChongWuDate"]

print("段6 顶层键:", list(s6.keys()))
print()
print("宠物槽位字段:", list(lst[0].keys()))
print()
for k in lst[0].keys():
    vals = [i.get(k) for i in lst]
    c = Counter(map(str, vals))
    uniq = len(c)
    sample = list(c.items())[:6]
    print("%-22s 唯一值=%-4d 样本=%s" % (k, uniq, sample))
