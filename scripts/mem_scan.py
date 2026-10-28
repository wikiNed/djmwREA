"""从设备拉回的分块里精确搜索 UTF-16 字符串（本地执行，避免 shell 引号地狱）。
先在设备上把命中的段名报出来，这里只处理本地已有的文件。
"""
import glob
import os
import sys

D = sys.argv[1] if len(sys.argv) > 1 else r"E:\DSH\game\.rea-study\emu\memd"
pats = {
    "SaveFile.es3": "SaveFile.es3".encode("utf-16-le"),
    "AutoSave.es3": "AutoSave.es3".encode("utf-16-le"),
    "SaveFile": b"SaveFile",
}
files = sorted(glob.glob(os.path.join(D, "seg_*.bin")))
print("files:", len(files))
for f in files:
    sz = os.path.getsize(f)
    if sz == 0:
        continue
    data = open(f, "rb").read()
    for name, p in pats.items():
        idx = data.find(p)
        if idx >= 0:
            print(f"  HIT {name!r} in {os.path.basename(f)} @ {idx:#x} (size {sz:,})")
            # 打印上下文
            lo = max(0, idx - 64)
            blob = data[lo : idx + 128]
            try:
                txt = blob.decode("utf-16-le", "replace")
            except Exception:
                txt = ""
            print(f"      utf16ctx: {txt!r}")
print("done")
