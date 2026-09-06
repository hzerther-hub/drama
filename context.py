# -*- coding: utf-8 -*-
"""上下文管理（类 DeepSeek Harness）：预算 + 渐进压缩。

对话/工具结果过大时按顺序处理：
  1. 超长工具结果就地截断（保头尾，标记原始长度）
  2. 超预算 → 中间轮次折叠为摘要行（保留 system + 首个用户问题 + 最近
     CONTEXT_KEEP_ROUNDS 轮原文，协议结构保持合法）

估算：装了 tiktoken 用精确 cl100k 计数（零配置、纯可选）；否则用分段启发式——
CJK 字符 ≈ 1 token/字，ASCII/代码 ≈ 1 token/4 字符。比旧的 len//2 粗算
更接近真实值（旧法对中文低估一半、对代码高估一倍）。
"""

from __future__ import annotations
import re

import config

# 可选精确分词：tiktoken 存在即用（requirements 不强制，缺失走启发式）
try:
    import tiktoken as _tiktoken
    _ENC = _tiktoken.get_encoding("cl100k_base")
except Exception:                       # noqa: BLE001
    _ENC = None

# CJK 统一表意文字 + 扩展 A + 全角标点/符号（这些在分词器里基本 1 字 1 token）
_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿　-〿＀-￯]")

# 多模态消息里一张图片的粗估 token（视觉 token 经验值，用于预算控制）
IMAGE_TOKEN_ESTIMATE = 1100



def estimate_text_tokens(s: str) -> int:
    """估算单段文本的 token 数：tiktoken 精确值优先，否则 CJK/ASCII 分段启发式。"""
    if not s:
        return 0
    if _ENC is not None:
        try:
            return len(_ENC.encode(s, disallowed_special=()))
        except Exception:               # noqa: BLE001  编码失败退回启发式
            pass
    cjk = len(_CJK_RE.findall(s))
    return cjk + (len(s) - cjk + 3) // 4


def estimate_tokens(messages: list) -> int:
    """估算消息列表的 token 数（支持多模态 content 列表；含每消息结构开销）。"""
    n = 0
    for m in messages:
        c = m.get("content") or ""
	
        if isinstance(c, str):
            n += estimate_text_tokens(c) + 8
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        n += estimate_text_tokens(part.get("text", "")) + 8
                    elif part.get("type") in ("image_url", "image", "input_image"):
                        n += IMAGE_TOKEN_ESTIMATE
                    else:
                        n += 32
        else:
            n += 200
        for tc in m.get("tool_calls") or []:
            n += estimate_text_tokens(tc["function"].get("arguments", "")) + 16
    return n


def _truncate(s: str, keep: int) -> str:
    """保头尾截断。"""
    if len(s) <= keep:
        return s
    head = keep * 2 // 3
    tail = keep - head
    return s[:head] + f"\n…[已压缩，原 {len(s)} 字符]\n" + s[-tail:]


def _rounds(messages: list) -> list[list[int]]:
    """把 messages[1:] 按轮次分组。

    一轮 = 一条 assistant 消息（可带 tool_calls）+ 其后连续的 tool 消息；
    user 消息单独成轮。
    """
    rounds: list[list[int]] = []
    i = 1
    while i < len(messages):
        if messages[i].get("role") == "assistant":
            idxs = [i]
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                idxs.append(j)
                j += 1
            rounds.append(idxs)
            i = j
        else:
            rounds.append([i])
            i += 1
    return rounds


def _protected_indices(rounds: list[list[int]], keep_from: int) -> set[int]:
    """最近 keep_rounds 轮的下标（这些消息不压缩图片）。"""
    keep = set()
    for idxs in rounds[keep_from:]:
        keep.update(idxs)
    return keep


def _strip_old_images(content: list) -> list:
    """把旧消息里的 image_url 部分换成占位文本（其余部分原样保留）。"""
    changed = False
    out = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "image_url":
            out.append({"type": "text",
                        "text": "[早期图片已省略以压缩上下文]"})
            changed = True
        else:
            out.append(part)
    return out if changed else content


def _round_summary(messages: list, idxs: list[int]) -> str:
    """把一轮压成一行摘要。"""
    head = messages[idxs[0]]
    parts = []
    text = head.get("content")
    if text and text.strip():
        parts.append("输出『" + text.strip()[:120].replace("\n", " ") + "』")
    names = [tc["function"]["name"] for tc in head.get("tool_calls") or []]
    if names:
        parts.append("调用工具 " + "/".join(names))
    return "· " + ("；".join(parts) if parts else "（空轮）")


