#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模板字段盘点：逐段、逐模板对比字段集合。

目的
====
new_save.py 用 playerDate_03.bin 当骨架，所以骨架的字段集合**必须**是
游戏运行时认的超集（或至少与真机档一致）。

我们发现的差异（见 docs/22）：
  - seg2(02)  ZiYuanLiXianTime   : 01/02 没有，03 与真机档有
  - seg12(12) TanPai_{IOP,ZCS,DTCS,CZT} : 01/02/03 都没有，真机档有
  - seg12 其余 31 个字段          : 真机档 = Date_FuLiLevel 全 31 字段
  且 01/02 的 seg12 只有 14 字段（连 CBX_* 都没有）—— 说明这两份模板
  是**旧版本遗留**，不能当基准。

用法: python tools/template_diff.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import es3save as E  # noqa: E402
from paths import TEMPLATES  # noqa: E402

TPL_NAMES = ("playerDate_01.bin", "playerDate_02.bin", "playerDate_03.bin")
SAVES = {
    "device_orig(真机首档)": "SaveFile_device_orig.es3",
    "after_orig(游戏回写)": "SaveFile_after_orig.es3",
}


def segs_of_plain(path):
    txt = open(path, "rb").read().decode("utf-8")
    return [json.loads(x) for x in txt.split("$")]


def segs_of_es3(path):
    plain = E.read_save(path)
    txt = plain.decode("utf-8") if isinstance(plain, bytes) else plain
    return [json.loads(x) for x in txt.split("$")]


def main():
    src = {}
    for n in TPL_NAMES:
        p = os.path.join(TEMPLATES, n)
        if os.path.exists(p):
            src[n] = segs_of_plain(p)
    for label, fn in SAVES.items():
        p = os.path.join(ROOT, "evidence", "saves", fn)
        if os.path.exists(p):
            src[label] = segs_of_es3(p)

    names = list(src)
    print("段字段数矩阵")
    print("  %-16s %s" % ("段", "  ".join("%-14s" % n[:14] for n in names)))
    for i in range(14):
        row = "  seg%-2d         %s" % (
            i, "  ".join("%-14d" % len(src[n][i]) for n in names))
        print(row)

    # 以真机档为准，找出「我们有、真机没有」和「真机有、我们没有」
    ref_label = "device_orig(真机首档)"
    if ref_label not in src:
        print("\n(缺真机档，跳过差异分析)")
        return
    ref = src[ref_label]
    print("\n差异（以真机档为基准）")
    for n in names:
        if n == ref_label:
            continue
        for i in range(14):
            a, r = set(src[n][i]), set(ref[i])
            extra, miss = sorted(a - r), sorted(r - a)
            if extra or miss:
                print("  %-22s seg%-2d  多 %s / 缺 %s"
                      % (n, i, extra, miss))


if __name__ == "__main__":
    main()
