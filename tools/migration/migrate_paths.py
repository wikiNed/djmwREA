"""一次性迁移：把 scripts/ 下硬编码的 E:\\DSH\\game\\.rea-study 路径改为从 paths.py 取。

用法（在仓库根目录）：
    python tools/migrate_paths.py [--dry-run]

策略：
  - 只处理形如  NAME = r"E:\\DSH\\...\\xxx"  或  NAME = "E:\\..."  的整行赋值
  - 从原路径推断对应哪个常量（libil2cpp.so / dump.cs / global-metadata.dat /
    apk / saves / work / evidence / emu / lib）
  - 全部替换行删掉，并在 import 块末尾插入 from paths import ...
  - 以 UTF-8 读、UTF-8 写，保持原编码
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
LEGACY = r"E:\DSH\game\.rea-study"

# 路径片段 -> paths.py 里的名字
RULES = [
    ("libil2cpp.so", "SO"),
    ("dump.cs", "DUMP"),
    ("global-metadata.dat", "META"),
    ("TapDemons", "APK"),
    (r"saves", "SAVES"),
    (r"work", "WORK"),
    (r"evidence", "EVIDENCE"),
    (r"emu", "EMU"),
]

# 坑（踩了三次才定位）：仓库里的脚本是当年从 PowerShell here-string 写出来的，
# 路径分隔符被转义成了 **双反斜杠**：r"E:\\DSH\\game\\.rea-study\\lib\\..."
# （Windows 容忍重复分隔符，所以脚本一直能跑，但写法规不规范。）
# 所以正则必须把 \ 写成 \\ 这一组，同时兼容单反斜杠的老写法。
_SEP = r"\\{1,2}"
_LEGACY_RE = re.escape(LEGACY).replace(r"\\", _SEP)
ASSIGN_RE = re.compile(
    r"""^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*r?(?P<q>['"])"""
    + _LEGACY_RE
    + r"""(?P<rest>[^'"]*)(?P=q)\s*$""",
    re.M,
)


def classify(rest: str) -> str | None:
    low = rest.replace("\\", "/").lower()
    for frag, name in RULES:
        if frag.lower() in low:
            return name
    return None


def inject_import(text: str, names: set[str]) -> str:
    """插入 from paths import ...，只放在模块文档字符串之后的安全位置。

    坑：早期版本找「最后一个顶层 import」，结果在
    find_slot_writers.py / unitypy_anchor.py / try_key.py 里把 import
    塞进了 try 块和缩进代码中，导致语法错误。
    现在只在文件头部（跳过 docstring 与注释）插入，不碰任何缩进上下文。
    """
    if not names:
        return text
    imp = "from paths import " + ", ".join(sorted(names))

    lines = text.split("\n")

    # 若已存在 from paths import，合并后返回
    for i, ln in enumerate(lines):
        if ln.strip().startswith("from paths import"):
            have = {x.strip() for x in ln.split("import", 1)[1].split(",") if x.strip()}
            lines[i] = "from paths import " + ", ".join(sorted(have | names))
            return "\n".join(lines)

    # 跳过模块 docstring（可能跨多行）
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines):
        s = lines[idx].lstrip()
        if s.startswith('"""') or s.startswith("'''"):
            quote = s[:3]
            rest = s[3:]
            if quote in rest:  # 单行 docstring
                idx += 1
            else:
                idx += 1
                while idx < len(lines) and quote not in lines[idx]:
                    idx += 1
                idx += 1  # 跨过结束引号所在行

    # 跳过紧随其后的空行与注释、以及 __future__ import
    while idx < len(lines) and (
        not lines[idx].strip() or lines[idx].lstrip().startswith("#")
    ):
        idx += 1
    if idx < len(lines) and "from __future__" in lines[idx]:
        idx += 1

    lines.insert(idx, imp)
    lines.insert(idx + 1, "")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = []
    skipped = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "paths.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if LEGACY not in text:
            continue

        names: set[str] = set()
        unknown: list[str] = []

        def repl(m: re.Match) -> str:
            rest = m.group("rest")
            name = classify(rest)
            if name is None:
                unknown.append(rest)
                return m.group(0)  # 保持原样
            names.add(name)
            return f"<<DROP:{m.group('name')}>>"

        new = ASSIGN_RE.sub(repl, text)
        new = re.sub(r"^<<DROP:[A-Za-z_][A-Za-z0-9_]*>>\n?", "", new, flags=re.M)
        new = re.sub(r"\n{4,}", "\n\n\n", new)

        if LEGACY in new:
            left = [
                ln.strip()
                for ln in new.splitlines()
                if LEGACY in ln and not ln.strip().startswith("#")
            ]
            skipped.append((p.name, left[:2]))
            continue

        if new != text:
            new = inject_import(new, names)
            changed.append((p.name, sorted(names)))
            if not args.dry_run:
                p.write_text(new, encoding="utf-8")

    print(f"{'[dry-run] ' if args.dry_run else ''}改写 {len(changed)} 个文件")
    for name, ns in changed:
        print(f"  {name:32s} -> {', '.join(ns)}")
    if skipped:
        print(f"\n仍残留（无法自动判定，需人工）：{len(skipped)} 个")
        for name, left in skipped[:15]:
            print(f"  {name}")
            for ln in left:
                print(f"      {ln[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
