# -*- coding: utf-8 -*-
"""Fill the native realname dialog (name/id/phone) and submit; verify."""
import subprocess, time, re, os

ADB = r'E:\Program Files\Netease\MuMu\nx_main\adb.exe'
DEV = '127.0.0.1:16384'
BASE = r'E:\DSH\game\djmwREA\work\live'

NAME = '张三'
IDNO = '110101199001010015'
PHONE = '13800138000'


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, 'shell'] + list(a),
                          capture_output=True, text=True, encoding='utf-8', errors='replace')


def dump():
    sh('uiautomator dump /sdcard/u.xml')
    r = subprocess.run([ADB, '-s', DEV, 'shell', 'cat', '/sdcard/u.xml'],
                       capture_output=True)
    raw = r.stdout
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16', 'replace')
    return raw.decode('utf-8', 'replace')


def fields(xml):
    out = {}
    for m in re.finditer(r'<node\b[^>]*>', xml):
        t = m.group(0)
        rid = re.search(r'resource-id="([^"]*)"', t)
        if not rid:
            continue
        key = rid.group(1).split('/')[-1]
        if key not in ('et_name', 'et_identify', 'et_phone', 'bt_submit'):
            continue
        txt = re.search(r'text="([^"]*)"', t)
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        cx = cy = None
        if b:
            x1, y1, x2, y2 = map(int, b.groups())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        out[key] = (txt.group(1) if txt else '', cx, cy)
    return out


x = dump()
f = fields(x)
if 'et_name' not in f:
    print('NO realname dialog on screen')
    raise SystemExit(0)

for key, val in (('et_name', NAME), ('et_identify', IDNO), ('et_phone', PHONE)):
    if key not in f:
        continue
    cur, cx, cy = f[key]
    if cur == val:
        print(key, 'already', val)
        continue
    sh('input', 'tap', str(cx), str(cy))
    time.sleep(1.0)
    # 清空：全选删除
    sh('input', 'keyevent', '123')      # MOVE_END
    for _ in range(len(cur) + 4):
        sh('input', 'keyevent', '67')   # DEL
    time.sleep(0.6)
    sh('input', 'text', val)
    time.sleep(1.0)

f2 = fields(dump())
for k in ('et_name', 'et_identify', 'et_phone'):
    print(k, '=', repr(f2.get(k, ('?',))[0]))

cx, cy = f2['bt_submit'][1], f2['bt_submit'][2]
sh('input', 'tap', str(cx), str(cy))
time.sleep(4)

after = fields(dump())
print('dialog still present:', 'et_name' in after)
