-- ============================================================
-- RWA-STO 雙智能體量化選股系統 · 資料庫 Schema (PostgreSQL)
-- ============================================================

-- 1. 財報基本面數據表
CREATE TABLE IF NOT EXISTS company_financials (
    stock_id          VARCHAR(10)  NOT NULL,
    quarter           VARCHAR(7)   NOT NULL,          -- e.g. '2026-Q1'
    company_name      VARCHAR(64),
    working_capital   NUMERIC,                        -- 流動資產 - 流動負債
    total_assets      NUMERIC,
    retained_earnings NUMERIC,
    ebit              NUMERIC,                         -- 息稅前利潤
    market_cap        NUMERIC,                         -- 總股數 × 當前股價
    total_liabilities NUMERIC,
    revenue           NUMERIC,
    z_score           NUMERIC,                         -- 計算得出的 Altman Z-Score
    updated_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (stock_id, quarter)
);
CREATE INDEX IF NOT EXISTS idx_fin_zscore ON company_financials (z_score);

-- 2. 每日量價 / 籌碼資料表 (Agent B 用)
CREATE TABLE IF NOT EXISTS daily_market (
    stock_id            VARCHAR(10) NOT NULL,
    trade_date          DATE        NOT NULL,
    close               NUMERIC,
    volume              BIGINT,
    main_force_buy_ratio NUMERIC,                      -- 主力買超比率 0~1
    PRIMARY KEY (stock_id, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_mkt_date ON daily_market (trade_date);

-- 3. 每日精選清單 (決策引擎輸出，APP 直接讀此表)
CREATE TABLE IF NOT EXISTS daily_picks (
    pick_date   DATE        NOT NULL,
    side        VARCHAR(5)  NOT NULL,                  -- 'LONG' / 'SHORT'
    rank        INT         NOT NULL,                  -- 1~10
    stock_id    VARCHAR(10) NOT NULL,
    z_score     NUMERIC,
    signal      VARCHAR(16),                            -- STRONG_BUY / STRONG_SHORT
    main_buy    NUMERIC,
    PRIMARY KEY (pick_date, side, rank)
);

-- 4. 用戶貢獻與分紅表
CREATE TABLE IF NOT EXISTS user_contributions (
    user_address        VARCHAR(42) NOT NULL,          -- 錢包地址
    quarter             VARCHAR(7)  NOT NULL,
    contribution_points NUMERIC DEFAULT 0,             -- 當季累計貢獻積分
    share_percentage    NUMERIC,                        -- 該用戶積分 / 總積分 × 70%
    is_paid             BOOLEAN DEFAULT FALSE,
    payout_tx_hash      VARCHAR(66),
    PRIMARY KEY (user_address, quarter)
);
