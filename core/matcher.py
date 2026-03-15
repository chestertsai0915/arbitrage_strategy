# core/matcher.py
from typing import List, Dict, Tuple
from collections import defaultdict
from rapidfuzz import fuzz 
from models.match import StandardEvent

def calculate_custom_similarity(id1: str, id2: str) -> float:
    """計算兩個 match_id 的相似度 (不再需要判斷 id1 == id2，因為交給第一階段處理了)"""
    if len(id1) < 11 or len(id2) < 11:
        return 0.0

    date1 = id1[-10:]
    date2 = id2[-10:]
    
    # 權重規則 1：時間不同，直接歸 0
    if date1 != date2:
        return 0.0
        
    teams1 = id1[:-11].replace("_", " ") 
    teams2 = id2[:-11].replace("_", " ") 
    
    # 權重規則 2：名字重疊加分
    return fuzz.token_set_ratio(teams1, teams2)


class MatchEngine:
    def __init__(self, threshold: float = 80.0, min_platforms: int = 2):
        self.threshold = threshold
        self.min_platforms = min_platforms

    def match_events(self, all_events: List[StandardEvent]) -> List[Tuple[str, List[StandardEvent]]]:
        print("\n" + "="*60)
        print("  啟動兩階段配對引擎")
        print("="*60)
        

        exact_db: Dict[str, List[StandardEvent]] = defaultdict(list)
        for event in all_events:
            exact_db[event.match_id].append(event)
            


     
        # 第二階段：模糊合併 (Fuzzy Merge)
    
        final_db: Dict[str, List[StandardEvent]] = {}

        # 我們直接拿第一階段分好的「代表 ID」來互相比較，不用一筆一筆比了！
        for exact_id, grouped_events in exact_db.items():
            placed = False
            
            for final_id in final_db.keys():
                score = calculate_custom_similarity(exact_id, final_id)
                
                if score >= self.threshold:
                    # 相似度夠高，把整包比賽倒進現有的抽屜裡
                    final_db[final_id].extend(grouped_events)
                    placed = True
                    break 
            
            if not placed:
                # 找不到相似的，自己開一個新抽屜
                final_db[exact_id] = grouped_events

        # ==========================================
        # 第三階段：過濾與輸出
        # ==========================================
        overlapping_matches = []
        for match_id, events in final_db.items():
            platforms_present = set(e.platform for e in events)
            if len(platforms_present) >= self.min_platforms:
                overlapping_matches.append((match_id, events))

        if not overlapping_matches:
            print(f"\n 目前連 {self.min_platforms} 個平台以上同時開盤的比賽都沒找到。")
        else:
            print(f"  成功配對出 {len(overlapping_matches)} 場交集比賽！")

        return overlapping_matches