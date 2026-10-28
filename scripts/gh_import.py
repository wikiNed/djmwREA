"""用 pyghidra 导入并分析 libil2cpp.so。

用 open_program(binary, project_location, project_name, analyze=True)。
"""

from paths import SO

import os
import time

os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

PROJ_DIR = r"E:\rea_ghidra\proj"
PROJ_NAME = "il2cpp"
os.makedirs(PROJ_DIR, exist_ok=True)

t0 = time.time()
with pyghidra.open_program(
    SO, project_location=PROJ_DIR, project_name=PROJ_NAME,
    analyze=True, language="AARCH64:LE:64:v8A",
) as api:
    prog = api.getCurrentProgram() if hasattr(api, "getCurrentProgram") else api.program
    print("OK name=", prog.getName(), "time=", round(time.time() - t0, 1), flush=True)
    print("functions:", prog.getFunctionManager().getFunctionCount(), flush=True)
    print("imagebase:", prog.getImageBase(), flush=True)
