# 匯入我們寫好的核心與各平台模組
from core_matching import TeamNameMapper
from get_full_soccer_game_xs_bet import SXBetFetcher, SXBetNormalizer
from fin_poly_soccer_games import PolymarketFetcher, PolymarketNormalizer
from get_full_soccer_games_limitless import LimitlessFetcher, LimitlessNormalizer

def test_all_parsers():
    # 1. 啟動名稱標準化引擎
    mapper = TeamNameMapper()

    # ==========================================
    # 測試 1: SX Bet
    # ==========================================
    print("="*60)
    print(" 啟動測試 1：SX Bet 解析")
    print("="*60)
    sx_fetcher = SXBetFetcher()
    sx_normalizer = SXBetNormalizer(mapper)
    
    sx_raw = sx_fetcher.fetch_soccer_games()
    if sx_raw:
        sx_std = sx_normalizer.parse_events(sx_raw)
        print(f"\n[SX Bet] 成功解析 {len(sx_std)} 筆賽事。前 3 筆結果：")
        for g in sx_std[:3]:
            print(f" 👉 主場: {g.home_team:<15} | 客場: {g.away_team:<15}")
            print(f"    全局匹配ID: {g.match_id}")
            print("-" * 40)

    # ==========================================
    # 測試 2: Polymarket
    # ==========================================
    print("\n" + "="*60)
    print(" 啟動測試 2：Polymarket 解析")
    print("="*60)
    poly_fetcher = PolymarketFetcher()
    poly_normalizer = PolymarketNormalizer(mapper)
    
    poly_raw = poly_fetcher.fetch_soccer_games()
    if poly_raw:
        poly_std = poly_normalizer.parse_events(poly_raw)
        print(f"\n[Polymarket] 成功解析 {len(poly_std)} 筆賽事。前 3 筆結果：")
        for g in poly_std[:3]:
            # 為了方便對照，我們把原始標題也印出來
            print(f" 📦 原始標題: {g.raw_data.get('title')}")
            print(f" 👉 主場: {g.home_team:<15} | 客場: {g.away_team:<15}")
            print(f"    全局匹配ID: {g.match_id}")
            print("-" * 40)

    # ==========================================
    # 測試 3: Limitless
    # ==========================================
    print("\n" + "="*60)
    print(" 啟動測試 3：Limitless 解析")
    print("="*60)
    limit_fetcher = LimitlessFetcher()
    limit_normalizer = LimitlessNormalizer(mapper)
    
    limit_raw = limit_fetcher.fetch_soccer_games()
    if limit_raw:
        limit_std = limit_normalizer.parse_events(limit_raw)
        print(f"\n[Limitless] 成功解析 {len(limit_std)} 筆賽事。前 3 筆結果：")
        for g in limit_std[:3]:
            print(f" 📦 原始標題: {g.raw_data.get('title')}")
            print(f" 👉 主場: {g.home_team:<15} | 客場: {g.away_team:<15}")
            print(f"    全局匹配ID: {g.match_id}")
            print("-" * 40)

if __name__ == "__main__":
    test_all_parsers()