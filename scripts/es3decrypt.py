"""ES3 存档解密器（PBKDF2-HMAC-SHA1, 100 轮, Aes-128-CBC）。

布局（由 libil2cpp.so 反汇编确定）：
  salt(16) + iv(16) + AES-128-CBC-PKCS7(cipher)

key = PBKDF2-HMAC-SHA1(password.encode('utf8'), salt, 100, dkLen=16)
"""
import hashlib
import sys

from Crypto.Cipher import AES


def decrypt(path: str, password: str) -> bytes:
    data = open(path, "rb").read()
    salt, iv, ct = data[:16], data[16:32], data[32:]
    key = hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), salt, 100, 16)
    pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    pad = pt[-1]
    if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
        pt = pt[:-pad]
    return pt


def looks_plain(pt: bytes) -> bool:
    """ES3 明文是 $ 拼接的 JSON。"""
    if len(pt) == 0:
        return False
    head = pt[:8]
    return head.lstrip(b"\xef\xbb\xbf").startswith(b"{") or head.startswith(b"[")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"E:\DSH\game\.rea-study\emu\SaveFile.es3"
    for pw in sys.argv[2:]:
        try:
            pt = decrypt(path, pw)
        except Exception as e:  # noqa: BLE001
            print(f"[{pw!r}] decrypt error: {e}")
            continue
        ok = looks_plain(pt)
        print(f"[{pw!r}] len={len(pt)} looks_plain={ok} head={pt[:60]!r}")
