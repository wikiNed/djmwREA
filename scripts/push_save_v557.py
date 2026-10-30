#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把存档推送到旧版 v5.5.7（com.HQGAMES.TopDemons）并修复 SELinux label。

旧版存档路径：/storage/emulated/0/Android/data/com.HQGAMES.TopDemons/files/<账号名>
  例如 test123@qq.com

用法::

    python scripts/push_save_v557.py <local.es3> [--account test123@qq.com]
    python scripts/push_save_v557.py --pull <local_out.es3> [--account ...]

要点：
  1. 先 force-stop，避免游戏覆盖我们推的文件
  2. 用 runcon 切到游戏域再 cp，让 SELinux label 自动继承
  3. 校验 ls -lZ / stat
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PACKAGE = "com.HQGAMES.TopDemons"
REMOTE_DIR = "/storage/emulated/0/Android/data/%s/files" % PACKAGE
GAME_CONTEXT = "u:r:untrusted_app:s0:c44,c256,c512,c768"
ADB_CANDIDATES = [
    r"E:\Program Files\Netease\MuMu\nx_main\adb.exe",
    "adb",
]
SERIAL = "127.0.0.1:16384"
DEFAULT_ACCOUNT = "test123@qq.com"


def find_adb():
    for c in ADB_CANDIDATES:
        if c == "adb" or os.path.exists(c):
            return c
    raise SystemExit("找不到 adb")


def run(adb, *args, check=True, capture=True):
    cmd = [adb, "-s", SERIAL] + list(args)
    r = subprocess.run(cmd, capture_output=capture, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print("命令失败:", " ".join(cmd), file=sys.stderr)
        if r.stdout:
            print(r.stdout, file=sys.stderr)
        if r.stderr:
            print(r.stderr, file=sys.stderr)
    return r


def shell(adb, cmd, check=True):
    return run(adb, "shell", cmd, check=check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("local", help="要推送的本地存档；--pull 时是输出路径")
    ap.add_argument("--account", default=DEFAULT_ACCOUNT)
    ap.add_argument("--pull", action="store_true", help="反向：从设备拉回")
    ap.add_argument("--no-stop", action="store_true", help="不 force-stop")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    adb = find_adb()
    remote = "%s/%s" % (REMOTE_DIR, a.account)

    if a.pull:
        tmp = "/data/local/tmp/_v557_pull.es3"
        print("[1] 复制到 /data/local/tmp")
        shell(adb, "su 0 cp '%s' %s" % (remote, tmp))
        shell(adb, "su 0 chown shell:shell %s" % tmp)
        shell(adb, "su 0 chmod 644 %s" % tmp)
        print("[2] adb pull")
        r = run(adb, "pull", tmp, a.local)
        print(r.stdout or "", r.stderr or "")
        print("[3] 大小:", os.path.getsize(a.local))
        return

    size = os.path.getsize(a.local)
    print("本地存档: %s (%d 字节)" % (a.local, size))
    print("目标路径: %s" % remote)

    if a.dry_run:
        print("[dry-run] 不执行")
        return

    if not a.no_stop:
        print("[1] force-stop")
        shell(adb, "am force-stop %s" % PACKAGE, check=False)
        import time
        time.sleep(2)

    print("[2] push 到 /data/local/tmp")
    r = run(adb, "push", a.local, "/data/local/tmp/_v557_push.es3")
    print("   ", (r.stdout or "").strip())

    print("[3] runcon 切域复制（继承 SELinux label）")
    shell(adb, "su 0 chmod 644 /data/local/tmp/_v557_push.es3")
    copy_cmd = ("su 0 runcon %s sh -c \"cp /data/local/tmp/_v557_push.es3 '%s'\""
                % (GAME_CONTEXT, remote))
    r = shell(adb, copy_cmd, check=False)
    if r.returncode != 0 or (r.stderr and "denied" in r.stderr.lower()):
        print("   runcon 失败，回退到普通 su cp")
        shell(adb, "su 0 cp /data/local/tmp/_v557_push.es3 '%s'" % remote)
        shell(adb, "su 0 restorecon '%s'" % remote, check=False)

    print("[4] 校验")
    r = shell(adb, "su 0 ls -lZ '%s'" % remote, check=False)
    print("   ", (r.stdout or r.stderr or "").strip())
    r = shell(adb, "su 0 stat -c '%%s 字节  owner=%%U:%%G  mode=%%a' '%s'" % remote,
              check=False)
    print("   ", (r.stdout or r.stderr or "").strip())


if __name__ == "__main__":
    main()
