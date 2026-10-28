"""在整段内存里做二进制特征搜索（不依赖 grep 的行语义）。

之前设备端 `grep -c` 对二进制文件按"行"计数，遇到超长无换行区域会漏判。
这里直接对每个段做 bytes.find，并同时尝试 UTF-8 与 UTF-16LE 两种编码。

用法：
    python scan_mem.py <段文件目录或单个文件>
"""
import os
import sys

FEATURES = [
    "DateID",
    "BaoShiSuiPian",
    "HeroBaoShis",
    "LiBaoIDs",
    "SuoYouBaoShiTongJi",
    "SaveFile",
    "HerosDates",
    "HuangJinShu",
    "ShuJuDate",
    ".es3",
]


def encodings(s):
    yield "utf8", s.encode("utf-8")
    yield "utf16le", s.encode("utf-16-le")


def scan_blob(data, label, results, limit_per_feat=3):
    for s in FEATURES:
        for enc, pat in encodings(s):
            start = 0
            n = 0
            while n < limit_per_feat:
                i = data.find(pat, start)
                if i < 0:
                    break
                results.append((s, enc, label, i))
                start = i + 1
                n += 1


def main():
    target = sys.argv[1]
    files = []
    if os.path.isdir(target):
        for f in sorted(os.listdir(target)):
            if f.endswith(".bin"):
                files.append(os.path.join(target, f))
    else:
        files = [target]

    print(f"扫描 {len(files)} 个文件")
    results = []
    total = 0
    for p in files:
        size = os.path.getsize(p)
        if size == 0:
            continue
        total += size
        with open(p, "rb") as fh:
            data = fh.read()
        scan_blob(data, os.path.basename(p), results)
        print(f"  {os.path.basename(p):28s} {size/1e6:8.2f} MB  cumulative hits={len(results)}")

    print(f"\n总扫描 {total/1e6:.1f} MB")
    if not results:
        print("!!! 零命中 !!!")
        return

    print("\n=== 命中 ===")
    for s, enc, label, off in results:
        print(f"  {s:22s} {enc:8s} {label}+0x{off:x}")


if __name__ == "__main__":
    main()
