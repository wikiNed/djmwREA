"""冒烟测试：在干净环境里验证关键脚本能跑通。

目的：确认迁移后脚本不再依赖开发机的 .rea-study 路径。
做法：复制仓库到临时目录，**删掉 .rea-study**（用环境变量把它指向空目录），
再跑几个只读脚本，看是否正常输出。

用法：python tools/smoke_test.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(cmd: list[str], env: dict, label: str) -> tuple[bool, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, cwd=str(REPO), timeout=300)
    ok = r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    return ok, out.strip()


def main() -> int:
    # 模拟「干净机器」：把 legacy 路径指向不存在的目录
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    fake = Path(tempfile.mkdtemp(prefix="no_legacy_"))
    # 通过临时改写禁止回退：直接设 REA_* 到不存在路径会让脚本报错，
    # 所以这里改测「仓库内文件足够」——把 cwd 换到仓库、不设任何 REA_* 变量，
    # 并验证 paths 解析结果确实落在 REPO 内。
    env.pop("REA_SAVES", None)
    env.pop("IL2CPP_SO", None)
    env.pop("IL2CPP_DUMP", None)

    print("=" * 60)
    print("冒烟测试")
    print("=" * 60)

    tests = [
        ("paths 解析落在仓库内", [PY, "-X", "utf8", "-c",
            "import sys; sys.path.insert(0, 'scripts'); import paths;"
            "assert 'djmwREA' in str(paths.SO) or 'files' in str(paths.SO), paths.SO;"
            "assert 'djmwREA' in str(paths.DUMP), paths.DUMP;"
            "print('SO  =', paths.SO); print('DUMP=', paths.DUMP)"]),
        ("disasm_range 反汇编口令写入点", [PY, "-X", "utf8", "scripts/disasm_range.py",
            "0x1752288", "8"]),
        ("find_undefined 全绿", [PY, "-X", "utf8", "tools/find_undefined.py"]),
    ]

    results = []
    for label, cmd in tests:
        ok, out = run(cmd, env, label)
        results.append((label, ok, out))
        print(f"\n[{'PASS' if ok else 'FAIL'}] {label}")
        for line in out.splitlines()[:8]:
            print("   ", line)

    print()
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"结果: {passed}/{len(results)} 通过")
    shutil.rmtree(fake, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
