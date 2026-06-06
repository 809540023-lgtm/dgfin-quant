# -*- coding: utf-8 -*-
"""
真實資料源：證交所免費公開資料（無需金鑰、無需付費）
=====================================================
提供與 Mock 相同介面：get_universe / get_financials / get_kline / get_chip

資料來源：
  openapi.twse.com.tw（財報、當日全市場行情）
    /v1/opendata/t187ap06_L_ci   綜合損益表(一般業)  → 營收、營業利益(EBIT)
    /v1/opendata/t187ap07_L_ci   資產負債表(一般業)  → 總資產、總負債、流動資產/負債、保留盈餘
    /v1/exchangeReport/BWIBBU_ALL 個股 PER/PBR/殖利率 → 推算市值
    /v1/exchangeReport/STOCK_DAY_ALL 全市場當日收盤/量
  www.twse.com.tw（真實 MA20 + 真實法人買賣超，免費）
    /rwd/zh/afterTrading/STOCK_DAY  單檔逐日收盤(近月) → 串兩個月算真實 MA20
    /rwd/zh/fund/T86                三大法人買賣超(個股) → 真實主力(法人)買超

⚠ 需在「網路不受限」的環境執行(Render / 你的電腦)。
"""

import time
import math
import datetime
import requests
import pandas as pd

BASE = "https://openapi.twse.com.tw/v1"
WWW = "https://www.twse.com.tw"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _get(path, params=None, retries=3):
    url = f"{BASE}{path}"
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                print(f"[TWSE] 抓取失敗 {url}: {e}")
                return []
            time.sleep(1.5)
    return []


def _get_www(path, params=None, retries=3):
    url = f"{WWW}{path}"
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            j = r.json()
            if j.get("stat") == "OK":
                return j
            return {}
        except Exception as e:
            if i == retries - 1:
                print(f"[TWSE-www] 抓取失敗 {url} {params}: {e}")
                return {}
            time.sleep(2.0)
    return {}


def _num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick(row, *keys):
    for k in keys:
        if k in row:
            n = _num(row[k])
            if n is not None:
                return n
    return None


