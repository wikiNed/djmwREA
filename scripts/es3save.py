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
import struct
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


class Variant:
    """一个游戏版本的加密参数集合。

    TapTap v5.9.2 与旧版 v5.5.7 的存档**结构完全相同**（14 段 `$` JSON，
    官方模板 playerDate_03 两版逐字节一致），只有外层 ES3 口令不同，
    内层 DES 的 `PJSQJ678` 两版一致（docs/14 §3.3）。

    两版口令的来源也不同，这点值得记住：

    * v5.9.2：口令硬编码进代码，经 IL2CPP 字面量哨兵 `0xA0005EF3`
      间接引用 —— usage index **12153**，metadata 里没有 `encryptionpassword`
      这个键（docs/10）。
    * v5.5.7：走 ES3 的默认配置机制，`ES3Defaults` 的 `encryptionpassword`
      值 —— usage index **656**（`files/old/global-metadata_v557.dat`，
      literal 表 `off=0x100 size=70448` → 8806 行）。

    两个 index 都是实测得出，不是猜的。
    """

    __slots__ = ("name", "password", "des_key", "literal_index", "meta")

    def __init__(self, name, password, des_key=DES_KEY,
                 literal_index=None, meta=None):
        self.name = name
        self.password = password
        self.des_key = des_key
        self.literal_index = literal_index
        self.meta = meta

    def __repr__(self):
        return "<Variant %s password=%r literal_index=%s>" % (
            self.name, self.password, self.literal_index)


#: TapTap v5.9.2（默认）
V592 = Variant("v5.9.2", "hqgames@2013", literal_index=12153,
               meta="global-metadata.dat")

#: 旧版 v5.5.7（包名 com.HQGAMES.TopDemons，仅 armeabi-v7a）
V557 = Variant("v5.5.7", "65w84e4p994z3Oq", literal_index=656,
               meta="old/global-metadata_v557.dat")

VARIANTS = {v.name: v for v in (V592, V557)}
DEFAULT_VARIANT = V592


def get_variant(name=None):
    """按名字取 Variant；None 或空返回默认（v5.9.2）。"""
    if not name:
        return DEFAULT_VARIANT
    key = name if name in VARIANTS else ("v" + name if "v" + name in VARIANTS else None)
    if key is None:
        raise KeyError("未知版本 %r，可选: %s"
                       % (name, ", ".join(sorted(VARIANTS))))
    return VARIANTS[key]

#: ES3 明文可能是 `key" : {...` 这种缺前导 `{` 的形态
#: （ES3 内部 Write 时把外层 `{` 吃掉了，不是解密错误）
_JSON_HINT = b'" : '


