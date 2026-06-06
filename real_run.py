# -*- coding: utf-8 -*-
"""
真實版每日執行：用 TWSE 真實資料跑雙智能體，產出 picks.json
在網路不受限的環境執行(Render Cron / 你的電腦)：
    pip install -r requirements.txt
    python3 real_run.py
"""

import json
from datetime import date

from agent_a_altman import calculate_altman_z_score, classify
from agent_b_quant import verify_quant_signals
from data_source_twse import TWSEDataSource
from decision_engine import pretty

# 精選非金融權值股清單(Altman Z-Score 不適用金控/銀行/保險，故排除金融股)
# 涵蓋半導體、電子、傳產、航運、汽車、電信等，免費方案可快速跑完。
WATCHLIST = [
    "2330", "2317", "2454", "2308", "2303", "2379", "2357", "2382", "2395", "3008",
    "3231", "2353", "2474", "3045", "4904", "2412", "2002", "1301", "1303", "1326",
    "1101", "1102", "2207", "2105", "1216", "2912", "9910", "2603", "2609", "2615",
    "2618", "2610", "1402", "2409", "6505", "2884",
]


def run_real(limit=None, watchlist="default"):
    if watchlist == "default":
        watchlist = WATCHLIST
    ds = TWSEDataSource(limit=limit, watchlist=watchlist)
    rows = []
    for sid in ds.get_universe():
        fin = ds.get_financials(sid)
        z = calculate_altman_z_score(fin)
        if z is None:
            continue
        rows.append({
            "stock_id": sid,
            "name": fin.get("company_name") or "",
            "z_score": z,
            "grade": classify(z),
            "_fin": fin,
        })

    # 先用 Z-Score 粗篩，縮小要抓日K的候選集合（避免對全市場抓單檔K線）
    long_cand = [r for r in rows if r["z_score"] > 2.99]
    short_cand = [r for r in rows if r["z_score"] < 1.81]

    def attach_signal(r):
        sig = verify_quant_signals(ds.get_kline(r["stock_id"]), ds.get_chip(r["stock_id"]))
        r["signal"] = sig
        r["main_buy"] = round(ds.get_chip(r["stock_id"])["main_force_buy_ratio"], 3)
        return r

    longs = [attach_signal(r) for r in long_cand]
    longs = [r for r in longs if r["signal"] == "STRONG_BUY"]
    longs.sort(key=lambda r: r["main_buy"], reverse=True)
    longs = longs[:10]

    shorts = [attach_signal(r) for r in short_cand]
    shorts = [r for r in shorts if r["signal"] == "STRONG_SHORT"]
    shorts.sort(key=lambda r: r["z_score"])
    shorts = shorts[:10]

    def clean(r, i):
        return {"rank": i + 1, "stock_id": r["stock_id"], "name": r["name"],
                "z_score": r["z_score"], "signal": r["signal"], "main_buy": r["main_buy"]}

    out = {
        "pick_date": str(date.today()),
        "source": "TWSE OpenAPI (real)",
        "scanned": len(rows),
        "long": [clean(r, i) for i, r in enumerate(longs)],
        "short": [clean(r, i) for i, r in enumerate(shorts)],
    }
    return out


if __name__ == "__main__":
    result = run_real()
    pretty(result)
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n✅ 已寫入真實 picks.json")
