# -*- coding: utf-8 -*-
"""Build patched APK v3.

变更点（相对 v2）：
- 撤销 0x6904E8 的 YG 静态权重补丁（该池在掷骰里拿不到远古，反而把分布打乱）
- 新增 0x7EC2BC get_YuanGuBaoShiUp 打桩，恒返回 3/7 = 0.42857143f
  掷骰逻辑：T = 1 + CSup + YGup，远古区间 = [1.0, T) => P(远古) = YGup/T = 0.3
- 保留进层衰减 -0.01、木材/矿石产量 x889
"""
import zipfile, struct, subprocess, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_APK = ROOT + r'\files\old\djmw_5.5.7.apk'
OUT_DIR = ROOT + r'\work\patched'
OUT_APK = OUT_DIR + r'\djmw_5.5.7_patched17.apk'
SO = OUT_DIR + r'\libil2cpp_v17.so'
KEY = OUT_DIR + r'\dshmod.keystore'
# 签名工具：优先环境变量 JARSIGNER，否则 PATH 里的 jarsigner。
# （不要写死某台机器的 JDK 路径 —— docs/30 §9 待办 4）
JARSIGNER = os.environ.get("JARSIGNER") or "jarsigner"

WORDS = [
    # ---- 反作弊豁免 ----
    (0x3D0F10, 0xE92D4830, 0xE12FFF1E, 'ZuoBi.Start -> bx lr（封号场景协程永不启动）'),
    (0xE8EBC0, 0xEBD86EE5, 0xE1A00000, 'ZuoBi 协程内 PlayerPrefs.DeleteAll nop'),
    (0xE8EC18, 0xEBE5965C, 0xE1A00000, 'ZuoBi 协程内 ChongWuPool.DeleteSave nop'),
    (0x3EE4CC, 0xEB029CC2, 0xE1A00000, 'FengHaoUI.SetActive(true) nop'),
    (0x7BDEF8, 0xE92D4C10, 0xE12FFF1E, 'ShuJuDate.QingDang -> bx lr（永不删档）'),
    (0x3EE4A0, 0x0A000061, 0xEA000061, 'HeiMingDan 判定 beq -> b（永远跳过封号分支）'),
    (0x3EDB48, 0xEB0ADC50, 0xE1A00000, 'GetBaoName -> LoadScene(Level_ZuoBi) nop'),
    (0x7B89C4, 0xEBFBB0B1, 0xE1A00000, 'ShengMingZhiShuUI 37天闸 -> LoadScene(Level_ZuoBi) nop'),
    # ---- 洞穴次数：模型/管理器两侧计数都冻结，上限保持原值 60 ----
    (0x68F9F0, 0xE92D4830, 0xE12FFF1E, 'AddBaoShiDongTiLi -> bx lr（模型侧已用次数不增）'),
    (0xED0B98, 0xE2800001, 0xE1A00000, 'DiXiaCheng 管理器 [r4+0x14] 自增 -> nop（界面侧次数不增）'),
    (0xED0428, 0xAA00003C, 0xE1A00000, 'SuiJiBaoShi 次数上限判定 bge -> nop'),
    # GetFenJieSuiPianShu: 原逻辑是 raw/2，这里改乘 50 => 净 x100
    (0x691938, 0xE1B020A1, 0xE3A02032, '分解碎片 x100: mov r2,#50'),
    (0x69193C, 0xE1A00060, 0xE0810290, '分解碎片 x100: umull r0,r1,r0,r2'),
    (0x691940, 0xE1901002, 0xE8BD8800, '分解碎片 x100: pop {fp,pc}'),
    (0x691944, 0x03000001, 0xE1A00000, '分解碎片 x100: nop'),
    (0x691948, 0x11A01002, 0xE1A00000, '分解碎片 x100: nop'),
    # 一键分解 GetYiJianFenJieShu 内联着同样的 raw/2 逻辑（0x691B9C 直接调 JiSuanSuiPian，不走 GetFenJieSuiPianShu）
    # 六种颜色各一份，全部在下面循环里补丁
    (0x690944, 0x00000000, 0x3EDB6DB7, 'YG 随机池(equal 分支) 0 -> 3/7 = 0.4286'),
    (0x6904E8, 0x00000000, 0x00000000, 'YG weight pool 保持 0（v2 的错误改动已撤销）'),
    (0xED02BC, 0xBDCCCCCD, 0xBC23D70A, 'next-layer decay -0.1f -> -0.01f'),
    (0x7AE764, 0xE3A01002, 0xE3001379, 'wood buff mov r1,#2 -> movw r1,#889'),
    (0x7AE77C, 0x03001001, 0x03001379, 'wood normal movweq r1,#1 -> #889'),
    (0x7AF4E0, 0xE3A01002, 0xE3001379, 'ore buff'),
    (0x7AF4F8, 0x03001001, 0x03001379, 'ore normal'),
    # ---- 资源生成量定值 10000/s ----
    # 产额函数：r0 = (1 或 2) * [this+0x14]（0x7AE780 / 0x7AF4FC 的 mul），改成常量 10000；
    # 触发间隔函数：threshold = 基数(0.5/0.25) * 3.0f 或 5.0f，改成恒定 1.0f，
    # 于是 Update 里「累计 >= 1.0s」时加 10000 -> 严格 10000/s（有/无 buff 都一样）。
    (0x7AE780, 0xE0000491, 0xE3020710, 'wood 产额 mul -> movw r0,#10000'),
    (0x7AF4FC, 0xE0000491, 0xE3020710, 'ore  产额 mul -> movw r0,#10000'),
    (0x7AE814, 0xEEB00A08, 0xE3000000, 'wood 间隔 vmov.f32 #3.0 -> movw r0,#0'),
    (0x7AE818, 0xEE010A10, 0xE3430F80, 'wood 间隔 -> movt r0,#0x3F80 (1.0f)'),
    (0x7AE81C, 0xEE210A00, 0xE1A00000, 'wood 间隔 vmul -> nop'),
    (0x7AE820, 0xEE100A10, 0xE1A00000, 'wood 间隔 vmov r0,s0 -> nop'),
    (0x7AF530, 0xEEB10A04, 0xE3000000, 'ore  间隔 vmov.f32 #5.0 -> movw r0,#0'),
    (0x7AF534, 0xEE010A10, 0xE3430F80, 'ore  间隔 -> movt r0,#0x3F80 (1.0f)'),
    (0x7AF538, 0xEE210A00, 0xE1A00000, 'ore  间隔 vmul -> nop'),
    (0x7AF53C, 0xEE100A10, 0xE1A00000, 'ore  间隔 vmov r0,s0 -> nop'),
    # ---- 分解「实际到账」也 x100（此前 x100 只打在显示函数上，见 docs/30 §7）----
    # FenSuiBaoShi @0x695984 才是真正加碎片的地方：
    #   shu = JiSuanSuiPian(gem); shu/=2; AddBaoShiSuiPian(this, shu)
    # 把 raw/2 换成 raw*50（净 x100），与显示侧 GetFenJieSuiPianShu 一致。
    # 0x6959B0 是紧随其后的 mov r0,r5，故 b 直接跳过去。
    (0x69599C, 0xE1B010A1, 0xE3A02032, '分解到账 x100: mov r2,#50'),
    (0x6959A0, 0xE1A02060, 0xE0832290, '分解到账 x100: umull r2,r3,r0,r2'),
    (0x6959A4, 0xE1923001, 0xEA000001, '分解到账 x100: b 0x6959B0'),
    (0x6959A8, 0x03002001, 0xE1A00000, '分解到账 x100: nop'),
    (0x6959AC, 0x11A03001, 0xE1A00000, '分解到账 x100: nop'),
]

