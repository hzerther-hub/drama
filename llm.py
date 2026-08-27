# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 客户端：流式 chat + tool_calls 累积。"""

from __future__ import annotations
import json
import urllib.error
import urllib.request

import config


class LLMError(Exception):
    pass


def _post_stream(model: config.ModelConfig, messages, tools):
    """流式 POST，yield 每个 SSE data JSON 对象。"""
    body = {
        "model": model.model_id,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        # 本地(gpulocal)模型 n_ctx 仅 ~131K，输出上限单独钳到 16K；
        # 云端(deepseek 1M 上下文)用全局 MAX_TOKENS(对齐 DSH 256K)
        "max_tokens": (16384 if model.key.startswith("gpulocal")
                       else config.MAX_TOKENS),
        "stream": True,
        # 请求在流末尾附带 usage（标准 OpenAI 及多数兼容端点支持；
        # 不支持的后端会忽略此参数，不影响正常输出）
        "stream_options": {"include_usage": True},
    }
    if tools:
        body["tools"] = tools
    # 推理等级（reasoning effort）：模型配置了才发送（如 low/medium/high）；兼容
    # OpenAI 及多数 code-plan 推理端点；不支持的后端会忽略该参数。
    effort = getattr(model, "reasoning_effort", "") or ""
    if effort:
        body["reasoning_effort"] = effort

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        model.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {model.api_key}"},
    )
    try:
        with opener.open(req, timeout=300) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                # 部分后端（如 llama.cpp 推测解码失败、服务端异常）会以
                # SSE 事件返回 {"error": {...}} 而非 HTTP 错误。若不显式
                # 抛出，流会"正常"结束、一条事件都没有——界面表现为
                # "没有返回"。这里必须抛 LLMError 让错误可见。
                err = obj.get("error")
                if err:
                    code = err.get("code", "")
                    msg = err.get("message", "未知服务端错误")
                    raise LLMError(f"服务端错误: {msg}"
                                   + (f" (code={code})" if code else ""))
                yield obj
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise LLMError(f"连接失败: {e.reason}")


def _parse_usage(u: dict) -> dict:
    """把 OpenAI 兼容 usage 归一化，提取缓存命中的 token 数。"""
    details = u.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens", details.get("cache_read_input_tokens"))
    if cached is None:
        cached = u.get("prompt_cache_hit_tokens")   # DeepSeek 格式
    if cached is None:
        cached = u.get("cached_tokens")
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
        "cached_tokens": cached,
        "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
    }


def stream_chat(model: config.ModelConfig, messages, tools=None):
    """流式对话。

    yield 事件字典，类型：
      {"type": "text", "delta": str}              # 正文流式片段
      {"type": "reasoning", "delta": str}         # 思考片段（可选）
      {"type": "tool_calls", "tool_calls": [...]} # 本轮最终 tool_calls（累积完成）
      {"type": "finish", "reason": str}
      {"type": "usage", "usage": {...}}           # token 用量（若后端返回）
    """

    acc: dict[int, dict] = {}

    for obj in _post_stream(model, messages, tools):
        # usage 一般在最后一个 chunk（stream_options.include_usage）或
        # 部分兼容后端直接随 chunk 返回；两者都兼容。
        usage = obj.get("usage")
        if usage:
            yield {"type": "usage", "usage": _parse_usage(usage)}

        # include_usage 的最后一个 chunk 只有 usage、choices 为空
        if not obj.get("choices"):
            continue
        choice = obj["choices"][0]
        delta = choice.get("delta") or {}

        if delta.get("content"):
            yield {"type": "text", "delta": delta["content"]}
        if delta.get("reasoning_content"):
            yield {"type": "reasoning", "delta": delta["reasoning_content"]}

        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index", 0)
            slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["arguments"] += fn["arguments"]

        finish = choice.get("finish_reason")
        if finish:
            if finish == "tool_calls" and acc:
                tool_calls = [
                    {
                        "id": s["id"],
                        "type": "function",
                        "function": {"name": s["name"], "arguments": s["arguments"]},
                    }
                    for s in acc.values()
                ]
                yield {"type": "tool_calls", "tool_calls": tool_calls}
            yield {"type": "finish", "reason": finish}
