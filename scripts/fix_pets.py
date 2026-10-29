#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按满级模板 playerDate_03 修正宠物数组，补齐全部字段。

背景（2026-10-29，关键突破）
==========================
存档里的 ``SuoYouChongWuDate`` 是 ``List<ChongWuDate>``，每条 8 个字段。
此前只写 ``ChongWuID`` / ``ChongWuLevel`` / ``IsMaoXian`` / ``IsXieDai``，
其余四个字段为 0，导致游戏「我的同伴」界面显示：

    同伴名称【未知型】  等级：未知  进化：未知  英雄体力 +未知  英雄攻击 +未知

从 ``data.unity3d`` 的 TextAsset ``playerDate_03``（满级 60 的官方存档模板）
取得权威取值，证明 4 个字段必须有非零值：

    {"ChongWuID":0,  "ChongWuLevel":20, "ChongWuJinHua":1, "ChongWuJinJie":10,
     "ChongWuYongJiu_HP":150, "ChongWuYongJiu_Damage":100, "IsXieDai":0, "IsMaoXian":-1}
    {"ChongWuID":75, "ChongWuLevel":45, "ChongWuJinHua":4, "ChongWuJinJie":1,
     "ChongWuYongJiu_HP":8271, "ChongWuYongJiu_Damage":21150, ...}

模板共 85 条（ID 0..84）。``IsMaoXian == -1`` 表示已拥有。

本脚本
======
默认从模板按 ID 复制四元组（JinHua/JinJie/HP/Damage），等级拉满，
``IsMaoXian = -1``（已拥有），``IsXieDai = 0``。这样每条都带真实配置值，
UI 应能显示名称、等级、进化与属性加成。

用法
====
    python scripts/fix_pets.py --in work/live/SaveFile_rich.es3 \\
                              --out work/live/SaveFile_pets_fixed.es3
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


def load_segs(from_file):
    """读 .es3 -> 14 段 dict（list 或 bytes 两种返回都兼容）。"""
    parts = read_save(str(from_file))
    if isinstance(parts, (list, tuple)):
        text = "$".join(p.decode("utf-8") if isinstance(p, bytes) else p for p in parts)
    else:
        text = parts.decode("utf-8") if isinstance(parts, bytes) else parts
    return savedit.load(text)


def load_template():
    """读满级模板，返回 {ChongWuID: 条目 dict}。"""
    text = TEMPLATE.read_text(encoding="utf-8", errors="replace")
    segs = savedit.load(text)
    pets = segs[6]["SuoYouChongWuDate"]
    return {p["ChongWuID"]: p for p in pets}, pets


def main(argv=None):
    ap = argparse.ArgumentParser(description="按满级模板补齐宠物四元组字段")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--level", type=int, default=60, help="宠物等级（默认 60）")
    ap.add_argument("--ids", default="", help="只处理这些 ID（逗号分隔，默认全部）")
    ap.add_argument("--keep-level", action="store_true", help="保留原等级，不统一拉满")
    ap.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    a = ap.parse_args(argv)

    tpl_by_id, tpl_list = load_template()
    print("模板宠物 %d 条，ID %d..%d" % (
        len(tpl_list), min(tpl_by_id), max(tpl_by_id)))

    segs = load_segs(a.inp)
    pets = segs[6]["SuoYouChongWuDate"]
    src_ids = [p.get("ChongWuID") for p in pets]
    print("输入宠物 %d 条，ID %r..%r" % (len(pets), src_ids[0], src_ids[-1]))

    want = None
    if a.ids:
        want = {int(x) for x in a.ids.split(",") if x.strip()}

    new_pets = []
    missing = []
    for p in pets:
        pid = p.get("ChongWuID")
        if want is not None and pid not in want:
            new_pets.append(p)
            continue
        t = tpl_by_id.get(pid)
        if t is None:
            # 模板里没有这个 ID：保持原样（避免写出未知组合）
            missing.append(pid)
            new_pets.append(p)
            continue
        e = dict(p)
        e["ChongWuJinHua"] = t["ChongWuJinHua"]
        e["ChongWuJinJie"] = t["ChongWuJinJie"]
        e["ChongWuYongJiu_HP"] = t["ChongWuYongJiu_HP"]
        e["ChongWuYongJiu_Damage"] = t["ChongWuYongJiu_Damage"]
        if not a.keep_level:
            e["ChongWuLevel"] = a.level
        e["IsXieDai"] = 0
        e["IsMaoXian"] = -1          # -1 = 已拥有
        new_pets.append(e)

    if missing:
        print("警告：模板里没有的 ID（保持原样）%r" % missing)

    segs[6]["SuoYouChongWuDate"] = new_pets
    # 模板里这两个开关与玩法相关，照抄可让「自动技能」等生效
    segs[6]["ChongWuIsZiDongJiNeng"] = 1

    print()
    print("%-4s %-5s %-5s %-6s %-8s %-10s %-10s" % (
        "ID", "Lv", "JinHua", "JinJie", "HP", "Dmg", "IsMaoXian"))
    for e in new_pets[:6]:
        print("%-4d %-5d %-5d %-6d %-8d %-10d %-10d" % (
            e["ChongWuID"], e["ChongWuLevel"], e["ChongWuJinHua"],
            e["ChongWuJinJie"], e["ChongWuYongJiu_HP"],
            e["ChongWuYongJiu_Damage"], e["IsMaoXian"]))
    print("... 共 %d 条" % len(new_pets))

    if a.dry_run:
        print("\n--dry-run：不写文件")
        return 0

    blob = Path(a.inp).read_bytes()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1

    plain = savedit.dump(segs).encode("utf-8")
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
          and bp[0]["ChongWuID"] == new_pets[0]["ChongWuID"]
          and bp[0]["ChongWuJinHua"] == new_pets[0]["ChongWuJinHua"])
    print("回读自检: %s" % ("通过" if ok else "失败"))
    print("  首条 = %s" % json.dumps(bp[0], ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
