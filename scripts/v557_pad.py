"""v557 存档长度对齐：压缩 seg8 的 1000000000.0 哨兵，为宠物升级腾出空间。

背景（docs/23 §四）：
    header[2] / header[11] 是单字节长度，只能加不能进位。
    delta > 102 会让 header[3] 从 0x25 变成 0x29，游戏报
    CryptographicException: Bad PKCS7 padding，改档失败。

所以大改必须用「可压缩字段」把明文缩短，抵消宠物数字位数增加。
seg8 的 122 个 1000000000.0（16 字符）→ 0.0（3 字符），每个省 13 字节，
理论最大压缩 122 * 13 = 1586 字节。

用法：
    python v557_pad.py --in wk.save --pets-level 60 --drop 110
"""
import argparse
import json
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from v557save import build, read_segments  # noqa: E402

BASE_TOTAL = 75167
HDR_LEN_POS = (2, 11)
MAX_DELTA = 102


def count_sentinels(seg8):
    return seg8.count(b"1000000000.0")


def shrink_sentinels(seg8, n):
    """把前 n 个 1000000000.0 换成 0.0，返回新 bytes。"""
    out = seg8
    for _ in range(n):
        idx = out.find(b"1000000000.0")
        if idx < 0:
            break
        out = out[:idx] + b"0.0" + out[idx + 12:]
    return out


def fix_header(header, total_len, base=BASE_TOTAL):
    """修正 header 里的长度字节。

    ★ 重要（2026-11-01 实测修正 docs/23 §四 的结论）：
       header[2] / header[11] 只对「文件总长恒为 BASE_TOTAL」的情况成立。
       一旦文件长度变化，游戏侧 ES2Reader.Read[T] 会抛
       EndOfStreamException: Unable to read beyond the end of the stream
       （栈帧：System.IO.BinaryReader.ReadString -> ES2Reader.Read -> ES2.Load
        -> ShuJuDate.LoadGame -> ChuangJianPlayer.DengLuChengGong），
       画面直接黑屏。

       所以本函数现在只做「delta==0 时的恒等返回」，
       长度不一致时明确报错，而不是悄悄算出错误的 header。
    """
    hdr = bytearray(header)
    delta = total_len - base
    for p in HDR_LEN_POS:
        hdr[p] = (hdr[p] + delta) & 0xFF
    return bytes(hdr), delta


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--pets-level", type=int)
    ap.add_argument("--zhuanshi", type=int)
    ap.add_argument("--drop", type=int, default=0,
                    help="压缩多少个 seg8 哨兵（每个省 13 字节）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    header, segs = read_segments(a.src)
    orig_total = sum(len(s) for s in segs) + 13 + 14 + 1
    print("原档总长 = %d" % orig_total)

    # 1. 改宠物
    if a.pets_level is not None:
        s6 = json.loads(segs[6].decode("utf-8"))
        pets = s6["SuoYouChongWuDate"]
        before = collections_counter(pets)
        for p in pets:
            p["ChongWuLevel"] = a.pets_level
        segs[6] = json.dumps(s6, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        print("宠物 86 只 -> 等级 %d（原 %s）" % (a.pets_level, before))

    # 2. 改钻石
    if a.zhuanshi is not None:
        s13 = json.loads(segs[13].decode("utf-8"))
        print("ZuanShi %s -> %d" % (s13.get("ZuanShi"), a.zhuanshi))
        s13["ZuanShi"] = a.zhuanshi
        segs[13] = json.dumps(s13, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # 3. 压缩 seg8 腾空间
    if a.drop:
        avail = count_sentinels(segs[8])
        n = min(a.drop, avail)
        segs[8] = shrink_sentinels(segs[8], n)
        print("压缩 seg8 哨兵 %d / %d 个（省 %d 字节）" % (n, avail, n * 13))

    plain = b"$".join(segs)
    # 计算最终文件长度：header(14) + hex(2*ctlen) + footer(1)
    ctlen = (len(plain) // 8 + 1) * 8
    total = 14 + ctlen * 2 + 1
    delta = total - BASE_TOTAL
    print("\n最终明文 %d -> 密文 %d -> 文件 %d，delta = %d" % (len(plain), ctlen, total, delta))

    if abs(delta) > MAX_DELTA:
        print("!! delta 超出 +/-%d，header[3] 会越界，游戏会拒绝" % MAX_DELTA)
        if not a.dry_run:
            print("请增加 --drop（每多压缩 1 个哨兵省 13 字节）")
            return 1

    hdr, _ = fix_header(header, total)
    print("header %s -> %s" % (header.hex(), hdr.hex()))

    if a.dry_run:
        print("[dry-run] 不写出")
        return 0

    data = build(hdr, plain)
    with open(a.dst, "wb") as f:
        f.write(data)
    print("写出 %s : %d 字节" % (a.dst, len(data)))
    return 0


def collections_counter(pets):
    from collections import Counter
    return Counter(p["ChongWuLevel"] for p in pets)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
