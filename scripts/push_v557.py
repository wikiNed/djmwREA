#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一份存档推到模拟器里的 v5.5.7 账号目录（含 SELinux label 修复）。

用法:
  python scripts/push_v557.py <本地存档> [账号]

会依次：
  1) force-stop 游戏
  2) adb push 到 /data/local/tmp/s.save
  3) su 0 cp 到 files/<账号>
  4) chown / chmod / chcon（媒体存储 MLS 类别，缺了游戏读不到）
  5) 校验远端 md5 == 本地 md5
"""
import hashlib
import os
import subprocess
import sys

ADB = r"E:\Program Files\Netease\MuMu\nx_main\adb.exe"
SERIAL = "127.0.0.1:16384"
PKG = "com.HQGAMES.TopDemons"
FILES = "/storage/emulated/0/Android/data/com.HQGAMES.TopDemons/files"
DEFAULT_ACCOUNT = "nw2026czzqq.com"
#: 媒体存储文件的完整 SELinux 上下文（su 0 cp 出来的文件缺 MLS 类别）
SELINUX = "u:object_r:media_rw_data_file:s0:c45,c256,c512,c768"
UID = "u0_a45"
GID = "ext_data_rw"


def sh(cmd, check=True):
    p = subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError("adb shell 失败: %s\n%s" % (cmd, p.stderr))
    return (p.stdout or "") + (p.stderr or "")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    account = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACCOUNT
    dst = "%s/%s" % (FILES, account)

    local_md5 = hashlib.md5(open(src, "rb").read()).hexdigest()
    print("本地 : %s (%d 字节) md5=%s"
          % (src, os.path.getsize(src), local_md5))

    print(sh("am force-stop %s" % PKG).strip() or "  (已停止游戏)")
    p = subprocess.run([ADB, "-s", SERIAL, "push", src, "/data/local/tmp/s.save"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        raise RuntimeError("adb push 失败:\n%s" % p.stderr)

    print(sh("su 0 cp /data/local/tmp/s.save %s" % dst).strip() or "  cp ok")
    print(sh("su 0 chown %s:%s %s" % (UID, GID, dst)).strip() or "  chown ok")
    print(sh("su 0 chmod 660 %s" % dst).strip() or "  chmod ok")
    print(sh("su 0 chcon %s %s" % (SELINUX, dst)).strip() or "  chcon ok")
    print(sh("rm -f /data/local/tmp/s.save").strip())

    print(sh("ls -laZ %s" % dst).strip())
    remote = sh("su 0 md5sum %s" % dst).strip()
    print("远端 md5: %s" % remote)
    ok = remote.split()[0].lower() == local_md5
    print("校验: %s" % ("通过 ✓" if ok else "失败 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())