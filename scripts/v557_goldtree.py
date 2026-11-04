#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v557 黄金树激活档：seg11 激活黄金生命之树（m12367 任务 1）。

- IsJiHuo=1（激活）、IsHuangJin=1（黄金形态）
- GuoQiTime = now + 30 天（< 37.01 天闸门 → 安全；30 天后需重推存档）
- JiHuoCiShu=1、GuoShiIsLingQu=0、GuoShiChongZhiTime = now-1000（果实可领）
- 其余 13 段原样保留（DangQianTiLi=10 已挖语义保持，反作弊安全）

用法: python scripts/v557_goldtree.py <src> <out>
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import v557save  # noqa: E402

DAY_MS = 30 * 86400_000  # 30 天（安全窗：37.01 天才封）


def seg_json(segs, i):
    b = segs[i]
    return json.loads(b.decode("utf-8") if isinstance(b, bytes) else b)


def seg_set(segs, i, obj):
    segs[i] = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()

    header, segs = v557save.read_segments(a.src)
    segs = list(segs)
    now = int(time.time() * 1000)

    s11 = seg_json(segs, 11)
    print("seg11 before:", s11)
    s11["IsJiHuo"] = 1
    s11["IsHuangJin"] = 1
    s11["GuoQiTime"] = now + DAY_MS
    s11["JiHuoCiShu"] = 1
    s11["GuoShiIsLingQu"] = 0
    s11["GuoShiChongZhiTime"] = now - 1000
    seg_set(segs, 11, s11)
    print("seg11 after :", s11)

    v557save.write_segments(a.out, header, segs)
    h2, segs2 = v557save.read_segments(a.out)
    ok = all(segs2[i] == segs[i] for i in range(14))
    print("roundtrip ok:", ok, "size:", os.path.getsize(a.out))


if __name__ == "__main__":
    main()
