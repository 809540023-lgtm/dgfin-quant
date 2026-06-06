# -*- coding: utf-8 -*-
"""
資料源介面 (Data Source)
- get_universe(): 回傳要掃描的股票清單
- get_financials(stock_id): 回傳該股財報 dict (對接 company_financials)
- get_kline(stock_id):      回傳近 N 日量價 DataFrame (對接 daily_market)
- get_chip(stock_id):       回傳籌碼 dict

目前為 MOCK 實作 (亂數產生 60 檔)，讓整套系統可端到端跑通。
正式環境：把 MockDataSource 換成串接「證交所 OpenAPI / 第三方金融數據 API」
或直接查詢 PostgreSQL 的版本即可，介面不變。
"""

import random
import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)


class MockDataSource:
    def __init__(self, n=60):
        # 產生 60 檔模擬股票，代碼 1101 起跳
        self.stocks = [str(1101 + i) for i in range(n)]
        self._fin = {}
        self._mkt = {}
        for s in self.stocks:
            self._gen(s)

    def _gen(self, s):
        ta = random.uniform(5e6, 5e7)
        health = random.random()  # 0=爛 1=好
        self._fin[s] = {
            "stock_id": s,
            "total_assets": ta,
            "working_capital": ta * random.uniform(-0.1, 0.4) * (0.4 + health),
            "retained_earnings": ta * random.uniform(-0.2, 0.5) * (0.3 + health),
            "ebit": ta * random.uniform(-0.05, 0.25) * (0.3 + health),
            "market_cap": ta * random.uniform(0.8, 3.0) * (0.4 + health),
            "total_liabilities": ta * random.uniform(0.3, 0.9) * (1.4 - health),
            "revenue": ta * random.uniform(0.3, 1.5),
        }
        # 量價：健康股偏多頭趨勢，弱股偏空頭
        drift = (health - 0.5) * 40
        base = np.linspace(100 - drift / 2, 100 + drift / 2, 25) + np.random.normal(0, 2, 25)
        self._mkt[s] = {
            "kline": pd.DataFrame({"close": base,
                                   "volume": np.random.randint(1000, 8000, 25)}),
            "chip": {"main_force_buy_ratio": min(max(health + random.uniform(-0.15, 0.15), 0), 1)},
        }

    def get_universe(self):
        return list(self.stocks)

    def get_financials(self, s):
        return self._fin[s]

    def get_kline(self, s):
        return self._mkt[s]["kline"]

    def get_chip(self, s):
        return self._mkt[s]["chip"]
