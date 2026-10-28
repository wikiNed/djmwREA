"""第二轮迁移：处理自动脚本漏掉的、路径写在表达式里的情况。

覆盖：
  - open(r"E:\\...\\dump.cs", ...)        -> open(DUMP, ...)
  - UnityPy.load(r"E:\\...\\apk\\xxx.apk") -> UnityPy.load(APK)
  - data = open(r"E:\\...\\lib\\libil2cpp.so","rb").read() -> open(SO,...)
  - os.environ["GHIDRA_INSTALL_DIR"] = r"E:\\...\\ghidra\\..."  -> 读环境变量
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
LEGACY = r"E:\DSH\game\.rea-study"
# 仓库里实际是双反斜杠写法
SEP = r"\\{1,2}"


def legacy_re(tail_pattern: str) -> re.Pattern:
    """构造匹配 r"E:\\DSH\\...\\<tail>" 的正则。

    坑（两次踩）：仓库里路径写法不统一——有的文件是单反斜杠 (\\DSH)，
    有的是双反斜杠 (\\\\DSH)，必须用 \\{1,2} 兼容两者。
    另外 tail_pattern 里的分隔符也统一交给 SEP 处理，
    不要再手工在前面拼 "% SEP" 再接文件名（会多出空格导致失配）。
    """
    body = re.escape(LEGACY).replace(r"\\", SEP)
    return re.compile(r"""r?['"]""" + body + SEP + tail_pattern + r"""[\\/]{0,4}[^'"]*['"]""")


RULES: list[tuple[re.Pattern, str]] = [
    (legacy_re(r"lib" + SEP + r"libil2cpp\.so"), "SO"),
    (legacy_re(r"lib" + SEP + r"global-metadata\.dat"), "META"),
    (legacy_re(r"apk" + SEP + r"TapDemons[^'\"\\/]*\.apk"), "APK"),
    (legacy_re(r"dump" + SEP + r"dump\.cs"), "DUMP"),
    (legacy_re(r"emu" + SEP + r"SaveFile\.es3"), "ES3_FILE"),
    (legacy_re(r"saves"), "SAVES"),
]


def main() -> int:
    dry = "--dry-run" in sys.argv
    changed = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "paths.py":
            continue
        text = p.read_text(encoding="utf-8")
        if LEGACY not in text:
            continue
        orig = text
        needed: set[str] = set()

        # 1) 先做限定于「表达式内」的替换（不处理整行赋值，那些第一轮已处理）
        for pat, name in RULES:
            def sub(m, _n=name):
                needed.add(_n)
                return _n
            text = pat.sub(sub, text)

        if text == orig:
            continue

        # 2) 补 import
        m = re.search(r"^from paths import (.+)$", text, re.M)
        if m:
            have = {x.strip() for x in m.group(1).split(",") if x.strip()}
            text = text[: m.start()] + "from paths import " + ", ".join(sorted(have | needed)) + text[m.end():]
        else:
            text = "from paths import " + ", ".join(sorted(needed)) + "\n" + text

        if not dry:
            p.write_text(text, encoding="utf-8")
        changed.append((p.name, sorted(needed)))

    print(f"{'[dry] ' if dry else ''}第二轮改写 {len(changed)} 个文件")
    for n, ns in changed:
        print(f"  {n:28s} -> {', '.join(ns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
