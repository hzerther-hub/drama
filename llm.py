# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 客户端：流式 chat + tool_calls 累积。"""

from __future__ import annotations
import json
import urllib.error
import urllib.request

import config


class LLMError(Exception):
    pass


def _effective_max_tokens(model: "config.ModelConfig") -> int:
    """实际下发的 max_tokens：模型声明 > key 启发式 > 全局兜底。"""
    mt = int(getattr(model, "max_tokens", 0) or 0)
    if mt > 0:
        return mt
    if model.key.startswith("gpulocal"):
        return 16384
    return int(getattr(config, "MAX_TOKENS", 32768))


# 有些模型（如 MiniMax-M3）把推理包在 <mm:think>…</mm:think> 里混进正文流
_THINK_OPEN = ("<mm:think>", "<think>")
_THINK_CLOSE = ("</mm:think>", "</think>")
_THINK_KEEP = max(len(t) for t in _THINK_OPEN + _THINK_CLOSE) - 1


class _ThinkFilter:
    """流式过滤推理块：块内内容不作为正文输出，跨 chunk 撕裂的标签也能识别。

    标签必以 `<` 开头：没有 `<` 的文本零延迟直通，只在出现 `<` 时
    缓冲等下一个 chunk 判定（避免"你好"这类普通增量被合并延迟）。
    """

    def __init__(self):
        self.buf = ""
        self.inside = False

    @staticmethod
    def _find(s, tags):
        idx = tag_hit = None
        for t in tags:
            i = s.find(t)
            if i != -1 and (idx is None or i < idx):
                idx, tag_hit = i, t
        return idx, tag_hit

    def feed(self, piece: str) -> str:
        self.buf += piece
        out = []
        while True:
            if not self.inside:
                i, t = self._find(self.buf, _THINK_OPEN)
                if i is not None:
                    out.append(self.buf[:i])
                    self.buf = self.buf[i + len(t):]
                    self.inside = True
                    continue
                lt = self.buf.rfind("<")
                if lt == -1:                       # 无潜在标签 → 全部直通
                    out.append(self.buf)
                    self.buf = ""
                else:
                    out.append(self.buf[:lt])      # `<` 之前的安全放行
                    tail = self.buf[lt:]
                    if len(tail) > _THINK_KEEP:    # 长到不可能是标签前缀
                        out.append(tail)
                        self.buf = ""
                    else:
                        self.buf = tail            # 等下一个 chunk 判定
                break
            else:
                i, t = self._find(self.buf, _THINK_CLOSE)
                if i is not None:
                    self.buf = self.buf[i + len(t):]
                    self.inside = False
                    continue
                # 块内内容丢弃；只保留可能是撕裂关闭标签的最后一段
                lt = self.buf.rfind("<")
                self.buf = self.buf[lt:] if lt != -1 else ""
                break
        return "".join(out)

    def flush(self) -> str:
        rest, self.buf = self.buf, ""
        return "" if self.inside else rest


