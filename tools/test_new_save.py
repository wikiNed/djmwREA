#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_save.py / edit_seg2510.py 的离线自检回归。

这是「第一层：离线自检」—— 不需要模拟器、不需要设备，只验产出文件的结构。

为什么这些断言有意义
====================

游戏不读我们的代码，它只读字节。所以自检的目标不是「代码没抛异常」，而是
**产出的字节在游戏眼里的形状和真档一致**：

    [1] 外层：salt/iv 必须与原档相同（docs/19：换 salt/iv -> 黑屏）
    [2] 桶   ：必须带 _Key、string 槽名 == 账号名、条目顺序与真档一致
    [3] 内层：14 段且每段 JSON 合法，DateID 连续 0..13
    [4] 往返：解包再封包字节完全一致（证明没有隐藏的归一化）

其中 [2] 的「桶条目顺序」是最容易默默出错的地方 —— ES3 是按 key 名写 JSON
对象，顺序有意义（真档是 _Key 打头）。

用法（工作目录 = 仓库根）
========================
    python tools/test_new_save.py
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import es3save as E  # noqa: E402
from paths import EVIDENCE, TEMPLATES  # noqa: E402

FAILS = []

#: 真机原档：游戏自己写过、确认能读。作为「形状基准」。
DEVICE_ORIG = os.path.join(ROOT, "evidence", "saves", "SaveFile_device_orig.es3")
#: 游戏回写过的档（进游戏后退出产生），也是形状基准
AFTER_ORIG = os.path.join(ROOT, "evidence", "saves", "SaveFile_after_orig.es3")

TEMPLATE_03 = os.path.join(TEMPLATES, "playerDate_03.bin")

#: 沙箱只允许写工作区，跟 test_savedit.py 保持一致
TMPROOT = os.path.join(ROOT, "saves", ".testtmp_new")
CASE = os.path.join(TMPROOT, "case")
os.makedirs(CASE, exist_ok=True)

ACCOUNT = "o2D+pAPsvrXCo74JUkh9jw=="


