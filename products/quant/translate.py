# -*- coding: utf-8 -*-
"""策略互转主流程：源平台代码 → IR → 目标平台代码 → 校验。

    translate(source_code, "joinquant", "ptrade")
        → {"ir": StrategyIR, "code": str, "validation": ValidationResult}

LLM 解析兜底：chat_fn 不为 None 时，AST 确定性解析抛 ParseError
会转 llm_parse.parse_with_llm（RAG：API 对照表 + few-shot 策略对）。
chat_fn 签名：chat_fn(messages) -> str；传 True 用生产默认
（core llm.stream_chat + 用户默认模型）。
"""

from __future__ import annotations

import time
from datetime import datetime

from .emitters import emit
from .ir import StrategyIR
from .parsers import ParseError, parse_code
from .validate import ValidationResult, validate


def _parse(source_code: str, platform: str, chat_fn) -> StrategyIR:
    try:
        return parse_code(source_code, platform)
    except ParseError:
        if chat_fn is None:
            raise
        from .llm_parse import default_chat, parse_with_llm  # noqa: PLC0415
        fn = default_chat if chat_fn is True else chat_fn
        return parse_with_llm(source_code, platform, chat_fn=fn)


# 平台标识 / 信号 / 数据周期 / 时点 → 中文名（生成代码备注里展示用）
_PLATFORM_NAMES = {"joinquant": "聚宽", "ptrade": "PTrade",
                   "gm": "掘金", "qmt": "QMT"}
_KIND_CN = {"ma_cross": "双均线交叉", "threshold": "价格阈值", "rsi": "RSI 超买超卖",
            "bollinger": "布林带", "grid": "网格", "momentum_rotation": "动量轮动"}
_FREQ_CN = {"daily": "日线", "minute": "分钟线", "tick": "tick 逐笔"}
_TIME_CN = {"open": "开盘", "close": "收盘"}


def _signal_desc(sig) -> str:
    """信号的人类可读逻辑：优先用 condition（解析器/LLM 已填），否则按 kind 兜底拼接。"""
    if sig.condition:
        return sig.condition
    k = _KIND_CN.get(sig.kind, sig.kind)
    p = sig.params
    if sig.kind == "ma_cross":
        return (f"{k}策略：MA{p.get('fast', '?')} 上穿 MA{p.get('slow', '?')} 买入，"
                f"下穿卖出（取价 {p.get('price', 'close')}）")
    if sig.kind == "threshold":
        return (f"{k}策略：价格 ≤ {p.get('buy_below', '?')} 买入，"
                f"≥ {p.get('sell_above', '?')} 卖出")
    if sig.kind == "rsi":
        return (f"{k}策略：RSI({p.get('period', '?')}) ≤ {p.get('buy_below', '?')} 买入，"
                f"≥ {p.get('sell_above', '?')} 卖出")
    if sig.kind == "bollinger":
        return (f"{k}策略：中轨(周期 {p.get('period', '?')}，"
                f"{p.get('std_mult', '?')} 倍标准差)上下轨买卖")
    if sig.kind == "grid":
        return f"{k}策略：按 {p.get('step', '?')} 价格比例网格加减仓"
    if sig.kind == "momentum_rotation":
        return (f"{k}策略：近 {p.get('lookback', '?')} 日动量打分，选前 "
                f"{p.get('top_n', '?')} 强标的等权持有")
    return f"{k}策略（{sig.kind}，参数 {p}）"


def _logic_desc(ir: StrategyIR) -> str:
    """整体策略逻辑说明：信号逻辑 + 下单语义，用「；」拼接。"""
    parts = [_signal_desc(s) for s in ir.signals] or ["未识别出明确信号逻辑"]
    o = ir.order
    if o.style == "target_pct":
        parts.append(f"目标仓位 {o.pct:.0%}")
    elif o.style == "target_value":
        parts.append("固定市值下单")
    elif o.style == "limit":
        parts.append("限价单")
    return "；".join(parts)


def _schedule_desc(ir: StrategyIR) -> str:
    """数据周期说明：日线/分钟线/tick，附触发时点。"""
    s = ir.schedule
    freq = _FREQ_CN.get(s.freq, s.freq)
    if not s.time:
        return freq
    t = s.time if ":" in s.time else _TIME_CN.get(s.time, f"{s.time} 点")
    return f"{freq}（{t}触发）"


def _convert_header(ir: StrategyIR, src: str, dst: str, seconds: float) -> str:
    """生成代码头部备注：原策略 / 目标平台 / 数据周期 / 标的 / 策略逻辑 / 时间 / 用时。"""
    src_cn = _PLATFORM_NAMES.get(src, src)
    dst_cn = _PLATFORM_NAMES.get(dst, dst)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    name = ir.name or "未命名策略"
    return (
        "# ============================================================\n"
        "# 策略互转生成代码\n"
        f"#   原策略(源平台): {name}（{src_cn}）\n"
        f"#   目标平台     : {dst_cn}\n"
        f"#   数据周期     : {_schedule_desc(ir)}\n"
        f"#   标的数量     : {len(ir.universe)}\n"
        f"#   策略逻辑     : {_logic_desc(ir)}\n"
        f"#   生成时间     : {now}\n"
        f"#   转换用时     : {seconds:.2f}s\n"
        "# ============================================================\n\n"
    )


def translate(source_code: str, src_platform: str,
              dst_platform: str, chat_fn=None) -> dict:
    """单方向互转。返回 ir / 目标代码 / 校验结果。"""
    t0 = time.time()
    ir = _parse(source_code, src_platform, chat_fn)
    code = emit(ir, dst_platform)
    vr = validate(code, dst_platform)
    code = _convert_header(ir, src_platform, dst_platform,
                           time.time() - t0) + code
    return {"ir": ir, "code": code, "validation": vr}


def roundtrip(source_code: str, src_platform: str,
              dst_platform: str, chat_fn=None) -> dict:
    """A → B → A 往返：验证互转语义不漂移。返回两端 IR 供一致性断言。"""
    fwd = translate(source_code, src_platform, dst_platform, chat_fn=chat_fn)
    back_ir = _parse(fwd["code"], dst_platform, chat_fn)
    return {"ir_src": fwd["ir"], "ir_back": back_ir,
            "code_dst": fwd["code"], "validation": fwd["validation"]}


__all__ = ["translate", "roundtrip", "ParseError",
           "StrategyIR", "ValidationResult"]
