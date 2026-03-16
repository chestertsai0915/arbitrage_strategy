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
    def __init__(self, threshold: float = 70.0, min_platforms: int = 2):
        self.threshold = threshold
        self.min_platforms = min_platforms

    def match_events(self, all_events: List[StandardEvent]) -> List[Tuple[str, List[StandardEvent]]]:
        print("\n" + "="*60)
        print("  啟動兩階段配對引擎")
        print("="*60)
        

        exact_db: Dict[str, List[StandardEvent]] = defaultdict(list)
        for event in all_events:
            exact_db[event.match_id].append(event)
            


     
        # 第二階段：模糊合併 (Fuzzy Merge) 優化版
        final_db: Dict[str, List[StandardEvent]] = {}

        # 優化 1：先按「日期」進行分群 (分桶)
        # 這樣就不用拿不同日期的比賽互相比對，大幅降低 O(N^2) 的迴圈次數
        date_partitions = defaultdict(dict)
        for exact_id, grouped_events in exact_db.items():
            # 取出最後 10 個字元作為日期 (例如 '2024-03-15')
            date_str = exact_id[-10:] 
            date_partitions[date_str][exact_id] = grouped_events

        # 優化 2：只在「同一天」的比賽中互相比對
        for date_str, exact_group in date_partitions.items():
            daily_final_db = {} # 用來存這一天已經確認的代表抽屜
            
            for exact_id, events in exact_group.items():
                best_match_id = None
                best_score = 0.0
                
                # 優化 3：尋找「分數最高」的配對，而不是「第一個及格」的就塞進去
                for final_id in daily_final_db.keys():
                    score = calculate_custom_similarity(exact_id, final_id)
                    
                    if score >= self.threshold and score > best_score:
                        best_score = score
                        best_match_id = final_id
                        
                        # 小優化：如果遇到 100 分 (完全一模一樣)，那不用找了，直接確定
                        if score == 100.0:
                            break 
                
                # 判斷歸屬
                if best_match_id:
                    # 找到最適合的抽屜，把整包比賽倒進去
                    daily_final_db[best_match_id].extend(events)
                else:
                    # 分數都不及格，自己開一個新抽屜
                    daily_final_db[exact_id] = events
            
            # 將這天的處理結果合併回總表
            final_db.update(daily_final_db)
       
        # 三過濾與輸出
        
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