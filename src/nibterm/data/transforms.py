"""Expression evaluation for plot transforms.

This module provides a sandboxed evaluator that supports basic math
operations (``+``, ``-``, ``*``, ``/``, ``**``, ``%``), common math
functions (sin, cos, sqrt, …), and named variables.
"""
from __future__ import annotations

import ast
import math

# Functions allowed inside user-defined expressions
ALLOWED_FUNCS: dict[str, object] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
}

# Names in expressions that are not variable references
_RESERVED = frozenset(ALLOWED_FUNCS) | {"pi", "e"}


def safe_eval(expr: str, variables: dict[str, float]) -> float:
    """Evaluate a mathematical expression in a restricted scope."""
    tree = ast.parse(expr, mode="eval")
    _validate_ast(tree)
    scope: dict[str, object] = {"__builtins__": {}}
    scope.update(ALLOWED_FUNCS)
    scope.update({"pi": math.pi, "e": math.e})
    scope.update(variables)
    return eval(compile(tree, "<expr>", "eval"), scope, {})  # noqa: S307


def _validate_ast(tree: ast.AST) -> None:
    """Walk the AST and raise ValueError for any disallowed node type."""
    _ALLOWED_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
    _ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.Constant):
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_OPS):
            continue
        if isinstance(node, _ALLOWED_OPS):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY_OPS):
            continue
        if isinstance(node, _ALLOWED_UNARY_OPS):
            continue
        if isinstance(node, ast.Name):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in ALLOWED_FUNCS:
                raise ValueError("Unsupported function in expression.")
            continue
        raise ValueError("Unsupported expression.")


def get_expression_variable_names(expr: str) -> set[str]:
    """Return the set of variable names referenced in an expression (not functions/constants)."""
    if not (expr or expr.strip()):
        return set()
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _RESERVED:
            names.add(node.id)
    return names


def rewrite_expression_rename(expr: str, old_name: str, new_name: str) -> str:
    """Replace all references to old_name with new_name in the expression. Returns expr unchanged on parse error."""
    if not expr or old_name == new_name:
        return expr
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return expr

    class _Renamer(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == old_name:
                return ast.Name(id=new_name, ctx=node.ctx)
            return self.generic_visit(node)

    tree = _Renamer().visit(tree)
    return ast.unparse(tree)
