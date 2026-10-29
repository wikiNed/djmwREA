#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用满级模板 playerDate_03 的 85 只宠物整体替换存档的宠物段。

数据来源
========
``data.unity3d`` 里的 TextAsset ``playerDate_03``（path_id=161，104886 字节）
是官方满级（TapLevel=60）存档模板，其中 ``seg6.SuoYouChongWuDate`` 有
85 条宠物，``ChongWuID`` 连续 0..84，每条 8 个字段都是非零真实值：

    ChongWuID / ChongWuLevel / ChongWuJinHua / ChongWuJinJie
    ChongWuYongJiu_HP / ChongWuYongJiu_Damage / IsXieDai / IsMaoXian

之前 ``fix_pets.py`` 只写 ID/Level/IsMaoXian/IsXieDai，四个字段为 0，
游戏 UI 因此显示「未知型 / 等级未知 / 进化未知 / 英雄体力+未知」。

本脚本
======
以模板为骨架，按 ``--jin-hua`` / ``--jin-jie`` / ``--level`` 统一改写
进化阶数、等级与属性，``IsMaoXian = -1``（已拥有），
``IsXieDai`` 只保留 ``--equip`` 指定的那一只。

用法
====
    python scripts/pet_from_template.py --in work/live/SaveFile_rich.es3 \\
                                       --out work/live/SaveFile_pets_all.es3
"""
import argparse
import json
import sys
from pathlib import Path

from Crypto.Util.Padding import pad

import paths
import savedit
from es3save import AES, ITERATIONS, KEY_LEN, PASSWORD, PBKDF2, SHA1, des_encrypt, read_save
from unlock_progress import find_slot, rebuild_bucket, split_l1

TEMPLATE = paths.REPO / "work" / "textassets" / "ta_161_104886.bin"

# 各 JinHua 档位的参考属性上限（取自模板里 JinJie=10 的最大值）
# JinHua -> (HP, Damage)
TIER_MAX = {
    1: (400, 500),
    2: (500, 600),
    3: (435600, 277200),
    4: (1755000, 1599750),
}


def load_segs(from_file):
    """读 .es3 -> 14 段 dict。"""
    parts = read_save(str(from_file))
    if isinstance(parts, (list, tuple)):
        text = "$".join(p.decode("utf-8") if isinstance(p, bytes) else p for p in parts)
    else:
        text = parts.decode("utf-8") if isinstance(parts, bytes) else parts
    return savedit.load(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="用满级模板整体替换宠物段")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--level", type=int, default=60, help="统一等级（默认 60）")
    ap.add_argument("--jin-hua", type=int, default=4, help="统一进化阶（默认 4 满阶）")
    ap.add_argument("--jin-jie", type=int, default=10, help="统一阶级（默认 10 满阶）")
    ap.add_argument("--equip", type=int, default=0, help="出战宠物 ChongWuID（默认 0）")
    ap.add_argument("--keep-stats", action="store_true",
                    help="保留模板原始 HP/Damage，不按档位拉满")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    a = ap.parse_args(argv)

    tpl_text = TEMPLATE.read_text(encoding="utf-8", errors="replace")
    tpl = savedit.load(tpl_text)
    tpl_pets = tpl[6]["SuoYouChongWuDate"]
    print("模板 %d 只宠物，ID %d..%d" % (
        len(tpl_pets), tpl_pets[0]["ChongWuID"], tpl_pets[-1]["ChongWuID"]))

    hp, dmg = TIER_MAX.get(a.jin_hua, (0, 0))

    new_pets = []
    for p in tpl_pets:
        e = dict(p)
        e["ChongWuLevel"] = a.level
        e["ChongWuJinHua"] = a.jin_hua
        e["ChongWuJinJie"] = a.jin_jie
        if not a.keep_stats:
            # 按档位给出上限值，个体差异用 ID 做小幅抖动（±10%）
            k = 0.90 + (e["ChongWuID"] % 21) / 100.0
            e["ChongWuYongJiu_HP"] = int(hp * k)
            e["ChongWuYongJiu_Damage"] = int(dmg * k)
        e["IsXieDai"] = 1 if e["ChongWuID"] == a.equip else 0
        e["IsMaoXian"] = -1
        new_pets.append(e)

    pre = load_segs(a.inp)
    print("输入存档宠物 %d 条" % len(pre[6]["SuoYouChongWuDate"]))
    pre[6]["SuoYouChongWuDate"] = new_pets
    pre[6]["ChongWuIsZiDongJiNeng"] = 1
    pre[6]["DianIsOpen"] = [1]

    print()
    print("%-4s %-4s %-7s %-6s %-12s %-12s %-6s" % (
        "ID", "Lv", "JinHua", "JinJie", "HP", "Dmg", "XieDai"))
    for e in new_pets[:5] + new_pets[-3:]:
        print("%-4d %-4d %-7d %-6d %-12d %-12d %-6d" % (
            e["ChongWuID"], e["ChongWuLevel"], e["ChongWuJinHua"],
            e["ChongWuJinJie"], e["ChongWuYongJiu_HP"],
            e["ChongWuYongJiu_Damage"], e["IsXieDai"]))
    print("... 共 %d 只" % len(new_pets))

    if a.dry_run:
        print("\n--dry-run：不写文件")
        return 0

    blob = Path(a.inp).read_bytes()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1

    plain = savedit.dump(pre).encode("utf-8")
    hexstr = des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = PBKDF2(PASSWORD.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    new_blob = salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(inner, 16))
    Path(a.out).write_bytes(new_blob)
    print("\n输出 %s (%d 字节)" % (a.out, len(new_blob)))

    back = load_segs(a.out)
    bp = back[6]["SuoYouChongWuDate"]
    ok = (len(bp) == len(new_pets)
          and bp[0]["ChongWuJinHua"] == a.jin_hua
          and bp[-1]["ChongWuID"] == new_pets[-1]["ChongWuID"])
    print("回读自检: %s（%d 只）" % ("通过" if ok else "失败", len(bp)))
    print("  首条 = %s" % json.dumps(bp[0], ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