def _post_stream(model: config.ModelConfig, messages, tools):
    """流式 POST，yield 每个 SSE data JSON 对象。"""
    body = {
        "model": model.model_id,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        # 输出上限：优先用模型自身声明（models.json 里 "max_tokens"），
        # 否则本地(gpulocal)默认 16K，云端用全局 MAX_TOKENS。
        # 部分后端（如 llama.cpp OpenAI 兼容端）硬性要求 max_tokens ≤ 32768，
        # 在此再夹一次保险。模型未声明则从 0 兜底成全局值。
        "max_tokens": min(_effective_max_tokens(model), 32768),
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

    根据 model.api_type 选择协议：
      openai_compatible（默认）→ /chat/completions 流式
      anthropic              → /messages 流式（SSE 事件重映射到上面同一组事件）
    """
    if getattr(model, "api_type", "openai_compatible") == "anthropic":
        yield from _stream_anthropic(model, messages, tools)
        return

    acc: dict[int, dict] = {}
    tf = _ThinkFilter()

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
            visible = tf.feed(delta["content"])
            if visible:
                yield {"type": "text", "delta": visible}
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
            tail = tf.flush()                  # 正文缓冲在收尾事件前清空
            if tail:
                yield {"type": "text", "delta": tail}
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


def _to_anthropic_messages(messages):
    """OpenAI 风格 messages → Anthropic (system, messages) 拆分。

    Anthropic 要求 system 是顶层字段，messages 只含 user/assistant。
    工具结果消息（role=tool）需合并为 user 的 tool_result 块。
    """
    system_parts = []
    out = []
    pending_tool_results = []

    def _flush_tool_results():
        """把累积的 tool 结果作为一个 user 消息发出（content 为 tool_result 块数组）。"""
        nonlocal pending_tool_results
        if not pending_tool_results:
            return
        out.append({"role": "user", "content": pending_tool_results})
        pending_tool_results = []

    for m in messages:
        role = m.get("role")
        if role == "system":
            content = m.get("content")
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        system_parts.append(part.get("text", ""))
            continue

        if role == "tool":
            # tool_call_id ↔ tool_use_id；content 若是字符串直接作为 tool_result 的 content
            content = m.get("content")
            tr_content = content if isinstance(content, list) else [
                {"type": "text", "text": str(content or "")}]
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": tr_content,
            })
            continue

        if role == "user":
            _flush_tool_results()
            content = m.get("content")
            # OpenAI 多模态 content 是数组 [text, image_url, ...]
            if isinstance(content, list):
                blocks = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "text":
                        blocks.append({"type": "text", "text": part.get("text", "")})
                    elif ptype == "image_url":
                        url = (part.get("image_url") or {}).get("url", "")
                        blocks.append(_anthropic_image_block(url))
                out.append({"role": "user", "content": blocks})
            else:
                out.append({"role": "user", "content": str(content or "")})
            continue

        if role == "assistant":
            _flush_tool_results()
            content_blocks = []
            text = m.get("content")
            if isinstance(text, str) and text:
                content_blocks.append({"type": "text", "text": text})
            elif isinstance(text, list):
                for part in text:
                    if isinstance(part, dict) and part.get("type") == "text":
                        content_blocks.append({"type": "text",
                                               "text": part.get("text", "")})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args_raw = fn.get("arguments", "")
                # Anthropic 要求 input 必须是 object/array，解析失败时给空对象
                try:
                    args_obj = json.loads(args_raw) if args_raw else {}
                except (ValueError, TypeError):
                    args_obj = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": args_obj,
                })
            if not content_blocks:
                # Anthropic 不允许空 content；用单个空格兜底
                content_blocks = [{"type": "text", "text": " "}]
            out.append({"role": "assistant", "content": content_blocks})
            continue

        # 未知 role 透传为 user（保底不让请求直接失败）
        out.append({"role": "user", "content": str(m.get("content") or "")})

    _flush_tool_results()
    return "\n\n".join([s for s in system_parts if s]), out


def _anthropic_image_block(url: str) -> dict:
    """data: URL → Anthropic image 块；http(s) URL 也可走 url 形式。"""
    if url.startswith("data:"):
        try:
            header, b64 = url.split(",", 1)
            media = header[5:]                 # "image/png;base64"
            return {"type": "image",
                    "source": {"type": "base64", "media_type": media,
                               "data": b64}}
        except ValueError:
            return {"type": "text", "text": "[图像数据无效]"}
    return {"type": "image",
            "source": {"type": "url", "url": url}}


def _to_anthropic_tools(tools):
    """OpenAI tools[] → Anthropic tools[]。

    Anthropic: {"name", "description", "input_schema"}；不需要外层 type=function。
    """
    out = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or {}
        if not fn:
            continue
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _post_stream_anthropic(model: config.ModelConfig, messages, tools):
    """Anthropic /messages 流式 POST，逐个事件 yield dict。"""
    system, msgs = _to_anthropic_messages(messages)
    body = {
        "model": model.model_id,
        "messages": msgs,
        "max_tokens": min(_effective_max_tokens(model), 32768),
        "stream": True,
    }
    if system:
        body["system"] = system
    ant_tools = _to_anthropic_tools(tools)
    if ant_tools:
        body["tools"] = ant_tools
    effort = getattr(model, "reasoning_effort", "") or ""
    if effort:
        # Anthropic 用 "thinking" 块实现思考；这里仅把 effort 透传给后端，
        # 不支持的实现会忽略（与 OpenAI 路径行为一致）。
        body["thinking"] = {"type": "adaptive"}

    url = model.base_url.rstrip("/") + "/messages"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "x-api-key": model.api_key,
                 "anthropic-version": "2023-06-01",
                 "anthropic-dangerous-direct-browser-access": "true"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=300) as resp:
            for line in resp:
                line = line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    evt = json.loads(payload)
                except ValueError:
                    continue
                err = evt.get("error")
                if err:
                    msg = err.get("message", "未知服务端错误")
                    raise LLMError(f"Anthropic 服务端错误: {msg}")
                yield evt
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"Anthropic HTTP {e.code}: {body_text}")
    except urllib.error.URLError as e:
        raise LLMError(f"Anthropic 连接失败: {e.reason}")


def _stream_anthropic(model: config.ModelConfig, messages, tools=None):
    """把 Anthropic SSE 事件重映射为与 OpenAI 路径同一组 stream_chat 事件。

    事件：
      message_start          → 取 message.usage
      content_block_start    → 区分 text / tool_use，开槽
      content_block_delta    → text_delta / input_json_delta（累积 tool arguments）
      content_block_stop     →
      message_delta          → 取 stop_reason / 增量 usage
      message_stop           → 收尾、产出 tool_calls / finish
    """
    text_buf: dict[int, str] = {}
    tool_acc: dict[int, dict] = {}
    final_stop_reason = "stop"
    tf = _ThinkFilter()

    for evt in _post_stream_anthropic(model, messages, tools):
        etype = evt.get("type")
        if etype == "message_start":
            u = (evt.get("message") or {}).get("usage") or {}
            if u:
                yield {"type": "usage", "usage": _parse_anthropic_usage(u, {})}
            continue

        if etype == "content_block_start":
            block = evt.get("content_block") or {}
            idx = evt.get("index", 0)
            btype = block.get("type")
            if btype == "text":
                text_buf[idx] = ""
            elif btype == "tool_use":
                tool_acc[idx] = {
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "arguments": "",
                }
            elif btype == "thinking":
                # 思考片段映射到 reasoning；这里只暴露增量由 delta 事件产出
                pass
            continue

        if etype == "content_block_delta":
            idx = evt.get("index", 0)
            delta = evt.get("delta") or {}
            dtype = delta.get("type")
            if dtype == "text_delta":
                piece = delta.get("text", "")
                if piece:
                    visible = tf.feed(piece)
                    if visible:
                        yield {"type": "text", "delta": visible}
            elif dtype == "input_json_delta":
                slot = tool_acc.get(idx)
                if slot is not None:
                    slot["arguments"] += delta.get("partial_json", "")
            elif dtype == "thinking_delta":
                piece = delta.get("thinking", "")
                if piece:
                    yield {"type": "reasoning", "delta": piece}
            continue

        if etype == "message_delta":
            delta = evt.get("delta") or {}
            sr = delta.get("stop_reason")
            if sr:
                final_stop_reason = sr
            u = evt.get("usage") or {}
            if u:
                yield {"type": "usage", "usage": _parse_anthropic_usage({}, u)}
            continue

        if etype == "message_stop":
            tail = tf.flush()
            if tail:
                yield {"type": "text", "delta": tail}
            if tool_acc:
                tool_calls = [
                    {
                        "id": s["id"],
                        "type": "function",
                        "function": {"name": s["name"],
                                     "arguments": s["arguments"] or "{}"},
                    }
                    for s in tool_acc.values()
                ]
                yield {"type": "tool_calls", "tool_calls": tool_calls}
                # Anthropic 在用工具时 stop_reason=tool_use；归一成 tool_calls
                final_stop_reason = "tool_calls" if final_stop_reason == "tool_use" \
                    else final_stop_reason
            yield {"type": "finish", "reason": final_stop_reason}
            return


def _parse_anthropic_usage(start: dict, delta: dict) -> dict:
    """Anthropic 的 input_tokens/output_tokens → 统一 usage 字典。"""
    merged = {**start, **delta}
    in_t = merged.get("input_tokens")
    out_t = merged.get("output_tokens")
    cached = merged.get("cache_read_input_tokens") \
        or merged.get("cache_creation_input_tokens")
    return {
        "prompt_tokens": in_t,
        "completion_tokens": out_t,
        "total_tokens": (in_t or 0) + (out_t or 0) if (in_t is not None
                                                       or out_t is not None) else None,
        "cached_tokens": cached,
        "reasoning_tokens": None,
    }