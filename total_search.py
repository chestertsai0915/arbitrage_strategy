from collections import defaultdict
from core_matching import TeamNameMapper
import json
#  優化後的寫法：直接從 platforms 模組包中一次匯入所有需要的類別
from platforms import (
    SXBetFetcher, SXBetNormalizer,
    PolymarketFetcher, PolymarketNormalizer,
    LimitlessFetcher, LimitlessNormalizer
)

class TotalSearch:
    """跨平台套利總管 (Total Search)：負責調度所有平台並尋找交集"""
    def __init__(self):
        self.mapper = TeamNameMapper()
        self.platforms = [] 

    def register_platform(self, name, fetcher_class, normalizer_class):
        """註冊新平台"""
        fetcher_instance = fetcher_class()
        normalizer_instance = normalizer_class(self.mapper)
        
        self.platforms.append({
            "name": name,
            "fetcher": fetcher_instance,
            "normalizer": normalizer_instance
        })
        print(f" 成功註冊平台：{name}")

    def fetch_and_normalize_all(self):
        """總管下令：所有人去抓資料並翻譯成標準格式！"""
        all_events = []
        print("\n" + "="*60)
        print("  第一階段：各平台資料收集與標準化")
        print("="*60)

        for platform in self.platforms:
            name = platform["name"]
            fetcher = platform["fetcher"]
            normalizer = platform["normalizer"]

            raw_data = fetcher.fetch_soccer_games()
            if raw_data:
                std_events = normalizer.parse_events(raw_data)
                all_events.extend(std_events)
            else:
                print(f" [{name}] 沒有抓到任何資料。")

        return all_events

    def execute_search(self):
        """總管下令：執行全網比對 (Total Search)"""
        # 1. 拿回所有標準化後的比賽
        all_events = self.fetch_and_normalize_all()

        # 2. 按照 match_id 分類進抽屜
        matches_db = defaultdict(list)
        for event in all_events:
            matches_db[event.match_id].append(event)

        debug_data = {}
        for match_id, events in matches_db.items():
            debug_data[match_id] = []
            for e in events:
                debug_data[match_id].append({
                    "platform": e.platform,
                    "market_type": e.market_type,
                    "market_name": e.market_name,
                    "home_team": e.home_team,
                    "away_team": e.away_team,
                    "start_time": e.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "platform_event_id": e.platform_event_id
                })

        with open("matches_db_debug.json", "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=4, ensure_ascii=False)
        print("\n [Debug] 已經將分組後的完整資料儲存為 matches_db_debug.json！")

        print("\n" + "="*60)
        print("  第二階段：尋找跨平台交集")
        print("="*60)

        perfect_matches = []
        target_platform_count = len(self.platforms) 

        for match_id, events in matches_db.items():
            platforms_present = set(e.platform for e in events)
            
            if len(platforms_present) == target_platform_count:
                perfect_matches.append((match_id, events))

        # 3. 輸出最終報表
        if not perfect_matches:
            print(f"\n 糟糕，目前沒有找到 {target_platform_count} 個平台同時開盤的比賽。")
        else:
            print(f"\n 恭喜！Total Search 找到了 {len(perfect_matches)} 場交集比賽：\n")
            for match_id, events in perfect_matches:
                sample_event = events[0]
                print(f" {sample_event.home_team} vs {sample_event.away_team}")
                print(f"   配對 ID: {match_id}")
                for e in events:
                    print(f"    - [{e.platform}] 玩法: {e.market_type:<10} | 盤口名: {e.market_name[:30]}")
                print("-" * 50)


# ==========================================
#  啟動 Total Search (主程式)
# ==========================================
if __name__ == "__main__":
    # 1. 建立總管
    search_engine = TotalSearch()

    # 2. 註冊平台
    search_engine.register_platform("SX Bet", SXBetFetcher, SXBetNormalizer)
    search_engine.register_platform("Polymarket", PolymarketFetcher, PolymarketNormalizer)
    search_engine.register_platform("Limitless", LimitlessFetcher, LimitlessNormalizer)

    # 3. 執行全網比對
    search_engine.execute_search()