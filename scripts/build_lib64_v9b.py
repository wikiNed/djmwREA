# -*- coding: utf-8 -*-
"""v9: patch the phone arm64 libil2cpp.so (on top of v8).

New in v9:
  1. Ad-reward count fixed at 80, never decreases.
  2. Wood 500000/s, ore 300000/s.
  3. Dispatch (PaiQian) duration 1 hour -> 3 seconds.
  4. Gem colour probability uniform (RandomYanSeBaoShi -> 0..5).

Every patch checks the original word first; any mismatch aborts the build.

Usage: python build_lib64_v9b.py [--dry-run]
"""
import argparse
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'patched', 'base_arm64.so')
OUT_DIR = os.path.join(ROOT, 'work', 'patched')
OUT = os.path.join(OUT_DIR, 'libil2cpp_64_v9.so')

RET = 0xD65F03C0
NOP = 0xD503201F

PATCHES = [
    (0xEBF9D0, 0x1B137D08, 0xD28F4240, 'wood: mul -> mov x0,#0x7A12'),
    (0xEBF9D4, 0x93407D00, 0xD37CEC00, 'wood: sxtw -> lsl x0,x0,#4 (=500000)'),
    (0xEC0550, 0x1B137D08, 0xD28927C0, 'ore : mul -> mov x0,#0x493E'),
    (0xEC0554, 0x93407D00, 0xD37CEC00, 'ore : sxtw -> lsl x0,x0,#4 (=300000)'),
    (0xEBFA54, 0x1E210800, 0x1E2E1000, 'wood interval fmul -> fmov s0,#1.0'),
    (0xEC057C, 0x1E210800, 0x1E2E1000, 'ore  interval fmul -> fmov s0,#1.0'),
    (0xEB6BF8, 0xD341FC08, 0xD2800648, 'fenjie display a'),
    (0xEB6C00, 0x9A9F1500, 0x9B087C00, 'fenjie display b'),
    (0xEB947C, 0xD341FC08, 0xD2800648, 'fenjie credit a'),
    (0xEB9484, 0x9A9F1501, 0x9B087C01, 'fenjie credit b'),
    (0xEB6E00, 0xD341FC08, 0xD2800648, 'yijian #1a'),
    (0xEB6E08, 0x9A9F1508, 0x9B087C08, 'yijian #1b'),
    (0xEB6FD0, 0xD341FC08, 0xD2800648, 'yijian #2a'),
    (0xEB6FD8, 0x9A9F1508, 0x9B087C08, 'yijian #2b'),
    (0xEB71A0, 0xD341FC08, 0xD2800648, 'yijian #3a'),
    (0xEB71A8, 0x9A9F1508, 0x9B087C08, 'yijian #3b'),
    (0xEB7370, 0xD341FC08, 0xD2800648, 'yijian #4a'),
    (0xEB7378, 0x9A9F1508, 0x9B087C08, 'yijian #4b'),
    (0xEB7540, 0xD341FC08, 0xD2800648, 'yijian #5a'),
    (0xEB7548, 0x9A9F1508, 0x9B087C08, 'yijian #5b'),
    (0xEB7710, 0xD341FC08, 0xD2800648, 'yijian #6a'),
    (0xEB7718, 0x9A9F1508, 0x9B087C08, 'yijian #6b'),
    (0xE557F0, 0xF81D0FF5, RET, 'RemoveZuanShi -> ret'),
    (0xE5EB34, 0xA9BE4FF4, RET, 'RemoveSiLiao -> ret'),
    (0xED9B24, 0xA9BE4FF4, RET, 'zhua chong AddCiShu -> ret'),
    (0xE0C7A0, 0xA9BE4FF4, RET, 'ZuoBi.Start -> ret'),
    (0xECAE10, 0xF81E0FF3, RET, 'QingDang -> ret'),
    (0xEB5730, 0xA9BE4FF4, RET, 'AddBaoShiDongTiLi -> ret'),
    (0xDF4118, 0x11000508, NOP, 'cave ui count -> nop'),
    (0xDF3CD4, 0x5400058A, NOP, 'cave count limit -> nop'),
    (0xFDDD88, 0xBDCCCCCD, 0xBC23D70A, 'next-layer decay -0.1 -> -0.01'),
    (0xEF5D68, 0x00000000, 0x3EDB6DB7, 'YG 3/7 const'),
    (0xEB6150, 0x1E2703E0, 0x1C1FE0C0, 'YG pool load'),
    (0xEB61D8, 0x1E232800, 0x1E2CD000, 'YG threshold 0.6875'),
    (0xEB61DC, 0x1E242800, 0x1E200900, 'YG threshold mul'),
    (0x406D9C, 0x39412800, 0x52800000, 'nullfix'),
    (0xE15304, 0x140000A8, 0x14000010, 'login resp0 -> success'),
    (0xE15100, 0x370000C0, 0x14000091, 'login neterr -> success'),
    (0xEE4064, 0xA9BF7BFD, 0x52800A00, 'GuangGaoShangXian -> mov w0,#80'),
    (0xEE4068, 0x910003FD, RET, 'GuangGaoShangXian -> ret'),
    (0xEE4090, 0xA9BE4FF4, 0x52800020, 'AddCiShu -> mov w0,#1'),
    (0xEE4094, 0xA9017BFD, RET, 'AddCiShu -> ret'),
    (0xEE4054, 0xB9401000, 0x52800000, 'get_GuangGaoDangQianCiShu -> mov w0,#0'),
    (0x8C5F5C, 0x529DD000, 0x52817700, 'get_PaiQianNeedTime -> mov w0,#3000'),
    (0x8C5F60, 0x72A006C0, RET, 'get_PaiQianNeedTime -> ret'),
]

