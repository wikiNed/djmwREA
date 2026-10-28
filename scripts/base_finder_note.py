"""本脚本本身不做事，仅记录正确的 base 计算公式，供其他脚本 import。

真实加载基址的定位法（2026-10-28 实测有效）：
    base = 用 Memory.scanSync 在进程里找 libil2cpp.so 中某函数的指纹
    锚点：RVA 0x174460C+0x18 (ES3Settings.get_location 中部) 的 16 字节
    命中地址 - 0x174460C - 0x18 = base

MuMu 的 ARM 翻译层下：
  - /proc/PID/maps 里的地址不是 IL2CPP 代码的真实地址（代码在 r--p 段）
  - Process.getModuleByName('libil2cpp.so') 找不到模块
  - Process.enumerateModules() 看不到 il2cpp
  - 但内存里确实存在一份完整镜像（在 0x7d396xxxxx 这类高地址）
  => 必须用内存扫描算 base，不能信 maps
"""

INFER = """
用以下 JS 现场求 base（实测命中率 100%）：

var ANCHOR_RVA = 0x174460C + 0x18;   // get_location 中部
var PAT = "...";                     // 文件里 0x1744624 起的 16 字节
Process.enumerateRanges('r--').forEach(r => {
    if (r.size < 8*1024*1024) return;
    Memory.scanSync(r.base, r.size, PAT).forEach(m => {
        var base = m.address.sub(ANCHOR_RVA);
        send({ tag: 'base', base: base.toString() });
    });
});
"""
