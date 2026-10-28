"""ES3 存档解密器（PBKDF2-HMAC-SHA1, 100 轮, AES-128-CBC）。

布局（由 libil2cpp.so 反汇编确定，见 docs/07-ES3口令追踪-阶段性结论.md）：
    salt(16) + iv(16) + AES-128-CBC-PKCS7(cipher)

    key = PBKDF2-HMAC-SHA1(password.encode('utf-8'), salt, 100, dkLen=16)

用法：
    from es3decrypt import decrypt, decrypt_or_raise
    plain = decrypt_or_raise('SaveFile.es3', password)

注意：口令错误时 AES-CBC 仍会解出等长字节，只是内容为乱码。
      decrypt() 只做宽松校验（剥 PKCS7）；decrypt_or_raise() 会强制校验
      明文必须以 '{' 或 '[' 开头，错误口令直接抛 PasswordError。
"""
import hashlib
import sys

from Crypto.Cipher import AES


class PasswordError(ValueError):
    """口令错误：解密结果不是合法的 ES3 明文。"""


def _kdf(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), salt, 100, 16)


def looks_plain(pt: bytes) -> bool:
    """判断明文是否像 ES3 的 JSON。

    注意：ES3 写 string 类型的顶层值时，文件开头就是 `key" : {...`，
    **没有前导 `{`**（`{` 被 ES3 自己的写入器丢掉了，见 docs/10）。
    所以不能只看首字符；这里改为判断"前 64 字节内出现 `" : "` 或首字符是 {/["。
    """
    if not pt:
        return False
    head = pt[:64].lstrip(b"\xef\xbb\xbf").lstrip()
    if head.startswith(b"{") or head.startswith(b"["):
        return True
    return b'" : ' in head


def _unpad(pt: bytes) -> bytes:
    """剥 PKCS7，并校验填充合法。"""
    if not pt:
        return pt
    pad = pt[-1]
    if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
        return pt[:-pad]
    return pt


def decrypt(path: str, password: str) -> bytes:
    """解密，返回去填充后的字节。口令错误时返回乱码（不抛异常）。

    需要严格校验请用 decrypt_or_raise()。
    """
    data = open(path, "rb").read()
    if len(data) < 32 or (len(data) - 32) % 16 != 0:
        raise ValueError(
            f"文件长度非法: {len(data)}，应为 32 + 16n（salt 16 + iv 16 + 密文）"
        )
    salt, iv, ct = data[:16], data[16:32], data[32:]
    key = _kdf(password, salt)
    pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    return _unpad(pt)


def decrypt_or_raise(path: str, password: str) -> bytes:
    """解密并强制校验明文形态；口令错误抛 PasswordError。"""
    pt = decrypt(path, password)
    if not looks_plain(pt):
        raise PasswordError(
            f"口令错误：解密结果不是合法 JSON（首 32 字节 {pt[:32]!r}）"
        )
    return pt


def check_password(path: str, password: str) -> bool:
    """快速判断口令是否正确。"""
    try:
        decrypt_or_raise(path, password)
        return True
    except PasswordError:
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        print("用法: python es3decrypt.py <SaveFile.es3> <password> [password2 ...]")
        sys.exit(1)

    path = sys.argv[1]
    found = False
    for pw in sys.argv[2:]:
        try:
            pt = decrypt_or_raise(path, pw)
        except PasswordError:
            print(f"[{pw!r}] 口令错误")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[{pw!r}] 错误: {e}")
            continue
        found = True
        print(f"[{pw!r}] *** 正确 ***  len={len(pt)}  段数={pt.count(b'$') + 1}")
        print(f"    首 120 字节: {pt[:120]!r}")
        out = path + ".dec.json"
        with open(out, "wb") as f:
            f.write(pt)
        print(f"    已写出: {out}")

    if not found:
        print("\n全部未命中。")
        sys.exit(2)
