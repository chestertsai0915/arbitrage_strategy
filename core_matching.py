from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from abc import ABC, abstractmethod
import re

# ==========================================
# 1. 資料模型 (Data Models)
# ==========================================
@dataclass
class StandardEvent:
    """標準化的比賽資料結構"""
    home_team: str          
    away_team: str          
    start_time: datetime    
    platform: str           
    platform_event_id: str  
    market_type: str        #  [新增] 玩法類型 (例如: "moneyline", "spread", "total")
    market_name: str        #  [新增] 具體的盤口名稱 (例如: "Over 2.5", "Atletico Madrid -1")
    raw_data: dict          

    @property
    def match_id(self) -> str:
        date_str = self.start_time.strftime("%Y-%m-%d")
        return f"{self.home_team}_{self.away_team}_{date_str}"


# ==========================================
# 2. 名稱標準化引擎 (簡化版)
# ==========================================
class TeamNameMapper:
    """處理球隊名稱標準化：一律轉小寫並清理字串"""
    
    def get_standard_name(self, raw_name: str) -> str:
        if not raw_name:
            return "unknown"
            
        # 1. 轉成全部小寫並去除頭尾空白
        clean = raw_name.lower().strip()

        # 🎯 2. [新增] 移除讓分盤的數字尾巴 (例如 " -1", " +1.5", "-0.5")
        # 正則表達式解釋：尋找字串「結尾($)」是否包含「+或-」，加上「數字(可能包含小數點)」
        clean = re.sub(r'\s*[+\-]\d+(\.\d+)?\s*$', '', clean)
        
        # 3. 移除常見的足球隊尾綴雜訊 (例如 fc, cf, afc)
        clean = re.sub(r'\b(fc|cf|afc|united)\b', '', clean).strip()
        
        # 4. 把字串中間的「多個連續空白」或「連字號 -」替換成單一底線
        clean = re.sub(r'[\s\-]+', '_', clean)
        
        return clean


# ==========================================
# 3. 平台轉換器 (Base Normalizer)
# ==========================================
class BasePlatformNormalizer(ABC):
    """所有平台轉換器的父類別"""
    def __init__(self, platform_name: str, name_mapper: TeamNameMapper):
        self.platform_name = platform_name
        self.name_mapper = name_mapper

    @abstractmethod
    def parse_events(self, raw_data_list: List[dict]) -> List[StandardEvent]:
        """將平台的原始 JSON 陣列轉換為 StandardEvent 列表"""
        pass


# ==========================================
# 4. 匹配測試 (使用範例)
# ==========================================
if __name__ == "__main__":
    mapper = TeamNameMapper()
    
    # 測試幾個常出錯的寫法
    test_names = [
        "Real Madrid", 
        "  arsenal  ", 
        "MANchester-city",
        "Bayern   Munich"
    ]
    
    print("--- 統一轉小寫與清理測試 ---")
    for name in test_names:
        clean = mapper.get_standard_name(name)
        print(f"原本: '{name}' \t-> 標準化後: '{clean}'")