"""第四轮：处理最后 6 个脚本的残留路径。

这些都是「输出到中间产物」或「sys.path 插入」，不适合做成 paths 常量：
  - 输出文件      -> 写到 EMU 目录下
  - 输入目录/文件 -> 改为必填或默认为 EMU 下的相对名
  - sys.path.insert -> 改为指向本仓库 scripts/
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
LEGACY = r"E:\DSH\game\.rea-study"
SEP = r"\\{1,2}"


def L(tail: str) -> re.Pattern:
    body = re.escape(LEGACY).replace(r"\\", SEP)
    return re.compile(r"""r?['"]""" + body + SEP + tail + r"""[\\/]{0,4}[^'"]*['"]""")


# (匹配, 替换, 需要导入的名字)
RULES: list[tuple[re.Pattern, str, set[str]]] = [
    # 输出：解密结果 -> EMU 下
    (L(r"emu" + SEP + r"save_decrypted\.json"), "str(SAVE_OUT)", {"SAVE_OUT"}),
    (L(r"emu" + SEP + r"save_plain\.json"), "str(SAVE_PLAIN)", {"SAVE_PLAIN"}),
    # 输入：内存 dump 目录/文件
    (L(r"emu" + SEP + r"dump2"), "str(EMU / 'dump2')", {"EMU"}),
    (L(r"emu" + SEP + r"memd"), "str(EMU / 'memd')", {"EMU"}),
    (L(r"emu" + SEP + r"mem2\.bin"), "str(EMU / 'mem2.bin')", {"EMU"}),
    # 自己 import 自己：指向仓库 scripts 目录
    (L(r"scripts"), "str(Path(__file__).resolve().parent)", {"Path"}),
]


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
        needed: set[str] = set()
        for pat, repl, names in RULES:
            def sub(m, r=repl, ns=names):
                needed.update(ns)
                return r
            text = pat.sub(sub, text)
        if text == orig:
            continue

        # 补 import
        extra = []
        if "SAVE_OUT" in needed:
            # SAVE_OUT 不是 paths 里的名字，就地定义
            text = text.replace(
                "from paths import", "from paths import EMU\nSAVE_OUT = EMU / 'save_decrypted.json'\nfrom paths import",
                1,
            ) if "from paths import" in text else "from paths import EMU\nSAVE_OUT = EMU / 'save_decrypted.json'\n" + text
            needed.discard("SAVE_OUT")
            needed.add("EMU")
        pnames = {n for n in needed if n in {"EMU", "SAVE_PLAIN"}}
        stdlib = {n for n in needed if n in {"Path"}}

        if pnames:
            if re.search(r"^from paths import", text, re.M):
                text = re.sub(
                    r"^from paths import (.+)$",
                    lambda m: "from paths import " + ", ".join(sorted(
                        {x.strip() for x in m.group(1).split(",")} | pnames)),
                    text, count=1, flags=re.M,
                )
            else:
                text = "from paths import " + ", ".join(sorted(pnames)) + "\n" + text
        if stdlib:
            if not re.search(r"^from pathlib import", text, re.M):
                text = "from pathlib import Path\n" + text
            else:
                text = re.sub(
                    r"^from pathlib import (.+)$",
                    lambda m: "from pathlib import " + ", ".join(sorted(
                        {x.strip() for x in m.group(1).split(",")} | stdlib)),
                    text, count=1, flags=re.M,
                )

        if not dry:
            p.write_text(text, encoding="utf-8")
        report.append((p.name, sorted(needed)))

    print(f"{'[dry] ' if dry else ''}第四轮改写 {len(report)} 个文件")
    for n, ns in report:
        print(f"  {n:28s} -> {', '.join(ns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
