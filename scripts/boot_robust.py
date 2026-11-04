# -*- coding: utf-8 -*-
"""Robust boot: force-stop, launch, poll logcat for the Unity 'Built from' line."""
import subprocess, time, os
from PIL import Image

ADB = r'E:\Program Files\Netease\MuMu\nx_main\adb.exe'
DEV = '127.0.0.1:16384'
MM = r'E:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe'
BASE = r'E:\DSH\game\djmwREA\work\live'


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, 'shell'] + list(a),
                          capture_output=True, text=True)


def snap(n):
    sh('screencap', '-p', '/sdcard/%s.png' % n)
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/%s.png' % n,
                    BASE + '\\' + n + '.png'], capture_output=True)
    return os.path.getsize(BASE + '\\' + n + '.png')


def wait_unity(timeout_s):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = sh('logcat -d | grep -c "Built from"')
        if r.stdout.strip().isdigit() and int(r.stdout.strip()) > 0:
            return time.time() - t0
        time.sleep(10)
    return -1


def boot_cycle(tag, vm_restart=False):
    if vm_restart:
        print('restarting VM...')
        subprocess.run([MM, 'control', '-v', '0', 'shutdown'], capture_output=True)
        time.sleep(25)
        subprocess.run([MM, 'control', '-v', '0', 'launch'], capture_output=True)
        time.sleep(180)
        subprocess.run([ADB, '-s', DEV, 'connect', '127.0.0.1:16384'],
                       capture_output=True)
        # hosts 重绑
        sh('su 0 mount --bind /data/local/tmp/hosts.new /system/etc/hosts')
    else:
        sh('am force-stop com.HQGAMES.TopDemons')
        time.sleep(60)
    sh('logcat -c')
    sh('am start -n com.HQGAMES.TopDemons/com.unity3d.player.UnityPlayerActivity')
    dt = wait_unity(420)
    print(tag, 'unity boot after %ss' % dt if dt > 0 else 'TIMEOUT')
    if dt > 0:
        time.sleep(90)
        sz = snap(tag + '_shot')
        print('shot', sz)
        return sz > 120000
    return False


ok = boot_cycle('c1')
if not ok:
    ok = boot_cycle('c2', vm_restart=True)
print('RESULT:', ok)
