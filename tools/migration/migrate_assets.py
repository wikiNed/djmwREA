"""第三轮：处理 Unity 资产与工具链路径。

两类：
  A. assets/data.unity3d  -> paths.unity_data_asset()   （从 APK 现取）
  B. ghidra / jdk         -> 读环境变量，缺失时明确提示如何安装
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
LEGACY = r"E:\DSH\game\.rea-study"
SEP = r"\\{1,2}"


def legacy_re(tail: str) -> re.Pattern:
    body = re.escape(LEGACY).replace(r"\\", SEP)
    return re.compile(r"""r?['"]""" + body + SEP + tail + r"""[\\/]{0,4}[^'"]*['"]""")


# A: Unity 资产
UNITY_RE = legacy_re(r"assets")


def fix_unity(text: str) -> tuple[str, bool]:
    if not UNITY_RE.search(text):
        return text, False
    text = UNITY_RE.sub("unity_data_asset()", text)
    return text, True


# B: 工具链 -> 环境变量优先
GHIDRA_RE = legacy_re(r"ghidra")
JDK_RE = legacy_re(r"jdk")


def fix_toolchain(text: str) -> tuple[str, bool]:
    changed = False
    if GHIDRA_RE.search(text):
        text = GHIDRA_RE.sub(
            "os.environ.get('GHIDRA_INSTALL_DIR')", text
        )
        changed = True
    if JDK_RE.search(text):
        # JAVA_HOME 直接从环境取，不再回退到硬编码的 jdk 目录
        text = re.sub(
            r"""os\.environ\[['"]JAVA_HOME['"]\]\s*=\s*os\.environ\.get\(['"]GHIDRA_INSTALL_DIR['"]\)""",
            "pass  # JAVA_HOME 由外部环境提供",
            text,
        )
        text = JDK_RE.sub("os.environ.get('JAVA_HOME')", text)
        changed = True
    return text, changed


def ensure_os_import(text: str) -> str:
    if re.search(r"^import os$", text, re.M) or re.search(r"^import .*\bos\b", text, re.M):
        return text
    return "import os\n" + text


def main() -> int:
    dry = "--dry-run" in sys.argv
    report = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "paths.py":
            continue
        text = p.read_text(encoding="utf-8")
        if LEGACY not in text:
            continue
        orig = text
        text, u = fix_unity(text)
        text, t = fix_toolchain(text)
        if text == orig:
            continue
        if u:
            if re.search(r"^from paths import", text, re.M):
                text = re.sub(
                    r"^from paths import (.+)$",
                    lambda m: "from paths import "
                    + ", ".join(sorted({x.strip() for x in m.group(1).split(",")}
                                       | {"unity_data_asset"})),
                    text,
                    count=1,
                    flags=re.M,
                )
            else:
                text = "from paths import unity_data_asset\n" + text
        if t:
            text = ensure_os_import(text)
        if not dry:
            p.write_text(text, encoding="utf-8")
        report.append((p.name, "unity" if u else "", "toolchain" if t else ""))

    print(f"{'[dry] ' if dry else ''}第三轮改写 {len(report)} 个文件")
    for n, a, b in report:
        tags = " / ".join(x for x in (a, b) if x)
        print(f"  {n:28s} {tags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
