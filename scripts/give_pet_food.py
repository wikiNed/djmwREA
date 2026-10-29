#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给宠物系统补资源 —— 肉（宠物饲料）、宠物点开启状态。

背景
====
2026-10-29 实测：地图上草丛点开「发现同伴」面板后，手动引导需要 10 个肉，
一键引导需要 25 肉 + 15 钻石。存档里 ``seg6.ChongWuSiLiao`` 当时只有 7，
所以抓不了宠物。同段的 ``DianIsOpen`` 是宠物点开启数组，``[0]`` 表示未开启。

字段依据（dump.cs / IL2CPP）
============================
    ChongWuDate                      // TypeDefIndex: 3066
    ChongWuManager                   // TypeDefIndex: 2939
        private const string MiMa = "HYTGBFRO";
        KaiShiZhuaPu()  ... 抓宠物小游戏入口
    Date_ChongWu                     // TypeDefIndex: 3065

存档段结构（savedit，14 段）
============================
    seg6 = 宠物段，字段：
        SuoYouChongWuDate      : 90 只宠物的数组
        ChongWuSiLiao          : 肉/饲料数量     <= 本脚本修改
        DianIsOpen             : 宠物点开启数组  <= 本脚本修改
        CaoCongChongZhiTime    : 草丛重置时间
        ZhuaChongZongShu       : 累计抓取数
        DangTianZhuaChongShu   : 当日抓取数
        JinHuaShi_*            : 六种进化石数量

约束（同 unlock_progress.py，踩过的坑）
=====================================
1. 必须复用原档 salt / iv / 槽名 / 桶结构
2. 内层 DES 必须 PKCS7 填充（es3save.des_encrypt 已实现）
3. 桶条目顺序照抄基准档（游戏回写的桶没有 _Key，有 Hero01ShuChu_Key）

用法
====
    python scripts/give_pet_food.py --in work/live/SaveFile_lv21.es3 \\
                                    --out work/live/SaveFile_food.es3 \\
                                    [--food 9999] [--stones 999]
"""
import argparse
import sys

from unlock_progress import find_slot, rebuild_bucket, split_l1

import savedit
from es3save import AES, ITERATIONS, KEY_LEN, PASSWORD, PBKDF2, SHA1, des_encrypt, read_save
from Crypto.Util.Padding import pad

# 六种进化石
STONE_KEYS = (
    "JinHuaShi_Feng", "JinHuaShi_Huo", "JinHuaShi_Shui",
    "JinHuaShi_Di", "JinHuaShi_Guang", "JinHuaShi_An",
)


def main(argv=None):
    ap = argparse.ArgumentParser(description="给宠物系统补肉/开启宠物点")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--food", type=int, default=9999, help="肉数量（默认 9999）")
    ap.add_argument("--stones", type=int, default=999, help="每种进化石数量（默认 999）")
    a = ap.parse_args(argv)

    blob = open(a.inp, "rb").read()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1
    print("基准 %s  (%d 字节, layer1 %d)" % (a.inp, len(blob), len(layer1)))
    print("  slot : %s" % slot)

    text = read_save(a.inp).decode("utf-8")
    segs = savedit.load(text)
    pet = segs[6]

    old_food = pet.get("ChongWuSiLiao")
    old_open = pet.get("DianIsOpen")
    pet["ChongWuSiLiao"] = a.food
    # 宠物点数组：保持长度，全部置 1 表示已开启
    if isinstance(old_open, list) and old_open:
        pet["DianIsOpen"] = [1] * len(old_open)
    else:
        pet["DianIsOpen"] = [1]
    for k in STONE_KEYS:
        if k in pet:
            pet[k] = a.stones

    print("  ChongWuSiLiao %r -> %d" % (old_food, a.food))
    print("  DianIsOpen    %r -> %r" % (old_open, pet["DianIsOpen"]))
    print("  进化石        -> %d x%d" % (a.stones, len(STONE_KEYS)))

    plain = savedit.dump(segs).encode("utf-8")
    hexstr = des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = PBKDF2(PASSWORD.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    new_blob = salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(inner, 16))
    with open(a.out, "wb") as f:
        f.write(new_blob)
    print("输出 %s  (%d 字节, 明文 %d 字节)" % (a.out, len(new_blob), len(plain)))

    back = savedit.load(read_save(a.out).decode("utf-8"))
    ok = (back[6].get("ChongWuSiLiao") == a.food
          and back[9].get("BaoShiSuiPian") == segs[9].get("BaoShiSuiPian")
          and back[8].get("GuanKaLevel") == segs[8].get("GuanKaLevel")
          and len(back[6].get("SuoYouChongWuDate", [])) == 90)
    print("回读自检: %s" % ("通过" if ok else "失败"))
    print("  ChongWuSiLiao = %r" % back[6].get("ChongWuSiLiao"))
    print("  DianIsOpen    = %r" % back[6].get("DianIsOpen"))
    print("  GuanKaLevel   = %r" % back[8].get("GuanKaLevel"))
    print("  BaoShiSuiPian = %r" % back[9].get("BaoShiSuiPian"))
    print("  宠物数        = %d" % len(back[6].get("SuoYouChongWuDate", [])))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
