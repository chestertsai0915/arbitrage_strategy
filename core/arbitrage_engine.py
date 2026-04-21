import itertools
import time
from datetime import datetime

# 建立全域快取字典，用於記錄已發現的套利機會，加入生命週期追蹤
seen_arbs = {}

def is_new_or_better(arb_key, roi, max_size):
    """
    檢查這個套利機會是否是全新的，或者比起上次記錄有顯著的變化。
    """
    current_time = time.time()
    
    if arb_key in seen_arbs and seen_arbs[arb_key].get('is_active', False):
        last_record = seen_arbs[arb_key]
        
        # 情況 A：ROI 變化極小，視為重複，僅更新最後見到它的時間 (Heartbeat)
        if abs(last_record['roi'] - roi) < 0.05 and \
           abs(last_record['max_size'] - max_size) < 1.0 and \
           (current_time - last_record['last_updated'] < 60):
            seen_arbs[arb_key]['last_updated'] = current_time
            return False
            
        # 情況 B：ROI/Size 有顯著變化，更新紀錄
        seen_arbs[arb_key]['last_updated'] = current_time
        seen_arbs[arb_key]['roi'] = roi
        seen_arbs[arb_key]['max_size'] = max_size
        return True
        
    # 情況 C：這是一個全新的機會，或是之前已經關閉現在又重新出現的機會
    seen_arbs[arb_key] = {
        "first_seen": current_time,
        "last_updated": current_time,
        "roi": roi,
        "max_size": max_size,
        "is_active": True  # 標記為開啟
    }
    return True

def check_and_close_opportunity(arb_key, match_id, match_title, current_cost):
    """
    檢查並結算已經消失的套利機會。
    (已移除存檔 JSON 邏輯，維持程式輕量化)
    """
    if arb_key in seen_arbs and seen_arbs[arb_key].get('is_active', False):
        current_time = time.time()
        first_seen = seen_arbs[arb_key]['first_seen']
        duration = current_time - first_seen
        
        # 標記為關閉，避免重複結算
        seen_arbs[arb_key]['is_active'] = False
        
        # 若需要觀察套利存活時間，可以把下面這行取消註解
        # print(f" ⚠️ [套利機會消失] 賽事: {match_title} | 存活時間: {duration:.2f} 秒 | 最終關閉成本: {current_cost:.4f}")


