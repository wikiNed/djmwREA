#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ES3 存档封包/解包器 —— 把 .es3 和 .json 打通。

【两层结构，2026-10 实测确认】

    第一层：ES3 加密（AES-128-CBC）
        file = salt(16) ‖ iv(16) ‖ AES-128-CBC-PKCS7(桶)
        key  = PBKDF2-HMAC-SHA1(password_utf8, salt, iterations=100, dkLen=16)
        桶   = `{"<随机key>" : {"__type":"string","value":"<hex>"}, "<xxx>_Key": {...}}`

    第二层：游戏自己的 Encrypt()（DES-CBC）—— 见 docs/11
        hex  = uppercase_hex( DES-CBC(key="PJSQJ678", iv="PJSQJ678").encrypt(save) )
        save = 14 段 JSON 用 '$' 拼接

所以真正能改的存档在**内层**。本模块把两层都包好：

用法:
    from es3save import unpack_to_json, pack_from_json, PASSWORD

    unpack_to_json('SaveFile.es3', 'playerDate.json')   # 两层都拆开
    pack_from_json('playerDate.json', 'SaveFile.es3')   # 两层都封回去

CLI:
    python scripts/es3save.py unpack <in.es3> [out.json]
    python scripts/es3save.py pack   <in.json> [out.es3]
    python scripts/es3save.py verify <in.es3> [password]
