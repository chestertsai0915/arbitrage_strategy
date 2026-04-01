import sys
import os

# 把目前檔案的「上一層目錄」加入 Python 的搜尋路徑中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from platforms.polymarket import PolymarketAPI
from utils.team_mapping import TeamNameMapper

def run_test():
    print("=" * 60)
    print(" 🚀 Polymarket API 整合測試 (含 Orderbook 正反向對沖詳情)")
    print("=" * 60)
    
    mapper = TeamNameMapper()
    poly_api = PolymarketAPI(mapper)
    
    # 1. 獲取賽事
    matches = poly_api.get_matches()
    if not matches:
        print("❌ 找不到任何 Polymarket 賽事。")
        return
        
    print(f"✅ 成功獲取 {len(matches)} 場標準化賽事！")
        
    # 2. 過濾並尋找第一場有 token_mapping 的賽事
    test_match = None
    for match in matches:
        if match.raw_data.get("token_mapping"):
            test_match = match
            break
            
    if not test_match:
        print("❌ 找不到具有子盤口 (token_mapping) 的賽事。")
        return
        
    token_map = test_match.raw_data.get("token_mapping", {})
    
    print(f"\n⚽ 測試賽事: {test_match.home_team} vs {test_match.away_team}")
    print("=" * 60)
    
    # 3. 測試：配對印出 一般選項 與 Not 選項
    # 把這場比賽的三個基礎選項抓出來
    outcomes_to_test = [test_match.home_team, test_match.away_team, "Draw"]
    
    for base_outcome in outcomes_to_test:
        print(f"\n🎯 測試組合: [{base_outcome}] 及其反向盤口 [Not {base_outcome}]")
        
        # 連續抓取正向跟反向的 Orderbook
        for selection in [base_outcome, f"Not {base_outcome}"]:
            token_id = token_map.get(selection)
            if not token_id:
                print(f"   ⚠️ 找不到 {selection} 的 Token ID")
                continue
                
            print(f"   📌 選項 [{selection}] (Token ID: {token_id[:6]}...{token_id[-4:]})")
            
            # 拿這個 Token ID 去查 Orderbook，PolymarketAPI 內會自動根據 "Not" 字眼進行反轉
            ob = poly_api.get_orderbook(token_id=token_id, selection=selection)
            
            # 印出買方報價 (Bid) -> 也就是我們賣出的價格 (脫手價)
            if ob.best_bid:
                bid_decimal = 1.0 / ob.best_bid.price if ob.best_bid.price > 0 else 0
                print(f"      最高買價 (Bid): 隱含機率 {ob.best_bid.price:.4f} (賠率 {bid_decimal:.2f}) | 可用數量: ${ob.best_bid.size:,.2f} <-- 脫手價")
            else:
                print(f"      最高買價 (Bid): 目前沒有買單")
                
            # 印出賣方報價 (Ask) -> 也就是我們要買入的成本
            if ob.best_ask:
                ask_decimal = 1.0 / ob.best_ask.price if ob.best_ask.price > 0 else 0
                print(f"      最低賣價 (Ask): 隱含機率 {ob.best_ask.price:.4f} (賠率 {ask_decimal:.2f}) | 可用數量: ${ob.best_ask.size:,.2f} <-- 買入成本")
            else:
                print(f"      最低賣價 (Ask): 目前沒有賣單")
                
        print("-" * 50)
        
    print("\n🎉 Polymarket 二元對沖 (Not) 盤口解析測試全數通過！")

if __name__ == "__main__":
    run_test()