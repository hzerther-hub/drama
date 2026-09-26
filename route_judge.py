# -*- coding: utf-8 -*-
"""LLM 复杂度判官：把用户指令分类 fast/pro 两档，供派发路由选模型。

定位与分工：ui._route_complex 的关键词规则是第 0 层（零成本、瞬时）；
本判官是第 1 层——关键词未命中时，用「派发-轻量(flash)」目标模型问一次
fast 还是 pro（OpenAI 兼容 chat；anthropic 协议的 flash 目标不判，回退）。
任何失败（无目标/超时/解析失败）一律返回 None，路由回退关键词结果；
判官永远不阻断、不拖垮消息发送。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request

_TIMEOUT_S = 5.0
_MAX_TEXT = 800                     # 判官只看指令主干，超长截断省钱
_CACHE: dict[str, str] = {}         # text-hash -> tier（会话级，同句不重复扣费）
_CACHE_MAX = 256

_SYS = (
    "你是模型路由判官。判断用户这条指令应交给哪档模型处理，只输出一个词："
    "pro 或 fast。\n"
    "判 pro：跨文件/整库分析、架构设计、大型重构、复杂调试、多步骤规划、"
    "生成长代码、需要严谨多步推理的任务。\n"
    "判 fast：简单问答、短文写作/翻译/润色、格式转换、单点小改动、闲聊。\n"
    "拿不准一律输出 fast。")
_TIER_RE = re.compile(r"\b(pro|fast)\b")


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip()[:_MAX_TEXT].encode("utf-8")).hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None                    # 禁跟随重定向：结果不可控不如直接失败


def _chat_once(model_config, text: str, timeout_s: float) -> str:
    """对 OpenAI 兼容端点发一次单轮 chat，返回回复文本；异常向上抛。

    端点来自用户自己配置的 flash 目标模型；仅接受 http(s) 协议，
    禁跟随重定向。anthropic 协议不走这里（调用方已过滤）。
    """
    base = (model_config.base_url or "").rstrip().rstrip("/")
    scheme = base.split("://", 1)[0] if "://" in base else ""
    if scheme not in ("http", "https") or not base:
        raise ValueError("判官目标端点协议非法：{}".format(base[:60]))
    url = base + "/chat/completions"
    body = {
        "model": model_config.model_id,
        # 思考型模型（glm-air 等）会把预算花在 reasoning 上，给足余量
        "max_tokens": 512,
        "messages": [
            {"role": "system", "content": _SYS},
            {"role": "user", "content": text[:_MAX_TEXT]},
        ],
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if model_config.api_key:
        req.add_header("Authorization", f"Bearer {model_config.api_key}")
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0].get("message") or {}
    # 思考型模型答案可能落在 reasoning_content；普通模型在 content
    return (str(msg.get("content") or "")
            or str(msg.get("reasoning_content") or ""))


def judge_tier(text: str, *, model_config, timeout_s: float = _TIMEOUT_S) -> str | None:
    """判档：返回 "fast" / "pro"；判不了返回 None（调用方回退关键词）。

    结果按指令文本缓存——同一句话一轮会话里只问一次，判官不重复扣费。
    """
    text = (text or "").strip()
    if not text or model_config is None:
        return None
    if getattr(model_config, "api_type", "openai_compatible") != "openai_compatible":
        return None                    # anthropic 协议 flash 目标不判，回退
    key = _cache_key(text)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    try:
        reply = _chat_once(model_config, text, timeout_s).lower()
        tiers = _TIER_RE.findall(reply)
        tier = tiers[-1] if tiers else None   # 取末次提及：思考模型的结论在结尾
    except Exception:                  # noqa: BLE001  判官挂了不影响发送
        return None
    if tier not in ("fast", "pro"):
        return None
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()                 # 简单防膨胀：满了整表清
    _CACHE[key] = tier
    return tier


def reset_cache():
    """清空判官缓存（测试用 / 换判官模型后可手动调）。"""
    _CACHE.clear()
