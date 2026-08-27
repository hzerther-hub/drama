# -*- coding: utf-8 -*-
"""量化研究数据：akshare 接入 + CSV 缓存 + 自带样本行情 + 多标的合成行情。"""

from .akshare_data import SAMPLE_CSV, fetch_daily, load_bars, load_csv, save_csv
from .synthetic import synthetic_bars

__all__ = ["SAMPLE_CSV", "fetch_daily", "load_bars", "load_csv", "save_csv",
           "synthetic_bars"]
