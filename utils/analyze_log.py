import json

def analyze_arbitrage_log(file_path):
    print("=" * 60)
    print(" 🔍 開始分析 JSON 套利日誌")
    print("=" * 60)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
                
            data = json.loads(line)
            time_str = data["datetime"]
            poly = data["orderbooks"].get("Polymarket", {})
            sx = data["orderbooks"].get("SX_Bet", {})
            
            # 安全獲取最佳 Ask 的函數
            def get_best_ask(book):
                asks = book.get("asks", [])
                return asks[0]["price"] if asks else 999.0 # 如果沒賣單就給個無限大
            
            # 1. 抓取各平台最佳 Ask
            mid_poly_ask = get_best_ask(poly.get("midtjylland", {}))
            mid_sx_ask = get_best_ask(sx.get("midtjylland", {}))
            
            for_poly_ask = get_best_ask(poly.get("nottingham_forest", {}))
            for_sx_ask = get_best_ask(sx.get("nottingham_forest", {}))
            
            draw_poly_ask = get_best_ask(poly.get("Draw", {}))
            draw_sx_ask = get_best_ask(sx.get("Draw", {}))
            
            # 2. 挑出每個選項全網最便宜的價格 (Dutching 邏輯)
            best_mid = min(mid_poly_ask, mid_sx_ask)
            best_for = min(for_poly_ask, for_sx_ask)
            best_draw = min(draw_poly_ask, draw_sx_ask)
            
            total_cost = best_mid + best_for + best_draw
            
            
            
            # 3. 判斷是否套利
            if total_cost < 1.0:
                profit_margin = (1.0 - total_cost) * 100
                print(f"\n {time_str} 發現套利機會")
                print(f"    發現套利空間！預期利潤率: {profit_margin:.2f}%")
                print(f"      - 買主勝: {best_mid}")
                print(f"      - 買客勝: {best_for}")
                print(f"      - 買平手: {best_draw}")
            else:
                pass

if __name__ == "__main__":
    # 假設你的資料存成 data.jsonl
    analyze_arbitrage_log(r"D:\investment\博弈套利\market_data\PURE_ORDERBOOK_manchester_liverpool_2026-04-04_20260404_195412.jsonl") 
   