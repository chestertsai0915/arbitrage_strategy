import sys
import os
import time
import json
import traceback
from datetime import datetime

# 匯入你的 API 模組
from utils.team_mapping import TeamNameMapper
from platforms.polymarket import PolymarketAPI
from platforms.sxbet import SXBetAPI

def clear_screen():
    """清除終端機畫面，製造即時儀表板的效果"""
    os.system('cls' if os.name == 'nt' else 'clear')

def serialize_orderbook(ob):
    """將 Orderbook 物件轉換為可存入 JSON 的字典格式"""
    if not ob:
        return {"asks": [], "bids": []}
    return {
        "asks": [{"price": a.price, "size": a.size} for a in ob.asks[:5]], # 記錄前 5 檔賣單
        "bids": [{"price": b.price, "size": b.size} for b in ob.bids[:5]]  # 記錄前 5 檔買單
    }

def main():
    # ==========================================
    # 1. 寫死狙擊目標的 Token Mapping (純基礎選項)
    # ==========================================
    match_title = "midtjylland vs nottingham_forest"
    home_team = "midtjylland"
    away_team = "nottingham_forest"
    POLL_INTERVAL = 0.2  # 輪詢間隔：0.2 秒
    
    # 只放標準的主勝、客勝、平手
    sx_keys = {
        "nottingham_forest": "0xb3a369610386ffd44a168b9e90d336b68cbba1c70fac7c40a8c8607182a0bebf",
        "midtjylland": "0x1d2944bd6d6b219820178a77dc3abccf15234e0f9c95cf5f50ed37d97b95d156",
        "Draw": "0x780a02e14273c4a1954031bc029239b174a23fe7e7b75a0dd1adee755dcc30f6"
    }

    poly_keys = {
        "midtjylland": "47382633911097324690852856526737287671649541085913855159696395204536496865583",
        "Draw": "74134930211927526143026940731841904884921926089936716117812294201223751932804",
        "nottingham_forest": "11381745081746637908130783364467955863250369078721878469131698218997759271578"
    }

    # ==========================================
    # 2. 初始化與建檔
    # ==========================================
    DATA_DIR = "market_data"
    os.makedirs(DATA_DIR, exist_ok=True)

    mapper = TeamNameMapper()
    poly_api = PolymarketAPI(mapper)
    sx_api = SXBetAPI(mapper)

    safe_title = match_title.replace(" ", "_").replace(":", "")
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(DATA_DIR, f"PURE_ORDERBOOK_{safe_title}_{timestamp_str}.jsonl")

    print("=" * 70)
    print(f" 📊 啟動純 Orderbook 數據採集器 | 目標: {match_title}")
    print(f" 📁 數據將即時寫入: {log_filename}")
    print("=" * 70)
    print("🚀 啟動極速紀錄模式...")

    base_outcomes = [home_team, away_team, "Draw"]
    poll_count = 0
    
    # ==========================================
    # 3. 無限迴圈數據採集 (純紀錄，無套利邏輯)
    # ==========================================
    with open(log_filename, "a", encoding="utf-8") as log_file:
        while True:
            try:
                poll_count += 1
                current_ts = time.time()
                current_dt = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                
                # 每一秒的數據快照
                snapshot_data = {
                    "timestamp": current_ts,
                    "datetime": current_dt,
                    "match": match_title,
                    "orderbooks": {"Polymarket": {}, "SX_Bet": {}}
                }

                dashboard_lines = []

                for outcome in base_outcomes:
                    # 分別抓取兩家平台的 Orderbook
                    poly_ob = poly_api.get_orderbook(poly_keys[outcome], outcome)
                    sx_ob = sx_api.get_orderbook(sx_keys[outcome], outcome)

                    # 寫入 JSON 結構
                    snapshot_data["orderbooks"]["Polymarket"][outcome] = serialize_orderbook(poly_ob)
                    snapshot_data["orderbooks"]["SX_Bet"][outcome] = serialize_orderbook(sx_ob)

                    # 擷取最佳買賣價供終端機顯示 (如果為空則顯示 0)
                    poly_bid = poly_ob.best_bid.price if poly_ob.best_bid else 0
                    poly_ask = poly_ob.best_ask.price if poly_ob.best_ask else 0
                    sx_bid = sx_ob.best_bid.price if sx_ob.best_bid else 0
                    sx_ask = sx_ob.best_ask.price if sx_ob.best_ask else 0

                    # 準備儀表板文字
                    dashboard_lines.append(f" 🎯 選項: {outcome[:17]:<17}")
                    dashboard_lines.append(f"    [Polymarket] 買價(Bid): {poly_bid:.4f}  |  賣價(Ask): {poly_ask:.4f}")
                    dashboard_lines.append(f"    [SX_Bet]     買價(Bid): {sx_bid:.4f}  |  賣價(Ask): {sx_ask:.4f}")
                    dashboard_lines.append("-" * 65)

                # 寫入檔案並強制 flush
                log_file.write(json.dumps(snapshot_data) + "\n")
                log_file.flush()

                # --- 畫面更新 (儀表板) ---
                if poll_count % 5 == 1:
                    clear_screen()
                    print("=" * 65)
                    print(f" 📊 鎖定賽事: {match_title} | 輪詢間隔: {POLL_INTERVAL}s")
                    print(f" 💾 資料記錄中... 已記錄 {poll_count} 筆 | 時間: {current_dt}")
                    print("=" * 65)
                    print("📈 即時最佳買賣價監控 (Best Bid / Best Ask):")
                    for line in dashboard_lines:
                        print(line)
                    print(f"按下 Ctrl+C 結束採集並保存資料。")

                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                print("\n🛑 接收到中斷指令，停止採集。資料已安全保存於 market_data/ 目錄下。")
                break
            except Exception as e:
                print(f"\n⚠️ 迴圈執行時發生錯誤: {e}")
                traceback.print_exc() 
                time.sleep(2)  # 發生錯誤稍微休息一下

if __name__ == "__main__":
    main()