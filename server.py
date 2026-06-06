# -*- coding: utf-8 -*-
"""
真實版網頁伺服器(部署到 Render Web Service)
- 同源提供 board.html / picks.json,讓看板顯示「真實」名單
- 啟動時在背景跑一次真實引擎；之後每天自動更新一次
- 不需要任何金鑰；TWSE OpenAPI 免費公開

本機測試:
    pip install -r requirements.txt flask gunicorn
    python3 server.py        # 開 http://localhost:8000/board.html
Render 啟動指令:
    gunicorn server:app
"""

import os
import json
import threading
import time
from datetime import date

from flask import Flask, send_from_directory, jsonify

ROOT = os.path.dirname(os.path.abspath(__file__))
# 網站檔(board.html / index.html…)與引擎同層(扁平 bundle);若不在同層則退回上層
SITE = ROOT if os.path.exists(os.path.join(ROOT, "board.html")) else os.path.abspath(os.path.join(ROOT, ".."))
PICKS = os.path.join(ROOT, "picks.json")

app = Flask(__name__)
_status = {"state": "starting", "updated": None}


def _generate():
    """背景產生真實 picks.json，每 24h 一次"""
    from real_run import run_real
    while True:
        try:
            _status["state"] = "running"
            out = run_real()                 # 真實 TWSE 資料
            with open(PICKS, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            _status["state"] = "ok"
            _status["updated"] = out.get("pick_date")
            print(f"[server] picks.json 已更新 {out.get('pick_date')} "
                  f"(多{len(out['long'])}/空{len(out['short'])})")
        except Exception as e:
            _status["state"] = f"error: {e}"
            print("[server] 產生失敗:", e)
        time.sleep(24 * 3600)


@app.route("/picks.json")
def picks():
    if os.path.exists(PICKS):
        return send_from_directory(ROOT, "picks.json", mimetype="application/json")
    return jsonify({"pick_date": str(date.today()), "scanned": 0,
                    "long": [], "short": [], "note": "首次資料產生中，請稍後重整"}), 200


@app.route("/status")
def status():
    return jsonify(_status)


@app.route("/")
@app.route("/<path:fname>")
def site(fname="index.html"):
    target = os.path.join(SITE, fname)
    if os.path.exists(target) and os.path.isfile(target):
        return send_from_directory(SITE, fname)
    return send_from_directory(SITE, "index.html")


# 啟動背景產生
threading.Thread(target=_generate, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
