"""统一文档里的本机绝对路径为仓库内相对路径。

映射规则（把开发机路径换成仓库内的位置）：
  <legacy>\\dump\\dump.cs      -> files/dump.cs
  <legacy>\\lib\\*.so          -> files/libil2cpp.so
  <legacy>\\lib\\global-metadata.dat -> files/global-metadata.dat
  <legacy>\\apk\\*.apk         -> files/<name>.apk
  <legacy>\\scripts\\X.py      -> scripts/X.py
  <legacy>\\scripts\\frida\\X  -> scripts/frida/X
  <legacy>\\saves              -> saves/
  <legacy>\\emu               -> emu/
  <legacy>\\install           -> install/
  <legacy>\\assets\\X         -> （不入库，从 APK 提取）
  <legacy>\\jdk / ghidra / work / memd -> 本机工具，不入库
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
LEGACY = r"E:\DSH\game\.rea-study"
SEP = r"\\{1,2}"


def L(tail: str) -> re.Pattern:
    body = re.escape(LEGACY).replace(r"\\", SEP)
    return re.compile(body + SEP + tail + r"((?:[\\/][^\s`'\"）)]*)?)")


MAP: list[tuple[re.Pattern, str]] = [
    (L(r"dump" + SEP + r"dump\.cs"), "files/dump.cs"),
    (L(r"lib" + SEP + r"libil2cpp\.so"), "files/libil2cpp.so"),
    (L(r"lib" + SEP + r"global-metadata\.dat"), "files/global-metadata.dat"),
    (L(r"apk" + SEP + r"([^`\s'\"）)]+\.apk)"), r"files/\g<1>"),
    (L(r"scripts"), "scripts"),
    (L(r"saves"), "saves/"),
    (L(r"emu"), "emu/"),
    (L(r"install"), "install/"),
    (L(r"assets"), "（data.unity3d 由 <code>scripts/paths.py:unity_data_asset()</code> 从 APK 提取）"),
    (L(r"jdk"), "<code>$JAVA_HOME</code>（本机工具，不入库）"),
    (L(r"ghidra"), "<code>$GHIDRA_INSTALL_DIR</code>（本机工具，不入库）"),
]


def main() -> int:
    dry = "--dry-run" in sys.argv
    report = []
    for p in sorted(REPO.rglob("*.md")):
        if ".git" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        if LEGACY not in text:
            continue
        orig = text
        for pat, repl in MAP:
            text = pat.sub(repl, text)
        # 残留（未覆盖的子路径）统一兜底
        text = re.sub(re.escape(LEGACY) + r"\\{1,2}", "", text)
        if text != orig:
            if not dry:
                p.write_text(text, encoding="utf-8")
            report.append(p.relative_to(REPO).as_posix())

    print(f"{'[dry] ' if dry else ''}更新 {len(report)} 个文档")
    for r in report:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
