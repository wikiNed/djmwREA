"""
逆向游戏的 double 格式化规则 —— 为「逐字节无损」目标服务。

已知样本（原文 = 游戏输出）:
    0.06608333438634873      (17 sig)
    0.19748541712760926      (17 sig)
    1.5413264036178589       (17 sig)
    2.4295361042022707       (17 sig)
    0.031873904168605807     (17 sig)
    0.43227869272232058      (17 sig)
    5.08809232711792         (15 sig)
    0.03304791450500488      (16 sig)
    76.2875747680664         (15 sig)
    64.51526641845703        (16 sig)
    0.3181036412715912       (16 sig)

结论待验证: 游戏使用的是 .NET Framework 的 "G15" 规则吗？还是 shortest?
    1.5413264036178589 -> G15 = 1.54132640361786 (不是)
故怀疑是 shortest-round-trip, 但 Python 的 repr 在少数情况下给出不同结果,
因为 Python 3 使用 David Gay / Grisu 的 shortest, 而 .NET Core 3+ 使用 Ryu。
两者都"最短且可复原", 但可能有多个等长表示, 选择不同。

本脚本: 对给定原文字符串, 检查每个浮点 token,
    - 若 float(token) 的 repr 与 token 不同, 记为"游戏格式≠Python格式"
    - 记录游戏 token 的有效位数分布
"""
import re
import json
import sys
from collections import Counter

SAVES = r"E:\DSH\game\.rea-study\saves"

# 匹配 JSON 中的浮点/整数字面量
NUM = re.compile(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')


def float_tokens(text):
    """返回原文中所有带小数点的数字 token 及其上下文。"""
    out = []
    for m in NUM.finditer(text):
        tok = m.group()
        if "." in tok or "e" in tok.lower():
            out.append(tok)
    return out


def sig_digits(tok):
    """有效数字位数（去掉前导 0 与小数点）。"""
    s = tok.lstrip("-").replace(".", "")
    s = s.lstrip("0")
    s = re.sub(r"[eE].*$", "", s)
    return len(s.rstrip("0")) if s.rstrip("0") else len(s)


def main(files):
    all_tokens = []
    for f in files:
        t = open(f, encoding="utf-8").read()
        all_tokens += float_tokens(t)

    print(f"浮点 token 总数: {len(all_tokens)}")
    uniq = list(dict.fromkeys(all_tokens))
    print(f"去重后: {len(uniq)}")

    dist = Counter(sig_digits(t) for t in all_tokens)
    print("\n有效数字位数分布:")
    for k in sorted(dist):
        print(f"  {k:2d} 位: {dist[k]:6d}")

    # 关键检验: Python repr 能否复原原文
    mismatch = []
    for t in uniq:
        r = repr(float(t))
        if r != t:
            mismatch.append((t, r))
    print(f"\nPython repr 与原文不一致的独立值: {len(mismatch)} / {len(uniq)}")
    for t, r in mismatch[:15]:
        print(f"  原文 {t:24} python {r}")

    # 检验: 原文是否 = %.17g 截尾 / %.16g 截尾
    def trunc_g(x, n):
        s = format(x, f".{n}g")
        if "e" in s:
            return s
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    for n in (15, 16, 17):
        ok = 0
        for t in uniq:
            if trunc_g(float(t), n) == t:
                ok += 1
        print(f"  %.{n}g 复原率: {ok}/{len(uniq)} = {ok/max(1,len(uniq)):.1%}")

    # 检验: 原文精度是否 = 能把该 double 复位的"最短位数"，但用 Gauss 舍入
    n_bits = []
    for t in uniq:
        x = float(t)
        for n in range(1, 18):
            if float(format(x, f".{n}g")) == x:
                n_bits.append((n, t))
                break
    ok = sum(1 for n, t in n_bits if trunc_g(float(t), n) == t)
    print(f"  最短可复位位数 复原率: {ok}/{len(uniq)} = {ok/max(1,len(uniq)):.1%}")


if __name__ == "__main__":
    files = sys.argv[1:] or [rf"{SAVES}\playerDate_0{i}.json" for i in (1, 2, 3)]
    main(files)
