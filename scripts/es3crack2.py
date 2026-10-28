"""ES3 存档解密器 v2：暴力穷举参数组合。

已知候选（来自 dump.cs:262695-262700 ShuJuDate）：
  MIMA = "PJSQJ678"
  zhangHaoKey = "UJHJKOikhS"
  miMaKey = "TSHYUJKSds"

以及可能的口令（来自 SaveManager..ctor 的静态字段）。

穷举维度：
  - 文件布局：salt+iv+ct / iv+salt+ct
  - 编码：utf8 / utf16-le
  - 迭代：100（已知）/ 10 / 1000
  - KDF：PBKDF2-SHA1 / PBKDF2-SHA256
  - key 长度：16 / 32
  - 密码加盐后缀组合
判据：解出后去掉合法 PKCS7，且以 '{' 开头（可有 BOM）。
"""

from paths import ES3_FILE, SAVE_PLAIN
import hashlib
import itertools
import json
import sys

from Crypto.Cipher import AES

ES3 = sys.argv[1] if len(sys.argv) > 1 else ES3_FILE

PASSWORDS = [
    "", "PJSQJ678", "UJHJKOikhS", "TSHYUJKSds",
    "PJSQJ678UJHJKOikhS", "PJSQJ678TSHYUJKSds",
    "UJHJKOikhSTSds", "es3", "ES3", "SaveFile",
    "TapDemons", "taptap", "HQGAMES", "game.taptap.HQGAMES.TapDemons",
    "PJSQJ678TSHYUJKSdsUJHJKOikhS",
]


def unpad(pt: bytes):
    if not pt:
        return None
    pad = pt[-1]
    if 1 <= pad <= 16 and len(pt) >= pad and pt[-pad:] == bytes([pad]) * pad:
        return pt[:-pad]
    return None


def looks(pt):
    if pt is None:
        return False
    b = pt
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b[:1] in (b"{", b"[")


def main():
    data = open(ES3, "rb").read()
    print(f"file size: {len(data)}")
    heads = {
        "salt+iv": (data[:16], data[16:32], data[32:]),
        "iv+salt": (data[16:32], data[:16], data[32:]),
    }
    hits = 0
    for pwname, fmtname, hashalg, iters, enc in itertools.product(
        PASSWORDS, heads, ("sha1", "sha256"), (100, 10, 1000, 10000), ("utf-8", "utf-16-le")
    ):
        salt, iv, ct = heads[fmtname]
        pw = pwname.encode(enc)
        for dklen in (16, 32):
            try:
                key = hashlib.pbkdf2_hmac(hashalg, pw, salt, iters, dklen)
            except Exception:
                continue
            if len(ct) % 16:
                continue
            pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
            body = unpad(pt)
            if looks(body):
                print(f"\n*** HIT *** pw={pwname!r} fmt={fmtname} hash={hashalg} "
                      f"iters={iters} enc={enc} dklen={dklen}")
                open(str(SAVE_PLAIN), "wb").write(body)
                print("head:", body[:120])
                hits += 1
    print("hits:", hits)


if __name__ == "__main__":
    main()
