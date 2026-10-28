"""按精确 RVA 反编译：先在地址上 createFunction，再反编译。

Ghidra 自动识别把 0x1782D44 吞进了前一个函数（FUN_01782d30）。
用 createFunction(addr, name) 在真起点重新定义，然后反编译。
"""

from paths import SO

import os

os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

PROJ_DIR = r"E:\rea_ghidra\proj"
PROJ_NAME = "il2cpp"
OUT = os.environ.get('GHIDRA_INSTALL_DIR')
os.makedirs(OUT, exist_ok=True)

# (名字, 起始 RVA, 结束 RVA)  —— 结束用下一个方法 RVA
TARGETS = [
    ("AESEncryptionAlgorithm__Encrypt_stream", 0x1782D44, 0x178329C),
    ("AESEncryptionAlgorithm__Decrypt_stream", 0x178329C, 0x1783838),
    ("AESEncryptionAlgorithm__Encrypt_bytes", 0x17826EC, 0x1782A18),
    ("AESEncryptionAlgorithm__CopyStream", 0x1782604, 0x17826EC),
    ("ES3IOUtil__ctor_enc_file", 0x1783840, 0x17838FC),
]

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

    dec = DecompInterface()
    dec.openProgram(prog)
    mon = ConsoleTaskMonitor()

    for name, start, end in TARGETS:
        a = rt.getAddress(start)
        f = fm.getFunctionAt(a)
        if f is None:
            f = fm.getFunctionContaining(a)
            if f is not None and int(str(f.getEntryPoint()), 16) != start:
                # 拆开：删掉旧函数在这段上的定义再建新的
                try:
                    fm.removeFunction(f.getEntryPoint())
                except Exception as e:  # noqa: BLE001
                    print("remove fail", e)
                f = None
        if f is None:
            try:
                f = fm.createFunction(str(name), a, None)
            except Exception as e:  # noqa: BLE001
                print(f"[{name}] createFunction failed: {e}")
                continue
        if f is None:
            print(f"[{name}] still None")
            continue
        try:
            f.setName(name, ghidra.program.model.symbol.SourceType.USER_DEFINED)
        except Exception:  # noqa: BLE001
            pass
        res = dec.decompileFunction(f, 180, mon)
        if res and res.decompileCompleted():
            txt = res.getDecompiledFunction().getC()
            path = os.path.join(OUT, name + ".c")
            open(path, "w", encoding="utf-8").write(txt)
            print(f"[{name}] OK {len(txt)}ch -> {path}", flush=True)
        else:
            print(f"[{name}] FAIL {res.getErrorMessage() if res else 'None'}", flush=True)
