#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v557 超量填充：把资源/货币填到游戏消耗不完的量。

不修改 APK，靠「数值远大于消耗」达到「保持不变」的效果。

设计原则（重要）：
  * 所有数值 **保持 < 2^31**，避免代码里 int/uint 混用时溢出变负。
  * 不动 seg11（ShengMingShu）—— GuoQiTime 留 0，绕开 37 天封号闸门。
  * 各种「每日重置时间」设为 now + 1 秒 → 读档即回满。

用法:
  python scripts/v557_overfill.py <src> <out>
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

# ── 超量值（全部 < 2^31）──
BIG = 100_000_000           # 1 亿：够用几十年，又不会溢成负数
BIG_ULONG = 100_000_000
MAX_LEVEL = {
    "JiaYuanLevel": 240,
    "FaMuChangLevel": 299,
    "KuangShiChangLevel": 245,
}
MAX_RENKOU = {
    "JiaYuanRenKou": 240,
    "FaMuChangRenKou": 225,
    "KuangShiChangRenKou": 245,
}
REFRESH_DELAY_MS = 1000     # 「立即回满」


def seg_json(segs, i):
    b = segs[i]
    return json.loads(b.decode("utf-8") if isinstance(b, bytes) else b)


def seg_set(segs, i, obj):
    segs[i] = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def now_ms():
    return int(time.time() * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()

    header, segs = v557save.read_segments(a.src)
    segs = list(segs)
    t = now_ms()
    refresh = t + REFRESH_DELAY_MS
    changes = []
    print("源: %s  (%d 段)   现在=%d" % (a.src, len(segs), t))

    def setk(seg, i, key, val):
        if seg.get(key) == val:
            return
        changes.append((i, key, seg.get(key), val))
        seg[key] = val

    # ── seg2：生产等级 + 人口 + 库存 ──
    s2 = seg_json(segs, 2)
    for k, v in MAX_LEVEL.items():
        setk(s2, 2, k, v)
    for k, v in MAX_RENKOU.items():
        setk(s2, 2, k, v)
    setk(s2, 2, "MuCaiShuLiang", BIG_ULONG)
    setk(s2, 2, "MuCaiShuLiang_LiXianKu", BIG_ULONG)
    setk(s2, 2, "KuangShiShuLiang", BIG_ULONG)
    setk(s2, 2, "KuangShiShuLiang_LiXianKu", BIG_ULONG)
    setk(s2, 2, "PaiQianCiShu", BIG)          # 派遣次数
    setk(s2, 2, "ZiYuanLiXianTime", t)         # 防离线结算爆时间差
    seg_set(segs, 2, s2)

    # ── seg6：肉 + 草丛 + 蛋 ──
    s6 = seg_json(segs, 6)
    setk(s6, 6, "ChongWuSiLiao", BIG)          # uint 肉
    setk(s6, 6, "CaoCongChongZhiTime", refresh)  # 草丛立即刷新
    setk(s6, 6, "ZaDanChongZhiTime", refresh)    # 杂蛋立即刷新
    setk(s6, 6, "DangTianZhuaChongShu", 0)
    if not s6.get("DianIsOpen"):
        setk(s6, 6, "DianIsOpen", [1])
    for k in ("JinHuaShi_Feng", "JinHuaShi_Huo", "JinHuaShi_Shui",
              "JinHuaShi_Di", "JinHuaShi_Guang", "JinHuaShi_An"):
        setk(s6, 6, k, BIG)                    # 六种进化石
    seg_set(segs, 6, s6)

    # ── seg9：宝石洞穴（体力=次数 拉满，重置时间立即到期）──
    s9 = seg_json(segs, 9)
    setk(s9, 9, "DangQianTiLi", BIG)           # 洞穴次数
    setk(s9, 9, "ChongZhiTime", refresh)
    setk(s9, 9, "BaoShiSuiPian", BIG_ULONG)    # 宝石碎片
    seg_set(segs, 9, s9)

    # ── seg10：魔石库体力 ──
    s10 = seg_json(segs, 10)
    setk(s10, 10, "MoKuTiLi", BIG)
    setk(s10, 10, "MoShiShuLiang", BIG)
    setk(s10, 10, "MoWuSuiPian", BIG)
    setk(s10, 10, "TiLiShopKuCun", BIG)
    setk(s10, 10, "ChongZhiTime", refresh)
    seg_set(segs, 10, s10)

    # ── seg5 / seg7 / seg12：每日重置类 ──
    s5 = seg_json(segs, 5)
    setk(s5, 5, "DaoZeiYaoShi", BIG)
    setk(s5, 5, "ChongZhiTime", refresh)
    seg_set(segs, 5, s5)

    s7 = seg_json(segs, 7)
    setk(s7, 7, "ChongZhiTime", refresh)
    seg_set(segs, 7, s7)

    s12 = seg_json(segs, 12)
    for k in ("ChongZhiBaMaoTime", "ChongZhiWaWaJiTime", "ChongZhiBaYaTime",
              "CBX_CZT", "TanPai_CZT"):
        setk(s12, 12, k, refresh)
    seg_set(segs, 12, s12)

    # ── seg13：钻石 + 看广告/紧急任务次数 ──
    s13 = seg_json(segs, 13)
    setk(s13, 13, "ZuanShi", BIG)              # uint 钻石
    setk(s13, 13, "KanGuangGaoCiShu", BIG)
    setk(s13, 13, "DangQianGuangGaoCiShu", BIG)
    setk(s13, 13, "ChongZhiGuangGaoTime", refresh)
    setk(s13, 13, "ChongZhiJinJiRenWuTime", refresh)
    seg_set(segs, 13, s13)

    # ── seg11 明确不动（GuoQiTime 保持 0 以避开 37 天闸门）──

    print("\n改动 %d 项：" % len(changes))
    for i, k, old, new in changes:
        print("  seg%-2d %-26s %-12s -> %s" % (i, k, old, new))

    v557save.write_segments(a.out, header, segs)
    print("\n写出 %s (%d 字节)" % (a.out, os.path.getsize(a.out)))

    # 回读校验
    blob = open(a.out, "rb").read()
    h2, body = v557save.split_parts(blob)
    back = v557save.decrypt_body(body).split(b"$")
    ok = True
    print("回读 header: %s  (len=%d, 密文=%d, 明文=%d)"
          % (h2.hex(), len(h2), len(body), sum(len(x) for x in back) + len(back) - 1))
    if h2 != v557save.make_header(len(body) * 2):
        print("  !! header 与公式不一致")
        ok = False
    b13 = seg_json(back, 13)
    b9 = seg_json(back, 9)
    if b13["ZuanShi"] != BIG or b9["DangQianTiLi"] != BIG:
        print("  !! 字段回读不符: ZuanShi=%s TiLi=%s" % (b13["ZuanShi"], b9["DangQianTiLi"]))
        ok = False
    if seg_json(back, 11)["GuoQiTime"] != 0:
        print("  !! seg11 GuoQiTime 被改动")
        ok = False
    print("回读校验: %s" % ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())