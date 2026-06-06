# -*- coding: utf-8 -*-
"""
中央決策引擎
每日收盤後執行：對全市場跑 Agent A + Agent B，產出多空各 10 檔。

多頭潛力榜：Z > 2.99 且 Agent B = STRONG_BUY，依主力買超由高到低取前 10。
空頭風險榜：Z < 1.81 且 Agent B = STRONG_SHORT，依 Z-Score 由低到高取前 10。

輸出：印出表格 + 寫入 picks.json (APP / board.html 可直接讀)
"""

import json
from datetime import date

from agent_a_altman import calculate_altman_z_score, classify
from agent_b_quant import verify_quant_signals
from data_source import MockDataSource


def run(ds=None):
    ds = ds or MockDataSource()
    rows = []
    for s in ds.get_universe():
        fin = ds.get_financials(s)
        z = calculate_altman_z_score(fin)
        if z is None:
            continue
        signal = verify_quant_signals(ds.get_kline(s), ds.get_chip(s))
        rows.append({
            "stock_id": s,
            "z_score": z,
            "grade": classify(z),
            "signal": signal,
            "main_buy": round(ds.get_chip(s)["main_force_buy_ratio"], 3),
        })

    longs = [r for r in rows if r["z_score"] > 2.99 and r["signal"] == "STRONG_BUY"]
    longs.sort(key=lambda r: r["main_buy"], reverse=True)
    longs = longs[:10]

    shorts = [r for r in rows if r["z_score"] < 1.81 and r["signal"] == "STRONG_SHORT"]
    shorts.sort(key=lambda r: r["z_score"])
    shorts = shorts[:10]

    out = {
        "pick_date": str(date.today()),
        "scanned": len(rows),
        "long": [{**r, "rank": i + 1} for i, r in enumerate(longs)],
        "short": [{**r, "rank": i + 1} for i, r in enumerate(shorts)],
    }
    return out


def pretty(out):
    print(f"\n=== 雙智能體選股結果  {out['pick_date']}  (掃描 {out['scanned']} 檔) ===")
    print("\n📈 多頭潛力榜 (Z>2.99 + STRONG_BUY，依主力買超排序)")
    print(f"{'排名':<4}{'代碼':<8}{'Z-Score':<10}{'主力買超':<10}{'訊號'}")
    for r in out["long"]:
        print(f"{r['rank']:<5}{r['stock_id']:<8}{r['z_score']:<11}{r['main_buy']:<11}{r['signal']}")
    if not out["long"]:
        print("（今日無符合條件標的）")
    print("\n📉 空頭風險榜 (Z<1.81 + STRONG_SHORT，依 Z-Score 由低到高)")
    print(f"{'排名':<4}{'代碼':<8}{'Z-Score':<10}{'主力買超':<10}{'訊號'}")
    for r in out["short"]:
        print(f"{r['rank']:<5}{r['stock_id']:<8}{r['z_score']:<11}{r['main_buy']:<11}{r['signal']}")
    if not out["short"]:
        print("（今日無符合條件標的）")


if __name__ == "__main__":
    result = run()
    pretty(result)
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n✅ 已寫入 picks.json")
