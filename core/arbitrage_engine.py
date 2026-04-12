import itertools
import os
from datetime import datetime


from envs.got.Lib import json

def check_all_arbitrage(match_id, match_mapping, price_memory):
    """
    核心套利引擎邏輯 (支援動態多平台、多賽果)
    :param match_id: 觸發更新的賽事 ID
    :param match_mapping: 賽事與 Hash/Slug 的對應表
    :param price_memory: 當前所有平台的最新報價與深度
    """
    match_data = match_mapping[match_id]
    outcomes = match_data["outcomes"]
    num_outcomes = len(outcomes) # 動態判斷這場比賽有幾個結果 (通常是 2 或 3)
    
    best_hedge_cost = float('inf')
    best_multi_cost = float('inf')
    
    # ==========================================
    #  策略一：跨平台對沖 (Yes vs No)
    # 邏輯：在 A 平台買「會發生」，在 B 平台買「不會發生」
    # ==========================================
    for outcome in outcomes:
        # 動態抓取目前這場比賽、這個選項，有哪幾家平台已經送報價來了
        platforms_available = list(price_memory[match_id][outcome].keys())
        
        # 就算有 3 家、4 家平台，itertools 都會自動幫我們算出所有「兩兩配對」
        for plat_A, plat_B in itertools.product(platforms_available, repeat=2):
            if plat_A == plat_B: continue # 避免同平台對沖
            
            pA_data = price_memory[match_id][outcome][plat_A]
            pB_data = price_memory[match_id][outcome][plat_B]
            
            yes_price = pA_data.get("yes_price")
            no_price = pB_data.get("no_price")
            
            if yes_price and no_price:
                cost_hedge = yes_price + no_price
                if cost_hedge < best_hedge_cost:
                    best_hedge_cost = cost_hedge
                
                #  觸發對沖套利
                if cost_hedge < 1.0:
                    roi = ((1.0 / cost_hedge) - 1.0) * 100
                    max_size = min(pA_data.get("yes_size", 0), pB_data.get("no_size", 0))
                    profit = max_size * (roi / 100)
                    
                    print(f"\n [跨平台對沖套利出現!] 賽事: {match_data['title']} | 選項: {outcome} ")
                    print(f" 總成本: {cost_hedge:.4f} | ROI: +{roi:.2f}% | Max Size: {max_size:.2f} U | 淨利: {profit:.2f} U")
                    print(f"    在 {plat_A:<9} 買入 [Yes] | 成本: {yes_price:.4f}")
                    print(f"    在 {plat_B:<9} 買入 [No ] | 成本: {no_price:.4f}")
                    print("-" * 50)


    # ==========================================
    # 🕵️ 策略二：跨平台組合套利 (買齊所有結果的 Yes)
    # 邏輯：湊齊 Home, Away, Draw 的 Yes，保證 100% 中獎
    # ==========================================
    prices_by_outcome = [price_memory[match_id][outcome] for outcome in outcomes]
    
    # 必須確保每個選項 (主/客/和) 至少有一家平台有報價才計算
    if all(platform_prices for platform_prices in prices_by_outcome):
        platforms_available = [list(p.keys()) for p in prices_by_outcome]
        
        # 這裡會依據 outcomes 的數量 (2或3) 以及平台的數量，自動展開所有可能的交叉組合矩陣！
        for combo in itertools.product(*platforms_available):
            cost_multi = 0.0
            sizes = []
            valid = True
            
            for i, outcome in enumerate(outcomes):
                plat = combo[i]
                yes_price = price_memory[match_id][outcome][plat].get("yes_price")
                yes_size = price_memory[match_id][outcome][plat].get("yes_size", 0)
                
                if not yes_price:
                    valid = False
                    break
                cost_multi += yes_price
                sizes.append(yes_size)
                
            if valid:
                if cost_multi < best_multi_cost:
                    best_multi_cost = cost_multi
                    
                #  觸發組合套利
                if cost_multi < 1.0:
                    roi = ((1.0 / cost_multi) - 1.0) * 100
                    max_size = min(sizes)
                    profit = max_size * (roi / 100)
                    
                    # 標題自動顯示是 2-Way 還是 3-Way
                    print(f"\n [{num_outcomes}-Way 組合套利出現!] 賽事: {match_data['title']} ")
                    print(f" 總成本: {cost_multi:.4f} | ROI: +{roi:.2f}% | Max Size: {max_size:.2f} U | 淨利: {profit:.2f} U")
                    for i, outcome in enumerate(outcomes):
                        plat = combo[i]
                        p = price_memory[match_id][outcome][plat].get("yes_price")
                        print(f"    在 {plat:<9} 買入 [{outcome:<15}] (Yes) | 成本: {p:.4f}")
                    if roi>3:
                        os.makedirs(f"arbitrage_opportunities", exist_ok=True)
                        # 取得目前時間，格式為：20231027_143005 (年月日_時分秒)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        with open(f"arbitrage_opportunities/{match_id}_{num_outcomes}way_{timestamp}.json", "w", encoding="utf-8") as f:
                            json.dump({
                                "match_id": match_id,
                                "match_title": match_data['title'],
                                "strategy": f"{num_outcomes}-Way 組合套利",
                                "total_cost": cost_multi,
                                "roi_percent": roi,
                                "max_size": max_size,
                                "profit": profit,
                                "match_data": match_data,
                                "price_memory": price_memory[match_id]
                            }, f, indent=4, ensure_ascii=False)

                    print("-" * 50)