"""尝试用 metadata 中可能的字符串字面量作为 ES3 口令，解出 SaveFile.es3。

口径：如果口令是 C# 字符串常量，它一定在 metadata 的 stringLiteral 表里。
策略：
  1. 优先试 ES3 相关字面量（已知的 SaveFile.es3 / AutoSave.es3 附近索引）
  2. 试全部 16..64 长度的 token 型字面量
  3. 试常见弱口令字典
AES-128-CBC, 密钥 = PBKDF2? 不，ES3 官方是直接 UTF8(password) 截取/补齐到 16/24/32 字节。
ES3 的 AESEncryptionAlgorithm 实现：key = Encoding.UTF8.GetBytes(password)，然后用
AES.Create() 设置 Key（自动按 16/24/32 处理），Mode=CBC, Padding=PKCS7。
文件布局：[16字节 IV][密文]
"""
import struct
import sys

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

if AES is None:
    print("pycryptodome not installed, trying pyaes...")
    sys.exit(2)

META = r"E:\DSH\game\.rea-study\lib\global-metadata.dat"
ES3 = r"E:\DSH\game\.rea-study\emu\SaveFile.es3"

meta = open(META, "rb").read()
SL_OFF, SL_CNT, SLD_OFF = 256, 133048, 133304


def lit(i):
    ln, di = struct.unpack_from("<ii", meta, SL_OFF + i * 8)
    return meta[SLD_OFF + di : SLD_OFF + di + ln].decode("utf-8", "replace")


blob = open(ES3, "rb").read()
iv, ct = blob[:16], blob[16:]
print(f"file {len(blob)} bytes, iv={iv.hex()}")


def try_key(pw: str):
    for enc in ("utf-8", "latin-1"):
        try:
            kb = pw.encode(enc)
        except UnicodeEncodeError:
            continue
        for klen in (16, 24, 32):
            if len(kb) == klen:
                key = kb
            elif len(kb) < klen:
                key = kb + b"\x00" * (klen - len(kb))
            else:
                continue
            try:
                c = AES.new(key, AES.MODE_CBC, iv)
                pt = c.decrypt(ct)
            except Exception:
                continue
            # PKCS7 去填充
            if not pt:
                continue
            pad = pt[-1]
            if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
                body = pt[:-pad]
            else:
                body = pt
            if body.startswith(b"{") or body.startswith(b"[") or b'"' in body[:200]:
                head = body[:120]
                if all(9 <= b < 127 or b in (0x0A, 0x0D) or b >= 0x80 for b in head):
                    return enc, klen, body
    return None


# 1) 先试 metadata 里 ES3 相关字面量
cands = []
for i in range(SL_CNT // 8):
    try:
        s = lit(i)
    except Exception:
        continue
    if 4 <= len(s) <= 64:
        cands.append(s)

print(f"testing {len(cands)} literals...")
for s in cands:
    r = try_key(s)
    if r:
        enc, klen, body = r
        print(f"\n*** MATCH *** password={s!r} enc={enc} keylen={klen}")
        print(body[:400])
        sys.exit(0)
print("no match in literals")
