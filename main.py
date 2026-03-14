# main.py

from platforms import (
    SXBetFetcher, SXBetNormalizer,
    PolymarketFetcher, PolymarketNormalizer,
    LimitlessFetcher, LimitlessNormalizer
)
from total_search import TotalSearch
from odds_engine import OddsEngine

def run_trading_system():
    print(" [系統啟動] 跨平台套利機器人啟動中...")

    # ==========================================
    # 1. 啟動並設定總管 (Total Search)
    # ==========================================
    search_engine = TotalSearch()
    search_engine.register_platform("SX Bet", SXBetFetcher, SXBetNormalizer)
    search_engine.register_platform("Polymarket", PolymarketFetcher, PolymarketNormalizer)
    search_engine.register_platform("Limitless", LimitlessFetcher, LimitlessNormalizer)

    # 執行搜尋，並把「有交集的比賽」拿回來存進變數
    # (注意：你的 total_search.py 裡面的 execute_search() 必須要有 return overlapping_matches)
    active_overlaps = search_engine.execute_search()

    # ==========================================
    # 2. 呼叫賠率引擎 (Odds Engine)
    # ==========================================
    if active_overlaps:
        print(f"\n 總管回報：找到 {len(active_overlaps)} 場交集比賽！交接給賠率引擎...")
        
        # 實例化賠率引擎
        odds_engine = OddsEngine()
        
        # 把資料餵給賠率引擎
        odds_engine.fetch_and_display_odds(active_overlaps)
        
    else:
        print("\n 總管回報：目前市場上沒有符合條件的交集比賽。程式結束。")

if __name__ == "__main__":
    run_trading_system()