"""用 pyghidra 反编译目标函数。

用 open_program(binary, project_location, project_name) —— 与导入时同一套
调用，Ghidra 会复用已存在的程序（不会重新分析）。
analyze=False 保证不重跑分析（已花 1320 秒）。
"""

import os

os.environ["GHIDRA_INSTALL_DIR"] = r"E:\DSH\game\.rea-study\ghidra\ghidra_12.2_PUBLIC"
os.environ["JAVA_HOME"] = r"E:\DSH\game\.rea-study\jdk\jdk-25.0.5.0.3"
os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
PROJ_DIR = r"E:\rea_ghidra\proj"
PROJ_NAME = "il2cpp"

from ghidra.app.decompiler import DecompInterface  # noqa: E402
from ghidra.util.task import ConsoleTaskMonitor  # noqa: E402

# 要看的函数 RVA（dump.cs 给出）。Ghidra 报告 imagebase=0x100000，
# 但 ELF 首个 LOAD vaddr=0，所以 RVA 与 Ghidra 地址大概率一致；两个都试。
TARGETS = [
    ("AESEncryptionAlgorithm.Encrypt_stream", 0x1782D44),
    ("SaveManager.get_SavePath", 0x17A5D84),
]

with pyghidra.open_program(
    SO, project_location=PROJ_DIR, project_name=PROJ_NAME, analyze=False,
    language="AARCH64:LE:64:v8A",
) as api:
    prog = api.getCurrentProgram()
    print("imagebase:", prog.getImageBase(), flush=True)
    print("functions:", prog.getFunctionManager().getFunctionCount(), flush=True)

    fm = prog.getFunctionManager()
    af = prog.getAddressFactory()
    rt = af.getDefaultAddressSpace()

    # 列出所有含 AESEncryptionAlgorithm / SaveManager 的函数
    names = []
    for f in fm.getFunctions(True):
        n = f.getName()
        if "AESEncryptionAlgorithm" in n or "SaveManager" in n or "ES3Settings" in n:
            names.append((str(f.getEntryPoint()), n))
    print(f"\n=== 相关函数 {len(names)} ===", flush=True)
    for a, n in names[:80]:
        print(f"  {a}  {n}", flush=True)
