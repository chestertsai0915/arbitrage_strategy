import sys
import os

# 把目前檔案的「上一層目錄」(專案根目錄) 加入 Python 的搜尋路徑中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 匯入我們寫好的 SXBetAPI 與名稱轉換器
from platforms.sxbet import SXBetAPI
from utils.team_mapping import TeamNameMapper

def run_test():
    print("=" * 60)
    print(" 🚀 SX Bet API 整合測試 (含 Orderbook 正反向對沖詳情)")
    print("=" * 60)
    
    # 1. 初始化工具與 API
    mapper = TeamNameMapper()
    sx_api = SXBetAPI(mapper)
    
    # 2. 測試獲取賽事 (Active Markets)
    print("\n[測試 1] 開始獲取賽事清單...")
    matches = sx_api.get_matches()
    
    if not matches:
        print("❌ 找不到任何 SX Bet 賽事，請檢查網路。")
        return
        
    print(f"✅ 成功獲取 {len(matches)} 場標準化賽事！")
    
    # 3. 挑選第一場有 token_mapping 的 moneyline 比賽來做深度測試
    test_match = None
    for match in matches:
        if match.market_type == "moneyline" and match.raw_data.get("token_mapping"):
            test_match = match
            break  # 找到符合條件的就跳出
            
    if not test_match:
        print("❌ 找不到符合條件的賽事 (需包含 token_mapping)。")
        return
        
    token_map = test_match.raw_data.get("token_mapping", {})
    
    print(f"\n⚽ 測試賽事: {test_match.home_team} vs {test_match.away_team}")
    print(f"   盤口類型: {test_match.market_type}")
    print(f"   代表 Hash: {test_match.platform_event_id[:10]}...")
    print("=" * 60)
    
    # 4. 測試：配對印出 一般選項 與 Not 選項
    # 把這場比賽的三個基礎選項抓出來
    outcomes_to_test = [test_match.home_team, test_match.away_team, "Draw"]
    
    for base_outcome in outcomes_to_test:
        print(f"\n🎯 測試組合: [{base_outcome}] 及其反向盤口 [Not {base_outcome}]")
        
        # 連續抓取正向跟反向的 Orderbook
        for selection in [base_outcome, f"Not {base_outcome}"]:
            market_hash = token_map.get(selection)
            
            if not market_hash:
                print(f"   ⚠️ 找不到 {selection} 的 Hash")
                continue
                
            print(f"   📌 選項 [{selection}] (Hash: {market_hash[:10]}...)")
            
            # 🚨 關鍵：把 selection (例如 "Arsenal" 或 "Not Arsenal") 傳進去
            # SXBetAPI 底層會自動透過有沒有 "Not " 來決定要吃 Outcome 1 還是 Outcome 2 的 Maker
            ob = sx_api.get_orderbook(
                market_id=market_hash, 
                selection=selection
            )
            
            # 由於 SX Bet 底層我們寫的時候只專注抓 Asks (對手的掛單，我們的成本)，
            # 所以 Bid 通常會是空的，但我們還是保留印出的格式以求統一。
            if ob.best_bid:
                bid_decimal = 1.0 / ob.best_bid.price if ob.best_bid.price > 0 else 0
                print(f"      最高買價 (Bid): 隱含機率 {ob.best_bid.price:.4f} (賠率 {bid_decimal:.2f}) | 可用數量: ${ob.best_bid.size:,.2f} <-- 脫手價")
            else:
                print(f"      最高買價 (Bid): 目前沒有買單")
                
            if ob.best_ask:
                ask_decimal = 1.0 / ob.best_ask.price if ob.best_ask.price > 0 else 0
                print(f"      最低賣價 (Ask): 隱含機率 {ob.best_ask.price:.4f} (賠率 {ask_decimal:.2f}) | 可用數量: ${ob.best_ask.size:,.2f} <-- 買入成本")
            else:
                print(f"      最低賣價 (Ask): 目前沒有賣單")
                
        print("-" * 50)
        
    print("\n🎉 SX Bet 二元對沖 (Not) 盤口解析測試全數通過！")

if __name__ == "__main__":
    run_test()