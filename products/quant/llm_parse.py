# -*- coding: utf-8 -*-
"""LLM 解析器：任意手写策略代码 → StrategyIR（parsers 的 ParseError 兜底）。

链路：手写代码 → RAG 检索（API 对照表 + few-shot 策略对）→ 组 prompt
     → LLM 输出 IR JSON → 严格校验 → 失败带错误反馈重试（默认 2 次）。

LLM 调用通过 chat_fn 注入（chat_fn(messages) -> str），：
  - 测试用 mock，无需网络/key
  - 生产默认 default_chat()：走 core 的 llm.stream_chat + 用户默认模型
    （量化产品定位本地模型，用户在设置里把默认模型指到本地即可策略不出机）
"""

from __future__ import annotations

import json
import re

from . import kb
from .ir import KNOWN_KINDS_HINT, StrategyIR
from .parsers import ParseError

_SYSTEM = """你是量化策略解析器。把用户给的聚宽/PTrade 策略源码解析为策略中间表示 IR（JSON）。

只输出一个 JSON 对象，不要任何解释、不要 markdown 代码围栏。字段：
{name: str, universe: [标的代码...], schedule: {freq: "daily"|"minute"|"tick", time: str},
 signals: [{kind, params: {}, condition: str}], order: {style: "target_pct", pct: 0-1},
 risk: {}, source_platform: str}
""" + KNOWN_KINDS_HINT + """
拿不准的字段宁可保守填默认值，不要编造平台 API。参数数值必须来自源码。"""

_JSON_RE = re.compile(r"\{.*\}", re.S)


def default_chat(messages: list[dict]) -> str:
    """生产链路：core llm.stream_chat + 模型。

    量化 LLM 兜底优先用「派发配置的云端 pro」（deepseek/deepseek-v4-pro，更强）；
    未配置或为本地则回退 app 默认模型。
    """
    import config  # noqa: PLC0415 延迟导入，避免拖慢无 LLM 场景
    import llm     # noqa: PLC0415

    models, _def_key = config.load_models()
    # 优先级：面板指定的 quant_llm_model > 派发云端 pro > 应用默认
    key = config.get_quant_llm_model() if hasattr(config, "get_quant_llm_model") else ""
    if not key:
        try:
            if hasattr(config, "get_dispatch_pro"):
                k = config.get_dispatch_pro()
                if k and not k.startswith("gpulocal"):
                    key = k
        except Exception:        # noqa: BLE001
            pass
    if not key:
        key = _def_key
    model = config.find_model(key) or (models[0] if models else None)
    if model is None:
        raise RuntimeError("未配置任何模型（设置里添加模型后再试）")
    parts: list[str] = []
    for ev in llm.stream_chat(model, messages):
        if ev.get("type") == "text":
            parts.append(ev["delta"])
    return "".join(parts)


def build_messages(source: str, platform: str, k: int = 3) -> list[dict]:
    """组 prompt：系统规则 + 对照表 + few-shot + 官方文档片段 + 目标代码。"""
    shots = kb.retrieve(source, k=k, kind="fewshot")
    kb_hits = kb.retrieve(source, k=1, kind="kb", snippet=True)
    api_maps = [d for d in kb.load_documents() if d["kind"] == "api_map"]
    ctx_parts = []
    if api_maps:
        ctx_parts.append("# 平台 API 对照表\n"
                         + "\n\n".join(d["text"] for d in api_maps))
    if kb_hits:
        ctx_parts.append("# 官方 API 文档（检索片段）\n" + kb_hits[0]["text"])
    ctx_parts += [d["text"] for d in shots]
    user = ("\n\n".join(ctx_parts)
            + f"\n\n# 待解析策略（平台：{platform}）\n```python\n{source}\n```"
            + "\n\n输出它的 IR JSON：")
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user}]


def extract_json(text: str) -> dict:
    """从 LLM 输出提取 JSON 对象（容忍 ```json 围栏和前后废话）。"""
    m = _JSON_RE.search(text or "")
    if not m:
        raise ParseError("LLM 输出中未找到 JSON 对象")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ParseError(f"LLM 输出 JSON 解析失败: {e}") from e


def _validate_ir(ir: StrategyIR) -> None:
    if not ir.universe:
        raise ParseError("LLM 输出的 IR 缺少 universe")
    if not ir.signals:
        raise ParseError("LLM 输出的 IR 缺少 signals")


def parse_with_llm(source: str, platform: str,
                   chat_fn=default_chat, max_retries: int = 2) -> StrategyIR:
    """手写策略代码 → IR。失败带反馈重试，最终失败抛 ParseError。"""
    messages = build_messages(source, platform)
    last_err = ""
    for _ in range(max_retries + 1):
        if last_err:
            messages.append({"role": "user", "content":
                             f"上一次输出有问题：{last_err}。请重新只输出修正后的 IR JSON。"})
        raw = chat_fn(messages)
        try:
            data = extract_json(raw)
            data.setdefault("source_platform", platform)
            ir = StrategyIR.from_json(json.dumps(data, ensure_ascii=False))
            _validate_ir(ir)
            return ir
        except (ParseError, TypeError, KeyError) as e:
            last_err = str(e)
            messages.append({"role": "assistant", "content": raw})
    raise ParseError(f"LLM 解析重试 {max_retries} 次仍失败：{last_err}")
