import requests
import time
from datetime import datetime
from typing import List, Dict

# 引入核心架構
from core_matching import StandardEvent, BasePlatformNormalizer, TeamNameMapper

# ==========================================
# 1. 數據收集器 (Data Fetcher) - SX Bet
# ==========================================
class SXBetFetcher:
    """專門負責與 SX Bet API 溝通，獲取原始資料 (包含分頁邏輯)"""
    def __init__(self):
        self.base_url = "https://api.sx.bet"
        self.endpoint = f"{self.base_url}/markets/active"
        self.headers = {"Accept": "application/json"}

    def fetch_soccer_games(self) -> List[Dict]:
        print("\n[SX Bet] 開始獲取足球賽事資料 (支援自動分頁)...")
        all_soccer_markets = []
        next_key = None
        page_count = 1

        while True:
            params = {
                "sportIds": 5, 
                "onlyMainLine": "true",
                "pageSize": 50
            }
            
            if next_key:
                params["paginationKey"] = next_key
                
            try:
                response = requests.get(self.endpoint, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    data = result.get('data', {})
                    
                    # 抓出這一頁的比賽陣列
                    current_page_markets = data.get('markets', [])
                    all_soccer_markets.extend(current_page_markets)
                    
                    # 處理下一頁
                    next_key = data.get('nextKey')
                    if not next_key:
                        break
                    
                    page_count += 1
                    time.sleep(0.5) # 遵守速率限制
                    
                else:
                    print(f"[SX Bet] 第 {page_count} 頁請求失敗，狀態碼: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"[SX Bet] 發生錯誤: {e}")
                break

        print(f"[SX Bet] 成功獲取 {len(all_soccer_markets)} 場原始賽事資料！")
        return all_soccer_markets


# ==========================================
# 2. 平台轉換器 (Platform Normalizer) - SX Bet
# ==========================================
class SXBetNormalizer(BasePlatformNormalizer):
    """負責將 SX Bet 的原始資料轉換為跨平台標準格式"""
    def __init__(self, name_mapper: TeamNameMapper):
        super().__init__(platform_name="SX_Bet", name_mapper=name_mapper)

    def parse_events(self, raw_data_list: List[Dict]) -> List[StandardEvent]:
        standard_events = []
        for raw_event in raw_data_list:
            try:
                raw_home = raw_event.get("outcomeOneName", "")
                raw_away = raw_event.get("outcomeTwoName", "")
                
                if not raw_home or not raw_away:
                    continue
                
                # 名稱標準化
                std_home = self.name_mapper.get_standard_name(raw_home)
                std_away = self.name_mapper.get_standard_name(raw_away)
                
                # 時間解析 (修正 Timestamp 錯誤)
                time_str = raw_event.get("gameTime")
                if time_str:
                    try:
                        # 嘗試當作 Timestamp (整數數字) 來解析
                        start_time = datetime.fromtimestamp(int(time_str))
                    except ValueError:
                        # 萬一它又給了 ISO 字串，我們有備用方案
                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                else:
                    start_time = datetime.now()

                event = StandardEvent(
                    home_team=std_home,
                    away_team=std_away,
                    start_time=start_time,
                    platform=self.platform_name,
                    platform_event_id=str(raw_event.get("marketHash")),
                    raw_data=raw_event 
                )
                standard_events.append(event)
                
            except Exception as e:
                # 這裡印出錯誤，幫助我們繼續除錯
                print(f"[SX Bet] 解析單筆賽事失敗: {e}")
                continue
                
        return standard_events


# ==========================================
# 3. 執行測試區塊
# ==========================================
if __name__ == "__main__":
    mapper = TeamNameMapper()
    
    sx_fetcher = SXBetFetcher()
    sx_normalizer = SXBetNormalizer(mapper)
    
    raw_games = sx_fetcher.fetch_soccer_games()
    
    if raw_games:
        std_games = sx_normalizer.parse_events(raw_games)
        
        print("\n--- SX Bet 標準化結果展示 (前 3 筆) ---")
        for game in std_games[:3]:
            print(f"[{game.platform}] {game.home_team} vs {game.away_team}")
            print(f"原始 Market Hash: {game.platform_event_id}")
            print(f"全局匹配ID: {game.match_id}")
            print("-" * 30)