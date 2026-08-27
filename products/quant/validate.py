# -*- coding: utf-8 -*-
"""静态校验：语法 + API 白名单（沙箱约束）。

白名单依据 api_maps/joinquant_ptrade.md「沙箱约束」一节：
两平台云端容器均禁止 os/sys/subprocess、文件读写、网络访问。
backtrader 语义校验（信号一致率）属 v0.5，不在本模块。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

# 两平台云端容器统一禁止（对照表已核实部分，不含臆造项）
_FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "socket", "requests", "urllib",
    "shutil", "pathlib", "io", "pickle", "importlib",
}
_FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__",
                    "input", "exit", "quit"}


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)


def check_syntax(code: str, result: ValidationResult) -> None:
    try:
        compile(code, "<strategy>", "exec")
    except SyntaxError as e:
        result.add(f"语法错误: {e}")


def check_whitelist(code: str, platform: str,
                    result: ValidationResult) -> None:
    """AST 扫描违禁 import / 调用。platform 目前两平台同规则，参数留着分平台细化。"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # 语法错误已由 check_syntax 报告
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in _FORBIDDEN_IMPORTS:
                    result.add(f"违禁 import: {a.name}（沙箱禁止文件/网络/系统访问）")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                result.add(f"违禁 import: from {node.module}（沙箱禁止）")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALLS:
                result.add(f"违禁调用: {node.func.id}()（沙箱禁止）")


def validate(code: str, platform: str) -> ValidationResult:
    """语法 + 白名单一次跑完。"""
    r = ValidationResult()
    check_syntax(code, r)
    check_whitelist(code, platform, r)
    return r
