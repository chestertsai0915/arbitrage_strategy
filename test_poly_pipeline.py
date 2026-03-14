import requests
import json
import time

def fetch_poly_odds_pipeline(event_id: str):
    print("="*60)
    print(f"  [Polymarket 管線啟動] 目標賽事 ID: {event_id}")
    print("="*60)

    # ==========================================
    #  步驟一：拿 Event ID 查藏寶圖 (Gamma API)
    # ==========================================
    gamma_url = f"https://gamma-api.polymarket.com/events/{event_id}"
    print(f" [1/2] 正在呼叫 Gamma API 取得市場結構...\n")
    
    try:
        response = requests.get(gamma_url, timeout=10)
        response.raise_for_status()
        event_data = response.json()
        
        title = event_data.get("title", "未知賽事")
        print(f" 賽事名稱: {title}\n")
        
        markets = event_data.get("markets", [])
        if not markets:
            print(" 這場比賽目前沒有任何市場 (Markets)。")
            return

        for market in markets:
            market_question = market.get("question", "未知盤口")
            
            #  [關鍵修復] 安全解析 outcomes 和 clobTokenIds
            raw_outcomes = market.get("outcomes", "[]")
            raw_tokens = market.get("clobTokenIds", "[]")
            
            if isinstance(raw_outcomes, str):
                try: outcomes = json.loads(raw_outcomes)
                except: outcomes = []
            else:
                outcomes = raw_outcomes
                
            if isinstance(raw_tokens, str):
                try: clob_token_ids = json.loads(raw_tokens)
                except: clob_token_ids = []
            else:
                clob_token_ids = raw_tokens

            # 確保都有資料，且長度一致才能一對一配對
            if not outcomes or not clob_token_ids or len(outcomes) != len(clob_token_ids):
                continue
                
            print(f" 發現盤口: {market_question}")
            
            # ==========================================
            #  步驟二：拿 Token ID 開寶箱查訂單簿 (CLOB API)
            # ==========================================
            for outcome, token_id in zip(outcomes, clob_token_ids):
                clob_url = "https://clob.polymarket.com/book"
                
                try:
                    time.sleep(0.2) # 禮貌性暫停，避免被鎖 IP
                    
                    clob_res = requests.get(clob_url, params={"token_id": token_id}, timeout=10)
                    clob_res.raise_for_status()
                    book_data = clob_res.json()
                    
                    bids = book_data.get("bids", [])
                    asks = book_data.get("asks", [])
                    
                    print(f"   選項 [{outcome}]")
                    print(f"      Token ID: {token_id[:10]}...{token_id[-5:]}")
                    
                    # 印出買方報價 (Bid)
                    if bids:
                        print(f"      最高買價 (Bid): 價格 {bids[-1]['price']:<6} | 數量 (Size): {bids[-1]['size']}")
                    else:
                        print(f"      目前沒有買單")
                        
                    # 印出賣方報價 (Ask) - 這是套利計算的重點！
                    if asks:
                        print(f"      最低賣價 (Ask): 價格 {asks[-1]['price']:<6} | 數量 (Size): {asks[-1]['size']}  <-- (成本與最大可下注量)")
                    else:
                        print(f"      目前沒有賣單")
                        
                    print("-" * 40)
                    
                except Exception as e:
                    print(f"   無法獲取 [{outcome}] 的訂單簿: {e}")
            
            print("*" * 50)
            
    except Exception as e:
        print(f" 發生錯誤: {e}")

if __name__ == "__main__":
    #  用你剛剛報錯的 Coventry vs Southampton 來驗證！
    TARGET_EVENT_ID = "240651" 
    
    fetch_poly_odds_pipeline(TARGET_EVENT_ID)