# -*- coding: utf-8 -*-
"""把洞穴已用次数(DangQianTiLi)改成指定值。"""
import sys
import json
sys.path.insert(0, r'E:\DSH\game\djmwREA\scripts')
from v557save import read_segments, write_segments

SRC = sys.argv[1] if len(sys.argv) > 1 else r'E:\DSH\game\djmwREA\work\live\cur12.save'
DST = sys.argv[2] if len(sys.argv) > 2 else r'E:\DSH\game\djmwREA\work\live\cur13.save'
VAL = int(sys.argv[3]) if len(sys.argv) > 3 else 0

header, segs = read_segments(SRC)
s9 = json.loads(segs[9])
print('before:', s9.get('DangQianTiLi'))
s9['DangQianTiLi'] = VAL
segs[9] = json.dumps(s9, ensure_ascii=False, separators=(',', ':'))
write_segments(DST, header, segs)

h2, s2 = read_segments(DST)
print('after:', json.loads(s2[9]).get('DangQianTiLi'))
