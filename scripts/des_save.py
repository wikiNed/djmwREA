"""按 ShuJuDate.Encrypt 的算法（DES-CBC, Key=IV=ASCII(key)）解密/加密存档。

Encrypt 逻辑（RVA 0x18A8A68）：
    des = DESCryptoServiceProvider()
    kb  = Encoding.ASCII.GetBytes(key)
    des.Key = kb          (偏移 0x1f8 属性槽)
    des.IV  = kb          (偏移 0x1d8 属性槽)
    ms  = MemoryStream(); cs = CryptoStream(ms, des.CreateEncryptor(), Write)
    cs.Write(UTF8.GetBytes(text), 0, len); cs.FlushFinalBlock()
    out = hex(ms.ToArray())        # 小写，每字节 %02x
"""

import binascii
import sys

from Crypto.Cipher import DES

KEYS = {
    "ShuJuDate": "PJSQJ678",
    "ShenQiBaoShiDateModel": "JNHPLSWE",
    "ChongWuClass_GaoJi": "YHNTGBFV",
    "ShengMingShuDate": "HTGFROKU",
    "PlayerData": "HYUUJSIW",
    "PlayerDataModel": "GHYTBNSI",
    "MoShiKuManager": "MJHNMJKL",
    "ZhiChiManager": "HSYGHJKW",
    "Boss": "HYMJSYLO",
    "ShenQi": "HBGNJUKS",
    "ChongWuManager": "HYTGBFRO",
    "ChongWuPool": "OAKSUENF",
    "XuanZeButton": "TYTYREIO",
    "TimeGetter": "D998A7SB",
    "HongBaoYuManager": "HONGBAOM",
    "LiBaoClass": "HQ@85126",
    "Dan": "DAN12345",
    "chongZhiIV": "DAN12335",
}


def des_decrypt_bytes(data: bytes, key: str) -> bytes:
    k = key.encode("ascii")
    c = DES.new(k, DES.MODE_CBC, k)
    return c.decrypt(data)


def des_encrypt_bytes(data: bytes, key: str) -> bytes:
    k = key.encode("ascii")
    c = DES.new(k, DES.MODE_CBC, k)
    pad = 8 - (len(data) % 8)
    return c.encrypt(data + bytes([pad]) * pad)


def try_file(path: str):
    raw = open(path, "rb").read()
    print(f"file={path} size={len(raw)} mod8={len(raw) % 8}")
    print(f"head32={raw[:32].hex()}")
    for name, key in KEYS.items():
        try:
            pt = des_decrypt_bytes(raw, key)
        except Exception as e:
            print(f"  {name:24s} {key}  ERR {e}")
            continue
        pad = pt[-1]
        ok_pad = 1 <= pad <= 8 and pt[-pad:] == bytes([pad]) * pad
        head = pt[:48]
        printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13, 0x24))
        score = printable / len(head)
        flag = ""
        if ok_pad:
            flag += " PAD_OK"
        if score > 0.8:
            flag += " TEXT"
        print(f"  {name:24s} {key}  pad={pad:3d} score={score:.2f}{flag}  {head[:40]!r}")
        if score > 0.8 and ok_pad:
            print(f"      >>> HIT with {key}")
            return key, pt
    return None, None


if __name__ == "__main__":
    try_file(sys.argv[1])
