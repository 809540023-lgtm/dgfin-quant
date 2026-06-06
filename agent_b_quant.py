# -*- coding: utf-8 -*-
"""
Agent B：籌碼面量化技術智能體
MA20 均線型態 + 主力大單買超 交叉驗證

回傳：
  STRONG_BUY   價站上 MA20 且主力買超 > 0.60
  STRONG_SHORT 價跌破 MA20 且主力買超 < 0.40
  HOLD         其餘
"""

import pandas as pd


def verify_quant_signals(kline_df: pd.DataFrame, chip_data: dict) -> str:
    if kline_df is None or len(kline_df) < 20:
        return "HOLD"
    if "close" not in kline_df.columns:
        return "HOLD"

    df = kline_df.copy()
    df["MA20"] = df["close"].rolling(window=20).mean()
    current_price = df["close"].iloc[-1]
    ma20_current = df["MA20"].iloc[-1]
    if pd.isna(ma20_current):
        return "HOLD"

    main_buy_ratio = float(chip_data.get("main_force_buy_ratio", 0.5))

    if current_price > ma20_current and main_buy_ratio > 0.60:
        return "STRONG_BUY"
    if current_price < ma20_current and main_buy_ratio < 0.40:
        return "STRONG_SHORT"
    return "HOLD"


if __name__ == "__main__":
    import numpy as np
    up = pd.DataFrame({"close": np.linspace(100, 130, 25),
                       "volume": np.random.randint(1000, 5000, 25)})
    print("多頭測試:", verify_quant_signals(up, {"main_force_buy_ratio": 0.72}))
    down = pd.DataFrame({"close": np.linspace(130, 95, 25),
                         "volume": np.random.randint(1000, 5000, 25)})
    print("空頭測試:", verify_quant_signals(down, {"main_force_buy_ratio": 0.30}))
