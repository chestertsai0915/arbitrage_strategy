# platforms/base.py
from abc import ABC, abstractmethod
from typing import List
# 假設你已經建立了 models 資料夾
from models.match import StandardEvent 
from models.orderbook import Orderbook
from utils.team_mapping import TeamNameMapper

class BasePlatformAPI(ABC):
    """所有平台 API 的統一模板"""
    
    def __init__(self, platform_name: str, name_mapper: TeamNameMapper):
        self.platform_name = platform_name
        self.name_mapper = name_mapper

    @abstractmethod
    def get_matches(self) -> List[StandardEvent]:
        """功能 1：獲取該平台所有活躍的足球比賽，並回傳標準化格式"""
        pass

    @abstractmethod
    def get_orderbook(self, market_id: str) -> Orderbook:
        """功能 2：輸入平台的賽事 ID，獲取該賽事的 Orderbook，並回傳標準化格式"""
        pass

