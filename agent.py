# -*- coding: utf-8 -*-
"""Agent 循环：流式 function-calling + 权限控制。"""

from __future__ import annotations
import json

import cache
import config
import context
import llm
import media
import mcp
import tools
import attach

# 权限模式
MODE_READONLY = "readonly"    # 只读：不提供可写工具
MODE_ASK = "ask"              # 询问：可写工具执行前需批准
MODE_ALWAYS = "always"        # 总是允许：直接执行


class Agent:
    """执行一次完整的对话：提问 → 工具调用 → 最终回答。

    权限模式：
      - readonly: 只提供只读工具（读文件/列目录/glob/grep）
      - ask:      可写工具（写文件/shell）执行前调用 on_approval 回调
      - always:   直接执行（当前默认）

    on_approval(name, args, summary) -> bool
      审批回调，返回 True 允许执行 / False 拒绝。仅 ask 模式对可写工具调用。

    on_event 回调事件：
      {"type": "text", "delta": str}
      {"type": "reasoning", "delta": str}
      {"type": "tool_start", "name": str, "args": dict}
      {"type": "tool_result", "name": str, "result": str}
      {"type": "tool_denied", "name": str}          # 用户拒绝
      {"type": "round", "n": int}
      {"type": "usage", "usage": {...}, "total": {...}}  # token 用量（单次+累计）
      {"type": "media", "paths": [str]}        # MCP 工具产出的图片文件（UI 内嵌显示）
      {"type": "model_switch", "from": str, "to": ModelConfig}  # 本地不可用自动回退云端（UI 模型按钮跟随）
    """

    def __init__(self, on_event=None, on_approval=None, on_stop=None,
                 mode=MODE_ALWAYS, model=None):
        self.on_event = on_event or (lambda _e: None)
        self.on_approval = on_approval or (lambda _n, _a, _s: True)
        self.on_stop = on_stop                     # 返回 True 则中止循环
        self.mode = mode
        self.model = model
        # 本次对话累计 token 用量
        self.usage_total = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cached_tokens": 0, "reasoning_tokens": 0, "requests": 0,
        }
        # 缓存命中统计（省下的请求数/估算 tokens）
        self.cache_hits = 0
        self.cache_saved_tokens = 0

    def _emit(self, event):
        self.on_event(event)

    @staticmethod
    def _build_user_message(user_message: str,
                            attachments: list | None) -> dict:
        """构造用户消息；有图片附件时转多模态 content 列表。"""
        if not attachments:
            return {"role": "user", "content": user_message}
        parts = [{"type": "text",
                  "text": (user_message or "请分析我附加的文件。").strip()}]
        media_lines = []
        for path in attachments:
            # 代码片段附件（编辑器选中区右键加入）：直接内联文件+行号+内容
            if isinstance(path, dict) and path.get("kind") == "snippet":
                parts.append({"type": "text", "text": attach.format_snippet(path)})
                continue
            try:
                kind = media.classify(path)
            except Exception:  # noqa: BLE001
                kind = ""
            if kind == "image":
                try:
                    url = media.image_to_data_url(path)
                    parts.append({"type": "image_url",
                                  "image_url": {"url": url}})
                    continue
                except Exception as e:  # noqa: BLE001 读取失败 → 文字说明
                    media_lines.append(f"[图片读取失败: {path}（{e}）]")
                    continue
            if kind in ("audio", "video"):
                label = "音频" if kind == "audio" else "视频"
                media_lines.append(f"[附件{label}: {path}]")
                continue
            # 文档/压缩包：就地分析（文本内联 / 解压清单），模型直接可操作
            analysis = attach.analyze(path)
            if analysis:
                parts.append({"type": "text", "text": analysis})
                continue
            media_lines.append(f"[附件文件: {path}]")
        if media_lines:
            parts.append({"type": "text",
                          "text": "\n".join(media_lines) +
                                  "\n（音视频附件可用 run_shell 调 "
                                  "ffmpeg/ffprobe 分析处理）"})
        return {"role": "user", "content": parts}

    def _execute_with_cache(self, name: str, args: dict) -> str:
        """执行工具；只读工具的结果走缓存。"""
        if name.startswith("mcp_"):
            # MCP 工具：经管理器路由；返回的图片发 media 事件给 UI 内嵌显示。
            # 外部服务器可能返回时效性数据，不走缓存。
            result = mcp.get_manager().call(name, args)
            if result.get("media"):
                self._emit({"type": "media", "paths": result["media"]})
            return result["text"]
        if not tools.is_write_tool(name):
            ws = tools.get_workspace()
            hit = cache.get_tool(name, args, ws)
            if hit is not None:
                self.cache_hits += 1
                return hit
            result = tools.execute_tool(name, args)
            cache.put_tool(name, args, ws, result)
            return result
        return tools.execute_tool(name, args)   # 可写工具不缓存

    def _emit_cache_hit(self, text_len: int):
        """报告一次 LLM 缓存命中（估算省下的 tokens）。"""
        saved = text_len // 2 + len(self.model.model_id)  # 粗略估算
        self.cache_saved_tokens += max(saved, 1)
        self._emit({"type": "cache_hit", "saved": max(saved, 1),
                    "hits": self.cache_hits})

    def _accumulate_usage(self, u: dict):
        """把一次请求的 usage 累加到本次对话总计。"""
        self.usage_total["requests"] += 1
        for k in ("prompt_tokens", "completion_tokens",
                  "total_tokens", "cached_tokens", "reasoning_tokens"):
            v = u.get(k)
            if isinstance(v, int):
                self.usage_total[k] += v

    def _is_mcp_write(self, name: str) -> bool:
        """MCP 工具是否视为可写（服务器未标记 readonly 即可写）。"""
        return name.startswith("mcp_") and mcp.get_manager().is_write_tool(name)

    def _tool_schemas(self):
        base = (tools.readonly_schemas() if self.mode == MODE_READONLY
                else tools.TOOL_SCHEMAS)
        # 模型派发开启时提供 call_model（把文本子任务派发给其它模型）
        base = base + tools.call_model_schema()
        # 公司知识库启用时提供 kb_search（企业代码 + 文档 RAG）
        base = base + tools.kb_schema()
        # 合并 MCP 外部服务器的工具（只读模式下只加只读服务器的工具）
        mgr = mcp.get_manager()
        if mgr.connected and mgr.tool_map:
            extra = mgr.tool_schemas()
            if self.mode == MODE_READONLY:
                extra = [s for s in extra
                         if not mgr.is_write_tool(s["function"]["name"])]
            base = base + extra
        return base

    # ---------------- 本地模型不可用 → 自动回退云端 ----------------

    @staticmethod
    def _local_unavailable(err: Exception) -> bool:
        """错误是否为本地模型不可用：服务加载中(HTTP 503)或没在运行。"""
        s = str(err)
        return ("HTTP 503" in s or "Loading model" in s.lower()
                or s.startswith("连接失败"))

    def _cloud_fallback(self, err: Exception):
        """本地模型不可用时挑一个可用的云端回退模型；不适用返回 None。

        仅对 gpulocal 本地模型生效（云端失败不回退，避免连环计费）；
        候选顺序 dispatch_flash → dispatch_pro，需已配置（存在、非本地、
        配了密钥）。受 auto_cloud_fallback 开关控制。
        """
        if self.model is None or not self.model.key.startswith("gpulocal"):
            return None
        if not self._local_unavailable(err):
            return None
        if not config.get_auto_cloud_fallback():
            return None
        cfg = config.get_dispatch_config()
        for key in (cfg.get("dispatch_flash"), cfg.get("dispatch_pro")):
            if not key or key.startswith("gpulocal"):
                continue
            mc = config.find_model(key)
            if mc is not None and mc.api_key:
                return mc
        return None

    def run(self, user_message: str, history: list | None = None,
            attachments: list | None = None):
        """同步运行整个 Agent 循环，返回最终文本。

        history: 传入则在该历史后追加本轮提问（多会话延续对话）；
                 运行后 self.messages 是（可能被压缩过的）完整消息列表。
        attachments: 本轮附件文件路径列表。图片转 base64 data URL 作为
                 视觉输入（需模型支持 vision）；音视频仅附上路径说明，
                 模型可用 run_shell+ffmpeg/ffprobe 处理。
        """
        user_msg = self._build_user_message(user_message, attachments)
        self._fallback_used = False          # 本地→云端自动回退只做一次
        if history is not None:
            messages = history
            messages.append(user_msg)
        else:
            messages = [
                {"role": "system", "content": config.get_system_prompt()},
                user_msg,
            ]
        # 自动注入公司知识库片段：开启后每次提问检索 top-k 片段进上下文
        # （与 kb_search 工具互补；省 token 可在面板关闭）
        if config.get_kb_inject() and config.get_kb_enabled() \
                and config.get_kb_roots():
            try:
                import codera
                codera.maybe_auto_refresh(config.get_kb_roots())
                block = codera.retrieve_context(user_message,
                                                top_k=config.get_kb_top_k())
                if block:
                    messages.insert(len(messages) - 1,
                                    {"role": "system", "content": block})
            except Exception:            # noqa: BLE001  知识库异常不阻断对话
                pass
        self.messages = messages
        final_text = []

        for round_no in range(1, config.MAX_TOOL_ROUNDS + 1):
            # 用户请求停止：带上已有内容立即退出
            if self.on_stop and self.on_stop():
                self._emit({"type": "text", "delta": "\n（已按用户请求停止）"})
                final_text.append("\n（已按用户请求停止）")
                break
            text_collected = []
            tool_calls = None
            schemas = self._tool_schemas()

            # 上下文预算：过大时渐进压缩（截断旧工具结果 → 折叠中间轮）
            messages = context.maybe_compact(messages, emit=self._emit,
                                             model=self.model)

            # ---- 缓存命中：直接重放事件，不调后端 ----
            cached = cache.get_llm(self.model.model_id, messages, schemas)
            if cached is not None:
                self.cache_hits += 1
                for event in cached:
                    if event["type"] == "text":
                        text_collected.append(event["delta"])
                    self._emit(event)
                self._emit_cache_hit(len("".join(text_collected)))
                final_text.extend(text_collected)
                break

            round_events: list[dict] = []
            aborted = False          # 用户中途停止：半程回复落盘但不进缓存
            try:
                for event in llm.stream_chat(self.model, messages, schemas):
                    # 流中协作式停止：关窗/点停止不必等整轮流完
                    if self.on_stop and self.on_stop():
                        aborted = True
                        break
                    if event["type"] == "text":
                        text_collected.append(event["delta"])
                        self._emit(event)
                    elif event["type"] == "reasoning":
                        self._emit(event)
                    elif event["type"] == "tool_calls":
                        tool_calls = event["tool_calls"]
                    elif event["type"] == "usage":
                        self._accumulate_usage(event["usage"])
                        self._emit({"type": "usage",
                                    "usage": event["usage"],
                                    "total": dict(self.usage_total)})
                    # 记录除 usage 外的事件用于缓存（usage 是后端实时数据）
                    if event["type"] != "usage":
                        round_events.append(event)
            except llm.LLMError as e:
                # 本地模型不可用（加载中/未运行）→ 自动切云端重试本轮。
                # 回退模型再失败就直接报错，不连环回退。
                fb = self._cloud_fallback(e)
                reason = ("正在加载，请稍候" if "503" in str(e)
                          else "未在运行，请先启动本地模型")
                if fb is None:
                    if (self.model is not None
                            and self.model.key.startswith("gpulocal")
                            and self._local_unavailable(e)):
                        raise llm.LLMError(
                            f"本地模型 {self.model.display_name} {reason}，"
                            f"且没有可用的云端回退模型。原始错误：{e}") from e
                    raise
                if self._fallback_used:
                    raise
                self._fallback_used = True
                old = self.model
                self.model = fb
                self._emit({"type": "text", "delta":
                            f"\n⚠️ 本地模型 {old.display_name} {reason}，"
                            f"已自动切换到云端 {fb.display_name} 继续。\n"})
                # 通知 UI 把顶部/底部模型按钮切到实际使用的模型，
                # 避免界面仍显示一个没在运行的本地模型
                self._emit({"type": "model_switch",
                            "from": old.display_name, "to": fb})
                continue

            # 服务端"正常结束"却既无正文也无工具调用（如空流）：
            # 明确提示，避免界面静默空白（用户主动停止除外）
            if not aborted and not text_collected and not tool_calls:
                msg = "模型未返回任何内容（服务端可能出错或上下文异常）"
                self._emit({"type": "text", "delta": f"\n⚠️ {msg}\n"})
                final_text.append(msg)
                break

            # 本轮没有工具调用 → 完成；纯文本回复写入缓存
            if not tool_calls:
                final_text.extend(text_collected)
                # 缓存键必须用「请求时」的消息列表（不含本轮回复），
                # 否则键里混入答案、下次同样提问永远匹配不上。
                # 用户中途停止的半程回复不缓存（内容不完整）。
                if not aborted:
                    cache.put_llm(self.model.model_id, messages, schemas,
                                  round_events)
                # 最终回复也进 messages（多会话保存完整历史）
                messages.append({"role": "assistant",
                                 "content": "".join(text_collected) or None})
                break

            assistant_msg = {
                "role": "assistant",
                "content": "".join(text_collected) or None,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)

            for tc in tool_calls:
                # 每个工具执行前也检查停止
                if self.on_stop and self.on_stop():
                    self._emit({"type": "tool_denied", "name": "(用户停止)"})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": "用户请求停止，未执行此工具",
                    })
                    continue
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                # 计划工具：先让界面把任务步骤换成模型的计划，再执行确认
                if name == "task_plan":
                    self._emit({"type": "plan",
                                "steps": args.get("steps") or []})

                # 权限判断：ask 模式下可写工具（内置或 MCP）需审批
                if self.mode == MODE_ASK and (tools.is_write_tool(name) or
                                              self._is_mcp_write(name)):
                    summary = tools.describe_arguments(name, args)
                    if not self.on_approval(name, args, summary):
                        self._emit({"type": "tool_denied", "name": name})
                        result = f"用户拒绝了工具调用 {name}"
                    else:
                        result = self._execute_with_cache(name, args)
                else:
                    result = self._execute_with_cache(name, args)

                self._emit({"type": "tool_start", "name": name, "args": args})
                self._emit({"type": "tool_result", "name": name, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            self._emit({"type": "round", "n": round_no})

        else:
            # 工具轮次用完仍没给出最终回答：做一次"无工具"强制收尾，
            # 避免分析类任务读了一圈文件却没有任何结论。
            self._emit({"type": "text",
                        "delta": "\n（工具轮次已达上限，正在汇总已有信息…）\n"})
            messages.append({
                "role": "system",
                "content": "工具调用轮次已达上限。请立即基于以上已收集的信息"
                           "给出最终完整回答，不要再调用任何工具。",
            })
            text_collected = []
            round_events = []
            forced_ok = True
            try:
                for event in llm.stream_chat(self.model, messages, []):
                    if self.on_stop and self.on_stop():
                        forced_ok = False
                        self._emit({"type": "text",
                                    "delta": "\n（已按用户请求停止）"})
                        break
                    if event["type"] == "text":
                        text_collected.append(event["delta"])
                        self._emit(event)
                    elif event["type"] == "reasoning":
                        self._emit(event)
                    elif event["type"] == "usage":
                        self._accumulate_usage(event["usage"])
                        self._emit({"type": "usage",
                                    "usage": event["usage"],
                                    "total": dict(self.usage_total)})
                    if event["type"] != "usage":
                        round_events.append(event)
            except llm.LLMError as e:
                forced_ok = False
                self._emit({"type": "text",
                            "delta": f"\n⚠️ 汇总失败：{e}\n"})
            if text_collected:
                final_text.extend(text_collected)
                if forced_ok:
                    cache.put_llm(self.model.model_id, messages, [],
                                  round_events)
                messages.append({"role": "assistant",
                                 "content": "".join(text_collected)})

        return "".join(final_text)
