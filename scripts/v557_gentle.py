#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.7 改档「温和版」：数值全部落在官方模板出现过的范围内。

与 scripts/v557_boost.py（激进版）的区别
----------------------------------------
激进版把资源拉到模板 03 的满级值（家园 240 / 伐木 299 / 矿石 245、
库存 536 万），并给生命树设了 2100 年的过期时间，实测**触发了封号**。

温和版每个字段都留在模板 01/02 出现过的区间里：

    生命树     GuoQiTime 只延到当年年底，JiHuoCiShu=1
    宝石碎片   30000（模板 03 是 303978，3 万很普通）
    宝石统计   只填 3 个主色，不伪造 21 项全表
    家园/伐木/矿石等级   68 / 92 / 76（模板 01 与 02 的值）
    库存       不超过模板 01 的 53.87 万

用法::

    python scripts/v557_gentle.py --in a.save --out b.save
    python scripts/v557_gentle.py --in a.save --out b.save --dry-run
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import v557save  # noqa: E402

#: 生命树（黄金树）—— 温和值。
#: GuoQiTime 由 main() 按「当年 12-31 23:59:59」动态计算，避免写死年份。
TREE_GENTLE = {
    "IsJiHuo": 1,
    "IsHuangJin": 1,
    "JiHuoCiShu": 1,
}

#: 宝石洞 —— BaoShiSuiPian 取 3 万（模板 03 是 303978，这个数字不显眼）。
GEM_GENTLE = {
    "BaoShiSuiPian": 30000,
}

#: 宝石统计只填总量与三种主色，其余保持 0（不伪造完整统计）。
GEM_STATS_GENTLE = {
    "baoShiZongShu": 300,
    "baoShiShu_Hong": 100,
    "baoShiShu_Lv": 100,
    "baoShiShu_lan": 100,
}

#: 资源建筑 —— 取模板 01（36 级档）与 02（56 级档）的实际值。
#: 库存压到模板 01 的量级，避免 500 万这种远超正常进度的数字。
RES_GENTLE = {
    "JiaYuanLevel": 68,
    "FaMuChangLevel": 92,
    "FaMuChangRenKou": 50,
    "KuangShiChangLevel": 76,
    "KuangShiChangRenKou": 76,
    "MuCaiShuLiang": 507840,
    "MuCaiShuLiang_LiXianKu": 354400,
    "KuangShiShuLiang": 346560,
    "KuangShiShuLiang_LiXianKu": 238523,
}


def load_json(seg):
    return json.loads(seg.decode("utf-8"))


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def year_end_ms(now=None):
    """当年 12-31 23:59:59 的毫秒时间戳（本地时区）。"""
    now = now or datetime.datetime.now()
    end = datetime.datetime(now.year, 12, 31, 23, 59, 59)
    return int(end.timestamp() * 1000)


def shrink_sentinels(segs, n):
    """压缩 seg8 的通关时间浮点，为明文长度变化腾空间。"""
    d = load_json(segs[8])
    arr = d.get("GuanKaSuTongTimes")
    if not isinstance(arr, list):
        return None, 0
    changed = 0
    for item in arr:
        if changed >= n:
            break
        st = item.get("SuTongTimes")
        if not isinstance(st, list):
            continue
        for i, v in enumerate(st):
            if changed >= n:
                break
            if isinstance(v, float) and v != 0.0:
                st[i] = 0.0
                changed += 1
    if not changed:
        return None, 0
    return dump_json(d), changed


def main():
    ap = argparse.ArgumentParser(description="v557 温和版改档")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-tree", action="store_true")
    ap.add_argument("--no-gem", action="store_true")
    ap.add_argument("--no-res", action="store_true")
    a = ap.parse_args()

    header, segs = v557save.read_segments(a.src)
    base_len = sum(len(s) for s in segs) + (len(segs) - 1)
    expires = year_end_ms()

    print("源文件 : %s" % a.src)
    print("header : %s" % header.hex())
    print("明文   : %d 字节" % base_len)
    print("过期时间: %d（本年 12-31 23:59:59）" % expires)

    changes = []

    if not a.no_tree:
        d = load_json(segs[11])
        targets = dict(TREE_GENTLE)
        targets["GuoQiTime"] = expires
        for k, v in targets.items():
            if d.get(k) != v:
                changes.append("seg11.%-16s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        segs[11] = dump_json(d)

    if not a.no_gem:
        d = load_json(segs[9])
        for k, v in GEM_GENTLE.items():
            if d.get(k) != v:
                changes.append("seg9.%-17s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        st = d.get("SuoYouBaoShiTongJi")
        if isinstance(st, dict):
            for k, v in GEM_STATS_GENTLE.items():
                st[k] = v
            changes.append("seg9.SuoYouBaoShiTongJi  4 项已填（不伪造全表）")
        segs[9] = dump_json(d)

    if not a.no_res:
        d = load_json(segs[2])
        for k, v in RES_GENTLE.items():
            if d.get(k) != v:
                changes.append("seg2.%-18s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        segs[2] = dump_json(d)

    print("\n改动：")
    for c in changes:
        print("  " + c)
    if not changes:
        print("  (无改动)")

    new_len = sum(len(s) for s in segs) + (len(segs) - 1)
    print("\n明文长度: %d -> %d (delta %+d)" % (base_len, new_len, new_len - base_len))

    if new_len != base_len:
        need = abs(new_len - base_len)
        n = (need + 8) // 9 + 1
        new_seg8, changed = shrink_sentinels(segs, n)
        if new_seg8 is not None:
            segs[8] = new_seg8
            now = sum(len(s) for s in segs) + (len(segs) - 1)
            print("  压缩 seg8 哨兵 %d 个 -> 明文 %d 字节 (delta %+d)"
                  % (changed, now, now - base_len))

    final_len = sum(len(s) for s in segs) + (len(segs) - 1)
    print("\n最终明文: %d 字节 (delta %+d)" % (final_len, final_len - base_len))

    if a.dry_run:
        print("\n--dry-run：未写文件")
        return

    size = v557save.write_segments(a.dst, header, segs)
    print("\n已写出: %s (%d 字节)" % (a.dst, size))

    h2, segs2 = v557save.read_segments(a.dst)
    print("\n回读自检：")
    print("  seg11 = %s" % load_json(segs2[11]))
    print("  seg9.BaoShiSuiPian = %s" % load_json(segs2[9])["BaoShiSuiPian"])
    d2 = load_json(segs2[2])
    for k in ("JiaYuanLevel", "FaMuChangLevel", "KuangShiChangLevel"):
        print("  seg2.%-18s = %s" % (k, d2[k]))


if __name__ == "__main__":
    main()
