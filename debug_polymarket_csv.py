import json

# 🌟 我們這次連 Normalizer 都不用，純粹叫 Fetcher 去把原始資料搬回來
from platforms import PolymarketFetcher

def export_raw_polymarket():
    print("="*60)
    print(" 🚀 [硬派 Debug 模式] 開始抓取 Polymarket 最原始資料...")
    print("="*60)

    # 1. 派出 Fetcher
    fetcher = PolymarketFetcher()
    raw_games = fetcher.fetch_soccer_games()

    if not raw_games:
        print("⚠️ 沒有抓取到 Polymarket 資料，請檢查連線或 API。")
        return

    # 2. 直接把這包原始資料存成排版漂亮的 JSON 檔案
    json_filename = "raw_polymarket_dump.json"
    
    with open(json_filename, "w", encoding="utf-8") as f:
        # indent=4 會幫你把括號和縮排排得整整齊齊，ensure_ascii=False 確保中文字元正常顯示
        json.dump(raw_games, f, indent=4, ensure_ascii=False)

    print("\n" + "="*60)
    print(f"🎉 大功告成！總共 {len(raw_games)} 筆最原始的賽事資料已匯出至：{json_filename}")
    print("="*60)
    print("💡 建議使用 VS Code 打開此檔案，可以方便地折疊/展開各個欄位來觀察。")

if __name__ == "__main__":
    export_raw_polymarket()