"""
import os
import sys

from Crypto.Cipher import AES, DES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

#: ES3 存档口令，由静态分析取得（docs/10）
PASSWORD = "hqgames@2013"

#: 内层 DES 的 key/iv。见 docs/11：BaoCunDate -> Encrypt(SourceText, key)，
#: key 是 const string MIMA = "PJSQJ678"；IV 也用同一个字符串（Encrypt 里
#: ASCII.GetBytes(key) 被算了两次，一次给 Key 一次给 IV）。
DES_KEY = "PJSQJ678"

SALT_LEN = 16
IV_LEN = 16
ITERATIONS = 100
KEY_LEN = 16

#: ES3 明文可能是 `key" : {...` 这种缺前导 `{` 的形态
#: （ES3 内部 Write 时把外层 `{` 吃掉了，不是解密错误）
_JSON_HINT = b'" : '


def _looks_like_save(pt: bytes) -> bool:
    s = pt.lstrip(b"\xef\xbb\xbf").lstrip()
    if s[:1] in (b"{", b"["):
        return True
    return _JSON_HINT in s[:64]


def decrypt_bytes(blob: bytes, password: str = PASSWORD) -> bytes:
    """解密 ES3 字节串，返回明文（已剥 PKCS7）。"""
    if len(blob) < SALT_LEN + IV_LEN or (len(blob) - SALT_LEN - IV_LEN) % 16:
        raise ValueError(
            "长度非法: %d，应为 32 + 16n（salt 16 + iv 16 + 密文）" % len(blob)
        )
    salt = blob[:SALT_LEN]
    iv = blob[SALT_LEN:SALT_LEN + IV_LEN]
    ct = blob[SALT_LEN + IV_LEN:]
    key = PBKDF2(password.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)


def encrypt_bytes(plain: bytes, password: str = PASSWORD) -> bytes:
    """加密成 ES3 字节串（新随机 salt + iv）。"""
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = PBKDF2(password.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plain, 16))
    return salt + iv + ct


# ---------------------------------------------------------------- 内层 DES

def des_decrypt(hexstr: str, key: str = DES_KEY) -> bytes:
    """把内层 hex 串解成明文。

    实测明文尾部填充是 `\\x04\\x04\\x04\\x04`（4 个 0x04），
    说明游戏给 CryptoStream 传的 PaddingMode 让最后一字节是填充长度，
    但 38144 是 8 的整数倍 —— 填充长度本来就该是 8 才对。
    所以这里**不信任填充值，只按 NUL 和已知填充字节剥**，
    并且优先走 unpad 失败后的 rstrip。
    """
    ct = bytes.fromhex(hexstr)
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    pt = DES.new(kb, DES.MODE_CBC, kb).decrypt(ct)
    # 去掉尾部填充：末尾若是 n 个相同字节且 n<=8 就剥
    if pt:
        n = pt[-1]
        if 1 <= n <= 8 and pt[-n:] == bytes([n]) * n:
            pt = pt[:-n]
        else:
            pt = pt.rstrip(b"\x00")
    return pt


def des_encrypt(plain: bytes, key: str = DES_KEY) -> str:
    """把明文封成内层 hex 串（大写，与游戏一致）。

    填充用 NUL（实测 _orig 解出来末尾不带填充字节，
    说明原文件就是 8 对齐的——这里补 NUL 最保守，
    游戏读的时候 JSON 解析器会忽略尾部空白/零字节）。
    """
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    if len(plain) % 8:
        plain = plain + b"\0" * (8 - len(plain) % 8)
    ct = DES.new(kb, DES.MODE_CBC, kb).encrypt(plain)
    return ct.hex().upper()


def read_save(path: str, password: str = PASSWORD) -> bytes:
    """读 .es3，返回 **最内层的 14 段明文**（UTF-8 字节）。"""
    with open(path, "rb") as f:
        blob = f.read()
    layer1 = decrypt_bytes(blob, password)
    return unwrap_bucket(layer1)


def unwrap_bucket(bucket: bytes) -> bytes:
    """从 ES3 桶里取出第一个 string 型条目的 hex，再 DES 解成 14 段明文。

    若桶本身已经是 14 段明文（未加内层的存档），原样返回。
    """
    if is_14_segment(bucket):
        return bucket
    hexstr, _ = parse_bucket(bucket)
    if hexstr is None:
        raise ValueError("桶里找不到 string 型 hex 条目")
    return des_decrypt(hexstr)


def build_bucket(hexstr: str) -> bytes:
    """拼出 ES3 桶的明文（逐字节对齐原文件排版）。

    原文件形态（实测 head/tail）：
        o74JUkh9jw==" : {\\n\\t\\t"__type" : "string",\\n\\t\\t"value" : "<HEX>"\\n\\t},
        \\n\\t"Hero06ShuChu_Key" : {\\n\\t\\t"__type" : "long",\\n\\t\\t"value" : 0\\n\\t},
        ...
        \\n\\t"TapShuChu_Key" : {\\n\\t\\t"__type" : "long",\\n\\t\\t"value" : 0\\n\\t}\\n}

    ★ 桶明文**缺最外层的 `{` 和第一个 key 的开引号**。
    这不是 bug，是 ES3 写入器的行为；补上游戏反而读不出来。
    """
    import base64
    import json
    newkey = base64.b64encode(os.urandom(8)).decode("ascii")
    head = '%s" : {\n\t\t"__type" : "string",\n\t\t"value" : "%s"\n\t}' % (newkey, hexstr)
    out = [head]
    for name in ("Hero06ShuChu_Key", "Hero05ShuChu_Key", "Hero04ShuChu_Key",
                 "Hero03ShuChu_Key", "Hero02ShuChu_Key", "Hero01ShuChu_Key",
                 "ChongWu01ShuChu_Key", "TapShuChu_Key"):
        out.append('%s : {\n\t\t"__type" : "long",\n\t\t"value" : 0\n\t}'
                   % json.dumps(name, ensure_ascii=False))
    return (",\n\t".join(out) + "\n}").encode("utf-8")


def parse_bucket(layer1: bytes):
    """解析 ES3 桶，返回 (hexstr, obj)。容错"缺外层 `{`"的形态。

    原文件第一项形如 `o74JUkh9jw==" : {...}`（key 的**开引号也丢了**，
    只剩收引号和 `"` + ` : `）。所以补写要补 `{"`，把开引号一起补上。
    """
    import json
    s = layer1.decode("utf-8-sig").lstrip()
    if s.startswith("{"):
        fixed = s
    elif s.startswith('"'):
        fixed = '{"' + s[1:]          # 已有开引号，只补 `{`
    else:
        fixed = '{"' + s              # 开引号也丢了
    obj = json.loads(fixed)
    hexstr = None
    for k, v in obj.items():
        if isinstance(v, dict) and v.get("__type") == "string":
            vv = v.get("value")
            if isinstance(vv, str) and vv and all(
                    c in "0123456789abcdefABCDEF" for c in vv):
                hexstr = vv
                break
    return hexstr, obj


def write_save(path: str, plain: bytes, password: str = PASSWORD,
               bak: bool = True) -> str:
    """把 14 段明文封成两层后写回 .es3；默认保留 .bak。"""
    hexstr = des_encrypt(plain)
    inner = build_bucket(hexstr)
    blob = encrypt_bytes(inner, password)
    if bak and os.path.exists(path):
        import shutil
        shutil.copy2(path, path + ".bak")
    with open(path, "wb") as f:
        f.write(blob)
    return path


def _fix_fragment(text: str) -> str:
    """把 ES3 缺前导 `{` 的明文补成可解析的 JSON。"""
    s = text.lstrip("\ufeff").lstrip()
    if s[:1] in ("{", "["):
        return s
    return '{"' + s


def is_14_segment(plain: bytes) -> bool:
    """是不是 14 段 `$` 拼接的正式存档（而不是 key-value 桶）。"""
    try:
        s = plain.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    parts = [p for p in s.split("$") if p.strip()]
    if len(parts) != 14:
        return False
    try:
        return all(p.strip().lstrip().startswith("{") for p in parts)
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ CLI

def cmd_unpack(inp, out=None):
    plain = read_save(inp)
    out = out or (inp + ".json")
    with open(out, "wb") as f:
        f.write(plain)
    ok = is_14_segment(plain)
    print("两层拆完 %s -> %s  (%d 字节, %s)"
          % (inp, out, len(plain), "14 段存档" if ok else "结构异常"))
    if not ok:
        print("  首 80 字节: %r" % plain[:80])
    return 0 if ok else 1


def cmd_pack(inp, out=None):
    plain = open(inp, "rb").read()
    out = out or (inp[:-5] if inp.endswith(".json") else inp + ".es3")
    write_save(out, plain)
    # 立刻回读校验
    back = read_save(out)
    same = back == plain.rstrip(b"\0")[:len(back)]
    print("两层封回 %s -> %s  (%d 字节明文 -> %d 字节密文)"
          % (inp, out, len(plain), os.path.getsize(out)))
    print("  回读校验: %s" % ("一致" if same else "不一致（可能是尾部填充差异）"))
    return 0 if same else 1


def cmd_verify(inp, password=PASSWORD):
    blob = open(inp, "rb").read()
    layer1 = decrypt_bytes(blob, password)
    print("第一层(AES) 口令 %r -> 解开 %d 字节" % (password, len(layer1)))
    try:
        plain = unwrap_bucket(layer1)
    except Exception as e:  # noqa: BLE001
        print("第二层(DES) 失败: %s" % e)
        return 1
    ok = is_14_segment(plain)
    print("第二层(DES key=%r) -> %d 字节, 14段=%s"
          % (DES_KEY, len(plain), ok))
    if ok:
        print("  首 60 字节: %r" % plain[:60])
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "unpack":
        return cmd_unpack(argv[1], argv[2] if len(argv) > 2 else None)
    if cmd == "pack":
        return cmd_pack(argv[1], argv[2] if len(argv) > 2 else None)
    if cmd == "verify":
        return cmd_verify(argv[1], argv[2] if len(argv) > 2 else PASSWORD)
    print("未知命令: %s" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
