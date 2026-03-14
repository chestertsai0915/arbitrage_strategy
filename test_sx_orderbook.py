import requests
import json

def fetch_specific_sx_orderbook(market_hash: str):
    print("="*60)
    print(f"  [SX Bet] 正在查詢指定 Market Hash 的訂單簿...")
    print(f"  目標 Hash: {market_hash}")
    print("="*60)
    
    url = "https://api.sx.bet/orders"
    params = {
        "marketHashes": market_hash, # 注意：官方文件寫的是 marketHashes (有s)
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        orders = data.get("data", [])
        
        print(f" 成功連線！這場比賽目前共有 {len(orders)} 筆掛單等待被吃。\n")
        
        if not orders:
            print(" 目前沒有掛單。")
            
            
        outcome_1_odds = [] 
        outcome_2_odds = [] 
        
        for order in orders:
            # 1. 計算剩餘數量 (區塊鏈原始單位)
            total_bet_size = float(order.get("totalBetSize", 0))
            fill_amount = float(order.get("fillAmount", 0))
            remaining_raw = total_bet_size - fill_amount
            
            if remaining_raw <= 0:
                continue # 已經被買光的單就跳過
                
            # 這是 Maker (掛單者) 剩餘的本金
            remaining_maker_usdc = remaining_raw / (10**6)
            
            # 2. 核心數學：計算雙方的隱含勝率
            percentage_odds_raw = float(order.get("percentageOdds", 0))
            maker_implied_prob = percentage_odds_raw / (10**20)  # 掛單者的勝率
            taker_implied_prob = 1 - maker_implied_prob          # 我們的勝率 (Price)
            
            # 避免除以零的錯誤
            if maker_implied_prob <= 0 or taker_implied_prob <= 0:
                continue
                
            # 算網頁常見的小數點賠率 (例如 2.50)
            taker_decimal_odds = 1 / taker_implied_prob 
            
            # 🌟 3. 將 Maker 的本金，換算成網頁上顯示的「我們可下注的最大金額 (Taker Size)」
            taker_size = remaining_maker_usdc * (taker_implied_prob / maker_implied_prob)
            
            # 4. 分類邏輯：Maker 賭一邊，我們接單就是賭另一邊
            is_maker_outcome_one = order.get("isMakerBettingOutcomeOne", False)
            
            order_info = {
                "implied_prob": taker_implied_prob,  # 用來算套利的成本 (0~1)
                "decimal_odds": taker_decimal_odds,  # 用來給人看的賠率 (大於1)
                "size": taker_size,                  #  這就是網頁上顯示的可下注金額！
                "base_token": order.get("baseToken", "")
            }
            
            if is_maker_outcome_one:
                # Maker 買 Outcome 1，我們接單是買 Outcome 2
                outcome_2_odds.append(order_info)
            else:
                # Maker 買 Outcome 2，我們接單是買 Outcome 1
                outcome_1_odds.append(order_info)
        
        # 排序：對我們來說，買入成本 (Price) 越低越好！
        outcome_1_odds.sort(key=lambda x: x["decimal_odds"])
        outcome_2_odds.sort(key=lambda x: x["decimal_odds"])
        
        print(" 訂單簿深度 (最佳接單價):")
        
        print("\n   如果你要下注 [Outcome 1]:")
        if outcome_1_odds:
            best = outcome_1_odds[0]
            print(f"      最低買入成本(Ask): {best['decimal_odds']:.4f} (隱含勝率 {best['implied_prob']*100:.1f}%)")
            print(f"      可買數量 (預估 USDC): ${best['size']:,.2f}") 
        else:
            print("      目前沒有人開單讓你買 Outcome 1")

        print("\n   如果你要下注 [Outcome 2]:")
        if outcome_2_odds:
            best = outcome_2_odds[0]
            print(f"      最低買入成本(Ask): {best['decimal_odds']:.4f} (隱含勝率 {best['implied_prob']*100:.1f}%)")
            print(f"     可買數量 (預估 USDC): ${best['size']:,.2f}")
        else:
            print("      目前沒有人開單讓你買 Outcome 2")

    except Exception as e:
        print(f" 發生錯誤: {e}")

if __name__ == "__main__":
    TARGET_MARKET_HASH = "0x3c9f3ad8322d372bfb3a0139ebd37bf51f9ac9903960642d934538ce488d30e2"
    fetch_specific_sx_orderbook(TARGET_MARKET_HASH)