import requests
from datetime import datetime, timezone
from typing import List, Dict
from core_matching import StandardEvent, BasePlatformNormalizer, TeamNameMapper
import time
# ==========================================
# 1. 數據收集器 (Data Fetcher) - Polymarket
# ==========================================
class PolymarketFetcher:
    """專門負責與 Polymarket API 溝通，獲取原始資料並執行標籤過濾 (支援自動翻頁)"""
    def __init__(self):
        self.api_url = "https://gamma-api.polymarket.com/events"
        self.required_tag_ids = {"1", "100639", "100350"}
        
        # 為了安全起見，我們每次抓 100 筆，然後一頁一頁翻
        self.limit_per_page = 500

    def fetch_soccer_games(self) -> List[Dict]:
        """執行 API 請求並回傳符合標籤條件的賽事 (自動翻頁抓取全部)"""
        print("\n[Polymarket] 開始使用 `offset` 參數自動翻頁抓取資料...")
        
        found_events = []
        offset = 0
        page_count = 1
        
        try:
            while True:
                # 每次請求加上 offset (0, 100, 200, 300...)
                params = {
                    "active": "true",
                    "closed": "false",
                    "tag_id": "100350", 
                    "limit": self.limit_per_page,
                    "offset": offset
                }
                
                print(f"[Polymarket] 正在抓取第 {page_count} 頁 (Offset: {offset})...")
                response = requests.get(self.api_url, params=params, timeout=10)
                response.raise_for_status()
                events = response.json()
                
                # 如果這頁是空的，代表全部抓完了
                if not events:
                    print("[Polymarket] 這一頁為空，抓取完畢！")
                    break
                
                # 過濾這 100 筆資料中符合我們標籤的賽事
                for event in events:
                    event_tag_ids = set()
                    for tag in event.get('tags', []):
                        if isinstance(tag, dict):
                            event_tag_ids.add(str(tag.get('id')))
                    
                    if self.required_tag_ids.issubset(event_tag_ids):
                        found_events.append(event)
                
                # 如果 API 回傳的數量小於我們要求的 limit，代表這是最後一頁了
                if len(events) < self.limit_per_page:
                    print("[Polymarket] 已經到達最後一頁，抓取完畢！")
                    break
                
                # 準備抓下一頁
                offset += self.limit_per_page
                page_count += 1
                
                # 保護 API 不被鎖，稍微暫停
                time.sleep(0.3)
                
            print(f"\n[Polymarket] 成功獲取 {len(found_events)} 場符合標籤的賽事！")
            return found_events
            
        except requests.exceptions.RequestException as e:
            print(f"[Polymarket] API 請求失敗: {e}")
            return found_events


# ==========================================
# 2. 平台轉換器 (Platform Normalizer) - Polymarket
# ==========================================
class PolymarketNormalizer(BasePlatformNormalizer):
    """負責將 Polymarket 的原始資料轉換為跨平台標準格式"""
    def __init__(self, name_mapper: TeamNameMapper):
        super().__init__(platform_name="Polymarket", name_mapper=name_mapper)

    def parse_events(self, raw_data_list: List[Dict]) -> List[StandardEvent]:
        standard_events = []
        current_time = datetime.now(timezone.utc)

        for raw_event in raw_data_list:
            try:
                title = raw_event.get("title", "")
                title = title.replace(" vs. ", " vs ")
                title = title.replace(" - More Markets", "") 
                
                if " vs " not in title:
                    continue
                
                parts = title.split(" vs ")
                raw_home = parts[0].strip()
                raw_away = parts[1].strip()
                
                std_home = self.name_mapper.get_standard_name(raw_home)
                std_away = self.name_mapper.get_standard_name(raw_away)
                
                #  專心使用 endDate
                time_str = raw_event.get("endDate")
                if time_str:
                    try:
                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                    except ValueError:
                        continue 
                else:
                    continue 

                

                event = StandardEvent(
                    home_team=std_home,
                    away_team=std_away,
                    start_time=start_time,
                    platform=self.platform_name,
                    platform_event_id=str(raw_event.get("id")),
                    market_type="moneyline",        
                    market_name=raw_event.get("title"), 
                    raw_data=raw_event 
                )
                standard_events.append(event)
                
            except Exception as e:
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