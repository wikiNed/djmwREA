# -*- coding: utf-8 -*-
"""用手机原版 APK + 打好补丁的 64 位 libil2cpp.so 拼出新的 APK（未签名）。

手机是 arm64-only，所以我们手里那份只有 armeabi-v7a 的包装不上；
这里改成「拿手机自己的 base.apk 当底，只替换 lib/arm64-v8a/libil2cpp.so」。

用法：
    python build_apk64.py [--lib 路径] [--out 路径]
"""
import argparse
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = r'E:\DSH\game\work'
BASE = os.path.join(WORK, 'phone64', 'base.apk')
LIB = os.path.join(WORK, 'patched', 'libil2cpp_64_patched.so')
TARGET = 'lib/arm64-v8a/libil2cpp.so'
OUT = os.path.join(WORK, 'patched', 'djmw_5.5.7_phone64_unsigned.apk')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=BASE)
    ap.add_argument('--lib', default=LIB)
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()

    lib = open(a.lib, 'rb').read()
    print('补丁 lib: %s  %d B  MD5 %s' % (a.lib, len(lib), hashlib.md5(lib).hexdigest()))

    with zipfile.ZipFile(a.base) as zin:
        infos = zin.infolist()
        out = zipfile.ZipFile(a.out, 'w')
        replaced = 0
        for info in infos:
            nm = info.filename
            data = lib if nm == TARGET else zin.read(nm)
            if nm == TARGET:
                replaced += 1
                print('替换 %s: %d B -> %d B' % (nm, info.file_size, len(data)))
            zi = zipfile.ZipInfo(nm, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            out.writestr(zi, data)
        out.close()
    if replaced != 1:
        print('!!! 没找到/重复 %s（%d 次）' % (TARGET, replaced))
        return 1
    print('已写出 %s  %d B  MD5 %s' % (a.out, os.path.getsize(a.out),
                                       hashlib.md5(open(a.out, 'rb').read()).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