class PasswordError(ValueError):
    """口令不对。与"文件损坏"区分开 —— AES-CBC 用错口令仍会吐出等长字节。"""


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
    try:
        return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), 16)
    except ValueError:
        # AES-CBC 用错口令也会解出等长字节，只是 PKCS7 校验不过。
        # 这里转成自己的异常，免得使用者把它当成"文件损坏"。
        hint = ""
        if password == V592.password:
            hint = " 若这是旧版 v5.5.7 的存档，请加 --variant v5.5.7。"
        elif password == V557.password:
            hint = " 这已是旧版 v5.5.7 口令；若文件来自 TapTap 版，请用 --variant v5.9.2（默认）。"
        raise PasswordError(
            "第一层 AES 解密失败：口令 %r 不对（PKCS7 校验不过）。%s"
            % (password, hint))


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

    游戏侧是 `CryptoStream` + `PaddingMode.PKCS7`（见 ShuJuDate.DesDecrypt）。
    实测原档密文 38184 字节、明文 38178 字节、尾部 6 个 `\\x06` —— 标准 PKCS7。
    所以这里按 PKCS7 剥离；只有填充非法时才退化为 rstrip(b"\\x00")，
    以兼容早期按 NUL 填充生成的历史文件。
    """
    ct = bytes.fromhex(hexstr)
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    pt = DES.new(kb, DES.MODE_CBC, kb).decrypt(ct)
    if pt:
        n = pt[-1]
        if 1 <= n <= 8 and pt[-n:] == bytes([n]) * n:
            pt = pt[:-n]
        else:
            pt = pt.rstrip(b"\x00")
    return pt


def des_encrypt(plain: bytes, key: str = DES_KEY) -> str:
    """把明文封成内层 hex 串（大写，与游戏一致）。

    **必须用 PKCS7 填充**：游戏 `ShuJuDate.DesDecrypt` 走
    `CryptoStream.FlushFinalBlock()`，填充不合法会抛
    `CryptographicException: Bad PKCS7 padding. Invalid length 0.`，
    随后 `LoadGame()` 中断、游戏卡在标题页。
    早期实现补 NUL，导致的正是这个异常。
    """
    kb = key.encode("ascii")[:8].ljust(8, b"\0")
    plain = pad(plain, 8)  # PKCS7，与游戏 CryptoStream 一致
    ct = DES.new(kb, DES.MODE_CBC, kb).encrypt(plain)
    return ct.hex().upper()


def read_save(path: str, password: str = None, variant=None) -> bytes:
    """读 .es3，返回 **最内层的 14 段明文**（UTF-8 字节）。

    参数
    ----
    password : str, optional
        显式指定外层口令，优先于 ``variant``。
    variant : Variant | str, optional
        版本对象或版本名（``'v5.9.2'`` / ``'v5.5.7'``）。不给用默认。
    """
    v, pw = _resolve(password, variant)
    with open(path, "rb") as f:
        blob = f.read()
    layer1 = decrypt_bytes(blob, pw)
    return unwrap_bucket(layer1, v.des_key)


def _resolve(password=None, variant=None):
    """把 (password, variant) 归一成 (Variant, 口令字符串)。

    规则：显式 password 覆盖 variant 自带的口令（方便试新口令）；
    两者都给时 variant 仍决定 DES key。
    """
    if variant is None or isinstance(variant, str):
        v = get_variant(variant)
    else:
        v = variant
    pw = password if password is not None else v.password
    return v, pw


def unwrap_bucket(bucket: bytes, des_key: str = DES_KEY) -> bytes:
    """从 ES3 桶里取出第一个 string 型条目的 hex，再 DES 解成 14 段明文。

    若桶本身已经是 14 段明文（未加内层的存档），原样返回。
    """
    if is_14_segment(bucket):
        return bucket
    hexstr, _ = parse_bucket(bucket)
    if hexstr is None:
        raise ValueError("桶里找不到 string 型 hex 条目")
    return des_decrypt(hexstr, des_key)


#: ES3 桶里固定存在的计数器条目；_Key 之外还有 7 个英雄/宠物输出计数键。
#: 顺序取自真机原档（SaveFile.es3.orig，2026-10-29 实测）：
#:     _Key, <base64 string key>, ChongWu01, Hero06, Hero05, Hero04,
#:     Hero03, Hero02, Tap
#: 注意原档**没有** Hero01ShuChu_Key；早先版本多写了一个，是错的。
_COUNTER_KEYS = ('ChongWu01ShuChu_Key', 'Hero06ShuChu_Key', 'Hero05ShuChu_Key',
                 'Hero04ShuChu_Key', 'Hero03ShuChu_Key', 'Hero02ShuChu_Key',
                 'TapShuChu_Key')


def build_bucket(hexstr, key_counter=2640, string_key=None):
    r"""拼出 ES3 桶的明文（逐字节对齐真机原档排版）。

    真机原档 layer1 的原文（2026-10-29 实测，前 100 字节）::

        _Key" : {\n\t\t"__type" : "long",\n\t\t"value" : 2640\n\t},
        \n\t"o2D+pAPsvrXCo74JUkh9jw==" : {\n\t\t"__type" : "string",...

    ★ 桶明文**缺最外层的 { 和第一个 key（_Key）的开引号**。
    这不是 bug，是 ES3 写入器的行为；补上游戏反而读不出来。

    ★ 必须带 _Key 条目。早先的实现直接拿随机 base64 当第一个 key，
    把 _Key 整个丢了，生成的文件结构上就和原档不一样 —— 这是游戏
    读不到改档的第一个嫌疑点。

    参数
    ----
    hexstr : str
        内层 DES 密文的十六进制（大写）。
    key_counter : int
        _Key 的 long 值。真机原档为 2640；疑似与内容规模相关，但没
        反推出确切公式，默认照抄原档实测值。
    string_key : str, optional
        形如 o2D+pAPsvrXCo74JUkh9jw== 的 base64 字符串 key。真机是
        32 字符（24 字节 raw 的 base64）。不给则生成同长度随机值。
    """
    import base64
    import json

    if string_key is None:
        # 24 字节 -> base64 恰好 32 字符，与真机原档同宽
        string_key = base64.b64encode(os.urandom(24)).decode("ascii")

    out = ['_Key" : {\n\t\t"__type" : "long",\n\t\t"value" : %d\n\t}' % key_counter]
    out.append('%s : {\n\t\t"__type" : "string",\n\t\t"value" : "%s"\n\t}'
               % (json.dumps(string_key, ensure_ascii=False), hexstr))
    for name in _COUNTER_KEYS:
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


def write_save(path: str, plain: bytes, password: str = None,
               bak: bool = True, variant=None) -> str:
    """把 14 段明文封成两层后写回 .es3；默认保留 .bak。"""
    v, pw = _resolve(password, variant)
    hexstr = des_encrypt(plain, v.des_key)
    inner = build_bucket(hexstr)
    blob = encrypt_bytes(inner, pw)
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

def cmd_unpack(inp, out=None, variant=None):
    plain = read_save(inp, variant=variant)
    out = out or (inp + ".json")
    with open(out, "wb") as f:
        f.write(plain)
    ok = is_14_segment(plain)
    v = get_variant(variant)
    print("两层拆完 %s -> %s  (%d 字节, %s, 版本 %s)"
          % (inp, out, len(plain), "14 段存档" if ok else "结构异常", v.name))
    if not ok:
        print("  首 80 字节: %r" % plain[:80])
    return 0 if ok else 1


def cmd_pack(inp, out=None, variant=None):
    plain = open(inp, "rb").read()
    out = out or (inp[:-5] if inp.endswith(".json") else inp + ".es3")
    write_save(out, plain, variant=variant)
    # 立刻回读校验
    back = read_save(out, variant=variant)
    same = back == plain.rstrip(b"\0")[:len(back)]
    v = get_variant(variant)
    print("两层封回 %s -> %s  (%d 字节明文 -> %d 字节密文, 版本 %s)"
          % (inp, out, len(plain), os.path.getsize(out), v.name))
    print("  回读校验: %s" % ("一致" if same else "不一致（可能是尾部填充差异）"))
    return 0 if same else 1


def cmd_verify(inp, password=None, variant=None):
    v, pw = _resolve(password, variant)
    blob = open(inp, "rb").read()
    try:
        layer1 = decrypt_bytes(blob, pw)
    except ValueError as e:
        print("第一层(AES) 失败: %s" % e)
        return 1
    print("第一层(AES) 口令 %r -> 解开 %d 字节" % (pw, len(layer1)))
    try:
        plain = unwrap_bucket(layer1, v.des_key)
    except Exception as e:  # noqa: BLE001
        print("第二层(DES) 失败: %s" % e)
        return 1
    ok = is_14_segment(plain)
    print("第二层(DES key=%r) -> %d 字节, 14段=%s"
          % (v.des_key, len(plain), ok))
    if ok:
        print("  首 60 字节: %r" % plain[:60])
    return 0 if ok else 1


def cmd_variants(_arg=None):
    """列出已知版本，并核对各自 metadata 里的口令字面量是否对得上。"""
    print("%-8s %-20s %-10s %s" % ("版本", "外层口令", "DES key", "metadata 校验"))
    for name in sorted(VARIANTS):
        v = VARIANTS[name]
        chk = _check_variant(v)
        print("%-8s %-20s %-10s %s" % (v.name, v.password, v.des_key, chk))
    return 0


def _check_variant(v):
    """拿 variant 的 literal_index 去读对应 metadata，核对口令。"""
    try:
        from paths import META, FILES
        import peek_literal as pl
        meta = (FILES / v.meta) if v.meta else META
        if not meta.exists():
            return "跳过（找不到 %s）" % v.meta
        data = meta.read_bytes()
        if v.meta and v.meta.startswith("old/"):
            # 旧版 header 布局不同，用实测的 literal 表位置
            ln, lo = struct.unpack_from("<ii", data, 0x100 + v.literal_index * 8)
            base = 0x100 + 70448
            got = data[base + lo: base + lo + ln]
        else:
            got = pl.literal(data, v.literal_index)
        if got and got.decode("utf-8", "replace") == v.password:
            return "OK  index %d == %r" % (v.literal_index, v.password)
        return "不一致 index %d -> %r" % (v.literal_index, got)
    except Exception as e:  # noqa: BLE001
        return "检查失败: %s" % e


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    # --variant / -v 是全命令全局开关，先摘出来
    variant = None
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--variant", "-V") and i + 1 < len(argv):
            variant = argv[i + 1]
            i += 2
            continue
        if a.startswith("--variant="):
            variant = a.split("=", 1)[1]
            i += 1
            continue
        rest.append(a)
        i += 1
    if not rest:
        print(__doc__)
        return 2
    cmd = rest[0]
    if cmd == "unpack":
        return cmd_unpack(rest[1], rest[2] if len(rest) > 2 else None, variant)
    if cmd == "pack":
        return cmd_pack(rest[1], rest[2] if len(rest) > 2 else None, variant)
    if cmd == "verify":
        return cmd_verify(rest[1], rest[2] if len(rest) > 2 else None, variant)
    if cmd in ("variants", "list"):
        return cmd_variants()
    print("未知命令: %s" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
