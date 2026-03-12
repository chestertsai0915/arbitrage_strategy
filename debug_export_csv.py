import csv
from core_matching import TeamNameMapper

# 🌟 從我們做好的模組包中匯入工具
from platforms import (
    SXBetFetcher, SXBetNormalizer,
    PolymarketFetcher, PolymarketNormalizer,
    LimitlessFetcher, LimitlessNormalizer
)

def export_all_platforms_to_csv():
    # 1. 啟動名稱標準化引擎
    mapper = TeamNameMapper()

    # 2. 準備三個平台的打工仔
    platforms = [
        ("SX Bet", SXBetFetcher(), SXBetNormalizer(mapper)),
        ("Polymarket", PolymarketFetcher(), PolymarketNormalizer(mapper)),
        ("Limitless", LimitlessFetcher(), LimitlessNormalizer(mapper))
    ]

    all_records = []

    print("="*60)
    print(" 🚀 [Debug 模式] 開始抓取全網資料並匯出 CSV...")
    print("="*60)

    # 3. 迴圈跑遍所有平台，把資料抓下來並標準化
    for platform_name, fetcher, normalizer in platforms:
        raw_data = fetcher.fetch_soccer_games()
        if not raw_data:
            print(f"⚠️ [{platform_name}] 沒有抓取到任何資料，跳過。")
            continue

        std_events = normalizer.parse_events(raw_data)
        
        # 4. 把每一個標準化物件轉成字典，準備寫入 CSV
        for event in std_events:
            record = {
                "Platform": event.platform,
                "Match_ID": event.match_id,           # 🎯 你最需要檢查的配對 ID
                "Market_Type": event.market_type,
                "Market_Name": event.market_name,
                "Home_Team": event.home_team,
                "Away_Team": event.away_team,
                "Start_Time": event.start_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "Platform_Event_ID": event.platform_event_id
            }
            all_records.append(record)

    # ==========================================
    # 5. 匯出至 CSV (使用 utf-8-sig 確保 Excel 不會亂碼)
    # ==========================================
    csv_filename = "debug_all_platforms.csv"
    
    if all_records:
        fieldnames = all_records[0].keys()
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
    export_all_platforms_to_csv()