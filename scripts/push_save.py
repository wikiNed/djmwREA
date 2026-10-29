#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地存档推送到 Android 设备。

为什么需要这个脚本
==================
`adb push` 会把文件的 SELinux label 写成 ``u:object_r:storage_file:s0``，
在 Android 11+ 的 ``/storage/emulated/0/Android/data/`` 下，游戏进程
（``u:r:untrusted_app:s0:c42,c256,c512,c768``）会因 MLS 类别不匹配而
**读不到**自己刚收到的存档。表现是：文件明明在、大小正确，游戏却像
没看见一样用旧档。

正确做法（2026-10-29 在 MuMu 12 / Android 12 上实测）
------------------------------------------------------
1. ``adb push`` 到 ``/data/local/tmp/``（这里是 ``shell:s0``，无所谓）；
2. 用游戏的 SELinux 域 + 游戏的 uid 执行 ``cp``::

       su 0 runcon u:r:untrusted_app:s0:c42,c256,c512,c768 \\
           sh -c 'cp /data/local/tmp/x.es3 ".../files/SaveFile.es3"'

   由游戏域自己 `cp` 出来的文件，label 会自动继承目录的
   ``media_rw_data_file:s0:c42,c256,c512,c768``，owner 也是对的。

顺序陷阱
--------
``runcon ... su 10042 ...`` 不行 —— ``su`` 会把域重置回 ``su:s0``。
必须是 ``su 10042 runcon ...``，或者干脆不切 uid、只用 ``runcon``
（实测 root + untrusted_app 域已足够读写该目录）。

另外 ``/storage/emulated/0/Android/data`` 挂载带 ``noatime``，
所以 **atime 不能用来判断"游戏读过没有"**。

用法
----
    python scripts/push_save.py work/live/SaveFile_mod.es3
    python scripts/push_save.py work/live/SaveFile_mod.es3 --dry-run
    python scripts/push_save.py work/live/SaveFile_mod.es3 --pull-back

