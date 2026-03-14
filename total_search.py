import json
import csv 
from collections import defaultdict
from rapidfuzz import fuzz 

from core_matching import TeamNameMapper
from platforms import (
    SXBetFetcher, SXBetNormalizer,
    PolymarketFetcher, PolymarketNormalizer,
    LimitlessFetcher, LimitlessNormalizer
)


def calculate_custom_similarity(id1: str, id2: str) -> float:
    # 快速通關：如果一模一樣，直接 100 分不用算
    if id1 == id2:
        return 100.0
        
    # 安全機制：確保字串夠長，避免切片報錯
    if len(id1) < 11 or len(id2) < 11:
        return 0.0

    date1 = id1[-10:]
    date2 = id2[-10:]
    
    # 權重規則 1：時間不同，直接歸 0！ (Blocking)
    if date1 != date2:
        return 0.0
        
    teams1 = id1[:-11].replace("_", " ") 
    teams2 = id2[:-11].replace("_", " ") 
    
    # 權重規則 2：名字有重疊加分！ 
    score = fuzz.token_set_ratio(teams1, teams2)
    return score

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

      
        print("\n" + "="*60)
        print("  第二階段：啟動 AI 模糊配對引擎 (相似度 >= 80 分)")
        print("="*60)
        
        matches_db = {} # 這裡不再用 defaultdict，改用普通的 dict

        for event in all_events:
            placed = False
            # 掃描目前已經建立的「抽屜」(代表性的 match_id)
            for existing_id in matches_db.keys():
                score = calculate_custom_similarity(event.match_id, existing_id)
                
                # 如果相似度大於等於 80，判定為同一場比賽！
                if score >= 80.0:
                    matches_db[existing_id].append(event)
                    placed = True
                    break # 找到家了，換下一個 event
            
            # 如果桌上的抽屜都不像 (都沒有 >= 80 分的)，就幫它開一個新抽屜
            if not placed:
                matches_db[event.match_id] = [event]

        
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
                    "original_match_id": e.match_id, # 加一個欄位讓你知道它原本的 ID 長怎樣
                    "platform_event_id": e.platform_event_id
                })

        with open("matches_db_debug.json", "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=4, ensure_ascii=False)
        print(" 已經將分組後的完整資料儲存為 matches_db_debug.json！")

        # 過濾出 2 個平台以上的交集
        overlapping_matches = []
        for match_id, events in matches_db.items():
            platforms_present = set(e.platform for e in events)
            if len(platforms_present) >= 2:
                overlapping_matches.append((match_id, events))

        # 寫入 CSV
        csv_filename = "overlapping_matches.csv"
        csv_records = []
        for match_id, events in overlapping_matches:
            for e in events:
                csv_records.append({
                    "Cluster_ID": match_id, # 這是群組代表的 ID
                    "Original_ID": e.match_id, # 這是它本來自己的 ID
                    "Platform": e.platform,
                    "Market_Type": e.market_type,
                    "Home_Team": e.home_team,
                    "Away_Team": e.away_team,
                    "Start_Time": e.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "Market_Name": e.market_name,
                    "Platform_Event_ID": e.platform_event_id
                })

        if csv_records:
            fieldnames = csv_records[0].keys()
            with open(csv_filename, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_records)
            print(f"  已將 {len(overlapping_matches)} 場交集比賽 存為 {csv_filename}！")
        else:
            print("\n 目前連 2 個平台以上同時開盤的比賽都沒找到。")

        # 輸出終端機報表
        if overlapping_matches:
            print(f"\n 找到 {len(overlapping_matches)} 場有交集的比賽：\n")
            for match_id, events in overlapping_matches:
                sample_event = events[0]
                plats_str = ", ".join(list(set(e.platform for e in events)))
                
                print(f" {sample_event.home_team} vs {sample_event.away_team} ({plats_str})")
                print(f"   代表配對 ID: {match_id}")
                for e in events:
                    # 順便印出它原本的名字，讓你感受一下演算法的神奇！
                    print(f"    - [{e.platform}] ({e.match_id}) | 盤口名: {e.market_name[:30]}")
                print("-" * 50)



if __name__ == "__main__":
    search_engine = TotalSearch()

    search_engine.register_platform("SX Bet", SXBetFetcher, SXBetNormalizer)
    search_engine.register_platform("Polymarket", PolymarketFetcher, PolymarketNormalizer)
    search_engine.register_platform("Limitless", LimitlessFetcher, LimitlessNormalizer)

    search_engine.execute_search()