"""v557 存档宠物携带实验：把 IsXieDai 置 1，观察战斗力变化。

背景：
    docs/23 已验证宠物数据被游戏读取并回写，但「战斗力」数值从未验证过。
    86 只宠物全都是 IsXieDai=0（未携带），所以主角战斗力一直是 1。
    携带宠物才可能加成。

用法：
    python v557_carry.py --in wk.save --out wk_carry.save --carry-id 0 --level 9
"""
import argparse
import json
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from v557save import build, read_segments  # noqa: E402

BASE_TOTAL = 75167
HDR_LEN_POS = (2, 11)


def fix_header(header, total_len, base=BASE_TOTAL):
    hdr = bytearray(header)
    delta = total_len - base
    for p in HDR_LEN_POS:
        hdr[p] = (hdr[p] + delta) & 0xFF
    return bytes(hdr), delta


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--carry-id", type=int, default=0)
    ap.add_argument("--level", type=int)
    ap.add_argument("--jin-hua", type=int)
    ap.add_argument("--jin-jie", type=int)
    ap.add_argument("--all", action="store_true", help="所有宠物都设为携带")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    header, segs = read_segments(a.src)

    s6 = json.loads(segs[6].decode("utf-8"))
    pets = s6["SuoYouChongWuDate"]
    touched = []
    for p in pets:
        hit = a.all or p["ChongWuID"] == a.carry_id
        if not hit:
            continue
        p["IsXieDai"] = 1
        if a.level is not None:
            p["ChongWuLevel"] = a.level
        if a.jin_hua is not None:
            p["ChongWuJinHua"] = a.jin_hua
        if a.jin_jie is not None:
            p["ChongWuJinJie"] = a.jin_jie
        touched.append(p["ChongWuID"])
    segs[6] = json.dumps(s6, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    print("设为携带的宠物 ID: %s" % touched[:12])

    plain = b"$".join(segs)
    ctlen = (len(plain) // 8 + 1) * 8
    total = 14 + ctlen * 2 + 1
    delta = total - BASE_TOTAL
    print("明文 %d -> 密文 %d -> 文件 %d，delta = %d" % (len(plain), ctlen, total, delta))
    if abs(delta) > 102:
        print("!! delta 越界")
        return 1

    hdr, _ = fix_header(header, total)
    if a.dry_run:
        print("[dry-run] header %s" % hdr.hex())
        return 0
    data = build(hdr, plain)
    with open(a.dst, "wb") as f:
        f.write(data)
    print("写出 %s : %d 字节，header %s" % (a.dst, len(data), hdr.hex()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
