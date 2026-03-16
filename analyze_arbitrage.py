import sys
import os
sys.path.append(os.getcwd())

from utils.team_mapping import TeamNameMapper
from platforms.polymarket import PolymarketAPI
from platforms.sxbet import SXBetAPI
from platforms.limitless import LimitlessAPI
from core.matcher import MatchEngine
from core.arbitrage_engine import ArbitrageEngine # 引入剛剛寫好的套利引擎

def main():
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
        all_events.extend(api.get_matches())
        
    # 3. 執行賽事配對
    match_engine = MatchEngine(threshold=80.0, min_platforms=2)
    overlapping_matches = match_engine.match_events(all_events)
    
    if not overlapping_matches:
        print(" 沒有找到交集比賽，結束分析。")
        return
        
    # 4. 執行套利分析！
    arb_engine = ArbitrageEngine()
    arbs = arb_engine.find_opportunities(overlapping_matches, api_clients)
    
    # 5. 印出最終報表
    print("\n" + "="*60)
    print(f"  掃描完畢！共發現 {len(arbs)} 個無風險套利機會。")
    print("="*60)
    
    for arb in arbs:
        print(f" ROI: {arb['roi']:>5.2f}% | 總成本: {arb['total_prob']:.4f} | 賽事: {arb['match']}")
        for outcome, data in arb["best_prices"].items():
            print(f"     -> 買 {outcome:15} @ {data['platform']:12} (隱含機率: {data['price']:.4f}, 深度: {data['size']:.2f}U)")
        print("-" * 50)

if __name__ == "__main__":
    main()