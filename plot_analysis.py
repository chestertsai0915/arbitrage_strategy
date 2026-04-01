import json
import matplotlib.pyplot as plt
import os

def plot_historical_data(file_path: str, target_team: str):
    """
    讀取 JSONL 歷史數據檔，並畫出指定隊伍在兩家平台的 Ask Price (買入成本)
    """
    if not os.path.exists(file_path):
        print(f"❌ 找不到檔案: {file_path}")
        return

    times = []
    poly_asks = []
    sx_asks = []

    print(f"📊 正在解析數據檔: {file_path} ...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                
                # 擷取時間 (格式例如 "02:50:03.525"，我們切掉毫秒只留 "02:50:03")
                dt_str = data.get("datetime", "")
                time_label = dt_str.split(".")[0] 
                
                # 擷取 Polymarket 的 Best Ask
                poly_book = data.get("orderbooks", {}).get("Polymarket", {}).get(target_team, {})
                poly_ask_list = poly_book.get("asks", [])
                poly_best_ask = poly_ask_list[0]["price"] if poly_ask_list else None
                
                # 擷取 SX Bet 的 Best Ask
                sx_book = data.get("orderbooks", {}).get("SX_Bet", {}).get(target_team, {})
                sx_ask_list = sx_book.get("asks", [])
                sx_best_ask = sx_ask_list[0]["price"] if sx_ask_list else None
                
                # 確保兩邊都有報價才畫出來，避免圖表斷層
                if poly_best_ask is not None and sx_best_ask is not None:
                    times.append(time_label)
                    poly_asks.append(poly_best_ask)
                    sx_asks.append(sx_best_ask)
                    
            except Exception as e:
                print(f"⚠️ 解析單行資料時發生錯誤: {e}")
                continue

    if not times:
        print("❌ 檔案內沒有足夠的有效數據可供繪圖。")
        return

    print(f"✅ 解析完成！共讀取 {len(times)} 筆有效報價，正在繪製圖表...")

    # ==========================================
    # 開始繪圖 (Matplotlib)
    # ==========================================
    plt.figure(figsize=(12, 6))
    
    # 畫兩條折線
    plt.plot(times, poly_asks, label='Polymarket Ask (Buy Cost)', color='blue', linewidth=2, marker='.', markersize=8)
    plt.plot(times, sx_asks, label='SX Bet Ask (Buy Cost)', color='orange', linewidth=2, marker='.', markersize=8)

    # 圖表標題與標籤
    plt.title(f"Best Ask Price Comparison for '{target_team}'", fontsize=15, fontweight='bold')
    plt.xlabel("Time", fontsize=12)
    plt.ylabel("Ask Price (Implied Probability)", fontsize=12)
    
    # X 軸時間標籤處理 (避免資料太多時字擠在一起，設定最多顯示 15 個時間點)
    tick_spacing = max(1, len(times) // 15)
    plt.xticks(range(0, len(times), tick_spacing), times[::tick_spacing], rotation=45)
    
    # 加上網格與圖例
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(loc="best", fontsize=11)
    
    # 自動排版避免邊緣被切掉
    plt.tight_layout()
    
    # 顯示圖表
    plt.show()

if __name__ == "__main__":
    # 🌟 在這裡換成你剛剛存下來的 jsonl 檔案路徑！
    # 如果放在 market_data 資料夾內，請改成相對路徑，例如：
    # FILE_TO_READ = "market_data/PURE_ORDERBOOK_midtjylland_vs_nottingham_forest_20260320_025000.jsonl"
    FILE_TO_READ = r"D:\investment\博弈套利\market_data\PURE_ORDERBOOK_midtjylland_vs_nottingham_forest_20260320_020921.jsonl"  
    
    TARGET_TEAM = "midtjylland"
    
    plot_historical_data(FILE_TO_READ, TARGET_TEAM)