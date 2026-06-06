# -*- coding: utf-8 -*-
"""
真實資料源：證交所 OpenAPI（免費公開，無需金鑰）
================================================
取代 MockDataSource。提供與 Mock 相同介面：
  get_universe() / get_financials(stock_id) / get_kline(stock_id) / get_chip(stock_id)

資料端點（皆為 https://openapi.twse.com.tw）:
  /v1/opendata/t187ap06_L_ci   綜合損益表(一般業)  → 營收、營業利益(EBIT)
  /v1/opendata/t187ap07_L_ci   資產負債表(一般業)  → 總資產、總負債、流動資產/負債、保留盈餘
  /v1/exchangeReport/BWIBBU_ALL 個股 PER/PBR/殖利率 → 推算市值
  /v1/exchangeReport/STOCK_DAY_ALL 全individuals當日收盤/量
  /v1/exchangeReport/STOCK_DAY?stockNo=XXXX 單檔近月日K (算 MA20)

⚠ 此程式需在「網路不受限」的環境執行(Render / 你的電腦)。
   欄位名稱以 TWSE 實際回傳為準，已用多組備援鍵名容錯。
"""

import time
import requests
import pandas as pd

BASE = "https://openapi.twse.com.tw/v1"
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


def _num(v):
    """把 '149804135.00' / '' / '1,234' 轉成 float；空值回 None"""
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
    """從多個可能的欄位名取第一個有值的"""
    for k in keys:
        if k in row:
            n = _num(row[k])
            if n is not None:
                return n
    return None


class TWSEDataSource:
    def __init__(self, limit=None, watchlist=None):
        print("[TWSE] 載入真實財報與股價…")
        self.income = self._index(_get("/opendata/t187ap06_L_ci"))   # 損益表
        self.balance = self._index(_get("/opendata/t187ap07_L_ci"))  # 資產負債表
        self.valuation = self._index_val(_get("/exchangeReport/BWIBBU_ALL"))
        self.daily = self._index_daily(_get("/exchangeReport/STOCK_DAY_ALL"))

        ids = sorted(set(self.income) & set(self.balance) & set(self.daily))
        if watchlist:
            wl = set(str(s) for s in watchlist)
            ids = [s for s in ids if s in wl]
            # 釋放記憶體：只保留清單內資料(免費方案友善)
            self.income = {k: v for k, v in self.income.items() if k in wl}
            self.balance = {k: v for k, v in self.balance.items() if k in wl}
            self.daily = {k: v for k, v in self.daily.items() if k in wl}
            self.valuation = {k: v for k, v in self.valuation.items() if k in wl}
        if limit:
            ids = ids[:limit]
        self._universe = ids
        self._kline_cache = {}
        print(f"[TWSE] 可用標的(財報+股價齊全): {len(self._universe)} 檔")

    # ---- 索引建立 ----
    def _index(self, rows):
        out = {}
        for r in rows:
            sid = str(r.get("公司代號", "")).strip()
            if sid:
                out[sid] = r
        return out

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

        working_capital = None
        if cur_assets is not None and cur_liab is not None:
            working_capital = cur_assets - cur_liab

        # 市值 ≈ 股東權益 × 股價淨值比(PBR)
        equity = None
        if total_assets is not None and total_liab is not None:
            equity = total_assets - total_liab
        pbr = _pick(val, "PBratio", "股價淨值比", "PBR")
        market_cap = equity * pbr if (equity is not None and pbr) else None

        return {
            "stock_id": sid,
            "company_name": inc.get("公司名稱") or bal.get("公司名稱"),
            "total_assets": total_assets,
            "working_capital": working_capital,
            "retained_earnings": retained,
            "ebit": ebit,
            "market_cap": market_cap,
            "total_liabilities": total_liab,
            "revenue": revenue,
        }

    def get_kline(self, sid):
        """抓單檔近一個月日K，算 MA20。已快取避免重複請求。"""
        if sid in self._kline_cache:
            return self._kline_cache[sid]
        data = _get("/exchangeReport/STOCK_DAY", params={"stockNo": sid})
        closes = []
        if isinstance(data, dict):
            rows = data.get("data", [])
            for row in rows:
                # STOCK_DAY 欄位: 日期,成交股數,成交金額,開盤,最高,最低,收盤,漲跌,成交筆數
                try:
                    closes.append(float(str(row[6]).replace(",", "")))
                except (ValueError, IndexError, TypeError):
                    pass
        if not closes:
            # 退而求其次：用 STOCK_DAY_ALL 當日收盤(只有一天，MA20 會不足→Agent B 回 HOLD)
            d = self.daily.get(sid, {})
            c = _num(d.get("ClosingPrice") or d.get("收盤價"))
            closes = [c] if c is not None else []
        df = pd.DataFrame({"close": closes})
        self._kline_cache[sid] = df
        time.sleep(0.3)  # 禮貌性延遲，避免被限流
        return df

    def get_chip(self, sid):
        """
        TWSE OpenAPI 無免費「主力買超」欄位。
        以當日漲跌幅方向作為籌碼方向的近似(正=偏買 0.65 / 負=偏賣 0.35)。
        若要真實主力買超，需另接券商分點資料源。
        """
        d = self.daily.get(sid, {})
        chg = _num(d.get("Change") or d.get("漲跌價差"))
        if chg is None:
            return {"main_force_buy_ratio": 0.5}
        return {"main_force_buy_ratio": 0.65 if chg > 0 else (0.35 if chg < 0 else 0.5)}
