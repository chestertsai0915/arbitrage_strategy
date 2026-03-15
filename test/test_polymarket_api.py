import sys
import os
import json

# 把目前檔案的「上一層目錄」加入 Python 的搜尋路徑中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from platforms.polymarket import PolymarketAPI

from utils.team_mapping import TeamNameMapper

def run_test():
    print("=" * 60)
    print(" 🚀 Polymarket API 整合測試 (含 Orderbook 詳情)")
    print("=" * 60)
    
    mapper = TeamNameMapper()
    poly_api = PolymarketAPI(mapper)
    
    # 1. 獲取賽事
    matches = poly_api.get_matches()
    if not matches:
        print("❌ 找不到任何 Polymarket 賽事。")
        return
        
    test_match = matches[0]
    token_map = test_match.raw_data.get("token_mapping", {})
    
    if not token_map:
        print("❌ 這場比賽沒有找到 Token Mapping。")
        return
        
    print(f"\n⚽ 測試賽事: {test_match.home_team} vs {test_match.away_team}")
    print("=" * 60)
    
    # 2. 迴圈遍歷這場比賽的所有下注選項 (Outcome)
    for outcome, token_id in token_map.items():
        print(f"   選項 [{outcome}]")
        print(f"      Token ID: {token_id[:10]}...{token_id[-5:]}")
        
        # 拿這個 Token ID 去查 Orderbook
        ob = poly_api.get_orderbook(token_id=token_id, selection=outcome)
        
        # 印出買方報價 (Bid) - 因為模型已經排序過，best_bid 絕對是最高買價
        if ob.best_bid:
            print(f"      最高買價 (Bid): 價格 {ob.best_bid.price:<6.3f} | 數量 (Size): {ob.best_bid.size}")
        else:
            print(f"      最高買價 (Bid): 目前沒有買單")
            
        # 印出賣方報價 (Ask) - 因為模型已經排序過，best_ask 絕對是最低賣價
        if ob.best_ask:
            print(f"      最低賣價 (Ask): 價格 {ob.best_ask.price:<6.3f} | 數量 (Size): {ob.best_ask.size}")
        else:
            print(f"      最低賣價 (Ask): 目前沒有賣單")
            
        print("-" * 40)

if __name__ == "__main__":
    run_test()