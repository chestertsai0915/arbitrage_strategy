# 透過相對路徑 (.) 將各檔案中的類別匯入到這個資料夾層級
from .get_full_soccer_games_sxbet import SXBetFetcher, SXBetNormalizer
from .get_full_soccer_games_polymarket import PolymarketFetcher, PolymarketNormalizer
from .get_full_soccer_games_limitless import LimitlessFetcher, LimitlessNormalizer

# (選項) 使用 __all__ 來明確定義：當別人 import platforms 時，只開放這些類別
__all__ = [
    "SXBetFetcher",
    "SXBetNormalizer",
    "PolymarketFetcher",
    "PolymarketNormalizer",
    "LimitlessFetcher",
    "LimitlessNormalizer"
]