def effective_budget(model=None) -> int:
    """按当前模型返回生效的上下文预算。

    - 模型未声明 context_window（0）→ 用全局 CONTEXT_BUDGET。
    - 声明了窗口 → 用 min(CONTEXT_BUDGET, 窗口 - MAX_TOKENS - 安全余量)，
      避免本地小窗口模型被 24k 全局预算撑爆。
    """
    budget = getattr(config, "CONTEXT_BUDGET", 24000)
    win = getattr(model, "context_window", 0) if model is not None else 0
    key = getattr(model, "key", "") if model is not None else ""
    # 输出上限：模型自身声明 > 本地 16K 启发式 > 云端全局兜底；与 llm.py 一致
    declared_mt = int(getattr(model, "max_tokens", 0) or 0) if model is not None else 0
    if declared_mt > 0:
        out_mt = declared_mt
    else:
        out_mt = 16384 if key.startswith("gpulocal") else getattr(config, "MAX_TOKENS", 32768)
    margin = out_mt + 1024
    # 本地(gpulocal)：context_window 常被同步重置为 0，按已知 131072 窗口兜底
    if key.startswith("gpulocal"):
        win = win or 131072
        return max(1024, win - margin)
    if win and win > 0:
        return min(budget, win - margin)
    return budget


def maybe_compact(messages: list, emit=None, model=None) -> list:
    """超过预算时压缩；返回（可能新的）消息列表。

    emit(event) 用于向 UI 报告压缩动作：
        {"type": "context_compact", "before": n, "after": n}
    model: 当前运行的模型，用于按它的 context_window 收紧预算（默认全局预算）。
    """
    budget = effective_budget(model)
    keep_rounds = getattr(config, "CONTEXT_KEEP_ROUNDS", 2)
    tool_keep = getattr(config, "TOOL_RESULT_KEEP", 3000)

    before = estimate_tokens(messages)
    if before <= budget:
        return messages

    rounds = _rounds(messages)
    keep_from = len(rounds) - keep_rounds   # 最近 N 轮保留原文

    # ---- 阶段 0：任何超长工具结果就地截断 ----
    # 无论轮次多少都执行：单条结果过长本身就应截断，
    # 保证"轮次太少没法折叠"时也能把上下文压下来。
    old_tool_idx = set()
    for r_i, idxs in enumerate(rounds):
        if r_i < keep_from:
            old_tool_idx.update(i for i in idxs if messages[i].get("role") == "tool")

    msgs = [dict(m) for m in messages]
    changed = False
    for i, m in enumerate(msgs):
        if m.get("role") == "tool" and isinstance(m.get("content"), str):
            limit = 400 if i in old_tool_idx else tool_keep
            if len(m["content"]) > limit:
                m["content"] = _truncate(m["content"], limit)
                changed = True
        # 多模态 user 消息：旧轮次里的图片 data URL 换成占位文本（大幅省 token）
        if (isinstance(m.get("content"), list) and i not in
                _protected_indices(rounds, keep_from)):
            new_content = _strip_old_images(m["content"])
            if new_content is not m["content"]:
                m["content"] = new_content
                changed = True

    # 没有可折叠的中间轮：截断后即返回
    if len(rounds) <= keep_rounds + 1:
        after = estimate_tokens(msgs)
        if emit and changed and after < before:
            emit({"type": "context_compact", "before": before, "after": after})
        return msgs

    # ---- 阶段 2：仍超预算 → 折叠中间轮 ----
    if estimate_tokens(msgs) > budget:
        out = [msgs[0]]                      # system
        if rounds and rounds[0][0] == 1:
            out.append(msgs[1])              # 首个 user 原文保留
            mid_range = range(1, keep_from)
        else:
            mid_range = range(0, keep_from)
        lines = [_round_summary(msgs, rounds[r]) for r in mid_range]
        if lines:
            out.append({"role": "assistant",
                        "content": "（历史对话已压缩摘要）\n" + "\n".join(lines)})
        for r in range(keep_from, len(rounds)):
            for idx in rounds[r]:
                out.append(msgs[idx])
        msgs = out

    after = estimate_tokens(msgs)
    if emit and after < before:
        emit({"type": "context_compact", "before": before, "after": after})
    return msgs
