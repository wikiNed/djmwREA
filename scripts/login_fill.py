# -*- coding: utf-8 -*-
"""清空并填写账号/密码/验证码后登录。"""
import subprocess, time

ADB = r'E:\Program Files\Netease\MuMu\nx_main\adb.exe'
DEV = '127.0.0.1:16384'

ACC = [42, 51, 9, 7, 9, 13, 31, 54, 54, 45, 45, 56, 31, 43, 41]  # nw2026czzqq.com
PWD = [29, 8, 9, 10, 11, 12, 13]                                  # a123456
CAP = [7, 7, 7, 7, 7, 7]                                         # 000000
DEL = 67


def sh(*a):
    subprocess.run([ADB, '-s', DEV, 'shell'] + list(a), capture_output=True)


def keys(codes, gap=0.28):
    for c in codes:
        sh('input', 'keyevent', str(c))
        time.sleep(gap)


def clear_field(x, y, n=24):
    sh('input', 'tap', str(x), str(y))
    time.sleep(0.8)
    sh('input', 'keyevent', '123')   # MOVE_END
    time.sleep(0.3)
    keys([DEL] * n, gap=0.08)


sh('input', 'tap', '540', '540')      # 失焦
time.sleep(0.8)

clear_field(540, 770)
keys(ACC)
time.sleep(0.5)

sh('input', 'tap', '540', '540')
time.sleep(0.8)
clear_field(500, 900)
keys(PWD)
time.sleep(0.5)

sh('input', 'tap', '540', '540')
time.sleep(0.8)
clear_field(415, 1080)
keys(CAP)
time.sleep(0.5)

sh('input', 'tap', '540', '540')
time.sleep(0.8)
sh('input', 'tap', '540', '1210')
time.sleep(0.6)
sh('input', 'tap', '540', '1210')
print('login submitted')