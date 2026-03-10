import json
# 這裡匯入我們剛剛寫好的抓取器
from get_full_soccer_game_xs_bet import SXBetFetcher

def test_sx_bet_api():
    print(" 啟動 SX Bet API 測試...\n")
    
    # 1. 實例化我們的 Fetcher
    fetcher = SXBetFetcher()
    
    # 2. 呼叫抓取功能
    raw_games = fetcher.fetch_soccer_games()
    
    # 3. 檢查結果
    if not raw_games:
        print("\n 測試失敗：沒有抓到任何資料。請檢查網路連線或 API 狀態。")
        return

    print(f"\n 測試成功！總共抓到 {len(raw_games)} 筆賽事資料。")
    print("\n" + "="*50)
    print(" 第一筆比賽的「完整原始資料 (Raw Data)」預覽：")
    print("="*50)
    
    # 使用 json.dumps 搭配 indent=4，讓字典的輸出呈現漂亮的縮排格式
    first_game_data = raw_games[0]
    pretty_json = json.dumps(first_game_data, indent=4, ensure_ascii=False)
    print(pretty_json)
    print("="*50)

if __name__ == "__main__":
    test_sx_bet_api()