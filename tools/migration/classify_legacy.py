"""列出仍未迁移的脚本及其残留路径，按依赖类型归类。"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
LEGACY = r"E:\DSH\game\.rea-study"

# 分类：这些不该进仓库（本机工具链），这些是中间产物，这些是真实输入
LOCAL_TOOLS = ("ghidra", "jdk", "work", "memd")
MIDPRODUCT = ("dump2", "mem2", "save_plain", "save_decrypted", "out")


def classify(rel: str) -> str:
    low = rel.replace("\\", "/").lower()
    if any(x in low for x in LOCAL_TOOLS):
        return "本机工具链"
    if any(x in low for x in MIDPRODUCT):
        return "中间产物"
    if "assets" in low:
        return "Unity 资产(未入库)"
    if "emu" in low:
        return "模拟器产物(未入库)"
    return "其他"


def main() -> None:
    buckets: dict[str, list[tuple[str, str]]] = {}
    for p in sorted(SCRIPTS.glob("*.py")):
        t = p.read_text(encoding="utf-8")
        if LEGACY not in t:
            continue
        for ln in t.splitlines():
            s = ln.strip()
            if LEGACY not in s or s.startswith("#"):
                continue
            # 取 legacy 之后的路径尾巴
            idx = s.find(LEGACY)
            tail = s[idx + len(LEGACY):]
            m = re.match(r"[\\/]+([^'\"\s)]+)", tail)
            rel = m.group(1) if m else "?"
            buckets.setdefault(classify(rel), []).append((p.name, rel))
            break

    for cat in ("本机工具链", "中间产物", "Unity 资产(未入库)", "模拟器产物(未入库)", "其他"):
        items = buckets.get(cat, [])
        if not items:
            continue
        print(f"=== {cat}（{len(items)} 个脚本）===")
        for name, rel in items:
            print(f"  {name:28s} {rel}")
        print()


if __name__ == "__main__":
    main()
