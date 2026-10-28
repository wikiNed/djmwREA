"""按 RVA 反编译并导出反编译文本。

Ghidra imagebase = 0x100000，但 ELF 首 LOAD vaddr = 0。
所以 Ghidra 地址 = RVA + 0x100000? 还是 = RVA?
→ 直接扫描两个候选，看哪个能拿到函数。
"""

from paths import SO

import os
import sys

os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

PROJ_DIR = r"E:\rea_ghidra\proj"
PROJ_NAME = "il2cpp"
OUT = os.environ.get('GHIDRA_INSTALL_DIR')

os.makedirs(OUT, exist_ok=True)

TARGETS = {
    "Encrypt_stream": 0x1782D44,
    "SaveManager_getSavePath": 0x17A5D84,
    "CopyStream": 0x1782604,
}

from ghidra.app.decompiler import DecompInterface  # noqa: E402
from ghidra.util.task import ConsoleTaskMonitor  # noqa: E402

with pyghidra.open_program(
    SO, project_location=PROJ_DIR, project_name=PROJ_NAME, analyze=False,
    language="AARCH64:LE:64:v8A",
) as api:
    prog = api.getCurrentProgram()
    fm = prog.getFunctionManager()
    af = prog.getAddressFactory()
    rt = af.getDefaultAddressSpace()

    # 先确定映射：取一个已知函数地址，看内存里是什么
    for off in (0x0, 0x100000):
        a = rt.getAddress(0x1782D44 + off)
        f = fm.getFunctionContaining(a)
        print(f"RVA 0x{0x1782D44+off:X} -> func={f.getName() if f else None}", flush=True)

    dec = DecompInterface()
    dec.openProgram(prog)
    mon = ConsoleTaskMonitor()

    for off in (0x0, 0x100000):
        a = rt.getAddress(0x1782D44 + off)
        f = fm.getFunctionContaining(a)
        if f is None:
            continue
        print(f"\n===== mapping offset 0x{off:X} -> {f.getName()} @ {f.getEntryPoint()} =====", flush=True)
        res = dec.decompileFunction(f, 120, mon)
        if res and res.decompileCompleted():
            txt = res.getDecompiledFunction().getC()
            path = os.path.join(OUT, f"Encrypt_{off:X}.c")
            open(path, "w", encoding="utf-8").write(txt)
            print("written", path, len(txt), flush=True)
            print(txt[:3000], flush=True)
        else:
            print("decompile failed:", res.getErrorMessage() if res else "None", flush=True)
