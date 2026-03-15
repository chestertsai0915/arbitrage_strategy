import sys
import os
import json

# 把目前檔案的「上一層目錄」(專案根目錄) 加入 Python 的搜尋路徑中
# 這樣不管你把這個檔案放在根目錄還是 test/ 資料夾裡，都能順利執行
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 匯入我們寫好的 SXBetAPI 與名稱轉換器
from platforms.sxbet import SXBetAPI

from utils.team_mapping import TeamNameMapper

def run_test():
    print("=" * 60)
    print(" 🚀 SX Bet API 整合測試 (含 Orderbook 詳情)")
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
    test_match = None
    for match in matches:
        if match.market_type == "moneyline":
            test_match = match
            break  # 找到第一場 moneyline 就立刻跳出迴圈

    # 3. 挑選第一場比賽來做深度測試
    
    token_map = test_match.raw_data.get("token_mapping", {})
    
    if not token_map:
        print("❌ 這場比賽沒有找到 Token Mapping (Outcome 對應表)。")
        return
        
    print(f"\n⚽ 測試賽事: {test_match.home_team} vs {test_match.away_team}")
    print(f"   盤口類型: {test_match.market_type}")
    print(f"   原始盤口名稱: {test_match.market_name}")
    print(f"   Market Hash: {test_match.platform_event_id[:10]}...")
    print("=" * 60)
    
    # 4. 迴圈遍歷這場比賽的下注選項 (Outcome 1 & Outcome 2)
    # SX Bet 的 token_map 會長這樣: {"Arsenal": "Outcome 1", "Chelsea": "Outcome 2"}
    for team_name, market_hash in token_map.items():
        print(f"   選項 [{team_name}] (Hash: {market_hash[:10]}...)")
        
        # SX Bet 的 Moneyline 我們永遠買 Outcome 2 (也就是買 Not 發生前的那個隊伍)
        ob = sx_api.get_orderbook(
            market_id=market_hash, 
            selection="Outcome 1"
        )
        
        # 因為我們的模型統一採用「隱含機率 (Implied Probability, 0~1)」，
        # 所以為了方便人類閱讀，我們在 Print 時把它轉回「十進位賠率 (Decimal Odds)」
        
        # 印出買方報價 (Bid) - 注意：SX Bet 在套利計算時我們通常只在乎 Asks(賣單/成本)，
        # 但如果模型裡有 bids，一樣可以印出來看
        if ob.best_bid:
            bid_decimal = 1.0 / ob.best_bid.price
            print(f"      最高買價 (Bid): 隱含機率 {ob.best_bid.price:.4f} (賠率 {bid_decimal:.2f}) | 可用數量: ${ob.best_bid.size:,.2f}")
        else:
            print(f"      最高買價 (Bid): 目前沒有買單")
            
        # 印出賣方報價 (Ask) - 這是我們套利吃單的「成本」
        if ob.best_ask:
            ask_decimal = 1.0 / ob.best_ask.price
            print(f"      最低賣價 (Ask): 隱含機率 {ob.best_ask.price:.4f} (賠率 {ask_decimal:.2f}) | 可用數量: ${ob.best_ask.size:,.2f} <-- 套利成本")
        else:
            print(f"      最低賣價 (Ask): 目前沒有賣單")
            
        print("-" * 40)
        
    print("\n🎉 SX Bet 管線測試全數通過！")

if __name__ == "__main__":
    run_test()