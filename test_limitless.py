import json
from get_full_soccer_games_limitless import LimitlessFetcher

def test_limitless_api():
    print(" 啟動 Limitless API 測試...\n")
    
    # 1. 實例化 Fetcher
    fetcher = LimitlessFetcher()
    
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
    
    first_game_data = raw_games[0]
    pretty_json = json.dumps(first_game_data, indent=4, ensure_ascii=False)
    print(pretty_json)
    print("="*50)

if __name__ == "__main__":
    test_limitless_api()