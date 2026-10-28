"""清理器：修掉迁移留下的机械问题。

处理：
  1. 自赋值 (SO = SO, APK = APK)  -> 删除该行
  2. 无意义环境变量自设 (os.environ["X"] = os.environ.get('X')) -> 删除
  3. import 语句被插到模块 docstring 之前 -> 移到 docstring 之后
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def fix_self_assign(text: str) -> tuple[str, int]:
    """删除 `X = X` 这种模块级自赋值。"""
    tree = ast.parse(text)
    lines = text.split("\n")
    drop = []
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.targets[0].id == node.value.id
        ):
            for ln in range(node.lineno - 1, node.end_lineno):
                drop.append(ln)
    for ln in sorted(set(drop), reverse=True):
        del lines[ln]
    return "\n".join(lines), len(set(drop))


def fix_env_selfset(text: str) -> tuple[str, int]:
    """删除 os.environ["X"] = os.environ.get('X') 这类空操作。"""
    pat = re.compile(
        r"""^[ \t]*os\.environ\[(?P<a>['"])(?P<k>\w+)(?P=a)\]\s*=\s*os\.environ\.get\((?P<b>['"])(?P=k)(?P=b)\)[ \t]*\n""",
        re.M,
    )
    return pat.subn("", text)


def move_import_after_docstring(text: str) -> tuple[str, bool]:
    """把被插到 docstring 之前的 `from paths import ...` 移到 docstring 之后。"""
    lines = text.split("\n")
    import_idx = None
    for i, ln in enumerate(lines[:5]):
        if ln.startswith("from paths import"):
            import_idx = i
            break
    if import_idx is None:
        return text, False

    # 找 docstring 起始（跳过 import 行后的空行）
    j = import_idx + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return text, False
    s = lines[j].lstrip()
    if not (s.startswith('"""') or s.startswith("'''")):
        return text, False

    quote = s[:3]
    # 找 docstring 结束行
    k = j
    rest = s[3:]
    if quote in rest:
        end = k
    else:
        k += 1
        while k < len(lines) and quote not in lines[k]:
            k += 1
        end = k

    imp_line = lines.pop(import_idx)
    # docstring 结束行位置因删除而前移 1
    end = end - 1 if end > import_idx else end
    # 在 docstring 结束后插入 import 和空行
    lines.insert(end + 1, "")
    lines.insert(end + 2, imp_line)
    return "\n".join(lines), True


def main() -> int:
    dry = "--dry-run" in sys.argv
    report = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "paths.py":
            continue
        text = p.read_text(encoding="utf-8")
        orig = text
        text, n1 = fix_self_assign(text)
        text, n2 = fix_env_selfset(text)
        text, moved = move_import_after_docstring(text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        if text != orig:
            if not dry:
                p.write_text(text, encoding="utf-8")
            report.append((p.name, n1, n2, moved))

    print(f"{'[dry] ' if dry else ''}清理 {len(report)} 个文件")
    for n, a, b, c in report:
        bits = []
        if a:
            bits.append(f"删自赋值 {a}")
        if b:
            bits.append(f"删空操作 {b}")
        if c:
            bits.append("import 移到 docstring 后")
        print(f"  {n:28s} {', '.join(bits)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
