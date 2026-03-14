# odds_engine.py

class OddsEngine:
    """負責接收交集比賽，並向各平台獲取最新賠率"""
    
    def __init__(self):
        print(" [Odds Engine] 賠率計算引擎已初始化。")

    def fetch_and_display_odds(self, overlapping_matches):
        """
        接收交集比賽清單，並負責抓取賠率
        overlapping_matches: List of tuples -> [(match_id, [StandardEvent, StandardEvent...]), ...]
        """
        print("\n" + "="*60)
        print("  第三階段：啟動即時賠率抓取")
        print("="*60)

        if not overlapping_matches:
            print(" 沒有收到任何交集比賽，賠率引擎休息中。")
            return

        for cluster_id, events in overlapping_matches:
            # cluster_id 是配對引擎給這場比賽的統一 ID
            home_team = events[0].home_team
            away_team = events[0].away_team
            
            print(f"\n 正在查詢賠率: {home_team} vs {away_team} (ID: {cluster_id})")
            
            for event in events:
                platform = event.platform
                event_id = event.platform_event_id
                
                # 這裡就是我們接下來要寫各平台 API 的地方！
                if platform == "SX Bet":
                    print(f"    [SX Bet] 準備拿 marketHash ({event_id[:10]}...) 去查 Orderbook...")
                    # sx_odds = self._get_sx_odds(event_id)
                
                elif platform == "Polymarket":
                    print(f"    [Polymarket] 準備拿 conditionId/token 去查 Gamma API...")
                    # poly_odds = self._get_poly_odds(event_id)
                    
                elif platform == "Limitless":
                    print(f"    [Limitless] 準備拿 Address 去查價格...")
                    # limitless_odds = self._get_limitless_odds(event_id)

            print("-" * 50)