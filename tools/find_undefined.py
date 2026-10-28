"""查找「迁移后仍引用已被删除的旧变量名」的脚本。

方法：对每个脚本做 AST 作用域分析（正确处理函数参数、局部赋值、
comprehension 变量、except 别名、with/try 目标），找出所有在**模块级**
被读取、却从未在模块级定义或导入的名字。

只报告名字形如全大写常量的（OUT/SO/DUMP/ES3/...），避免误报函数内局部变量。
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def collect_bound(node: ast.AST) -> set[str]:
    """收集一个作用域内所有被绑定（赋值/参数/导入/循环/with/except）的名字。"""
    bound: set[str] = set()

    class V(ast.NodeVisitor):
        def visit_Name(self, n: ast.Name):
            if isinstance(n.ctx, (ast.Store, ast.Del)):
                bound.add(n.id)

        def visit_arg(self, n: ast.arg):
            bound.add(n.arg)

        def visit_Import(self, n: ast.Import):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])

        def visit_ImportFrom(self, n: ast.ImportFrom):
            for a in n.names:
                bound.add(a.asname or a.name)

        def visit_FunctionDef(self, n: ast.FunctionDef):
            bound.add(n.name)  # 不深入函数体

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, n: ast.ClassDef):
            bound.add(n.name)

        def visit_ExceptHandler(self, n: ast.ExceptHandler):
            if n.name:
                bound.add(n.name)
            for x in n.body:
                self.visit(x)

    for child in ast.iter_child_nodes(node):
        V().visit(child)
    return bound


def module_scope_reads(tree: ast.Module) -> set[tuple[str, int]]:
    """模块级作用域里被读取的名字（含位置）。"""
    reads: set[tuple[str, int]] = set()

    class R(ast.NodeVisitor):
        def visit_Name(self, n: ast.Name):
            if isinstance(n.ctx, ast.Load):
                reads.add((n.id, n.lineno))

        def visit_FunctionDef(self, n):
            # 只检查默认参数与装饰器，不深入函数体
            for d in n.decorator_list:
                self.visit(d)
            for d in n.args.defaults:
                self.visit(d)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, n):
            for d in n.decorator_list:
                self.visit(d)
            for d in n.bases:
                self.visit(d)

    for child in ast.iter_child_nodes(tree):
        R().visit(child)
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # 上面的 visit 已处理装饰器/默认值
            pass
    return reads


def main() -> int:
    builtin = set(dir(builtins))
    found = 0
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "paths.py":
            continue
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print(f"{p.name}: 语法错误 {e}")
            found += 1
            continue

        bound = collect_bound(tree) | builtin
        reads = module_scope_reads(tree)

        # 只看全大写的常量名，减少噪音
        bad = [
            (n, ln)
            for n, ln in sorted(reads, key=lambda x: x[1])
            if n not in bound and n.isupper() and len(n) > 1
        ]
        if bad:
            found += 1
            print(f"{p.name}")
            for n, ln in dict.fromkeys(bad):
                print(f"    第 {ln:3d} 行引用了未定义的 {n}")
            print()

    if found == 0:
        print("通过：模块级没有引用未定义的常量")
    return 0


if __name__ == "__main__":
    sys.exit(main())
