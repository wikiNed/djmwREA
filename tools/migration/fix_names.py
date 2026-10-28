"""修剩余 9 个脚本的变量名不匹配问题。

不是所有被删掉的赋值都该换成 paths 常量——先看它原本指向什么：
  ES3 = ...\\emu\\SaveFile.es3   -> paths.ES3_FILE
  MEM = ...\\emu\\memdump.bin    -> paths.MEMDUMP
  OUT = ...\\saves               -> paths.SAVES
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"

# 文件名 -> [(旧名, 新名)]
FIXES: dict[str, list[tuple[str, str]]] = {
    "brute_100iter.py": [("ES3", "ES3_FILE")],
    "brute_password.py": [("ES3", "ES3_FILE")],
    "brute_pbkdf2.py": [("ES3", "ES3_FILE")],
    "brute_pbkdf2_v2.py": [("ES3", "ES3_FILE")],
    "try_key.py": [("ES3", "ES3_FILE")],
    "try_key_deriv.py": [("ES3", "ES3_FILE")],
    "try_key_strict.py": [("ES3", "ES3_FILE")],
    "mem_str.py": [("MEM", "MEMDUMP")],
    "extract_saves.py": [("OUT", "SAVES")],
}


def patch_imports(text: str, new_names: set[str]) -> str:
    m = re.search(r"^from paths import (.+)$", text, re.M)
    if m:
        have = {x.strip() for x in m.group(1).split(",") if x.strip()}
        merged = ", ".join(sorted(have | new_names))
        return text[: m.start()] + f"from paths import {merged}" + text[m.end() :]
    return "from paths import " + ", ".join(sorted(new_names)) + "\n" + text


def main() -> int:
    dry = "--dry-run" in sys.argv
    for name, pairs in FIXES.items():
        p = SCRIPTS / name
        text = p.read_text(encoding="utf-8")
        orig = text
        new_names: set[str] = set()
        for old, new in pairs:
            # 只替换「作为独立名字出现」的地方，不动字符串与注释
            text2, n = re.subn(rf"(?<![\w.'\"]){re.escape(old)}(?![\w'\"])", new, text)
            if n == 0:
                print(f"[跳过] {name}: 未找到 {old}")
                continue
            text = text2
            new_names.add(new)
            # 导入里如果还有旧名，一并去掉
        if text != orig:
            text = patch_imports(text, new_names)
            # 清掉 import 里已不存在的旧名
            m = re.search(r"^from paths import (.+)$", text, re.M)
            if m:
                cur = [x.strip() for x in m.group(1).split(",") if x.strip()]
                olds = {o for o, _ in pairs}
                cur = [c for c in cur if c not in olds]
                text = text[: m.start()] + "from paths import " + ", ".join(cur) + text[m.end() :]
            if not dry:
                p.write_text(text, encoding="utf-8")
            print(f"{'[dry] ' if dry else ''}{name}: {', '.join(f'{o}->{n}' for o, n in pairs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
