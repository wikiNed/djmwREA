from paths import SO
import os
import sys

os.environ["GHIDRA_JAVA_HOME"] = os.environ["JAVA_HOME"]

import pyghidra

pyghidra.start()

from pyghidra import open_program  # noqa: E402

print("size", os.path.getsize(SO))
print("pyghidra ok")