def check(name, cond, detail=""):
    print("  %-50s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "  <- " + detail))
    if not cond:
        FAILS.append(name)
    return cond


def clean():
    for name in os.listdir(CASE):
        fp = os.path.join(CASE, name)
        try:
            os.remove(fp)
        except OSError:
            pass


def run(script, argv):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + argv,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def bucket_of(path):
    blob = open(path, "rb").read()
    layer1 = E.decrypt_bytes(blob, E.PASSWORD)
    return blob, layer1


def shape(path):
    """提取一个 .es3 的「形状」：salt/iv、桶条目名与类型、段数、每段字段名。"""
    blob, layer1 = bucket_of(path)
    salt, iv = E.salt_iv_of(blob)
    hexstr, obj = E.parse_bucket(layer1)
    entries = [(k, v.get("__type")) for k, v in obj.items()
               if isinstance(v, dict)]
    plain = E.des_decrypt(hexstr, E.DES_KEY).decode("utf-8")
    # ES3 写入的明文可能末尾带 NUL 填充，按 $ 切后逐段解析即可
    segs = [json.loads(x) for x in plain.split("$")]
    return {
        "salt": salt,
        "iv": iv,
        "leading_brace": layer1.lstrip().startswith(b"{"),
        "entries": entries,
        "n_seg": len(segs),
        "field_sets": [frozenset(s.keys()) for s in segs],
        "dateids": [s.get("DateID") for s in segs],
        "plain_len": len(plain),
    }


# ---------------------------------------------------------------- 第一层

def test_new_save_outside():
    """[1] new_save.py 造出来的档，外层与桶的形状必须和真档一致。"""
    print("[1] new_save.py 外层与桶形状")
    if not os.path.exists(TEMPLATE_03):
        print("  (跳过: 缺模板 playerDate_03.bin)")
        return
    if not os.path.exists(DEVICE_ORIG):
        print("  (跳过: 缺真机原档)")
        return

    clean()
    out = os.path.join(CASE, "ns.es3")
    rc, log = run("new_save.py", ["--account", ACCOUNT, "--out", out,
                                  "--verify"])
    check("生成成功", rc == 0, log[-400:])
    if rc != 0:
        return

    ref = shape(DEVICE_ORIG)
    got = shape(out)

    check("14 段", got["n_seg"] == 14, str(got["n_seg"]))
    check("DateID 连续 0..13", got["dateids"] == list(range(14)),
          str(got["dateids"]))
    check("salt 复用原档", got["salt"] == ref["salt"],
          "%s vs %s" % (got["salt"].hex(), ref["salt"].hex()))
    check("iv 复用原档", got["iv"] == ref["iv"],
          "%s vs %s" % (got["iv"].hex(), ref["iv"].hex()))
    check("桶不以 { 开头（ES3 裸形态）", not got["leading_brace"])
    check("桶条目集合与真档一致",
          [k for k, _ in got["entries"]] == [k for k, _ in ref["entries"]],
          "%s\n      vs %s" % (got["entries"], ref["entries"]))
    check("string 槽名 == 账号名",
          [k for k, t in got["entries"] if t == "string"] == [ACCOUNT],
          str([k for k, t in got["entries"] if t == "string"]))


def test_new_save_sets():
    """[2] --set 确实改到目标字段，且不影响其它段。"""
    print("[2] --set 精确改写")
    if not os.path.exists(TEMPLATE_03):
        print("  (跳过: 缺模板)")
        return
    clean()
    base = os.path.join(CASE, "base.es3")
    rc, log = run("new_save.py", ["--account", ACCOUNT, "--out", base])
    if not check("基线生成成功", rc == 0, log[-300:]):
        return

    out = os.path.join(CASE, "set.es3")
    rc, log = run("new_save.py", [
        "--account", ACCOUNT, "--out", out,
        "--set", "13.ZuanShi=123456",
        "--set", "0.TapLevel=7",
    ])
    check("带 --set 生成成功", rc == 0, log[-300:])
    if rc != 0:
        return

    a = shape(base)
    b = shape(out)
    check("段数不变", b["n_seg"] == a["n_seg"])
    check("每段字段集合不变", a["field_sets"] == b["field_sets"],
          "某些段的字段集合被改了")

    segs_a = [json.loads(x) for x in
              E.des_decrypt(E.parse_bucket(bucket_of(base)[1])[0], E.DES_KEY)
              .decode("utf-8").split("$")]
    segs_b = [json.loads(x) for x in
              E.des_decrypt(E.parse_bucket(bucket_of(out)[1])[0], E.DES_KEY)
              .decode("utf-8").split("$")]
    check("13.ZuanShi 改到 123456", segs_b[13]["ZuanShi"] == 123456,
          str(segs_b[13].get("ZuanShi")))
    check("0.TapLevel 改到 7", segs_b[0]["TapLevel"] == 7,
          str(segs_b[0].get("TapLevel")))
    # 只改两个字段，其余段必须逐字段相等
    diff_segs = [i for i in range(14) if segs_a[i] != segs_b[i]]
    check("只有 seg0/seg13 有差异", diff_segs == [0, 13], str(diff_segs))


def test_roundtrip_identity():
    """[3] 解包再封包必须逐字节还原 —— 证明没有隐藏归一化。"""
    print("[3] 解包/封包往返")
    if not os.path.exists(DEVICE_ORIG):
        print("  (跳过: 缺真机原档)")
        return
    clean()
    orig = open(DEVICE_ORIG, "rb").read()
    same = os.path.join(CASE, "same.es3")
    open(same, "wb").write(orig)
    plain = E.read_save(same)
    E.write_save(same, plain, bak=False)
    reblob = open(same, "rb").read()
    check("零改动重封 == 原档", reblob == orig,
          "%d vs %d 字节" % (len(reblob), len(orig)))


# ---------------------------------------------------------------- 第二层

def test_shape_vs_game_written():
    """[4] 交叉验证：new_save 造的档 vs 游戏自己回写的档，结构应当一致。

    值当然不同（模板是满级、live 档是新手），但**形状**必须一样：
    桶条目、段数、每段字段集合。形状一致 => 游戏读我们造的档时走的代码
    路径和读它自己写的档一样。
    """
    print("[4] 交叉验证：与游戏回写档的结构对比")
    if not os.path.exists(TEMPLATE_03) or not os.path.exists(AFTER_ORIG):
        print("  (跳过: 缺模板或游戏回写档)")
        return
    clean()
    out = os.path.join(CASE, "cross.es3")
    rc, log = run("new_save.py", ["--account", ACCOUNT, "--out", out])
    if not check("生成成功", rc == 0, log[-300:]):
        return

    ref = shape(AFTER_ORIG)   # 游戏自己回写的
    got = shape(out)          # 我们造的

    check("段数一致", got["n_seg"] == ref["n_seg"],
          "%d vs %d" % (got["n_seg"], ref["n_seg"]))
    check("DateID 序列一致", got["dateids"] == ref["dateids"],
          "%s vs %s" % (got["dateids"], ref["dateids"]))

    # 每段字段集合逐个比
    for i in range(min(len(got["field_sets"]), len(ref["field_sets"]))):
        ga = got["field_sets"][i]
        ra = ref["field_sets"][i]
        if ga == ra:
            check("seg%-2d 字段集合一致" % i, True)
            continue
        only_us = sorted(ga - ra)
        only_ref = sorted(ra - ga)
        check("seg%-2d 字段集合一致" % i, False,
              "多出 %s / 缺少 %s" % (only_us, only_ref))


def test_no_merge_is_worse():
    """[5] 负例：--no-merge 必须真的缺字段，否则 [4] 是假绿。

    这是防止「补全逻辑没生效但测试通过」的关键对照。docs/22 记录的
    真实缺口是 seg12 的 4 个 TanPai_* 字段。
    """
    print("[5] 负例：--no-merge 应当缺字段（保证 [4] 不是假绿）")
    if not os.path.exists(TEMPLATE_03) or not os.path.exists(AFTER_ORIG):
        print("  (跳过: 缺模板或游戏回写档)")
        return
    clean()
    out = os.path.join(CASE, "nomerge.es3")
    rc, log = run("new_save.py", ["--account", ACCOUNT, "--out", out,
                                  "--no-merge"])
    if not check("生成成功", rc == 0, log[-300:]):
        return

    ref = shape(AFTER_ORIG)
    got = shape(out)
    missing = sorted(ref["field_sets"][12] - got["field_sets"][12])
    check("seg12 确实缺 TanPai_* 4 个字段",
          set(missing) == {"TanPai_IOP", "TanPai_ZCS", "TanPai_DTCS",
                           "TanPai_CZT"},
          str(missing))


def test_edit_seg_shape():
    """[6] edit_seg2510 改完后形状不变，且只动了 seg2/5/10。"""
    print("[6] edit_seg2510 形状保持")
    if not os.path.exists(TEMPLATE_03):
        print("  (跳过: 缺模板)")
        return
    clean()
    base = os.path.join(CASE, "e_base.es3")
    rc, log = run("new_save.py", ["--account", ACCOUNT, "--out", base])
    if not check("基线生成成功", rc == 0, log[-300:]):
        return

    out = os.path.join(CASE, "e_out.es3")
    rc, log = run("edit_seg2510.py", ["--in", base, "--out", out,
                                      "--home-max", "--chests", "--moku"])
    check("三项编辑成功", rc == 0, log[-500:])
    if rc != 0:
        return

    a, b = shape(base), shape(out)
    check("段数不变", b["n_seg"] == a["n_seg"])
    check("桶条目不变", [k for k, _ in a["entries"]] ==
          [k for k, _ in b["entries"]])
    check("salt 不变", a["salt"] == b["salt"])
    check("iv 不变", a["iv"] == b["iv"])

    sa = [json.loads(x) for x in
          E.des_decrypt(E.parse_bucket(bucket_of(base)[1])[0], E.DES_KEY)
          .decode("utf-8").split("$")]
    sb = [json.loads(x) for x in
          E.des_decrypt(E.parse_bucket(bucket_of(out)[1])[0], E.DES_KEY)
          .decode("utf-8").split("$")]
    diff = [i for i in range(14) if sa[i] != sb[i]]
    check("只动了 seg2/seg5/seg10", diff == [2, 5, 10], str(diff))
    check("seg2 家园等级已拉高", sb[2]["JiaYuanLevel"] >= sa[2]["JiaYuanLevel"],
          "%r -> %r" % (sa[2].get("JiaYuanLevel"), sb[2].get("JiaYuanLevel")))
    check("seg5 宝箱全开", sb[5]["BaoXiangIsOpen"] == [1] * 9,
          str(sb[5].get("BaoXiangIsOpen")))


def main():
    test_new_save_outside()
    test_new_save_sets()
    test_roundtrip_identity()
    test_shape_vs_game_written()
    test_no_merge_is_worse()
    test_edit_seg_shape()
    clean()
    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
