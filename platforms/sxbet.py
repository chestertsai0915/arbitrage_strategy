import requests
import time
from datetime import datetime, timezone
from typing import List

# 確保你的 models 與 utils 路徑正確
from models.match import StandardEvent
from models.orderbook import Orderbook, OrderLevel
from utils.team_mapping import TeamNameMapper

class SXBetAPI:
    """SX Bet 平台標準化介面"""
    
    def __init__(self, name_mapper: TeamNameMapper):
        self.name = "SX_Bet"
        self.mapper = name_mapper
        
        # API 網址與設定
        self.base_url = "https://api.sx.bet"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})

  
    # 1. 獲取賽事
 
    def get_matches(self) -> List[StandardEvent]:
        print(f"\n[{self.name}] 開始獲取足球賽事資料 (支援自動分頁並聚合盤口)...")
        
        # 用字典來將同一場比賽的不同盤口「合併」起來
        matches_db = {} 
        
        next_key = None
        page_count = 1
        current_time = datetime.now(timezone.utc)

        while True:
            params = {
                "sportIds": 5, 
                "onlyMainLine": "true",
                "pageSize": 50
            }
            if next_key:
                params["paginationKey"] = next_key
                
            try:
                print(f"[{self.name}] 正在抓取第 {page_count} 頁...")
                response = self.session.get(f"{self.base_url}/markets/active", params=params, timeout=10)
                response.raise_for_status()
                data = response.json().get('data', {})
                
                markets = data.get('markets', [])
                if not markets:
                    break

                for raw_event in markets:
                    try:
                        # 1. 名稱與時間解析
                        raw_home = raw_event.get("teamOneName", "")
                        raw_away = raw_event.get("teamTwoName", "")
                        if not raw_home or not raw_away:
                            continue
                            
                        std_home = self.mapper.get_standard_name(raw_home)
                        std_away = self.mapper.get_standard_name(raw_away)
                        
                        time_str = raw_event.get("gameTime")
                        if not time_str: continue
                        
                        start_time = datetime.fromtimestamp(int(time_str), tz=timezone.utc)
                        if start_time < current_time: continue 
                            
                        # 2. 建立比賽專屬 ID (用來把同場比賽的盤口裝進同一個抽屜)
                        match_id = f"{std_home}_{std_away}_{start_time.strftime('%Y-%m-%d')}"
                        
                        # 如果這場比賽還沒建立過，先幫它開一個乾淨的 StandardEvent
                        if match_id not in matches_db:
                            matches_db[match_id] = StandardEvent(
                                home_team=std_home,
                                away_team=std_away,
                                start_time=start_time,
                                platform=self.name,
                                platform_event_id=match_id, # 這裡用 match_id 當代表
                                market_type="moneyline",   
                                market_name=f"{raw_home} vs {raw_away}", 
                                raw_data={
                                    "token_mapping": {} # 準備拿來裝 Home, Away, Draw Hash
                                } 
                            )
                            
                        # 3. 判斷這是什麼盤口，並塞進 token_mapping
                        out1 = raw_event.get("outcomeOneName", "")
                        out2 = raw_event.get("outcomeTwoName", "")
                        m_hash = raw_event.get("marketHash")
                        std_out1 = self.mapper.get_standard_name(out1)
                        
                        # 🌟 [核心修改] 統一使用 Home, Away, Draw 標籤
                        # SX Bet 獨贏盤(Moneyline)最大的特徵：選項二一定是 "Not xxx"
                        if "Not " in out2 or "not " in out2.lower():
                            if std_out1 == std_home or std_out1 in std_home or std_home in std_out1:
                                matches_db[match_id].raw_data["token_mapping"]["Home"] = m_hash
                                matches_db[match_id].raw_data["token_mapping"]["Not Home"] = m_hash
                            elif std_out1 == std_away or std_out1 in std_away or std_away in std_out1:
                                matches_db[match_id].raw_data["token_mapping"]["Away"] = m_hash
                                matches_db[match_id].raw_data["token_mapping"]["Not Away"] = m_hash
                            elif "tie" in out1.lower() or "draw" in out1.lower():
                                matches_db[match_id].raw_data["token_mapping"]["Draw"] = m_hash
                                matches_db[match_id].raw_data["token_mapping"]["Not Draw"] = m_hash
                                
                    except Exception as e:
                        continue

                next_key = data.get('nextKey')
                if not next_key:
                    break
                    
                page_count += 1
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"[{self.name}] 抓取失敗: {e}")
                break

        # 4. 最後把字典轉回 List，並過濾掉沒有抓到 Moneyline 盤口的比賽
        standard_events = [
            event for event in matches_db.values() 
            if len(event.raw_data["token_mapping"]) > 0
        ]
        
        print(f"[{self.name}] 成功合併出 {len(standard_events)} 場標準化賽事！")
        return standard_events


  
    # 2. 獲取訂單簿
  
    def get_orderbook(self, market_id: str, selection: str) -> Orderbook:
        """
        market_id: SX Bet 的 marketHash
        selection: 來自引擎的查詢字串，例如 "Home" 或 "Not Home"
        """
        try:
            time.sleep(0.5)
            params = {"marketHashes": market_id}
            response = self.session.get(f"{self.base_url}/orders", params=params, timeout=10)
            response.raise_for_status()
            orders = response.json().get("data", [])
            
            asks = []
            
            # 透過 selection 判斷是否為 Not 盤口
            is_not_market = selection.startswith("Not ")
            
            for order in orders:
                total_bet_size = float(order.get("totalBetSize", 0))
                fill_amount = float(order.get("fillAmount", 0))
                remaining_raw = total_bet_size - fill_amount
                
                if remaining_raw <= 0:
                    continue 
                    
                remaining_maker_usdc = remaining_raw / (10**6)
                percentage_odds_raw = float(order.get("percentageOdds", 0))
                maker_implied_prob = percentage_odds_raw / (10**20)  
                taker_implied_prob = 1 - maker_implied_prob          
                
                if maker_implied_prob <= 0 or taker_implied_prob <= 0:
                    continue
                    
                taker_size = remaining_maker_usdc * (taker_implied_prob / maker_implied_prob)
                is_maker_outcome_one = order.get("isMakerBettingOutcomeOne", False)
                
                # --- 🎯 動態分配邏輯 ---
                if not is_not_market:
                    # 一般情況 (想買隊伍本身 = Outcome 1)，我們要找押注 Outcome 2 的 Maker 對賭
                    if not is_maker_outcome_one:
                        asks.append(OrderLevel(price=taker_implied_prob, size=taker_size))
                else:
                    # Not 情況 (想買 Not 隊伍 = Outcome 2)，我們要找押注 Outcome 1 的 Maker 對賭
                    if is_maker_outcome_one:
                        asks.append(OrderLevel(price=taker_implied_prob, size=taker_size))

            # 建立模型 (模型內的 __post_init__ 會自動幫你把 Asks 依照價格由低到高排好！)
            return Orderbook(
                platform=self.name,
                match_id="tbd", 
                market_id=market_id,
                selection=selection,
                asks=asks  # 專注於 Asks (我們的買入成本)
            )
            
        except Exception as e:
            print(f"[{self.name}] 獲取 Orderbook 失敗 (Hash: {market_id[:8]}...): {e}")
            return Orderbook(platform=self.name, match_id="error", market_id=market_id, selection=selection)