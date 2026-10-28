import os
import sys

os.environ["GHIDRA_INSTALL_DIR"] = r"E:\DSH\game\.rea-study\ghidra\ghidra_12.2_PUBLIC"
os.environ["JAVA_HOME"] = r"E:\DSH\game\.rea-study\jdk\jdk-25.0.5.0.3"
os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

from pyghidra import open_program  # noqa: E402

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
print("size", os.path.getsize(SO))
print("pyghidra ok")
