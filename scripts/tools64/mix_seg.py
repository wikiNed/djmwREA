# -*- coding: utf-8 -*-
"""把 donor 存档的指定段搬进 base 存档，用于定位「哪一段触发作弊判定」。

用法：
    python mix_seg.py <base.save> <donor.save> <out.save> [0-6 | 10,11,13]
段号范围写法与 Python range 一致（左闭右开），逗号可混用；不给段号 = 原样重打包（自检）。
"""
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
import v557save as V


def parse_spec(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main():
    base, donor, out = sys.argv[1], sys.argv[2], sys.argv[3]
    idxs = parse_spec(sys.argv[4]) if len(sys.argv) > 4 else []
    _, segs = V.read_segments(base)
    _, dsegs = V.read_segments(donor)
    segs = list(segs)
    for i in idxs:
        print("seg%-2d  base %6d B  <- donor %6d B" % (i, len(segs[i]), len(dsegs[i])))
        segs[i] = dsegs[i]
    n = V.write_segments(out, None, segs)
    print("wrote %s  %d bytes" % (out, n))


if __name__ == "__main__":
    main()
