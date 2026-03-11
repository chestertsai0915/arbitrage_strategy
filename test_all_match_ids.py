import csv
from core_matching import TeamNameMapper
from get_full_soccer_game_xs_bet import SXBetFetcher, SXBetNormalizer
from fin_poly_soccer_games import PolymarketFetcher, PolymarketNormalizer
from get_full_soccer_games_limitless import LimitlessFetcher, LimitlessNormalizer

def export_all_match_ids_to_csv():
    # 啟動名稱標準化引擎
    mapper = TeamNameMapper()

    # 建立一個清單，把三個平台打包起來方便使用迴圈處理
    platforms = [
        ("SX Bet", SXBetFetcher(), SXBetNormalizer(mapper)),
        ("Polymarket", PolymarketFetcher(), PolymarketNormalizer(mapper)),
        ("Limitless", LimitlessFetcher(), LimitlessNormalizer(mapper))
    ]

    all_records = []

    print("="*60)
    print("  開始抓取並準備匯出資料...")
    print("="*60)

    for platform_name, fetcher, normalizer in platforms:
        # 1. 抓取原始資料
        raw_data = fetcher.fetch_soccer_games()
        if not raw_data:
            print(f"[{platform_name}] 沒有抓取到任何資料，跳過。")
            continue

        # 2. 轉換為標準格式
        std_events = normalizer.parse_events(raw_data)
        
        # 3. 把標準化後的物件轉換成字典，準備寫入 CSV
        for event in std_events:
            record = {
                "Platform": event.platform,
                "Match_ID": event.match_id,
                "Market_Type": event.market_type,
                "Home_Team": event.home_team,
                "Away_Team": event.away_team,
                "Start_Time": event.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Market_Name": event.market_name,
                "Platform_Event_ID": event.platform_event_id
            }
            all_records.append(record)

    # ==========================================
    # 匯出至 CSV
    # ==========================================
    csv_filename = "all_markets_exported.csv"
    
    if all_records:
        # 取得字典的 keys 作為 CSV 的標題列 (Header)
        fieldnames = all_records[0].keys()
        
        # 使用 utf-8-sig 確保 Excel 打開不會亂碼
        with open(csv_filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)
            
        print("\n" + "="*60)
        print(f"🎉 大功告成！成功將 {len(all_records)} 筆盤口資料匯出至檔案：{csv_filename}")
        print("="*60)
    else:
        print("\n 糟糕，沒有收集到任何資料，無法產生 CSV 檔案。")

if __name__ == "__main__":
    export_all_match_ids_to_csv()