# models/match.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StandardEvent:
    """標準化的比賽資料結構"""
    home_team: str          
    away_team: str          
    start_time: datetime    
    platform: str           
    platform_event_id: str  
    market_type: str        # 玩法類型 (例如: "moneyline", "spread", "total")
    market_name: str        # 具體的盤口名稱 (例如: "Over 2.5", "Atletico Madrid -1")
    raw_data: dict          

    @property
    def match_id(self) -> str:
        date_str = self.start_time.strftime("%Y-%m-%d")
        return f"{self.home_team}_{self.away_team}_{date_str}"