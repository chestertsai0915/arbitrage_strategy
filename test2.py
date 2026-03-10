import requests
import json

def get_active_markets(limit=5):
    # Polymarket 的公開資料主要透過 Gamma API 提供
    url = "https://gamma-api.polymarket.com/markets"
    
    # 設定參數：只抓取活躍的市場，並限制數量
    params = {
        "active": "true",
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        markets = response.json()
        
        print(f"\n=== 最新 {limit} 個活躍市場 ===")
        for i, market in enumerate(markets, 1):
            print(f"{i}. 問題: {market.get('question')}")
            print(f"   市場 ID: {market.get('id')}")
            print(f"   交易量: ${market.get('volume', '0')}")
            print("-" * 30)
            
    except requests.exceptions.RequestException as e:
        print(f"取得市場資料失敗: {e}")

get_active_markets()