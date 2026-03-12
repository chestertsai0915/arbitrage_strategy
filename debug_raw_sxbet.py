import json

# 🌟 這次我們派出 SX Bet 的抓取員，一樣不經過轉換器
from platforms import SXBetFetcher

def export_raw_sxbet():
    print("="*60)
    print(" 🚀 [硬派 Debug 模式] 開始抓取 SX Bet 最原始資料...")
    print("="*60)

    # 1. 派出 Fetcher
    fetcher = SXBetFetcher()
    raw_games = fetcher.fetch_soccer_games()

    if not raw_games:
        print("⚠️ 沒有抓取到 SX Bet 資料，請檢查網路連線或 API 狀態。")
        return

    # 2. 將原始資料存成排版漂亮的 JSON 檔案
    json_filename = "raw_sxbet_dump.json"
    
    with open(json_filename, "w", encoding="utf-8") as f:
        # indent=4 幫助我們自動縮排，ensure_ascii=False 確保文字不變亂碼
        json.dump(raw_games, f, indent=4, ensure_ascii=False)

    print("\n" + "="*60)
    print(f"🎉 大功告成！總共 {len(raw_games)} 筆 SX Bet 最原始的盤口資料已匯出至：{json_filename}")
    print("="*60)
    print("💡 建議使用 VS Code 打開，可以用關鍵字搜尋特定球隊來觀察它的完整結構。")

if __name__ == "__main__":
    export_raw_sxbet()