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
    home_team: str          # 標準化後的主場球隊名稱 (已全小寫)
    away_team: str          # 標準化後的客場球隊名稱 (已全小寫)
    start_time: datetime    # 比賽開始時間
    platform: str           # 來源平台
    platform_event_id: str  # 該平台上的原始比賽 ID
    raw_data: dict          # 保留原始資料以供除錯

    @property
    def match_id(self) -> str:
        """產生一個唯一的比賽 ID，用來將不同平台的同一場比賽分組"""
        # 取出日期的部分，例如: "2024-05-12"
        date_str = self.start_time.strftime("%Y-%m-%d")
        
        # 組合 ID: home_away_date
        return f"{self.home_team}_{self.away_team}_{date_str}"


# ==========================================
# 2. 名稱標準化引擎 (簡化版)
# ==========================================
class TeamNameMapper:
    def get_standard_name(self, raw_name: str) -> str:
        if not raw_name: return "unknown"
        
        # 1. 轉小寫並去除頭尾空白
        clean = raw_name.lower().strip()
        
        # 2. 移除常見的足球隊尾綴雜訊 (例如 fc, cf, afc)
        # 用正則表達式把字尾獨立的 fc 拿掉 (例如 "portsmouth fc" -> "portsmouth")
        clean = re.sub(r'\b(fc|cf|afc|united)\b', '', clean).strip()
        
        # 3. 把連續空白或符號換成底線
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