# 一键分解：六种颜色（红/绿/蓝/黄/紫/玉）各有一份内联 raw/2，改 raw*50 => 净 x100
for _a in (0x691BA0, 0x691E70, 0x69213C, 0x692408, 0x6926D4, 0x6929B4):
    WORDS += [
        (_a,        0xE1B010A1, 0xE3A02032, '一键分解 x100 @%X: mov r2,#50' % _a),
        (_a + 0x04, 0xE1A00060, 0xE0810290, '一键分解 x100 @%X: umull r0,r1,r0,r2' % _a),
        (_a + 0x08, 0xE1902001, 0xE1A02001, '一键分解 x100 @%X: mov r2,r1' % _a),
        (_a + 0x0C, 0x03000001, 0xE1A00000, '一键分解 x100 @%X: nop' % _a),
        (_a + 0x10, 0x11A02001, 0xE1A00000, '一键分解 x100 @%X: nop' % _a),
    ]

# get_YuanGuBaoShiUp @0x7EC2BC -> return 0.42857143f
STUB_OLD = [0xE590106C, 0xE2811001, 0xEE001A10, 0xEEB80AC0]
STUB_NEW = [0xE3060DB7, 0xE3430EDB, 0xEE000A10, 0xE12FFF1E]  # movw r0,#0x6DB7; movt r0,#0x3EDB; vmov s0,r0; bx lr

with zipfile.ZipFile(SRC_APK) as z:
    data = z.read('lib/armeabi-v7a/libil2cpp.so')
buf = bytearray(data)

for off, orig, new, label in WORDS:
    cur = struct.unpack_from('<I', buf, off)[0]
    if cur != orig:
        print('MISMATCH @0x%X: got %08x want %08x (%s)' % (off, cur, orig, label))
        sys.exit(1)
    if cur != new:
        struct.pack_into('<I', buf, off, new)
    print('ok @0x%X %08x -> %08x (%s)' % (off, cur, new, label))

for i, (old, new) in enumerate(zip(STUB_OLD, STUB_NEW)):
    off = 0x7EC2BC + i * 4
    cur = struct.unpack_from('<I', buf, off)[0]
    if cur != old:
        print('MISMATCH @0x%X: got %08x want %08x' % (off, cur, old))
        sys.exit(1)
    struct.pack_into('<I', buf, off, new)
    print('stub @0x%X %08x -> %08x' % (off, old, new))

os.makedirs(OUT_DIR, exist_ok=True)
open(SO, 'wb').write(bytes(buf))

if os.path.exists(OUT_APK):
    os.remove(OUT_APK)
with zipfile.ZipFile(SRC_APK) as zin, zipfile.ZipFile(OUT_APK, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename.startswith('META-INF/'):
            continue
        if item.filename == 'lib/armeabi-v7a/libil2cpp.so':
            zout.writestr(item, bytes(buf))
        else:
            zout.writestr(item, zin.read(item.filename))

try:
    subprocess.run([
        JARSIGNER,
        '-keystore', KEY, '-storepass', 'dshmod123', OUT_APK, 'dshmod'
    ], check=True, capture_output=True)
except FileNotFoundError:
    print('未找到 jarsigner（%r）。请装 JDK 并设 JARSIGNER 环境变量，或把 jarsigner 放进 PATH。' % JARSIGNER)
    print('未签名 APK 已生成: %s' % OUT_APK)
    sys.exit(2)
print('signed:', os.path.getsize(OUT_APK))
