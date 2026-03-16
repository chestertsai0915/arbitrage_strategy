from typing import List, Tuple, Dict
from models.match import StandardEvent

class ArbitrageEngine:
    """套利引擎：負責計算跨平台的最佳賠率組合，尋找無風險套利機會"""
    
    def __init__(self):
        # 未來如果需要設定手續費、最小利潤門檻，可以加在這裡
        self.min_roi_threshold = 0.0 # 大於 0% 就當作有套利機會
        
    def find_opportunities(self, overlapping_matches: List[Tuple[str, List[StandardEvent]]], api_clients: dict) -> List[dict]:
        """
        遍歷交集賽事，抓取 Orderbook 分析 3-way (主勝/客勝/平手) 的套利空間。
        回傳依 ROI (投資報酬率) 由高到低排序的套利機會列表。
        """
        print("\n" + "="*60)
        print(" 找最佳賠率組合")
        print("="*60)
        
        opportunities = []

        for cluster_id, events in overlapping_matches:
            if not events:
                continue
                
            home_team = events[0].home_team
            away_team = events[0].away_team
            outcomes = [home_team, away_team, "Draw"]
            
            # 準備記錄每個選項的「最佳價格 (最小隱含機率)」與「來源平台」
            best_prices = {
                outcome: {"price": float('inf'), "platform": None, "size": 0} 
                for outcome in outcomes
            }
            
            for event in events:
                platform = event.platform
                api = api_clients.get(platform)
                if not api:
                    continue
                    
                token_mapping = event.raw_data.get("token_mapping", {})
                
                for outcome in outcomes:
                    token_id = token_mapping.get(outcome)
                    if not token_id:
                        continue 
                        
                    try:
                        # [相容性處理] SX Bet 的 API 需要傳入 Outcome 1 / 2 
                        selection_arg = outcome
                        if platform == "SX_Bet":
                            if outcome == home_team: selection_arg = "Outcome 1"
                            elif outcome == away_team: selection_arg = "Outcome 2"
                            else: selection_arg = "Draw"
                            
                        # 呼叫平台的 Orderbook API
                        ob = api.get_orderbook(token_id, selection_arg)
                        
                        # 我們要「買」這個結果，所以看 Asks (賣家掛單)
                        if ob and ob.asks:
                            cheapest_ask = min(ob.asks, key=lambda x: x.price)
                            
                            # 如果這個平台的價格比目前記錄的還要便宜，就更新最佳解！
                            if cheapest_ask.price < best_prices[outcome]["price"]:
                                best_prices[outcome]["price"] = cheapest_ask.price
                                best_prices[outcome]["platform"] = platform
                                best_prices[outcome]["size"] = cheapest_ask.size
                                
                    except Exception as e:
                        # 若某平台該選項獲取失敗，靜默跳過，讓其他平台補上
                        pass
                        
            # ---------------------------------------------
            # 結算這場比賽的總隱含機率
            # ---------------------------------------------
            # 必須確保三個選項 (A贏、B贏、平手) 都有拿到報價，才能進行無風險套利
            if all(best_prices[o]["price"] != float('inf') for o in outcomes):
                total_implied_prob = sum(best_prices[o]["price"] for o in outcomes)
                
                # 套利判定核心！如果加總小於 1，代表有利可圖
                if total_implied_prob < 1.0:
                    roi = (1.0 / total_implied_prob - 1) * 100
                    
                    if roi > self.min_roi_threshold:
                        opportunities.append({
                            "cluster_id": cluster_id,
                            "match": f"{home_team} vs {away_team}",
                            "roi": roi,
                            "total_prob": total_implied_prob,
                            "best_prices": best_prices
                        })

        # 按照 ROI 排序，由高到低
        opportunities.sort(key=lambda x: x["roi"], reverse=True)
        return opportunities