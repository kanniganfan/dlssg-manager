#!/usr/bin/env python3
"""静态自检：捕获"元组结构改了但遍历点没同步"这类错误。

用法: python scripts/check_tuple_arity.py

WT 项目里 ENTRIES / RUNTIMES 是固定长度的元组表，加字段时极易漏改遍历点
（本项目犯过两次：ENTRIES 4→5 元后 entry_of_deployment 仍按 4 解包）。
本脚本用 AST 找出所有对这些表的名字解包/索引的地方，核对 arity。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if not SRC.is_dir():
    SRC = Path(__file__).resolve().parents[2] / "DLSSG_Manager"

# 表名 -> 预期元组长度（从源码 AST 里读名字绑定推断，这里做兜底声明）
EXPECTED = {"ENTRIES": 5, "RUNTIMES": 3, "GPU_NAME_VALUES": None}


def tuple_arity_from_ast(tree: ast.Module) -> dict[str, int]:
    """找出形如 NAME = [(...), ...] 的模块级列表，返回其元素元组长度。"""
    out: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name) or not isinstance(node.value, ast.List):
                continue
            elts = node.value.elts
            first = next((e for e in elts if isinstance(e, ast.Tuple)), None)
            if first is not None:
                out[tgt.id] = len(first.elts)
    return out


def main() -> int:
    problems: list[str] = []
    for py in sorted(SRC.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        arity = tuple_arity_from_ast(tree) or EXPECTED

        for node in ast.walk(tree):
            # 1) for a, b, c, ... in NAME:
            if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple) \
                    and isinstance(node.iter, ast.Name):
                name = node.iter.id
                if name in arity:
                    want = arity[name]
                    got = len(node.target.elts)
                    if got != want:
                        problems.append(
                            f"{py.name}:{node.lineno} for 解包 {got} 元组，"
                            f"但 {name} 是 {want} 元组")
            # 2) 解包式赋值 a, b, c = NAME[i]
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Tuple):
                v = node.value
                if isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) \
                        and v.value.id in arity:
                    want = arity[v.value.id]
                    got = len(node.targets[0].elts)
                    if got != want:
                        problems.append(
                            f"{py.name}:{node.lineno} 下标解包 {got} 元组，"
                            f"但 {v.value.id} 是 {want} 元组")

    if problems:
        print("发现元组 arity 不一致：")
        for p in problems:
            print("  -", p)
        return 1
    print(f"元组 arity 自检通过（{SRC}）")
    for name, n in (EXPECTED.items() if not arity else arity.items()):
        print(f"  {name}: {n} 元组")
    return 0


if __name__ == "__main__":
    sys.exit(main())
