"""验证 ES3_FILE = PBKDF2(password, salt, 100 iterations) + AES-CBC。

反汇编证据（libil2cpp.so @0x1782e64）：
    mov  x24, x0        // Rfc2898DeriveBytes 实例
    mov  w3, #0x64      // iterations = 100
    mov  x1, x20        // password
    mov  x2, x25        // salt
    bl   #0x27a87e0     // Rfc2898DeriveBytes..ctor(byte[] pwd, byte[] salt, int iter, HashAlgorithmName, ...)
    ...
    mov  w1, #0x10      // GetBytes(16) -> keySize = 16

即 key = PBKDF2-HMAC-SHA1/256(password, salt, 100 iterations, 16 bytes)

ES3_FILE 的 Stream 布局（Encrypt(Stream)）实际顺序：
    salt(16) + iv(16) + cipher      或   iv(16) + salt(16) + cipher
需要两个都试。

另外 salt 也可能是固定的，或从文件头读。
"""
from paths import EMU, ES3_FILE

import hashlib

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
blob = open(ES3_FILE, "rb").read()
print("file len", len(blob))


def ok_plain(body: bytes) -> bool:
    head = body[:200]
    if len(head) < 2:
        return False
    pr = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    return pr / len(head) >= 0.90 and head[:1] in (b"{", b"[")


def test(iv: bytes, ct: bytes, key: bytes, label: str):
    try:
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    except Exception:
        return False
    pad = pt[-1]
    if not (1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad):
        return False
    body = pt[:-pad]
    if ok_plain(body):
        print(f"\n*** MATCH {label}")
        print("key:", key.hex())
        print(body[:800].decode("utf-8", "replace"))
        return True
    return False


PW = ["password", "Password", "PASSWORD", "SaveFile.es3", "es3", "ES3",
      "TapDemons", "taptap", "HQGAMES", "game.taptap.HQGAMES.TapDemons",
      "dianji", "DianJi", "mowang", "MoWang", "123456", "12345678",
      "abcdefghijklmnop", "TapTap", "easysave"]

HASHES = {
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "md5": hashlib.md5,
}

# 布局候选：(iv_off, ct_off, salt_off)
LAYOUTS = [
    ("salt16+iv16", 16, 32, 0),
    ("iv16+salt16", 0, 32, 16),
    ("salt16+iv0pad", 0, 16, 0),   # 无独立 iv
]

found = False
for layout_name, iv_off, ct_off, salt_off in LAYOUTS:
    iv = blob[iv_off : iv_off + 16]
    salt = blob[salt_off : salt_off + 16]
    ct = blob[ct_off:]
    if len(ct) % 16:
        continue
    for pw in PW:
        for hname, hf in HASHES.items():
            try:
                key = PBKDF2(pw, salt, dkLen=16, count=100, hmac_hash_module=hf)
            except Exception:
                continue
            if test(iv, ct, key, f"{layout_name} pw={pw!r} hash={hname} iter=100"):
                found = True
                break
        if found:
            break
    if found:
        break

print("FOUND" if found else "no match — 需要确认 salt 是否随机或口令不是这些候选")
