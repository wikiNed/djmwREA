#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交叉验证：从零构造的档 vs 游戏自己写的档，逐项比形状。

这是「第二层」的**取证版**（tools/test_new_save.py 里那个是断言版）。
断言版只说 PASS/FAIL；这个脚本把每一项差异都打出来，方便：

  - 换一份新模板/新参考档之后，看一眼差在哪
  - 提交前人工确认「形状差异」都是已知的、可解释的

用法:
    python tools/cross_check_shape.py
    python tools/cross_check_shape.py --generated work/live/x.es3
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import es3save as E  # noqa: E402
from paths import TEMPLATES  # noqa: E402

#: 游戏自己写过 = 形状基准（按可信度排序）
REF_CANDIDATES = (
    os.path.join(ROOT, "evidence", "saves", "SaveFile_after_orig.es3"),
    os.path.join(ROOT, "evidence", "saves", "SaveFile_device_orig.es3"),
    os.path.join(ROOT, "evidence", "saves", "SaveFile_after_safe.es3"),
)

TEMPLATE = os.path.join(TEMPLATES, "playerDate_03.bin")
ACCOUNT = "o2D+pAPsvrXCo74JUkh9jw=="


def segs_of_plain(path):
    txt = open(path, "rb").read().decode("utf-8")
    return [json.loads(x) for x in txt.split("$")]


def segs_of_es3(path):
    plain = E.read_save(path)
    txt = plain.decode("utf-8") if isinstance(plain, bytes) else plain
    return [json.loads(x) for x in txt.split("$")]


def bucket_entries(path):
    """桶里的 (条目名, __type, 长度/值) —— 形状的另一个维度。"""
    blob = open(path, "rb").read()
    layer1 = E.decrypt_bytes(blob, E.PASSWORD)
    _, obj = E.parse_bucket(layer1)
    out = []
    for k, v in obj.items():
        if not isinstance(v, dict):
            continue
        t = v.get("__type")
        val = v.get("value")
        if t == "string":
            out.append((k, t, len(val) if isinstance(val, str) else -1))
        else:
            out.append((k, t, val))
    return out


def diff_segs(label, got, ref):
    print("\n--- %s ---" % label)
    ok = True
    for i in range(14):
        g, r = set(got[i]), set(ref[i])
        extra, miss = sorted(g - r), sorted(r - g)
        if not extra and not miss:
            continue
        ok = False
        print("  seg%-2d 多 %s / 缺 %s" % (i, extra or "无", miss or "无"))
    if ok:
        print("  14 段字段集合完全一致")
    return ok


def first_ref():
    for p in REF_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated", default=None,
                    help="要检查的 .es3；不给则现场用 new_save.py 生成")
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "live",
                                                  "_cross.es3"))
    a = ap.parse_args()

    ref_path = first_ref()
    if ref_path is None:
        raise SystemExit("找不到游戏写的参考档")
    print("基准档 : %s" % ref_path)
    ref = segs_of_es3(ref_path)

    gen = a.generated
    if gen is None:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import new_save  # noqa: E402
        for p in (a.out,):
            d = os.path.dirname(p)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
        argv = ["--account", ACCOUNT, "--out", a.out]
        rc = new_save.main(argv)
        if rc != 0:
            raise SystemExit("生成失败")
        gen = a.out
    print("待检查 : %s" % gen)

    got = segs_of_es3(gen)

    print("\n=========== 段字段集合 ===========")
    seg_ok = diff_segs("generated vs %s" % os.path.basename(ref_path),
                       got, ref)

    print("\n=========== 桶条目 ===========")
    eb_ref = bucket_entries(ref_path)
    eb_got = bucket_entries(gen)
    print("  %-40s %-8s %s" % ("基准条目", "type", "长度/值"))
    for k, t, v in eb_ref:
        print("  %-40s %-8s %s" % (k[:40], t, v))
    print("  ---")
    print("  %-40s %-8s %s" % ("待查条目", "type", "长度/值"))
    for k, t, v in eb_got:
        print("  %-40s %-8s %s" % (k[:40], t, v))
    names_ref = [k for k, t, _ in eb_ref]
    names_got = [k for k, t, _ in eb_got]
    types_ref = [t for _, t, _ in eb_ref]
    types_got = [t for _, t, _ in eb_got]
    print("  条目名一致: %s" % (names_ref == names_got))
    print("  类型序列一致: %s" % (types_ref == types_got))

    print("\n=========== 外层 ===========")
    b_ref = open(ref_path, "rb").read()
    b_got = open(gen, "rb").read()
    s1, i1 = E.salt_iv_of(b_ref)
    s2, i2 = E.salt_iv_of(b_got)
    print("  基准 salt/iv : %s / %s" % (s1.hex(), i1.hex()))
    print("  待查 salt/iv : %s / %s" % (s2.hex(), i2.hex()))
    print("  salt 一致: %s   iv 一致: %s" % (s1 == s2, i1 == i2))
    print("  文件大小 : %d vs %d" % (len(b_ref), len(b_got)))
    print("  注：salt/iv 与文件大小**不应当**一致 —— 基准档是游戏自己回写的"
          "（新随机 salt），而我们复用 device_orig 的 salt（docs/19 要求）。")
    print("      大小差主要来自内层明文长度（模板是满级档，比新手档大）。")

    # 真正的硬性检查：我们这份的 salt/iv 必须来自 baseline，而不是随机
    base = os.path.join(ROOT, "evidence", "saves", "SaveFile_device_orig.es3")
    outer_ok = True
    if os.path.exists(base):
        bs, bi = E.salt_iv_of(open(base, "rb").read())
        outer_ok = (bs, bi) == (s2, i2)
        print("  salt/iv 来自 %s: %s"
              % (os.path.basename(base), outer_ok))

    print("\n=========== 结论 ===========")
    if seg_ok and names_ref == names_got and types_ref == types_got and outer_ok:
        print("  形状一致：14 段字段集合、桶条目名与类型、外层 salt/iv 来源全部符合")
        print("  （值不同是预期的：模板是满级档，基准是新手档）")
        return 0
    print("  形状有差异，见上。已知可解释的差异写在 docs/22")
    return 1


if __name__ == "__main__":
    sys.exit(main())
