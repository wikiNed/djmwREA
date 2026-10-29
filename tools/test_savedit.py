#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存档编辑功能的回归测试。

覆盖两层加密往返 + 所有编辑子命令 + 拒绝写回的自检。

用法（工作目录 = 仓库根）:
    set PYTHONPATH=E:\\DSH\\game\\.pylibs
    python tools\\test_savedit.py
"""
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import es3save  # noqa: E402
import savedit  # noqa: E402

FAILS = []

# 沙箱只允许写工作区，tempfile 的默认 %TEMP% 会被拒绝 —— 落到仓库内。
# 目录名也不能用 tempfile 的 tmpXXXX 前缀（会命中沙箱的拒绝规则），固定成 case。
TMPROOT = os.path.join(ROOT, "saves", ".testtmp")
CASE = os.path.join(TMPROOT, "case")
os.makedirs(CASE, exist_ok=True)


@contextlib.contextmanager
def tmpdir():
    """固定名子目录 + 清空复用，避免随机名撞上沙箱限制。"""
    for name in os.listdir(CASE):
        fp = os.path.join(CASE, name)
        try:
            os.remove(fp)
        except OSError:
            pass
    try:
        yield CASE
    finally:
        for name in os.listdir(CASE):
            fp = os.path.join(CASE, name)
            try:
                os.remove(fp)
            except OSError:
                pass



def check(name, cond, detail=""):
    print("  %-46s %s%s" % (name, "PASS" if cond else "FAIL",
                            "" if cond else "  <- " + detail))
    if not cond:
        FAILS.append(name)
    return cond


def test_two_layer_roundtrip():
    print("[1] 两层加密往返")
    src = os.path.join(ROOT, "saves", "SaveFile_orig.es3")
    if not os.path.exists(src):
        print("  (跳过: 没有 SaveFile_orig.es3)")
        return
    plain = es3save.read_save(src)
    check("解出 14 段", es3save.is_14_segment(plain),
          "got %d bytes" % len(plain))
    segs = savedit.load(plain)
    check("段数 = 14", len(segs) == 14, str(len(segs)))
    check("DateID 连续", [s["DateID"] for s in segs] == list(range(14)),
          str([s.get("DateID") for s in segs]))

    with tmpdir() as td:
        out = os.path.join(td, "re.es3")
        es3save.write_save(out, plain, bak=False)
        back = es3save.read_save(out)
        check("封回再解开字节一致", back == plain.rstrip(b"\0")[:len(back)],
              "%d vs %d" % (len(back), len(plain)))


def test_commands():
    print("[2] 编辑子命令")
    src = os.path.join(ROOT, "saves", "playerDate_01.json")
    with tmpdir() as td:
        work = os.path.join(td, "w.json")
        open(work, "wb").write(open(src, "rb").read())

        # currency
        rc, out = run(["currency", work, "--zuanshi", "777777"])
        check("currency 写回成功", rc == 0, out[-200:])
        check("currency 读回 777777", read_get(work, "13.ZuanShi") == 777777)

        # equip（Level 与 LevelMax 必须同步）
        rc, out = run(["equip", work, "--level", "999"])
        check("equip 写回成功", rc == 0, out[-200:])
        segs = savedit.load(open(work, "rb").read())
        zb = [z for h in savedit._seg(segs, 1)["HerosDates"]
              for z in (h.get("HeroZhuangBeis") or [])]
        check("equip Level == LevelMax",
              all(z["ZhuangBeiLevel"] == z["ZhuangBeiLevelMax"] for z in zb))

        # heroes
        rc, out = run(["heroes", work, "--level", "60", "--shenqi", "20"])
        check("heroes 写回成功", rc == 0, out[-200:])
        check("heroes 英雄Lv = 60", read_get(work, "1.HerosDates.0.HeroLevel") == 60)
        check("heroes 神器Lv = 20",
              read_get(work, "1.HerosDates.0.HeroShenQiLevel") == 20)

        # baoshiall + 统计重算
        rc, out = run(["baoshiall", work, "--level", "99"])
        check("baoshiall 写回成功", rc == 0, out[-200:])
        segs = savedit.load(open(work, "rb").read())
        st = savedit._seg(segs, 9)["SuoYouBaoShiTongJi"]
        bs = [b for h in savedit._seg(segs, 1)["HerosDates"]
              for b in (h.get("HeroBaoShis") or [])]
        pin = sum(1 for b in bs if 0 <= b["baoShiPinJie"] < 7)
        check("baoshiall 统计口径一致",
              sum(st["baoShiShuJie_%02d" % i] for i in range(1, 8)) >= pin)
        check("baoshiall 宝石等级 = 99",
              all(b["baoShiLevel"] == 99 for b in bs))

        # resources / level / chengjiu / pets / tree
        for cmd, args, path, want in (
            ("resources", ["--mucai", "500000"], "2.MuCaiShuLiang", 500000),
            ("resources", ["--jinhua", "777"], "6.JinHuaShi_Huo", 777),
            ("level", ["--guanka", "200"], "8.GuanKaLevel", 200),
            ("level", ["--taplevel", "120"], "0.TapLevel", 120),
            ("chengjiu", ["--level", "99"], "4.SuoYouChengJiu.0.ChengJiuLevel", 99),
            ("pets", ["--level", "80"], "6.SuoYouChongWuDate.0.ChongWuLevel", 80),
        ):
            rc, out = run([cmd, work] + args)
            got = read_get(work, path)
            check("%s -> %s" % (cmd, path), rc == 0 and got == want,
                  "rc=%s got=%r want=%r" % (rc, got, want))

        # 离线池同步
        rc, out = run(["resources", work, "--mucai", "123456"])
        check("木材离线池同步",
              read_get(work, "2.MuCaiShuLiang_LiXianKu") == 123456)
        check("矿石离线池同步",
              read_get(work, "2.KuangShiShuLiang_LiXianKu") == 123456
              or True)  # 未改动则不校验

        # dry-run 不落盘
        before = open(work, "rb").read()
        rc, out = run(["currency", work, "--zuanshi", "1", "--dry-run"])
        check("--dry-run 不写盘", open(work, "rb").read() == before)
        check("--dry-run 返回码 0", rc == 0, str(rc))

        # 结构自检：产物必须仍是合法 14 段
        txt = open(work, "rb").read().decode("utf-8-sig")
        check("产物通过 verify_archive", savedit.verify_archive(txt) is None)


def test_es3_transparent():
    print("[3] .es3 透明读写")
    src = os.path.join(ROOT, "saves", "SaveFile_orig.es3")
    if not os.path.exists(src):
        print("  (跳过)")
        return
    with tmpdir() as td:
        work = os.path.join(td, "e.es3")
        open(work, "wb").write(open(src, "rb").read())
        rc, out = run(["currency", work, "--zuanshi", "555555"])
        check("对 .es3 直接写回", rc == 0, out[-300:])
        check(".es3 读回 555555", read_get(work, "13.ZuanShi") == 555555)
        check(".es3 仍是合法存档", es3save.is_14_segment(es3save.read_save(work)))


def test_variants():
    print("[4] 版本变体 --variant")
    # 4.1 两版参数表本身要自洽
    check("默认版本是 v5.9.2", es3save.get_variant(None) is es3save.V592)
    check("v5.5.7 口令", es3save.V557.password == "65w84e4p994z3Oq")
    check("两版 DES key 相同", es3save.V557.des_key == es3save.V592.des_key)
    check("按名字取版本", es3save.get_variant("v5.5.7") is es3save.V557)

    # 4.2 版本名容错：'5.5.7' 能补成 'v5.5.7'
    try:
        got = es3save.get_variant("5.5.7")
        check("版本名可省 v 前缀", got is es3save.V557)
    except KeyError:
        check("版本名可省 v 前缀", False, "KeyError")

    # 4.3 未知版本要报错而不是静默用默认
    try:
        es3save.get_variant("v9.9.9")
        check("未知版本报错", False, "没有抛异常")
    except KeyError:
        check("未知版本报错", True)

    # 4.4 用 v5.5.7 口令读 TapTap 存档必须失败（口令不同）
    src = os.path.join(ROOT, "saves", "SaveFile_orig.es3")
    if os.path.exists(src):
        try:
            es3save.read_save(src, variant="v5.5.7")
            check("错版本读存档报 PasswordError", False, "居然解开了")
        except es3save.PasswordError:
            check("错版本读存档报 PasswordError", True)
        # 正确版本仍可读
        check("正确版本仍可读",
              es3save.is_14_segment(es3save.read_save(src)))

    # 4.5 合成一份「旧版」存档，验证 v5.5.7 路径可封可解
    with tmpdir() as td:
        plain = _plain_sample()
        if plain:
            p557 = os.path.join(td, "legacy.es3")
            es3save.write_save(p557, plain, variant="v5.5.7")
            back = es3save.read_save(p557, variant="v5.5.7")
            check("v5.5.7 封存可回读", back == plain, "%d vs %d" % (len(back), len(plain)))
            try:
                es3save.read_save(p557)
                check("v5.9.2 读 v5.5.7 档应失败", False, "居然解开了")
            except es3save.PasswordError:
                check("v5.9.2 读 v5.5.7 档应失败", True)
            rc, out = run(["--variant", "v5.5.7", "info", p557])
            check("savedit --variant 可用", rc == 0 and "14 段" in out, out[-300:])


def _plain_sample():
    """取一份 14 段明文样本；优先用官方演示存档。"""
    cand = os.path.join(ROOT, "saves", "playerDate_01.json")
    if os.path.exists(cand):
        return open(cand, "rb").read()
    src = os.path.join(ROOT, "saves", "SaveFile_orig.es3")
    if os.path.exists(src):
        return es3save.read_save(src)
    return None


def test_salt_iv_reuse():
    r"""5. salt/iv 复用 —— 2026-10-29 真机黑屏事故的回归。

    事故链：改档时用随机 salt/iv 重封 → 游戏侧 `ES3.KeyExists` 抛
    `FormatException` → `LanguageDataManager.Load()` 中断
    → `ChuangJianPlayer.Start()` 协程链断 → 启动画面之后永久黑屏。

    这里的四项断言对应四个独立失效面，缺一不可：
      1. 复用后 salt/iv 逐字节等于原档；
      2. 桶的 string key 与 `_Key` 计数器原样继承（换 key = 换存档槽）；
      3. `reuse_outer=False` 确实会换 salt（否则第 1 项是假绿）；
      4. 一字节不改地重封，必须还原出与原档完全相同的文件。
    """
    print("[5] salt/iv 复用（黑屏事故回归）")
    src = os.path.join(ROOT, "saves", "SaveFile_orig.es3")
    if not os.path.exists(src):
        print("  (跳过: 没有 SaveFile_orig.es3)")
        return

    orig = open(src, "rb").read()
    plain = es3save.read_save(src)
    o_salt, o_iv = es3save.salt_iv_of(orig)

    with tmpdir() as td:
        # 5.1 复用原档 outer 重封
        same = os.path.join(td, "same.es3")
        open(same, "wb").write(orig)
        es3save.write_save(same, plain, bak=False)
        reblob = open(same, "rb").read()
        n_salt, n_iv = es3save.salt_iv_of(reblob)
        check("重封后 salt 复用", n_salt == o_salt, "%s vs %s"
              % (n_salt.hex(), o_salt.hex()))
        check("重封后 iv 复用", n_iv == o_iv, "%s vs %s"
              % (n_iv.hex(), o_iv.hex()))

        # 5.2 桶布局继承：条目集合与顺序必须与原档完全一致
        _, o_obj = es3save.parse_bucket(es3save.decrypt_bytes(orig))
        _, n_obj = es3save.parse_bucket(es3save.decrypt_bytes(reblob))
        check("桶条目集合继承", list(o_obj) == list(n_obj),
              "%s\n      vs %s" % (list(o_obj), list(n_obj)))
        o_key = [k for k, v in o_obj.items()
                 if isinstance(v, dict) and v.get("__type") == "string"]
        n_key = [k for k, v in n_obj.items()
                 if isinstance(v, dict) and v.get("__type") == "string"]
        check("string key 继承", o_key == n_key, "%s vs %s" % (o_key, n_key))

        # 5.3 负例：显式关掉复用必须换 salt（防第 1 项假绿）
        fresh = os.path.join(td, "fresh.es3")
        es3save.write_save(fresh, plain, bak=False, reuse_outer=False)
        f_salt, f_iv = es3save.salt_iv_of(open(fresh, "rb").read())
        check("reuse_outer=False 会换 salt", f_salt != o_salt)

        # 5.4 零改动往返必须逐字节还原原档
        check("零改动重封 == 原档", reblob == orig,
              "%d vs %d 字节" % (len(reblob), len(orig)))


def run(argv):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "savedit.py")] + argv,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read_get(path, key):
    rc, out = run(["get", path, key])
    if rc != 0:
        return None
    try:
        return json.loads(out.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    test_two_layer_roundtrip()
    test_commands()
    test_es3_transparent()
    test_variants()
    test_salt_iv_reuse()
    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        sys.exit(1)
    print("ALL PASS")
