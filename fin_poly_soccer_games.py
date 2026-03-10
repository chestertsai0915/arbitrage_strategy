import requests
from datetime import datetime
from typing import List, Dict
from core_matching import StandardEvent, BasePlatformNormalizer, TeamNameMapper

# ==========================================
# 1. 數據收集器 (Data Fetcher) - Polymarket
# ==========================================
class PolymarketFetcher:
    """專門負責與 Polymarket API 溝通，獲取原始資料並執行標籤過濾"""
    def __init__(self):
        self.api_url = "https://gamma-api.polymarket.com/events"
        self.required_tag_ids = {"1", "100639", "100350"}
        self.params = {
            "active": "true",
            "closed": "false",
            "tag_id": "100350", 
            "limit": 1000
        }

    def fetch_soccer_games(self) -> List[Dict]:
        """執行 API 請求並回傳符合標籤條件的賽事"""
        print("[Polymarket] 開始獲取足球賽事資料...")
        try:
            response = requests.get(self.api_url, params=self.params, timeout=10)
            response.raise_for_status()
            events = response.json()
            
            found_events = []
            for event in events:
                event_tag_ids = set()
                for tag in event.get('tags', []):
                    if isinstance(tag, dict):
                        event_tag_ids.add(str(tag.get('id')))
                
                # 檢查標籤是否完全符合
                if self.required_tag_ids.issubset(event_tag_ids):
                    found_events.append(event)
                    
            print(f"[Polymarket] 成功獲取 {len(found_events)} 場符合標籤的賽事！")
            return found_events
            
        except requests.exceptions.RequestException as e:
            print(f"[Polymarket] API 請求失敗: {e}")
            return []


# ==========================================
# 2. 平台轉換器 (Platform Normalizer) - Polymarket
# ==========================================
class PolymarketNormalizer(BasePlatformNormalizer):
    """負責將 Polymarket 的原始資料轉換為跨平台標準格式"""
    def __init__(self, name_mapper: TeamNameMapper):
        super().__init__(platform_name="Polymarket", name_mapper=name_mapper)

    def parse_events(self, raw_data_list: List[Dict]) -> List[StandardEvent]:
        standard_events = []
        for raw_event in raw_data_list:
            try:
                title = raw_event.get("title", "")
                
                # 1. 處理標題裡的 "vs." (多了一個點的狀況)
                title = title.replace(" vs. ", " vs ")
                
                if " vs " not in title:
                    continue
                
                # 2. 拆解主客隊
                parts = title.split(" vs ")
                raw_home = parts[0].strip()
                raw_away = parts[1].strip()
                
                # 3. 名稱標準化 (剛才就是漏了這兩行！)
                std_home = self.name_mapper.get_standard_name(raw_home)
                std_away = self.name_mapper.get_standard_name(raw_away)
                
                # 4. 時間處理
                time_str = raw_event.get("startDate") or raw_event.get("endDate")
                if time_str:
                    try:
                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                    except ValueError:
                        start_time = datetime.now()
                else:
                    start_time = datetime.now()

                event = StandardEvent(
                    home_team=std_home,
                    away_team=std_away,
                    start_time=start_time,
                    platform=self.platform_name,
                    platform_event_id=str(raw_event.get("id")),
                    raw_data=raw_event 
                )
                standard_events.append(event)
                
            except Exception as e:
                print(f"[Polymarket] 解析單筆賽事失敗: {e}, 標題: {raw_event.get('title')}")
                continue
                
        return standard_events

# ==========================================
# 3. 執行測試區塊
# ==========================================
if __name__ == "__main__":
    # 1. 建立名稱字典引擎 (來自 core_matching.py)
    mapper = TeamNameMapper()
    
    # 2. 實例化 Fetcher 與 Normalizer
    poly_fetcher = PolymarketFetcher()
    poly_normalizer = PolymarketNormalizer(mapper)
    
    # 3. 獲取並標準化資料
    raw_poly_games = poly_fetcher.fetch_soccer_games()
    
    if raw_poly_games:
        std_poly_games = poly_normalizer.parse_events(raw_poly_games)
        
        # 4. 印出前三筆標準化結果來驗證
        print("\n--- Polymarket 標準化結果展示 (前 3 筆) ---")
        for game in std_poly_games[:3]:
            print(f"[{game.platform}] {game.home_team} vs {game.away_team}")
            print(f"原始標題: {game.raw_data.get('title')}")
            print(f"開賽時間: {game.start_time}")
            print(f"全局匹配ID: {game.match_id}")
            print("-" * 30)