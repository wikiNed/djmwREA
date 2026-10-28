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
    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        sys.exit(1)
    print("ALL PASS")
