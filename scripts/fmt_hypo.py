"""
推断游戏的 double 文本格式化算法。

--- 已确立的事实（来自 3 个官方演示存档, 372 个带小数点的 token）---
1. 游戏使用"小数整存"格式: 存储的 double 值 = token 的十进制读数本身
   （如 "1.5413264036178589" -> double(1.5413264036178589)）
   而不是 float(1.5413264036178589f) 那种 float32 扩展值。
2. 所以原文字节 == 该 double 的标准 shortest-repr 绝大多数情况相同,
   仅约 34% 的值游戏多输出几位（17 位有效数字）。

--- 本脚本: 用多个假设逐一试算, 看哪个能 100% 复原 ---
H1  Python repr                                  (shortest)
H2  ROUND_HALF_UP @17 sig on repr value
H3  ROUND_HALF_UP @17 sig on exact value
H4  ROUND_HALF_UP on exact value with quantum = ulp/2^24
H5  .NET "R" = shortest-then-17 混合
H6  Java Double.toString 算法 (SciNotation)
"""
from paths import SAVES

import math
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from collections import Counter

getcontext().prec = 80
NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def tokens_with_dot(text):
    return [m.group() for m in NUM.finditer(text) if "." in m.group()]


def trim(s):
    """去掉多余尾随 0, 保证至少一位小数。"""
    if "." in s:
        s = s.rstrip("0")
        if s.endswith("."):
            s += "0"
    return s


def h1(x):
    return repr(x)


def _rh(x, n, exact=False):
    d = Decimal(x) if exact else Decimal(repr(float(x)))
    if d == 0:
        return "0.0"
    e = d.adjusted()
    q = Decimal(1).scaleb(e - n + 1)
    return trim(format(d.quantize(q, rounding=ROUND_HALF_UP), "f"))


def h2(x):
    return _rh(x, 17, exact=False)


def h3(x):
    return _rh(x, 17, exact=True)


def h4(x):
    """quantum = ulp/2^24  (即保留约 17 位有效数字, 但按二进制 ulp 对齐)"""
    d = Decimal(x)
    if d == 0:
        return "0.0"
    e = d.adjusted()
    ulp = Decimal(2) ** Decimal(e - 15)
    q = ulp / Decimal(2) ** 24
    return trim(format(d.quantize(q, rounding=ROUND_HALF_UP), "f"))


def h5(x):
    """shortest 若不足 17 位则用最短, 否则补齐到 17 位(截断)。"""
    s = repr(float(x))
    if s.endswith(".0"):
        return s
    digits = len(s.replace("-", "").replace(".", "").lstrip("0"))
    if digits >= 17:
        return h3(x)
    return s


def h6(x):
    """Java Double.toString 的简化版（不做全 range 分支, 仅常规范围）。"""
    if x == 0:
        return "0.0"
    neg = x < 0
    a = abs(x)
    if 1e-3 <= a < 1e7:
        s = repr(a)
        if "e" in s:
            s = format(a, "f")
        return ("-" if neg else "") + trim(s)
    return repr(x)


HYPOTHESES = {"H1 repr": h1, "H2 RH17-repr": h2, "H3 RH17-exact": h3,
              "H4 RH-ulp/2^24": h4, "H5 shortest-or-RH17": h5, "H6 java": h6}


def main():
    toks = []
    for i in (1, 2, 3):
        t = open(rf"{SAVES}\playerDate_0{i}.json", encoding="utf-8").read()
        toks += tokens_with_dot(t)
    uniq = list(dict.fromkeys(toks))
    print(f"token 总数 {len(toks)}, 独立值 {len(uniq)}\n")

    for name, fn in HYPOTHESES.items():
        ok = 0
        bad = []
        for tk in uniq:
            try:
                if fn(float(tk)) == tk:
                    ok += 1
                else:
                    bad.append(tk)
            except Exception as e:
                bad.append(tk)
        print(f"{name:22} 复原率 {ok}/{len(uniq)} = {ok/len(uniq):.1%}")
        if bad and len(bad) <= 12:
            for b in bad:
                print(f"      miss {b}")

    # 关键统计: 原文位数 vs Python repr 位数
    print("\n原文有效位数 vs Python repr 有效位数:")
    c = Counter()
    for tk in uniq:
        a = len(tk.replace("-", "").replace(".", "").lstrip("0").rstrip("0"))
        r = repr(float(tk)).replace("-", "").replace(".", "")
        b = len(r.lstrip("0").rstrip("0"))
        c[(b, a)] += 1
    for (b, a), n in sorted(c.items()):
        print(f"   python {b:2d} 位 -> 原文 {a:2d} 位 : {n}")


if __name__ == "__main__":
    main()
