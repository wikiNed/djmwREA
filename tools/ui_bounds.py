# -*- coding: utf-8 -*-
"""Parse uiautomator dump for realname widget bounds."""
import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else r'E:\DSH\game\djmwREA\work\live\u2.xml'
raw = open(path, 'rb').read()
if raw[:2] in (b'\xff\xfe', b'\xfe\xff') or raw[:1] == b'\x00':
    s = raw.decode('utf-16', 'replace')
else:
    try:
        s = raw.decode('utf-8', 'replace')
    except Exception:
        s = raw.decode('utf-16', 'replace')
pat = re.compile(r'<node\b[^>]*>')
for m in pat.finditer(s):
    tag = m.group(0)
    rid = re.search(r'resource-id="([^"]*)"', tag)
    if not rid:
        continue
    r = rid.group(1)
    if not any(k in r for k in ('et_name', 'et_identify', 'et_phone', 'bt_submit')):
        continue
    b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
    if b:
        x1, y1, x2, y2 = map(int, b.groups())
        print('%-40s center=(%d,%d) bounds=[%d,%d][%d,%d]' %
              (r, (x1 + x2) // 2, (y1 + y2) // 2, x1, y1, x2, y2))
