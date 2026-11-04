# -*- coding: utf-8 -*-
"""Refill cur9.save: wood/ore to caps, keep everything else (incl. tree)."""
import sys, re, json
sys.path.insert(0, r'E:\DSH\game\djmwREA\scripts')
from v557save import read_segments, write_segments

SRC = r'E:\DSH\game\djmwREA\work\live\cur9.save'
OUT = r'E:\DSH\game\djmwREA\work\live\refill.save'

h, segs = read_segments(SRC)
segs = [s.decode('utf-8') if isinstance(s, bytes) else s for s in segs]


def setk(seg, key, val):
    new, n = re.subn(r'("%s":\s*)[^,}]+' % key, r'\g<1>%s' % val, segs[seg])
    assert n == 1, (key, n)
    segs[seg] = new


setk(2, 'MuCaiShuLiang', 5364060)
setk(2, 'KuangShiShuLiang', 3601500)
write_segments(OUT, h, segs)

h2, s2 = read_segments(OUT)
s2 = [x.decode('utf-8') if isinstance(x, bytes) else x for x in s2]
for k in ('MuCaiShuLiang', 'KuangShiShuLiang'):
    m = re.search(r'"%s":\s*("?[^,}"]*"?)"?' % k, s2[2])
    print(k, '=', m.group(1))
m = re.search(r'"ZuanShi":\s*("?[^,}"]*"?)"?', s2[13])
print('ZuanShi =', m.group(1))
m = re.search(r'"IsHuangJin":\s*("?[^,}"]*"?)"?', s2[11])
print('IsHuangJin =', m.group(1))
print('OK ->', OUT)
