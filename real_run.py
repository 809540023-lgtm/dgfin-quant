# -*- coding: utf-8 -*-
"""
真實版每日執行：用 TWSE 真實資料跑雙智能體，產出 picks.json

Agent A：用真實財報算 Altman Z-Score（資產負債表 + 損益表）。
Agent B：用真實「當日量價方向」判斷多空（免費 OpenAPI 無現成逐檔歷史K線可算 MA20，
        故以當日漲跌方向作為趨勢代理；要真正的 MA20/主力買超需另接付費資料源）。

多頭潛力榜：Z > 2.99（基本面安全）且當日上漲 → STRONG_BUY，依當日漲幅由高到低。
空頭風險榜：Z < 1.81（違約風險高）且當日下跌 → STRONG_SHORT，依 Z-Score 由低到高。
"""

import json
from datetime import date

from agent_a_altman import calculate_altman_z_score, classify
from data_source_twse import TWSEDataSource, _num
from decision_engine import pretty

# 精選非金融權值股清單（Altman Z-Score 不適用金控/銀行/保險，故排除金融股）
WATCHLIST = [
    "2330", "2317", "2454", "2308", "2303", "2379", "2357", "2382", "2395", "3008",
    "3231", "2353", "2474", "3045", "4904", "2412", "2002", "1301", "1303", "1326",
    "1101", "1102", "2207", "2105", "1216", "2912", "9910", "2603", "2609", "2615",
    "2618", "2610", "1402", "2409", "6505",
]


def _daily(ds, sid):
    d = ds.daily.get(sid, {})
    close = _num(d.get("ClosingPrice"))
    chg = _num(d.get("Change"))
    pct = None
    if close is not None and chg is not None:
        prev = close - chg
        if prev:
            pct = round(chg / prev * 100, 2)
    return close, chg, pct


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
        close, chg, pct = _daily(ds, sid)
        rows.append({
            "stock_id": sid,
            "name": fin.get("company_name") or "",
            "z_score": z,
            "grade": classify(z),
            "close": close,
            "chg": chg,
            "pct": pct if pct is not None else 0.0,
        })

    # 多頭：基本面安全 + 當日上漲
    longs = [r for r in rows if r["z_score"] > 2.99 and r["chg"] is not None and r["chg"] > 0]
    longs.sort(key=lambda r: r["pct"], reverse=True)
    longs = longs[:10]

    # 空頭：違約風險高 + 當日下跌
    shorts = [r for r in rows if r["z_score"] < 1.81 and r["chg"] is not None and r["chg"] < 0]
    shorts.sort(key=lambda r: r["z_score"])
    shorts = shorts[:10]

    def clean(r, i, sig):
        # board.html 以 main_buy(0~1) 畫長條：用當日漲跌幅正規化呈現強度
        strength = min(abs(r["pct"]) / 10.0, 1.0) if r["pct"] is not None else 0.5
        return {"rank": i + 1, "stock_id": r["stock_id"], "name": r["name"],
                "z_score": r["z_score"], "signal": sig,
                "pct": r["pct"], "close": r["close"],
                "main_buy": round(strength, 3)}

    out = {
        "pick_date": str(date.today()),
        "source": "TWSE OpenAPI (real)",
        "scanned": len(rows),
        "long": [clean(r, i, "STRONG_BUY") for i, r in enumerate(longs)],
        "short": [clean(r, i, "STRONG_SHORT") for i, r in enumerate(shorts)],
    }
    return out


if __name__ == "__main__":
    result = run_real()
    pretty(result)
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n✅ 已寫入真實 picks.json")
