#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v557 资源/货币定值设置器。

- 人口、木材、矿石：满级 + 80% 库存
- 钻石恒 15000、肉恒 300
- 草丛冷却立即刷新（= 可抓次数 9）
- 宝石洞穴重置时间立即刷新（= 体力 60）

用法:
  python scripts/v557_setres.py <src> <out> [--no-tree]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import v557save  # noqa: E402

# ── 满级值：取官方满级模板 playerDate_03 的上限 ──
MAX_LEVEL = {
    "JiaYuanLevel": 240,
    "FaMuChangLevel": 299,
    "KuangShiChangLevel": 245,
}

# 人口：模板 03 的 FaMuChangRenKou=225 / KuangShiChangRenKou=245
MAX_RENKOU = {
    "JiaYuanRenKou": 240,
    "FaMuChangRenKou": 225,
    "KuangShiChangRenKou": 245,
}

# 库存：模板 03 的满仓值
MAX_STOCK = {
    "MuCaiShuLiang": 5364060,
    "KuangShiShuLiang": 3601500,
}

# ── 定值 ──
FIXED = {
    "ZuanShi": 15000,       # seg13 钻石
    "ChongWuSiLiao": 300,   # seg6 肉
}
STOCK_PCT = 0.80
CAO_CONG_REFRESH = 0        # 草丛冷却时间置 0 = 立即可抓
DONG_XUE_REFRESH = 0        # 洞穴重置时间置 0 = 体力立刻回满


def seg_json(segs, i):
    b = segs[i]
    return json.loads(b.decode("utf-8") if isinstance(b, bytes) else b)


def seg_set(segs, i, obj):
    segs[i] = json.dumps(obj, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--level", type=int, default=None,
                    help="覆盖家园/伐木场/矿石场等级（默认用模板满级）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    header, segs = v557save.read_segments(a.src)
    segs = list(segs)
    print("源: %s  (%d 段)" % (a.src, len(segs)))

    # ── seg2：家园 / 伐木场 / 矿石场 ──
    s2 = seg_json(segs, 2)
    for k, v in MAX_LEVEL.items():
        s2[k] = a.level if a.level is not None else v
    for k, v in MAX_RENKOU.items():
        s2[k] = v
    for k, v in MAX_STOCK.items():
        s2[k] = int(v * STOCK_PCT)
        print("  %s = %d (满仓 %d × %.0f%%)" % (k, s2[k], v, STOCK_PCT * 100))
    # 离线库存也给同样数值，避免一上线就被清零
    s2["MuCaiShuLiang_LiXianKu"] = s2["MuCaiShuLiang"]
    s2["KuangShiShuLiang_LiXianKu"] = s2["KuangShiShuLiang"]
    seg_set(segs, 2, s2)
    print("seg2: 等级=%s 人口=%s"
          % ({k: s2[k] for k in MAX_LEVEL}, {k: s2[k] for k in MAX_RENKOU}))

    # ── seg6：肉 + 草丛冷却 ──
    s6 = seg_json(segs, 6)
    s6["ChongWuSiLiao"] = FIXED["ChongWuSiLiao"]
    s6["CaoCongChongZhiTime"] = CAO_CONG_REFRESH
    if not s6.get("DianIsOpen"):
        s6["DianIsOpen"] = [1]
    seg_set(segs, 6, s6)
    print("seg6: 肉=%d 草丛冷却=%d DianIsOpen=%s"
          % (s6["ChongWuSiLiao"], s6["CaoCongChongZhiTime"], s6["DianIsOpen"]))

    # ── seg9：洞穴重置 ──
    s9 = seg_json(segs, 9)
    s9["ChongZhiTime"] = DONG_XUE_REFRESH
    seg_set(segs, 9, s9)
    print("seg9: 洞穴重置时间=%d (当前层=%d)"
          % (s9["ChongZhiTime"], s9.get("DangQianCengJi", 0)))

    # ── seg13：钻石 ──
    s13 = seg_json(segs, 13)
    s13["ZuanShi"] = FIXED["ZuanShi"]
    seg_set(segs, 13, s13)
    print("seg13: 钻石=%d" % s13["ZuanShi"])

    if a.dry_run:
        print("\n--dry-run：未写文件")
        return 0

    v557save.write_segments(a.out, header, segs)
    print("\n写出 %s (%d 字节)"
          % (a.out, os.path.getsize(a.out)))

    # 回读校验
    _h, back = v557save.read_segments(a.out)
    b2 = seg_json(back, 2)
    b6 = seg_json(back, 6)
    b9 = seg_json(back, 9)
    b13 = seg_json(back, 13)
    ok = (b2["JiaYuanLevel"] == s2["JiaYuanLevel"]
          and b2["MuCaiShuLiang"] == s2["MuCaiShuLiang"]
          and b6["ChongWuSiLiao"] == FIXED["ChongWuSiLiao"]
          and b13["ZuanShi"] == FIXED["ZuanShi"])
    print("回读校验: %s" % ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
