import requests

def get_best_odds_for_market(market_hash):
    endpoint = "https://api.sx.bet/orders"
    
    # 完全依照你貼的文件設定參數
    params = {
        "marketHashes": market_hash, # 注意這裡是複數
        "perPage": 1000              # 一次最多拿 1000 筆掛單
    }
    
    print(f" 正在分析 Market Hash: {market_hash[:10]}... 的盤口\n")
    
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            # 根據文件，回傳的直接是 data 陣列
            orders = result.get('data', [])
            
            if not orders:
                print("📭 這場比賽目前沒有任何掛單。")
                return
            
            print(f" 成功抓取到 {len(orders)} 筆掛單！正在計算最佳賠率...\n")
            
            # 用來儲存你要下注 選項1 或 選項2 的所有可用賠率
            odds_for_outcome_1 = []
            odds_for_outcome_2 = []
            
            for order in orders:
                # 排除已經被完全買光的單 (fillAmount == totalBetSize)
                if int(order.get('fillAmount', 0)) >= int(order.get('totalBetSize', 0)):
                    continue
                
                is_maker_outcome_one = order.get('isMakerBettingOutcomeOne')
                
                # 計算 Taker (你) 的實際歐洲賠率
                raw_odds = int(order.get('percentageOdds', 0))
                maker_implied_prob = raw_odds / (10 ** 20)
                taker_implied_prob = 1 - maker_implied_prob
                
                if taker_implied_prob <= 0:
                    continue
                    
                decimal_odds = 1 / taker_implied_prob
                
                # 分類：如果你要押選項 1，你要找 Maker 押選項 2 的單 (is_maker_outcome_one == False)
                if is_maker_outcome_one is False:
                    odds_for_outcome_1.append(decimal_odds)
                else:
                    # 如果你要押選項 2，你要找 Maker 押選項 1 的單
                    odds_for_outcome_2.append(decimal_odds)
            
            # 找出最高賠率
            best_odd_1 = max(odds_for_outcome_1) if odds_for_outcome_1 else 0
            best_odd_2 = max(odds_for_outcome_2) if odds_for_outcome_2 else 0
            
            print(" 目前市場最佳賠率 (Best Odds)：")
            print("-" * 40)
            print(f"如果你想下注【選項 1 (主隊)】: 最高賠率 {best_odd_1:.2f} 倍")
            print(f"如果你想下注【選項 2 (客隊)】: 最高賠率 {best_odd_2:.2f} 倍")
            print("-" * 40)

        else:
            print(f" 請求失敗，狀態碼: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f" 發生錯誤: {e}")

if __name__ == "__main__":
    # 使用你剛才的熱刺 vs 水晶宮的 Hash
    target_hash = "0x079d236524fe9b0978599414e51b5476c252368b9c83f82ae668f52359642953"
    get_best_odds_for_market(target_hash)