# -*- coding: utf-8 -*-
"""
Agent A：基本面違約風險智能體
計算台灣上市公司 Altman Z-Score（製造業標準版）

Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 0.999*X5
  X1 = 營運資金 / 總資產
  X2 = 保留盈餘 / 總資產
  X3 = EBIT     / 總資產
  X4 = 市值     / 總負債
  X5 = 營業收入 / 總資產

分級：Z > 2.99 健康；1.81 <= Z <= 2.99 灰色；Z < 1.81 高違約風險
"""

from typing import Optional

REQUIRED = ["total_assets", "working_capital", "retained_earnings",
            "ebit", "market_cap", "total_liabilities", "revenue"]


def calculate_altman_z_score(financial_data: dict) -> Optional[float]:
    """回傳 Z-Score；資料缺失回傳 None；分母為 0 回傳 0.0"""
    missing = [k for k in REQUIRED if k not in financial_data]
    if missing:
        print(f"[Agent A] 數據缺失欄位: {missing}")
        return None
    try:
        ta   = float(financial_data["total_assets"])
        wc   = float(financial_data["working_capital"])
        re   = float(financial_data["retained_earnings"])
        ebit = float(financial_data["ebit"])
        mc   = float(financial_data["market_cap"])
        tl   = float(financial_data["total_liabilities"])
        sales = float(financial_data["revenue"])
    except (TypeError, ValueError) as e:
        print(f"[Agent A] 型別錯誤: {e}")
        return None

    if ta == 0 or tl == 0:
        return 0.0

    x1 = wc / ta
    x2 = re / ta
    x3 = ebit / ta
    x4 = mc / tl
    x5 = sales / ta
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5
    return round(z, 2)


def classify(z: Optional[float]) -> str:
    """分級標籤"""
    if z is None:
        return "UNKNOWN"
    if z > 2.99:
        return "HEALTHY"        # 財務健康 → 多頭候選
    if z >= 1.81:
        return "GREY"           # 灰色地帶 → 觀望
    return "DISTRESS"           # 高違約風險 → 觸發 Agent B 空頭驗證


if __name__ == "__main__":
    example = {
        "total_assets": 10_000_000, "working_capital": 2_500_000,
        "retained_earnings": 1_500_000, "ebit": 800_000,
        "market_cap": 12_000_000, "total_liabilities": 4_000_000,
        "revenue": 5_000_000,
    }
    z = calculate_altman_z_score(example)
    print(f"該股 Z-Score: {z}  分級: {classify(z)}")
