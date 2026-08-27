#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.1 互转 demo：双均线策略 聚宽 ↔ PTrade 双向互转。

运行：python -m products.quant.demo
每步打印：生成的代码 + 校验结果；末尾断言往返 IR 一致。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from products.quant.emitters import emit                      # noqa: E402
from products.quant.ir import demo_ma_cross                   # noqa: E402
from products.quant.translate import roundtrip, translate     # noqa: E402


def _show(title: str, code: str) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}")
    print(code)


def main() -> None:
    ir0 = demo_ma_cross()
    print("原始 IR：")
    print(ir0.to_json())

    # 方向一：聚宽 → PTrade
    jq_code = emit(ir0, "joinquant")
    _show("聚宽代码（IR 直接发射）", jq_code)
    fwd = translate(jq_code, "joinquant", "ptrade")
    _show("互转结果：PTrade 代码", fwd["code"])
    v = fwd["validation"]
    print("PTrade 侧校验:", "✅ 通过" if v.ok else f"❌ {v.errors}")

    # 方向二：PTrade → 聚宽（往返）
    rt = roundtrip(fwd["code"], "ptrade", "joinquant")
    _show("往返结果：PTrade → 聚宽", rt["code_dst"])
    v2 = rt["validation"]
    print("聚宽侧校验:", "✅ 通过" if v2.ok else f"❌ {v2.errors}")

    # 一致性断言（source_platform 记录解析来源，往返后必然不同，比对时排除）
    a, b = rt["ir_src"], rt["ir_back"]
    a.source_platform = b.source_platform = ""
    same = a.to_json() == b.to_json()
    print("\n往返 IR 一致:", "✅" if same else "❌")
    if not same:
        print("--- 去程 IR ---"); print(rt["ir_src"].to_json())
        print("--- 回程 IR ---"); print(rt["ir_back"].to_json())
        sys.exit(1)
    print("\nv0.1 demo 完成：双均线 聚宽 ↔ PTrade 双向互转 + 语法/白名单校验通过")


if __name__ == "__main__":
    main()
