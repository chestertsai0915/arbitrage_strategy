import requests

def get_events_with_specific_tags():
    url = "https://gamma-api.polymarket.com/events"
    
    # 這是我們規定「必須同時存在」的 4 個 Tag ID
    # 統一使用字串格式，避免 JSON 解析時型別不一致的問題
    required_tag_ids = {"1", "100639", "100350"}
    
    # 為了節省頻寬與時間，我們先讓 API 幫我們挑出含有 La Liga (780) 的賽事
    params = {
        "active": "true",
        "closed": "false",
        "tag_id": "100350", 
        "limit": 1000
    }
    
    print(" 正在尋找同時包含 [Sports, Games, Soccer] 這 3 個標籤的賽事...\n")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        events = response.json()
        
        found_events = []
        
        for event in events:
            # 收集這場賽事「身上掛的所有 Tag ID」
            event_tag_ids = set()
            for tag in event.get('tags', []):
                if isinstance(tag, dict):
                    # 將 ID 轉為字串並加入集合中
                    event_tag_ids.add(str(tag.get('id')))
            
            # 核心邏輯：檢查 required_tag_ids 是否為 event_tag_ids 的「子集」
            # 意思是：這 4 個 ID 是不是「全部都在」這場比賽的標籤清單裡？
            if required_tag_ids.issubset(event_tag_ids):
                found_events.append(event)
                
        if not found_events:
            print("目前沒有找到同時完美包含這 4 個標籤的賽事。")
            return
            
        print(f" 總共找到 {len(found_events)} 場符合條件的賽事！\n")
        print("-" * 60)
        
        # 輸出結果，並順便把該賽事的所有標籤印出來當作驗證
        for i, event in enumerate(found_events, 1):
            print(f"{i}.  賽事名稱: {event.get('title')}")
            print(f"   賽事 ID: {event.get('id')}")
            print(f"   網址 Slug: {event.get('slug')}")
            
            # 把這場比賽掛的標籤名稱整理出來，方便我們肉眼檢查
            actual_labels = [t.get('label') for t in event.get('tags', []) if isinstance(t, dict)]
            print(f"   實際掛載的標籤: {', '.join(actual_labels)}")
            print("-" * 60)
            
    except requests.exceptions.RequestException as e:
        print(f"API 請求失敗: {e}")

get_events_with_specific_tags()