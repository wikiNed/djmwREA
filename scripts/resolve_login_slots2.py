import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from rela_resolve import Elf
from paths import META, SO

elf = Elf(SO)
d = open(META, 'rb').read()
LIT_OFF, LIT_SIZE = 0x100, 133048
DAT_OFF = 0x100 + LIT_SIZE
N = LIT_SIZE // 8


def lit(i):
    if not (0 <= i < N):
        return f'<越界 {i}>'
    ln, off = struct.unpack_from('<ii', d, LIT_OFF + i * 8)
    return d[DAT_OFF + off:DAT_OFF + off + ln].decode('utf-8', 'replace')


def show(va):
    try:
        t, val = elf.resolve(va)
    except KeyError:
        return f'{va:#x} 未重定位'
    if t != 1027:
        return f'{va:#x} type={t} addend={val:#x}'
    off = elf.va2off(val)
    v = struct.unpack_from('<Q', elf.d[off:off + 8])[0]
    if (v >> 20) != 0xa00:
        return f'{va:#x} .data[{val:#x}]={v:#x} 非哨兵'
    idx = (v & 0xffffff) >> 1
    return f'{va:#x} idx={idx:<6} {lit(idx)!r}'


# DengLuUI.OnClickButton 用到的槽
for va in (0x35e8898, 0x35e87f0, 0x35e87f8, 0x35e8808):
    print(show(va))
