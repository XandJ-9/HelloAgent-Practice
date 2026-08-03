"""Small and intentionally constrained tools used by the agent."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


Tool = Callable[..., str]


class ToolError(Exception):
    """A recoverable error produced while selecting or running a tool."""


_BINARY_OPERATORS: Mapping[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS: Mapping[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression without using eval()."""

    try:
        tree = ast.parse(expression, mode="eval")
        value = _evaluate_node(tree.body)
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ToolError(f"无法计算表达式 {expression!r}: {exc}") from exc
    return str(value)


def _evaluate_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand))
    raise ValueError("只允许数字、括号和 + - * / 运算")


def make_text_reader(allowed_directory: Path) -> Tool:
    """Create a reader that cannot access files outside its data directory."""

    root = allowed_directory.resolve()

    def read_text(path: str) -> str:
        candidate = (root / path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ToolError("文件路径超出允许的数据目录")
        try:
            return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ToolError(f"无法读取文件 {path!r}: {exc}") from exc

    return read_text


def default_tools(data_directory: Path) -> dict[str, Tool]:
    return {
        "calculator": calculator,
        "read_text": make_text_reader(data_directory),
    }
