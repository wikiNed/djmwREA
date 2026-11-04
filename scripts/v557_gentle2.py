#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v557 温和版存档 v2：按用户指定数值（m09765）生成。

用户指定：钻石15000 / 肉300 / 木材矿石=仓库上限80% / 草丛刷新(9) / 洞穴体力60。
其余大数值字段保持 audit 底稿值（1e8 类已实测 30 分钟不掉、不触发钳制）。
**完全不动 seg11**（GuoQiTime 留 0，避开 37 天封号闸门）。

用法: python scripts/v557_gentle2.py <src> <out>
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
    past = now - 3600_000  # 1 小时前 → 草丛/杂蛋立即刷新
    changes = []

    def setk(i, obj, key, val):
        if obj.get(key) == val:
            return
        changes.append((i, key, obj.get(key), val))
        obj[key] = val

    # seg13：钻石 15000
    s13 = seg_json(segs, 13)
    setk(13, s13, "ZuanShi", 15000)
    seg_set(segs, 13, s13)

    # seg2：木材/矿石 = 底稿值(=仓库上限) × 80%
    s2 = seg_json(segs, 2)
    wood = int(s2.get("MuCaiShuLiang", 0) * 0.8)
    ore = int(s2.get("KuangShiShuLiang", 0) * 0.8)
    setk(2, s2, "MuCaiShuLiang", wood)
    setk(2, s2, "MuCaiShuLiang_LiXianKu", wood)
    setk(2, s2, "KuangShiShuLiang", ore)
    setk(2, s2, "KuangShiShuLiang_LiXianKu", ore)
    seg_set(segs, 2, s2)

    # seg6：肉 300；草丛立即刷新（最多 9 丛可用），今日抓宠清 0
    s6 = seg_json(segs, 6)
    setk(6, s6, "ChongWuSiLiao", 300)
    setk(6, s6, "CaoCongChongZhiTime", past)
    setk(6, s6, "DangTianZhuaChongShu", 0)
    seg_set(segs, 6, s6)

    # seg9：洞穴体力 60（宝石洞穴次数）
    s9 = seg_json(segs, 9)
    setk(9, s9, "DangQianTiLi", 60)
    seg_set(segs, 9, s9)

    # seg5 钥匙保持底稿值（游戏自己写出的稳定值）；seg11 完全不动

    print("改动 %d 项：" % len(changes))
    for i, k, old, new in changes:
        print("  seg%-2d %-26s %-14s -> %s" % (i, k, old, new))

    v557save.write_segments(a.out, header, segs)
    print("写出 %s (%d 字节)" % (a.out, os.path.getsize(a.out)))

    # 回读校验
    blob = open(a.out, "rb").read()
    h2, body = v557save.split_parts(blob)
    plain = v557save.decrypt_body(body).split(b"$")
    ok = h2 == v557save.make_header(len(body) * 2)
    b13 = seg_json(plain, 13)
    b9 = seg_json(plain, 9)
    b6 = seg_json(plain, 6)
    checks = [
        b13["ZuanShi"] == 15000,
        b9["DangQianTiLi"] == 60,
        b6["ChongWuSiLiao"] == 300,
        seg_json(plain, 11)["GuoQiTime"] == 0,
        len(plain) == 14,
    ]
    print("回读: header一致=%s ZuanShi=%s TiLi=%s Rou=%s GuoQiTime=%s 段数=%d"
          % (ok, b13["ZuanShi"], b9["DangQianTiLi"], b6["ChongWuSiLiao"],
             seg_json(plain, 11)["GuoQiTime"], len(plain)))
    print("校验: %s" % ("通过" if (ok and all(checks)) else "失败"))
    return 0 if (ok and all(checks)) else 1


if __name__ == "__main__":
    sys.exit(main())
