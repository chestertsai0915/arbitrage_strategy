# 引入各個平台的 Connector
from .sx_connector import SXBetConnector
from .poly_connector import PolyConnector
from .limitless_connector import LimitlessConnector

# 提供列表格式 (給需要遍歷所有 Connector 的情境使用)
AVAILABLE_CONNECTORS = [
    SXBetConnector,
    PolyConnector,
   # LimitlessConnector
]

#  超級好用的對應表：直接把 JSON 裡的字串對應到真實的 Class
CONNECTOR_MAP = {
    "SX_BET": SXBetConnector,
    "POLY": PolyConnector,
    "LIMITLESS": LimitlessConnector
}

# 限制外部使用 from package import * 時能拿到什麼
__all__ = [
    "AVAILABLE_CONNECTORS",
    "CONNECTOR_MAP",
    "SXBetConnector",
    "PolyConnector",
    "LimitlessConnector"
]