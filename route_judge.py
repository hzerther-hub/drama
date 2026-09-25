# -*- coding: utf-8 -*-
"""LLM 复杂度判官：把用户指令分类 fast/pro 两档，供派发路由选模型。

定位与分工：ui._route_complex 的关键词规则是第 0 层（零成本、瞬时）；
本判官是第 1 层——关键词未命中时，用一句话直连 TypeSafe chat
（OpenAI 兼容 /v1/systemone，与 jev 同一账号体系，不需要起浏览器）
问一次 fast 还是 pro。任何失败（无 key/超时/解析失败）一律返回 None，
路由回退关键词结果；判官永远不阻断、不拖垮消息发送。
"""

from __future__ import annotations

import hashlib
import json
import urllib.request

_URL = "https://api.typesafe.ai/v1/systemone"
_HOST_ALLOW = "api.typesafe.ai"     # 判官端点固定：仅允许 https + 此域名
_TIMEOUT_S = 6.0
_MAX_TEXT = 800                     # 判官只看指令主干，超长截断省钱
_CACHE: dict[str, str] = {}         # text-hash -> tier（会话级，同句不重复扣费）
_CACHE_MAX = 256

_SYS = (
    "你是模型路由判官。判断用户这条指令应交给哪档模型处理，只输出 JSON："
    '{"tier": "pro"} 或 {"tier": "fast"}。\n'
    "判 pro：跨文件/整库分析、架构设计、大型重构、复杂调试、多步骤规划、"
    "生成长代码、需要严谨多步推理的任务。\n"
    "判 fast：简单问答、短文写作/翻译/润色、格式转换、单点小改动、闲聊。\n"
    "拿不准一律判 fast。")


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip()[:_MAX_TEXT].encode("utf-8")).hexdigest()


def _post(key: str, body: dict, timeout_s: float) -> dict:
    """与 jev-ultrafast 同契约的 JSON POST：https+域名白名单校验、禁重定向、
    429/5xx 短退避一次。端点是模块常量，不接收外部动态 URL。"""
    from urllib.parse import urlsplit
    u = urlsplit(_URL)
    if u.scheme != "https" or (u.hostname or "") != _HOST_ALLOW:
        raise ValueError("判官端点配置非法（仅允许 https://" + _HOST_ALLOW + "）")
    opener = urllib.request.build_opener(_NoRedirect)
    last = None
    for attempt in range(2):
        if attempt:
            import time
            time.sleep(0.6)
        req = urllib.request.Request(
            _URL, data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {key}")
        try:
            with opener.open(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:         # noqa: BLE001  网络/HTTP 一律按不可用
            last = e
    raise last


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None                    # 禁跟随重定向：防重定向绕出白名单域名


def judge_tier(text: str, *, api_key: str, model: str = "jev-latest",
               timeout_s: float = _TIMEOUT_S) -> str | None:
    """判档：返回 "fast" / "pro"；判不了返回 None（调用方回退关键词）。

    结果按指令文本缓存——同一句话一轮会话里只问一次，判官不重复扣费。
    """
    text = (text or "").strip()
    if not text or not api_key:
        return None
    key = _cache_key(text)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    body = {
        "model": model or "jev-latest",
        "max_tokens": 64,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYS},
            {"role": "user",
             "content": text[:_MAX_TEXT]},
        ],
    }
    try:
        data = _post(api_key, body, timeout_s)
        out = json.loads(data["choices"][0]["message"]["content"])
        tier = str(out.get("tier", "")).strip().lower()
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