class TWSEDataSource:
    def __init__(self, limit=None, watchlist=None):
        print("[TWSE] 載入真實財報與行情…")
        self.income = self._index(_get("/opendata/t187ap06_L_ci"))
        self.balance = self._index(_get("/opendata/t187ap07_L_ci"))
        self.valuation = self._index_val(_get("/exchangeReport/BWIBBU_ALL"))
        self.daily = self._index_daily(_get("/exchangeReport/STOCK_DAY_ALL"))

        ids = sorted(set(self.income) & set(self.balance) & set(self.daily))
        if watchlist:
            wl = set(str(s) for s in watchlist)
            ids = [s for s in ids if s in wl]
            self.income = {k: v for k, v in self.income.items() if k in wl}
            self.balance = {k: v for k, v in self.balance.items() if k in wl}
            self.daily = {k: v for k, v in self.daily.items() if k in wl}
            self.valuation = {k: v for k, v in self.valuation.items() if k in wl}
        if limit:
            ids = ids[:limit]
        self._universe = ids
        self._kline_cache = {}

        # 真實法人買賣超(T86)：找最近一個有資料的交易日載入
        self.chip = {}
        self.trade_date = None
        self._load_t86()
        print(f"[TWSE] 可用標的: {len(self._universe)} 檔 | 法人資料日: {self.trade_date} "
              f"| 法人檔數: {len(self.chip)}")

    # ---- 索引 ----
    def _index(self, rows):
        return {str(r.get("公司代號", "")).strip(): r for r in rows if r.get("公司代號")}

    def _index_val(self, rows):
        out = {}
        for r in rows:
            sid = str(r.get("Code") or r.get("證券代號") or "").strip()
            if sid:
                out[sid] = r
        return out

    def _index_daily(self, rows):
        out = {}
        for r in rows:
            sid = str(r.get("Code") or r.get("證券代號") or "").strip()
            if sid:
                out[sid] = r
        return out

    # ---- 真實法人買賣超 T86 ----
    def _load_t86(self):
        today = datetime.date.today()
        for back in range(0, 8):  # 往前找最多 8 天，跳過假日/無資料日
            d = today - datetime.timedelta(days=back)
            ymd = d.strftime("%Y%m%d")
            j = _get_www("/rwd/zh/fund/T86", {"date": ymd, "selectType": "ALL", "response": "json"})
            data = j.get("data") if isinstance(j, dict) else None
            if data:
                self.trade_date = d.isoformat()
                for row in data:
                    try:
                        sid = str(row[0]).strip()
                        net = _num(row[-1])  # 三大法人買賣超股數(最後一欄)
                        if sid and net is not None:
                            self.chip[sid] = net
                    except (IndexError, TypeError):
                        pass
                break
            time.sleep(0.5)

    # ---- 介面 ----
    def get_universe(self):
        return list(self._universe)

    def get_financials(self, sid):
        inc = self.income.get(sid, {})
        bal = self.balance.get(sid, {})
        val = self.valuation.get(sid, {})
        total_assets = _pick(bal, "資產總額", "資產總計")
        total_liab = _pick(bal, "負債總額", "負債總計")
        cur_assets = _pick(bal, "流動資產")
        cur_liab = _pick(bal, "流動負債")
        retained = _pick(bal, "保留盈餘")
        revenue = _pick(inc, "營業收入")
        ebit = _pick(inc, "營業利益（損失）", "營業利益(損失)", "營業利益")
        working_capital = (cur_assets - cur_liab) if (cur_assets is not None and cur_liab is not None) else None
        equity = (total_assets - total_liab) if (total_assets is not None and total_liab is not None) else None
        pbr = _pick(val, "PBratio", "股價淨值比", "PBR")
        market_cap = equity * pbr if (equity is not None and pbr) else None
        return {
            "stock_id": sid,
            "company_name": inc.get("公司名稱") or bal.get("公司名稱"),
            "total_assets": total_assets, "working_capital": working_capital,
            "retained_earnings": retained, "ebit": ebit, "market_cap": market_cap,
            "total_liabilities": total_liab, "revenue": revenue,
        }

    def get_kline(self, sid):
        """真實 MA20：抓本月 + 上月逐日收盤，串成近 20+ 交易日。"""
        if sid in self._kline_cache:
            return self._kline_cache[sid]
        today = datetime.date.today()
        first_this = today.replace(day=1)
        last_prev = first_this - datetime.timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        recs = []
        for d0 in (first_prev, first_this):
            j = _get_www("/rwd/zh/afterTrading/STOCK_DAY",
                         {"date": d0.strftime("%Y%m%d"), "stockNo": sid, "response": "json"})
            for row in (j.get("data") or []):
                try:
                    recs.append((str(row[0]).strip(), float(str(row[6]).replace(",", ""))))
                except (ValueError, IndexError, TypeError):
                    pass
            time.sleep(0.6)  # 避免 www.twse 限流
        recs.sort(key=lambda x: x[0])           # 依日期(ROC 字串)由舊到新
        closes = [c for _, c in recs]
        if not closes:
            c = _num(self.daily.get(sid, {}).get("ClosingPrice"))
            closes = [c] if c is not None else []
        df = pd.DataFrame({"close": closes})
        self._kline_cache[sid] = df
        return df

    def get_chip(self, sid):
        """真實法人買賣超：三大法人買賣超股數 / 當日成交量 → 0~1 強度。"""
        net = self.chip.get(sid)
        vol = _num(self.daily.get(sid, {}).get("TradeVolume"))
        if net is None or not vol:
            return {"main_force_buy_ratio": 0.5, "net_shares": net}
        ratio = 0.5 + 0.5 * math.tanh((net / vol) * 5.0)   # 法人淨買占成交量比例 → 平滑映射 0~1
        return {"main_force_buy_ratio": round(max(0.0, min(1.0, ratio)), 3), "net_shares": net}
