"""验证 ES3 密钥派生方式。

ES3 的 AESEncryptionAlgorithm（源码口径）：
    private static byte[] GetKey(string password) {
        // key 长度固定 16 字节（AES-128）
        // 实际实现：Encoding.UTF8.GetBytes(password)，然后 pad/truncate 到 16
        // 但部分版本用 MD5(password) 作为 key
    }
    Encrypt: 明文 -> PKCS7 pad -> AES-CBC(key, iv=随机16字节) -> 文件 = iv + cipher

可能的 key 派生：
  K1: UTF8(password) 截断/补零到 16          ← 已试（try_key_strict.py）
  K2: MD5(UTF8(password))                    ← 未试
  K3: SHA256(UTF8(password))[:16]            ← 未试
  K4: UTF8(password) 补零到 32 并当 AES-256   ← 已试
  K5: 口令本身是 base64/hex 解出来的 16 字节    ← 未试

本脚本对 metadata 全部字面量做 K2/K3/K5，用严格判据（明文可打印且以 { 开头）。
"""
import base64
import hashlib
import struct

from Crypto.Cipher import AES

META = r"E:\DSH\game\.rea-study\lib\global-metadata.dat"
ES3 = r"E:\DSH\game\.rea-study\emu\SaveFile.es3"

meta = open(META, "rb").read()
SL_OFF, SL_CNT, SLD_OFF = 256, 133048, 133304
blob = open(ES3, "rb").read()
iv, ct = blob[:16], blob[16:]


def lit(i):
    ln, di = struct.unpack_from("<ii", meta, SL_OFF + i * 8)
    return meta[SLD_OFF + di : SLD_OFF + di + ln].decode("utf-8", "replace")


def ok_plain(body: bytes) -> bool:
    head = body[:256]
    if len(head) < 2:
        return False
    printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(head) < 0.95:
        return False
    return head[:1] in (b"{", b"[")


def dec(key: bytes, mode=AES.MODE_CBC):
    try:
        pt = AES.new(key, mode, iv[:16]).decrypt(ct)
    except Exception:
        return None
    pad = pt[-1]
    if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
        body = pt[:-pad]
    else:
        return None
    return body if ok_plain(body) else None


def keys_from(pw: str):
    ub = pw.encode("utf-8", "ignore")
    yield "md5", hashlib.md5(ub).digest()
    yield "sha256[:16]", hashlib.sha256(ub).digest()[:16]
    # 口令本身可能就是 hex/base64 编码的 16 字节
    try:
        h = bytes.fromhex(pw)
        if len(h) == 16:
            yield "hex", h
    except Exception:
        pass
    try:
        b = base64.b64decode(pw, validate=True)
        if len(b) == 16:
            yield "b64", b
    except Exception:
        pass


found = 0
for i in range(SL_CNT // 8):
    try:
        s = lit(i)
    except Exception:
        continue
    if not (4 <= len(s) <= 128):
        continue
    for label, k in keys_from(s):
        body = dec(k)
        if body:
            found += 1
            print(f"*** HIT literal#{i} pw={s!r} deriv={label}")
            print(body[:400])
print("hits:", found)
