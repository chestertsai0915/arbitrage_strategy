from typing import List, Tuple, Dict
from models.match import StandardEvent

class ArbitrageEngine:
    """套利引擎：負責計算跨平台的最佳賠率組合，尋找無風險套利機會"""
    
    def __init__(self):
        # 設定最小利潤門檻 (0.0 代表大於 0% 就算套利)
        self.min_roi_threshold = 0.0 
        
    def find_opportunities(self, overlapping_matches: List[Tuple[str, List[StandardEvent]]], api_clients: dict) -> List[dict]:
        """
        遍歷交集賽事，抓取 Orderbook 分析 3-way (主/客/和) 與 2-way (正/反) 的套利空間。
        回傳依 ROI (投資報酬率) 由高到低排序的套利機會列表。
        """
        print("\n  啟動核心套利引擎：尋找最佳賠率組合...")
        opportunities = []

        for cluster_id, events in overlapping_matches:
            if not events:
                continue
                
            home_team = events[0].home_team
            away_team = events[0].away_team
            
           
            # 策略一：3-Way 傳統套利 (主勝 + 客勝 + 平手)
           
            outcomes_3way = [home_team, away_team, "Draw"]
            best_prices_3way = {o: {"price": float('inf'), "platform": None, "size": 0} for o in outcomes_3way}
            
           
            # 策略二：2-Way 二元對沖套利 (Team + Not Team)
            
            outcomes_2way_pairs = [
                (home_team, f"Not {home_team}"),
                (away_team, f"Not {away_team}"),
                ("Draw", "Not Draw")
            ]
            # 扁平化所有需要的選項名稱，一次性抓取
            all_required_outcomes = outcomes_3way + [pair[1] for pair in outcomes_2way_pairs]
            
            # 儲存所有抓到的報價 (格式: platform -> outcome -> OrderLevel)
            fetched_data = {}

            # 1. 抓取資料 (Data Fetching Phase)
            for event in events:
                platform = event.platform
                api = api_clients.get(platform)
                if not api: continue
                    
                fetched_data[platform] = {}
                token_mapping = event.raw_data.get("token_mapping", {})
                
                for outcome in all_required_outcomes:
                    token_id = token_mapping.get(outcome)
                    if not token_id: continue 
                        
                    try:
                        
                        ob = api.get_orderbook(token_id, outcome)
                        
                     
                        if ob and ob.best_ask:
                            fetched_data[platform][outcome] = ob.best_ask
                            
                            # 同步更新 3-Way 的全網最低價
                            if outcome in outcomes_3way:
                                if ob.best_ask.price < best_prices_3way[outcome]["price"]:
                                    best_prices_3way[outcome] = {
                                        "price": ob.best_ask.price,
                                        "platform": platform,
                                        "size": ob.best_ask.size
                                    }
                    except Exception as e:
                        pass # 靜默跳過失敗的請求

            # 2. 計算 3-Way 套利 (Calculation Phase - 3-Way)
            if all(best_prices_3way[o]["price"] != float('inf') for o in outcomes_3way):
                total_prob_3way = sum(best_prices_3way[o]["price"] for o in outcomes_3way)
                
                if total_prob_3way < 1.0:
                    roi = (1.0 / total_prob_3way - 1) * 100
                    if roi > self.min_roi_threshold:
                        # 估算最大可吃單量 (取各選項深度的最小值)
                        max_size = min(best_prices_3way[o]["size"] for o in outcomes_3way)
                        opportunities.append({
                            "type": "3-Way",
                            "cluster_id": cluster_id,
                            "match": f"{home_team} vs {away_team}",
                            "roi": roi,
                            "total_prob": total_prob_3way,
                            "max_size": max_size,
                            "legs": best_prices_3way
                        })

            # 3. 計算 2-Way 套利 (Calculation Phase - 2-Way)
            # 遍歷每一對 (例如 Arsenal 和 Not Arsenal)
            for yes_out, not_out in outcomes_2way_pairs:
                best_yes = {"price": float('inf'), "platform": None, "size": 0}
                best_not = {"price": float('inf'), "platform": None, "size": 0}
                
                # 找出全網最便宜的 Yes 和全網最便宜的 Not
                for platform, outcomes_dict in fetched_data.items():
                    if yes_out in outcomes_dict and outcomes_dict[yes_out].price < best_yes["price"]:
                        best_yes = {"price": outcomes_dict[yes_out].price, "platform": platform, "size": outcomes_dict[yes_out].size}
                        
                    if not_out in outcomes_dict and outcomes_dict[not_out].price < best_not["price"]:
                        best_not = {"price": outcomes_dict[not_out].price, "platform": platform, "size": outcomes_dict[not_out].size}
                
                # 必須兩個都有報價，而且不能在同一個平台上對沖 (同平台對沖無意義且浪費手續費)
                if best_yes["price"] != float('inf') and best_not["price"] != float('inf'):
                    if best_yes["platform"] != best_not["platform"]:
                        total_prob_2way = best_yes["price"] + best_not["price"]
                        
                        if total_prob_2way < 1.0:
                            roi = (1.0 / total_prob_2way - 1) * 100
                            if roi > self.min_roi_threshold:
                                max_size = min(best_yes["size"], best_not["size"])
                                opportunities.append({
                                    "type": f"2-Way ({yes_out})",
                                    "cluster_id": cluster_id,
                                    "match": f"{home_team} vs {away_team}",
                                    "roi": roi,
                                    "total_prob": total_prob_2way,
                                    "max_size": max_size,
                                    "legs": {
                                        yes_out: best_yes,
                                        not_out: best_not
                                    }
                                })

        # 最終按照 ROI 由高到低排序所有機會
        opportunities.sort(key=lambda x: x["roi"], reverse=True)
        return opportunities