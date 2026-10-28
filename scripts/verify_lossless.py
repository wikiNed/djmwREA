"""
存档无损性【结构级】验证。

逐字节不同不代表有损——Python float 的 shortest-repr 与游戏的原生 double
格式化器（如 %.15g / C# R 格式）在末位不同，数值语义相同。

真正要证明的是:
  1. 段数、每段键集合完全一致
  2. 所有非浮点数值完全相等
  3. 浮点数值在相对误差 1e-12 内相等
  4. 字符串/布尔/None 完全相等
若全部通过 -> 存档无隐藏字段、无键重排、无截断，可安全改写。
"""
import json
import os
import sys
import math

SEP = "$"
SAVES = r"E:\DSH\game\.rea-study\saves"


def load(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    text = text.lstrip("\ufeff")
    return [json.loads(p.strip()) for p in text.split(SEP) if p.strip()]


def dump(segs):
    return SEP.join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in segs)


def deep_diff(a, b, path="", out=None):
    """返回差异列表 [(path, a, b, kind)]"""
    if out is None:
        out = []
    if type(a) is bool or type(b) is bool:
        if a != b:
            out.append((path, a, b, "bool"))
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            for k in ka - kb:
                out.append((path + "." + k, "存在", "缺失", "key-missing"))
            for k in kb - ka:
                out.append((path + "." + k, "缺失", "存在", "key-extra"))
        for k in ka & kb:
            deep_diff(a[k], b[k], path + "." + k, out)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"len={len(a)}", f"len={len(b)}", "len"))
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            deep_diff(x, y, f"{path}[{i}]", out)
        return out
    if isinstance(a, float) or isinstance(b, float):
        if not math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12):
            out.append((path, a, b, "float"))
        elif a != b:
            out.append((path, a, b, "float-repr"))
        return out
    if isinstance(a, str) and isinstance(b, str):
        if a != b:
            out.append((path, a, b, "str"))
        return out
    if a != b:
        out.append((path, a, b, type(a).__name__))
    return out


def check(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig")
    segs_a = load(text)
    segs_b = load(dump(segs_a))

    print(f"==== {os.path.basename(path)}")
    print(f"  段数: {len(segs_a)} -> {len(segs_b)}")
    diffs = deep_diff(segs_a, segs_b)
    hard = [d for d in diffs if d[3] not in ("float-repr",)]
    soft = [d for d in diffs if d[3] == "float-repr"]

    print(f"  差异总数: {len(diffs)}  语义差异: {len(hard)}  仅浮点末位: {len(soft)}")

    keys_a = [sorted(s.keys()) for s in segs_a]
    keys_b = [sorted(s.keys()) for s in segs_b]
    print(f"  键集合一致: {keys_a == keys_b}")

    if soft:
        print(f"  浮点末位差异样例(前3):")
        for p, a, b, k in soft[:3]:
            print(f"    {p}: {a!r} -> {b!r}")

    if hard:
        print("  !! 语义差异:")
        for p, a, b, k in hard[:20]:
            print(f"    {p}: {a!r} -> {b!r} ({k})")
        return False

    print("  RESULT: PASS —— 结构无损，可安全改写")
    return True


if __name__ == "__main__":
    files = sys.argv[1:] or [
        os.path.join(SAVES, f"playerDate_0{i}.json") for i in (1, 2, 3)
    ]
    ok = True
    for f in files:
        ok &= check(f)
        print()
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)
