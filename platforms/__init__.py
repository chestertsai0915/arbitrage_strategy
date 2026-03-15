from .sxbet import SXBetAPI
from .polymarket import PolymarketAPI
from .limitless import LimitlessAPI

# 2. 🌟 建立平台註冊表 (Registry)
# 未來如果有新平台 (例如 BinanceAPI)，只要 import 進來並把它塞進這個 List 即可
AVAILABLE_PLATFORMS = [
    SXBetAPI,
    PolymarketAPI,
    LimitlessAPI
]

# 3. 使用 __all__ 限制外部 import 的內容
__all__ = [
    "AVAILABLE_PLATFORMS",
    "SXBetAPI",
    "PolymarketAPI",
    "LimitlessAPI"
]