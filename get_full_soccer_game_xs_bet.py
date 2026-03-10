import requests
import time
from datetime import datetime

def get_all_soccer_markets():
    base_url = "https://api.sx.bet"
    endpoint = f"{base_url}/markets/active"
    headers = {"Accept": "application/json"}
    
    # 準備一個空的清單，用來收集每一頁的比賽
    all_soccer_markets = []
    
    # 初始的下一頁鑰匙是空的
    next_key = None
    page_count = 1
    
    print(" 開始向 SX Bet 請求所有足球 (Soccer) 活躍主盤口...\n")
    
    while True:
        # 基本參數
        params = {
            "sportIds": 5, 
            "onlyMainLine": "true",
            "pageSize": 50
        }
        
        # 如果有 next_key (代表要抓第二頁以後)，就把 paginationKey 塞進參數裡
        if next_key:
            params["paginationKey"] = next_key
            
        try:
            print(f" 正在抓取第 {page_count} 頁...")
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                data = result.get('data', {})
                
                # 拿出這一頁的比賽
                current_page_markets = data.get('markets', [])
                all_soccer_markets.extend(current_page_markets) # 把這一頁的比賽裝進總清單
                
                # 更新 next_key
                next_key = data.get('nextKey')
                
                # 如果 next_key 是空的 (None 或空字串)，代表已經沒有下一頁了
                if not next_key:
                    print(" 已經抓取到最後一頁！")
                    break
                
                page_count += 1
                
                # 為了保護你的 IP 不被 API 伺服器因為「請求過快」而封鎖，稍微暫停一下
                time.sleep(0.5) 
                
            else:
                print(f" 第 {page_count} 頁請求失敗，狀態碼: {response.status_code}")
                break
                
        except Exception as e:
            print(f" 發生錯誤: {e}")
            break

    # --- 迴圈結束，開始印出總結果 ---
    if all_soccer_markets:
        print("\n" + "="*70)
        print(f" 大功告成！總共抓取到 {len(all_soccer_markets)} 場足球賽事。")
        print("="*70)
        
        # 預覽前 5 筆跟最後 5 筆來確認資料
        print(f"\n--- 前 3 場比賽預覽 ---")
        for market in all_soccer_markets[:3]:
            print(f"{market.get('teamOneName')} vs {market.get('teamTwoName')} | {market.get('leagueLabel')}")
            
        print(f"\n--- 最後 3 場比賽預覽 ---")
        for market in all_soccer_markets[-3:]:
            print(f"{market.get('teamOneName')} vs {market.get('teamTwoName')} | {market.get('leagueLabel')}")
            
        print("\n 你現在擁有完整的足球比賽清單了！")
        # 挑選第一場比賽的 Hash 供下一步使用
        print(f" 範例 Market Hash: {all_soccer_markets[0].get('marketHash')}")

if __name__ == "__main__":
    get_all_soccer_markets()