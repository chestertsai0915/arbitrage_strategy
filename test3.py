import requests

def test_kalshi_get_markets():
    # 官方 V2 API 端點
    url = "https://trading-api.kalshi.com/trade-api/v2/markets"
    
    # 根據官方文件，我們可以使用 limit 和 status 來篩選
    params = {
        "limit": 5,
        "status": "open" # 只抓取目前開放交易的市場
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        markets = data.get('markets', [])
        
        print(f"=== 抓取 {len(markets)} 個 Kalshi 開放市場 ===\n")
        
        for market in markets:
            ticker = market.get('ticker')
            title = market.get('title')
            
            # 價格與流動性資料 (Kalshi 以美分計價)
            last_price = market.get('last_price')
            yes_bid = market.get('yes_bid')
            yes_ask = market.get('yes_ask')
            volume = market.get('volume')
            open_interest = market.get('open_interest') # 未平倉合約數
            
            print(f" 標題: {title}")
            print(f"   代號 (Ticker): {ticker}")
            print(f"   最新成交價: {last_price}¢")
            print(f"   最佳買價 (Yes Bid): {yes_bid}¢ | 最佳賣價 (Yes Ask): {yes_ask}¢")
            print(f"   24h 交易量: {volume} | 未平倉量 (OI): {open_interest}")
            print("-" * 50)
            
    except requests.exceptions.RequestException as e:
        print(f"API 請求失敗: {e}")

test_kalshi_get_markets()