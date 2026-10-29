#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解锁推进 —— 把关卡/家园进度改到足以打开各功能界面的程度。

背景
====
存档里三项修改（宝石碎片 / 黄金树 / 宠物等级）在 2026-10-29 已实测生效：
游戏读档后两次回写都保留了这些值，宝石碎片 88888 也在 UI 上拍到实证
（work/shots/baoshi2.png）。但「宠物列表」「生命之树」等界面本身还有
解锁门槛，档里 GuanKaLevel 只有 3，所以 UI 打不开、无法截图验收。

解锁门槛（反汇编，libil2cpp.so）
==============================
    PlayerDataModel.get_ChongWuIsJieSuo  @ 0x188C550（完整拆开，2026-10-29）
        ldr x0, [x19]             ; 静态单例
        ldr x8, [x0, #0xb8]       ; PlayerDataModel 数据对象
        ldr w8, [x8, #0x40]       ; = GuanKaLevel
        cmp w8, #0x14             ; 和 20 比
        cset w0, gt               ; 返回 (GuanKaLevel > 20)
        ret

        **门槛是 GuanKaLevel > 20，即至少 21 关。**
        早期从 0x1888534 的 ``cmp w22, #0xb / b.ge`` 误判为 ">= 11"，
        那条指令不在本 getter 里，判断作废。

    PlayerDataModel.get_GuanKaLevel       @ 0x1899C14
        ldr x0, [x19]             ; 静态单例
        ldr x8, [x0, #0xb8]       ; 数据对象
        ldr w0, [x8, #0x40]       ; 返回 GuanKaLevel
        ; 该字段来自存档 seg8["GuanKaLevel"]

存档 seg8["GuanKaSuTongTimes"] 是长度 61 的数组，每项
``{"SuTongTimes": [float, float]}``；故关卡总数约 61，21 关在合法范围内。
顺带把 seg2 的家园/伐木场/矿石场从 0 级升到 5 级 —— 它们同样是 0 级
导致地图上建筑点不开。

关键约束（踩过的坑）
====================
1. **必须复用原档的 salt / iv / 槽名 / 桶结构**。ES3 桶里的 string 槽名
   是 TapTap 防沉迷标识（形如 ``o74JUkh9jw==``），游戏用它认槽；换成别的
   名字就读到空档。
2. **内层 DES 必须 PKCS7 填充**。游戏走 CryptoStream.FlushFinalBlock()，
   填错会抛 ``CryptographicException: Bad PKCS7 padding. Invalid length 0.``
   然后卡在标题页。es3save.des_encrypt 已按 PKCS7 实现。
3. **桶结构照抄基准档**。2026-10-29 实测游戏回写的桶：没有 `_Key` 条目，
   首项就是 string 槽，且有 `Hero01ShuChu_Key`。这与 es3save.build_bucket
   里照抄更早原档的模板不同 —— 以游戏当前输出为准。
4. **savedit.dump 只改目标字段**，其余键原样保留（float 文本会轻微漂移，
   但实测不影响游戏读档）。

用法
====
    python scripts/unlock_progress.py --in work/live/SaveFile_now2.es3 \\
                                      --out work/live/SaveFile_unlock.es3 \\
                                      [--level 11] [--home-level 5]
"""
import argparse
import json
import sys

from Crypto.Util.Padding import pad

import savedit
from es3save import (
    AES, ITERATIONS, KEY_LEN, PASSWORD, PBKDF2, SHA1,
    des_encrypt, parse_bucket, read_save,
)


def split_l1(blob: bytes, password: str = PASSWORD):
    """把 .es3 拆成 (salt, iv, layer1_bytes)，保留原 key 派生参数。"""
    salt, iv, ct = blob[:16], blob[16:32], blob[32:]
    key = PBKDF2(password.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    layer1 = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    n = layer1[-1]
    if 1 <= n <= 16:
        layer1 = layer1[:-n]
    return salt, iv, layer1


def find_slot(layer1: bytes):
    """从桶里取出 string 槽的 key 与计数器值。"""
    _, obj = parse_bucket(layer1)
    slot = None
    for k, v in obj.items():
        if isinstance(v, dict) and v.get("__type") == "string":
            vv = v.get("value")
            if isinstance(vv, str) and vv and all(
                    c in "0123456789abcdefABCDEF" for c in vv):
                slot = k
                break
    counter = obj.get("_Key")
    if isinstance(counter, dict):
        counter = counter.get("value")
    return slot, counter, obj


def rebuild_bucket(hexstr: str, obj: dict) -> bytes:
    """按基准桶的实际条目顺序与名称重建，只替换 string 槽的 hex。"""
    parts = []
    for k, v in obj.items():
        if not isinstance(v, dict):
            continue
        t = v.get("__type")
        if t == "string":
            body = ('%s : {\n\t\t"__type" : "string",\n\t\t"value" : "%s"\n\t}'
                    % (json.dumps(k, ensure_ascii=False), hexstr))
        else:
            body = ('%s : {\n\t\t"__type" : "%s",\n\t\t"value" : %s\n\t}'
                    % (json.dumps(k, ensure_ascii=False), t, v.get("value", 0)))
        parts.append(body)
    joined = ",\n\t".join(parts)
    # 首项 key 的开引号在 ES3 写入器里会丢；照原样去掉
    if joined.startswith('"'):
        joined = joined[1:]
    return (joined + "\n}").encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="解锁推进：把关卡/家园进度改到界面可开的程度")
    ap.add_argument("--in", dest="inp", required=True,
                    help="基准 .es3（原档或已改档）")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--level", type=int, default=21,
                    help="GuanKaLevel 目标值（默认 21，宠物解锁门槛 >20）")
    ap.add_argument("--home-level", type=int, default=5,
                    help="家园/伐木场/矿石场等级（默认 5）")
    ap.add_argument("--resources", type=int, default=100000,
                    help="木材/矿石数量（默认 100000）")
    a = ap.parse_args(argv)

    blob = open(a.inp, "rb").read()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1
    print("基准 %s  (%d 字节, layer1 %d)" % (a.inp, len(blob), len(layer1)))
    print("  salt : %s" % salt.hex())
    print("  iv   : %s" % iv.hex())
    print("  slot : %s" % slot)
    print("  _Key : %r" % counter)
    print("  桶条目: %s" % ", ".join(obj.keys()))

    text = read_save(a.inp).decode("utf-8")
    segs = savedit.load(text)
    old_lv = segs[8].get("GuanKaLevel")
    segs[8]["GuanKaLevel"] = a.level
    segs[8]["IsGameOver"] = 0
    segs[8]["GuanKaLoad"] = 0
    segs[2]["JiaYuanLevel"] = a.home_level
    segs[2]["FaMuChangLevel"] = a.home_level
    segs[2]["KuangShiChangLevel"] = a.home_level
    segs[2]["JiaYuanRenKou"] = a.home_level
    segs[2]["FaMuChangRenKou"] = a.home_level
    segs[2]["KuangShiChangRenKou"] = a.home_level
    segs[2]["MuCaiShuLiang"] = a.resources
    segs[2]["KuangShiShuLiang"] = a.resources
    print("  GuanKaLevel %r -> %d" % (old_lv, a.level))

    plain = savedit.dump(segs).encode("utf-8")
    hexstr = des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = PBKDF2(PASSWORD.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    new_blob = salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(inner, 16))
    with open(a.out, "wb") as f:
        f.write(new_blob)
    print("输出 %s  (%d 字节, 明文 %d 字节)"
          % (a.out, len(new_blob), len(plain)))

    back = savedit.load(read_save(a.out).decode("utf-8"))
    ok = (back[8].get("GuanKaLevel") == a.level
          and back[2].get("JiaYuanLevel") == a.home_level
          and back[9].get("BaoShiSuiPian") == segs[9].get("BaoShiSuiPian")
          and back[11].get("IsHuangJin") == segs[11].get("IsHuangJin")
          and len(back[6].get("SuoYouChongWuDate", [])) == 90)
    print("回读自检: %s" % ("通过" if ok else "失败"))
    print("  GuanKaLevel   = %r" % back[8].get("GuanKaLevel"))
    print("  JiaYuanLevel  = %r" % back[2].get("JiaYuanLevel"))
    print("  BaoShiSuiPian = %r" % back[9].get("BaoShiSuiPian"))
    print("  IsHuangJin    = %r" % back[11].get("IsHuangJin"))
    print("  宠物数        = %d" % len(back[6].get("SuoYouChongWuDate", [])))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
