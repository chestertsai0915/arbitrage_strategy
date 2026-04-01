from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import time

@dataclass
class OrderLevel:
    """單一價格層級 (Price Level)"""
    price: float  # 統一使用「隱含機率 (0~1)」，例如 0.29。代表買 1 塊錢的合約成本是 0.29 塊。
    size: float   # 數量 (統一為合約股數/預期獲利總額，1 單位 = 1 USD)

@dataclass
class Orderbook:
    platform: str
    match_id: str
    market_id: str
    selection: str
    bids: List[OrderLevel] = field(default_factory=list)
    asks: List[OrderLevel] = field(default_factory=list)
    local_timestamp: float = field(default_factory=lambda: time.time())

    def __post_init__(self):
        """不管各家 API 回傳什麼順序，進來模型後統一強制重新排序"""
        
        # Bids: 別人想買的價格。我們想賣給出價「最高」的人，所以由大排到小 (reverse=True)
        # 排序後，bids[0] 就是 Best Bid
        self.bids.sort(key=lambda x: x.price, reverse=True)
        
        # Asks: 別人想賣的價格。我們想跟開價「最低」的人買，所以由小排到大
        # 排序後，asks[0] 就是 Best Ask (我們的最低買入成本)
        self.asks.sort(key=lambda x: x.price)

    @property
    def best_bid(self) -> Optional[OrderLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderLevel]:
        return self.asks[0] if self.asks else None

    def get_vwap_ask(self, target_size: float) -> Optional[float]:
        """
        [進階功能] 計算吃到指定數量 (target_size) 時的成交均價 (VWAP)
        這在套利中非常重要！因為最佳賣價可能只有 $10 的深度，你想買 $100 就會吃到更差的價格。
        """
        if not self.asks:
            return None
            
        accumulated_size = 0.0
        total_cost = 0.0
        
        for ask in self.asks:
            # 還差多少數量才滿
            remaining = target_size - accumulated_size
            
            if ask.size >= remaining:
                # 這個價格層級的深度足夠吃滿剩下的量
                total_cost += remaining * ask.price
                accumulated_size += remaining
                break
            else:
                # 這個價格層級的深度不夠，全部吃光，繼續看下一層
                total_cost += ask.size * ask.price
                accumulated_size += ask.size
                
        # 如果把整個 Orderbook 吃穿了都不夠 target_size，回傳 None 或發出警告
        if accumulated_size < target_size:
            return None 
            
        return total_cost / target_size