# -*- coding: utf-8 -*-
"""用 input text 填账号/密码/验证码（ASCII 可靠）。"""
import subprocess, time

ADB = r'E:\Program Files\Netease\MuMu\nx_main\adb.exe'
DEV = '127.0.0.1:16384'


def sh(*a):
    subprocess.run([ADB, '-s', DEV, 'shell'] + list(a), capture_output=True)


def fill(x, y, text):
    sh('input', 'tap', str(x), str(y))
    time.sleep(1.0)
    sh('input', 'keyevent', '123')          # MOVE_END
    time.sleep(0.3)
    for _ in range(30):
        sh('input', 'keyevent', '67')       # DEL
    time.sleep(0.5)
    sh('input', 'text', text)
    time.sleep(0.8)


sh('input', 'tap', '540', '540')
time.sleep(0.8)
fill(540, 770, 'nw2026czzqq.com')
sh('input', 'tap', '540', '540')
time.sleep(0.8)
fill(500, 900, 'a123456')
sh('input', 'tap', '540', '540')
time.sleep(0.8)
fill(415, 1080, '000000')
sh('input', 'tap', '540', '540')
time.sleep(0.8)
sh('input', 'tap', '540', '1210')
time.sleep(0.6)
sh('input', 'tap', '540', '1210')
print('done')