import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from rela_resolve import Elf
from paths import META, SO

elf = Elf(SO)
d = open(META, 'rb').read()
LIT_OFF, LIT_SIZE = 0x100, 133048
DAT_OFF = 0x100 + LIT_SIZE
N = LIT_SIZE // 8


def lit_by_idx(i):
    if i < 0 or i >= N:
        return f'<idx {i} 越界>'
    ln, off = struct.unpack_from('<ii', d, LIT_OFF + i * 8)
    return d[DAT_OFF + off:DAT_OFF + off + ln].decode('utf-8', 'replace')


def slot(va):
    """解析 GOT 槽 -> addend -> 哨兵 -> literal 字符串"""
    va &= 0x3ffffffff
    try:
        t, val = elf.resolve(va)
    except KeyError:
        return None, f'未重定位 (GOT 里没有 {va:#x})'
    if t != 1027:
        return None, f'type={t} addend={val:#x}（非 RELATIVE）'
    return val, None


def decode_addend(addend):
    """addend 指向 .data 槽，读出哨兵值，再索引 literal"""
    off = elf.va2off(addend)
    raw = elf.d[off:off + 8]
    v = struct.unpack_from('<Q', raw)[0]
    if (v >> 20) != 0xa00:
        return None, f'.data[{addend:#x}] 内容 {v:#x} 不是哨兵'
    idx = (v & 0xffffff) >> 1
    return idx, lit_by_idx(idx)


SLOTS = {
    0x35e87b0: 'AddField#1 字段名',
    0x35e87d8: 'AddField#2 字段名',
    0x35e87a8: 'AddField#3 字段名',
    0x35e8760: 'AddField#4 字段名',
    0x35e8870: 'Post uri',
    0x35e8880: 'Concat 前缀',
    0x35e87b8: '错误提示',
    0x35e87d0: '返回值比较 A',
    0x35e8770: '返回值比较 B',
    0x35e8778: '返回值比较 C',
    0x35e8780: '返回值比较 D',
    0x35e8788: '返回值比较 E',
    0x35e8790: '返回值比较 F',
    0x35e8798: '返回值比较 G',
    0x35e87a0: '返回值比较 H',
    0x35e87c0: '返回值比较 I',
}

for va, note in SLOTS.items():
    addend, err = slot(va)
    if err:
        print(f'{va:#x}  {note:20}  {err}')
        continue
    idx, s = decode_addend(addend)
    if idx is None:
        print(f'{va:#x}  {note:20}  {s}')
    else:
        print(f'{va:#x}  {note:20}  addend={addend:#x} idx={idx:<6} {s!r}')
