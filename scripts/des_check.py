#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解密 .es3，断言它就是 `ShuJuDate.Encrypt` 的产物（DES-CBC/ECB）。

结论链（见 docs/11）：
    BaoCunDate @0x18A71B4
      -> 逐个 ToJson(14 个 Date_*) 拼成 string[]
      -> ZhuanHuanString @0x18A89D0  用 '$' 拼接
      -> Encrypt @0x18A8A68          DESCryptoServiceProvider
      -> str 到 ShuJuDate.gameDateStr 后在 SaveGame 里写 ES3

`Encrypt` 的细节（反汇编 0x18A8A68..0x18A8CF0）：
    UTF8.GetBytes(SourceText)          ; x20
    ASCII.GetBytes(key)                ; x19   -> DES 的 Key
    desc.Key = ascii(key)
    ASCII.GetBytes(key) 再一次          ; -> DES 的 IV（同样 8 字节）
    StreamWriter(mem).Write(ciphertext)  -> 转成 hex 大写串

用法:
    python scripts/des_check.py saves/SaveFile_orig.es3
"""
import json
import sys

from Crypto.Cipher import DES
from es3_probe import main as probe

#: 由 BaoCunDate 的 `bl #0x18a75d4` 之前 `ldr x2,[x21]`（槽 0x35ee2b0）拿到的常量
#: 反查 metadata 字面量得到；见 docs/11
MIMA = "PJSQJ678"


def try_des(ct, key):
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    out = []
    for name, mode in (("ECB", DES.MODE_ECB), ("CBC-iv=key", DES.MODE_CBC)):
        for pad in ("none", "zero", "pkcs7"):
            try:
                if mode == DES.MODE_ECB:
                    c = DES.new(kb, DES.MODE_ECB)
                else:
                    c = DES.new(kb, DES.MODE_CBC, kb)
                pt = c.decrypt(ct)
                if pad == "pkcs7":
                    n = pt[-1]
                    if not 1 <= n <= 8 or pt[-n:] != bytes([n]) * n:
                        continue
                    pt = pt[:-n]
                elif pad == "zero":
                    pt = pt.rstrip(b"\0")
                out.append((name, pad, pt))
            except Exception:  # noqa: BLE001
                pass
    return out


def main(argv):
    path = argv[0]
    print("=" * 70)
    print("先看 ES3 外层桶：")
    probe([path])

    from es3save import PASSWORD, decrypt_bytes, _fix_fragment
    text = decrypt_bytes(open(path, "rb").read(), PASSWORD).decode("utf-8-sig")
    obj = json.loads(_fix_fragment(text))
    k0 = list(obj.keys())[0]
    inner = bytes.fromhex(obj[k0]["value"])
    print("=" * 70)
    print("内层 hex 负载 %d 字节，用 DES 试解：" % len(inner))
    hits = try_des(inner, MIMA)
    if not hits:
        print("  [!] 没有一种组合成功")
        return 1
    for name, pad, pt in hits:
        printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in pt) / max(1, len(pt))
        flag = " <<< 像明文" if printable > 0.9 else ""
        print("  %-10s pad=%-5s printable=%.1f%%  head=%r%s"
              % (name, pad, printable * 100, pt[:60], flag))
    return 0


if __name__ == "__main__":
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("--")]))
