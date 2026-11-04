# -*- coding: utf-8 -*-
"""给手机上的 64 位 libil2cpp.so 打补丁（v5.5.7 arm64 build）。

所有落点都来自 32 位补丁表（scripts/build_patched_apk.py 的 WORDS）
通过 methodPointers 索引对齐 + 指令形状核对翻译而来；
每条补丁都校验「原字」必须与预期一致，防止打错位置。

用法：
    python build_patched_lib64.py --dry-run     # 只校验，不写文件
    python build_patched_lib64.py               # 写出 work/patched/libil2cpp_64_patched.so
"""
import argparse
import hashlib
import os
import struct
import sys

SRC = r'E:\DSH\game\work\phone64\libil2cpp_64.so'
OUT_DIR = r'E:\DSH\game\work\patched'
OUT = os.path.join(OUT_DIR, 'libil2cpp_64_patched.so')

RET = 0xD65F03C0
NOP = 0xD503201F

# (文件偏移/VA, 原字, 新字, 说明)
# 代码段 addr == off（.text 与 il2cpp 段都是）
PATCHES = [
    # ---- 资源严格 10000/s ----
    (0xEBF9D0, 0x1B137D08, 0x5284E208, 'wood 产额 mul w8,w8,w19 -> mov w8,#10000'),
    (0xEC0550, 0x1B137D08, 0x5284E208, 'ore  产额 mul w8,w8,w19 -> mov w8,#10000'),
    (0xEBFA54, 0x1E210800, 0x1E2E1000, 'wood 间隔 fmul -> fmov s0,#1.0'),
    (0xEC057C, 0x1E210800, 0x1E2E1000, 'ore  间隔 fmul -> fmov s0,#1.0'),
    # ---- 宝石分解显示 x100（GetFenJieSuiPianShu: raw/2 -> raw*50）----
    (0xEB6BF8, 0xD341FC08, 0xD2800648, '分解显示: lsr x8,x0,#1 -> mov x8,#50'),
    (0xEB6C00, 0x9A9F1500, 0x9B087C00, '分解显示: csinc -> mul x0,x0,x8'),
    # ---- 宝石分解到账 x100（FenSuiBaoShi: raw/2 -> raw*50）----
    (0xEB947C, 0xD341FC08, 0xD2800648, '分解到账: lsr x8,x0,#1 -> mov x8,#50'),
    (0xEB9484, 0x9A9F1501, 0x9B087C01, '分解到账: csinc -> mul x1,x0,x8'),
    # ---- 钻石不扣减（余额恒定，绝不制造「余额上升」避免反作弊）----
    (0xE557F0, 0xF81D0FF5, RET, 'RemoveZuanShi -> ret（消耗钻石不扣余额）'),
    # ---- 反作弊豁免 ----
    (0xE0C7A0, 0xA9BE4FF4, RET, 'ZuoBi.Start -> ret（封号协程不启动）'),
    (0xECAE10, 0xF81E0FF3, RET, 'ShuJuDate.QingDang -> ret（永不删档）'),
    (0xEB5730, 0xA9BE4FF4, RET, 'AddBaoShiDongTiLi -> ret（模型侧次数不增）'),
    # ---- 洞穴探秘次数 ----
    (0xDF4118, 0x11000508, NOP, 'DiXiaCheng 界面侧次数自增 -> nop'),
    (0xDF3CD4, 0x5400058A, NOP, 'SuiJiBaoShi 次数上限判定 b.ge -> nop'),
    # ---- 一键分解「可获得碎片」总数 x100 ----
    # 32 位版这里是调用 GetFenJieSuiPianShu（已打补丁）；64 位被内联成 raw/2，
    # 6 个分级分支各一份，必须逐处改，否则弹窗数字仍是原值。
    (0xEB6E00, 0xD341FC08, 0xD2800648, '一键分解总数: lsr x8,x0,#1 -> mov x8,#50 (档1)'),
    (0xEB6E08, 0x9A9F1508, 0x9B087C08, '一键分解总数: csinc -> mul x8,x0,x8 (档1)'),
    (0xEB6FD0, 0xD341FC08, 0xD2800648, '一键分解总数: mov x8,#50 (档2)'),
    (0xEB6FD8, 0x9A9F1508, 0x9B087C08, '一键分解总数: mul x8,x0,x8 (档2)'),
    (0xEB71A0, 0xD341FC08, 0xD2800648, '一键分解总数: mov x8,#50 (档3)'),
    (0xEB71A8, 0x9A9F1508, 0x9B087C08, '一键分解总数: mul x8,x0,x8 (档3)'),
    (0xEB7370, 0xD341FC08, 0xD2800648, '一键分解总数: mov x8,#50 (档4)'),
    (0xEB7378, 0x9A9F1508, 0x9B087C08, '一键分解总数: mul x8,x0,x8 (档4)'),
    (0xEB7540, 0xD341FC08, 0xD2800648, '一键分解总数: mov x8,#50 (档5)'),
    (0xEB7548, 0x9A9F1508, 0x9B087C08, '一键分解总数: mul x8,x0,x8 (档5)'),
    (0xEB7710, 0xD341FC08, 0xD2800648, '一键分解总数: mov x8,#50 (档6)'),
    (0xEB7718, 0x9A9F1508, 0x9B087C08, '一键分解总数: mul x8,x0,x8 (档6)'),
    # ---- 进下层衰减 -0.1f -> -0.01f ----
    # 64 位没有尾部字面量池，-0.1f 是 .rodata 里的共享常量（全代码只有 1 处引用）。
    (0xFDDD88, 0xBDCCCCCD, 0xBC23D70A, 'next-layer decay -0.1f -> -0.01f'),
    # ---- 远古随机池 3/7（对应 32 位把 0.0f 池值改成 0x3EDB6DB7）----
    # 64 位在 0xEB6150 用 fmov s0,wzr 内联了那个 0.0f；改成从 .rodata 空位取 3/7。
    (0xEF5D68, 0x00000000, 0x3EDB6DB7, 'YG 3/7 常量落位（.rodata 零填充空位）'),
    (0xEB6150, 0x1E2703E0, 0x1C1FE0C0, 'YG 随机池: fmov s0,wzr -> ldr s0,#0xef5d68'),
    # ---- 远古爆率 ~31%：把「远古」的判定阈值改成 s8 的固定比例（与权重表无关）----
    # 原代码：s0 = PT+JZ+XY+SS+CS（累计权重），s9 = Random(0,s8)，远古 iff s9 >= s0。
    # 改成：s0 = 0.6875 * s8，远古 iff s9 >= 0.6875*s8 -> 概率恒为 31.25%。
    (0xEB61D8, 0x1E232800, 0x1E2CD000, 'YG 阈值: fadd s0,s0,s3 -> fmov s0,#0.6875'),
    (0xEB61DC, 0x1E242800, 0x1E200900, 'YG 阈值: fadd s0,s0,s4 -> fmul s0,s8,s0'),
    # ---- 重签包启动崩溃绕过：0x406d9c 对 NULL 读 [x0+0x4a] ----
    (0x406D9C, 0x39412800, 0x52800000, 'nullfix: ldrb w0,[x0,#0x4a] -> mov w0,#0'),
    # ---- 登录绕过：把「服务器返回 0 / 网络错误」都当成功（进 111 成功体 0xE15344）----
    (0xE15304, 0x140000A8, 0x14000010, 'login: 响应"0"分支 0xE155A4 -> 0xE15344 成功体'),
    (0xE15100, 0x370000C0, 0x14000091, 'login: 网络错误分支 0xE15118 -> 0xE15344 成功体'),
    # ---- 肉（宠物饲料）只增不减：RemoveSiLiao 直接返回，不扣 chongWuSiLiao(+0x128) ----
    (0xE5EB34, 0xA9BE4FF4, RET, 'RemoveSiLiao -> ret（饲料不减少）'),
    # ---- 草丛（今日抓宠次数）只增不减：AddCiShu 不执行，used 恒 0 -> 界面恒 9/9 ----
    # AddCiShu @0xed9b24: ldr w8,[x0,#0x90]; add w8,w8,#1; str w8,[x0,#0x90] -> 同步进 date+0x34
    (0xED9B24, 0xA9BE4FF4, RET, '抓宠次数 AddCiShu -> ret（草丛不减少）'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--skip', default='',
                    help='逗号分隔的补丁地址（如 0xeb6bf8,0xeb6c00），用于做对照实验')
    a = ap.parse_args()
    skip = {int(x, 0) for x in a.skip.split(',') if x.strip()}

    data = bytearray(open(SRC, 'rb').read())
    print('源文件 %s  %d 字节  MD5 %s' % (SRC, len(data), hashlib.md5(data).hexdigest()))
    ok = True
    for off, old, new, desc in PATCHES:
        if off in skip:
            print('  [skip] %#010x  %s' % (off, desc))
            continue
        cur = struct.unpack_from('<I', data, off)[0]
        if cur != old:
            print('  [FAIL] %#010x 期望 %08X 实际 %08X  %s' % (off, old, cur, desc))
            ok = False
            continue
        print('  [ok]   %#010x %08X -> %08X  %s' % (off, old, new, desc))
        struct.pack_into('<I', data, off, new)

    if not ok:
        print('\n有补丁点不匹配，未写文件。')
        return 1
    if a.dry_run:
        print('\n校验全部通过（dry-run，未写文件）。')
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    open(a.out, 'wb').write(bytes(data))
    print('\n已写出 %s  %d 字节  MD5 %s' % (a.out, len(data), hashlib.md5(bytes(data)).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
