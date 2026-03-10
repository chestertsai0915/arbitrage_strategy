import requests
import time

def get_all_limitless_football_markets():
    url = "https://api.limitless.exchange/markets/active/49"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }
    
    all_markets = []
    limit = 25
    page = 1  # 這次我們直接用直觀的頁碼 (Page) 來翻頁
    
    print(" 開始使用 `page` 參數自動翻頁抓取...\n")
    
    try:
        while True:
            # 改用 limit 和 page 組合
            params = {
                "limit": limit,
                "page": page
            }
            
            print(f" 正在抓取第 {page} 頁...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                current_markets = result.get('data', result) if isinstance(result, dict) else result
                
                # 如果這一頁沒有資料，代表已經抓完了
                if not current_markets:
                    print(" 這一頁為空，抓取完畢！")
                    break
                
                all_markets.extend(current_markets)
                print(f"    成功抓到 {len(current_markets)} 筆資料。")
                
                # 如果這頁拿到的資料小於 25 筆，代表這是最後一頁了
                if len(current_markets) < limit:
                    print(" 已經到達最後一頁，抓取完畢！")
                    break
                
                # 準備抓下一頁
                page += 1
                
                # 遵守速率限制，暫停 0.3 秒
                time.sleep(0.3)
                
            else:
                # 萬一連 page 都不吃，我們要把錯誤印出來看
                print(f" 第 {page} 頁請求失敗，狀態碼: {response.status_code}")
                print(f"錯誤訊息: {response.text}")
                break
                
    except Exception as e:
        print(f" 發生錯誤: {e}")

    # --- 總結報表 ---
    if all_markets:
        print("\n" + "=" * 60)
        print(f" 大功告成！全站總共抓取到 {len(all_markets)} 場足球比賽。")
        print("=" * 60)
        
        print("\n隨機預覽最後 2 場比賽：")
        for market in all_markets[-2:]:
            title = market.get('title', '未知賽事')
            slug = market.get('slug', 'N/A')
            print(f" - {title[:45]}... |  Slug: {slug[:15]}...")

if __name__ == "__main__":
    get_all_limitless_football_markets()