def check_all_arbitrage(match_id, match_mapping, price_memory, paper_trader=None):
    """
    核心套利引擎邏輯 (支援動態多平台、多賽果)，加入 paper_trader 串接
    """
    match_data = match_mapping[match_id]
    outcomes = match_data["outcomes"]
    num_outcomes = len(outcomes) 
    
    best_hedge_cost = float('inf')
    best_multi_cost = float('inf')
    
    # ==========================================
    #  策略一：跨平台對沖 (Yes vs No)
    # ==========================================
    for outcome in outcomes:
        platforms_available = list(price_memory[match_id][outcome].keys())
        
        for plat_A, plat_B in itertools.product(platforms_available, repeat=2):
            if plat_A == plat_B: continue 
            
            pA_data = price_memory[match_id][outcome][plat_A]
            pB_data = price_memory[match_id][outcome][plat_B]
            
            yes_price = pA_data.get("yes_price")
            no_price = pB_data.get("no_price")
            
            arb_key = f"hedge_{match_id}_{outcome}_Yes:{plat_A}_No:{plat_B}"
            
            # 判斷報價是否還存在
            if yes_price and no_price:
                cost_hedge = yes_price + no_price
                if cost_hedge < best_hedge_cost:
                    best_hedge_cost = cost_hedge
                
                if cost_hedge < 1.0:
                    # 💡 套利空間開啟或維持
                    roi = ((1.0 / cost_hedge) - 1.0) * 100
                    max_size = min(pA_data.get("yes_size", 0), pB_data.get("no_size", 0))
                    
                    if is_new_or_better(arb_key, roi, max_size):
                        # ----------------------------------------------------
                        profit = max_size * (roi / 100)
                        
                        print(f"\n [跨平台對沖套利出現!] 賽事: {match_data['title']} | 選項: {outcome} ")
                        print(f" 總成本: {cost_hedge:.4f} | ROI: +{roi:.2f}% | Max Size: {max_size:.2f} U | 淨利: {profit:.2f} U")
                        print(f"    在 {plat_A:<9} 買入 [Yes] | 成本: {yes_price:.4f}")
                        print(f"    在 {plat_B:<9} 買入 [No ] | 成本: {no_price:.4f}")
                        # ----------------------------------------------------
                        # 🌟 觸發虛擬下單 (打包資料給 Paper Trader)
                        # ----------------------------------------------------
                        # 設定最低過濾門檻 (例: ROI > 1% 才觸發模擬下單)
                        if paper_trader and roi > 0.2: 
                            arb_signal = {
                                "arb_key": arb_key,
                                "match_title": match_data['title'],
                                "strategy": "跨平台對沖 (Yes vs No)",
                                "total_cost": cost_hedge,
                                "roi_percent": roi,
                                "max_size": max_size,
                                "legs": {
                                    "Yes": {"platform": plat_A, "price": yes_price, "side": "yes", "market_hash": match_data[plat_A][outcome]},
                                    "No": {"platform": plat_B, "price": no_price, "side": "no", "market_hash": match_data[plat_B][outcome]}
                                }
                            }
                            paper_trader.execute_virtual_trade(arb_signal)
                else:
                    # 💡 套利空間關閉 (報價還在，但成本 >= 1.0)
                    check_and_close_opportunity(arb_key, match_id, match_data['title'], cost_hedge)
            else:
                # 💡 套利空間關閉 (其中一邊的流動性枯竭，掛單被吃光)
                check_and_close_opportunity(arb_key, match_id, match_data['title'], current_cost=999.0)


    # ==========================================
    # 🕵️ 策略二：跨平台組合套利 (買齊所有結果的 Yes)
    # ==========================================
    prices_by_outcome = [price_memory[match_id][outcome] for outcome in outcomes]
    
    if all(platform_prices for platform_prices in prices_by_outcome):
        platforms_available = [list(p.keys()) for p in prices_by_outcome]
        
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
                
            combo_str = "_".join(combo)
            arb_key = f"multi_{num_outcomes}way_{match_id}_{combo_str}"
            
            if valid:
                if cost_multi < best_multi_cost:
                    best_multi_cost = cost_multi
                    
                if cost_multi < 1.0:
                    # 💡 套利空間開啟或維持
                    roi = ((1.0 / cost_multi) - 1.0) * 100
                    max_size = min(sizes)
                    
                    if is_new_or_better(arb_key, roi, max_size):
                        
                        # ----------------------------------------------------
                        # 🌟 觸發虛擬下單 (打包資料給 Paper Trader)
                        # ----------------------------------------------------
                        if paper_trader and roi > 0.2:
                            legs_data = {}
                            for i, outcome in enumerate(outcomes):
                                plat = combo[i]
                                p = price_memory[match_id][outcome][plat].get("yes_price")
                                legs_data[outcome] = {
                                    "platform": plat, 
                                    "price": p,
                                    "side": "yes", # 🌟 組合套利全部都是買 Yes
                                    "market_hash": match_data[plat][outcome] # 🌟 傳入該平台的盤口ID
                                }
                                
                            arb_signal = {
                                "arb_key": arb_key,
                                "match_title": match_data['title'],
                                "strategy": f"{num_outcomes}-Way 組合套利",
                                "total_cost": cost_multi,
                                "roi_percent": roi,
                                "max_size": max_size,
                                "legs": legs_data
                            }
                            paper_trader.execute_virtual_trade(arb_signal)
                else:
                    # 💡 套利空間關閉 (報價還在，但成本 >= 1.0)
                    check_and_close_opportunity(arb_key, match_id, match_data['title'], cost_multi)
            else:
                # 💡 套利空間關閉 (有選項報價缺失)
                check_and_close_opportunity(arb_key, match_id, match_data['title'], current_cost=999.0)