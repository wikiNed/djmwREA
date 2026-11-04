# -*- coding: utf-8 -*-
"""反复重试启动直到 Unity 出 'Built from'。"""
import subprocess, time

ADB = r'E:\Program Files\Netease\MuMu\nx_main\adb.exe'
DEV = '127.0.0.1:16384'
MM = r'E:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe'


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, 'shell'] + list(a),
                          capture_output=True, text=True)


def built():
    r = sh('logcat -d | grep -c "Built from"')
    try:
        return int(r.stdout.strip()) > 0
    except Exception:
        return False


def try_once(tag):
    sh('am force-stop com.HQGAMES.TopDemons')
    time.sleep(20)
    sh('logcat -c')
    sh('am start -n com.HQGAMES.TopDemons/com.unity3d.player.UnityPlayerActivity')
    for i in range(30):
        time.sleep(10)
        if built():
            print(tag, 'BOOTED after', (i + 1) * 10, 's', flush=True)
            return True
    print(tag, 'timeout', flush=True)
    return False


for k in range(1, 9):
    if try_once('try%d' % k):
        break
    if k % 3 == 0:
        print('vm restarting...', flush=True)
        subprocess.run([MM, 'control', '-v', '0', 'shutdown'], capture_output=True)
        time.sleep(25)
        subprocess.run([MM, 'control', '-v', '0', 'launch'], capture_output=True)
        time.sleep(180)
        subprocess.run([ADB, '-s', DEV, 'connect', '127.0.0.1:16384'],
                       capture_output=True)
print('DONE', flush=True)