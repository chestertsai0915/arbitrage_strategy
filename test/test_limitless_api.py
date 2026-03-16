import sys
import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from platforms.limitless import LimitlessAPI

from utils.team_mapping import TeamNameMapper

def run_test():
    print("=" * 60)
    print("  Limitless API 整合測試 (含 Orderbook 詳情)")
    print("=" * 60)
    
    mapper = TeamNameMapper()
    lim_api = LimitlessAPI(mapper)
    
    # 1. 獲取賽事
    matches = lim_api.get_matches()
    
    if not matches:
        print(" 找不到任何 Limitless 賽事。")
        return
        
    print(f" 成功獲取 {len(matches)} 場標準化賽事！")
    
    # 2. 過濾並尋找第一場有 token_mapping 的 Moneyline 賽事
    test_match = None
    for match in matches:
        if match.market_type == "moneyline" and match.raw_data.get("token_mapping"):
            test_match = match
            break
            
    if not test_match:
        print(" 找不到具有子盤口 (token_mapping) 的賽事。")
        return
    
    print(f"\n 測試賽事: {test_match.home_team} vs {test_match.away_team}")
    print(f"   母賽事 Slug: {test_match.platform_event_id}")
    print("=" * 60)
    
    token_map = test_match.raw_data.get("token_mapping", {})
    
    # 3. 遍歷選項並取得 Orderbook
    for team_name, child_slug in token_map.items():
        print(f"   選項 [{team_name}] (子盤口 Slug: {child_slug[:20]}...)")
        
        ob = lim_api.get_orderbook(market_id=child_slug, selection=team_name)
        
        if ob.best_bid:
            bid_decimal = 1.0 / ob.best_bid.price if ob.best_bid.price > 0 else 0
            print(f"      最高買價 (Bid): 隱含機率 {ob.best_bid.price:.4f} (賠率 {bid_decimal:.2f}) | 可用數量: ${ob.best_bid.size:,.2f}")
        else:
            print(f"      最高買價 (Bid): 目前沒有買單")
            
        if ob.best_ask:
            ask_decimal = 1.0 / ob.best_ask.price if ob.best_ask.price > 0 else 0
            print(f"      最低賣價 (Ask): 隱含機率 {ob.best_ask.price:.4f} (賠率 {ask_decimal:.2f}) | 可用數量: ${ob.best_ask.size:,.2f} <-- 成本")
        else:
            print(f"      最低賣價 (Ask): 目前沒有賣單")
            
        print("-" * 40)
        
    print("\n🎉 Limitless 管線測試全數通過！")

if __name__ == "__main__":
    run_test()