# -*- coding: utf-8 -*-
"""
真實版每日執行：用 TWSE 免費真實資料跑雙智能體，產出 picks.json

Agent A：真實財報 → Altman Z-Score。
Agent B：真實 MA20(近月+上月逐日收盤) + 真實三大法人買賣超(T86) 交叉驗證。
  多頭潛力榜：Z>2.99 且 STRONG_BUY(站上 MA20 且法人買超>60%)，依法人買超強度由高到低。
  空頭風險榜：Z<1.81 且 STRONG_SHORT(跌破 MA20 且法人賣超)，依 Z-Score 由低到高。
"""

import json
from datetime import date

from agent_a_altman import calculate_altman_z_score, classify
from agent_b_quant import verify_quant_signals
from data_source_twse import TWSEDataSource, _num

WATCHLIST = [
    "2330", "2317", "2454", "2308", "2303", "2379", "2357", "2382", "2395", "3008",
    "3231", "2353", "2474", "3045", "4904", "2412", "2002", "1301", "1303", "1326",
    "1101", "1102", "2207", "2105", "1216", "2912", "9910", "2603", "2609", "2615",
    "2618", "2610", "1402", "2409", "6505",
]


def _pct(ds, sid):
    d = ds.daily.get(sid, {})
    close = _num(d.get("ClosingPrice")); chg = _num(d.get("Change"))
    if close is not None and chg is not None:
        prev = close - chg
        if prev:
            return round(chg / prev * 100, 2), close
    return None, close


def run_real(limit=None, watchlist="default"):
    if watchlist == "default":
        watchlist = WATCHLIST
    ds = TWSEDataSource(limit=limit, watchlist=watchlist)

    # Agent A：先算 Z-Score 粗篩(不打網路)
    base = []
    for sid in ds.get_universe():
        fin = ds.get_financials(sid)
        z = calculate_altman_z_score(fin)
        if z is None:
            continue
        base.append({"stock_id": sid, "name": fin.get("company_name") or "", "z_score": z})

    long_cand = [r for r in base if r["z_score"] > 2.99]
    short_cand = [r for r in base if r["z_score"] < 1.81]

    # Agent B：只對候選抓真實 MA20 + 真實法人買賣超
    def enrich(r):
        chip = ds.get_chip(r["stock_id"])
        r["signal"] = verify_quant_signals(ds.get_kline(r["stock_id"]), chip)
        r["main_buy"] = chip["main_force_buy_ratio"]
        r["net_shares"] = chip.get("net_shares")
        r["pct"], r["close"] = _pct(ds, r["stock_id"])
        return r

    longs = [enrich(r) for r in long_cand]
    longs = [r for r in longs if r["signal"] == "STRONG_BUY"]
    longs.sort(key=lambda r: r["main_buy"], reverse=True)
    longs = longs[:10]

    shorts = [enrich(r) for r in short_cand]
    shorts = [r for r in shorts if r["signal"] == "STRONG_SHORT"]
    shorts.sort(key=lambda r: r["z_score"])
    shorts = shorts[:10]

    def clean(r, i):
        return {"rank": i + 1, "stock_id": r["stock_id"], "name": r["name"],
                "z_score": r["z_score"], "signal": r["signal"],
                "main_buy": r["main_buy"], "net_shares": r.get("net_shares"),
                "pct": r.get("pct"), "close": r.get("close")}

    return {
        "pick_date": str(date.today()),
        "source": "TWSE 真實財報 + MA20 + 三大法人買賣超(T86)",
        "trade_date": ds.trade_date,
        "scanned": len(base),
        "long": [clean(r, i) for i, r in enumerate(longs)],
        "short": [clean(r, i) for i, r in enumerate(shorts)],
    }


if __name__ == "__main__":
    from decision_engine import pretty
    result = run_real()
    pretty(result)
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n✅ 已寫入真實 picks.json")
