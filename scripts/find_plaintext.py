"""一次性搜所有 rw 大段里的 ES3 明文特征。

依据：ES3 序列化 JSON 的顶层以 `{` 开头，本项目存档是
`{seg0}${seg1}$...${seg13}`，每段含 `"DateID"`。任何时刻写盘前，
这个字符串必然完整存在于托管堆/大对象堆上。

特征选择（按区分度从高到低）：
  '"DateID"'          本项目特有字段名，几乎不可能误报
  'BaoShiSuiPian'     宝石碎片字段
  '"LiBaoIDs"'        福利码字段
  '"HerosDates"'      角色数组字段
  'SaveFile.es3'      路径
若这些都搜不到，再退回 'DateID'、'$' 分隔符组合。
"""

from paths import EMU
import os
import re
import sys

FEATURES = [
    b'"DateID"',
    b'BaoShiSuiPian',
    b'"LiBaoIDs"',
    b'"HerosDates"',
    b'SaveFile.es3',
    b'"SuoYouBaoShiTongJi"',
    b'"HuangJinShu"',
]


def scan_dir(d):
    files = [f for f in os.listdir(d) if f.endswith(".bin")]
    print(f"扫描 {len(files)} 个文件, {sum(os.path.getsize(os.path.join(d, f)) for f in files)/1e6:.1f} MB")
    total = {f: 0 for f in FEATURES}
    samples = {}
    for fn in files:
        p = os.path.join(d, fn)
        with open(p, "rb") as fh:
            data = fh.read()
        for feat in FEATURES:
            c = data.count(feat)
            if c:
                total[feat] += c
                if feat not in samples:
                    i = data.find(feat)
                    lo = max(0, i - 200)
                    hi = min(len(data), i + 600)
                    samples[feat] = (fn, i, data[lo:hi])
    print("\n=== 命中统计 ===")
    for feat, c in total.items():
        print(f"{feat.decode():26s} {c}")
    print("\n=== 首次命中上下文 ===")
    for feat, (fn, off, blob) in samples.items():
        print(f"\n--- {feat.decode()} @ {fn}+0x{off:x} ---")
        try:
            print(blob.decode("utf-8", "replace")[:800])
        except Exception:
            print(blob[:400])
    return total


if __name__ == "__main__":
    scan_dir(sys.argv[1] if len(sys.argv) > 1 else str(EMU / 'dump2'))
