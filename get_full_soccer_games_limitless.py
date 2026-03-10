import requests
import time
from datetime import datetime
from typing import List, Dict

from core_matching import StandardEvent, BasePlatformNormalizer, TeamNameMapper

# ==========================================
# 1. 數據收集器 (Data Fetcher) - Limitless
# ==========================================
class LimitlessFetcher:
    """專門負責與 Limitless API 溝通，獲取原始資料 (包含自動翻頁)"""
    def __init__(self):
        # 填入正確的 API URL
        self.api_url = "https://api.limitless.exchange/markets/active/49"
        
        # 加上你原本的 User-Agent 避免被擋
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_soccer_games(self) -> List[Dict]:
        """執行 API 請求並回傳原始賽事列表 (自動翻頁抓取全部)"""
        print("\n[Limitless] 開始使用 `page` 參數自動翻頁抓取賽事資料...")
        
        all_markets = []
        limit = 25
        page = 1
        
        try:
            while True:
                params = {
                    "limit": limit,
                    "page": page
                }
                
                print(f"[Limitless] 正在抓取第 {page} 頁...")
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    current_markets = result.get('data', result) if isinstance(result, dict) else result
                    
                    # 如果這一頁沒有資料，代表已經抓完了
                    if not current_markets:
                        print("[Limitless] 這一頁為空，抓取完畢！")
                        break
                    
                    all_markets.extend(current_markets)
                    print(f"    成功抓到 {len(current_markets)} 筆資料。")
                    
                    # 如果這頁拿到的資料小於 limit，代表這是最後一頁了
                    if len(current_markets) < limit:
                        print("[Limitless] 已經到達最後一頁，抓取完畢！")
                        break
                    
                    # 準備抓下一頁
                    page += 1
                    
                    # 遵守速率限制，暫停 0.3 秒
                    time.sleep(0.3)
                    
                else:
                    print(f"[Limitless] 第 {page} 頁請求失敗，狀態碼: {response.status_code}")
                    print(f"錯誤訊息: {response.text}")
                    break
                    
        except Exception as e:
            print(f"[Limitless] 發生錯誤: {e}")

        print(f"\n[Limitless] 大功告成！全站總共抓取到 {len(all_markets)} 場足球比賽原始資料。")
        return all_markets


# ==========================================
# 2. 平台轉換器 (Platform Normalizer) - Limitless
# ==========================================
class LimitlessNormalizer(BasePlatformNormalizer):
    """負責將 Limitless 的原始資料轉換為跨平台標準格式 (StandardEvent)"""
    def __init__(self, name_mapper: TeamNameMapper):
        super().__init__(platform_name="Limitless", name_mapper=name_mapper)

    def parse_events(self, raw_data_list: List[Dict]) -> List[StandardEvent]:
        standard_events = []
        for raw_event in raw_data_list:
            try:
                # Limitless 通常將比賽名稱寫在 title (e.g. "Arsenal vs Chelsea")
                title = raw_event.get("title", "")

                # 1. 找出包含 "vs" 的區段
                # 例如: ["⚽ UEL", " Panathinaikos vs Real Betis", " Mar 12", " 2026"]
                match_segment = ""
                for segment in title.split(","):
                    if "vs" in segment.lower(): # 找裡面有 vs 的那一段
                        match_segment = segment
                        break

                if not match_segment:
                    continue # 如果整串標題都沒有 vs，就跳過

                # 2. 把那一段拿來切割主客隊
                # " Panathinaikos vs Real Betis" -> "Panathinaikos" 和 "Real Betis"
                # 一樣先處理一下萬一有 "vs." 的情況
                match_segment = match_segment.replace(" vs. ", " vs ")
                parts = match_segment.split(" vs ")

                if len(parts) == 2:
                    raw_home = parts[0].strip()
                    raw_away = parts[1].strip()
                else:
                    continue
                
                # 透過字典引擎標準化名稱
                std_home = self.name_mapper.get_standard_name(raw_home)
                std_away = self.name_mapper.get_standard_name(raw_away)
                
                # Limitless 時間處理
                time_str = raw_event.get("endDate") or raw_event.get("createdAt") 
                if time_str:
                    # 嘗試轉換 ISO 時間，若格式不符則捕捉例外
                    try:
                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                    except ValueError:
                        start_time = datetime.now()
                else:
                    start_time = datetime.now()

                # 建立標準化物件
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
                # print(f"[Limitless] 解析單筆賽事失敗: {e}")
                continue
                
        return standard_events


# ==========================================
# 3. 執行測試區塊
# ==========================================
if __name__ == "__main__":
    mapper = TeamNameMapper()
    
    limitless_fetcher = LimitlessFetcher()
    limitless_normalizer = LimitlessNormalizer(mapper)
    
    raw_limitless_games = limitless_fetcher.fetch_soccer_games()
    
    if raw_limitless_games:
        std_limitless_games = limitless_normalizer.parse_events(raw_limitless_games)
        
        print("\n" + "=" * 50)
        print(f"--- Limitless 標準化結果展示 (共 {len(std_limitless_games)} 筆，顯示前 3 筆) ---")
        for game in std_limitless_games[:3]:
            print(f"[{game.platform}] {game.home_team} vs {game.away_team}")
            print(f"開賽時間: {game.start_time}")
            print(f"全局匹配ID: {game.match_id}")
            print("-" * 30)



