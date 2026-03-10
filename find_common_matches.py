import time
import requests
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

# 匯入我們之前的核心模組
from core_matching import TeamNameMapper, StandardEvent, BasePlatformNormalizer
# 匯入你寫好的 SX Bet 和 Polymarket 模組
from get_full_soccer_game_xs_bet import SXBetFetcher, SXBetNormalizer
from fin_poly_soccer_games import PolymarketFetcher, PolymarketNormalizer


# ==========================================
# 1. Limitless 模組 (根據你原本的翻頁腳本重構)
# ==========================================
class LimitlessFetcher:
    """負責 Limitless 的自動翻頁抓取"""
    def __init__(self):
        self.api_url = "https://api.limitless.exchange/markets/active/49"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

    def fetch_soccer_games(self) -> List[Dict]:
        print("\n[Limitless] 開始獲取足球賽事資料 (支援自動翻頁)...")
        all_markets = []
        limit = 25
        page = 1
        
        try:
            while True:
                response = requests.get(self.api_url, headers=self.headers, params={"limit": limit, "page": page}, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    current_markets = result.get('data', result) if isinstance(result, dict) else result
                    
                    if not current_markets: break
                    all_markets.extend(current_markets)
                    
                    if len(current_markets) < limit: break
                    page += 1
                    time.sleep(0.3)
                else:
                    break
            print(f"[Limitless] 成功抓取 {len(all_markets)} 筆賽事！")
            return all_markets
        except Exception as e:
            print(f"[Limitless] 抓取失敗: {e}")
            return []

class LimitlessNormalizer(BasePlatformNormalizer):
    def __init__(self, name_mapper: TeamNameMapper):
        super().__init__(platform_name="Limitless", name_mapper=name_mapper)

    def parse_events(self, raw_data_list: List[Dict]) -> List[StandardEvent]:
        standard_events = []
        for raw_event in raw_data_list:
            try:
                # Limitless 通常將比賽名稱寫在 title (e.g. "Arsenal vs Chelsea")
                title = raw_event.get("title", "")
                if " vs " not in title: continue
                
                parts = title.split(" vs ")
                raw_home, raw_away = parts[0].strip(), parts[1].strip()
                
                std_home = self.name_mapper.get_standard_name(raw_home)
                std_away = self.name_mapper.get_standard_name(raw_away)
                
                # 假設如果 Limitless 沒有明確時間，我們先以今日日期為基準確保 match_id 能對齊
                # (實務上若 Limitless API 提供 endDate，請替換成真實時間)
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
            except Exception:
                continue
        return standard_events


# ==========================================
# 2. 跨平台匹配引擎 (Cross-Platform Matcher)
# ==========================================
def find_arbitrage_opportunities():
    # 1. 啟動名稱轉換器 (確保你的字典檔裡有最近熱門的球隊)
    mapper = TeamNameMapper()

    # 2. 實例化所有的 Fetcher 和 Normalizer
    sx_fetcher, sx_normalizer = SXBetFetcher(), SXBetNormalizer(mapper)
    poly_fetcher, poly_normalizer = PolymarketFetcher(), PolymarketNormalizer(mapper)
    limit_fetcher, limit_normalizer = LimitlessFetcher(), LimitlessNormalizer(mapper)

    # 3. 抓取並轉換所有平台的資料
    print("=" * 50)
    print(" 第一階段：資料收集與標準化")
    print("=" * 50)
    
    sx_raw = sx_fetcher.fetch_soccer_games()
    sx_std = sx_normalizer.parse_events(sx_raw)

    poly_raw = poly_fetcher.fetch_soccer_games()
    poly_std = poly_normalizer.parse_events(poly_raw)

    limit_raw = limit_fetcher.fetch_soccer_games()
    limit_std = limit_normalizer.parse_events(limit_raw)

    # 4. 把所有比賽倒進一個池子裡
    all_events = sx_std + poly_std + limit_std

    # 5. 按照 match_id 進行分組 (Grouping)
    matches_db = defaultdict(list)
    for event in all_events:
        # 將比賽放進對應的 match_id 抽屜裡
        matches_db[event.match_id].append(event)

    # 6. 尋找「三個平台都有」的比賽
    print("\n" + "=" * 50)
    print(" 第二階段：尋找三平台重疊的賽事")
    print("=" * 50)
    
    perfect_matches = []
    
    for match_id, events in matches_db.items():
        # 用 set (集合) 算出這個 match_id 裡包含了幾個「不重複的平台」
        platforms_present = set(e.platform for e in events)
        
        # 如果集合裡有 3 個元素 (代表 SX_Bet, Polymarket, Limitless 都齊了)
        if len(platforms_present) == 3:
            perfect_matches.append((match_id, events))

    # 7. 輸出結果
    if not perfect_matches:
        print("\n 糟糕，目前沒有找到三個平台同時開盤且名稱對得上的比賽。")
        print(" 提示：可能是字典檔 (TeamNameMapper) 裡沒有建立它們別名的對應喔！")
    else:
        print(f"\n恭喜！找到了 {len(perfect_matches)} 場三個平台都有的比賽：\n")
        for match_id, events in perfect_matches:
            # 隨便取其中一場來印出主客場名稱
            sample_event = events[0]
            print(f" {sample_event.home_team} vs {sample_event.away_team}")
            print(f"   配對 ID: {match_id}")
            print("   平台原始 ID 對照:")
            for e in events:
                print(f"    - {e.platform}: ID [{e.platform_event_id}]")
            print("-" * 40)


if __name__ == "__main__":
    find_arbitrage_opportunities()