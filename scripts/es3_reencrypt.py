#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把明文按「指定基准档的 salt/iv」重新加密，用于隔离变量。

背景（2026-10-29 实测）
=======================
`SaveFile.es3` 有两层封装：

    外层：ES3 AES-128-CBC，file = salt(16) || iv(16) || cipher
    内层：游戏自己的 DES-CBC，hex 后放进 ES3 桶的 string 条目

用 `es3save.write_save()` 重新封装的档（新随机 salt/iv）推到设备后，
游戏 `ES3JSONReader..ctor` 会抛：

    FormatException: Cannot load from file because the data in it is not
    JSON data, or the data is encrypted.

而且画面全黑（游戏卡在加载）。同一个档用 `read_save()` 读回来却
完全正常，说明**封装层没有破坏内容**，是别的东西让 ES3 拒绝了文件。

本脚本用来做控制变量：把明文用**基准档原样的 salt/iv** 重新加密，
于是除密文可预期地一致外，其余字节与基准档完全相同。如果这样游戏
能读，问题就在 salt/iv；如果仍然不能读，问题在密文之外的机制。

用法::

    python scripts/es3_reencrypt.py <基准.es3> <明文来源.es3> <输出.es3>
    python scripts/es3_reencrypt.py --same-key <输入.es3> <输出.es3>

`--same-key` 模式 = 用输入档自己的 salt/iv 重加密自己的明文，
输出应当与输入**逐字节相同**（这是一个自检）。
"""

import os
import sys

from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from es3save import PASSWORD, decrypt_bytes  # noqa: E402


def derive_key(salt, password=PASSWORD):
    return PBKDF2(password.encode("utf-8"), salt, dkLen=16, count=100,
                  hmac_hash_module=SHA1)


def splice(baseline_path, plain_path, out_path):
    """用 baseline 的 salt/iv 加密 plain_path 的内层明文。

    `plain_path` 可以是任意 .es3（会先解密出 layer1），也可以是
    直接给 layer1 原文的文件（以 `.layer1` 结尾）。
    """
    base = open(baseline_path, "rb").read()
    salt, iv = base[:16], base[16:32]
    key = derive_key(salt)

    if plain_path.endswith(".layer1"):
        layer1 = open(plain_path, "rb").read()
    else:
        layer1 = decrypt_bytes(open(plain_path, "rb").read())

    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(layer1, 16))
    blob = salt + iv + ct
    with open(out_path, "wb") as f:
        f.write(blob)

    print("基准 %s" % baseline_path)
    print("  salt %s  iv %s" % (salt.hex(), iv.hex()))
    print("明文 %d 字节 -> 输出 %d 字节" % (len(layer1), len(blob)))
    print("已写出 %s" % out_path)
    return blob


def same_key(in_path, out_path):
    """用输入档自己的 salt/iv 重加密自己的明文；应逐字节还原。"""
    blob = open(in_path, "rb").read()
    salt, iv, ct = blob[:16], blob[16:32], blob[32:]
    key = derive_key(salt)
    pt = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)
    re = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(pt, 16))
    with open(out_path, "wb") as f:
        f.write(salt + iv + re)
    same = re == ct
    print("自检：重加密与原文一致? %s" % same)
    print("已写出 %s" % out_path)
    return same


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--same-key":
        if len(argv) != 3:
            print(__doc__)
            return 2
        return 0 if same_key(argv[1], argv[2]) else 1
    if len(argv) != 3:
        print(__doc__)
        return 2
    splice(argv[0], argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