默认目标路径是游戏的外置数据目录下的 ``SaveFile.es3``。
"""

import argparse
import os
import posixpath
import subprocess
import sys
import tempfile

PACKAGE = "game.taptap.HQGAMES.TapDemons"
REMOTE_DIR = "/storage/emulated/0/Android/data/%s/files" % PACKAGE
REMOTE_SAVE = posixpath.join(REMOTE_DIR, "SaveFile.es3")

# 游戏进程的 SELinux 标签；目录的 label 也是同一组 MLS 类别
GAME_CONTEXT = "u:r:untrusted_app:s0:c42,c256,c512,c768"


def find_adb():
    """按常见安装位置找 adb；找到多个时优先 MuMu 自带的（版本匹配）。"""
    cands = []
    if os.environ.get("ANDROID_HOME"):
        cands.append(os.path.join(os.environ["ANDROID_HOME"], "platform-tools", "adb.exe"))
    for root in (r"E:\Program Files\Netease\MuMu\nx_main",
                 r"C:\Program Files\Netease\MuMu\nx_main",
                 r"D:\Program Files\Netease\MuMu\nx_main"):
        cands.append(os.path.join(root, "adb.exe"))
    cands += ["adb", "adb.exe"]
    for c in cands:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            from shutil import which
            p = which(c)
            if p:
                return p
    raise SystemExit("找不到 adb。请把 MuMu 的 adb.exe 加进 PATH，或设 ANDROID_HOME。")


def find_device(adb):
    """返回单台已连接设备的 serial。"""
    out = subprocess.run([adb, "devices"], capture_output=True, text=True).stdout
    devs = [ln.split("\t")[0] for ln in out.splitlines()[1:] if "\tdevice" in ln]
    if not devs:
        raise SystemExit("没有已连接的设备。先启动 MuMu，再跑：adb connect 127.0.0.1:16384")
    if len(devs) > 1:
        print("!! 检测到多台设备：%s，使用第一台" % devs)
    return devs[0]


def sh(adb, serial, command, timeout=90):
    """在设备上执行 sh 命令，返回 (returncode, stdout, stderr)。"""
    r = subprocess.run([adb, "-s", serial, "shell", command],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def push_save(local_path, remote=REMOTE_SAVE, context=GAME_CONTEXT,
              dry_run=False, verify=True):
    """推送存档并修复 SELinux 上下文。返回 True 表示成功。"""
    if not os.path.isfile(local_path):
        raise SystemExit("本地文件不存在: %s" % local_path)

    adb = find_adb()
    serial = find_device(adb)
    size = os.path.getsize(local_path)
    print("adb     : %s" % adb)
    print("设备    : %s" % serial)
    print("本地    : %s (%d 字节)" % (local_path, size))
    print("目标    : %s" % remote)
    print("SELinux : %s" % context)

    if dry_run:
        print("\n[dry-run] 不实际推送。")
        return True

    # 0) 游戏必须先停下，否则它可能在我们背后覆写存档
    rc, out, err = sh(adb, serial, "am force-stop %s" % PACKAGE)
    if rc != 0:
        print("!! 无法停止游戏: %s" % (err or out))
    print("\n[1] 已停止游戏")

    # 1) 传到 tmp —— 这里 shell:s0 无所谓，下一步由游戏域复制
    tmp_remote = "/data/local/tmp/_rea_push.es3"
    r = subprocess.run([adb, "-s", serial, "push", local_path, tmp_remote],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("push 失败: %s" % r.stderr.strip())
    print("[2] 已上传到 %s" % tmp_remote)

    # 2) 让游戏域自己去 cp —— 这样 label 会自动继承目录
    cp_cmd = "runcon %s sh -c 'cp %s \"%s\"'" % (context, tmp_remote, remote)
    rc, out, err = sh(adb, serial, "su 0 " + cp_cmd)
    if rc != 0:
        raise SystemExit("游戏域复制失败: %s" % (err or out))
    print("[3] 已用游戏域覆盖目标文件")

    if not verify:
        return True

    # 3) 校验：大小、owner、SELinux label 三项都要对
    rc, out, err = sh(adb, serial, "su 0 ls -lZ \"%s\"" % remote)
    print("[4] 设备端状态: %s" % out)
    want = ("media_rw_data_file", "u0_a42")
    ok = all(w in out for w in want)
    if not ok:
        print("!! label/owner 看起来不对，期望包含 %s" % (want,))

    rc, out2, _ = sh(adb, serial, "su 0 stat -c %%s \"%s\"" % remote)
    if out2.strip() == str(size):
        print("[5] 大小一致: %s 字节" % out2.strip())
    else:
        print("!! 大小不一致: 设备 %s / 本地 %d" % (out2.strip(), size))
        ok = False

    sh(adb, serial, "su 0 rm -f %s" % tmp_remote)
    return ok


def pull_save(local_path, remote=REMOTE_SAVE):
    """从设备拉回存档（root 身份，绕过 scoped storage）。

    陷阱：如果只是 ``su 0 cp``，复制出来的文件属于 root、label 为
    ``su:s0`` 的临时类型，``adb pull``（以 shell 用户运行）读不到，
    报 ``remote open failed: Permission denied``。所以复制完必须
    ``chown shell:shell`` + ``chmod 644``。
    """
    adb = find_adb()
    serial = find_device(adb)
    tmp_local = os.path.join(tempfile.gettempdir(), "_rea_pull.es3")
    tmp_remote = "/data/local/tmp/_rea_pull.es3"
    rc, out, err = sh(adb, serial,
                      "su 0 sh -c 'cp \"%s\" %s && chown shell:shell %s && chmod 644 %s'"
                      % (remote, tmp_remote, tmp_remote, tmp_remote))
    if rc != 0:
        raise SystemExit("设备端复制失败: %s" % (err or out))
    r = subprocess.run([adb, "-s", serial, "pull", tmp_remote, tmp_local],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("pull 失败: %s" % r.stderr.strip())
    os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
    with open(tmp_local, "rb") as f:
        data = f.read()
    with open(local_path, "wb") as f:
        f.write(data)
    sh(adb, serial, "su 0 rm -f %s" % tmp_remote)
    print("已拉回: %s (%d 字节)" % (local_path, len(data)))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(
        description="把存档安全地推送到 Android 设备（修复 adb push 的 SELinux label 问题）")
    p.add_argument("archive", help="本地存档路径（.es3 或明文 .json）")
    p.add_argument("--remote", default=REMOTE_SAVE, help="设备上的目标路径")
    p.add_argument("--context", default=GAME_CONTEXT, help="游戏进程的 SELinux 上下文")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不实际推送")
    p.add_argument("--pull-back", action="store_true", help="推送成功后立刻拉回一份做对比")
    p.add_argument("--no-verify", action="store_true", help="跳过推送后的校验")
    a = p.parse_args(argv)

    ok = push_save(a.archive, remote=a.remote, context=a.context,
                   dry_run=a.dry_run, verify=not a.no_verify)
    print("\n结果: %s" % ("OK" if ok else "FAILED"))

    if ok and a.pull_back and not a.dry_run:
        base = os.path.splitext(a.archive)[0]
        pull_save(base + ".roundtrip.es3", remote=a.remote)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
