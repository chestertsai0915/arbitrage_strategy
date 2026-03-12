import json

# 🌟 呼叫 Limitless 的專屬抓取員
from platforms import LimitlessFetcher

def export_raw_limitless():
    print("="*60)
    print(" 🚀 [硬派 Debug 模式] 開始抓取 Limitless 最原始資料...")
    print("="*60)

    # 1. 派出 Fetcher (它內建了自動翻頁邏輯，會把所有活躍市場都抓回來)
    fetcher = LimitlessFetcher()
    raw_games = fetcher.fetch_soccer_games()

    if not raw_games:
        print("⚠️ 沒有抓取到 Limitless 資料，請檢查網路連線或 API 狀態。")
        return

    # 2. 將原始資料存成排版漂亮的 JSON 檔案
    json_filename = "raw_limitless_dump.json"
    
    with open(json_filename, "w", encoding="utf-8") as f:
        # indent=4 幫助排版，ensure_ascii=False 保留原始字元
        json.dump(raw_games, f, indent=4, ensure_ascii=False)

    print("\n" + "="*60)
    print(f"🎉 大功告成！總共 {len(raw_games)} 筆 Limitless 最原始的盤口資料已匯出至：{json_filename}")
    print("="*60)
    print("💡 建議使用 VS Code 打開，檢查看看除了 title 以外，有沒有更乾淨的球隊名稱欄位！")

if __name__ == "__main__":
    export_raw_limitless()