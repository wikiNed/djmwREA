"""冒烟测试：在干净环境里验证关键脚本能跑通。

目的：确认迁移后脚本不再依赖开发机的 .rea-study 路径。
做法：复制仓库到临时目录，**删掉 .rea-study**（用环境变量把它指向空目录），
再跑几个只读脚本，看是否正常输出。

用法：python tools/smoke_test.py
"""
from __future__ import annotations

import os
import subprocess
import sys
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
    # 模拟「干净机器」：禁掉 paths.py 里指向开发机 .rea-study 的兜底。
    # 不这样做的话，本机验证会被兜底掩盖，看不出是否真有隐藏依赖。
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["REA_NO_LEGACY"] = "1"
    env.pop("REA_SAVES", None)
    env.pop("REA_EMU", None)
    env.pop("IL2CPP_SO", None)
    env.pop("IL2CPP_DUMP", None)
    env.pop("IL2CPP_META", None)
    env.pop("TAPDEMONS_APK", None)

    print("=" * 60)
    print("冒烟测试")
    print("=" * 60)

    repo_files = (REPO / "files").resolve()
    tests = [
        # 断言不该写死仓库目录名（克隆目录可能叫别的名字），
        # 只验证解析结果落在 <repo>/files/ 之下。
        ("paths 解析落在仓库内", [PY, "-X", "utf8", "-c",
            "import sys; sys.path.insert(0, 'scripts'); import paths;"
            f"assert paths.SO.resolve().parent == paths.Path(r'{repo_files}'), paths.SO;"
            f"assert paths.DUMP.resolve().parent == paths.Path(r'{repo_files}'), paths.DUMP;"
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
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
