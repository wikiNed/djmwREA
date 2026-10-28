"""重点验证：口令候选 "password"，穷举派生/偏移/模式。

ES3_FILE 的 AESEncryptionAlgorithm（官方源码）实际实现是：
    private Aes CreateAes() {
        Aes aes = Aes.Create();
        aes.Key = GetKey(password);          // 关键
        aes.Mode = CipherMode.CBC;
        aes.Padding = PaddingMode.PKCS7;
        return aes;
    }
    private byte[] GetKey(string password) {
        // 旧版：直接用 UTF8 bytes，不足 16 补 0
        // 新版：用 MD5 取前 16
    }

而且 ES3_FILE 加密文件的写入顺序是：
    byte[] iv = aes.IV;                  // 16 字节，随机
    byte[] encrypted = aes.CreateEncryptor().TransformFinalBlock(data);
    stream.Write(iv); stream.Write(encrypted);

所以 offset 16 是对的。但注意：**ES3_FILE 可能会对 IV 做 Base64 或存为 ASCII**，
以及部分版本用的是 `File.ReadAllBytes` 全量，前面还有 4 字节长度。

穷举：
  key 派生    : raw / pad0 / MD5 / SHA256[:16] / uppercase / lowercase / reversed
  密文起点    : 0, 4, 12, 16, 20, 32
  IV          : 前16 / 全零 / 从起点前16
  模式        : CBC / ECB / CFB
"""
from paths import EMU, ES3_FILE

import hashlib
import struct

from Crypto.Cipher import AES
blob = open(ES3_FILE, "rb").read()

PW_CANDS = ["password", "Password", "PASSWORD", "passWord", "p@ssw0rd", "pass"]


def ok_plain(body: bytes) -> bool:
    head = body[:200]
    if len(head) < 2:
        return False
    pr = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    return pr / len(head) >= 0.90 and head[:1] in (b"{", b"[")


def key_variants(pw: str):
    ub = pw.encode("utf-8")
    yield "raw", ub
    if len(ub) < 16:
        yield "pad0_16", ub + b"\x00" * (16 - len(ub))
    if len(ub) < 32:
        yield "pad0_32", ub + b"\x00" * (32 - len(ub))
    yield "md5", hashlib.md5(ub).digest()
    yield "sha256_16", hashlib.sha256(ub).digest()[:16]
    yield "sha1_16", hashlib.sha1(ub).digest()[:16]
    yield "rev", ub[::-1]


best = None
for pw in PW_CANDS:
    for kname, key in key_variants(pw):
        if len(key) not in (16, 24, 32):
            continue
        for ct_off in (0, 4, 8, 12, 16, 20, 32):
            for iv_mode in ("head", "zero", "none"):
                if iv_mode == "head":
                    iv = blob[:16]
                elif iv_mode == "zero":
                    iv = b"\x00" * 16
                else:
                    iv = None
                ct = blob[ct_off:]
                if len(ct) % 16:
                    ct = ct[: len(ct) // 16 * 16]
                if len(ct) < 32:
                    continue
                try:
                    if iv is None:
                        c = AES.new(key, AES.MODE_ECB)
                    else:
                        c = AES.new(key, AES.MODE_CBC, iv)
                    pt = c.decrypt(ct)
                except Exception:
                    continue
                pad = pt[-1]
                if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
                    body = pt[:-pad]
                else:
                    body = pt
                if ok_plain(body):
                    print(f"*** MATCH pw={pw!r} deriv={kname} ct_off={ct_off} iv={iv_mode}")
                    print(body[:600])
                    raise SystemExit(0)

print("no match for password family")
