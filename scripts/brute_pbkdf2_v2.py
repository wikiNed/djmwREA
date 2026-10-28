"""确认 ES3_FILE 文件布局 + PBKDF2-HMAC-SHA1(password, salt, 100, 16)。

用 Crypto.Hash.SHA1 作为 hmac_hash_module（pycryptodome 需要模块而非函数）。

布局候选：
   A: salt(16) + iv(16) + cipher
   B: iv(16) + salt(16) + cipher
   C: salt(16) + cipher（iv 从固定偏移取）
"""
from paths import EMU, ES3_FILE

from Crypto.Cipher import AES
from Crypto.Hash import MD5, SHA1, SHA256
from Crypto.Protocol.KDF import PBKDF2
blob = open(ES3_FILE, "rb").read()
print("len", len(blob))

PW = ["password", "Password", "PASSWORD", "SaveFile.es3", "es3", "ES3",
      "ES3Settings", "encryptionPassword", "TapDemons", "taptap", "TapTap",
      "HQGAMES", "game.taptap.HQGAMES.TapDemons", "dianji", "DianJi",
      "mowang", "MoWang", "123456", "12345678", "abcdefghijklmnop",
      "1234567890", "qwerty", "easysave", "EasySave", "SaveFile", "savefile"]

LAYOUTS = [
    ("salt@0 iv@16 ct@32", 0, 16, 32),
    ("iv@0 salt@16 ct@32", 16, 0, 32),
]

HASHES = {"sha1": SHA1, "sha256": SHA256, "md5": MD5}


def ok_plain(body: bytes) -> bool:
    head = body[:300]
    if len(head) < 2:
        return False
    pr = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    return pr / len(head) >= 0.90 and head[:1] in (b"{", b"[")


found = False
for name, salt_off, iv_off, ct_off in LAYOUTS:
    salt = blob[salt_off : salt_off + 16]
    iv = blob[iv_off : iv_off + 16]
    ct = blob[ct_off:]
    for hn, H in HASHES.items():
        for pw in PW:
            key = PBKDF2(pw, salt, dkLen=16, count=100, hmac_hash_module=H)
            pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
            pad = pt[-1]
            if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
                body = pt[:-pad]
                if ok_plain(body):
                    print(f"\n*** MATCH layout={name} hash={hn} pw={pw!r}")
                    print(body[:900].decode("utf-8", "replace"))
                    found = True
                    break
        if found:
            break
    if found:
        break

print("FOUND" if found else "no match")
