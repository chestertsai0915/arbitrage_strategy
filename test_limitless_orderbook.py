import requests
import json
import time

def fetch_limitless_group_orderbook(parent_slug: str):
    print("="*60)
    print(f" 🚀 [Limitless] 啟動群組市場 (Group Market) 解析...")
    print(f" 🔑 母賽事 Slug: {parent_slug}")
    print("="*60)
    
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    
    # ==========================================
    #  步驟一：取得母賽事結構，萃取子盤口 Slug
    # ==========================================
    market_url = f"https://api.limitless.exchange/markets/{parent_slug}"
    print(f" [1/2] 正在獲取賽事結構...")
    
    try:
        res = requests.get(market_url, headers=headers, timeout=10)
        res.raise_for_status()
        parent_data = res.json()
        
        # 檢查這是不是群組市場
        market_type = parent_data.get("marketType", "")
        if market_type != "group":
            print(f" 這似乎不是群組市場 (類型: {market_type})，可能不適用本程式邏輯。")
            
        markets = parent_data.get("markets", [])
        if not markets:
            print(" 找不到子盤口 (Markets)。")
            return
            
        print(f" 成功找到 {len(markets)} 個子盤口，準備分別獲取訂單簿...\n")
        print("-" * 50)
        
        # ==========================================
        #  步驟二：遍歷子盤口，獲取各自的 Orderbook
        # ==========================================
        for market in markets:
            title = market.get("title", "未知選項")
            child_slug = market.get("slug")
            
            if not child_slug:
                print(f" 選項 [{title}] 沒有專屬 slug，跳過。")
                continue
                
            print(f" 選項: {title} (Slug: {child_slug})")
            
            # 呼叫 Orderbook API
            ob_url = f"https://api.limitless.exchange/markets/{child_slug}/orderbook"
            
            try:
                time.sleep(0.2) # 禮貌性暫停
                ob_res = requests.get(ob_url, headers=headers, timeout=10)
                ob_res.raise_for_status()
                ob_data = ob_res.json()
                
                bids = ob_data.get("bids", [])
                asks = ob_data.get("asks", [])
                
                #  賣方報價 (這是我們「買入」這個選項的成本)
                if asks:
                    best_ask = asks[0]
                    ask_price = float(best_ask.get("price", 0))
                    ask_size = float(best_ask.get("size", 0))
                    print(f"   最低賣價 (Ask): 價格 {ask_price:.4f} (隱含勝率 {ask_price*100:.1f}%)")
                    print(f"   可買數量 (Size): {ask_size}")
                else:
                    print("   目前沒有賣單 (無流動性)")
                    
                #  買方報價 (選用，為了完整性印出)
                if bids:
                    best_bid = bids[0]
                    bid_price = float(best_bid.get("price", 0))
                    print(f"   最高買價 (Bid): 價格 {bid_price:.4f}")
                
            except Exception as e:
                print(f"   無法獲取 [{title}] 的訂單簿: {e}")
                
            print("-" * 50)

    except requests.exceptions.HTTPError as errh:
        print(f" HTTP 錯誤: {errh}")
    except Exception as e:
        print(f" 發生錯誤: {e}")

if __name__ == "__main__":
    # 使用你剛才發現的斯圖加特比賽母 Slug 來測試
    TARGET_PARENT_SLUG = "efl-champ-southampton-vs-oxford-united-mar-21-2026-1772874002650"
    fetch_limitless_group_orderbook(TARGET_PARENT_SLUG)