COLOR_START = 0xEB64A8
COLOR_END = 0xEB6624
COLOR_OLD_FIRST = 0xFC1E0FE8
COLOR_WORDS = [
    0xA9BF7BFD,
    0x910003FD,
    0x1E2703E0,
    0x1E2E1001,
    0xAA1F03E0,
    0x97E1FDBF,
    0x528000C8,
    0x1E220101,
    0x1E210800,
    0x1E380000,
    0x7100141F,
    0x528000A1,
    0x1A813000,
    0xA8C17BFD,
    0xD65F03C0,
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    data = bytearray(open(SRC, 'rb').read())
    print('src %s  %d bytes  MD5 %s' % (SRC, len(data), hashlib.md5(bytes(data)).hexdigest()))
    ok = True
    for off, old, new, desc in PATCHES:
        cur = struct.unpack_from('<I', data, off)[0]
        if cur != old:
            print('  [FAIL] %#010x expect %08X got %08X  %s' % (off, old, cur, desc))
            ok = False
            continue
        struct.pack_into('<I', data, off, new)
        print('  [ok]   %#010x %08X -> %08X  %s' % (off, old, new, desc))

    cur = struct.unpack_from('<I', data, COLOR_START)[0]
    if cur != COLOR_OLD_FIRST:
        print('  [FAIL] %#010x color first word expect %08X got %08X'
              % (COLOR_START, COLOR_OLD_FIRST, cur))
        ok = False
    else:
        region = COLOR_END - COLOR_START
        body = COLOR_WORDS + [NOP] * ((region // 4) - len(COLOR_WORDS))
        for i, w in enumerate(body):
            struct.pack_into('<I', data, COLOR_START + i * 4, w)
        print('  [ok]   %#010x..%#010x gem colour uniform (%d words)'
              % (COLOR_START, COLOR_END, len(body)))

    if not ok:
        print('\nsome patch points mismatch, nothing written.')
        return 1
    if a.dry_run:
        print('\ndry-run ok')
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    open(OUT, 'wb').write(bytes(data))
    print('\nwritten %s  %d bytes  MD5 %s' % (OUT, len(data), hashlib.md5(bytes(data)).hexdigest()))


if __name__ == '__main__':
    sys.exit(main())
