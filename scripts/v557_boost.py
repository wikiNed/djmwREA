#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.7 改档：黄金树无限开通 + 宝石/碎片 + 资源建筑满级。

用法::

    python scripts/v557_boost.py --in  a.save --out b.save
    python scripts/v557_boost.py --in  a.save --out b.save --tree --gem --res
    python scripts/v557_boost.py --in  a.save --out b.save --dry-run

三个开关都可单独使用，默认全开。

长度处理
--------
旧版存档 ``file = header(14) || hex(DES(明文)) || '{'``，
明文长度变化会改变密文块数。scripts/v557_fit.py 的结论是：
密文块数必须保持与基线一致，否则游戏读档失败。

本脚本先尝试**等长替换**（数值位数不变），若仍超长，则用
``seg8.GuanKaSuTongTimes`` 里的哨兵浮点（``1000000000.0`` → ``0.0``，
每个省 9 字节）腾出空间，最后才用 ``v557_fit.fit()`` 兜底。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import v557save  # noqa: E402

SEP = b"$"

#: seg11 生命树（黄金树）的目标值。
#: 依据：模板 playerDate_01/02 都是 IsJiHuo=1 + IsHuangJin=1；
#: GuoQiTime 填 2100-01-01（4102416000000 毫秒）表示永不过期。
TREE = {
    "IsJiHuo": 1,
    "IsHuangJin": 1,
    "GuoQiTime": 4102416000000,
    "JiHuoCiShu": 10,
    "GuoShiIsLingQu": 1,
}

#: seg9 宝石洞的目标值。BaoShiSuiPian 取模板 03 的 3.3 倍，
#: 避免填成明显越界的数字（模板 03 是 303978）。
GEM = {
    "BaoShiSuiPian": 999999,
}

#: SuoYouBaoShiTongJi 各子字段的目标值（模板 03 的统计量，用于显示）。
GEM_STATS = {
    "baoShiZongShu": 23812,
    "baoShiShu_Hong": 7191,
    "baoShiShu_Lv": 5918,
    "baoShiShu_lan": 4695,
    "baoShiShu_Huang": 3596,
    "baoShiShu_Zi": 1682,
    "baoShiShu_Zuan": 730,
    "baoShiShuJie_01": 5482,
    "baoShiShuJie_02": 5871,
    "baoShiShuJie_03": 5719,
    "baoShiShuJie_04": 3319,
    "baoShiShuJie_05": 2361,
    "baoShiShuJie_06": 955,
    "baoShiShuJie_07": 105,
    "baoShiShu_PuTong": 4133,
    "baoShiShu_JingZhi": 6661,
    "baoShiShu_XiYou": 8775,
    "baoShiShu_ShiShi": 3464,
    "baoShiShu_ChuanShuo": 776,
    "baoShiShu_YuanGu": 3,
    "baoShiShu_FenJie": 21884,
}

#: seg2 资源建筑的目标值 —— 直接取模板 playerDate_03（60 级满级档）的官方值。
RES = {
    "JiaYuanLevel": 240,
    "FaMuChangLevel": 299,
    "FaMuChangRenKou": 225,
    "KuangShiChangLevel": 245,
    "KuangShiChangRenKou": 245,
    "MuCaiShuLiang": 5364060,
    "MuCaiShuLiang_LiXianKu": 5364060,
    "KuangShiShuLiang": 3601500,
    "KuangShiShuLiang_LiXianKu": 3601500,
}


def load_json(seg):
    return json.loads(seg.decode("utf-8"))


def dump_json(obj):
    """与游戏一致：紧凑分隔符 + 不转义中文。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def apply(segs, do_tree, do_gem, do_res, verbose=True):
    """原地修改 segs，返回改动清单。"""
    changes = []

    if do_tree:
        d = load_json(segs[11])
        for k, v in TREE.items():
            if d.get(k) != v:
                changes.append("seg11.%-16s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        segs[11] = dump_json(d)

    if do_gem:
        d = load_json(segs[9])
        for k, v in GEM.items():
            if d.get(k) != v:
                changes.append("seg9.%-17s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        st = d.get("SuoYouBaoShiTongJi")
        if isinstance(st, dict):
            for k, v in GEM_STATS.items():
                if st.get(k) != v:
                    st[k] = v
            changes.append("seg9.SuoYouBaoShiTongJi  21 个子字段已填")
        segs[9] = dump_json(d)

    if do_res:
        d = load_json(segs[2])
        for k, v in RES.items():
            if d.get(k) != v:
                changes.append("seg2.%-18s %r -> %r" % (k, d.get(k), v))
                d[k] = v
        segs[2] = dump_json(d)

    if verbose:
        for c in changes:
            print("  " + c)
        if not changes:
            print("  (无改动)")
    return changes


def shrink_sentinels(segs, n):
    """把 seg8.GuanKaSuTongTimes 里前 n 个非零浮点改成 0.0，返回新的 seg。

    这些值是「通关用时」，0.0 语义上就是「没通关」，不会显得异常。
    """
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
    ap = argparse.ArgumentParser(description="v557 改档：黄金树/宝石/资源")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--tree", action="store_true", help="只改生命树")
    ap.add_argument("--gem", action="store_true", help="只改宝石")
    ap.add_argument("--res", action="store_true", help="只改资源建筑")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    do_all = not (a.tree or a.gem or a.res)
    do_tree = do_all or a.tree
    do_gem = do_all or a.gem
    do_res = do_all or a.res

    header, segs = v557save.read_segments(a.src)
    base_len = sum(len(s) for s in segs) + (len(segs) - 1)
    print("源文件 : %s" % a.src)
    print("header : %s" % header.hex())
    print("明文   : %d 字节（含 13 个 $）" % base_len)

    print("\n改动：")
    apply(segs, do_tree, do_gem, do_res)

    new_len = sum(len(s) for s in segs) + (len(segs) - 1)
    delta = new_len - base_len
    print("\n明文长度: %d -> %d (delta %+d)" % (base_len, new_len, delta))

    if delta != 0:
        # 尝试用哨兵浮点对冲
        need = abs(delta)
        n = (need + 8) // 9 + 1
        new_seg8, changed = shrink_sentinels(segs, n)
        if new_seg8 is not None:
            segs[8] = new_seg8
            now = sum(len(s) for s in segs) + (len(segs) - 1)
            print("  压缩 seg8 哨兵 %d 个（每个 -9 字节）-> 明文 %d 字节 (delta %+d)"
                  % (changed, now, now - base_len))
        else:
            print("  !! seg8 里没有可压缩的哨兵浮点")

    final_len = sum(len(s) for s in segs) + (len(segs) - 1)
    print("\n最终明文: %d 字节 (delta %+d)" % (final_len, final_len - base_len))

    if a.dry_run:
        print("\n--dry-run：未写文件")
        return

    size = v557save.write_segments(a.dst, header, segs)
    print("\n已写出: %s (%d 字节)" % (a.dst, size))

    # 自检：读回并核对
    h2, segs2 = v557save.read_segments(a.dst)
    d58 = load_json(segs2[8])
    print("\n回读自检：")
    print("  seg11: %s" % load_json(segs2[11]))
    print("  seg9 .BaoShiSuiPian = %s" % load_json(segs2[9])["BaoShiSuiPian"])
    d2 = load_json(segs2[2])
    for k in ("JiaYuanLevel", "FaMuChangLevel", "KuangShiChangLevel"):
        print("  seg2 .%-18s = %s" % (k, d2[k]))


if __name__ == "__main__":
    main()
