"""精确还原 SaveManager.ctor 的寄存器流与调用参数。"""
import struct

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
data = open(SO, "rb").read()

e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
eps = struct.unpack_from("<H", data, 0x36)[0]
epn = struct.unpack_from("<H", data, 0x38)[0]
segs = []
for i in range(epn):
    o = e_phoff + i * eps
    if struct.unpack_from("<I", data, o)[0] != 1:
        continue
    fl = struct.unpack_from("<I", data, o + 4)[0]
    off, va, pa, fs, ms = struct.unpack_from("<QQQQQ", data, o + 8)
    segs.append((fl, off, va, fs, ms))


def va2off(va):
    for fl, off, bva, fs, ms in segs:
        if bva <= va < bva + fs:
            return off + (va - bva)
    return None


# 目标：找到 ES3Settings 的完整 ctor（4 参数版本），确认参数语义
# 0x17522a4 是另一个 ctor: (x0=this, w1, x2, x3, x4)
# 0x175226c 是前面看到的: (x0=this, w1=type, x2=password) -> +0x28
print("=== 检查 ES3Settings 字段偏移 ===")
# 从 dump.cs 找 ES3Settings 字段布局
lines = open(r"E:\DSH\game\.rea-study\dump\dump.cs", encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(lines):
    if "class ES3Settings" in l and "TypeDefIndex" in l:
        print("line", i + 1, l.strip())
        for j in range(i, min(i + 40, len(lines))):
            t = lines[j].strip()
            if t.startswith("// Methods"):
                break
            if t and not t.startswith("//"):
                print("   ", t)
        break
