import sys
import os
sys.path.append(os.getcwd())

from utils.team_mapping import TeamNameMapper
from platforms.polymarket import PolymarketAPI
from platforms.sxbet import SXBetAPI
from platforms.limitless import LimitlessAPI
from core.matcher import MatchEngine
from core.arbitrage_engine import ArbitrageEngine

def main():
    print("=" * 60)
    print("  啟動跨平台套利深度搜尋系統 (支援 3-Way 與 2-Way 對沖)")
    print("=" * 60)

    # 1. 初始化資源
    mapper = TeamNameMapper()
    api_clients = {
        "SX_Bet": SXBetAPI(mapper),
        "Polymarket": PolymarketAPI(mapper),
        "Limitless": LimitlessAPI(mapper)
    }
    
    # 2. 抓取所有資料
    all_events = []
    print(" 正在抓取各大平台賽事...")
    for api in api_clients.values():
        try:
            all_events.extend(api.get_matches())
        except Exception as e:
            print(f"❌ 抓取 {api.name} 失敗: {e}")
            
    #  2.5. 安檢過濾 - 只保留安全的套利標的
    moneyline_events = [
        e for e in all_events 
        if e.market_type == "moneyline" and e.raw_data.get("token_mapping")
    ]
        
    # 3. 執行賽事配對
    match_engine = MatchEngine(threshold=80.0, min_platforms=2)
    # 注意：這裡解包 matcher 回傳的兩個變數 (交集比賽, 獨立比賽)
    overlapping_matches = match_engine.match_events(moneyline_events)
    
    if not overlapping_matches:
        print("\n 目前沒有找到交集比賽，結束分析。")
        return
        
    # 4. 執行套利分析！ (引擎內部已經自動尋找 3-Way 與 2-Way 了)
    arb_engine = ArbitrageEngine()
    arbs = arb_engine.find_opportunities(overlapping_matches, api_clients)
    
    # 5. 印出最終報表
    print("\n" + "="*70)
    print(f"  掃描完畢！共發現 {len(arbs)} 個無風險套利機會。")
    print("="*70)
    
    for arb in arbs:
        arb_type = arb.get("type", "Unknown")
        max_size = arb.get("max_size", 0)
        
        # 標題行：加上套利類型 (3-Way 或 2-Way) 與 可用資金容量
        print(f"[{arb_type}] ROI: {arb['roi']:>5.2f}% | 總成本: {arb['total_prob']:.4f} | 容量: ${max_size:,.2f}")
        print(f"    賽事: {arb['match']}")
        
        # 迴圈印出每一個需要下注的「腳 (Legs)」
        for outcome, data in arb["legs"].items():
            print(f"     -> 買 {outcome:15} @ {data['platform']:12} (機率: {data['price']:.4f}, 深度: ${data['size']:,.2f})")
        print("-" * 70)

if __name__ == "__main__":
    main()