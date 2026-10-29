#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补充资源 —— 加钻石、肉、进化石，并解锁草丛/宠物点。

背景（2026-10-29 14:30）
========================
抓宠物消耗：手动引导 1 次 = 10 肉；一键引导 = 25 肉 + 15 钻石。
当前存档 ``ZuanShi = 11``、``ChongWuSiLiao = 9924``，用户反馈「钻石和草丛都不够了」。

草丛相关字段（seg6）：
    CaoCongChongZhiTime  ulong  草丛重置时间戳（毫秒）
    DianIsOpen           uint[] 宠物点开启数组
    ZaDanChongZhiTime    ulong  杂蛋重置时间戳

**不触碰 SuoYouChongWuDate**，让游戏的宠物状态保持原样，避免再次打乱。

用法
====
    python scripts/give_resources.py --in work/live/SaveFile_cur.es3 \\
                                     --out work/live/SaveFile_rich.es3
"""
import argparse
import sys

from Crypto.Util.Padding import pad

import savedit
from es3save import AES, ITERATIONS, KEY_LEN, PASSWORD, PBKDF2, SHA1, des_encrypt, read_save
from unlock_progress import find_slot, rebuild_bucket, split_l1


def main(argv=None):
    ap = argparse.ArgumentParser(description="补充钻石/肉/进化石并解锁草丛")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--zhuanshi", type=int, default=9999999, help="钻石数量")
    ap.add_argument("--siliao", type=int, default=99999, help="肉（宠物饲料）数量")
    ap.add_argument("--jinhua", type=int, default=9999, help="六种进化石数量")
    ap.add_argument("--cao-cong", type=int, default=0,
                    help="草丛重置时间（0 = 立即刷新）")
    a = ap.parse_args(argv)

    blob = open(a.inp, "rb").read()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1

    text = read_save(a.inp).decode("utf-8")
    segs = savedit.load(text)

    old_z = segs[13].get("ZuanShi")
    segs[13]["ZuanShi"] = a.zhuanshi

    pet = segs[6]
    old_s = pet.get("ChongWuSiLiao")
    pet["ChongWuSiLiao"] = a.siliao
    pet["CaoCongChongZhiTime"] = a.cao_cong
    pet["ZaDanChongZhiTime"] = a.cao_cong
    # 宠物点全部开启
    n = len(pet.get("DianIsOpen") or [0])
    pet["DianIsOpen"] = [1] * max(n, 1)

    for k in ("JinHuaShi_Feng", "JinHuaShi_Huo", "JinHuaShi_Shui",
              "JinHuaShi_Di", "JinHuaShi_Guang", "JinHuaShi_An"):
        pet[k] = a.jinhua

    print("钻石 ZuanShi      : %r -> %d" % (old_z, a.zhuanshi))
    print("肉   ChongWuSiLiao: %r -> %d" % (old_s, a.siliao))
    print("进化石 x6         : -> %d" % a.jinhua)
    print("草丛重置时间      : -> %d" % a.cao_cong)
    print("宠物数组          : 保持原样（%d 条）" % len(pet["SuoYouChongWuDate"]))

    plain = savedit.dump(segs).encode("utf-8")
    hexstr = des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = PBKDF2(PASSWORD.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    new_blob = salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(inner, 16))
    with open(a.out, "wb") as f:
        f.write(new_blob)
    print("输出 %s (%d 字节)" % (a.out, len(new_blob)))

    back = savedit.load(read_save(a.out).decode("utf-8"))
    ok = (back[13].get("ZuanShi") == a.zhuanshi
          and back[6].get("ChongWuSiLiao") == a.siliao
          and len(back[6].get("SuoYouChongWuDate", [])) == len(pet["SuoYouChongWuDate"]))
    print("回读自检: %s" % ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
