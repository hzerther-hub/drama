# -*- coding: utf-8 -*-
"""研究数据接入：akshare 实时/历史行情 + 本地 CSV 缓存与样本数据。

v0.5 范围：日线 bars。akshare 是可选依赖（懒加载），未安装时
`fetch_daily` 给出明确报错；`load_bars` 优先读 CSV，方便离线开发、
CI 与 benchmark（仓库自带样本行情 sample_000001.XSHE.csv）。

bars 统一格式：[{"date": "2026-01-02", "open": .., "high": ..,
                 "low": .., "close": .., "volume": ..}, ...]
"""

from __future__ import annotations

import csv
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(DATA_DIR, "cache")
SAMPLE_CSV = os.path.join(DATA_DIR, "sample_000001.XSHE.csv")

_FIELDS = ("date", "open", "high", "low", "close", "volume")


def _norm_symbol(symbol: str) -> str:
    """聚宽风格 000001.XSHE → akshare 风格 sz000001。"""
    code, _, ex = symbol.partition(".")
    ex = ex.upper()
    prefix = {"XSHE": "sz", "XSHG": "sh"}.get(ex, "")
    return prefix + code


def load_csv(path: str) -> list[dict]:
    """读 CSV 为 bars（列名需含 date/open/high/low/close，volume 可选）。"""
    bars: list[dict] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            bar = {k: row[k] for k in _FIELDS if k in row and row[k] != ""}
            for k in ("open", "high", "low", "close", "volume"):
                if k in bar:
                    bar[k] = float(bar[k])
            bars.append(bar)
    return bars


def save_csv(bars: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        w.writeheader()
        w.writerows(bars)


def fetch_daily(symbol: str, start: str = "20240101",
                end: str = "20261231", use_cache: bool = True) -> list[dict]:
    """akshare 拉 A 股日线（前复权）。结果缓存到 data/cache/*.csv。

    未安装 akshare 时抛 RuntimeError（可选依赖，不拖累打包体积）。
    """
    cache = os.path.join(CACHE_DIR, f"{symbol}_{start}_{end}.csv")
    if use_cache and os.path.isfile(cache):
        return load_csv(cache)
    try:
        import akshare as ak                       # noqa: PLC0415 懒加载
    except ImportError as e:
        raise RuntimeError(
            "akshare 未安装（可选依赖）：pip install akshare；"
            "或改用 load_bars 读本地 CSV / 仓库自带样本行情") from e
    df = ak.stock_zh_a_hist(symbol=_norm_symbol(symbol), period="daily",
                            start_date=start, end_date=end, adjust="qfq")
    bars = [{
        "date": str(r["日期"]), "open": float(r["开盘"]),
        "high": float(r["最高"]), "low": float(r["最低"]),
        "close": float(r["收盘"]), "volume": float(r["成交量"]),
    } for _, r in df.iterrows()]
    save_csv(bars, cache)
    return bars


def load_bars(source: str = "") -> list[dict]:
    """统一入口：CSV 路径 → 读文件；空 → 自带样本行情；否则按 symbol 拉 akshare。"""
    if not source:
        return load_csv(SAMPLE_CSV)
    if os.path.isfile(source):
        return load_csv(source)
    return fetch_daily(source)
