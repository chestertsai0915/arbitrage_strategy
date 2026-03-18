
from collections import defaultdict
import time
import json
# 匯入各平台 API
from platforms import AVAILABLE_PLATFORMS

# 匯入核心工具 (依據你的資料夾結構，若放在 utils 請自行更改)

from utils.team_mapping import TeamNameMapper

# 匯入配對引擎
# 假設你已經將兩階段配對邏輯存放在 core/matcher.py 中
from core.matcher import MatchEngine 

def main():  
    print("  Total Search")
    
    # 步驟 1：初始化系統工具與平台
    
    mapper = TeamNameMapper()
    
    # 初始化配對引擎：門檻 70 分，至少需要 2 個平台重疊
    match_engine = MatchEngine(threshold=70.0, min_platforms=2)
    
    # 註冊我們要掃描的平台
    mapper = TeamNameMapper()
    
    # 動態實例化所有在 __init__.py 註冊過的平台！
    platforms = [PlatformClass(mapper) for PlatformClass in AVAILABLE_PLATFORMS]

   
    # 步驟 2：第一階段 - 盤前靜態資料收集
    
    all_events = []
    for api in platforms:
        try:
            events = api.get_matches()
            all_events.extend(events)
        except Exception as e:
            print(f" {api.name} 獲取賽事失敗: {e}")

  
    # 步驟 3：安檢過濾 - 只保留安全的套利標的
   
    # 1. 確保是獨贏盤 (moneyline)
    # 2. 確保我們有成功解析出子盤口的鑰匙 (token_mapping)
    moneyline_events = [
        e for e in all_events 
        if e.market_type == "moneyline" and e.raw_data.get("token_mapping")
    ]
    
    print(f"\n 總計獲取 {len(all_events)} 場比賽。")
    print(f" 過濾後剩下 {len(moneyline_events)} 場高品質 Moneyline (獨贏盤) 賽事準備進行配對。")

    
    # 步驟 4：啟動 AI 配對引擎，尋找 Overlap
   
    overlapping_matches = match_engine.match_events(moneyline_events)

    overlapping_export_data = []
    matched_event_ids = set()

    for cluster in overlapping_matches:
        # 你的結構應該是 (cluster_id, [event1, event2...])
        cluster_id, events_in_cluster = cluster 
        
        cluster_events_dict = []
        for e in events_in_cluster:
            # 紀錄已配對的 ID，等等用來過濾孤立比賽
            matched_event_ids.add(e.platform_event_id)
            
            # 轉換為字典
            cluster_events_dict.append({
                "platform": e.platform,
                "home_team": e.home_team,
                "away_team": e.away_team,
                "start_time": e.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "market_name": e.market_name,
                "platform_event_id": e.platform_event_id,
                "token_mapping": e.raw_data.get("token_mapping", {})
            })
            
        # 將這個交集群組打包
        overlapping_export_data.append({
            "cluster_id": cluster_id,
            "matched_count": len(events_in_cluster),
            "events": cluster_events_dict
        })

    # 將交集比賽存成 JSON
    if overlapping_export_data:
        with open("overlapping_matches.json", "w", encoding="utf-8") as f:
            json.dump(overlapping_export_data, f, ensure_ascii=False, indent=4)
        print(f"\n 成功儲存 {len(overlapping_export_data)} 組交集比賽至 overlapping_matches.json")


    # ==========================================
    # 2. 儲存「無交集」(Unique) 的孤立比賽
    # ==========================================
    # 從總清單中，剔除配對成功的，剩下就是孤立比賽
    unique_events = [e for e in moneyline_events if e.platform_event_id not in matched_event_ids]

    unique_by_platform = defaultdict(list)
    for e in unique_events:
        event_dict = {
            "match_id": e.match_id,
            "home_team": e.home_team,
            "away_team": e.away_team,
            "start_time": e.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "market_name": e.market_name,
            "platform": e.platform,
            "platform_event_id": e.platform_event_id,
            "token_mapping": e.raw_data.get("token_mapping", {})
        }
        unique_by_platform[e.platform].append(event_dict)

    print("\n" + "="*50)
    print("🔍 儲存未產生交集的獨立比賽：")
    for platform, events in unique_by_platform.items():
        filename = f"{platform}_unique.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=4)
        print(f"  - {platform}: {len(events)} 場 -> 已儲存至 {filename}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()