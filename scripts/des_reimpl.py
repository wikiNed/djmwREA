"""复刻 ShuJuDate.Encrypt 的完整算法并验证。

反汇编证据（RVA 0x18A8A68，ARM64）：
    x19 = key (参数 x2)          -> 0x18A8A88  mov x19, x2
    x20 = SourceText (参数 x1)   -> 0x18A8A8C  mov x20, x1

    0x18A8AF4  bl  0x27AF8F0     DESCryptoServiceProvider..ctor()
    0x18A8AFC  bl  0x279B39C     Encoding.get_UTF8()
    0x18A8B14  blr x9            UTF8.GetBytes(SourceText)  -> x20 = 明文字节
    0x18A8B20  bl  0x279C9EC     Encoding.get_ASCII()
    0x18A8B38  blr x9            ASCII.GetBytes(key)        -> x0 = key 字节
    0x18A8B4C  ldp x9,x2,[x8,#0x1f8] ; blr x9   Slot 12 = set_Key(keyBytes)
    0x18A8B58  bl  0x279C9EC     Encoding.get_ASCII()
    0x18A8B80  blr x9            ASCII.GetBytes(key) 再来一次
    0x18A8B94  ldp x9,x2,[x8,#0x1d8] ; blr x9   Slot 10 = set_IV(keyBytes)
    0x18A8BA8  bl  0x284280C     MemoryStream..ctor()
    0x18A8BBC  blr x9            des.CreateEncryptor()      -> x21 = transform
    0x18A8BE4  bl  0x27A9300     CryptoStream..ctor(ms, transform, Write)
    0x18A8C14  blr x9            cryptoStream.Write(明文字节, 0, len)
    0x18A8C20  bl  0x27A976C     FlushFinalBlock()
    0x18A8C44  blr x9            ms.ToArray()               -> byte[]
    0x18A8C64..0x18A8CC0  逐字节 StringBuilder.AppendFormat("{0:x2}", b)
    0x18A8CD4  blr x9            sb.ToString()              -> 小写 hex 字符串

结论：Encrypt(plain, key) = hex( DES-CBC-PKCS7( UTF8(plain), key=ASCII(key), iv=ASCII(key) ) )
"""

from Crypto.Cipher import DES


def enc(text: str, key: str) -> str:
    k = key.encode("ascii")
    d = DES.new(k, DES.MODE_CBC, k)
    data = text.encode("utf-8")
    pad = 8 - (len(data) % 8)
    data += bytes([pad]) * pad
    return d.encrypt(data).hex()


def dec(hexstr: str, key: str) -> bytes:
    k = key.encode("ascii")
    d = DES.new(k, DES.MODE_CBC, k)
    return d.decrypt(bytes.fromhex(hexstr))


if __name__ == "__main__":
    # 自检
    for key in ("PJSQJ678",):
        for txt in ("a", "hello", '{"DateID":0,"PlayerName":"wikined"}'):
            ct = enc(txt, key)
            pt = dec(ct, key)
            assert pt.startswith(txt.encode("utf-8")), (txt, pt)
            print(f"key={key} len({txt})={len(txt):3d} -> hex {len(ct):5d} chars  OK")
    print()
    print("DES hex 长度 = ceil((len+1..8)/8)*8*2 字符")
    print("  76896 字节文件若为 hex 字符串 => 明文约 38446 字节")
